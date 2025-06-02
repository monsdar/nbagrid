from django.http import HttpResponsePermanentRedirect
from django.conf import settings

class DomainRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Get the host from the request
        host = request.get_host().split(':')[0]
        
        # Check if the request is coming from the old PythonAnywhere domain
        if settings.PYTHONANYWHERE_DOMAIN in host:
            # Redirect to the new domain
            return HttpResponsePermanentRedirect(f'https://www.nbagr.id{request.path}')
        
        return self.get_response(request) 