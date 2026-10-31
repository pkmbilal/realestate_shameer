from rest_framework import serializers

from .models import City, District


class PointField(serializers.Field):
    """A GeoDjango Point as {"lat": …, "lng": …}, or null."""

    def to_representation(self, value):
        return {"lat": value.y, "lng": value.x}


class CitySerializer(serializers.ModelSerializer):
    center = PointField(allow_null=True)

    class Meta:
        model = City
        fields = ("id", "name_ar", "name_en", "slug_ar", "slug_en", "region", "center")


class DistrictSerializer(serializers.ModelSerializer):
    center = PointField(allow_null=True)

    class Meta:
        model = District
        fields = ("id", "name_ar", "name_en", "slug_ar", "slug_en", "center")
