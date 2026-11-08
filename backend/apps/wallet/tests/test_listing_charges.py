"""How listing actions spend and refund credits (apps/listings/services.py)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.brokers.tests.factories import AgencyFactory, VerifiedUserFactory
from apps.listings import services as listings
from apps.listings.models import Listing
from apps.listings.tests.factories import ListingFactory, ListingPhotoFactory
from apps.wallet import services
from apps.wallet.models import CreditTransaction

pytestmark = pytest.mark.django_db
Kind = CreditTransaction.Kind
Action = CreditTransaction.Action
Status = Listing.Status


def error_code(fn, *args, **kwargs):
    with pytest.raises(listings.ListingError) as exc:
        fn(*args, **kwargs)
    return exc.value.code


def balance(wallet):
    wallet.refresh_from_db()
    return wallet.balance


@pytest.fixture
def post_costs_10(set_price):
    return set_price(Action.POST, 10)


# --- Posting -------------------------------------------------------------------------


def test_submit_charges_the_post_price(funded_wallet, broker_listing, post_costs_10):
    listings.submit_for_review(broker_listing, broker_listing.created_by)
    assert balance(funded_wallet) == 90
    spend = funded_wallet.transactions.get(kind=Kind.SPEND)
    assert spend.action == Action.POST
    assert spend.listing == broker_listing


def test_approve_does_not_charge_again(funded_wallet, broker_listing, post_costs_10, staff):
    listings.submit_for_review(broker_listing, broker_listing.created_by)
    listings.approve(broker_listing, staff)
    assert broker_listing.status == Status.ACTIVE
    assert balance(funded_wallet) == 90


def test_submit_without_enough_credits_is_refused(broker, broker_listing, set_price):
    set_price(Action.POST, 10)
    code = error_code(listings.submit_for_review, broker_listing, broker.user)
    assert code == "insufficient_credits"
    broker_listing.refresh_from_db()
    assert broker_listing.status == Status.DRAFT
    assert not broker_listing.status_changes.exists()  # the transition was rolled back


def test_free_post_needs_no_credits(broker, broker_listing):
    listings.submit_for_review(broker_listing, broker.user)
    assert broker_listing.status == Status.PENDING_REVIEW
    assert not CreditTransaction.objects.exists()


def test_owner_listings_are_free(post_costs_10):
    listing = ListingFactory()  # created by an owner
    ListingPhotoFactory(listing=listing)
    listings.submit_for_review(listing, listing.created_by)
    assert listing.status == Status.PENDING_REVIEW
    assert not CreditTransaction.objects.exists()


def test_agency_admin_listing_charges_the_agency(post_costs_10, staff):
    agency = AgencyFactory()
    wallet = services.wallet_for_user(agency.admin)
    services.grant(wallet, 25, staff, "x")
    listing = ListingFactory(created_by=agency.admin, agency=agency)
    ListingPhotoFactory(listing=listing)
    listings.submit_for_review(listing, agency.admin)
    assert balance(wallet) == 15


# --- Refunds ---------------------------------------------------------------------------


def test_reject_refunds_the_post_charge_once(funded_wallet, broker_listing, post_costs_10, staff):
    listings.submit_for_review(broker_listing, broker_listing.created_by)
    listings.reject(broker_listing, staff, "Blurry photos")
    assert balance(funded_wallet) == 100
    refund = funded_wallet.transactions.get(kind=Kind.REFUND)
    assert refund.amount == 10

    # Fixed and sent again: charged again, then approved without a second charge.
    listings.submit_for_review(broker_listing, broker_listing.created_by)
    assert balance(funded_wallet) == 90
    listings.approve(broker_listing, staff)
    assert balance(funded_wallet) == 90
    assert services.balance_matches_ledger(funded_wallet)


def test_withdrawing_before_review_refunds(funded_wallet, broker_listing, post_costs_10):
    listings.submit_for_review(broker_listing, broker_listing.created_by)
    listings.archive(broker_listing, broker_listing.created_by)
    assert balance(funded_wallet) == 100


def test_archiving_a_live_listing_keeps_the_charge(
    funded_wallet, broker_listing, post_costs_10, staff
):
    listings.submit_for_review(broker_listing, broker_listing.created_by)
    listings.approve(broker_listing, staff)
    listings.archive(broker_listing, broker_listing.created_by)
    assert balance(funded_wallet) == 90


def test_licence_expiring_during_review_refunds(funded_wallet, broker_listing, post_costs_10):
    listings.submit_for_review(broker_listing, broker_listing.created_by)
    Listing.objects.filter(pk=broker_listing.pk).update(
        licence_expires_on=timezone.localdate() - timedelta(days=2)
    )
    assert listings.expire_due_listings() == 1
    assert balance(funded_wallet) == 100
    listings.expire_due_listings()  # running again changes nothing
    assert balance(funded_wallet) == 100


def test_take_down_keeps_the_charge(funded_wallet, broker_listing, post_costs_10, staff):
    listings.submit_for_review(broker_listing, broker_listing.created_by)
    listings.take_down(broker_listing, staff, "Misleading")
    assert balance(funded_wallet) == 90


# --- Editing a live listing ------------------------------------------------------------


def test_editing_a_live_listing_is_not_charged(funded_wallet, broker_listing, post_costs_10, staff):
    user = broker_listing.created_by
    listings.submit_for_review(broker_listing, user)
    listings.approve(broker_listing, staff)
    listings.update_listing(broker_listing, user, price_halalas=90_000_000)
    assert broker_listing.status == Status.PENDING_REVIEW
    listings.reject(broker_listing, staff, "Price looks wrong")  # nothing to refund
    listings.submit_for_review(broker_listing, user)
    listings.approve(broker_listing, staff)
    assert balance(funded_wallet) == 90


def test_post_period_ending_during_review_is_charged_on_approval(
    funded_wallet, broker_listing, post_costs_10, staff
):
    user = broker_listing.created_by
    listings.submit_for_review(broker_listing, user)
    listings.approve(broker_listing, staff)
    listings.update_listing(broker_listing, user, bedrooms=4)  # back to review, period running
    Listing.objects.filter(pk=broker_listing.pk).update(
        post_expires_at=timezone.now() - timedelta(minutes=1)
    )
    broker_listing.refresh_from_db()
    listings.approve(broker_listing, staff)
    assert balance(funded_wallet) == 80
    assert broker_listing.post_expires_at > timezone.now() + timedelta(days=29)


def test_approve_fails_when_new_period_cannot_be_paid(broker, broker_listing, set_price, staff):
    wallet = services.wallet_for_user(broker.user)
    listings.submit_for_review(broker_listing, broker.user)  # free at the time
    listings.approve(broker_listing, staff)
    listings.update_listing(broker_listing, broker.user, bedrooms=4)
    Listing.objects.filter(pk=broker_listing.pk).update(
        post_expires_at=timezone.now() - timedelta(minutes=1)
    )
    broker_listing.refresh_from_db()
    set_price(Action.POST, 10)
    assert error_code(listings.approve, broker_listing, staff) == "insufficient_credits"
    broker_listing.refresh_from_db()
    assert broker_listing.status == Status.PENDING_REVIEW
    assert balance(wallet) == 0


# --- Refresh and feature ---------------------------------------------------------------


@pytest.fixture
def live_listing(funded_wallet, broker_listing, staff):
    listings.submit_for_review(broker_listing, broker_listing.created_by)
    return listings.approve(broker_listing, staff)


def test_refresh_moves_listing_to_top_and_charges(live_listing, funded_wallet, set_price):
    set_price(Action.REFRESH, 5)
    before = live_listing.refreshed_at
    listings.refresh_listing(live_listing, live_listing.created_by)
    assert live_listing.refreshed_at > before
    assert balance(funded_wallet) == 95
    assert funded_wallet.transactions.filter(action=Action.REFRESH, listing=live_listing).exists()


def test_feature_sets_days_and_stacks(live_listing, funded_wallet, set_price):
    set_price(Action.FEATURE, 30, days=7)
    listings.feature_listing(live_listing, live_listing.created_by)
    first_end = live_listing.featured_until
    assert first_end > timezone.now() + timedelta(days=6, hours=23)
    listings.feature_listing(live_listing, live_listing.created_by)
    assert live_listing.featured_until == first_end + timedelta(days=7)
    assert balance(funded_wallet) == 40


def test_feature_needs_days_configured(live_listing, set_price):
    set_price(Action.FEATURE, 30, days=0)
    code = error_code(listings.feature_listing, live_listing, live_listing.created_by)
    assert code == "feature_unavailable"


def test_paid_actions_only_on_live_listings(funded_wallet, broker_listing):
    user = broker_listing.created_by
    assert error_code(listings.refresh_listing, broker_listing, user) == "not_active"
    assert error_code(listings.feature_listing, broker_listing, user) == "not_active"


def test_paid_action_without_credits_changes_nothing(live_listing, funded_wallet, set_price):
    set_price(Action.REFRESH, 500)
    before = live_listing.refreshed_at
    code = error_code(listings.refresh_listing, live_listing, live_listing.created_by)
    assert code == "insufficient_credits"
    live_listing.refresh_from_db()
    assert live_listing.refreshed_at == before


def test_owners_cannot_refresh_or_feature(staff):
    owner = VerifiedUserFactory(role=User.Role.OWNER)
    listing = ListingFactory(created_by=owner)
    ListingPhotoFactory(listing=listing)
    listings.submit_for_review(listing, owner)
    listings.approve(listing, staff)
    assert error_code(listings.refresh_listing, listing, owner) == "paid_actions_unavailable"
    assert error_code(listings.feature_listing, listing, owner) == "paid_actions_unavailable"
