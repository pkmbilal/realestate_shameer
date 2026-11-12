import json
import urllib.request

from django.conf import settings

from .base import ExpiryWarning, LeadNotification, WhatsAppClient

GRAPH_URL = "https://graph.facebook.com/v21.0/{phone_number_id}/messages"


class LiveWhatsAppClient(WhatsAppClient):
    """WhatsApp Cloud API. Sends approved message templates (settings.WHATSAPP_*).

    Lead template body parameters, in order: listing reference, contact channel,
    buyer name, buyer phone.
    Expiry template body parameters, in order: listing reference, expiry date (YYYY-MM-DD),
    reason ("licence" or "post_period"), dashboard link.
    """

    def send_lead_notification(self, notification: LeadNotification) -> None:
        self._send_template(
            to=notification.to,
            template=settings.WHATSAPP_LEAD_TEMPLATE,
            locale=notification.locale,
            params=[
                notification.listing_reference,
                notification.channel,
                notification.buyer_name or "-",
                notification.buyer_phone or "-",
            ],
        )

    def send_expiry_warning(self, warning: ExpiryWarning) -> None:
        self._send_template(
            to=warning.to,
            template=settings.WHATSAPP_EXPIRY_TEMPLATE,
            locale=warning.locale,
            params=[
                warning.listing_reference,
                warning.expires_on.isoformat(),
                warning.reason,
                warning.dashboard_url,
            ],
        )

    def _send_template(self, *, to: str, template: str, locale: str, params: list[str]) -> None:
        if not (settings.WHATSAPP_PHONE_NUMBER_ID and settings.WHATSAPP_ACCESS_TOKEN):
            raise NotImplementedError(
                "WhatsApp Cloud API is not configured. Set WHATSAPP_PHONE_NUMBER_ID and "
                "WHATSAPP_ACCESS_TOKEN, or use INTEGRATIONS_MODE=mock."
            )
        body = {
            "messaging_product": "whatsapp",
            "to": to.lstrip("+"),
            "type": "template",
            "template": {
                "name": template,
                "language": {"code": locale},
                "components": [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": p} for p in params],
                    }
                ],
            },
        }
        request = urllib.request.Request(
            GRAPH_URL.format(phone_number_id=settings.WHATSAPP_PHONE_NUMBER_ID),
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        # urlopen raises HTTPError on 4xx/5xx, so the Celery task retries.
        with urllib.request.urlopen(request, timeout=15):  # noqa: S310 (fixed https URL)
            pass
