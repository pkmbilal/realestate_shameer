"""Listing business logic: start from a REGA licence, edit, moderate, expire, photos.

Views and admin call these functions; they never change `Listing.status` themselves.
Every status change is written to ListingStatusChange inside a locked transaction.
"""

import logging
import re
import uuid
from datetime import timedelta

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.contrib.gis.geos import Polygon
from django.db import IntegrityError, transaction
from django.db.models import BooleanField, Case, F, Max, Q, QuerySet, Value, When
from django.utils import timezone

from apps.accounts.models import User
from apps.brokers.models import Agency, BrokerProfile
from apps.core.dates import riyadh_today
from apps.core.storage import bucket_name, s3_client
from apps.locations.models import City, District
from integrations.rega import RegaAdLicence, RegaError, get_rega_client

from .models import Favourite, Listing, ListingPhoto, ListingStatusChange

logger = logging.getLogger(__name__)
Status = Listing.Status

# Fields the advertiser may set. Everything else comes from REGA or from moderation.
ADVERTISER_FIELDS = {
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
}
PHOTO_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
PRESIGN_SECONDS = 15 * 60
_LICENCE_RE = re.compile(r"^\d{6,20}$")


class ListingError(Exception):
    """A problem the user can see. `code` is a stable key the frontend translates;
    `fields` lists what is missing when code is `incomplete`."""

    def __init__(self, code: str, fields: list[str] | None = None):
        super().__init__(code)
        self.code = code
        self.fields = fields or []


# --- Starting a listing from a REGA licence -------------------------------------


def normalize_licence_number(raw: str) -> str:
    number = re.sub(r"[\s-]", "", raw or "")
    if not _LICENCE_RE.match(number):
        raise ListingError("invalid_licence_number")
    return number


def _advertiser(user: User) -> tuple[BrokerProfile | None, Agency | None, set[str]]:
    """Who the listing is posted for, and the FAL licences this user may advertise under."""
    if not user.is_nafath_verified:
        raise ListingError("nafath_required")
    broker = BrokerProfile.objects.select_related("agency").filter(user=user).first()
    if user.role == User.Role.OWNER:
        return None, None, set()
    if user.role == User.Role.BROKER:
        if broker is None:
            raise ListingError("broker_profile_required")
        agency = broker.agency
    elif user.role == User.Role.AGENCY_ADMIN:
        agency = Agency.objects.filter(admin=user).first()
        if agency is None:
            raise ListingError("agency_profile_required")
    else:
        raise ListingError("not_an_advertiser")
    fals = {x.fal_licence for x in (broker, agency) if x is not None and x.fal_licence}
    return broker, agency, fals


def fetch_valid_licence(number: str) -> RegaAdLicence:
    try:
        licence = get_rega_client().fetch_ad_licence(number)
    except RegaError as exc:
        raise ListingError(exc.code) from None
    if licence.expires_on < riyadh_today():
        raise ListingError("licence_expired")
    return licence


def _match_location(licence: RegaAdLicence) -> tuple[City, District | None]:
    """Find our city and district for the names REGA gives (Arabic or English)."""
    city = (
        City.objects.filter(is_active=True)
        .filter(Q(name_ar=licence.city_name_ar) | Q(name_en__iexact=licence.city_name_en))
        .first()
    )
    if city is None:
        raise ListingError("unsupported_city")
    district = (
        city.districts.filter(is_active=True)
        .filter(Q(name_ar=licence.district_name_ar) | Q(name_en__iexact=licence.district_name_en))
        .first()
    )
    return city, district


def start_listing_from_licence(user: User, raw_number: str) -> Listing:
    """Create a draft listing filled with the licence data REGA holds."""
    number = normalize_licence_number(raw_number)
    broker, agency, fals = _advertiser(user)
    licence = fetch_valid_licence(number)
    # Broker/agency licences carry the FAL number they were issued to. Owner licences
    # don't; the live client must confirm those belong to this owner.
    if licence.advertiser_fal and licence.advertiser_fal not in fals:
        raise ListingError("licence_not_yours")
    if Listing.objects.filter(licence_number=number, status__in=Listing.LIVE_STATUSES).exists():
        raise ListingError("licence_in_use")
    city, district = _match_location(licence)

    try:
        with transaction.atomic():
            return Listing.objects.create(
                created_by=user,
                broker=broker,
                agency=agency,
                licence_number=number,
                licence_expires_on=licence.expires_on,
                purpose=licence.purpose,
                property_type=licence.property_type,
                city=city,
                district=district,
                area_m2=licence.area_m2,
                location=f"POINT({licence.longitude} {licence.latitude})",
                rega_data=licence.raw,
                rega_synced_at=timezone.now(),
                rent_period=(
                    Listing.RentPeriod.YEARLY if licence.purpose == Listing.Purpose.RENT else ""
                ),
            )
    except IntegrityError:
        # Someone else started a listing with this licence at the same moment.
        raise ListingError("licence_in_use") from None


# --- Status changes ---------------------------------------------------------------


def _transition(
    listing: Listing,
    to_status: str,
    *,
    allowed_from,
    by: User | None,
    reason: str = "",
    **updates,
) -> Listing:
    """Move the listing to `to_status` and log it. Raises `invalid_status` if it is no
    longer in one of `allowed_from` (another request may have changed it)."""
    with transaction.atomic():
        locked = Listing.objects.select_for_update().get(pk=listing.pk)
        if locked.status not in allowed_from:
            raise ListingError("invalid_status")
        from_status = locked.status
        locked.status = to_status
        for name, value in updates.items():
            setattr(locked, name, value)
        locked.save()
        ListingStatusChange.objects.create(
            listing=locked,
            from_status=from_status,
            to_status=to_status,
            changed_by=by,
            reason=reason[:500],
        )
    listing.refresh_from_db()
    return listing


def missing_fields(listing: Listing) -> list[str]:
    """What the advertiser still has to fill in before the listing can be reviewed."""
    missing = []
    if not listing.price_halalas:
        missing.append("price_halalas")
    if listing.purpose == Listing.Purpose.RENT and not listing.rent_period:
        missing.append("rent_period")
    if not (listing.title_ar or listing.title_en):
        missing.append("title")
    if not listing.photos.exists():
        missing.append("photos")
    return missing


def _require_valid_licence(listing: Listing) -> None:
    if listing.licence_expires_on < riyadh_today():
        raise ListingError("licence_expired")


def submit_for_review(listing: Listing, by: User) -> Listing:
    missing = missing_fields(listing)
    if missing:
        raise ListingError("incomplete", missing)
    _require_valid_licence(listing)
    return _transition(
        listing,
        Status.PENDING_REVIEW,
        allowed_from={Status.DRAFT},
        by=by,
        moderation_note="",
    )


def approve(listing: Listing, by: User) -> Listing:
    """Publish a reviewed listing for LISTING_POST_DAYS days.

    Re-approving after an edit keeps the original post period.
    """
    _require_valid_licence(listing)
    now = timezone.now()
    post_expires_at = listing.post_expires_at
    if post_expires_at is None or post_expires_at <= now:
        post_expires_at = now + timedelta(days=settings.LISTING_POST_DAYS)
        # WALLET: the "post" credit charge goes here once the wallet app exists
        # (brokers and agencies only; owner listings are free).
    return _transition(
        listing,
        Status.ACTIVE,
        allowed_from={Status.PENDING_REVIEW},
        by=by,
        published_at=listing.published_at or now,
        refreshed_at=listing.refreshed_at or now,
        post_expires_at=post_expires_at,
    )


def _require_reason(reason: str) -> str:
    reason = (reason or "").strip()
    if not reason:
        raise ListingError("reason_required")
    return reason


def reject(listing: Listing, by: User, reason: str) -> Listing:
    """Send a listing back to the advertiser with the reason shown to them."""
    reason = _require_reason(reason)
    return _transition(
        listing,
        Status.DRAFT,
        allowed_from={Status.PENDING_REVIEW},
        by=by,
        reason=reason,
        moderation_note=reason[:500],
    )


def take_down(listing: Listing, by: User, reason: str) -> Listing:
    """Staff remove a listing from the site (CLAUDE.md §2 rule 4). Logged with the reason."""
    reason = _require_reason(reason)
    return _transition(
        listing,
        Status.TAKEN_DOWN,
        allowed_from={*Listing.LIVE_STATUSES, Status.EXPIRED},
        by=by,
        reason=reason,
        moderation_note=reason[:500],
    )


def archive(listing: Listing, by: User) -> Listing:
    """The advertiser removes their own listing (sold, rented, or no longer offered)."""
    return _transition(
        listing,
        Status.ARCHIVED,
        allowed_from={*Listing.LIVE_STATUSES, Status.EXPIRED},
        by=by,
    )


def expire_due_listings() -> int:
    """Expire listings whose REGA licence or post period has ended. Safe to run repeatedly.

    Returns how many listings were expired.
    """
    today = riyadh_today()
    now = timezone.now()
    due = [
        (pk, "licence_expired")
        for pk in Listing.objects.filter(
            status__in=(Status.ACTIVE, Status.PENDING_REVIEW), licence_expires_on__lt=today
        ).values_list("pk", flat=True)
    ]
    seen = {pk for pk, _ in due}
    due += [
        (pk, "post_period_ended")
        for pk in Listing.objects.filter(status=Status.ACTIVE, post_expires_at__lte=now)
        .exclude(pk__in=seen)
        .values_list("pk", flat=True)
    ]

    expired = 0
    for pk, reason in due:
        try:
            _transition(
                Listing(pk=pk),
                Status.EXPIRED,
                allowed_from={Status.ACTIVE, Status.PENDING_REVIEW},
                by=None,
                reason=reason,
            )
        except ListingError:
            continue  # Its status changed in the meantime; nothing to do.
        expired += 1
    logger.info("expired %s listings", expired)
    return expired


# --- Editing -----------------------------------------------------------------------


def _require_editable(listing: Listing) -> None:
    if listing.status not in Listing.LIVE_STATUSES:
        raise ListingError("not_editable")


def _back_to_review_if_active(listing: Listing, by: User) -> None:
    """A live listing that changes must be reviewed again before it shows the change."""
    if listing.status == Status.ACTIVE:
        _transition(
            listing, Status.PENDING_REVIEW, allowed_from={Status.ACTIVE}, by=by, reason="edited"
        )


def update_listing(listing: Listing, by: User, *, amenities=None, **fields) -> Listing:
    """Save the advertiser's fields. `fields` are already validated by the serializer;
    anything REGA supplies is ignored here even if it slips through."""
    _require_editable(listing)
    with transaction.atomic():
        for name, value in fields.items():
            if name in ADVERTISER_FIELDS:
                setattr(listing, name, value)
        if listing.purpose == Listing.Purpose.SALE:
            listing.rent_period = ""
        listing.save()
        if amenities is not None:
            listing.amenities.set(amenities)
        _back_to_review_if_active(listing, by)
    return listing


# --- Photos -------------------------------------------------------------------------


def _photo_prefix(listing: Listing) -> str:
    return f"listings/{listing.reference}/"


def _max_photo_bytes() -> int:
    return settings.LISTING_PHOTO_MAX_MB * 1024 * 1024


def presign_photo_upload(listing: Listing, content_type: str, size_bytes: int) -> dict:
    """Give the browser a short-lived URL to PUT one photo straight into storage.

    After uploading, the browser calls confirm_photo() with the returned key.
    """
    _require_editable(listing)
    if content_type not in PHOTO_TYPES:
        raise ListingError("unsupported_photo_type")
    if not 0 < size_bytes <= _max_photo_bytes():
        raise ListingError("photo_too_large")
    if listing.photos.count() >= settings.LISTING_PHOTO_MAX_COUNT:
        raise ListingError("too_many_photos")

    key = f"{_photo_prefix(listing)}{uuid.uuid4().hex}.{PHOTO_TYPES[content_type]}"
    url = s3_client(public=True).generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket_name(), "Key": key, "ContentType": content_type},
        ExpiresIn=PRESIGN_SECONDS,
    )
    return {
        "key": key,
        "upload_url": url,
        "method": "PUT",
        "headers": {"Content-Type": content_type},
        "expires_in": PRESIGN_SECONDS,
    }


def _delete_object(key: str) -> None:
    try:
        s3_client().delete_object(Bucket=bucket_name(), Key=key)
    except (BotoCoreError, ClientError):
        logger.warning("could not delete stored photo %s", key, exc_info=True)


def confirm_photo(listing: Listing, by: User, key: str) -> ListingPhoto:
    """Record a photo the browser has finished uploading. Checks it really is in storage
    and within the limits; a photo that breaks them is deleted."""
    _require_editable(listing)
    if not key.startswith(_photo_prefix(listing)) or ListingPhoto.objects.filter(key=key).exists():
        raise ListingError("invalid_photo_key")
    try:
        head = s3_client().head_object(Bucket=bucket_name(), Key=key)
    except ClientError:
        raise ListingError("photo_not_uploaded") from None

    size = head.get("ContentLength", 0)
    if head.get("ContentType") not in PHOTO_TYPES:
        _delete_object(key)
        raise ListingError("unsupported_photo_type")
    if size > _max_photo_bytes():
        _delete_object(key)
        raise ListingError("photo_too_large")

    try:
        with transaction.atomic():
            locked = Listing.objects.select_for_update().get(pk=listing.pk)
            if locked.photos.count() >= settings.LISTING_PHOTO_MAX_COUNT:
                raise ListingError("too_many_photos")
            last = locked.photos.aggregate(last=Max("position"))["last"]
            photo = ListingPhoto.objects.create(
                listing=locked,
                key=key,
                position=0 if last is None else last + 1,
                size_bytes=size,
            )
            _back_to_review_if_active(listing, by)
    except ListingError:
        _delete_object(key)
        raise
    return photo


def reorder_photos(listing: Listing, photo_ids: list[int]) -> None:
    """Put the photos in this order; the first one becomes the cover."""
    _require_editable(listing)
    with transaction.atomic():
        photos = {p.pk: p for p in listing.photos.select_for_update()}
        if len(photo_ids) != len(photos) or set(photo_ids) != set(photos):
            raise ListingError("invalid_photo_order")
        for position, pk in enumerate(photo_ids):
            photos[pk].position = position
        ListingPhoto.objects.bulk_update(photos.values(), ["position"])


def delete_photo(listing: Listing, by: User, photo_id: int) -> None:
    _require_editable(listing)
    with transaction.atomic():
        photo = listing.photos.select_for_update().filter(pk=photo_id).first()
        if photo is None:
            raise ListingError("photo_not_found")
        key = photo.key
        photo.delete()
        remaining = list(listing.photos.select_for_update())
        for position, p in enumerate(remaining):
            p.position = position
        ListingPhoto.objects.bulk_update(remaining, ["position"])
        _back_to_review_if_active(listing, by)
        transaction.on_commit(lambda: _delete_object(key))


# --- Public ---------------------------------------------------------------------------


def record_view(listing: Listing) -> None:
    Listing.objects.filter(pk=listing.pk).update(view_count=F("view_count") + 1)


def public_listings() -> QuerySet[Listing]:
    """Active listings with what cards and listing pages need loaded in one go."""
    return (
        Listing.objects.filter(status=Listing.Status.ACTIVE)
        .select_related("city", "district", "broker", "agency")
        .prefetch_related("photos")
    )


SORTS = {
    "newest": ("-refreshed_at", "-id"),
    "price_asc": (F("price_halalas").asc(nulls_last=True), "-id"),
    "price_desc": (F("price_halalas").desc(nulls_last=True), "-id"),
}


def search_listings(params: dict) -> QuerySet[Listing]:
    """Filter and sort active listings. `params` is SearchParamsSerializer.validated_data.

    Featured listings (featured_until in the future) always come first, whatever the sort.
    Prices in params are already in halalas.
    """
    qs = public_listings()
    exact = {
        "purpose": "purpose",
        "city": "city__slug_en",
        "district": "district__slug_en",
        "completion": "completion",
        "furnishing": "furnishing",
        "rent_period": "rent_period",
    }
    for param, lookup in exact.items():
        if params.get(param):
            qs = qs.filter(**{lookup: params[param]})
    if params.get("type"):
        qs = qs.filter(property_type__in=params["type"])

    ranges = {
        "price_min": "price_halalas__gte",
        "price_max": "price_halalas__lte",
        "beds_min": "bedrooms__gte",
        "baths_min": "bathrooms__gte",
        "area_min": "area_m2__gte",
        "area_max": "area_m2__lte",
    }
    for param, lookup in ranges.items():
        if params.get(param) is not None:
            qs = qs.filter(**{lookup: params[param]})

    if params.get("bbox"):
        qs = qs.filter(location__within=Polygon.from_bbox(params["bbox"]))

    featured = Case(
        When(featured_until__gt=timezone.now(), then=Value(True)),
        default=Value(False),
        output_field=BooleanField(),
    )
    order = SORTS[params.get("sort") or "newest"]
    return qs.annotate(featured_now=featured).order_by("-featured_now", *order)


# --- Favourites -----------------------------------------------------------------------


def add_favourite(user: User, listing: Listing) -> Favourite:
    """Save a listing for this user. Saving it twice is fine (returns the existing row)."""
    if listing.status != Listing.Status.ACTIVE:
        raise ListingError("not_active")
    favourite, _ = Favourite.objects.get_or_create(user=user, listing=listing)
    return favourite


def remove_favourite(user: User, listing: Listing) -> None:
    Favourite.objects.filter(user=user, listing=listing).delete()


def favourite_listings(user: User) -> QuerySet[Listing]:
    """The user's saved listings that are still active, most recently saved first."""
    return (
        public_listings()
        .filter(favourites__user=user)
        .annotate(saved_at=Max("favourites__created_at", filter=Q(favourites__user=user)))
        .order_by("-saved_at", "-id")
    )


def favourite_references(user: User) -> list[str]:
    return list(
        Favourite.objects.filter(user=user, listing__status=Listing.Status.ACTIVE).values_list(
            "listing__reference", flat=True
        )
    )
