from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory
from apps.brokers.tests.factories import AgencyFactory, BrokerProfileFactory, VerifiedUserFactory
from apps.listings import services
from apps.listings.models import Amenity, Listing
from apps.listings.seed import seed_amenities

from .factories import ListingFactory, ListingPhotoFactory

pytestmark = pytest.mark.django_db


def api(user=None):
    client = APIClient()
    if user:
        client.force_authenticate(user)
    return client


def owner():
    return VerifiedUserFactory(role=User.Role.OWNER)


def make_active(**kwargs):
    listing = ListingFactory(**kwargs)
    ListingPhotoFactory(listing=listing)
    services.submit_for_review(listing, listing.created_by)
    return services.approve(listing, UserFactory(role=User.Role.STAFF, is_staff=True))


# --- Advertiser endpoints ---------------------------------------------------------------


@pytest.mark.parametrize(
    "user_factory, status_code",
    [
        (lambda: None, 401),
        (lambda: UserFactory(role=User.Role.OWNER), 403),
        (lambda: VerifiedUserFactory(role=User.Role.BUYER), 403),
    ],
)
def test_my_listings_need_verified_advertiser(user_factory, status_code):
    response = api(user_factory()).get(reverse("my-listings"))
    assert response.status_code == status_code


def test_start_edit_and_submit_through_api(s3):
    seed_amenities()
    user = owner()
    client = api(user)

    response = client.post(reverse("my-listings"), {"licence_number": "7400000001"}, format="json")
    assert response.status_code == 201
    body = response.json()
    ref = body["reference"]
    assert body["status"] == "draft"
    assert body["licence_number"] == "7400000001"
    assert {"price_halalas", "title", "photos"} <= set(body["missing_fields"])
    assert body["city"]["name_en"] in ("Dammam", "Khobar", "Dhahran", "Jubail")
    original_area = body["area_m2"]

    amenity = Amenity.objects.first()
    response = client.patch(
        reverse("my-listing", args=[ref]),
        {
            "price_halalas": 120_000_000,
            "title_en": "Nice place",
            "amenity_ids": [amenity.pk],
            # REGA fields are read-only: these must be ignored.
            "area_m2": 1,
            "licence_number": "999",
            "status": "active",
        },
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["price_halalas"] == 120_000_000
    assert body["amenity_ids"] == [amenity.pk]
    assert body["area_m2"] == original_area
    assert body["licence_number"] == "7400000001"
    assert body["status"] == "draft"
    assert "price_halalas" not in body["missing_fields"]
    assert "title" not in body["missing_fields"]

    response = client.post(reverse("my-listing-submit", args=[ref]))
    assert response.status_code == 400
    assert response.json()["code"] == "incomplete"
    assert "photos" in response.json()["fields"]

    presign = client.post(
        reverse("my-listing-photo-presign", args=[ref]),
        {"content_type": "image/webp", "size_bytes": 5000},
        format="json",
    )
    assert presign.status_code == 200
    key = presign.json()["key"]
    response = client.post(reverse("my-listing-photos", args=[ref]), {"key": key}, format="json")
    assert response.status_code == 201
    assert "card_url" in response.json()

    if Listing.objects.get(reference=ref).purpose == "rent":
        client.patch(reverse("my-listing", args=[ref]), {"rent_period": "yearly"}, format="json")
    response = client.post(reverse("my-listing-submit", args=[ref]))
    assert response.status_code == 200
    assert response.json()["status"] == "pending_review"


def test_start_with_unknown_licence_returns_code():
    response = api(owner()).post(
        reverse("my-listings"), {"licence_number": "7400010000"}, format="json"
    )
    assert response.status_code == 400
    assert response.json() == {"code": "not_found"}


def test_cannot_touch_someone_elses_listing():
    listing = ListingFactory()
    client = api(owner())
    assert client.get(reverse("my-listing", args=[listing.reference])).status_code == 404
    response = client.post(reverse("my-listing-archive", args=[listing.reference]))
    assert response.status_code == 404


def test_agency_admin_sees_agency_listings():
    agency = AgencyFactory()
    profile = BrokerProfileFactory(agency=agency)
    listing = ListingFactory(created_by=profile.user, broker=profile, agency=agency)
    response = api(agency.admin).get(reverse("my-listings"))
    assert [x["reference"] for x in response.json()] == [listing.reference]


def test_rent_period_rejected_for_sale_listing():
    listing = ListingFactory()
    response = api(listing.created_by).patch(
        reverse("my-listing", args=[listing.reference]), {"rent_period": "monthly"}, format="json"
    )
    assert response.status_code == 400


def test_archive_and_reorder_and_delete_photo(s3):
    listing = ListingFactory()
    a = ListingPhotoFactory(listing=listing, position=0)
    b = ListingPhotoFactory(listing=listing, position=1)
    client = api(listing.created_by)

    response = client.put(
        reverse("my-listing-photos", args=[listing.reference]),
        {"photo_ids": [b.pk, a.pk]},
        format="json",
    )
    assert [p["id"] for p in response.json()["photos"]] == [b.pk, a.pk]

    response = client.delete(reverse("my-listing-photo", args=[listing.reference, a.pk]))
    assert response.status_code == 204

    response = client.post(reverse("my-listing-archive", args=[listing.reference]))
    assert response.json()["status"] == "archived"


# --- Public endpoints -----------------------------------------------------------------------


def test_public_list_shows_only_active_listings_featured_first():
    older = make_active()
    newer = make_active()
    featured = make_active()
    Listing.objects.filter(pk=featured.pk).update(
        featured_until=timezone.now() + timedelta(days=3),
        refreshed_at=timezone.now() - timedelta(days=10),
    )
    ListingFactory()  # draft: hidden
    ListingFactory(status=Listing.Status.TAKEN_DOWN)  # hidden

    response = api().get(reverse("listing-list"))
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3
    refs = [x["reference"] for x in body["results"]]
    assert refs == [featured.reference, newer.reference, older.reference]
    assert body["results"][0]["is_featured"] is True
    assert body["results"][0]["cover"]["card_url"].startswith("http://localhost:8081/")


def test_public_list_filters():
    make_active(purpose="rent", rent_period="yearly")
    sale = make_active()
    response = api().get(reverse("listing-list"), {"purpose": "sale", "city": "dammam"})
    assert [x["reference"] for x in response.json()["results"]] == [sale.reference]
    assert api().get(reverse("listing-list"), {"city": "jubail"}).json()["count"] == 0


def test_public_detail_has_licence_badge_and_counts_views():
    listing = make_active()
    url = reverse("listing-detail", args=[listing.reference])
    body = api().get(url).json()
    assert body["licence_number"] == listing.licence_number
    assert body["licence_expires_on"] == listing.licence_expires_on.isoformat()
    assert body["advertiser"]["type"] == "owner"
    assert body["view_count"] == 1
    # No personal data on the public page.
    assert "created_by" not in body
    assert listing.created_by.phone not in str(body)
    assert api().get(url).json()["view_count"] == 2


def test_public_detail_hides_drafts():
    listing = ListingFactory()
    assert api().get(reverse("listing-detail", args=[listing.reference])).status_code == 404


def test_amenities_are_public():
    seed_amenities()
    body = api().get(reverse("amenity-list")).json()
    assert {"slug": "parking", "name_en": "Parking"}.items() <= body[0].items()
