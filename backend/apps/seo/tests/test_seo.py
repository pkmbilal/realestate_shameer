import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.listings.models import Listing
from apps.listings.tests.factories import ListingFactory
from apps.listings.tests.test_views import make_active
from apps.locations.models import City
from apps.seo import services

pytestmark = pytest.mark.django_db


def dammam():
    return City.objects.get(slug_en="dammam")


def a_district(city):
    return city.districts.order_by("id").first()


def find(rows, *, purpose="sale", type="apartment", city=None, district=None):
    for row in rows:
        if (
            row["purpose"] == purpose
            and row["type"] == type
            and (row["city"] or {}).get("slug_en") == city
            and (row["district"] or {}).get("slug_en") == district
        ):
            return row
    return None


# --- area_counts -----------------------------------------------------------------------------


def test_counts_only_active_listings_and_rolls_up():
    district = a_district(dammam())
    make_active(district=district)
    make_active(district=district)
    make_active()  # Dammam, no district
    ListingFactory(district=district)  # draft: not counted

    rows = services.area_counts()
    assert find(rows)["count"] == 3
    assert find(rows, city="dammam")["count"] == 3
    row = find(rows, city="dammam", district=district.slug_en)
    assert row["count"] == 2
    assert row["district"]["slug_ar"] == district.slug_ar
    assert row["city"]["name_ar"] == dammam().name_ar


def test_counts_are_split_by_purpose_and_type():
    make_active()
    make_active(property_type=Listing.PropertyType.VILLA)
    rows = services.area_counts()
    assert find(rows)["count"] == 1
    assert find(rows, type="villa")["count"] == 1
    assert find(rows, purpose="rent") is None


def test_inactive_city_is_left_out():
    make_active()
    City.objects.filter(slug_en="dammam").update(is_active=False)
    assert services.area_counts() == []


def test_inactive_district_still_counts_for_city():
    district = a_district(dammam())
    make_active(district=district)
    district.is_active = False
    district.save()
    rows = services.area_counts()
    assert find(rows, city="dammam")["count"] == 1
    assert find(rows, city="dammam", district=district.slug_en) is None


# --- sitemap_listings ------------------------------------------------------------------------


def test_sitemap_lists_active_listings_in_chunks(monkeypatch):
    monkeypatch.setattr(services, "SITEMAP_CHUNK", 2)
    active = [make_active() for _ in range(3)]
    ListingFactory()  # draft
    first = services.sitemap_listings(1)
    second = services.sitemap_listings(2)
    assert first["count"] == 3
    assert [r["reference"] for r in first["results"] + second["results"]] == [
        listing.reference for listing in active
    ]
    assert services.sitemap_listings(3)["results"] == []
    assert services.sitemap_listings(0)["results"] == []


def test_sitemap_with_no_listings_is_empty():
    assert services.sitemap_listings(1) == {
        "count": 0,
        "chunk_size": services.SITEMAP_CHUNK,
        "results": [],
    }


# --- Endpoints -------------------------------------------------------------------------------


def test_area_endpoint_is_public_and_read_only():
    make_active()
    client = APIClient()
    response = client.get(reverse("seo-areas"))
    assert response.status_code == 200
    assert find(response.json(), city="dammam")["count"] == 1
    assert client.post(reverse("seo-areas")).status_code == 405


def test_sitemap_endpoint_is_public_and_read_only():
    listing = make_active()
    client = APIClient()
    response = client.get(reverse("seo-sitemap-listings"), {"page": "abc"})
    assert response.status_code == 200
    assert response.json()["results"][0]["reference"] == listing.reference
    assert client.post(reverse("seo-sitemap-listings")).status_code == 405
