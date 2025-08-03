from django.conf import settings
from django.http import HttpResponsePermanentRedirect


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
