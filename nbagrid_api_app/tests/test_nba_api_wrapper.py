"""
Tests for the NBA API wrapper functionality.
"""

import time
import unittest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.core.cache import cache

from nbagrid_api_app.nba_api_wrapper import NBAAPIWrapper, NBAAPIRateLimitError


class TestNBAAPIWrapper(TestCase):
    """Test cases for NBA API wrapper."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.wrapper = NBAAPIWrapper()
        self.wrapper.reset_counters()
        cache.clear()
    
    def tearDown(self):
        """Clean up after tests."""
        cache.clear()
    
    def test_initialization(self):
        """Test wrapper initialization."""
        self.assertEqual(self.wrapper.max_calls_per_minute, 300)
        self.assertEqual(self.wrapper.calls_this_minute, 0)
        self.assertEqual(self.wrapper.max_retries, 3)
        self.assertEqual(self.wrapper.max_delay, 120.0)
        self.assertEqual(self.wrapper.rate_limit_base_delay, 60.0)
        self.assertEqual(self.wrapper.rate_limit_max_delay, 300.0)
        self.assertEqual(self.wrapper.request_timeout, 5.0)
        self.assertEqual(self.wrapper.connect_timeout, 5.0)
    
    def test_rate_limit_counter_reset(self):
        """Test rate limit counter reset functionality."""
        # Simulate time passing
        self.wrapper.calls_this_minute = 5
        self.wrapper.last_reset_time = time.time() - 70  # 70 seconds ago
        
        self.wrapper._reset_rate_limit_counter()
        
        self.assertEqual(self.wrapper.calls_this_minute, 0)
        self.assertGreater(self.wrapper.last_reset_time, time.time() - 5)
    
    def test_rate_limit_check_within_limits(self):
        """Test rate limit check when within limits."""
        self.wrapper.calls_this_minute = 10
        self.wrapper.last_reset_time = time.time()
        
        # Should not raise any exception
        self.wrapper._check_rate_limit()
        self.assertEqual(self.wrapper.calls_this_minute, 11)
    
    def test_rate_limit_check_exceeds_limits(self):
        """Test rate limit check when exceeding limits."""
        # Set up a scenario where we're over the rate limit
        self.wrapper.calls_this_minute = 300
        self.wrapper.last_reset_time = time.time() - 30  # 30 seconds ago
        
        # Should wait and reset
        with patch('time.sleep') as mock_sleep:
            self.wrapper._check_rate_limit()
            # Should have called sleep once
            self.assertTrue(mock_sleep.called)
            # The counter should be incremented (the exact value depends on the logic)
            self.assertGreater(self.wrapper.calls_this_minute, 0)
    
    def test_minimum_delay_enforcement(self):
        """Test minimum delay enforcement between calls."""
        self.wrapper.last_call_time = time.time()
        
        with patch('time.sleep') as mock_sleep:
            self.wrapper._enforce_minimum_delay()
            mock_sleep.assert_called_once()
    
    def test_exponential_backoff_standard(self):
        """Test exponential backoff for standard errors."""
        delay1 = self.wrapper._exponential_backoff(0, is_rate_limit=False)
        delay2 = self.wrapper._exponential_backoff(1, is_rate_limit=False)
        delay3 = self.wrapper._exponential_backoff(2, is_rate_limit=False)
        
        self.assertGreater(delay2, delay1)
        self.assertGreater(delay3, delay2)
        self.assertLessEqual(delay3, self.wrapper.max_delay)
    
    def test_exponential_backoff_rate_limit(self):
        """Test exponential backoff for rate limit errors."""
        delay1 = self.wrapper._exponential_backoff(0, is_rate_limit=True)
        delay2 = self.wrapper._exponential_backoff(1, is_rate_limit=True)
        delay3 = self.wrapper._exponential_backoff(2, is_rate_limit=True)
        
        # Rate limit delays should be much longer
        self.assertGreaterEqual(delay1, self.wrapper.rate_limit_base_delay)
        self.assertGreater(delay2, delay1)
        self.assertGreater(delay3, delay2)
        self.assertLessEqual(delay3, self.wrapper.rate_limit_max_delay)
    
    def test_handle_api_error_rate_limit(self):
        """Test error handling for rate limit errors."""
        error = Exception("Rate limit exceeded")
        
        with patch('time.sleep') as mock_sleep:
            result = self.wrapper._handle_api_error(error, 0, 3)
            
            self.assertTrue(result)  # Should retry
            mock_sleep.assert_called_once()
            self.assertEqual(self.wrapper.rate_limited_calls, 1)
    
    def test_handle_api_error_network_error(self):
        """Test error handling for network errors."""
        error = Exception("Connection timeout")
        
        with patch('time.sleep') as mock_sleep:
            result = self.wrapper._handle_api_error(error, 0, 3)
            
            self.assertTrue(result)  # Should retry
            mock_sleep.assert_called_once()
    
    def test_handle_api_error_non_retryable(self):
        """Test error handling for non-retryable errors."""
        error = Exception("Invalid parameter")
        
        result = self.wrapper._handle_api_error(error, 0, 3)
        
        self.assertFalse(result)  # Should not retry
    
    def test_handle_api_error_429_status(self):
        """Test error handling for 429 status code."""
        error = Exception("HTTP 429 Too Many Requests")
        
        with patch('time.sleep') as mock_sleep:
            result = self.wrapper._handle_api_error(error, 0, 3)
            
            self.assertTrue(result)  # Should retry
            self.assertEqual(self.wrapper.rate_limited_calls, 1)
    
    def test_handle_api_error_503_status(self):
        """Test error handling for 503 status code."""
        error = Exception("HTTP 503 Service Unavailable")
        
        with patch('time.sleep') as mock_sleep:
            result = self.wrapper._handle_api_error(error, 0, 3)
            
            self.assertTrue(result)  # Should retry
            self.assertEqual(self.wrapper.rate_limited_calls, 1)
    
    def test_handle_api_error_timeout(self):
        """Test error handling for timeout errors."""
        error = Exception("Read timed out. (read timeout=30)")
        
        with patch('time.sleep') as mock_sleep:
            result = self.wrapper._handle_api_error(error, 0, 3)
            
            self.assertTrue(result)  # Should retry
            self.assertEqual(self.wrapper.rate_limited_calls, 1)
    
    def test_handle_api_error_connection_timeout(self):
        """Test error handling for connection timeout errors."""
        error = Exception("Connection timeout")
        
        with patch('time.sleep') as mock_sleep:
            result = self.wrapper._handle_api_error(error, 0, 3)
            
            self.assertTrue(result)  # Should retry
    
    def test_handle_api_error_blocked_access(self):
        """Test error handling for blocked access."""
        error = Exception("Access denied - IP blocked")
        
        with patch('time.sleep') as mock_sleep:
            result = self.wrapper._handle_api_error(error, 0, 3)
            
            self.assertTrue(result)  # Should retry
            self.assertEqual(self.wrapper.rate_limited_calls, 1)
    
    def test_cache_key_generation(self):
        """Test cache key generation."""
        params = {'player_id': 123, 'season': '2023-24'}
        cache_key = self.wrapper._get_cache_key('test_endpoint', params)
        
        self.assertIn('nba_api:test_endpoint', cache_key)
        # Parameters are now URL-encoded, so we check for the encoded version
        self.assertIn('player_id%3D123', cache_key)  # = becomes %3D
        self.assertIn('season%3D2023-24', cache_key)  # = becomes %3D
    
    def test_cache_key_deterministic(self):
        """Test that cache keys are deterministic."""
        params1 = {'player_id': 123, 'season': '2023-24'}
        params2 = {'season': '2023-24', 'player_id': 123}  # Different order
        
        key1 = self.wrapper._get_cache_key('test_endpoint', params1)
        key2 = self.wrapper._get_cache_key('test_endpoint', params2)
        
        self.assertEqual(key1, key2)
    
    @patch('nbagrid_api_app.nba_api_wrapper.cache')
    def test_get_cached_response_django_cache_hit(self, mock_cache):
        """Test getting cached response from Django cache."""
        mock_cache.get.return_value = {'test': 'data'}
        
        result = self.wrapper._get_cached_response('test_key')
        
        self.assertEqual(result, {'test': 'data'})
        mock_cache.get.assert_called_once_with('test_key')
    
    @patch('nbagrid_api_app.nba_api_wrapper.cache')
    def test_get_cached_response_django_cache_miss(self, mock_cache):
        """Test getting cached response when Django cache misses."""
        mock_cache.get.return_value = None
        
        with patch('os.path.exists', return_value=False):
            result = self.wrapper._get_cached_response('test_key')
        
        self.assertIsNone(result)
    
    @patch('nbagrid_api_app.nba_api_wrapper.cache')
    def test_set_cached_response(self, mock_cache):
        """Test setting cached response."""
        response_data = {'test': 'data'}
        
        with patch('builtins.open', create=True) as mock_open:
            with patch('json.dump') as mock_json_dump:
                self.wrapper._set_cached_response('test_key', response_data, 3600)
        
        mock_cache.set.assert_called_once_with('test_key', response_data, 3600)
        mock_open.assert_called_once()
        mock_json_dump.assert_called_once()
    
    def test_get_status(self):
        """Test getting wrapper status."""
        self.wrapper.total_calls = 10
        self.wrapper.successful_calls = 8
        self.wrapper.failed_calls = 2
        self.wrapper.rate_limited_calls = 1
        
        status = self.wrapper.get_status()
        
        self.assertEqual(status['total_calls'], 10)
        self.assertEqual(status['successful_calls'], 8)
        self.assertEqual(status['failed_calls'], 2)
        self.assertEqual(status['rate_limited_calls'], 1)
        self.assertEqual(status['success_rate'], 80.0)
    
    def test_reset_counters(self):
        """Test resetting counters."""
        self.wrapper.total_calls = 10
        self.wrapper.successful_calls = 8
        self.wrapper.failed_calls = 2
        self.wrapper.rate_limited_calls = 1
        
        self.wrapper.reset_counters()
        
        self.assertEqual(self.wrapper.total_calls, 0)
        self.assertEqual(self.wrapper.successful_calls, 0)
        self.assertEqual(self.wrapper.failed_calls, 0)
        self.assertEqual(self.wrapper.rate_limited_calls, 0)
    
    def test_call_api_success(self):
        """Test successful API call."""
        mock_api_call = Mock(return_value={'data': 'test'})
        mock_api_call.__name__ = 'test_api'
        
        with patch.object(self.wrapper, '_check_rate_limit'):
            with patch.object(self.wrapper, '_enforce_minimum_delay'):
                with patch.object(self.wrapper, '_get_cached_response', return_value=None):
                    with patch.object(self.wrapper, '_set_cached_response'):
                        result = self.wrapper.call_api(mock_api_call, param1='value1')
        
        self.assertEqual(result, {'data': 'test'})
        self.assertEqual(self.wrapper.successful_calls, 1)
        self.assertEqual(self.wrapper.total_calls, 1)
    
    @patch('nbagrid_api_app.nba_api_wrapper.cache')
    def test_call_api_with_caching(self, mock_cache):
        """Test API call with caching."""
        mock_cache.get.return_value = None  # No cache hit
        mock_api_call = Mock(return_value={'data': 'test'})
        mock_api_call.__name__ = 'test_api'
        
        with patch.object(self.wrapper, '_check_rate_limit'):
            with patch.object(self.wrapper, '_enforce_minimum_delay'):
                result = self.wrapper.call_api(mock_api_call, param1='value1')
        
        # Should cache the result
        mock_cache.set.assert_called_once()
        self.assertEqual(result, {'data': 'test'})
    
    @patch('nbagrid_api_app.nba_api_wrapper.cache')
    def test_call_api_with_cache_hit(self, mock_cache):
        """Test API call with cache hit."""
        cached_data = {'data': 'cached'}
        mock_cache.get.return_value = cached_data
        mock_api_call = Mock()
        mock_api_call.__name__ = 'test_api'
        
        result = self.wrapper.call_api(mock_api_call, param1='value1')
        
        # Should return cached data without making API call
        self.assertEqual(result, cached_data)
        mock_api_call.assert_not_called()
    
    def test_call_api_retry_on_error(self):
        """Test API call retry on error."""
        mock_api_call = Mock(side_effect=Exception("Rate limit exceeded"))
        mock_api_call.__name__ = 'test_api'
        
        with patch.object(self.wrapper, '_check_rate_limit'):
            with patch.object(self.wrapper, '_enforce_minimum_delay'):
                with patch.object(self.wrapper, '_handle_api_error', return_value=True):
                    with patch.object(self.wrapper, '_get_cached_response', return_value=None):
                        with self.assertRaises(Exception):
                            self.wrapper.call_api(mock_api_call, param1='value1')
        
        # Should have attempted multiple times
        self.assertEqual(mock_api_call.call_count, 3)  # max_retries
        self.assertEqual(self.wrapper.failed_calls, 3)
    
    @patch('nbagrid_api_app.nba_api_wrapper.cache')
    def test_call_api_fallback_to_cache(self, mock_cache):
        """Test API call fallback to cached data on failure."""
        cached_data = {'data': 'cached'}
        mock_cache.get.return_value = cached_data
        mock_api_call = Mock(side_effect=Exception("API error"))
        mock_api_call.__name__ = 'test_api'
        
        with patch.object(self.wrapper, '_check_rate_limit'):
            with patch.object(self.wrapper, '_enforce_minimum_delay'):
                with patch.object(self.wrapper, '_handle_api_error', return_value=False):
                    result = self.wrapper.call_api(mock_api_call, param1='value1')
        
        # Should return cached data as fallback
        self.assertEqual(result, cached_data)


class TestNBAAPIWrapperIntegration(TestCase):
    """Integration tests for NBA API wrapper."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.wrapper = NBAAPIWrapper()
        self.wrapper.reset_counters()
        cache.clear()
    
    def tearDown(self):
        """Clean up after tests."""
        cache.clear()
    
    def test_rate_limit_indicators_comprehensive(self):
        """Test that all rate limit indicators are properly detected."""
        rate_limit_errors = [
            "Rate limit exceeded",
            "Too many requests",
            "HTTP 429",
            "Connection timeout",
            "Access blocked",
            "Forbidden access",
            "Access denied",
            "Quota exceeded",
            "Request throttled",
            "Service unavailable",
            "HTTP 503"
        ]
        
        for error_msg in rate_limit_errors:
            error = Exception(error_msg)
            with patch('time.sleep'):
                result = self.wrapper._handle_api_error(error, 0, 3)
                self.assertTrue(result, f"Failed to detect rate limit for: {error_msg}")
                self.assertEqual(self.wrapper.rate_limited_calls, 1)
                self.wrapper.rate_limited_calls = 0  # Reset for next test
    
    def test_network_error_indicators(self):
        """Test that network error indicators are properly detected."""
        network_errors = [
            "Connection timeout",
            "Network error",
            "HTTP 500",
            "HTTP 502",
            "HTTP 504"
        ]
        
        for error_msg in network_errors:
            error = Exception(error_msg)
            with patch('time.sleep'):
                result = self.wrapper._handle_api_error(error, 0, 3)
                self.assertTrue(result, f"Failed to detect network error for: {error_msg}")
    
    def test_non_retryable_errors(self):
        """Test that non-retryable errors are not retried."""
        non_retryable_errors = [
            "Invalid parameter",
            "Player not found",
            "HTTP 404",
            "Bad request",
            "HTTP 400"
        ]
        
        for error_msg in non_retryable_errors:
            error = Exception(error_msg)
            result = self.wrapper._handle_api_error(error, 0, 3)
            self.assertFalse(result, f"Should not retry for: {error_msg}")


if __name__ == '__main__':
    unittest.main()
