from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from django.db.models import Count
from django.utils.translation import gettext_lazy as _

from .models import City, District


@admin.register(City)
class CityAdmin(GISModelAdmin):
    list_display = ("name_en", "name_ar", "region", "district_count", "is_active", "sort_order")
    list_editable = ("is_active", "sort_order")
    list_filter = ("region", "is_active")
    search_fields = ("name_en", "name_ar")
    prepopulated_fields = {"slug_en": ("name_en",)}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_district_count=Count("districts"))

    @admin.display(description=_("districts"), ordering="_district_count")
    def district_count(self, obj):
        return obj._district_count


@admin.register(District)
class DistrictAdmin(GISModelAdmin):
    list_display = ("name_en", "name_ar", "city", "is_active")
    list_editable = ("is_active",)
    list_filter = ("city", "is_active")
    list_select_related = ("city",)
    search_fields = ("name_en", "name_ar")
    prepopulated_fields = {"slug_en": ("name_en",)}
