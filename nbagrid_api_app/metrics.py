from prometheus_client import Counter, Histogram, Gauge
import time

# Define metrics
game_completions_counter = Counter(
    'nbagrid_game_completions_total',
    'Number of completed games',
    ['result']  # 'win', 'lose'
)

game_starts_counter = Counter(
    'nbagrid_game_starts_total',
    'Number of started games'
)

game_score_histogram = Histogram(
    'nbagrid_game_score',
    'Distribution of game scores',
    ['result'],
    buckets=(0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100)
)

active_games_gauge = Gauge(
    'nbagrid_active_games',
    'Number of currently active games'
)

unique_users_gauge = Counter(
    'nbagrid_unique_users',
    'Number of unique users based on session keys'
)

# API request latency
api_request_latency = Histogram(
    'nbagrid_api_request_latency_seconds',
    'API request latency in seconds',
    ['endpoint']
)

# API request counter
api_request_counter = Counter(
    'nbagrid_api_requests_total',
    'Number of API requests',
    ['endpoint', 'status']
)

# Helper function to track API request latency
def track_request_latency(endpoint):
    start_time = time.time()
    
    def stop_timer(status='success'):
        latency = time.time() - start_time
        api_request_latency.labels(endpoint=endpoint).observe(latency)
        api_request_counter.labels(endpoint=endpoint, status=status).inc()
        
    return stop_timer

# Increment counter when a game is completed
def record_game_completion(score, result):
    game_completions_counter.labels(result=result).inc()
    game_score_histogram.labels(result=result).observe(score)

# Increment counter when a new game is started
def record_game_start():
    game_starts_counter.inc()

# Update active games gauge
def update_active_games(count):
    active_games_gauge.set(count)

# Increment active games
def increment_active_games():
    active_games_gauge.inc()

# Update unique users gauge
def increment_unique_users():
    unique_users_gauge.inc()
