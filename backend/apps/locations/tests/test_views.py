import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.locations.models import City, District
from apps.locations.services import load_locations

pytestmark = pytest.mark.django_db


@pytest.fixture
def locations():
    load_locations(
        {
            "cities": [
                {
                    "name_en": "Dammam",
                    "name_ar": "الدمام",
                    "region": "eastern",
                    "center": [50.0888, 26.4207],
                    "sort_order": 1,
                    "districts": [
                        {"name_en": "Al Shulah", "name_ar": "الشعلة"},
                        {"name_en": "Al Nur", "name_ar": "النور"},
                    ],
                },
                {"name_en": "Khobar", "name_ar": "الخبر", "region": "eastern", "sort_order": 2},
            ]
        }
    )


def test_cities_are_public_and_ordered(locations):
    response = APIClient().get(reverse("locations-cities"))

    assert response.status_code == 200
    data = response.json()
    assert [c["slug_en"] for c in data] == ["dammam", "khobar"]
    assert data[0]["name_ar"] == "الدمام"
    assert data[0]["center"] == {"lat": 26.4207, "lng": 50.0888}
    assert data[1]["center"] is None


def test_inactive_city_is_hidden(locations):
    City.objects.filter(slug_en="khobar").update(is_active=False)
    response = APIClient().get(reverse("locations-cities"))
    assert [c["slug_en"] for c in response.json()] == ["dammam"]


def test_districts_of_a_city(locations):
    District.objects.filter(slug_en="al-nur").update(is_active=False)
    response = APIClient().get(reverse("locations-districts", args=["dammam"]))

    assert response.status_code == 200
    assert [d["slug_ar"] for d in response.json()] == ["الشعلة"]


def test_unknown_city_is_404(locations):
    response = APIClient().get(reverse("locations-districts", args=["riyadh"]))
    assert response.status_code == 404


@pytest.mark.parametrize("model", ["city", "district"])
def test_admin_pages_load(locations, client, model):
    client.force_login(UserFactory(is_staff=True, is_superuser=True))
    assert client.get(reverse(f"admin:locations_{model}_changelist")).status_code == 200
    obj = (City if model == "city" else District).objects.first()
    change_url = reverse(f"admin:locations_{model}_change", args=[obj.pk])
    assert client.get(change_url).status_code == 200
