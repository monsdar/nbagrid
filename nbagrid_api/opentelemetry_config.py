"""
OpenTelemetry configuration for NBA Grid API.

This module sets up OpenTelemetry tracing and metrics collection.
"""

import os
import logging
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.sqlite3 import SQLite3Instrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

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
        
    grafana_instance_id = os.getenv("GRAFANA_INSTANCE_ID")
    grafana_api_token = os.getenv("GRAFANA_API_TOKEN")
    
    logger.info(f"OpenTelemetry setup: service={service_name}, env={environment}, otlp={otlp_endpoint}")
    logger.info(f"Grafana Cloud: instance_id={grafana_instance_id}, api_token={'*' * 8 if grafana_api_token else 'None'}")
    logger.info(f"Sampling: {os.getenv('OTEL_TRACES_SAMPLER')} with arg {os.getenv('OTEL_TRACES_SAMPLER_ARG')}")
    
    # Grafana Cloud authentication
    
    # Create authentication headers for gRPC
    import base64
    auth_string = f"{grafana_instance_id}:{grafana_api_token}"
    auth_bytes = auth_string.encode('utf-8')
    auth_b64 = base64.b64encode(auth_bytes).decode('utf-8')
        
    # Set up tracing with sampling
    from opentelemetry.sdk.trace.sampling import ALWAYS_ON
    sampler = ALWAYS_ON
    trace_provider = TracerProvider(sampler=sampler)
    
    try:
        otlp_trace_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            insecure=False,  # Use TLS for Grafana Cloud
            headers=[("authorization", f"Basic {auth_b64}")])
        trace_provider.add_span_processor(
            BatchSpanProcessor(otlp_trace_exporter)
        )
    except Exception as e:
        logger.error(f"Failed to create OTLP trace exporter: {e}")
    
    # Set the global trace provider
    trace.set_tracer_provider(trace_provider)
    
    # Set up metrics
    metric_readers = [] 
    if otlp_endpoint:
        # OTLP exporter for production
        try:
            # Configure OTLP gRPC metric exporter
            # Authentication is handled at the gRPC channel level
            logger.debug(f"Creating OTLP gRPC metric exporter for endpoint: {otlp_endpoint}")
            otlp_metric_exporter = OTLPMetricExporter(
                endpoint=otlp_endpoint,
                insecure=False,  # Use TLS for Grafana Cloud
                headers=[("authorization", f"Basic {auth_b64}")]
            )
            
            metric_readers.append(
                PeriodicExportingMetricReader(otlp_metric_exporter)
            )
            logger.debug("OTLP metric exporter added successfully")
        except Exception as e:
            logger.error(f"Failed to create OTLP metric exporter: {e}")
    
    # Create meter provider
    meter_provider = MeterProvider(metric_readers=metric_readers)
    metrics.set_meter_provider(meter_provider)
    
    # Get tracer and meter
    tracer = trace.get_tracer(__name__)
    meter = metrics.get_meter(__name__)
    
    logger.debug("OpenTelemetry setup complete")
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
