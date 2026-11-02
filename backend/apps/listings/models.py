"""Property listings. Every listing starts from a REGA advertising licence (CLAUDE.md §2).

Fields REGA supplies (licence, purpose, type, place, area) are copied from the licence and
never edited by advertisers. Status changes go through services.py, which logs each one.
"""

import secrets

from django.conf import settings
from django.contrib.gis.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

# No 0/O or 1/I so references are easy to read out on the phone.
REFERENCE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
REFERENCE_LENGTH = 8


def new_reference() -> str:
    return "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(REFERENCE_LENGTH))


class Amenity(models.Model):
    slug = models.SlugField(_("slug"), max_length=50, unique=True)
    name_ar = models.CharField(_("name (Arabic)"), max_length=100)
    name_en = models.CharField(_("name (English)"), max_length=100)
    sort_order = models.PositiveSmallIntegerField(_("sort order"), default=0)

    class Meta:
        verbose_name = _("amenity")
        verbose_name_plural = _("amenities")
        ordering = ("sort_order", "name_en")

    def __str__(self):
        return f"{self.name_en} / {self.name_ar}"


class Listing(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        PENDING_REVIEW = "pending_review", _("Pending review")
        ACTIVE = "active", _("Active")
        EXPIRED = "expired", _("Expired")
        TAKEN_DOWN = "taken_down", _("Taken down")
        ARCHIVED = "archived", _("Archived")

    # A licence number may only be used by one listing in these statuses at a time.
    LIVE_STATUSES = (Status.DRAFT, Status.PENDING_REVIEW, Status.ACTIVE)

    class Purpose(models.TextChoices):
        SALE = "sale", _("For sale")
        RENT = "rent", _("For rent")

    class RentPeriod(models.TextChoices):
        YEARLY = "yearly", _("Yearly")
        MONTHLY = "monthly", _("Monthly")

    class PropertyType(models.TextChoices):
        APARTMENT = "apartment", _("Apartment")
        VILLA = "villa", _("Villa")
        FLOOR = "floor", _("Floor")
        DUPLEX = "duplex", _("Duplex")
        TOWNHOUSE = "townhouse", _("Townhouse")
        LAND = "land", _("Land")
        BUILDING = "building", _("Building")

    class Furnishing(models.TextChoices):
        UNFURNISHED = "unfurnished", _("Unfurnished")
        SEMI_FURNISHED = "semi_furnished", _("Semi-furnished")
        FURNISHED = "furnished", _("Furnished")

    class Completion(models.TextChoices):
        READY = "ready", _("Ready")
        OFF_PLAN = "off_plan", _("Off-plan")

    reference = models.CharField(
        _("reference"), max_length=REFERENCE_LENGTH, unique=True, default=new_reference
    )

    # --- Who posted it ---
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="listings",
        verbose_name=_("created by"),
    )
    broker = models.ForeignKey(
        "brokers.BrokerProfile",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="listings",
        verbose_name=_("broker"),
    )
    agency = models.ForeignKey(
        "brokers.Agency",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="listings",
        verbose_name=_("agency"),
    )

    # --- Supplied by REGA (read-only for advertisers) ---
    licence_number = models.CharField(_("REGA ad licence number"), max_length=32)
    licence_expires_on = models.DateField(_("licence expires on"))
    purpose = models.CharField(_("purpose"), max_length=10, choices=Purpose.choices)
    property_type = models.CharField(
        _("property type"), max_length=20, choices=PropertyType.choices
    )
    city = models.ForeignKey(
        "locations.City", on_delete=models.PROTECT, related_name="listings", verbose_name=_("city")
    )
    district = models.ForeignKey(
        "locations.District",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="listings",
        verbose_name=_("district"),
    )
    area_m2 = models.PositiveIntegerField(_("area (m²)"))
    location = models.PointField(_("map point"), srid=4326)
    rega_data = models.JSONField(_("REGA data"), default=dict, blank=True)
    rega_synced_at = models.DateTimeField(_("REGA synced at"))

    # --- Entered by the advertiser ---
    price_halalas = models.PositiveBigIntegerField(_("price (halalas)"), null=True, blank=True)
    rent_period = models.CharField(
        _("rent period"), max_length=10, choices=RentPeriod.choices, blank=True
    )
    bedrooms = models.PositiveSmallIntegerField(_("bedrooms"), null=True, blank=True)
    bathrooms = models.PositiveSmallIntegerField(_("bathrooms"), null=True, blank=True)
    furnishing = models.CharField(
        _("furnishing"), max_length=20, choices=Furnishing.choices, blank=True
    )
    completion = models.CharField(
        _("completion"), max_length=10, choices=Completion.choices, default=Completion.READY
    )
    title_ar = models.CharField(_("title (Arabic)"), max_length=150, blank=True)
    title_en = models.CharField(_("title (English)"), max_length=150, blank=True)
    description_ar = models.TextField(_("description (Arabic)"), blank=True)
    description_en = models.TextField(_("description (English)"), blank=True)
    amenities = models.ManyToManyField(
        Amenity, blank=True, related_name="listings", verbose_name=_("amenities")
    )

    # --- Lifecycle ---
    status = models.CharField(
        _("status"), max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    # Why moderation sent it back; shown to the advertiser and cleared on resubmit.
    moderation_note = models.CharField(_("moderation note"), max_length=500, blank=True)
    published_at = models.DateTimeField(_("published at"), null=True, blank=True)
    post_expires_at = models.DateTimeField(_("post period ends at"), null=True, blank=True)
    # Sort key for "newest"; moved forward by the paid "refresh" action later.
    refreshed_at = models.DateTimeField(_("refreshed at"), null=True, blank=True)
    featured_until = models.DateTimeField(_("featured until"), null=True, blank=True)
    view_count = models.PositiveIntegerField(_("views"), default=0)

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("listing")
        verbose_name_plural = _("listings")
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["licence_number"],
                condition=Q(status__in=["draft", "pending_review", "active"]),
                name="listing_one_live_listing_per_licence",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "city", "purpose"], name="listing_search_idx"),
            models.Index(fields=["status", "licence_expires_on"], name="listing_licence_exp_idx"),
            models.Index(fields=["status", "post_expires_at"], name="listing_post_exp_idx"),
        ]

    def __str__(self):
        return f"{self.reference} ({self.get_status_display()})"


class ListingPhoto(models.Model):
    listing = models.ForeignKey(
        Listing, on_delete=models.CASCADE, related_name="photos", verbose_name=_("listing")
    )
    # Object key in the media bucket; images are served through imgproxy.
    key = models.CharField(_("storage key"), max_length=255, unique=True)
    # 0 is the cover photo.
    position = models.PositiveSmallIntegerField(_("position"), default=0)
    size_bytes = models.PositiveIntegerField(_("size (bytes)"), default=0)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("listing photo")
        verbose_name_plural = _("listing photos")
        ordering = ("listing", "position", "id")

    def __str__(self):
        return self.key


class ListingStatusChange(models.Model):
    """Append-only log of every status change (moderation, takedown, expiry). Never edited."""

    listing = models.ForeignKey(
        Listing, on_delete=models.CASCADE, related_name="status_changes", verbose_name=_("listing")
    )
    from_status = models.CharField(_("from"), max_length=20, choices=Listing.Status.choices)
    to_status = models.CharField(_("to"), max_length=20, choices=Listing.Status.choices)
    # Empty for automatic changes such as the nightly expiry job.
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("changed by"),
    )
    reason = models.CharField(_("reason"), max_length=500, blank=True)
    created_at = models.DateTimeField(_("at"), auto_now_add=True)

    class Meta:
        verbose_name = _("status change")
        verbose_name_plural = _("status changes")
        ordering = ("-created_at", "-id")

    def __str__(self):
        return f"{self.listing.reference}: {self.from_status} → {self.to_status}"


class PendingListing(Listing):
    """Admin-only view of listings waiting for moderation (the moderation queue)."""

    class Meta:
        proxy = True
        verbose_name = _("listing to review")
        verbose_name_plural = _("moderation queue")
