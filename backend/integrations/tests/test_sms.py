import logging

import pytest

from integrations.sms import get_sms_client
from integrations.sms.live import LiveSmsClient
from integrations.sms.mock import MockSmsClient


def test_mock_client_masks_phone_in_logs(caplog):
    with caplog.at_level(logging.INFO):
        MockSmsClient().send("+966512345678", "code: 123456")

    assert "+966512345678" not in caplog.text
    assert "+9665•••••678" in caplog.text
    assert "123456" in caplog.text


def test_get_sms_client_follows_mode(settings):
    settings.INTEGRATIONS_MODE = "mock"
    assert isinstance(get_sms_client(), MockSmsClient)
    settings.INTEGRATIONS_MODE = "live"
    assert isinstance(get_sms_client(), LiveSmsClient)


def test_live_client_is_not_configured_yet():
    with pytest.raises(NotImplementedError):
        LiveSmsClient().send("+966512345678", "hi")
