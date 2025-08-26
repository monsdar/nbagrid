"""
Robust wrapper around the NBA API that handles rate limiting, retries, and caching.
This makes the API calls more reliable and efficient when dealing with NBA.com's rate limits.
"""

import time
import logging
import random
import json
import os
import hashlib
from functools import wraps
from typing import Dict, Any, Optional, Callable
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

class NBAAPIRateLimitError(Exception):
    """Custom exception for NBA API rate limiting."""
    pass

class NBAAPIWrapper:
    """
    Robust wrapper for NBA API calls with rate limiting, retries, and caching.
    """
    
    def __init__(self):
        # Rate limiting configuration
        self.max_calls_per_minute = 300  # Conservative limit
        self.calls_this_minute = 0
        self.last_reset_time = time.time()
        
        # Minimum delay between calls (to avoid NBA API detection)
        self.min_delay_between_calls = .5
        self.last_call_time = 0
        
        # Retry configuration
        self.max_retries = 3
        self.base_delay = 1.0  # Base delay in seconds
        self.max_delay = 60.0  # Maximum delay in seconds
        
        # Cache configuration
        self.default_cache_timeout = 3600 * 10  # 10 hours default
        self.cache_prefix = "nba_api"
        
        # File-based persistent cache configuration
        self.persistent_cache_dir = os.path.join(settings.BASE_DIR, 'nba_api_cache')
        self._ensure_cache_directory()
        
        # Track API calls for monitoring
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.rate_limited_calls = 0
    
    def _reset_rate_limit_counter(self):
        """Reset the rate limit counter if a minute has passed."""
        current_time = time.time()
        if current_time - self.last_reset_time >= 60:
            self.calls_this_minute = 0
            self.last_reset_time = current_time
    
    def _check_rate_limit(self):
        """Check if we're within rate limits."""
        self._reset_rate_limit_counter()
        
        if self.calls_this_minute >= self.max_calls_per_minute:
            wait_time = 60 - (time.time() - self.last_reset_time)
            if wait_time > 0:
                logger.warning(f"Rate limit reached. Waiting {wait_time:.1f} seconds...")
                time.sleep(wait_time)
                self._reset_rate_limit_counter()
        
        self.calls_this_minute += 1
        self.total_calls += 1
    
    def _enforce_minimum_delay(self):
        """Enforce minimum delay between API calls to avoid detection."""
        current_time = time.time()
        time_since_last_call = current_time - self.last_call_time
        
        if time_since_last_call < self.min_delay_between_calls:
            wait_time = self.min_delay_between_calls - time_since_last_call
            logger.debug(f"Enforcing minimum delay: waiting {wait_time:.1f} seconds between calls")
            time.sleep(wait_time)
        
        self.last_call_time = time.time()
    
    def _ensure_cache_directory(self):
        """Ensure the persistent cache directory exists."""
        try:
            if not os.path.exists(self.persistent_cache_dir):
                os.makedirs(self.persistent_cache_dir, exist_ok=True)
                logger.info(f"Created persistent cache directory: {self.persistent_cache_dir}")
        except Exception as e:
            logger.warning(f"Could not create cache directory: {e}")
    
    def _get_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """Generate a cache key for the API call."""
        # Create a deterministic cache key from endpoint and sorted parameters
        sorted_params = sorted(params.items())
        param_str = "&".join(f"{k}={v}" for k, v in sorted_params)
        return f"{self.cache_prefix}:{endpoint}:{param_str}"
    
    def _get_file_cache_path(self, cache_key: str) -> str:
        """Generate a safe file path for persistent caching."""
        # Create a hash of the cache key to avoid filesystem issues
        safe_key = hashlib.md5(cache_key.encode()).hexdigest()
        return os.path.join(self.persistent_cache_dir, f"{safe_key}.json")
    
    def _get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached response if available."""
        # Try Django cache first
        try:
            cached = cache.get(cache_key)
            if cached:
                logger.debug(f"Django cache hit for {cache_key}")
                return cached
        except Exception as e:
            logger.warning(f"Django cache error: {e}")
        
        # Try persistent file cache
        try:
            file_path = self._get_file_cache_path(cache_key)
            if os.path.exists(file_path):
                # Check if file is still valid (not expired)
                file_age = time.time() - os.path.getmtime(file_path)
                if file_age < self.default_cache_timeout:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        cached_data = json.load(f)['data']
                        logger.debug(f"File cache hit for {cache_key}")
                        # Also update Django cache for faster future access
                        try:
                            cache.set(cache_key, cached_data, self.default_cache_timeout)
                        except Exception as e:
                            logger.warning(f"Could not update Django cache: {e}")
                        return cached_data
                else:
                    # File is expired, remove it
                    os.remove(file_path)
                    logger.debug(f"Removed expired cache file: {file_path}")
        except Exception as e:
            logger.warning(f"File cache error: {e}")
        
        return None
    
    def _set_cached_response(self, cache_key: str, response: Dict[str, Any], timeout: int = None):
        """Cache the API response."""
        if timeout is None:
            timeout = self.default_cache_timeout
        
        # Save to Django cache for fast access
        try:
            cache.set(cache_key, response, timeout)
            logger.debug(f"Cached response in Django cache for {cache_key} (timeout: {timeout}s)")
        except Exception as e:
            logger.warning(f"Django cache set error: {e}")
        
        # Save to persistent file cache
        try:
            file_path = self._get_file_cache_path(cache_key)
            cache_data = {
                'data': response,
                'timestamp': time.time(),
                'timeout': timeout,
                'cache_key': cache_key
            }
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Persisted response to file cache: {file_path}")
        except Exception as e:
            logger.warning(f"File cache set error: {e}")
    
    def _exponential_backoff(self, attempt: int) -> float:
        """Calculate delay for exponential backoff with jitter."""
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        # Add jitter to prevent thundering herd
        jitter = random.uniform(0, 0.1 * delay)
        return delay + jitter
    
    def _handle_api_error(self, error: Exception, attempt: int, max_attempts: int) -> bool:
        """Handle API errors and decide whether to retry."""
        error_str = str(error).lower()
        
        # Check for rate limiting indicators
        if any(indicator in error_str for indicator in ['rate limit', 'too many requests', '429', 'timeout']):
            self.rate_limited_calls += 1
            logger.warning(f"Rate limit detected on attempt {attempt + 1}/{max_attempts}: {error}")
            
            if attempt < max_attempts - 1:
                wait_time = self._exponential_backoff(attempt)
                logger.info(f"Waiting {wait_time:.1f} seconds before retry...")
                time.sleep(wait_time)
                return True  # Retry
        
        # Check for other retryable errors
        elif any(indicator in error_str for indicator in ['timeout', 'connection', 'network']):
            logger.warning(f"Network error on attempt {attempt + 1}/{max_attempts}: {error}")
            if attempt < max_attempts - 1:
                return True  # Retry
        
        # Log non-retryable errors
        else:
            logger.error(f"Non-retryable error on attempt {attempt + 1}/{max_attempts}: {error}")
        
        return False  # Don't retry
    
    def call_api(self, 
                 api_call: Callable, 
                 cache_timeout: int = None,
                 force_refresh: bool = False,
                 **kwargs) -> Dict[str, Any]:
        """
        Make a robust API call with rate limiting, retries, and caching.
        
        Args:
            api_call: The NBA API function to call
            cache_timeout: How long to cache the response (in seconds)
            force_refresh: Skip cache and force fresh API call
            **kwargs: Arguments to pass to the API call
        
        Returns:
            API response data
            
        Raises:
            NBAAPIRateLimitError: If rate limit is exceeded after all retries
            Exception: If API call fails after all retries
        """
        cache_key = self._get_cache_key(api_call.__name__, kwargs)
        
        # Check cache first (unless forcing refresh)
        if not force_refresh:
            cached_response = self._get_cached_response(cache_key)
            if cached_response:
                return cached_response
        
        # Make API call with retries
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                # Check rate limits before making the call
                self._check_rate_limit()
                
                # Enforce minimum delay between calls
                self._enforce_minimum_delay()
                
                # Make the API call
                logger.debug(f"Making API call to {api_call.__name__} (attempt {attempt + 1}/{self.max_retries})")
                response = api_call(**kwargs)
                
                # Convert to normalized dict if it's an NBA API response object
                if hasattr(response, 'get_normalized_dict'):
                    response_data = response.get_normalized_dict()
                else:
                    response_data = response
                
                # Cache successful response
                self._set_cached_response(cache_key, response_data, cache_timeout)
                
                # Log success
                self.successful_calls += 1
                logger.debug(f"API call successful: {api_call.__name__}")
                
                return response_data
                
            except Exception as error:
                last_error = error
                self.failed_calls += 1
                
                # Check if we should retry
                if self._handle_api_error(error, attempt, self.max_retries):
                    continue
                else:
                    break
        
        # If we get here, all retries failed
        error_msg = f"API call to {api_call.__name__} failed after {self.max_retries} attempts"
        if last_error:
            error_msg += f": {last_error}"
        
        logger.error(error_msg)
        
        # Try to return cached data as fallback
        cached_response = self._get_cached_response(cache_key)
        if cached_response:
            logger.warning(f"Returning cached data as fallback for {api_call.__name__}")
            return cached_response
        
        # Re-raise the last error
        if isinstance(last_error, Exception):
            raise last_error
        else:
            raise Exception(error_msg)
    
    def get_stats(self, 
                  endpoint_class, 
                  cache_timeout: int = None,
                  force_refresh: bool = False,
                  **kwargs) -> Dict[str, Any]:
        """
        Convenience method for getting NBA stats with the wrapper.
        
        Args:
            endpoint_class: The NBA API endpoint class (e.g., PlayerCareerStats)
            cache_timeout: How long to cache the response
            force_refresh: Skip cache and force fresh API call
            **kwargs: Arguments to pass to the endpoint
        
        Returns:
            API response data
        """
        def api_call(**call_kwargs):
            endpoint = endpoint_class(**call_kwargs)
            return endpoint
        
        return self.call_api(api_call, cache_timeout, force_refresh, **kwargs)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the API wrapper."""
        status = {
            'total_calls': self.total_calls,
            'successful_calls': self.successful_calls,
            'failed_calls': self.failed_calls,
            'rate_limited_calls': self.rate_limited_calls,
            'success_rate': (self.successful_calls / max(self.total_calls, 1)) * 100,
            'calls_this_minute': self.calls_this_minute,
            'max_calls_per_minute': self.max_calls_per_minute,
            'last_reset_time': self.last_reset_time,
            'min_delay_between_calls': self.min_delay_between_calls
        }
        
        # Add cache statistics
        cache_stats = self.get_cache_stats()
        status.update(cache_stats)
        
        return status
    
    def reset_counters(self):
        """Reset all counters (useful for testing)."""
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.rate_limited_calls = 0
        self.calls_this_minute = 0
        self.last_reset_time = time.time()
        self.last_call_time = 0
    
    def clear_persistent_cache(self):
        """Clear all persistent file cache files."""
        try:
            if os.path.exists(self.persistent_cache_dir):
                for filename in os.listdir(self.persistent_cache_dir):
                    if filename.endswith('.json'):
                        file_path = os.path.join(self.persistent_cache_dir, filename)
                        os.remove(file_path)
                logger.info(f"Cleared persistent cache directory: {self.persistent_cache_dir}")
        except Exception as e:
            logger.error(f"Error clearing persistent cache: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the persistent cache."""
        try:
            if not os.path.exists(self.persistent_cache_dir):
                return {'file_count': 0, 'total_size_mb': 0, 'cache_dir': self.persistent_cache_dir}
            
            file_count = 0
            total_size = 0
            
            for filename in os.listdir(self.persistent_cache_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(self.persistent_cache_dir, filename)
                    total_size += os.path.getsize(file_path)
                    file_count += 1
            
            return {
                'file_count': file_count,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'cache_dir': self.persistent_cache_dir
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {'error': str(e)}

# Global instance
nba_api_wrapper = NBAAPIWrapper()

# Convenience functions
def get_player_career_stats(player_id: int, **kwargs) -> Dict[str, Any]:
    """Get player career stats with robust error handling."""
    from nba_api.stats.endpoints import PlayerCareerStats
    return nba_api_wrapper.get_stats(PlayerCareerStats, player_id=player_id, **kwargs)

def get_team_roster(team_id: str, season: str, **kwargs) -> Dict[str, Any]:
    """Get team roster with robust error handling."""
    from nba_api.stats.endpoints import CommonTeamRoster
    return nba_api_wrapper.get_stats(CommonTeamRoster, team_id=team_id, season=season, **kwargs)

def get_team_dash_lineups(team_id: int, season: str, **kwargs) -> Dict[str, Any]:
    """Get team dash lineups with robust error handling."""
    from nba_api.stats.endpoints import TeamDashLineups
    return nba_api_wrapper.get_stats(TeamDashLineups, team_id=team_id, season=season, **kwargs)

def get_league_dash_lineups(team_id: int, season: str, **kwargs) -> Dict[str, Any]:
    """Get league dash lineups with robust error handling. Returns more lineups than team dash lineups."""
    from nba_api.stats.endpoints import LeagueDashLineups
    return nba_api_wrapper.get_stats(LeagueDashLineups, team_id_nullable=team_id, season=season, **kwargs)

def clear_nba_api_cache():
    """Clear all NBA API cache (both Django and persistent)."""
    nba_api_wrapper.clear_persistent_cache()
    logger.info("NBA API cache cleared")

def get_nba_api_status():
    """Get comprehensive status of the NBA API wrapper."""
    return nba_api_wrapper.get_status()
