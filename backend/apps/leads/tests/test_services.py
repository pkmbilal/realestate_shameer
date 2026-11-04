import logging
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import unquote

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory
from apps.brokers.tests.factories import AgencyFactory, BrokerProfileFactory
from apps.leads import services, tasks
from apps.leads.models import Lead
from apps.listings.models import Listing
from apps.listings.tests.factories import ListingFactory
from apps.listings.tests.test_views import make_active

pytestmark = pytest.mark.django_db


def broker_listing(**kwargs):
    broker = BrokerProfileFactory()
    return make_active(created_by=broker.user, broker=broker, **kwargs)


# --- Who to contact ----------------------------------------------------------------------


def test_contact_number_is_broker_whatsapp():
    listing = broker_listing()
    assert services.contact_number(listing) == listing.broker.whatsapp


def test_contact_number_falls_back_to_poster_phone_for_owner_listing():
    listing = make_active()
    assert services.contact_number(listing) == listing.created_by.phone


def test_contact_number_for_agency_only_listing_is_poster_phone():
    agency = AgencyFactory()
    listing = make_active(created_by=agency.admin, agency=agency)
    assert services.contact_number(listing) == agency.admin.phone


def test_whatsapp_url_has_number_reference_and_link(settings):
    settings.SITE_URL = "https://example.sa"
    listing = broker_listing()
    url = services.whatsapp_url(listing, "en")
    assert url.startswith(f"https://wa.me/{listing.broker.whatsapp.lstrip('+')}?text=")
    text = unquote(url)
    assert listing.reference in text
    assert f"https://example.sa/en/listings/{listing.reference}" in text


def test_whatsapp_url_arabic_and_unknown_locale_defaults_to_arabic():
    listing = broker_listing()
    assert "مهتم" in unquote(services.whatsapp_url(listing, "ar"))
    assert "مهتم" in unquote(services.whatsapp_url(listing, "fr"))


def test_tel_url():
    listing = broker_listing()
    assert services.tel_url(listing) == f"tel:{listing.broker.whatsapp}"


def test_fingerprint_is_salted_and_not_raw(settings):
    a = services.client_fingerprint("1.2.3.4", "UA")
    assert "1.2.3.4" not in a and len(a) == 64
    settings.LEAD_HASH_SALT = "other"
    assert services.client_fingerprint("1.2.3.4", "UA") != a


# --- Recording leads ---------------------------------------------------------------------


def test_record_whatsapp_lead_snapshots_broker_and_queues_notice(
    queued, django_capture_on_commit_callbacks
):
    listing = broker_listing()
    with django_capture_on_commit_callbacks(execute=True):
        lead = services.record_lead(listing, "whatsapp", client_hash="h")
    assert lead.broker == listing.broker
    assert lead.channel == Lead.Channel.WHATSAPP
    assert lead.notify_status == Lead.NotifyStatus.PENDING
    queued.assert_called_once_with(lead.pk)


@pytest.mark.parametrize(
    "status", [Listing.Status.DRAFT, Listing.Status.EXPIRED, Listing.Status.TAKEN_DOWN]
)
def test_lead_on_inactive_listing_is_rejected(status):
    listing = ListingFactory(status=status)
    with pytest.raises(services.LeadError) as exc:
        services.record_lead(listing, "call")
    assert exc.value.code == "listing_not_active"
    assert not Lead.objects.exists()


def test_invalid_channel_rejected():
    with pytest.raises(services.LeadError) as exc:
        services.record_lead(broker_listing(), "sms")
    assert exc.value.code == "invalid_channel"


def test_repeat_click_by_same_visitor_is_not_a_new_lead(queued):
    listing = broker_listing()
    first = services.record_lead(listing, "whatsapp", client_hash="h")
    second = services.record_lead(listing, "whatsapp", client_hash="h")
    assert first.pk == second.pk
    assert Lead.objects.count() == 1


def test_repeat_click_by_same_signed_in_user_is_not_a_new_lead(queued):
    listing, user = broker_listing(), UserFactory(role=User.Role.BUYER)
    services.record_lead(listing, "call", user=user, client_hash="a")
    services.record_lead(listing, "call", user=user, client_hash="b")
    assert Lead.objects.count() == 1


def test_different_channel_or_visitor_counts_separately(queued):
    listing = broker_listing()
    services.record_lead(listing, "whatsapp", client_hash="h")
    services.record_lead(listing, "call", client_hash="h")
    services.record_lead(listing, "whatsapp", client_hash="other")
    assert Lead.objects.count() == 3


def test_click_after_dedup_window_is_a_new_lead(queued):
    listing = broker_listing()
    first = services.record_lead(listing, "whatsapp", client_hash="h")
    Lead.objects.filter(pk=first.pk).update(
        created_at=timezone.now() - services.DEDUP_WINDOW - timedelta(minutes=1)
    )
    services.record_lead(listing, "whatsapp", client_hash="h")
    assert Lead.objects.count() == 2


def test_form_lead_requires_name_and_valid_phone():
    with pytest.raises(services.LeadError) as exc:
        services.record_lead(broker_listing(), "form", name=" ", phone="123")
    assert exc.value.code == "invalid"
    assert exc.value.fields == {"name": "required", "phone": "invalid_phone"}


def test_form_lead_normalises_phone_and_is_never_deduplicated(queued):
    listing = broker_listing()
    lead = services.record_lead(
        listing, "form", client_hash="h", name=" Sara ", phone="0512345678", message=" Hi "
    )
    services.record_lead(listing, "form", client_hash="h", name="Sara", phone="0512345678")
    assert (lead.name, lead.phone, lead.message) == ("Sara", "+966512345678", "Hi")
    assert Lead.objects.count() == 2


def test_click_leads_drop_form_fields(queued):
    lead = services.record_lead(broker_listing(), "call", name="x", phone="0512345678")
    assert (lead.name, lead.phone) == ("", "")


# --- Notifying the advertiser ------------------------------------------------------------


def make_lead(listing=None, **kwargs):
    listing = listing or broker_listing()
    return Lead.objects.create(
        listing=listing, broker=listing.broker, agency=listing.agency, channel="form", **kwargs
    )


def test_notify_sends_once_and_is_idempotent():
    lead = make_lead(name="Sara", phone="+966512345678")
    with patch("integrations.whatsapp.mock.MockWhatsAppClient.send_lead_notification") as send:
        assert services.notify_advertiser(lead.pk) == "sent"
        assert services.notify_advertiser(lead.pk) == "sent"
    send.assert_called_once()
    notice = send.call_args.args[0]
    assert notice.to == lead.broker.whatsapp
    assert notice.listing_reference == lead.listing.reference
    assert notice.buyer_phone == "+966512345678"
    lead.refresh_from_db()
    assert lead.notified_at is not None


def test_notify_skips_owner_listing():
    lead = make_lead(listing=make_active())
    assert services.notify_advertiser(lead.pk) == "skipped"


def test_mock_notice_masks_phones_in_logs(caplog):
    lead = make_lead(name="Sara", phone="+966512345678", message="secret message")
    with caplog.at_level(logging.INFO):
        services.notify_advertiser(lead.pk)
    assert "[mock whatsapp]" in caplog.text
    assert "+966512345678" not in caplog.text
    assert lead.broker.whatsapp not in caplog.text
    assert "secret message" not in caplog.text


def test_task_marks_failed_after_last_retry():
    lead = make_lead()
    with (
        patch(
            "integrations.whatsapp.mock.MockWhatsAppClient.send_lead_notification",
            side_effect=RuntimeError("down"),
        ),
        patch.object(tasks.notify_advertiser_of_lead, "max_retries", 0),
    ):
        result = tasks.notify_advertiser_of_lead.apply(args=[lead.pk]).get()
    assert result == "failed"
    lead.refresh_from_db()
    assert lead.notify_status == Lead.NotifyStatus.FAILED


def test_task_retries_on_failure():
    lead = make_lead()
    with (
        patch(
            "integrations.whatsapp.mock.MockWhatsAppClient.send_lead_notification",
            side_effect=RuntimeError("down"),
        ),
        patch.object(tasks.notify_advertiser_of_lead, "retry", side_effect=RuntimeError("retry")),
    ):
        with pytest.raises(RuntimeError, match="retry"):
            tasks.notify_advertiser_of_lead.run(lead.pk)
    lead.refresh_from_db()
    assert lead.notify_status == Lead.NotifyStatus.PENDING
