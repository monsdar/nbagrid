"""
Tracing utilities for NBA Grid API.

This module provides easy-to-use decorators and context managers for adding
OpenTelemetry tracing to your application code.
"""

import time
from functools import wraps
from contextlib import contextmanager
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode


def trace_function(operation_name, **attributes):
    """
    Decorator to trace function execution with OpenTelemetry.
    
    Args:
        operation_name (str): Name of the operation being traced
        **attributes: Additional attributes to add to the span
    
    Example:
        @trace_function("player_search", search_term="lebron")
        def search_players(name):
            # Function implementation
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            
            with tracer.start_as_current_span(operation_name, attributes=attributes) as span:
                # Add function metadata
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)
                
                # Add arguments as attributes (be careful with sensitive data)
                if args:
                    span.set_attribute("function.args_count", len(args))
                if kwargs:
                    # Only add non-sensitive kwargs
                    safe_kwargs = {k: str(v) for k, v in kwargs.items() 
                                 if not k.lower() in ['password', 'token', 'secret', 'key']}
                    for k, v in safe_kwargs.items():
                        span.set_attribute(f"function.kwarg.{k}", v)
                
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    execution_time = time.time() - start_time
                    
                    # Record success
                    span.set_attribute("operation.success", True)
                    span.set_attribute("operation.execution_time_ms", execution_time * 1000)
                    span.set_status(Status(StatusCode.OK))
                    
                    return result
                    
                except Exception as e:
                    execution_time = time.time() - start_time
                    
                    # Record failure
                    span.set_attribute("operation.success", False)
                    span.set_attribute("operation.execution_time_ms", execution_time * 1000)
                    span.set_attribute("operation.error", str(e))
                    span.set_attribute("operation.error_type", type(e).__name__)
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    
                    raise
                    
        return wrapper
    return decorator


@contextmanager
def trace_operation(operation_name, **attributes):
    """
    Context manager for tracing operations with OpenTelemetry.
    
    Args:
        operation_name (str): Name of the operation being traced
        **attributes: Additional attributes to add to the span
    
    Example:
        with trace_operation("database_query", table="players", operation="select"):
            # Database operation code
            players = Player.objects.filter(name__icontains=name)
    """
    print(f"Creating trace operation: {operation_name}")
    tracer = trace.get_tracer(__name__)
    
    with tracer.start_as_current_span(operation_name, attributes=attributes) as span:
        # Check if this is a real span or a NonRecordingSpan
        if hasattr(span, 'name') and span.name:
            print(f"Operation span created: {span.name} with ID: {span.get_span_context().span_id}")
        else:
            print(f"NonRecordingSpan created for operation: {operation_name}")
        
        start_time = time.time()
        try:
            yield span
            execution_time = time.time() - start_time
            
            # Record success
            if hasattr(span, 'set_attribute'):
                span.set_attribute("operation.success", True)
                span.set_attribute("operation.execution_time_ms", execution_time * 1000)
                span.set_status(Status(StatusCode.OK))
            
            print(f"Operation {operation_name} completed successfully in {execution_time*1000:.2f}ms")
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            # Record failure
            if hasattr(span, 'set_attribute'):
                span.set_attribute("operation.success", False)
                span.set_attribute("operation.execution_time_ms", execution_time * 1000)
                span.set_attribute("operation.error", str(e))
                span.set_attribute("operation.error_type", type(e).__name__)
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
            
            print(f"Operation {operation_name} failed: {e}")
            raise


def trace_database_query(query_type, table=None, **attributes):
    """
    Decorator specifically for tracing database operations.
    
    Args:
        query_type (str): Type of database operation (select, insert, update, delete)
        table (str): Database table being operated on
        **attributes: Additional attributes to add to the span
    
    Example:
        @trace_database_query("select", table="players")
        def get_player_by_name(name):
            return Player.objects.filter(name__icontains=name)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            
            # Create database-specific attributes
            db_attributes = {
                "db.system": "sqlite" if "sqlite" in str(args) else "postgresql",
                "db.operation": query_type,
                "db.table": table,
                **attributes
            }
            
            with tracer.start_as_current_span(f"db.{query_type}", attributes=db_attributes) as span:
                # Check if this is a real span or a NonRecordingSpan
                if hasattr(span, 'name') and span.name:
                    print(f"Database span created: {span.name} with ID: {span.get_span_context().span_id}")
                else:
                    print(f"NonRecordingSpan created for database operation: {query_type}")
                
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    execution_time = time.time() - start_time
                    
                    # Record success
                    if hasattr(span, 'set_attribute'):
                        span.set_attribute("operation.success", True)
                        span.set_attribute("operation.execution_time_ms", execution_time * 1000)
                        span.set_attribute("db.result_count", len(result) if hasattr(result, '__len__') else 1)
                        span.set_status(Status(StatusCode.OK))
                    
                    print(f"Database operation {query_type} completed successfully in {execution_time*1000:.2f}ms")
                    return result
                    
                except Exception as e:
                    execution_time = time.time() - start_time
                    
                    # Record failure
                    if hasattr(span, 'set_attribute'):
                        span.set_attribute("operation.success", False)
                        span.set_attribute("operation.execution_time_ms", execution_time * 1000)
                        span.set_attribute("operation.error", str(e))
                        span.set_attribute("operation.error_type", type(e).__name__)
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                    
                    print(f"Database operation {query_type} failed: {e}")
                    raise
                    
        return wrapper
    return decorator


def trace_view(view_name, **attributes):
    """
    Decorator specifically for tracing Django views.
    
    Args:
        view_name (str): Name of the view being traced
        **attributes: Additional attributes to add to the span
    
    Example:
        @trace_view("player_search", endpoint="/search-players/")
        def search_players(request):
            # View implementation
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            print(f"Creating trace for view: {view_name}")
            tracer = trace.get_tracer(__name__)
            
            # Create view-specific attributes
            view_attributes = {
                "http.route": getattr(request, 'resolver_match', None) and getattr(request.resolver_match, 'route', ''),
                "http.method": request.method,
                "http.url": request.build_absolute_uri(),
                "user.id": getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
                "session.id": request.session.session_key if hasattr(request, 'session') else None,
                **attributes
            }
            
            print(f"View attributes: {view_attributes}")
            
            with tracer.start_as_current_span(f"view.{view_name}", attributes=view_attributes) as span:
                # Check if this is a real span or a NonRecordingSpan
                if hasattr(span, 'name') and span.name:
                    print(f"Span created: {span.name} with ID: {span.get_span_context().span_id}")
                else:
                    print(f"NonRecordingSpan created for view: {view_name}")
                
                start_time = time.time()
                try:
                    result = func(request, *args, **kwargs)
                    execution_time = time.time() - start_time
                    
                    # Record success
                    if hasattr(span, 'set_attribute'):
                        span.set_attribute("operation.success", True)
                        span.set_attribute("operation.execution_time_ms", execution_time * 1000)
                        span.set_attribute("http.status_code", getattr(result, 'status_code', 200))
                        span.set_status(Status(StatusCode.OK))
                    
                    print(f"View {view_name} completed successfully in {execution_time*1000:.2f}ms")
                    return result
                    
                except Exception as e:
                    execution_time = time.time() - start_time
                    
                    # Record failure
                    if hasattr(span, 'set_attribute'):
                        span.set_attribute("operation.success", False)
                        span.set_attribute("operation.execution_time_ms", execution_time * 1000)
                        span.set_attribute("operation.error", str(e))
                        span.set_attribute("operation.error_type", type(e).__name__)
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                    
                    print(f"View {view_name} failed: {e}")
                    raise
                    
        return wrapper
    return decorator


def add_span_attribute(key, value):
    """
    Add an attribute to the current span.
    
    Args:
        key (str): Attribute key
        value: Attribute value
    
    Example:
        add_span_attribute("user.action", "player_selection")
        add_span_attribute("game.date", "2025-04-01")
    """
    current_span = trace.get_current_span()
    if current_span:
        current_span.set_attribute(key, value)


def record_exception(exception, **attributes):
    """
    Record an exception in the current span.
    
    Args:
        exception: The exception to record
        **attributes: Additional attributes to add to the span
    
    Example:
        try:
            # Some operation
            pass
        except Exception as e:
            record_exception(e, operation="player_search", user_id=123)
            raise
    """
    current_span = trace.get_current_span()
    if current_span:
        for key, value in attributes.items():
            current_span.set_attribute(key, value)
        current_span.record_exception(exception)
        current_span.set_status(Status(StatusCode.ERROR, str(exception)))
