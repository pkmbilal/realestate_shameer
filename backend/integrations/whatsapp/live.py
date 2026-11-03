import json
import urllib.request

from django.conf import settings

from .base import LeadNotification, WhatsAppClient

GRAPH_URL = "https://graph.facebook.com/v21.0/{phone_number_id}/messages"


class LiveWhatsAppClient(WhatsAppClient):
    """WhatsApp Cloud API. Sends the approved lead template (settings.WHATSAPP_*).

    The template takes four body parameters, in this order:
    listing reference, contact channel, buyer name, buyer phone.
    """

    def send_lead_notification(self, notification: LeadNotification) -> None:
        if not (settings.WHATSAPP_PHONE_NUMBER_ID and settings.WHATSAPP_ACCESS_TOKEN):
            raise NotImplementedError(
                "WhatsApp Cloud API is not configured. Set WHATSAPP_PHONE_NUMBER_ID and "
                "WHATSAPP_ACCESS_TOKEN, or use INTEGRATIONS_MODE=mock."
            )
        params = [
            notification.listing_reference,
            notification.channel,
            notification.buyer_name or "-",
            notification.buyer_phone or "-",
        ]
        body = {
            "messaging_product": "whatsapp",
            "to": notification.to.lstrip("+"),
            "type": "template",
            "template": {
                "name": settings.WHATSAPP_LEAD_TEMPLATE,
                "language": {"code": notification.locale},
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
