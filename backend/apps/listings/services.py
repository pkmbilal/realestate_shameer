"""Listing business logic: start from a REGA licence, edit, moderate, expire, photos.

Views and admin call these functions; they never change `Listing.status` themselves.
Every status change is written to ListingStatusChange inside a locked transaction.
"""

import logging
import re
import uuid
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.contrib.gis.geos import Polygon
from django.db import IntegrityError, transaction
from django.db.models import BooleanField, Case, F, Max, Q, QuerySet, Value, When
from django.utils import timezone

from apps.accounts.models import User
from apps.brokers.models import Agency, BrokerProfile
from apps.core.dates import riyadh_today
from apps.core.models import IntegrationError
from apps.core.services import record_integration_error
from apps.core.storage import bucket_name, s3_client
from apps.leads.services import contact_number
from apps.locations.models import City, District
from apps.wallet import services as wallet_services
from apps.wallet.models import CreditTransaction
from integrations.rega import RegaAdLicence, RegaError, get_rega_client
from integrations.whatsapp import ExpiryWarning, get_whatsapp_client

from .models import Favourite, Listing, ListingPhoto, ListingStatusChange, RegaSync

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
        if exc.code != "not_found":  # not_found is usually a typo, not an outage
            record_integration_error(
                IntegrationError.Integration.REGA,
                "fetch_ad_licence",
                exc,
                reference=f"licence:{number}",
            )
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
            listing = Listing.objects.create(
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
            RegaSync.objects.create(
                listing=listing,
                licence_number=number,
                trigger=RegaSync.Trigger.CREATE,
                outcome=RegaSync.Outcome.OK,
                created_by=user,
            )
            return listing
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


# --- Credits (brokers and agencies pay; owner listings are free) ----------------------


def _post_period_active(listing: Listing) -> bool:
    return listing.post_expires_at is not None and listing.post_expires_at > timezone.now()


def _charge(listing: Listing, action: str, by: User | None):
    """Take the credits for `action` from the listing's wallet (none for owners)."""
    wallet = wallet_services.wallet_for_listing(listing)
    if wallet is None:
        return None
    try:
        return wallet_services.charge(wallet, action, listing=listing, by=by)
    except wallet_services.WalletError as exc:
        raise ListingError(exc.code) from None


def _unused_post_charges(listing: Listing):
    """Post charges paid since the listing last went live: paid for, but not yet used."""
    charges = CreditTransaction.objects.filter(
        listing=listing,
        kind=CreditTransaction.Kind.SPEND,
        action=CreditTransaction.Action.POST,
        reversed_by__isnull=True,
    )
    last_live = ListingStatusChange.objects.filter(
        listing=listing, to_status=Status.ACTIVE
    ).aggregate(at=Max("created_at"))["at"]
    if last_live is not None:
        charges = charges.filter(created_at__gt=last_live)
    return charges


def _refund_unused_post_charge(listing: Listing, by: User | None) -> None:
    """A submission that ends without going live (rejected, withdrawn, expired) gets its
    post credits back. Safe to call more than once."""
    for entry in _unused_post_charges(listing):
        try:
            # No note: the row already shows "refund · post" and the listing reference.
            wallet_services.refund(entry, by=by)
        except wallet_services.WalletError:
            continue  # Already refunded by another request.


def submit_for_review(listing: Listing, by: User) -> Listing:
    """Send a draft to moderation. Takes the post credits unless a post period is still
    running (e.g. a live listing that was edited); they are refunded if it is rejected."""
    missing = missing_fields(listing)
    if missing:
        raise ListingError("incomplete", missing)
    _require_valid_licence(listing)
    with transaction.atomic():
        listing = _transition(
            listing,
            Status.PENDING_REVIEW,
            allowed_from={Status.DRAFT},
            by=by,
            moderation_note="",
        )
        if not _post_period_active(listing) and not _unused_post_charges(listing).exists():
            _charge(listing, CreditTransaction.Action.POST, by)
    return listing


def approve(listing: Listing, by: User) -> Listing:
    """Publish a reviewed listing for LISTING_POST_DAYS days.

    Re-approving after an edit keeps the original post period. If that period ran out while
    the listing waited for review, a new one starts and is charged now.
    """
    _require_valid_licence(listing)
    now = timezone.now()
    post_expires_at = listing.post_expires_at
    with transaction.atomic():
        if post_expires_at is None or post_expires_at <= now:
            post_expires_at = now + timedelta(days=settings.LISTING_POST_DAYS)
            if not _unused_post_charges(listing).exists():
                _charge(listing, CreditTransaction.Action.POST, by)
        return _transition(
            listing,
            Status.ACTIVE,
            allowed_from={Status.PENDING_REVIEW},
            by=by,
            published_at=listing.published_at or now,
            refreshed_at=listing.refreshed_at or now,
            post_expires_at=post_expires_at,
        )


def _paid_action(listing: Listing, by: User, action: str, apply) -> Listing:
    """Charge `action` on a live listing and apply its effect, all or nothing."""
    if wallet_services.wallet_for_listing(listing) is None:
        raise ListingError("paid_actions_unavailable")
    with transaction.atomic():
        locked = Listing.objects.select_for_update().get(pk=listing.pk)
        if locked.status != Status.ACTIVE:
            raise ListingError("not_active")
        apply(locked)
        locked.save()
        _charge(locked, action, by)
    listing.refresh_from_db()
    return listing


def refresh_listing(listing: Listing, by: User) -> Listing:
    """Move a live listing back to the top of "newest"."""

    def apply(locked):
        locked.refreshed_at = timezone.now()

    return _paid_action(listing, by, CreditTransaction.Action.REFRESH, apply)


def feature_listing(listing: Listing, by: User) -> Listing:
    """Pin a live listing on top of search for the configured number of days. Buying again
    while it is featured adds the days on to the end."""
    days = wallet_services.price_for(CreditTransaction.Action.FEATURE).days
    if days <= 0:
        raise ListingError("feature_unavailable")

    def apply(locked):
        now = timezone.now()
        start = max(now, locked.featured_until or now)
        locked.featured_until = start + timedelta(days=days)

    return _paid_action(listing, by, CreditTransaction.Action.FEATURE, apply)


def _require_reason(reason: str) -> str:
    reason = (reason or "").strip()
    if not reason:
        raise ListingError("reason_required")
    return reason


def reject(listing: Listing, by: User, reason: str) -> Listing:
    """Send a listing back to the advertiser with the reason shown to them."""
    reason = _require_reason(reason)
    with transaction.atomic():
        listing = _transition(
            listing,
            Status.DRAFT,
            allowed_from={Status.PENDING_REVIEW},
            by=by,
            reason=reason,
            moderation_note=reason[:500],
        )
        _refund_unused_post_charge(listing, by)
    return listing


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
    """The advertiser removes their own listing (sold, rented, or no longer offered).
    Withdrawing it before it was ever published refunds the post credits."""
    with transaction.atomic():
        listing = _transition(
            listing,
            Status.ARCHIVED,
            allowed_from={*Listing.LIVE_STATUSES, Status.EXPIRED},
            by=by,
        )
        _refund_unused_post_charge(listing, by)
    return listing


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

    expired = sum(_expire(pk, reason, by=None) for pk, reason in due)
    logger.info("expired %s listings", expired)
    return expired


def _expire(pk: int, reason: str, by: User | None) -> bool:
    """Expire one active or pending listing. False if its status changed in the meantime."""
    try:
        with transaction.atomic():
            listing = _transition(
                Listing(pk=pk),
                Status.EXPIRED,
                allowed_from={Status.ACTIVE, Status.PENDING_REVIEW},
                by=by,
                reason=reason,
            )
            # A licence that expires while waiting for review never went live.
            _refund_unused_post_charge(listing, by)
    except ListingError:
        return False
    return True


# --- Re-checking licences with REGA ---------------------------------------------------


def _rega_differences(listing: Listing, licence: RegaAdLicence) -> dict:
    """REGA fields (other than the expiry date) where REGA now says something else.
    These are not copied automatically; staff review them."""
    diff = {}
    for name, ours, theirs in (
        ("purpose", listing.purpose, licence.purpose),
        ("property_type", listing.property_type, licence.property_type),
        ("area_m2", listing.area_m2, licence.area_m2),
    ):
        if ours != theirs:
            diff[name] = [ours, theirs]
    city, district = listing.city, listing.district
    if not _same_place(city, licence.city_name_ar, licence.city_name_en):
        diff["city"] = [city.name_en, licence.city_name_en]
    if district is not None and not _same_place(
        district, licence.district_name_ar, licence.district_name_en
    ):
        diff["district"] = [district.name_en, licence.district_name_en]
    return diff


def _same_place(place, name_ar: str, name_en: str) -> bool:
    """Same matching rule as _match_location: Arabic name, or English name ignoring case."""
    return place.name_ar == name_ar or place.name_en.lower() == name_en.lower()


def resync_licence(listing: Listing, trigger: str, by: User | None = None) -> RegaSync:
    """Read the listing's licence from REGA again and log the result as a RegaSync row.

    - New expiry date at REGA (renewed or shortened): copied to the listing.
    - Other REGA fields differ: logged as a mismatch for staff; the listing is not changed.
    - Licence gone at REGA (cancelled): an active or pending listing is expired.
    - REGA did not answer: nothing changes; the failure goes to the integration error log.
    Safe to run any number of times.
    """

    def log(outcome, changes=None, error_code=""):
        return RegaSync.objects.create(
            listing=listing,
            licence_number=listing.licence_number,
            trigger=trigger,
            outcome=outcome,
            changes=changes or {},
            error_code=error_code,
            created_by=by,
        )

    try:
        licence = get_rega_client().fetch_ad_licence(listing.licence_number)
    except RegaError as exc:
        if exc.code == "not_found":
            _expire(listing.pk, "licence_cancelled", by=by)
            listing.refresh_from_db()
            return log(RegaSync.Outcome.NOT_FOUND)
        error = exc
    except Exception as exc:  # The live client may fail in ways we can't list.
        error = exc
    else:
        error = None

    if error is not None:
        record_integration_error(
            IntegrationError.Integration.REGA,
            "fetch_ad_licence",
            error,
            reference=f"listing:{listing.reference}",
        )
        return log(RegaSync.Outcome.ERROR, error_code=getattr(error, "code", "") or "error")

    changes = _rega_differences(listing, licence)
    with transaction.atomic():
        locked = Listing.objects.select_for_update().get(pk=listing.pk)
        expiry_changed = locked.licence_expires_on != licence.expires_on
        if expiry_changed:
            changes["licence_expires_on"] = [
                locked.licence_expires_on.isoformat(),
                licence.expires_on.isoformat(),
            ]
        locked.licence_expires_on = licence.expires_on
        locked.rega_data = licence.raw
        locked.rega_synced_at = timezone.now()
        locked.save(
            update_fields=["licence_expires_on", "rega_data", "rega_synced_at", "updated_at"]
        )
        if licence.expires_on < riyadh_today():
            outcome = RegaSync.Outcome.EXPIRED  # the nightly expiry job takes it down
        elif set(changes) - {"licence_expires_on"}:
            outcome = RegaSync.Outcome.MISMATCH
        elif expiry_changed:
            outcome = RegaSync.Outcome.UPDATED
        else:
            outcome = RegaSync.Outcome.OK
        sync = log(outcome, changes)
    listing.refresh_from_db()
    return sync


def resync_active_licences() -> dict[str, int]:
    """Nightly: re-check the licence of every active or pending listing with REGA.
    One listing failing never stops the rest. Returns how many ended with each outcome."""
    counts: dict[str, int] = {}
    listings = Listing.objects.filter(
        status__in=(Status.ACTIVE, Status.PENDING_REVIEW)
    ).select_related("city", "district")
    for listing in listings.iterator(chunk_size=200):
        try:
            outcome = str(resync_licence(listing, RegaSync.Trigger.NIGHTLY).outcome)
        except Exception:
            logger.exception("REGA re-check failed for listing %s", listing.reference)
            outcome = "crashed"
        counts[outcome] = counts.get(outcome, 0) + 1
    logger.info("REGA re-check: %s", counts)
    return counts


# --- Warning advertisers before a listing comes down ----------------------------------


def _riyadh_date(dt) -> date:
    return dt.astimezone(ZoneInfo(settings.DISPLAY_TIME_ZONE)).date()


def coming_down(listing: Listing) -> tuple[date, str]:
    """The (Riyadh) date an active listing comes down, and why: "licence" or "post_period"."""
    options = [(listing.licence_expires_on, "licence")]
    if listing.post_expires_at is not None:
        options.append((_riyadh_date(listing.post_expires_at), "post_period"))
    return min(options)


def listings_to_warn() -> list[Listing]:
    """Active listings that come down within LISTING_EXPIRY_WARNING_DAYS and whose
    advertiser has not been warned about that date yet. Catches up if a day was missed."""
    days = settings.LISTING_EXPIRY_WARNING_DAYS
    today = riyadh_today()
    last_day = today + timedelta(days=days)
    # A generous database filter; the exact Riyadh-date check is done below.
    post_cutoff = timezone.now() + timedelta(days=days + 1)
    candidates = Listing.objects.filter(status=Status.ACTIVE).filter(
        Q(licence_expires_on__lte=last_day) | Q(post_expires_at__lt=post_cutoff)
    )
    due = []
    for listing in candidates:
        expires_on = coming_down(listing)[0]
        if today <= expires_on <= last_day and listing.expiry_warned_for != expires_on:
            due.append(listing)
    return due


def send_expiry_warning(listing_id: int) -> str:
    """WhatsApp the advertiser that this listing comes down soon. Safe to call again:
    each expiry date is warned about once. Client errors propagate so the task retries.

    Returns "sent" or "skipped" (no longer active, or already warned for this date).
    """
    with transaction.atomic():
        # Lock only the listing row (broker is an optional join, which Postgres can't lock).
        listing = (
            Listing.objects.select_for_update(of=("self",))
            .select_related("broker", "created_by")
            .get(pk=listing_id)
        )
        if listing.status != Status.ACTIVE:
            return "skipped"
        expires_on, reason = coming_down(listing)
        if listing.expiry_warned_for == expires_on:
            return "skipped"
        locale = "ar"
        get_whatsapp_client().send_expiry_warning(
            ExpiryWarning(
                to=contact_number(listing),
                listing_reference=listing.reference,
                expires_on=expires_on,
                reason=reason,
                dashboard_url=f"{settings.SITE_URL}/{locale}/dashboard",
                locale=locale,
            )
        )
        listing.expiry_warned_for = expires_on
        listing.save(update_fields=["expiry_warned_for", "updated_at"])
    return "sent"


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
