import base64
import json
import urllib.request

from django.conf import settings

from .base import Checkout, GatewayResult, GatewayStatus, PaymentsClient

API_URL = "https://api.moyasar.com/v1"

# Moyasar invoice statuses -> ours. Anything else (e.g. "initiated") is still pending.
STATUS_MAP = {
    "paid": GatewayStatus.PAID,
    "failed": GatewayStatus.FAILED,
    "expired": GatewayStatus.FAILED,
    "canceled": GatewayStatus.FAILED,
    "voided": GatewayStatus.FAILED,
}


class LivePaymentsClient(PaymentsClient):
    """Moyasar Invoices API: Moyasar hosts the payment page (mada, Apple Pay, STC Pay).

    Not yet tested against Moyasar: needs MOYASAR_SECRET_KEY from the merchant contract.
    """

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        if not settings.MOYASAR_SECRET_KEY:
            raise NotImplementedError(
                "Moyasar is not configured. Set MOYASAR_SECRET_KEY, or use INTEGRATIONS_MODE=mock."
            )
        token = base64.b64encode(f"{settings.MOYASAR_SECRET_KEY}:".encode()).decode()
        request = urllib.request.Request(
            f"{API_URL}{path}",
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"},
            method=method,
        )
        # urlopen raises HTTPError on 4xx/5xx.
        with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 (fixed https URL)
            return json.loads(response.read())

    def create_checkout(self, *, amount_halalas, description, return_url, metadata) -> Checkout:
        data = self._request(
            "POST",
            "/invoices",
            {
                "amount": amount_halalas,
                "currency": "SAR",
                "description": description,
                "success_url": return_url,
                "back_url": return_url,
                "metadata": {k: str(v) for k, v in metadata.items()},
            },
        )
        return Checkout(ref=str(data["id"]), url=data["url"])

    def fetch(self, ref: str) -> GatewayResult:
        data = self._request("GET", f"/invoices/{ref}")
        return GatewayResult(
            status=STATUS_MAP.get(data.get("status", ""), GatewayStatus.PENDING),
            amount_halalas=int(data.get("amount", 0)),
            currency=str(data.get("currency", "")).upper(),
        )
