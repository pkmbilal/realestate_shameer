from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class LeadNotification:
    """What the broker is told about a new lead. Phones are E.164."""

    to: str  # the broker's WhatsApp number
    listing_reference: str
    listing_url: str
    channel: str  # "whatsapp", "call" or "form"
    buyer_name: str = ""
    buyer_phone: str = ""
    message: str = ""
    locale: str = "ar"


class WhatsAppClient(ABC):
    """Sends WhatsApp messages from the portal's business number."""

    @abstractmethod
    def send_lead_notification(self, notification: LeadNotification) -> None:
        """Raise an exception if the message could not be sent (the caller retries)."""
