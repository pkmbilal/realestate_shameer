"""Lead business logic: who to contact, logging each contact and notifying the advertiser."""

import hashlib
from datetime import timedelta
from urllib.parse import quote

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.phone import normalize_phone
from apps.listings.models import Listing
from integrations.whatsapp import LeadNotification, get_whatsapp_client

from .models import Lead

# A repeat WhatsApp/call click by the same visitor within this window is not a new lead.
DEDUP_WINDOW = timedelta(minutes=30)
LOCALES = ("ar", "en")

WHATSAPP_TEXT = {
    "ar": "مرحباً، أنا مهتم بالعقار رقم {reference} المعلن على {portal}: {url}",
    "en": "Hello, I am interested in listing {reference} on {portal}: {url}",
}


class LeadError(Exception):
    def __init__(self, code: str, fields: dict | None = None):
        super().__init__(code)
        self.code = code
        self.fields = fields or {}


def client_fingerprint(ip: str, user_agent: str) -> str:
    """Salted SHA-256 of the visitor's IP and browser. The raw values are never stored."""
    raw = f"{settings.LEAD_HASH_SALT}|{ip or ''}|{user_agent or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()


def contact_number(listing: Listing) -> str:
    """The broker's WhatsApp number, or else the phone of whoever posted the listing."""
    if listing.broker_id and listing.broker.whatsapp:
        return listing.broker.whatsapp
    return listing.created_by.phone


def listing_url(listing: Listing, locale: str) -> str:
    return f"{settings.SITE_URL}/{locale}/listings/{listing.reference}"


def whatsapp_url(listing: Listing, locale: str) -> str:
    """wa.me deep link with a pre-filled message that names the listing reference."""
    locale = locale if locale in LOCALES else "ar"
    text = WHATSAPP_TEXT[locale].format(
        reference=listing.reference, portal=settings.PORTAL_NAME, url=listing_url(listing, locale)
    )
    return f"https://wa.me/{contact_number(listing).lstrip('+')}?text={quote(text)}"


def tel_url(listing: Listing) -> str:
    return f"tel:{contact_number(listing)}"


def _recent_duplicate(listing, channel, user, client_hash) -> Lead | None:
    if not (user or client_hash):
        return None
    recent = Lead.objects.filter(
        listing=listing, channel=channel, created_at__gte=timezone.now() - DEDUP_WINDOW
    )
    recent = recent.filter(user=user) if user else recent.filter(client_hash=client_hash)
    return recent.first()


def _clean_form(name: str, phone: str, message: str) -> tuple[str, str, str]:
    errors = {}
    name = (name or "").strip()
    if not name:
        errors["name"] = "required"
    try:
        phone = normalize_phone(phone)
    except ValidationError:
        errors["phone"] = "invalid_phone"
    if errors:
        raise LeadError("invalid", errors)
    return name[:100], phone, (message or "").strip()[:1000]


def record_lead(
    listing: Listing,
    channel: str,
    *,
    user: User | None = None,
    client_hash: str = "",
    name: str = "",
    phone: str = "",
    message: str = "",
) -> Lead:
    """Log a contact on an active listing and queue the advertiser's WhatsApp notification."""
    if listing.status != Listing.Status.ACTIVE:
        raise LeadError("listing_not_active")
    if channel not in Lead.Channel.values:
        raise LeadError("invalid_channel")

    if channel == Lead.Channel.FORM:
        name, phone, message = _clean_form(name, phone, message)
    else:
        name = phone = message = ""
        duplicate = _recent_duplicate(listing, channel, user, client_hash)
        if duplicate:
            return duplicate

    lead = Lead.objects.create(
        listing=listing,
        broker=listing.broker,
        agency=listing.agency,
        channel=channel,
        user=user,
        client_hash=client_hash,
        name=name,
        phone=phone,
        message=message,
    )

    from .tasks import notify_advertiser_of_lead  # imported here to avoid an import cycle

    transaction.on_commit(lambda: notify_advertiser_of_lead.delay(lead.pk))
    return lead


def notify_advertiser(lead_id: int) -> str:
    """Send the WhatsApp notice for one lead. Safe to call more than once.

    Returns the lead's notify_status. Client errors propagate so the Celery task retries.
    """
    with transaction.atomic():
        lead = Lead.objects.select_for_update().get(pk=lead_id)
        if lead.notify_status != Lead.NotifyStatus.PENDING:
            return lead.notify_status
        broker = lead.broker
        if not (broker and broker.whatsapp):
            # Owner and agency-only listings: visitors contact the owner's phone directly.
            lead.notify_status = Lead.NotifyStatus.SKIPPED
            lead.save(update_fields=["notify_status"])
            return lead.notify_status

        locale = "ar"
        get_whatsapp_client().send_lead_notification(
            LeadNotification(
                to=broker.whatsapp,
                listing_reference=lead.listing.reference,
                listing_url=listing_url(lead.listing, locale),
                channel=lead.channel,
                buyer_name=lead.name,
                buyer_phone=lead.phone,
                message=lead.message,
                locale=locale,
            )
        )
        lead.notify_status = Lead.NotifyStatus.SENT
        lead.notified_at = timezone.now()
        lead.save(update_fields=["notify_status", "notified_at"])
        return lead.notify_status


def mark_notify_failed(lead_id: int) -> None:
    Lead.objects.filter(pk=lead_id, notify_status=Lead.NotifyStatus.PENDING).update(
        notify_status=Lead.NotifyStatus.FAILED
    )
