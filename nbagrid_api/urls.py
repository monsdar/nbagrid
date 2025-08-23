"""
URL configuration for nbagrid_api project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django_prometheus import exports

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from django.views.static import serve


import nbagrid_api_app.views
from nbagrid_api_app.auth import basic_auth_required

from .api import api


# Create secured versions of the django-prometheus endpoints
@basic_auth_required
def secured_metrics_view(request):
    return HttpResponse(exports.ExportToDjangoView(request))


# The metrics endpoint
@basic_auth_required
def secured_metrics_registry_view(request):
    return HttpResponse(exports.ExportToDjangoPrometheusDjangoMetrics(request))



urlpatterns = [
    path("", nbagrid_api_app.views.index, name="index"),
    path("<int:year>/<int:month>/<int:day>/", nbagrid_api_app.views.game, name="game"),
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    path("metrics/", nbagrid_api_app.views.metrics_view, name="metrics"),
    # Display name endpoints
    path("api/update-display-name/", nbagrid_api_app.views.update_display_name, name="update-display-name"),
    path("api/random-name/", nbagrid_api_app.views.generate_random_name, name="random-name"),
    # Player search endpoint
    path("search-players/", nbagrid_api_app.views.search_players, name="search-players"),
    # Secure the django-prometheus exports
    path("django_metrics", secured_metrics_view, name="django-metrics"),
    path("prometheus/metrics", secured_metrics_registry_view, name="prometheus-django-metrics"),
    # Serve favicon.ico
    path("favicon.ico", serve, {"path": "favicon.ico", "document_root": settings.STATIC_ROOT}),

]
