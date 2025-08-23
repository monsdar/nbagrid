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

# New vs Returning Users metrics (only counts users who have made at least one guess)
new_users_counter = Counter("nbagrid_new_users_total", "Number of new users who have made guesses")
returning_users_counter = Counter("nbagrid_returning_users_total", "Number of returning users who have made guesses")

# User return frequency metrics
user_return_frequency_histogram = Histogram(
    "nbagrid_user_return_frequency_days", 
    "Distribution of days between user visits", 
    buckets=(1, 2, 3, 7, 14, 30, 60, 90, 180, 365, float('inf'))
)

# Daily active users (only counts users who have made guesses)
daily_active_users_gauge = Gauge("nbagrid_daily_active_users", "Number of unique users active today who have made guesses")

# User activity metrics
user_sessions_by_age_histogram = Histogram(
    "nbagrid_user_sessions_by_age_days",
    "Distribution of user sessions by account age in days",
    buckets=(1, 7, 14, 30, 60, 90, 180, 365, float('inf'))
)

# Guess tracking metrics
user_guesses_counter = Counter("nbagrid_user_guesses_total", "Number of correct user guesses", ["date"])
wrong_guesses_counter = Counter("nbagrid_wrong_guesses_total", "Number of incorrect user guesses", ["date"])
total_guesses_gauge = Gauge("nbagrid_total_guesses", "Total number of guesses for a date", ["date"])

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

# Record new user event
def record_new_user():
    """Record when a new user who has made guesses is created."""
    new_users_counter.inc()


# Record returning user event
def record_returning_user(days_since_last_visit=None):
    """
    Record when a returning user who has made guesses visits.
    
    Args:
        days_since_last_visit (float, optional): Number of days since the user's last visit.
                                               If provided, will be recorded in the return frequency histogram.
    """
    returning_users_counter.inc()
    
    if days_since_last_visit is not None:
        user_return_frequency_histogram.observe(days_since_last_visit)


# Record user session by account age
def record_user_session_by_age(account_age_days):
    """
    Record a user session categorized by how old their account is.
    
    Args:
        account_age_days (float): Number of days since the user account was created.
    """
    user_sessions_by_age_histogram.observe(account_age_days)


# Update daily active users count
def update_daily_active_users(count):
    """
    Update the gauge for daily active users.
    
    Args:
        count (int): Number of unique users active today.
    """
    daily_active_users_gauge.set(count)
    
# Record user guesses metrics
def record_user_guess(date_str):
    """Record a correct user guess for a specific date."""
    user_guesses_counter.labels(date=date_str).inc()


def record_wrong_guess(date_str):
    """Record an incorrect user guess for a specific date."""
    wrong_guesses_counter.labels(date=date_str).inc()


def update_total_guesses_gauge(date_str, total_guesses):
    """Update the total guesses gauge for a specific date."""
    total_guesses_gauge.labels(date=date_str).set(total_guesses)

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
