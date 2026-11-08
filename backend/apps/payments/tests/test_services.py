from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.brokers.tests.factories import AgencyFactory, VerifiedUserFactory
from apps.payments import services
from apps.payments.models import Payment
from apps.wallet import services as wallet_services
from apps.wallet.models import CreditTransaction
from integrations.payments import GatewayResult, GatewayStatus
from integrations.payments.mock import MockPaymentsClient

pytestmark = pytest.mark.django_db
Status = Payment.Status


# --- start_top_up -------------------------------------------------------------------


def test_start_creates_pending_payment_and_checkout(broker, package):
    payment, url = services.start_top_up(broker.user, package.pk, "en")
    assert payment.status == Status.PENDING
    assert payment.credits == 100
    assert payment.amount_halalas == 10000
    assert payment.wallet == wallet_services.wallet_for_user(broker.user)
    assert payment.gateway_ref.startswith("mock_")
    assert url.endswith(f"/api/payments/mock-checkout/{payment.gateway_ref}/")
    state = MockPaymentsClient.get_state(payment.gateway_ref)
    assert state["amount"] == 10000
    assert state["return_url"].endswith(f"/en/dashboard/wallet/top-up/result?payment={payment.pk}")


def test_start_copies_package_price(broker, package):
    payment, _ = services.start_top_up(broker.user, package.pk)
    package.price_halalas = 99900
    package.save()
    payment.refresh_from_db()
    assert payment.amount_halalas == 10000


def test_agency_admin_tops_up_agency_wallet(package):
    agency = AgencyFactory()
    payment, _ = services.start_top_up(agency.admin, package.pk)
    assert payment.wallet.agency == agency


@pytest.mark.parametrize("role", [User.Role.OWNER, User.Role.BUYER])
def test_users_without_wallet_cannot_top_up(role, package):
    with pytest.raises(services.PaymentError) as err:
        services.start_top_up(VerifiedUserFactory(role=role), package.pk)
    assert err.value.code == "no_wallet"


def test_inactive_or_missing_package_rejected(broker, package):
    package.is_active = False
    package.save()
    for package_id in (package.pk, 99999):
        with pytest.raises(services.PaymentError) as err:
            services.start_top_up(broker.user, package_id)
        assert err.value.code == "package_not_found"
    assert not Payment.objects.exists()


def test_gateway_down_marks_payment_failed(broker, package):
    with patch.object(MockPaymentsClient, "create_checkout", side_effect=OSError("down")):
        with pytest.raises(services.PaymentError) as err:
            services.start_top_up(broker.user, package.pk)
    assert err.value.code == "gateway_unavailable"
    assert Payment.objects.get().status == Status.FAILED


# --- confirm_payment ----------------------------------------------------------------


def test_paid_adds_credits_once_and_queues_invoice(
    broker, package, gateway, invoice_queued, django_capture_on_commit_callbacks
):
    payment, _ = services.start_top_up(broker.user, package.pk)
    gateway.pay(payment)
    with django_capture_on_commit_callbacks(execute=True):
        payment = services.confirm_payment(payment)
    assert payment.status == Status.PAID
    assert payment.paid_at is not None
    entry = payment.credit_transaction
    assert entry.kind == CreditTransaction.Kind.TOPUP
    assert entry.amount == 100
    wallet = wallet_services.wallet_for_user(broker.user)
    assert wallet.balance == 100
    assert wallet_services.balance_matches_ledger(wallet)
    invoice_queued.assert_called_once_with(payment.pk)


def test_confirm_twice_credits_once(broker, package, gateway, invoice_queued):
    payment, _ = services.start_top_up(broker.user, package.pk)
    gateway.pay(payment)
    services.confirm_payment(payment)
    stale = Payment.objects.get(pk=payment.pk)
    stale.status = Status.PENDING  # a second caller holding an old copy
    services.confirm_payment(stale)
    services.confirm_by_ref(payment.gateway_ref)
    wallet = wallet_services.wallet_for_user(broker.user)
    assert wallet.balance == 100
    assert wallet.transactions.filter(kind=CreditTransaction.Kind.TOPUP).count() == 1


def test_still_pending_changes_nothing(broker, package, invoice_queued):
    payment, _ = services.start_top_up(broker.user, package.pk)
    payment = services.confirm_payment(payment)
    assert payment.status == Status.PENDING
    assert not CreditTransaction.objects.exists()


def test_failed_adds_nothing(broker, package, gateway, invoice_queued):
    payment, _ = services.start_top_up(broker.user, package.pk)
    gateway.fail(payment)
    payment = services.confirm_payment(payment)
    assert payment.status == Status.FAILED
    assert not CreditTransaction.objects.exists()
    invoice_queued.assert_not_called()


@pytest.mark.parametrize(
    "result",
    [
        GatewayResult(status=GatewayStatus.PAID, amount_halalas=100, currency="SAR"),
        GatewayResult(status=GatewayStatus.PAID, amount_halalas=10000, currency="USD"),
    ],
)
def test_amount_mismatch_never_credits(broker, package, invoice_queued, result, caplog):
    payment, _ = services.start_top_up(broker.user, package.pk)
    with patch.object(MockPaymentsClient, "fetch", return_value=result):
        payment = services.confirm_payment(payment)
    assert payment.status == Status.PENDING
    assert not CreditTransaction.objects.exists()
    assert "amount mismatch" in caplog.text


def test_gateway_unreachable_leaves_pending(broker, package, invoice_queued):
    payment, _ = services.start_top_up(broker.user, package.pk)
    with patch.object(MockPaymentsClient, "fetch", side_effect=OSError("timeout")):
        payment = services.confirm_payment(payment)
    assert payment.status == Status.PENDING


def test_late_payment_after_expiry_still_credited(broker, package, gateway, invoice_queued):
    payment, _ = services.start_top_up(broker.user, package.pk)
    Payment.objects.filter(pk=payment.pk).update(status=Status.EXPIRED)
    gateway.pay(payment)
    payment = services.confirm_by_ref(payment.gateway_ref)
    assert payment.status == Status.PAID
    assert wallet_services.wallet_for_user(broker.user).balance == 100


def test_unknown_ref_is_ignored():
    assert services.confirm_by_ref("nope") is None


# --- expire_stale_payments ----------------------------------------------------------


def _age(payment, minutes):
    Payment.objects.filter(pk=payment.pk).update(
        created_at=timezone.now() - timedelta(minutes=minutes)
    )


def test_expire_stale_payments(broker, package, gateway, invoice_queued, settings):
    settings.PAYMENT_PENDING_TTL_MINUTES = 60
    old, _ = services.start_top_up(broker.user, package.pk)
    old_paid, _ = services.start_top_up(broker.user, package.pk)
    fresh, _ = services.start_top_up(broker.user, package.pk)
    _age(old, 61)
    _age(old_paid, 61)
    gateway.pay(old_paid)

    assert services.expire_stale_payments() == 1
    statuses = dict(Payment.objects.values_list("pk", "status"))
    assert statuses[old.pk] == Status.EXPIRED
    assert statuses[old_paid.pk] == Status.PAID
    assert statuses[fresh.pk] == Status.PENDING


def test_expire_skips_when_gateway_down(broker, package, invoice_queued):
    payment, _ = services.start_top_up(broker.user, package.pk)
    _age(payment, 120)
    with patch.object(MockPaymentsClient, "fetch", side_effect=OSError("down")):
        assert services.expire_stale_payments() == 0
    assert Payment.objects.get().status == Status.PENDING


def test_expire_task_runs(broker, package):
    from apps.payments.tasks import expire_stale_payments

    payment, _ = services.start_top_up(broker.user, package.pk)
    _age(payment, 120)
    assert expire_stale_payments() == 1


def test_wallet_top_up_rejects_bad_amounts(broker):
    wallet = wallet_services.wallet_for_user(broker.user)
    for bad in (0, -5, True, 1.5):
        with pytest.raises(wallet_services.WalletError):
            wallet_services.top_up(wallet, bad)
