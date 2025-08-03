import base64
from functools import wraps

from django.conf import settings
from django.http import HttpResponse


def basic_auth_required(view_func):
    """
    Decorator that implements Basic Authentication for views.
    Specifically designed for the Prometheus metrics endpoint.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not settings.PROMETHEUS_METRICS_ENABLED:
            return HttpResponse("Metrics collection is disabled", status=404)

        # Get credentials from request
        auth_header = request.META.get("HTTP_AUTHORIZATION")
        if not auth_header:
            return unauthorized_response()

        # Check if it's Basic Auth
        auth_type, auth_string = auth_header.split(" ", 1)
        if auth_type.lower() != "basic":
            return unauthorized_response()

        # Decode credentials
        try:
            auth_decoded = base64.b64decode(auth_string).decode("utf-8")
            username, password = auth_decoded.split(":", 1)

            # Check credentials against settings
            if username == settings.PROMETHEUS_METRICS_AUTH_USERNAME and password == settings.PROMETHEUS_METRICS_AUTH_PASSWORD:
                return view_func(request, *args, **kwargs)
        except Exception:
            pass

        return unauthorized_response()

    return _wrapped_view


def unauthorized_response():
    """Return a 401 Unauthorized response with WWW-Authenticate header"""
    response = HttpResponse("Unauthorized: Authentication credentials were not provided or are invalid.", status=401)
    response["WWW-Authenticate"] = 'Basic realm="Prometheus Metrics"'
    return response
