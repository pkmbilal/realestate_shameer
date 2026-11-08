import pytest
from django.test import Client
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory
from apps.brokers.tests.factories import BrokerProfileFactory, VerifiedUserFactory
from apps.payments import services
from apps.payments.models import Payment, TopUpPackage
from apps.wallet import services as wallet_services

pytestmark = pytest.mark.django_db


def api(user=None):
    client = APIClient()
    if user:
        client.force_authenticate(user)
    return client


@pytest.mark.parametrize(
    "user_factory, status_code",
    [
        (lambda: None, 401),
        (lambda: VerifiedUserFactory(role=User.Role.BUYER), 403),
        (lambda: UserFactory(role=User.Role.BROKER), 403),  # not Nafath-verified
    ],
)
@pytest.mark.parametrize("url_name", ["topup-packages", "topups"])
def test_needs_verified_advertiser(user_factory, status_code, url_name):
    assert api(user_factory()).get(reverse(url_name)).status_code == status_code


def test_packages_lists_active_only(broker, package):
    TopUpPackage.objects.create(
        name_ar="x", name_en="Hidden", credits=5, price_halalas=500, is_active=False
    )
    body = api(broker.user).get(reverse("topup-packages")).json()
    names = [p["name_en"] for p in body]
    assert "Test pack" in names
    assert "Hidden" not in names
    pack = next(p for p in body if p["name_en"] == "Test pack")
    assert pack == {
        "id": package.pk,
        "name_ar": "باقة",
        "name_en": "Test pack",
        "credits": 100,
        "price_halalas": 10000,
    }


def test_start_top_up(broker, package):
    response = api(broker.user).post(
        reverse("topups"), {"package_id": package.pk, "locale": "en"}, format="json"
    )
    assert response.status_code == 201
    body = response.json()
    payment = Payment.objects.get(pk=body["payment_id"])
    assert body["checkout_url"].endswith(f"/mock-checkout/{payment.gateway_ref}/")


def test_start_top_up_errors(broker, package):
    client = api(broker.user)
    assert client.post(reverse("topups"), {}, format="json").status_code == 400
    response = client.post(reverse("topups"), {"package_id": 9999}, format="json")
    assert response.status_code == 400
    assert response.json() == {"code": "package_not_found"}
    owner = VerifiedUserFactory(role=User.Role.OWNER)
    response = api(owner).post(reverse("topups"), {"package_id": package.pk}, format="json")
    assert response.json() == {"code": "no_wallet"}


def test_detail_confirms_with_gateway(broker, package, gateway, invoice_queued):
    payment, _ = services.start_top_up(broker.user, package.pk)
    url = reverse("topup-detail", args=[payment.pk])
    assert api(broker.user).get(url).json()["status"] == "pending"
    gateway.pay(payment)
    body = api(broker.user).get(url).json()
    assert body["status"] == "paid"
    assert body["credits"] == 100
    assert body["balance"] == 100
    assert body["invoice_id"] is None  # issued by the background task


def test_cannot_see_someone_elses_payment(broker, package):
    payment, _ = services.start_top_up(broker.user, package.pk)
    other = BrokerProfileFactory().user
    assert api(other).get(reverse("topup-detail", args=[payment.pk])).status_code == 404
    assert api(other).get(reverse("topups")).json()["results"] == []


def test_list_my_top_ups(broker, package):
    services.start_top_up(broker.user, package.pk)
    body = api(broker.user).get(reverse("topups")).json()
    assert len(body["results"]) == 1
    assert body["results"][0]["package_name_en"] == "Test pack"


# --- Webhook ------------------------------------------------------------------------


def test_webhook_settles_payment(broker, package, gateway, invoice_queued, settings):
    settings.MOYASAR_WEBHOOK_SECRET = "s3cret"
    payment, _ = services.start_top_up(broker.user, package.pk)
    gateway.pay(payment)
    payload = {
        "type": "payment_paid",
        "secret_token": "s3cret",
        "data": {"invoice_id": payment.gateway_ref, "status": "paid"},
    }
    response = APIClient().post(reverse("payments-webhook"), payload, format="json")
    assert response.status_code == 200
    payment.refresh_from_db()
    assert payment.status == "paid"


def test_webhook_body_alone_cannot_add_credits(broker, package, invoice_queued, settings):
    """A correct secret but an unpaid checkout: we ask the gateway and it says pending."""
    settings.MOYASAR_WEBHOOK_SECRET = "s3cret"
    payment, _ = services.start_top_up(broker.user, package.pk)
    payload = {"secret_token": "s3cret", "data": {"invoice_id": payment.gateway_ref}}
    APIClient().post(reverse("payments-webhook"), payload, format="json")
    payment.refresh_from_db()
    assert payment.status == "pending"
    assert wallet_services.wallet_for_user(broker.user).balance == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"secret_token": "wrong", "data": {"invoice_id": "x"}},
        {"data": {"invoice_id": "x"}},
        {"secret_token": "s3cret"},
    ],
)
def test_webhook_rejects_bad_payloads(payload, settings):
    settings.MOYASAR_WEBHOOK_SECRET = "s3cret"
    response = APIClient().post(reverse("payments-webhook"), payload, format="json")
    assert response.status_code == 403


# --- Mock checkout page -------------------------------------------------------------


def test_mock_checkout_pay_redirects_back(broker, package, invoice_queued):
    payment, url = services.start_top_up(broker.user, package.pk, "ar")
    path = reverse("mock-checkout", args=[payment.gateway_ref])
    page = Client().get(path)
    assert page.status_code == 200
    assert "SAR 100.00" in page.content.decode()
    response = Client().post(path, {"outcome": "pay"})
    assert response.status_code == 302
    assert f"/ar/dashboard/wallet/top-up/result?payment={payment.pk}" in response["Location"]
    assert services.confirm_payment(payment).status == "paid"


def test_mock_checkout_fail(broker, package):
    payment, _ = services.start_top_up(broker.user, package.pk)
    Client().post(reverse("mock-checkout", args=[payment.gateway_ref]), {"outcome": "fail"})
    assert services.confirm_payment(payment).status == "failed"


def test_mock_checkout_unknown_or_live(settings):
    assert Client().get(reverse("mock-checkout", args=["nope"])).status_code == 404
    assert Client().post(reverse("mock-checkout", args=["nope"])).status_code == 404
    settings.INTEGRATIONS_MODE = "live"
    assert Client().get(reverse("mock-checkout", args=["nope"])).status_code == 404
