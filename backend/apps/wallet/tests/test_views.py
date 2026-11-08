import pytest
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory
from apps.brokers.tests.factories import BrokerProfileFactory, VerifiedUserFactory
from apps.listings import services as listings
from apps.wallet import services
from apps.wallet.models import CreditTransaction, Wallet

pytestmark = pytest.mark.django_db
Action = CreditTransaction.Action


def api(user=None):
    client = APIClient()
    if user:
        client.force_authenticate(user)
    return client


# --- Wallet API -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "user_factory, status_code",
    [
        (lambda: None, 401),
        (lambda: VerifiedUserFactory(role=User.Role.BUYER), 403),
        (lambda: UserFactory(role=User.Role.BROKER), 403),  # not Nafath-verified
    ],
)
@pytest.mark.parametrize("url_name", ["wallet", "wallet-transactions"])
def test_wallet_needs_verified_advertiser(user_factory, status_code, url_name):
    assert api(user_factory()).get(reverse(url_name)).status_code == status_code


def test_wallet_shows_balance_and_prices(funded_wallet, broker, set_price):
    set_price(Action.FEATURE, 40, days=7)
    body = api(broker.user).get(reverse("wallet")).json()
    assert body["has_wallet"] is True
    assert body["balance"] == 100
    assert {"action": "feature", "credits": 40, "days": 7} in body["prices"]


def test_owner_has_no_wallet():
    body = api(VerifiedUserFactory(role=User.Role.OWNER)).get(reverse("wallet")).json()
    assert body["has_wallet"] is False
    assert body["balance"] == 0
    assert not Wallet.objects.exists()


def test_transactions_are_mine_only_newest_first(funded_wallet, broker, staff, set_price):
    set_price(Action.REFRESH, 5)
    services.charge(funded_wallet, Action.REFRESH)
    other = services.wallet_for_user(BrokerProfileFactory().user)
    services.grant(other, 7, staff, "someone else")

    body = api(broker.user).get(reverse("wallet-transactions")).json()
    assert body["count"] == 2
    assert [r["amount"] for r in body["results"]] == [-5, 100]
    assert body["results"][0]["kind"] == "spend"


# --- Listing actions through the API ------------------------------------------------------


def test_submit_without_credits_returns_402(broker, broker_listing, set_price):
    set_price(Action.POST, 10)
    url = reverse("my-listing-submit", args=[broker_listing.reference])
    response = api(broker.user).post(url)
    assert response.status_code == 402
    assert response.json() == {"code": "insufficient_credits"}


def test_refresh_and_feature_endpoints(funded_wallet, broker, broker_listing, staff, set_price):
    listings.submit_for_review(broker_listing, broker.user)
    listings.approve(broker_listing, staff)
    set_price(Action.REFRESH, 5)
    set_price(Action.FEATURE, 20, days=7)
    client = api(broker.user)

    response = client.post(reverse("my-listing-refresh", args=[broker_listing.reference]))
    assert response.status_code == 200
    assert response.json()["refreshed_at"]

    response = client.post(reverse("my-listing-feature", args=[broker_listing.reference]))
    assert response.status_code == 200
    assert response.json()["featured_until"]

    funded_wallet.refresh_from_db()
    assert funded_wallet.balance == 75


def test_cannot_refresh_someone_elses_listing(broker_listing, staff):
    listings.submit_for_review(broker_listing, broker_listing.created_by)
    listings.approve(broker_listing, staff)
    stranger = BrokerProfileFactory().user
    url = reverse("my-listing-refresh", args=[broker_listing.reference])
    assert api(stranger).post(url).status_code == 404


def test_refresh_draft_returns_400(broker, broker_listing):
    url = reverse("my-listing-refresh", args=[broker_listing.reference])
    response = api(broker.user).post(url)
    assert response.status_code == 400
    assert response.json() == {"code": "not_active"}


# --- Admin -----------------------------------------------------------------------------


@pytest.fixture
def admin_client(client):
    admin = User.objects.create_superuser(phone="+966511111111", password="x")
    client.force_login(admin)
    return client


def test_admin_grant_action_adds_a_ledger_row(admin_client, broker):
    wallet = services.wallet_for_user(broker.user)
    url = reverse("admin:wallet_wallet_changelist")
    page = admin_client.post(url, {"action": "grant_credits", ACTION_CHECKBOX_NAME: [wallet.pk]})
    assert page.status_code == 200  # the amount form
    admin_client.post(
        url,
        {
            "action": "grant_credits",
            ACTION_CHECKBOX_NAME: [wallet.pk],
            "apply": "1",
            "credits": "50",
            "note": "Launch promotion",
        },
    )
    wallet.refresh_from_db()
    assert wallet.balance == 50
    assert wallet.transactions.get().kind == CreditTransaction.Kind.GRANT


def test_admin_adjust_cannot_overdraw(admin_client, funded_wallet):
    admin_client.post(
        reverse("admin:wallet_wallet_changelist"),
        {
            "action": "adjust_balance",
            ACTION_CHECKBOX_NAME: [funded_wallet.pk],
            "apply": "1",
            "amount": "-500",
            "note": "oops",
        },
    )
    funded_wallet.refresh_from_db()
    assert funded_wallet.balance == 100


def test_admin_pages_load(admin_client, funded_wallet):
    for url in (
        reverse("admin:wallet_wallet_changelist"),
        reverse("admin:wallet_wallet_change", args=[funded_wallet.pk]),
        reverse("admin:wallet_wallet_add"),
        reverse("admin:wallet_credittransaction_changelist"),
        reverse("admin:wallet_creditprice_changelist"),
    ):
        assert admin_client.get(url).status_code == 200, url


def test_admin_ledger_is_read_only(admin_client, funded_wallet):
    entry = funded_wallet.transactions.get()
    url = reverse("admin:wallet_credittransaction_delete", args=[entry.pk])
    assert admin_client.post(url, {"post": "yes"}).status_code == 403
    assert CreditTransaction.objects.filter(pk=entry.pk).exists()
