import pytest

from integrations.whatsapp import LeadNotification, get_whatsapp_client
from integrations.whatsapp.live import LiveWhatsAppClient
from integrations.whatsapp.mock import MockWhatsAppClient


def test_get_whatsapp_client_follows_mode(settings):
    settings.INTEGRATIONS_MODE = "mock"
    assert isinstance(get_whatsapp_client(), MockWhatsAppClient)
    settings.INTEGRATIONS_MODE = "live"
    assert isinstance(get_whatsapp_client(), LiveWhatsAppClient)


def test_live_client_needs_credentials(settings):
    settings.WHATSAPP_PHONE_NUMBER_ID = ""
    settings.WHATSAPP_ACCESS_TOKEN = ""
    notice = LeadNotification(
        to="+966512345678", listing_reference="ABCD2345", listing_url="https://x", channel="call"
    )
    with pytest.raises(NotImplementedError):
        LiveWhatsAppClient().send_lead_notification(notice)
