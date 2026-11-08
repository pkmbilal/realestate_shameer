import hmac
from abc import ABC, abstractmethod
from dataclasses import dataclass

from django.conf import settings


class GatewayStatus:
    """Our simplified view of a checkout's state at the gateway."""

    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"


@dataclass(frozen=True)
class Checkout:
    ref: str  # the gateway's id for this checkout (Moyasar invoice id)
    url: str  # where the buyer's browser goes to pay


@dataclass(frozen=True)
class GatewayResult:
    status: str  # one of GatewayStatus
    amount_halalas: int
    currency: str


class WebhookError(Exception):
    """The webhook could not be trusted (wrong or missing secret)."""


class PaymentsClient(ABC):
    """A payment gateway with a hosted checkout page (mada, Apple Pay, STC Pay)."""

    @abstractmethod
    def create_checkout(
        self, *, amount_halalas: int, description: str, return_url: str, metadata: dict
    ) -> Checkout:
        """Start a checkout for `amount_halalas` SAR (VAT included)."""

    @abstractmethod
    def fetch(self, ref: str) -> GatewayResult:
        """Ask the gateway for the current state of a checkout. Never trust the browser."""

    def parse_webhook(self, payload: dict) -> str:
        """Check the shared secret and return the checkout ref the webhook is about.

        The webhook only tells us *which* checkout changed; the caller then calls fetch()
        to learn the real status, so a forged body cannot add credits.
        """
        expected = settings.MOYASAR_WEBHOOK_SECRET
        given = str(payload.get("secret_token") or "")
        if not expected or not hmac.compare_digest(given.encode(), expected.encode()):
            raise WebhookError("bad_secret")
        data = payload.get("data") or {}
        ref = data.get("invoice_id") or data.get("id")
        if not ref:
            raise WebhookError("no_ref")
        return str(ref)
