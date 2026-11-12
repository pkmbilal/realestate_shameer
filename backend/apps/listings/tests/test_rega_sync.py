"""Re-checking licences with REGA, and the REGA sync log."""

from datetime import timedelta
from unittest.mock import patch

import pytest

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory
from apps.brokers.tests.factories import VerifiedUserFactory
from apps.core.dates import riyadh_today
from apps.core.models import IntegrationError
from apps.listings import services, tasks
from apps.listings.models import Listing, RegaSync
from apps.listings.services import ListingError
from integrations.rega.mock import MockRegaClient

from .factories import ListingFactory, ListingPhotoFactory, licence_for

pytestmark = pytest.mark.django_db
Status = Listing.Status
Outcome = RegaSync.Outcome


def staff():
    return UserFactory(role=User.Role.STAFF, is_staff=True)


def listing_from_rega(number: str, **kwargs) -> Listing:
    """An active owner listing whose REGA fields match what the mock REGA returns."""
    licence = MockRegaClient().fetch_ad_licence(number)
    city, district = services._match_location(licence)
    listing = ListingFactory(
        licence_number=number,
        licence_expires_on=licence.expires_on,
        purpose=licence.purpose,
        property_type=licence.property_type,
        area_m2=licence.area_m2,
        city=city,
        district=district,
        rent_period="yearly" if licence.purpose == "rent" else "",
        **kwargs,
    )
    ListingPhotoFactory(listing=listing)
    services.submit_for_review(listing, listing.created_by)
    return services.approve(listing, staff())


def test_creating_a_listing_logs_a_sync():
    user = VerifiedUserFactory(role=User.Role.OWNER)
    listing = services.start_listing_from_licence(user, licence_for("sale"))
    sync = listing.rega_syncs.get()
    assert sync.trigger == RegaSync.Trigger.CREATE
    assert sync.outcome == Outcome.OK
    assert sync.created_by == user


def test_matching_licence_is_ok_and_marks_synced():
    listing = listing_from_rega(licence_for("sale"))
    before = listing.rega_synced_at
    sync = services.resync_licence(listing, RegaSync.Trigger.NIGHTLY)
    assert sync.outcome == Outcome.OK
    assert sync.changes == {}
    listing.refresh_from_db()
    assert listing.rega_synced_at > before
    assert listing.status == Status.ACTIVE


def test_renewed_licence_updates_expiry_date():
    listing = listing_from_rega(licence_for("sale"))
    real_expiry = listing.licence_expires_on
    Listing.objects.filter(pk=listing.pk).update(
        licence_expires_on=riyadh_today() + timedelta(days=5)
    )
    listing.refresh_from_db()

    sync = services.resync_licence(listing, RegaSync.Trigger.NIGHTLY)

    assert sync.outcome == Outcome.UPDATED
    assert sync.changes["licence_expires_on"][1] == real_expiry.isoformat()
    listing.refresh_from_db()
    assert listing.licence_expires_on == real_expiry


def test_different_rega_fields_are_logged_not_copied():
    listing = listing_from_rega(licence_for("sale"))
    Listing.objects.filter(pk=listing.pk).update(area_m2=1, purpose="rent")
    listing.refresh_from_db()

    sync = services.resync_licence(listing, RegaSync.Trigger.NIGHTLY)

    assert sync.outcome == Outcome.MISMATCH
    assert sync.changes["area_m2"][0] == 1
    assert sync.changes["purpose"] == ["rent", "sale"]
    listing.refresh_from_db()
    assert listing.area_m2 == 1  # staff decide; nothing REGA-supplied is overwritten here


def test_cancelled_licence_expires_the_listing():
    listing = listing_from_rega(licence_for("sale"))
    Listing.objects.filter(pk=listing.pk).update(licence_number="7200000000")
    listing.refresh_from_db()

    sync = services.resync_licence(listing, RegaSync.Trigger.NIGHTLY)

    assert sync.outcome == Outcome.NOT_FOUND
    listing.refresh_from_db()
    assert listing.status == Status.EXPIRED
    assert listing.status_changes.first().reason == "licence_cancelled"


def test_expired_at_rega_is_left_for_the_expiry_job():
    listing = listing_from_rega(licence_for("sale"))
    Listing.objects.filter(pk=listing.pk).update(licence_number="7200009999")
    listing.refresh_from_db()

    sync = services.resync_licence(listing, RegaSync.Trigger.NIGHTLY)

    assert sync.outcome == Outcome.EXPIRED
    listing.refresh_from_db()
    assert listing.licence_expires_on < riyadh_today()
    assert services.expire_due_listings() == 1


def test_rega_down_changes_nothing_and_logs_an_error():
    listing = listing_from_rega(licence_for("sale"))
    Listing.objects.filter(pk=listing.pk).update(licence_number="7200007777")
    listing.refresh_from_db()
    expiry = listing.licence_expires_on

    sync = services.resync_licence(listing, RegaSync.Trigger.NIGHTLY)

    assert sync.outcome == Outcome.ERROR
    assert sync.error_code == "unavailable"
    listing.refresh_from_db()
    assert listing.status == Status.ACTIVE
    assert listing.licence_expires_on == expiry
    error = IntegrationError.objects.get()
    assert error.integration == "rega"
    assert error.reference == f"listing:{listing.reference}"


def test_unexpected_client_crash_is_an_error_row():
    listing = listing_from_rega(licence_for("sale"))
    with patch(
        "integrations.rega.mock.MockRegaClient.fetch_ad_licence",
        side_effect=TimeoutError("slow"),
    ):
        sync = services.resync_licence(listing, RegaSync.Trigger.MANUAL)
    assert sync.outcome == Outcome.ERROR
    assert IntegrationError.objects.get().error_code == "TimeoutError"


def test_manual_check_on_a_draft_does_not_change_status():
    listing = ListingFactory(licence_number="7200010000")  # ends 0000: not found
    sync = services.resync_licence(listing, RegaSync.Trigger.MANUAL, by=staff())
    assert sync.outcome == Outcome.NOT_FOUND
    listing.refresh_from_db()
    assert listing.status == Status.DRAFT


def test_nightly_job_checks_live_listings_only_and_survives_errors():
    ok = listing_from_rega(licence_for("sale"))
    down = listing_from_rega(licence_for("rent"))
    Listing.objects.filter(pk=down.pk).update(licence_number="7200017777")
    ListingFactory()  # draft: not checked

    counts = tasks.resync_active_licences()

    assert counts == {Outcome.OK: 1, Outcome.ERROR: 1}
    assert RegaSync.objects.filter(trigger=RegaSync.Trigger.NIGHTLY).count() == 2
    assert ok.rega_syncs.filter(trigger=RegaSync.Trigger.NIGHTLY).exists()
    # Running it again just logs another check; nothing breaks.
    tasks.resync_active_licences()
    assert RegaSync.objects.filter(trigger=RegaSync.Trigger.NIGHTLY).count() == 4


def test_rega_outage_when_starting_a_listing_is_logged():
    user = VerifiedUserFactory(role=User.Role.OWNER)
    with pytest.raises(ListingError):
        services.start_listing_from_licence(user, "7300007777")
    assert IntegrationError.objects.get().reference == "licence:7300007777"


def test_unknown_licence_when_starting_is_not_an_integration_error():
    user = VerifiedUserFactory(role=User.Role.OWNER)
    with pytest.raises(ListingError):
        services.start_listing_from_licence(user, "7300000000")
    assert not IntegrationError.objects.exists()
