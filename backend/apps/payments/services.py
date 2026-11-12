"""Top-up business logic.

Flow: start_top_up() creates a pending Payment and a gateway checkout -> the broker pays on
the gateway's page -> the gateway's webhook, the return page or the 15-minute task calls
confirm_payment(). confirm_payment() asks the gateway itself (never trusts the browser or
the webhook body) and adds the credits exactly once, however many times it is called.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import IntegrationError
from apps.core.services import record_integration_error
from apps.wallet import services as wallet_services
from integrations.payments import GatewayStatus, get_payments_client

from .models import Payment, TopUpPackage

logger = logging.getLogger(__name__)
Status = Payment.Status


class PaymentError(Exception):
    """A problem the user can see. `code` is a stable key the frontend translates."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def active_packages():
    return TopUpPackage.objects.filter(is_active=True)


def payments_for_user(user: User):
    wallet = wallet_services.wallet_for_user(user)
    if wallet is None:
        return Payment.objects.none()
    return wallet.payments.select_related("package", "invoice")


def return_url(payment: Payment, locale: str) -> str:
    locale = locale if locale in ("ar", "en") else "ar"
    return f"{settings.SITE_URL}/{locale}/dashboard/wallet/top-up/result?payment={payment.pk}"


def start_top_up(user: User, package_id, locale: str = "ar") -> tuple[Payment, str]:
    """Create a pending payment and return it with the URL of the gateway's checkout page."""
    wallet = wallet_services.wallet_for_user(user)
    if wallet is None:
        raise PaymentError("no_wallet")
    package = active_packages().filter(pk=package_id).first()
    if package is None:
        raise PaymentError("package_not_found")

    payment = Payment.objects.create(
        wallet=wallet,
        package=package,
        credits=package.credits,
        amount_halalas=package.price_halalas,
        created_by=user,
    )
    try:
        checkout = get_payments_client().create_checkout(
            amount_halalas=payment.amount_halalas,
            description=f"{settings.PORTAL_NAME}: {package.credits} credits",
            return_url=return_url(payment, locale),
            metadata={"payment_id": payment.pk},
        )
    except Exception as exc:
        logger.exception("payment %s: could not start checkout", payment.pk)
        record_integration_error(
            IntegrationError.Integration.PAYMENTS,
            "create_checkout",
            exc,
            reference=f"payment:{payment.pk}",
        )
        payment.status = Status.FAILED
        payment.save(update_fields=["status", "updated_at"])
        raise PaymentError("gateway_unavailable") from None
    payment.gateway_ref = checkout.ref
    payment.save(update_fields=["gateway_ref", "updated_at"])
    logger.info("payment %s: checkout started (%s halalas)", payment.pk, payment.amount_halalas)
    return payment, checkout.url


# An expired checkout can still be settled: if the buyer paid after we gave up, a late webhook
# must still add the credits they paid for.
SETTLEABLE = (Status.PENDING, Status.EXPIRED)


def confirm_payment(payment: Payment) -> Payment:
    """Settle a payment from the gateway's own answer. Safe to call any number of times.

    Paid  -> add the credits (once) and queue the e-invoice.
    Failed -> mark failed. Still pending, or gateway unreachable -> leave it.
    """
    payment, _ = _confirm(payment)
    return payment


def _confirm(payment: Payment) -> tuple[Payment, bool]:
    """Like confirm_payment, and also says whether the gateway answered."""
    if payment.status not in SETTLEABLE or not payment.gateway_ref:
        return payment, True

    # Ask the gateway outside the lock: it is a slow network call.
    try:
        result = get_payments_client().fetch(payment.gateway_ref)
    except Exception as exc:
        logger.exception("payment %s: could not reach the gateway", payment.pk)
        record_integration_error(
            IntegrationError.Integration.PAYMENTS, "fetch", exc, reference=f"payment:{payment.pk}"
        )
        return payment, False

    with transaction.atomic():
        locked = Payment.objects.select_for_update().get(pk=payment.pk)
        if locked.status not in SETTLEABLE:
            return locked, True  # someone else settled it while we waited

        if result.status == GatewayStatus.PAID:
            if result.amount_halalas != locked.amount_halalas or result.currency != "SAR":
                # Never credit a payment whose amount does not match. Staff must check it.
                logger.error(
                    "payment %s: amount mismatch (expected %s SAR halalas, gateway said %s %s)",
                    locked.pk,
                    locked.amount_halalas,
                    result.amount_halalas,
                    result.currency,
                )
                record_integration_error(
                    IntegrationError.Integration.PAYMENTS,
                    "amount_mismatch",
                    message=(
                        f"expected {locked.amount_halalas} SAR halalas, gateway said "
                        f"{result.amount_halalas} {result.currency}"
                    ),
                    reference=f"payment:{locked.pk}",
                    once=True,  # confirm runs again every 15 minutes; one open row is enough
                )
                return locked, True
            entry = wallet_services.top_up(
                locked.wallet,
                locked.credits,
                note=f"Top-up payment #{locked.pk}",
                by=locked.created_by,
            )
            locked.credit_transaction = entry
            locked.status = Status.PAID
            locked.paid_at = timezone.now()
            locked.save(update_fields=["credit_transaction", "status", "paid_at", "updated_at"])
            logger.info("payment %s: paid, %s credits added", locked.pk, locked.credits)

            from apps.invoicing.tasks import issue_invoice

            payment_id = locked.pk
            transaction.on_commit(lambda: issue_invoice.delay(payment_id))
        elif result.status == GatewayStatus.FAILED and locked.status == Status.PENDING:
            locked.status = Status.FAILED
            locked.save(update_fields=["status", "updated_at"])
            logger.info("payment %s: failed at the gateway", locked.pk)
    return locked, True


def confirm_by_ref(ref: str) -> Payment | None:
    """Used by the webhook: settle the payment the gateway is telling us about."""
    payment = Payment.objects.filter(gateway_ref=ref).first()
    if payment is None:
        logger.warning("webhook for an unknown checkout")
        return None
    return confirm_payment(payment)


def expire_stale_payments() -> int:
    """Settle pending payments older than PAYMENT_PENDING_TTL_MINUTES; expire the unpaid ones."""
    cutoff = timezone.now() - timedelta(minutes=settings.PAYMENT_PENDING_TTL_MINUTES)
    expired = 0
    for payment in Payment.objects.filter(status=Status.PENDING, created_at__lt=cutoff):
        payment, answered = _confirm(payment)  # one last check: it may have been paid
        if payment.status != Status.PENDING or not answered:
            continue  # settled, or gateway down: try again next run
        updated = Payment.objects.filter(pk=payment.pk, status=Status.PENDING).update(
            status=Status.EXPIRED, updated_at=timezone.now()
        )
        expired += updated
    if expired:
        logger.info("expired %s unpaid top-ups", expired)
    return expired
