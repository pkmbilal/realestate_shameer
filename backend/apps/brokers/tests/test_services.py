import pytest

from apps.accounts.models import User
from apps.brokers import services
from apps.brokers.models import Agency, BrokerProfile
from apps.brokers.tests.factories import AgencyFactory, BrokerProfileFactory, VerifiedUserFactory
from apps.locations.models import City

pytestmark = pytest.mark.django_db

PROFILE = {
    "name_ar": "أحمد",
    "name_en": "Ahmed",
    "photo_url": "",
    "fal_licence": "1100123456",
    "whatsapp": "+966512345678",
}


@pytest.fixture
def city():
    return City.objects.create(
        name_ar="الدمام", name_en="Dammam", slug_en="dammam", slug_ar="الدمام", region="eastern"
    )


def test_first_profile_makes_buyer_a_broker(city):
    user = VerifiedUserFactory()

    profile = services.save_broker_profile(user, cities_served=[city], **PROFILE)

    user.refresh_from_db()
    assert user.role == User.Role.BROKER
    assert list(profile.cities_served.all()) == [city]


def test_saving_again_updates_the_same_profile(city):
    user = VerifiedUserFactory()
    services.save_broker_profile(user, cities_served=[city], **PROFILE)

    profile = services.save_broker_profile(user, cities_served=[], **{**PROFILE, "name_en": "A."})

    assert BrokerProfile.objects.count() == 1
    assert profile.name_en == "A."
    assert profile.cities_served.count() == 0


def test_broker_cannot_set_own_agency():
    agency = AgencyFactory()
    profile = services.save_broker_profile(VerifiedUserFactory(), agency=agency, **PROFILE)
    assert profile.agency is None


def test_staff_role_is_kept():
    user = VerifiedUserFactory(role=User.Role.STAFF)
    services.save_broker_profile(user, **PROFILE)
    user.refresh_from_db()
    assert user.role == User.Role.STAFF


def test_agency_creation_makes_broker_an_admin():
    user = VerifiedUserFactory(role=User.Role.BROKER)

    agency = services.save_agency(
        user,
        name_ar="مكتب",
        name_en="Office",
        logo_url="",
        cr_number="2050123456",
        fal_licence="1200123456",
    )

    user.refresh_from_db()
    assert user.role == User.Role.AGENCY_ADMIN
    assert agency.admin == user
    assert Agency.objects.count() == 1


def test_add_and_remove_member():
    agency = AgencyFactory()
    profile = BrokerProfileFactory()

    services.add_agency_member(agency, profile.user.phone)
    assert list(agency.members.all()) == [profile]

    services.remove_agency_member(agency, profile.pk)
    profile.refresh_from_db()
    assert profile.agency is None


def test_add_member_accepts_local_phone_format():
    agency = AgencyFactory()
    profile = BrokerProfileFactory(user__phone="+966512345678")
    assert services.add_agency_member(agency, "0512345678") == profile


@pytest.mark.parametrize(
    ("phone", "code"),
    [("abc", "invalid_phone"), ("+966599999999", "broker_not_found")],
)
def test_add_member_errors(phone, code):
    with pytest.raises(services.BrokerError) as exc:
        services.add_agency_member(AgencyFactory(), phone)
    assert exc.value.code == code


def test_cannot_take_broker_from_another_agency():
    profile = BrokerProfileFactory(agency=AgencyFactory())
    with pytest.raises(services.BrokerError) as exc:
        services.add_agency_member(AgencyFactory(), profile.user.phone)
    assert exc.value.code == "broker_in_other_agency"


def test_cannot_remove_another_agencys_member():
    profile = BrokerProfileFactory(agency=AgencyFactory())
    with pytest.raises(services.BrokerError):
        services.remove_agency_member(AgencyFactory(), profile.pk)
