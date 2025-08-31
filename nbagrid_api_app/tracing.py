"""
Tracing utilities for NBA Grid API.

This module provides easy-to-use decorators and context managers for adding
OpenTelemetry tracing to your application code.
"""

import os
import time
from functools import wraps
from contextlib import contextmanager
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode


# Cache for tracing enabled status
_TRACING_ENABLED = None

def is_tracing_enabled():
    """
    Check if OpenTelemetry tracing is configured and enabled.
    This includes checking if the configured endpoint is actually reachable.
    
    Returns:
        bool: True if tracing is enabled and endpoint is reachable, False otherwise
    """
    global _TRACING_ENABLED
    
    # Return cached result if available
    if _TRACING_ENABLED is not None:
        return _TRACING_ENABLED
        
    # Check if OTLP endpoint is configured
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not otlp_endpoint:
        _TRACING_ENABLED = False
        return _TRACING_ENABLED
    
    return _TRACING_ENABLED

def reset_tracing_cache():
    """
    Reset the tracing enabled cache. Useful for testing or when environment
    variables change during runtime.
    """
    global _TRACING_ENABLED
    _TRACING_ENABLED = None

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
            # If tracing is not enabled, just call the function
            if not is_tracing_enabled():
                return func(*args, **kwargs)
            
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
    # If tracing is not enabled, just yield a dummy span
    if not is_tracing_enabled():
        class DummySpan:
            def set_attribute(self, key, value):
                pass
            def set_status(self, status):
                pass
            def record_exception(self, exception):
                pass
        
        try:
            yield DummySpan()
        except Exception as e:
            raise
        return
    
    tracer = trace.get_tracer(__name__)
    
    with tracer.start_as_current_span(operation_name, attributes=attributes) as span:        
        start_time = time.time()
        try:
            yield span
            execution_time = time.time() - start_time
            
            # Record success
            if hasattr(span, 'set_attribute'):
                span.set_attribute("operation.success", True)
                span.set_attribute("operation.execution_time_ms", execution_time * 1000)
                span.set_status(Status(StatusCode.OK))
            
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
            # If tracing is not enabled, just call the function
            if not is_tracing_enabled():
                return func(*args, **kwargs)
            
            tracer = trace.get_tracer(__name__)
            
            # Create database-specific attributes
            db_attributes = {
                "db.system": "sqlite" if "sqlite" in str(args) else "postgresql",
                "db.operation": query_type,
                "db.table": table,
                **attributes
            }
            
            with tracer.start_as_current_span(f"db.{query_type}", attributes=db_attributes) as span:                
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
            # If tracing is not enabled, just call the function
            if not is_tracing_enabled():
                return func(request, *args, **kwargs)
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
            
            with tracer.start_as_current_span(f"view.{view_name}", attributes=view_attributes) as span:                
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
    # If tracing is not enabled, do nothing
    if not is_tracing_enabled():
        return
    
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
    # If tracing is not enabled, do nothing
    if not is_tracing_enabled():
        return
    
    current_span = trace.get_current_span()
    if current_span:
        for key, value in attributes.items():
            current_span.set_attribute(key, value)
        current_span.record_exception(exception)
        current_span.set_status(Status(StatusCode.ERROR, str(exception)))
