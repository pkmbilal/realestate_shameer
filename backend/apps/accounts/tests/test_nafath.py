import logging

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts import services
from apps.accounts.models import NafathVerification, User
from apps.accounts.permissions import IsNafathVerified, IsVerifiedAdvertiser
from apps.accounts.tests.factories import UserFactory
from integrations.nafath import NafathRequest, NafathStatus

pytestmark = pytest.mark.django_db

NATIONAL_ID = "1012345678"


@pytest.fixture
def nafath(monkeypatch):
    """A fake Nafath whose answer the test controls."""

    class FakeNafath:
        answer = NafathStatus.PENDING
        started = []

        def start(self, national_id):
            self.started.append(national_id)
            return NafathRequest(transaction_ref=f"ref-{len(self.started)}", random_number="42")

        def status(self, ref):
            return self.answer

    fake = FakeNafath()
    fake.started = []
    monkeypatch.setattr(services, "get_nafath_client", lambda: fake)
    return fake


def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


# --- services ---


def test_start_creates_pending_record_without_the_id(nafath):
    user = UserFactory()

    verification, number = services.start_nafath_verification(user, NATIONAL_ID)

    assert number == "42"
    assert verification.status == NafathVerification.Status.PENDING
    assert nafath.started == [NATIONAL_ID]
    row = NafathVerification.objects.values().get(pk=verification.pk)
    assert NATIONAL_ID not in str(row)


@pytest.mark.parametrize("bad", ["", "123", "3012345678", "10123456789", "10123x5678"])
def test_start_rejects_bad_national_id(nafath, bad):
    with pytest.raises(services.NafathError) as exc:
        services.start_nafath_verification(UserFactory(), bad)
    assert exc.value.code == "invalid_national_id"
    assert nafath.started == []


def test_new_request_expires_the_old_pending_one(nafath):
    user = UserFactory()
    first, _ = services.start_nafath_verification(user, NATIONAL_ID)
    services.start_nafath_verification(user, NATIONAL_ID)

    first.refresh_from_db()
    assert first.status == NafathVerification.Status.EXPIRED


def test_check_approves_and_user_becomes_verified(nafath):
    user = UserFactory()
    verification, _ = services.start_nafath_verification(user, NATIONAL_ID)
    assert (
        services.check_nafath_verification(user, verification.transaction_ref).status == "pending"
    )

    nafath.answer = NafathStatus.APPROVED
    verification = services.check_nafath_verification(user, verification.transaction_ref)

    assert verification.status == NafathVerification.Status.APPROVED
    assert verification.verified_at is not None
    assert user.is_nafath_verified


def test_check_is_final_once_decided(nafath):
    user = UserFactory()
    verification, _ = services.start_nafath_verification(user, NATIONAL_ID)
    nafath.answer = NafathStatus.REJECTED
    services.check_nafath_verification(user, verification.transaction_ref)

    nafath.answer = NafathStatus.APPROVED
    verification = services.check_nafath_verification(user, verification.transaction_ref)

    assert verification.status == NafathVerification.Status.REJECTED
    assert not user.is_nafath_verified


def test_check_other_users_request_is_not_found(nafath):
    verification, _ = services.start_nafath_verification(UserFactory(), NATIONAL_ID)
    with pytest.raises(services.NafathError) as exc:
        services.check_nafath_verification(UserFactory(), verification.transaction_ref)
    assert exc.value.code == "not_found"


def test_already_verified_cannot_start_again(nafath):
    user = UserFactory()
    NafathVerification.objects.create(
        user=user, transaction_ref="done", status=NafathVerification.Status.APPROVED
    )
    with pytest.raises(services.NafathError) as exc:
        services.start_nafath_verification(user, NATIONAL_ID)
    assert exc.value.code == "already_verified"


def test_mock_flow_never_logs_the_id(caplog):
    user = UserFactory()
    with caplog.at_level(logging.DEBUG):
        verification, _ = services.start_nafath_verification(user, NATIONAL_ID)
        services.check_nafath_verification(user, verification.transaction_ref)
    assert NATIONAL_ID not in caplog.text
    assert user.is_nafath_verified


# --- permissions ---


class _Request:
    def __init__(self, user):
        self.user = user


@pytest.mark.parametrize(
    ("role", "verified", "nafath_ok", "advertiser_ok"),
    [
        (User.Role.BUYER, False, False, False),
        (User.Role.BUYER, True, True, False),
        (User.Role.BROKER, False, False, False),
        (User.Role.BROKER, True, True, True),
        (User.Role.OWNER, True, True, True),
        (User.Role.AGENCY_ADMIN, True, True, True),
    ],
)
def test_permissions(role, verified, nafath_ok, advertiser_ok):
    user = UserFactory(role=role)
    if verified:
        NafathVerification.objects.create(
            user=user, transaction_ref=f"r-{user.pk}", status="approved"
        )
    request = _Request(user)
    assert IsNafathVerified().has_permission(request, None) is nafath_ok
    assert IsVerifiedAdvertiser().has_permission(request, None) is advertiser_ok


# --- views ---


def test_start_and_poll_endpoints(nafath):
    user = UserFactory()
    client = api(user)

    response = client.post(reverse("nafath-start"), {"national_id": NATIONAL_ID}, format="json")
    assert response.status_code == 201
    body = response.json()
    assert body == {"transaction_ref": "ref-1", "random_number": "42", "status": "pending"}
    assert NATIONAL_ID not in response.content.decode()

    nafath.answer = NafathStatus.APPROVED
    response = client.post(
        reverse("nafath-status"), {"transaction_ref": body["transaction_ref"]}, format="json"
    )
    assert response.json() == {"status": "approved"}
    assert client.get(reverse("accounts-me")).json()["is_nafath_verified"] is True


def test_start_endpoint_bad_id(nafath):
    response = api(UserFactory()).post(
        reverse("nafath-start"), {"national_id": "999"}, format="json"
    )
    assert response.status_code == 400
    assert response.json() == {"code": "invalid_national_id"}


def test_status_endpoint_unknown_ref(nafath):
    response = api(UserFactory()).post(
        reverse("nafath-status"), {"transaction_ref": "nope"}, format="json"
    )
    assert response.status_code == 404


def test_endpoints_need_login():
    client = APIClient()
    assert client.post(reverse("nafath-start"), {}, format="json").status_code == 401
    assert client.post(reverse("nafath-status"), {}, format="json").status_code == 401
