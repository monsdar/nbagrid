import time

import requests
from prometheus_client import Counter, Gauge, Histogram

# Define metrics
game_completions_counter = Counter("nbagrid_game_completions_total", "Number of completed games", ["result"])  # 'win', 'lose'

game_starts_counter = Counter("nbagrid_game_starts_total", "Number of started games")

game_score_histogram = Histogram(
    "nbagrid_game_score", "Distribution of game scores", ["result"], buckets=(0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100)
)

active_games_gauge = Gauge("nbagrid_active_games", "Number of currently active games")

unique_users_gauge = Counter("nbagrid_unique_users", "Number of unique users based on session keys")

# PythonAnywhere API metrics
cpu_limit_gauge = Gauge("pythonanywhere_cpu_limit_seconds", "Daily CPU limit in seconds")

cpu_usage_gauge = Gauge("pythonanywhere_cpu_usage_seconds", "Daily CPU usage in seconds")

cpu_usage_percent_gauge = Gauge("pythonanywhere_cpu_usage_percent", "Daily CPU usage as percentage of limit")

cpu_reset_seconds_gauge = Gauge("pythonanywhere_cpu_reset_seconds", "Seconds until CPU usage reset")

# API request latency
api_request_latency = Histogram("nbagrid_api_request_latency_seconds", "API request latency in seconds", ["endpoint"])

# API request counter
api_request_counter = Counter("nbagrid_api_requests_total", "Number of API requests", ["endpoint", "status"])


# Helper function to track API request latency
def track_request_latency(endpoint):
    start_time = time.time()

    def stop_timer(status="success"):
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


# Function to update CPU metrics from PythonAnywhere API
def update_pythonanywhere_cpu_metrics(username, token, host="www.pythonanywhere.com"):
    """
    Update Prometheus metrics with CPU usage data from PythonAnywhere API

    Args:
        username (str): PythonAnywhere username
        token (str): PythonAnywhere API token
        host (str): API host (www.pythonanywhere.com or eu.pythonanywhere.com)

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        response = requests.get(f"https://{host}/api/v0/user/{username}/cpu/", headers={"Authorization": f"Token {token}"})

        if response.status_code == 200:
            data = response.json()

            # Update metrics
            cpu_limit_gauge.set(data["daily_cpu_limit_seconds"])
            cpu_usage_gauge.set(data["daily_cpu_total_usage_seconds"])

            # Calculate percentage
            usage_percent = (data["daily_cpu_total_usage_seconds"] / data["daily_cpu_limit_seconds"]) * 100
            cpu_usage_percent_gauge.set(usage_percent)

            # Calculate seconds until reset
            reset_time = time.strptime(data["next_reset_time"], "%Y-%m-%dT%H:%M:%S.%f")
            reset_timestamp = time.mktime(reset_time)
            current_timestamp = time.time()
            seconds_until_reset = max(0, reset_timestamp - current_timestamp)
            cpu_reset_seconds_gauge.set(seconds_until_reset)

            return True
        else:
            return False
    except Exception as e:
        print(f"Error updating CPU metrics: {e}")
        return False


# Test function for the API
def test_pythonanywhere_api(username, token, host="www.pythonanywhere.com"):
    """
    Test the PythonAnywhere API connection

    Args:
        username (str): PythonAnywhere username
        token (str): PythonAnywhere API token
        host (str): API host (www.pythonanywhere.com or eu.pythonanywhere.com)

    Returns:
        dict: API response data if successful, None otherwise
    """
    try:
        response = requests.get(f"https://{host}/api/v0/user/{username}/cpu/", headers={"Authorization": f"Token {token}"})

        if response.status_code == 200:
            return response.json()
        else:
            print(f"API error: Status code {response.status_code}, Response: {response.text}")
            return None
    except Exception as e:
        print(f"Exception when testing API: {e}")
        return None
