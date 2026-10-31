import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.brokers.tests.factories import AgencyFactory, BrokerProfileFactory, VerifiedUserFactory
from apps.locations.models import City

pytestmark = pytest.mark.django_db


def api(user=None):
    client = APIClient()
    if user:
        client.force_authenticate(user)
    return client


@pytest.fixture
def city():
    return City.objects.create(
        name_ar="الخبر", name_en="Khobar", slug_en="khobar", slug_ar="الخبر", region="eastern"
    )


def profile_payload(city, **overrides):
    return {
        "name_ar": "سارة",
        "name_en": "Sara",
        "photo_url": "",
        "fal_licence": "1100555000",
        "whatsapp": "0512345678",
        "city_ids": [city.pk],
        **overrides,
    }


def test_unverified_user_cannot_create_profile(city):
    response = api(UserFactory()).put(reverse("broker-me"), profile_payload(city), format="json")
    assert response.status_code == 403
    assert response.json()["detail"] == "nafath_required"


def test_create_then_update_profile(city):
    client = api(VerifiedUserFactory())
    assert client.get(reverse("broker-me")).status_code == 404

    response = client.put(reverse("broker-me"), profile_payload(city), format="json")
    assert response.status_code == 201
    body = response.json()
    assert body["whatsapp"] == "+966512345678"
    assert body["city_ids"] == [city.pk]
    assert body["agency"] is None

    response = client.put(
        reverse("broker-me"), profile_payload(city, name_en="Sara A."), format="json"
    )
    assert response.status_code == 200
    assert client.get(reverse("broker-me")).json()["name_en"] == "Sara A."
    assert client.get(reverse("accounts-me")).json()["role"] == "broker"


@pytest.mark.parametrize(
    ("field", "value"),
    [("whatsapp", "abc"), ("fal_licence", "FAL-1"), ("city_ids", [9999]), ("name_ar", "")],
)
def test_profile_validation(city, field, value):
    response = api(VerifiedUserFactory()).put(
        reverse("broker-me"), profile_payload(city, **{field: value}), format="json"
    )
    assert response.status_code == 400
    assert field in response.json()


def test_fal_licence_must_be_unique(city):
    BrokerProfileFactory(fal_licence="1100555000")
    response = api(VerifiedUserFactory()).put(
        reverse("broker-me"), profile_payload(city), format="json"
    )
    assert response.status_code == 400
    assert "fal_licence" in response.json()


def test_public_profile_hides_contact_details(city):
    profile = BrokerProfileFactory()
    profile.cities_served.add(city)

    response = api().get(reverse("broker-detail", args=[profile.pk]))

    assert response.status_code == 200
    body = response.json()
    assert body["cities_served"][0]["slug_en"] == "khobar"
    assert "whatsapp" not in body
    assert profile.whatsapp not in response.content.decode()


def test_agency_create_and_members():
    admin = VerifiedUserFactory()
    client = api(admin)
    assert client.get(reverse("agency-me")).status_code == 404

    response = client.put(
        reverse("agency-me"),
        {
            "name_ar": "مكتب الخليج",
            "name_en": "Gulf Office",
            "logo_url": "",
            "cr_number": "2050111222",
            "fal_licence": "1200111222",
        },
        format="json",
    )
    assert response.status_code == 201
    assert client.get(reverse("accounts-me")).json()["role"] == "agency_admin"

    broker = BrokerProfileFactory(user__phone="+966511111222")
    response = client.post(reverse("agency-members"), {"phone": "0511111222"}, format="json")
    assert response.status_code == 201
    assert response.json()["masked_whatsapp"].count("•") > 0

    members = client.get(reverse("agency-members")).json()
    assert [m["id"] for m in members] == [broker.pk]

    broker.refresh_from_db()
    public = api().get(reverse("agency-detail", args=[broker.agency_id]))
    assert public.status_code == 200
    assert public.json()["members"][0]["id"] == broker.pk
    assert "cr_number" not in public.json()

    assert client.delete(reverse("agency-member-detail", args=[broker.pk])).status_code == 204
    assert client.get(reverse("agency-members")).json() == []


def test_add_member_errors():
    agency = AgencyFactory()
    response = api(agency.admin).post(
        reverse("agency-members"), {"phone": "+966599999999"}, format="json"
    )
    assert response.status_code == 400
    assert response.json() == {"code": "broker_not_found"}


def test_members_need_an_agency():
    client = api(VerifiedUserFactory())
    assert client.get(reverse("agency-members")).status_code == 404
    assert client.delete(reverse("agency-member-detail", args=[1])).status_code == 404


def test_cannot_remove_member_of_other_agency():
    other = BrokerProfileFactory(agency=AgencyFactory())
    response = api(AgencyFactory().admin).delete(reverse("agency-member-detail", args=[other.pk]))
    assert response.status_code == 404
