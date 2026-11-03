import logging

from apps.accounts.phone import mask_phone

from .base import LeadNotification, WhatsAppClient

logger = logging.getLogger(__name__)


class MockWhatsAppClient(WhatsAppClient):
    """Local development: writes the notification to the logs instead of sending it.

    Phone numbers are masked and the buyer's message is left out (PDPL).
    """

    def send_lead_notification(self, notification: LeadNotification) -> None:
        logger.info(
            "[mock whatsapp] to %s: new %s lead on %s (buyer %s)",
            mask_phone(notification.to),
            notification.channel,
            notification.listing_reference,
            mask_phone(notification.buyer_phone) if notification.buyer_phone else "-",
        )
