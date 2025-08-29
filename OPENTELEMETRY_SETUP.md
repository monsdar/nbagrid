# OpenTelemetry Setup and Usage Guide for NBA Grid API

## Overview

OpenTelemetry has been integrated into the NBA Grid API to provide comprehensive tracing and observability. This enables detailed performance monitoring, distributed tracing, and better debugging capabilities.

## Installation

### 1. Install Required Packages

```bash
pip install -r requirements.txt
```

The following OpenTelemetry packages are now included:
- `opentelemetry-api` - Core API
- `opentelemetry-sdk` - SDK implementation
- `opentelemetry-instrumentation-django` - Django auto-instrumentation
- `opentelemetry-instrumentation-sqlite3` - SQLite database tracing
- `opentelemetry-instrumentation-psycopg2` - PostgreSQL database tracing
- `opentelemetry-exporter-otlp-proto-http` - OTLP exporter for production
- `opentelemetry-exporter-prometheus` - Prometheus metrics exporter

### 2. Configuration

OpenTelemetry is automatically initialized when Django starts. Configuration is done via environment variables:

```bash
# Service identification
export OTEL_SERVICE_NAME="nbagrid-api"
export OTEL_ENVIRONMENT="development"  # or "production"

# For production - OTLP endpoint (Jaeger, Grafana Tempo, etc.)
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:14268"

# Optional: Log level for OpenTelemetry
export OTEL_LOG_LEVEL="INFO"
```

## Features

### 1. Automatic Instrumentation

The following are automatically traced:
- **Django views** - All HTTP requests and responses
- **Database queries** - SQLite and PostgreSQL operations
- **Logging** - Enhanced with trace context

### 2. Manual Instrumentation

Use the provided tracing utilities for custom operations:

```python
from nbagrid_api.tracing import trace_view, trace_function, trace_operation, add_span_attribute

# Trace a view
@trace_view("search_players", endpoint="/search-players/")
def search_players(request):
    name = request.GET.get("name", "")
    add_span_attribute("search.query", name)
    
    with trace_operation("database_query", table="players", operation="select"):
        players = Player.objects.filter(name__icontains=name)[:5]
    
    add_span_attribute("search.result_count", len(players))
    return JsonResponse([{"stats_id": p.stats_id, "name": p.name} for p in players])

# Trace a function
@trace_function("complex_calculation", operation_type="computation")
def calculate_game_score(game_data):
    # Function implementation
    pass

# Trace database operations
@trace_database_query("select", table="players")
def get_player_by_name(name):
    return Player.objects.filter(name__icontains=name).first()
```

### 3. Context Propagation

Traces automatically propagate across:
- HTTP requests
- Database operations
- Function calls within the same request

## Performance Monitoring

### Key Metrics Tracked

1. **Request Performance**
   - Total request time
   - Database query time
   - Template rendering time
   - Session operations

2. **Database Performance**
   - Query execution time
   - Number of queries per request
   - Slow query identification
   - Query result counts

3. **Application Performance**
   - View execution time
   - Game filter generation time
   - Grid building time
   - User data retrieval time

### Example Traces

When a user searches for players, you'll see traces like:

```
view.search_players (200ms)
├── database_query (180ms)
│   └── SELECT * FROM players WHERE name ILIKE '%lebron%' LIMIT 5
└── json_serialization (20ms)
```

When loading a game page:

```
view.game (800ms)
├── database_query.grid_metadata (50ms)
├── user_data_retrieval (100ms)
├── game_filters_generation (300ms)
├── grid_building (50ms)
├── correct_players_retrieval (200ms)
└── template_rendering (100ms)
```

## Production Setup

### 1. Jaeger (Recommended)

```bash
# Run Jaeger locally with OTLP support
docker run -d --name jaeger -p 16686:16686 -p 14268:14268 -p 4317:4317 -p 4318:4318 jaegertracing/all-in-one:latest

# Set environment variable for OTLP HTTP endpoint
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
```

**Port Explanation:**
- **16686**: Jaeger UI (http://localhost:16686)
- **14268**: Legacy Jaeger collector (for backward compatibility)
- **4317**: OTLP gRPC receiver
- **4318**: OTLP HTTP receiver (recommended for most use cases)

### 2. Grafana Tempo

```bash
# Set environment variable for Grafana Tempo
export OTEL_EXPORTER_OTLP_ENDPOINT="http://your-tempo-instance:3200"
```

### 3. Console Output (Development)

For development, traces are automatically printed to the console when no OTLP endpoint is configured.

## Debugging Performance Issues

### 1. Identify Slow Operations

```python
# Add custom attributes for debugging
add_span_attribute("user.session_key", request.session.session_key)
add_span_attribute("game.date", f"{year}-{month}-{day}")
add_span_attribute("search.query_length", len(search_term))
```

### 2. Trace Database Queries

```python
# Wrap database operations for detailed tracing
with trace_operation("player_search_query", query_type="icontains", table="players"):
    players = Player.objects.filter(name__icontains=name)[:5]
    add_span_attribute("db.result_count", len(players))
```

### 3. Monitor Complex Operations

```python
# Trace filter generation (often a performance bottleneck)
with trace_operation("game_filters_generation", date=requested_date.isoformat()):
    static_filters, dynamic_filters = get_game_filters(requested_date)
    add_span_attribute("filters.static_count", len(static_filters))
    add_span_attribute("filters.dynamic_count", len(dynamic_filters))
```

## Integration with Existing Metrics

OpenTelemetry works alongside your existing Prometheus metrics:

- **Prometheus**: Aggregate metrics for dashboards and alerting
- **OpenTelemetry**: Detailed traces for debugging and optimization

## Common Use Cases

### 1. Debug Slow Player Search

```python
@trace_view("search_players")
def search_players(request):
    name = request.GET.get("name", "")
    add_span_attribute("search.query", name)
    
    if len(name) < 3:
        add_span_attribute("search.result", "query_too_short")
        return JsonResponse([])
    
    with trace_operation("database_query", operation="player_search"):
        start_time = time.time()
        players = Player.objects.filter(name__icontains=name)[:5]
        query_time = time.time() - start_time
        
        add_span_attribute("db.query_time_ms", query_time * 1000)
        add_span_attribute("db.result_count", len(players))
    
    return JsonResponse([{"stats_id": p.stats_id, "name": p.name} for p in players])
```

### 2. Monitor Game Loading Performance

```python
@trace_view("game")
def game(request, year, month, day):
    add_span_attribute("game.date", f"{year}-{month:02d}-{day:02d}")
    
    with trace_operation("grid_generation"):
        game_grid = build_grid(static_filters, dynamic_filters)
        add_span_attribute("grid.size", f"{len(game_grid)}x{len(game_grid[0])}")
    
    with trace_operation("stats_calculation"):
        stats = get_game_stats(requested_date)
        add_span_attribute("stats.completion_count", stats["completion_count"])
```

## Best Practices

### 1. Attribute Naming

Use consistent naming conventions:
- `http.*` for HTTP-related attributes
- `db.*` for database operations
- `user.*` for user-related data
- `game.*` for game-specific attributes
- `search.*` for search operations

### 2. Sensitive Data

Never include sensitive information in spans:
```python
# ❌ Don't do this
add_span_attribute("user.password", password)

# ✅ Do this instead
add_span_attribute("user.has_password", bool(password))
```

### 3. Performance Impact

OpenTelemetry has minimal performance impact, but:
- Use sampling in high-traffic production environments
- Avoid excessive span creation in tight loops
- Use context managers for related operations

## Troubleshooting

### 1. Traces Not Appearing

Check:
- Environment variables are set correctly
- OTLP endpoint is reachable (the exporter will automatically append `/v1/traces`)
- No firewall blocking the connection
- Jaeger container is running with OTLP ports exposed (4317, 4318)

### 2. Missing Database Traces

Ensure the correct instrumentation is installed:
```bash
pip install opentelemetry-instrumentation-sqlite3  # For SQLite
pip install opentelemetry-instrumentation-psycopg2  # For PostgreSQL
```

### 3. Import Errors

If OpenTelemetry packages aren't available, the application falls back to no-op implementations, so it won't break.

## Performance Analysis Examples

### Before Optimization
```
view.search_players (500ms)
├── database_query (480ms)  ← Slow!
│   └── SELECT * FROM players WHERE name ILIKE '%lebron%'
└── json_serialization (20ms)
```

### After Adding Index
```
view.search_players (50ms)
├── database_query (30ms)   ← Much faster!
│   └── SELECT * FROM players WHERE name ILIKE '%lebron%'
└── json_serialization (20ms)
```

## Integration with Grafana

Create dashboards to visualize:
- Request latency percentiles
- Database query performance
- Error rates by endpoint
- Trace volume over time

Example Grafana queries:
```promql
# Average request duration
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Database query count
rate(db_queries_total[5m])

# Error rate
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])
```

This OpenTelemetry integration provides comprehensive observability for your NBA Grid application, making it easy to identify and resolve performance bottlenecks.
