from django.core.exceptions import ValidationError
from rest_framework import serializers

from apps.accounts.phone import normalize_phone
from apps.locations.models import City

from .models import Agency, BrokerProfile


class AgencySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Agency
        fields = ("id", "name_ar", "name_en", "logo_url")
        read_only_fields = fields


class CitySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ("id", "name_ar", "name_en", "slug_en")
        read_only_fields = fields


class BrokerProfileSerializer(serializers.ModelSerializer):
    """The logged-in broker's own profile (read and write)."""

    city_ids = serializers.PrimaryKeyRelatedField(
        source="cities_served", many=True, queryset=City.objects.filter(is_active=True)
    )
    agency = AgencySummarySerializer(read_only=True)

    class Meta:
        model = BrokerProfile
        fields = (
            "id",
            "name_ar",
            "name_en",
            "photo_url",
            "fal_licence",
            "whatsapp",
            "city_ids",
            "agency",
        )
        read_only_fields = ("id", "agency")

    def validate_whatsapp(self, value):
        try:
            return normalize_phone(value)
        except ValidationError:
            raise serializers.ValidationError("invalid_phone") from None


class PublicBrokerSerializer(serializers.ModelSerializer):
    """What anyone can see about a broker. No contact details: leads go through tracked buttons."""

    agency = AgencySummarySerializer(read_only=True)
    cities_served = CitySummarySerializer(many=True, read_only=True)

    class Meta:
        model = BrokerProfile
        fields = ("id", "name_ar", "name_en", "photo_url", "fal_licence", "agency", "cities_served")
        read_only_fields = fields


class AgencySerializer(serializers.ModelSerializer):
    """The agency admin's own agency (read and write)."""

    class Meta:
        model = Agency
        fields = ("id", "name_ar", "name_en", "logo_url", "cr_number", "fal_licence")
        read_only_fields = ("id",)


class AgencyMemberSerializer(serializers.ModelSerializer):
    """A member as the agency admin sees it. The phone stays masked."""

    class Meta:
        model = BrokerProfile
        fields = ("id", "name_ar", "name_en", "photo_url", "fal_licence", "masked_whatsapp")
        read_only_fields = fields


class PublicAgencySerializer(serializers.ModelSerializer):
    members = serializers.SerializerMethodField()

    class Meta:
        model = Agency
        fields = ("id", "name_ar", "name_en", "logo_url", "fal_licence", "members")
        read_only_fields = fields

    def get_members(self, agency):
        members = agency.members.all()
        return [
            {"id": m.id, "name_ar": m.name_ar, "name_en": m.name_en, "photo_url": m.photo_url}
            for m in members
        ]


class AddMemberSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
