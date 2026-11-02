from django.contrib import admin
from django.urls import include, path

api_patterns = [
    path("", include("apps.core.urls")),
    path("auth/", include("apps.accounts.auth_urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("locations/", include("apps.locations.urls")),
    path("brokers/", include("apps.brokers.urls")),
    path("listings/", include("apps.listings.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(api_patterns)),
]
