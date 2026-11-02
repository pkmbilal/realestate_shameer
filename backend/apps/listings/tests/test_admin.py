import pytest
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.urls import reverse

from apps.accounts.models import User
from apps.listings import services
from apps.listings.models import Listing

from .factories import ListingFactory, ListingPhotoFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client):
    admin = User.objects.create_superuser(phone="+966511111111", password="x")
    client.force_login(admin)
    return client


def pending_listing():
    listing = ListingFactory()
    ListingPhotoFactory(listing=listing)
    return services.submit_for_review(listing, listing.created_by)


def test_moderation_queue_shows_only_pending(admin_client):
    pending = pending_listing()
    draft = ListingFactory()
    page = admin_client.get(reverse("admin:listings_pendinglisting_changelist")).content.decode()
    assert pending.reference in page
    assert draft.reference not in page


def test_approve_action(admin_client):
    listing = pending_listing()
    admin_client.post(
        reverse("admin:listings_pendinglisting_changelist"),
        {"action": "approve_listings", ACTION_CHECKBOX_NAME: [listing.pk]},
    )
    listing.refresh_from_db()
    assert listing.status == Listing.Status.ACTIVE


def test_reject_action_asks_for_reason_then_applies(admin_client):
    listing = pending_listing()
    url = reverse("admin:listings_pendinglisting_changelist")
    data = {"action": "reject_listings", ACTION_CHECKBOX_NAME: [listing.pk]}

    response = admin_client.post(url, data)
    assert response.status_code == 200
    assert b'name="reason"' in response.content
    listing.refresh_from_db()
    assert listing.status == Listing.Status.PENDING_REVIEW

    admin_client.post(url, {**data, "apply": "1", "reason": "Wrong district photos"})
    listing.refresh_from_db()
    assert listing.status == Listing.Status.DRAFT
    assert listing.status_changes.first().reason == "Wrong district photos"


def test_take_down_from_all_listings(admin_client):
    listing = pending_listing()
    admin_client.post(
        reverse("admin:listings_listing_changelist"),
        {
            "action": "take_down_listings",
            ACTION_CHECKBOX_NAME: [listing.pk],
            "apply": "1",
            "reason": "Complaint upheld",
        },
    )
    listing.refresh_from_db()
    assert listing.status == Listing.Status.TAKEN_DOWN


def test_listing_change_page_renders(admin_client):
    listing = pending_listing()
    response = admin_client.get(reverse("admin:listings_listing_change", args=[listing.pk]))
    assert response.status_code == 200
