import logging

import pytest

from integrations.nafath import NafathStatus, get_nafath_client
from integrations.nafath.live import LiveNafathClient
from integrations.nafath.mock import MockNafathClient

NATIONAL_ID = "1012345678"


def test_mock_client_approves_and_never_logs_the_id(caplog):
    client = MockNafathClient()
    with caplog.at_level(logging.INFO):
        request = client.start(NATIONAL_ID)

    assert request.transaction_ref
    assert 10 <= int(request.random_number) <= 99
    assert NATIONAL_ID not in caplog.text
    assert client.status(request.transaction_ref) == NafathStatus.APPROVED


def test_get_nafath_client_follows_mode(settings):
    settings.INTEGRATIONS_MODE = "mock"
    assert isinstance(get_nafath_client(), MockNafathClient)
    settings.INTEGRATIONS_MODE = "live"
    assert isinstance(get_nafath_client(), LiveNafathClient)


def test_live_client_is_not_configured_yet():
    with pytest.raises(NotImplementedError):
        LiveNafathClient().start(NATIONAL_ID)
