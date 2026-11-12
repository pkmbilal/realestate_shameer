import json
from datetime import date
from unittest.mock import patch

import pytest

from integrations.whatsapp import ExpiryWarning, LeadNotification, get_whatsapp_client
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


def test_live_expiry_warning_sends_the_expiry_template(settings):
    settings.WHATSAPP_PHONE_NUMBER_ID = "123"
    settings.WHATSAPP_ACCESS_TOKEN = "token"
    settings.WHATSAPP_EXPIRY_TEMPLATE = "listing_expiring"
    warning = ExpiryWarning(
        to="+966512345678",
        listing_reference="ABCD2345",
        expires_on=date(2026, 12, 1),
        reason="licence",
        dashboard_url="https://example.test/ar/dashboard",
    )
    with patch("urllib.request.urlopen") as urlopen:
        LiveWhatsAppClient().send_expiry_warning(warning)
    body = json.loads(urlopen.call_args.args[0].data)
    assert body["to"] == "966512345678"
    assert body["template"]["name"] == "listing_expiring"
    params = [p["text"] for p in body["template"]["components"][0]["parameters"]]
    assert params == ["ABCD2345", "2026-12-01", "licence", "https://example.test/ar/dashboard"]
