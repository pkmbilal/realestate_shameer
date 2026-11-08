"""Payment gateway adapter for credit top-ups. Live client: Moyasar (see live.py)."""

from integrations.base import get_client

from .base import Checkout, GatewayResult, GatewayStatus, PaymentsClient, WebhookError
from .live import LivePaymentsClient
from .mock import MockPaymentsClient


def get_payments_client() -> PaymentsClient:
    return get_client(MockPaymentsClient, LivePaymentsClient)


__all__ = [
    "Checkout",
    "GatewayResult",
    "GatewayStatus",
    "PaymentsClient",
    "WebhookError",
    "get_payments_client",
]
