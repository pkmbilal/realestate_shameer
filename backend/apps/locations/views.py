from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from .models import City
from .serializers import CitySerializer, DistrictSerializer

# Locations change rarely, so the public lists are cached in Redis.
# An edit in admin shows up on the site within this many seconds.
CACHE_SECONDS = 10 * 60


@method_decorator(cache_page(CACHE_SECONDS), name="dispatch")
class CityListView(ListAPIView):
    """Active cities, for search filters and area pages."""

    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = CitySerializer
    pagination_class = None
    queryset = City.objects.filter(is_active=True)


@method_decorator(cache_page(CACHE_SECONDS), name="dispatch")
class DistrictListView(ListAPIView):
    """Active districts of one city, by the city's English slug."""

    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = DistrictSerializer
    pagination_class = None

    def get_queryset(self):
        city = get_object_or_404(City, slug_en=self.kwargs["city_slug"], is_active=True)
        return city.districts.filter(is_active=True)
