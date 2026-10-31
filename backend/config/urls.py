from django.contrib import admin
from django.urls import include, path

api_patterns = [
    path("", include("apps.core.urls")),
    path("accounts/", include("apps.accounts.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(api_patterns)),
]
