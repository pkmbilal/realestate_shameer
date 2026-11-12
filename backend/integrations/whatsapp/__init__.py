"""WhatsApp Cloud API adapter, used to tell brokers about new leads."""

from integrations.base import get_client

from .base import ExpiryWarning, LeadNotification, WhatsAppClient
from .live import LiveWhatsAppClient
from .mock import MockWhatsAppClient


def get_whatsapp_client() -> WhatsAppClient:
    return get_client(MockWhatsAppClient, LiveWhatsAppClient)


__all__ = ["ExpiryWarning", "LeadNotification", "WhatsAppClient", "get_whatsapp_client"]
