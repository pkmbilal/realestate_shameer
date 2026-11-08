import uuid
from urllib.parse import urlencode

from django.conf import settings
from django.core.cache import cache

from .base import Checkout, GatewayResult, GatewayStatus, PaymentsClient

STATE_TTL = 60 * 60 * 24


def _key(ref: str) -> str:
    return f"mock-payments:{ref}"


class MockPaymentsClient(PaymentsClient):
    """Local development: a fake checkout page on the API with "Pay" and "Fail" buttons.

    The checkout state lives in the cache. Nothing leaves the machine.
    """

    def create_checkout(self, *, amount_halalas, description, return_url, metadata) -> Checkout:
        ref = f"mock_{uuid.uuid4().hex}"
        cache.set(
            _key(ref),
            {
                "status": GatewayStatus.PENDING,
                "amount": amount_halalas,
                "return_url": return_url,
                "description": description,
            },
            STATE_TTL,
        )
        url = f"{settings.API_PUBLIC_URL}/api/payments/mock-checkout/{ref}/"
        return Checkout(ref=ref, url=url)

    def fetch(self, ref: str) -> GatewayResult:
        state = cache.get(_key(ref))
        if state is None:
            return GatewayResult(status=GatewayStatus.FAILED, amount_halalas=0, currency="SAR")
        return GatewayResult(status=state["status"], amount_halalas=state["amount"], currency="SAR")

    # --- Used by the mock checkout page and by tests -------------------------------------

    @staticmethod
    def get_state(ref: str) -> dict | None:
        return cache.get(_key(ref))

    @staticmethod
    def set_status(ref: str, status: str) -> str | None:
        """Mark the checkout paid or failed; returns the URL to send the browser back to."""
        state = cache.get(_key(ref))
        if state is None:
            return None
        state["status"] = status
        cache.set(_key(ref), state, STATE_TTL)
        sep = "&" if "?" in state["return_url"] else "?"
        return state["return_url"] + sep + urlencode({"status": status})
