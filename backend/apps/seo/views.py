from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services

# Counts on area pages may lag new listings by this many seconds.
CACHE_SECONDS = 10 * 60


@method_decorator(cache_page(CACHE_SECONDS), name="dispatch")
class AreaCountsView(APIView):
    """Listing counts per area, for area pages, internal links and sitemaps."""

    permission_classes = [AllowAny]
    authentication_classes = []
    http_method_names = ["get", "head", "options"]

    def get(self, request):
        return Response(services.area_counts())


class SitemapListingsView(APIView):
    """References of active listings for the sitemap, in chunks (?page=1, 2, …)."""

    permission_classes = [AllowAny]
    authentication_classes = []
    http_method_names = ["get", "head", "options"]

    def get(self, request):
        try:
            page = int(request.query_params.get("page", "1"))
        except ValueError:
            page = 1
        return Response(services.sitemap_listings(page))
