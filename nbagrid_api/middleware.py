from django.conf import settings
from django.http import HttpResponsePermanentRedirect
import logging
import sys
import os

logger = logging.getLogger(__name__)

class DomainRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Get the host from the request
        host = request.get_host().split(":")[0]

        # Check if the request is coming from the old PythonAnywhere domain
        if settings.PYTHONANYWHERE_DOMAIN and (settings.PYTHONANYWHERE_DOMAIN in host):
            # Redirect to the new domain
            return HttpResponsePermanentRedirect(f"https://www.nbagr.id{request.path}")

        return self.get_response(request)


class TrafficSourceTrackingMiddleware:
    """Middleware to track traffic sources and referrer information."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Quick check: skip traffic source tracking during tests
        is_testing = (
            getattr(settings, 'TESTING', False) or
            'test' in sys.argv or
            'pytest' in sys.argv[0] or
            'manage.py' in sys.argv[0] and 'test' in sys.argv or
            os.environ.get('DISABLE_TRAFFIC_TRACKING', '').lower() == 'true'
        )
        
        if not is_testing:
            try:
                # Extract traffic source information
                self._extract_traffic_source(request)
            except Exception as e:
                logger.error(f"Error extracting traffic source: {e}")
                # Don't let traffic source errors break the request
                request.traffic_source = {'source': 'unknown', 'error': str(e)}
        else:
            # During tests, just set a minimal traffic source
            request.traffic_source = {'source': 'test', 'test_mode': True}
        
        response = self.get_response(request)
        
        # Record traffic source data after response (to ensure session is available)
        # Only record if we have valid traffic source data and a session key
        # Skip during tests to avoid interfering with test execution
        if (hasattr(request, 'traffic_source') and 
            request.traffic_source.get('source') not in ['unknown', 'test'] and
            hasattr(request, 'session') and 
            request.session.session_key and
            not is_testing):
            try:
                # Only import if the model exists (prevents import errors during tests)
                try:
                    from nbagrid_api_app.models import TrafficSource
                    TrafficSource.record_visit(request, request.traffic_source)
                except ImportError:
                    logger.warning("TrafficSource model not available, skipping traffic recording")
                except Exception as e:
                    logger.error(f"Error recording traffic source visit: {e}")
            except Exception as e:
                logger.error(f"Error in traffic source recording logic: {e}")
        
        return response
    
    def _extract_traffic_source(self, request):
        """Extract and log traffic source information from the request."""
        try:
            # Get referrer information
            referrer = request.META.get('HTTP_REFERER', '')
            
            # Get UTM parameters
            utm_source = request.GET.get('utm_source', '')
            utm_medium = request.GET.get('utm_medium', '')
            utm_campaign = request.GET.get('utm_campaign', '')
            utm_term = request.GET.get('utm_term', '')
            utm_content = request.GET.get('utm_content', '')
            
            # Get other potential source indicators
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            # Determine traffic source
            traffic_source = self._determine_traffic_source(
                referrer, utm_source, utm_medium, user_agent
            )
            
            # Store in request for use in views
            request.traffic_source = {
                'source': traffic_source,
                'referrer': referrer,
                'utm_source': utm_source,
                'utm_medium': utm_medium,
                'utm_campaign': utm_campaign,
                'utm_term': utm_term,
                'utm_content': utm_content,
                'user_agent': user_agent,
                'path': request.path,
                'query_string': request.GET.urlencode(),
            }
            
            # Log traffic source for analysis (but not during tests)
            is_testing = (
                getattr(settings, 'TESTING', False) or
                'test' in sys.argv or
                'pytest' in sys.argv[0] or
                'manage.py' in sys.argv[0] and 'test' in sys.argv or
                os.environ.get('DISABLE_TRAFFIC_TRACKING', '').lower() == 'true'
            )
            
            if traffic_source != 'direct' and not is_testing:
                logger.info(
                    f"Traffic source detected: {traffic_source} | "
                    f"Referrer: {referrer} | "
                    f"UTM: {utm_source}/{utm_medium}/{utm_campaign} | "
                    f"Path: {request.path}"
                )
            
        except Exception as e:
            logger.error(f"Error extracting traffic source: {e}")
            request.traffic_source = {'source': 'unknown', 'error': str(e)}
    
    def _determine_traffic_source(self, referrer, utm_source, utm_medium, user_agent):
        """Determine the primary traffic source based on available data."""
        
        # UTM parameters take priority
        if utm_source:
            if utm_source.lower() in ['google', 'bing', 'yahoo']:
                return 'search_engine'
            elif utm_source.lower() in ['reddit', 'twitter', 'facebook', 'instagram', 'tiktok']:
                return 'social_media'
            elif utm_source.lower() in ['email', 'newsletter']:
                return 'email'
            elif utm_source.lower() in ['partner', 'affiliate']:
                return 'partner'
            else:
                return f'utm_{utm_source.lower()}'
        
        # Check referrer for search engines
        if referrer:
            referrer_lower = referrer.lower()
            
            # Search engines
            if any(engine in referrer_lower for engine in [
                'google.com', 'bing.com', 'yahoo.com', 'duckduckgo.com',
                'baidu.com', 'yandex.com', 'qwant.com'
            ]):
                return 'search_engine'
            
            # Social media platforms
            if any(platform in referrer_lower for platform in [
                'reddit.com', 'twitter.com', 'facebook.com', 'instagram.com',
                'tiktok.com', 'linkedin.com', 'youtube.com', 'discord.com'
            ]):
                return 'social_media'
            
            # News and content sites
            if any(site in referrer_lower for site in [
                'medium.com', 'substack.com', 'news.ycombinator.com',
                'techcrunch.com', 'theverge.com'
            ]):
                return 'content_site'
            
            # Gaming platforms
            if any(platform in referrer_lower for platform in [
                'steam.com', 'epicgames.com', 'itch.io', 'gamejolt.com'
            ]):
                return 'gaming_platform'
            
            # If we have a referrer but can't categorize it
            return 'referral'
        
        # Check user agent for bots
        if user_agent:
            user_agent_lower = user_agent.lower()
            if any(bot in user_agent_lower for bot in [
                'bot', 'crawler', 'spider', 'scraper', 'googlebot',
                'bingbot', 'slurp', 'duckduckbot'
            ]):
                return 'bot'
        
        # Default to direct traffic
        return 'direct'
