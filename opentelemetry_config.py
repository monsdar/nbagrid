"""
OpenTelemetry configuration for NBA Grid API.

This module sets up OpenTelemetry tracing and metrics collection.
"""

import os
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader, ConsoleMetricExporter
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.sqlite3 import SQLite3Instrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter


def test_otlp_connection(endpoint):
    """Test if the OTLP endpoint is reachable."""
    import requests
    try:
        # Test the endpoint with a simple GET request
        # For OTLP, we need to test the base endpoint, not the /v1/traces path
        base_endpoint = endpoint.replace('/v1/traces', '') if '/v1/traces' in endpoint else endpoint
        response = requests.get(base_endpoint, timeout=5)
        print(f"OTLP endpoint test: {base_endpoint} - Status: {response.status_code}")
        return True
    except Exception as e:
        print(f"OTLP endpoint test failed: {base_endpoint} - Error: {e}")
        return False


def setup_opentelemetry():
    """Set up OpenTelemetry tracing and metrics."""
    
    # Get configuration from environment variables
    service_name = os.getenv("OTEL_SERVICE_NAME", "nbagrid-api")
    environment = os.getenv("OTEL_ENVIRONMENT", "development")
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    
    # Set sampling environment variables if not already set
    if not os.getenv("OTEL_TRACES_SAMPLER"):
        os.environ["OTEL_TRACES_SAMPLER"] = "always_on"
    if not os.getenv("OTEL_TRACES_SAMPLER_ARG"):
        os.environ["OTEL_TRACES_SAMPLER_ARG"] = "1.0"
    
    print(f"OpenTelemetry setup: service={service_name}, env={environment}, otlp={otlp_endpoint}")
    print(f"Sampling: {os.getenv('OTEL_TRACES_SAMPLER')} with arg {os.getenv('OTEL_TRACES_SAMPLER_ARG')}")
    
    # Set up tracing with sampling
    try:
        from opentelemetry.sdk.trace.sampling import AlwaysOnSampler
        sampler = AlwaysOnSampler()
    except ImportError:
        try:
            from opentelemetry.sdk.trace.sampling import ALWAYS_ON
            sampler = ALWAYS_ON  # ALWAYS_ON is already a sampler instance
        except ImportError:
            # Fallback to default sampler
            sampler = None
            print("Warning: Could not import AlwaysOnSampler, using default sampler")
    
    if sampler:
        trace_provider = TracerProvider(sampler=sampler)
    else:
        trace_provider = TracerProvider()
    
    # Add span processors
    if environment == "development" or not otlp_endpoint:
        # Console exporter for development
        print("Adding console exporter for development")
        trace_provider.add_span_processor(
            BatchSpanProcessor(ConsoleSpanExporter())
        )
    
    if otlp_endpoint:
        # Test the OTLP endpoint connection
        print(f"Testing OTLP endpoint: {otlp_endpoint}")
        if test_otlp_connection(otlp_endpoint):
            # OTLP exporter for production
            print(f"Adding OTLP exporter to {otlp_endpoint}")
            
            # For Jaeger v1, use the OTLP HTTP endpoint on port 4318
            # The endpoint should be the base URL, and the exporter will add the correct path
            try:
                # Ensure the endpoint ends with /v1/traces for Jaeger
                if not otlp_endpoint.endswith('/v1/traces'):
                    if otlp_endpoint.endswith('/'):
                        otlp_endpoint = otlp_endpoint.rstrip('/')
                    otlp_endpoint = f"{otlp_endpoint}/v1/traces"
                
                print(f"Using OTLP endpoint: {otlp_endpoint}")
                otlp_trace_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
                trace_provider.add_span_processor(
                    BatchSpanProcessor(otlp_trace_exporter)
                )
                print("OTLP trace exporter added successfully")
            except Exception as e:
                print(f"Failed to create OTLP trace exporter: {e}")
        else:
            print("OTLP endpoint not reachable, falling back to console exporter")
            trace_provider.add_span_processor(
                BatchSpanProcessor(ConsoleSpanExporter())
            )
    
    # Set the global trace provider
    trace.set_tracer_provider(trace_provider)
    
    # Set up metrics
    metric_readers = []
    
    if environment == "development" or not otlp_endpoint:
        # Console exporter for development
        metric_readers.append(
            PeriodicExportingMetricReader(ConsoleMetricExporter())
        )
    
    if otlp_endpoint:
        # OTLP exporter for production
        try:
            otlp_metric_exporter = OTLPMetricExporter(endpoint=otlp_endpoint)
            metric_readers.append(
                PeriodicExportingMetricReader(otlp_metric_exporter)
            )
            print("OTLP metric exporter added successfully")
        except Exception as e:
            print(f"Failed to create OTLP metric exporter: {e}")
    
    # Create meter provider
    meter_provider = MeterProvider(metric_readers=metric_readers)
    metrics.set_meter_provider(meter_provider)
    
    # Get tracer and meter
    tracer = trace.get_tracer(__name__)
    meter = metrics.get_meter(__name__)
    
    print("OpenTelemetry setup complete")
    return tracer, meter


def instrument_django():
    """Instrument Django with OpenTelemetry."""
    
    # Instrument Django
    DjangoInstrumentor().instrument(
        request_hook=lambda span, request: span.set_attribute("http.request_id", getattr(request, "id", None)),
        response_hook=lambda span, response: span.set_attribute("http.response_size", len(response.content) if hasattr(response, 'content') else 0)
    )
    
    # Instrument database drivers
    try:
        SQLite3Instrumentor().instrument()
    except Exception:
        pass  # SQLite might not be available
    
    try:
        Psycopg2Instrumentor().instrument()
    except Exception:
        pass  # PostgreSQL might not be available
    
    # Instrument logging
    LoggingInstrumentor().instrument(
        set_logging_format=True,
        log_level=os.getenv("OTEL_LOG_LEVEL", "INFO")
    )


def create_custom_span(operation_name, **attributes):
    """Create a custom span for manual instrumentation."""
    tracer = trace.get_tracer(__name__)
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(operation_name, attributes=attributes) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("operation.success", True)
                    return result
                except Exception as e:
                    span.set_attribute("operation.success", False)
                    span.record_exception(e)
                    span.set_attribute("operation.error", str(e))
                    raise
        return wrapper
    return decorator


def create_custom_metric(metric_name, metric_type="counter", **attributes):
    """Create a custom metric for manual instrumentation."""
    meter = metrics.get_meter(__name__)
    
    if metric_type == "counter":
        return meter.create_counter(metric_name, attributes=attributes)
    elif metric_type == "histogram":
        return meter.create_histogram(metric_name, attributes=attributes)
    elif metric_type == "gauge":
        return meter.create_up_down_counter(metric_name, attributes=attributes)
    else:
        raise ValueError(f"Unsupported metric type: {metric_type}")


# Global tracer and meter instances
tracer = None
meter = None


def initialize():
    """Initialize OpenTelemetry globally."""
    global tracer, meter
    
    if tracer is None:
        tracer, meter = setup_opentelemetry()
        instrument_django()
    
    return tracer, meter


def get_tracer():
    """Get the global tracer instance."""
    if tracer is None:
        initialize()
    return tracer


def get_meter():
    """Get the global meter instance."""
    if meter is None:
        initialize()
    return meter
