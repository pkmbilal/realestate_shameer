"""WhatsApp warnings to advertisers a few days before a listing comes down."""

import logging
from datetime import datetime, time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from apps.brokers.tests.factories import BrokerProfileFactory
from apps.core.dates import riyadh_today
from apps.core.models import IntegrationError
from apps.listings import services, tasks
from apps.listings.models import Listing

from .factories import ListingFactory

pytestmark = pytest.mark.django_db
SEND = "integrations.whatsapp.mock.MockWhatsAppClient.send_expiry_warning"
RIYADH = ZoneInfo("Asia/Riyadh")


def in_days(n):
    return riyadh_today() + timedelta(days=n)


def riyadh_noon(day):
    return datetime.combine(day, time(12, 0), tzinfo=RIYADH)


def active(licence_days=90, post_days=30, **kwargs):
    """An active listing; statuses are set directly because these tests are about dates."""
    return ListingFactory(
        status=Listing.Status.ACTIVE,
        licence_expires_on=in_days(licence_days),
        post_expires_at=riyadh_noon(in_days(post_days)),
        published_at=timezone.now(),
        **kwargs,
    )


def test_picks_listings_coming_down_within_three_days():
    licence_soon = active(licence_days=3)
    post_soon = active(post_days=2)
    today = active(licence_days=0)
    active(licence_days=4)  # not yet
    active(post_days=10)  # not yet
    ListingFactory(licence_expires_on=in_days(1))  # draft: never warned

    due = {x.pk for x in services.listings_to_warn()}

    assert due == {licence_soon.pk, post_soon.pk, today.pk}


def test_earlier_of_licence_and_post_period_decides():
    listing = active(licence_days=2, post_days=3)
    assert services.coming_down(listing) == (in_days(2), "licence")
    listing = active(licence_days=20, post_days=1)
    assert services.coming_down(listing) == (in_days(1), "post_period")


def test_send_warns_once_per_expiry_date():
    listing = active(licence_days=3)
    with patch(SEND) as send:
        assert services.send_expiry_warning(listing.pk) == "sent"
        assert services.send_expiry_warning(listing.pk) == "skipped"
    send.assert_called_once()
    warning = send.call_args.args[0]
    assert warning.listing_reference == listing.reference
    assert warning.expires_on == in_days(3)
    assert warning.reason == "licence"
    assert warning.dashboard_url.endswith("/ar/dashboard")
    listing.refresh_from_db()
    assert listing.expiry_warned_for == in_days(3)
    assert services.listings_to_warn() == []


def test_extended_listing_is_warned_again_before_the_new_date():
    listing = active(post_days=2)
    with patch(SEND):
        services.send_expiry_warning(listing.pk)
    # The advertiser renews: a new post period ends later; warn again near that date.
    Listing.objects.filter(pk=listing.pk).update(post_expires_at=riyadh_noon(in_days(3)))
    assert [x.pk for x in services.listings_to_warn()] == [listing.pk]


def test_broker_gets_it_on_whatsapp_owner_on_their_phone():
    broker = BrokerProfileFactory()
    broker_listing = active(licence_days=1, broker=broker, created_by=broker.user)
    owner_listing = active(licence_days=1)
    with patch(SEND) as send:
        services.send_expiry_warning(broker_listing.pk)
        services.send_expiry_warning(owner_listing.pk)
    assert send.call_args_list[0].args[0].to == broker.whatsapp
    assert send.call_args_list[1].args[0].to == owner_listing.created_by.phone


def test_listing_no_longer_active_is_skipped():
    listing = active(licence_days=1)
    Listing.objects.filter(pk=listing.pk).update(status=Listing.Status.ARCHIVED)
    with patch(SEND) as send:
        assert services.send_expiry_warning(listing.pk) == "skipped"
    send.assert_not_called()


def test_daily_job_queues_one_task_per_listing():
    a = active(licence_days=1)
    b = active(post_days=3)
    with patch.object(tasks.send_listing_expiry_warning, "delay") as delay:
        assert tasks.warn_expiring_listings() == 2
    assert {c.args[0] for c in delay.call_args_list} == {a.pk, b.pk}


def test_failed_send_is_retried_then_logged():
    listing = active(licence_days=1)
    with (
        patch(SEND, side_effect=RuntimeError("whatsapp down for +966512345678")),
        patch.object(tasks.send_listing_expiry_warning, "max_retries", 0),
    ):
        result = tasks.send_listing_expiry_warning.apply(args=[listing.pk]).get()
    assert result == "failed"
    listing.refresh_from_db()
    assert listing.expiry_warned_for is None  # the next daily run tries again
    error = IntegrationError.objects.get()
    assert error.integration == "whatsapp"
    assert error.reference == f"listing:{listing.reference}"
    assert "966512345678" not in error.message


def test_failed_send_retries_first():
    listing = active(licence_days=1)
    with (
        patch(SEND, side_effect=RuntimeError("down")),
        patch.object(tasks.send_listing_expiry_warning, "retry", side_effect=RuntimeError("retry")),
    ):
        with pytest.raises(RuntimeError, match="retry"):
            tasks.send_listing_expiry_warning.run(listing.pk)
    assert not IntegrationError.objects.exists()


def test_mock_warning_masks_the_phone(caplog):
    listing = active(licence_days=1)
    with caplog.at_level(logging.INFO):
        services.send_expiry_warning(listing.pk)
    assert "[mock whatsapp]" in caplog.text
    assert listing.created_by.phone not in caplog.text
