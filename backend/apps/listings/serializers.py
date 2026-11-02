from django.utils import timezone
from rest_framework import serializers

from apps.brokers.serializers import AgencySummarySerializer
from apps.core.imgproxy import imgproxy_url

from .models import Amenity, Listing, ListingPhoto


class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = ("id", "slug", "name_ar", "name_en")
        read_only_fields = fields


class PhotoSerializer(serializers.ModelSerializer):
    """Photo URLs come from imgproxy in fixed sizes (card, large)."""

    card_url = serializers.SerializerMethodField()
    large_url = serializers.SerializerMethodField()

    class Meta:
        model = ListingPhoto
        fields = ("id", "position", "card_url", "large_url")
        read_only_fields = fields

    def get_card_url(self, obj):
        return imgproxy_url(obj.key, 640, 480)

    def get_large_url(self, obj):
        return imgproxy_url(obj.key, 1600, 1200, fit="fit")


class PlaceMixin(serializers.Serializer):
    city = serializers.SerializerMethodField()
    district = serializers.SerializerMethodField()
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    def get_city(self, obj):
        c = obj.city
        return {"id": c.pk, "name_ar": c.name_ar, "name_en": c.name_en, "slug_en": c.slug_en}

    def get_district(self, obj):
        d = obj.district
        if d is None:
            return None
        return {"id": d.pk, "name_ar": d.name_ar, "name_en": d.name_en, "slug_en": d.slug_en}

    def get_latitude(self, obj):
        return obj.location.y

    def get_longitude(self, obj):
        return obj.location.x


# Fields REGA supplies; always read-only through the API (CLAUDE.md §2 rule 2).
REGA_FIELDS = (
    "licence_number",
    "licence_expires_on",
    "purpose",
    "property_type",
    "area_m2",
)
ADVERTISER_FIELDS = (
    "price_halalas",
    "rent_period",
    "bedrooms",
    "bathrooms",
    "furnishing",
    "completion",
    "title_ar",
    "title_en",
    "description_ar",
    "description_en",
)


class MyListingSerializer(PlaceMixin, serializers.ModelSerializer):
    """The advertiser's own listing: REGA fields and status read-only, the rest editable."""

    amenity_ids = serializers.PrimaryKeyRelatedField(
        source="amenities", many=True, queryset=Amenity.objects.all(), required=False
    )
    photos = PhotoSerializer(many=True, read_only=True)

    class Meta:
        model = Listing
        fields = (
            "id",
            "reference",
            "status",
            "moderation_note",
            *REGA_FIELDS,
            "city",
            "district",
            "latitude",
            "longitude",
            *ADVERTISER_FIELDS,
            "amenity_ids",
            "photos",
            "published_at",
            "post_expires_at",
            "featured_until",
            "view_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = tuple(
            f for f in fields if f not in ADVERTISER_FIELDS and f != "amenity_ids"
        )

    def validate(self, attrs):
        rent_period = attrs.get("rent_period")
        if rent_period and self.instance and self.instance.purpose != Listing.Purpose.RENT:
            raise serializers.ValidationError({"rent_period": "only_for_rent"})
        return attrs


class StartListingSerializer(serializers.Serializer):
    licence_number = serializers.CharField(max_length=40)


class PresignPhotoSerializer(serializers.Serializer):
    content_type = serializers.CharField(max_length=50)
    size_bytes = serializers.IntegerField(min_value=1)


class ConfirmPhotoSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=255)


class ReorderPhotosSerializer(serializers.Serializer):
    photo_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)


class AdvertiserSerializer(serializers.Serializer):
    """Who is advertising. No phone numbers: contact goes through tracked lead buttons."""

    def to_representation(self, listing):
        broker = listing.broker
        return {
            "type": "broker" if broker else ("agency" if listing.agency else "owner"),
            "broker": (
                {
                    "id": broker.pk,
                    "name_ar": broker.name_ar,
                    "name_en": broker.name_en,
                    "photo_url": broker.photo_url,
                    "fal_licence": broker.fal_licence,
                }
                if broker
                else None
            ),
            "agency": AgencySummarySerializer(listing.agency).data if listing.agency else None,
        }


class PublicListingCardSerializer(PlaceMixin, serializers.ModelSerializer):
    """Compact listing for search results and maps."""

    cover = serializers.SerializerMethodField()
    is_featured = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = (
            "reference",
            "purpose",
            "property_type",
            "price_halalas",
            "rent_period",
            "bedrooms",
            "bathrooms",
            "area_m2",
            "title_ar",
            "title_en",
            "city",
            "district",
            "latitude",
            "longitude",
            "cover",
            "is_featured",
            "published_at",
        )
        read_only_fields = fields

    def get_cover(self, obj):
        photos = list(obj.photos.all())  # prefetched, already ordered by position
        return PhotoSerializer(photos[0]).data if photos else None

    def get_is_featured(self, obj):
        return bool(obj.featured_until and obj.featured_until > timezone.now())


class PublicListingSerializer(PublicListingCardSerializer):
    """Full public listing page, including the REGA licence badge data."""

    photos = PhotoSerializer(many=True, read_only=True)
    amenities = AmenitySerializer(many=True, read_only=True)
    advertiser = AdvertiserSerializer(source="*", read_only=True)

    class Meta(PublicListingCardSerializer.Meta):
        fields = (
            *PublicListingCardSerializer.Meta.fields,
            "furnishing",
            "completion",
            "description_ar",
            "description_en",
            "licence_number",
            "licence_expires_on",
            "photos",
            "amenities",
            "advertiser",
            "view_count",
        )
        read_only_fields = fields
