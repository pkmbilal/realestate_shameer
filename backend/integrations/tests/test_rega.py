from datetime import timedelta

import pytest

from apps.core.dates import riyadh_today
from integrations.rega import RegaError, get_rega_client
from integrations.rega.live import LiveRegaClient
from integrations.rega.mock import OTHER_ADVERTISER_FAL, MockRegaClient


def test_mock_returns_stable_valid_licence():
    client = MockRegaClient()
    first = client.fetch_ad_licence("7100012345")
    assert first == client.fetch_ad_licence("7100012345")
    assert first.expires_on > riyadh_today()
    assert first.purpose in ("sale", "rent")
    assert first.city_name_en in ("Dammam", "Khobar", "Dhahran", "Jubail")
    assert first.advertiser_fal == ""


def test_mock_special_endings():
    client = MockRegaClient()
    with pytest.raises(RegaError) as exc:
        client.fetch_ad_licence("7100010000")
    assert exc.value.code == "not_found"
    expired = client.fetch_ad_licence("7100019999")
    assert expired.expires_on == riyadh_today() - timedelta(days=1)
    assert client.fetch_ad_licence("7100018888").advertiser_fal == OTHER_ADVERTISER_FAL


def test_get_rega_client_follows_mode(settings):
    settings.INTEGRATIONS_MODE = "mock"
    assert isinstance(get_rega_client(), MockRegaClient)
    settings.INTEGRATIONS_MODE = "live"
    assert isinstance(get_rega_client(), LiveRegaClient)


def test_live_client_is_not_configured_yet():
    with pytest.raises(NotImplementedError):
        LiveRegaClient().fetch_ad_licence("7100012345")
