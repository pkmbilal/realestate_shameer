from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.listings import services
from apps.listings.models import Listing
from apps.listings.serializers import SearchParamsSerializer
from apps.locations.models import City

from .factories import ListingFactory
from .test_views import make_active

pytestmark = pytest.mark.django_db

DAMMAM_BBOX = (49.9, 26.3, 50.2, 26.5)  # contains the factory point 50.0372, 26.3929


def search(**query):
    serializer = SearchParamsSerializer(data={k: str(v) for k, v in query.items()})
    serializer.is_valid(raise_exception=True)
    return list(services.search_listings(serializer.validated_data))


def refs(listings):
    return [listing.reference for listing in listings]


# --- Filters -----------------------------------------------------------------------------


def test_only_active_listings_are_found():
    active = make_active()
    ListingFactory()  # draft
    assert refs(search()) == [active.reference]


def test_filters_by_purpose_city_and_type():
    sale = make_active(purpose=Listing.Purpose.SALE)
    rent_villa = make_active(
        purpose=Listing.Purpose.RENT,
        rent_period=Listing.RentPeriod.YEARLY,
        property_type=Listing.PropertyType.VILLA,
        city=City.objects.get(slug_en="khobar"),
    )
    assert refs(search(purpose="sale")) == [sale.reference]
    assert refs(search(city="khobar")) == [rent_villa.reference]
    assert refs(search(type="villa")) == [rent_villa.reference]
    assert set(refs(search(type="villa,apartment"))) == {sale.reference, rent_villa.reference}


def test_price_range_is_in_sar():
    cheap = make_active(price_halalas=50_000_00)  # 50,000 SAR
    dear = make_active(price_halalas=2_000_000_00)  # 2,000,000 SAR
    assert refs(search(price_max=100_000)) == [cheap.reference]
    assert refs(search(price_min=1_000_000)) == [dear.reference]
    assert refs(search(price_min=50_000, price_max=50_000)) == [cheap.reference]


def test_beds_baths_and_area_minimums():
    small = make_active(bedrooms=1, bathrooms=1, area_m2=60)
    big = make_active(bedrooms=5, bathrooms=4, area_m2=400)
    assert refs(search(beds_min=3)) == [big.reference]
    assert refs(search(baths_min=2)) == [big.reference]
    assert refs(search(area_max=100)) == [small.reference]
    assert refs(search(area_min=100)) == [big.reference]


def test_completion_furnishing_and_rent_period():
    off_plan = make_active(completion=Listing.Completion.OFF_PLAN)
    furnished = make_active(furnishing=Listing.Furnishing.FURNISHED)
    monthly = make_active(purpose=Listing.Purpose.RENT, rent_period=Listing.RentPeriod.MONTHLY)
    assert refs(search(completion="off_plan")) == [off_plan.reference]
    assert refs(search(furnishing="furnished")) == [furnished.reference]
    assert refs(search(rent_period="monthly")) == [monthly.reference]


def test_bbox_keeps_only_listings_inside_the_map_area():
    inside = make_active()
    make_active(location="POINT(39.17 21.54)")  # Jeddah
    assert refs(search(bbox=",".join(map(str, DAMMAM_BBOX)))) == [inside.reference]


# --- Sorting -----------------------------------------------------------------------------


def test_sorts_by_newest_and_price():
    older = make_active(price_halalas=300_00)
    newer = make_active(price_halalas=100_00)
    Listing.objects.filter(pk=older.pk).update(refreshed_at=timezone.now() - timedelta(days=2))
    assert refs(search()) == [newer.reference, older.reference]
    assert refs(search(sort="price_asc")) == [newer.reference, older.reference]
    assert refs(search(sort="price_desc")) == [older.reference, newer.reference]


@pytest.mark.parametrize("sort", ["newest", "price_asc", "price_desc"])
def test_featured_listings_are_pinned_on_top_in_every_sort(sort):
    plain_cheap = make_active(price_halalas=100_00)
    featured = make_active(price_halalas=200_00)
    plain_dear = make_active(price_halalas=300_00)
    Listing.objects.filter(pk=featured.pk).update(featured_until=timezone.now() + timedelta(days=3))
    result = refs(search(sort=sort))
    assert result[0] == featured.reference
    assert set(result[1:]) == {plain_cheap.reference, plain_dear.reference}


def test_expired_feature_is_not_pinned():
    plain = make_active()
    was_featured = make_active()
    Listing.objects.filter(pk=was_featured.pk).update(
        featured_until=timezone.now() - timedelta(hours=1),
        refreshed_at=timezone.now() - timedelta(days=1),
    )
    assert refs(search()) == [plain.reference, was_featured.reference]


# --- Validation --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query",
    [
        {"purpose": "swap"},
        {"type": "castle"},
        {"price_min": "-1"},
        {"price_min": "500", "price_max": "100"},
        {"area_min": "200", "area_max": "100"},
        {"sort": "random"},
        {"bbox": "1,2,3"},
        {"bbox": "a,b,c,d"},
        {"bbox": "50,27,49,26"},  # min greater than max
        {"bbox": "0,0,200,10"},
    ],
)
def test_bad_search_params_are_rejected(query):
    response = APIClient().get(reverse("listing-list"), query)
    assert response.status_code == 400


def test_search_endpoint_returns_paginated_cards():
    listing = make_active()
    response = APIClient().get(reverse("listing-list"), {"purpose": "sale", "sort": "price_asc"})
    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["reference"] == listing.reference


def test_repeated_type_params_work():
    villa = make_active(property_type=Listing.PropertyType.VILLA)
    make_active(property_type=Listing.PropertyType.LAND)
    response = APIClient().get(f"{reverse('listing-list')}?type=villa&type=duplex")
    assert [r["reference"] for r in response.data["results"]] == [villa.reference]


# --- Map ---------------------------------------------------------------------------------


def test_map_requires_bbox():
    response = APIClient().get(reverse("listing-map"))
    assert response.status_code == 400
    assert "bbox" in response.data


def test_map_returns_light_pins_in_the_area():
    listing = make_active()
    response = APIClient().get(reverse("listing-map"), {"bbox": "49.9,26.3,50.2,26.5"})
    assert response.status_code == 200
    assert response.data["truncated"] is False
    pin = response.data["results"][0]
    assert pin["reference"] == listing.reference
    assert pin["latitude"] == pytest.approx(26.3929)
    assert pin["longitude"] == pytest.approx(50.0372)
    assert set(pin) == {
        "reference",
        "latitude",
        "longitude",
        "price_halalas",
        "purpose",
        "rent_period",
        "is_featured",
    }


def test_map_is_capped(monkeypatch):
    from apps.listings.views import ListingMapView

    monkeypatch.setattr(ListingMapView, "MAX_PINS", 2)
    for _ in range(3):
        make_active()
    response = APIClient().get(reverse("listing-map"), {"bbox": "49.9,26.3,50.2,26.5"})
    assert len(response.data["results"]) == 2
    assert response.data["truncated"] is True
