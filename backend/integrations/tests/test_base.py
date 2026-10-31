from integrations.base import get_client


class FakeMock:
    pass


class FakeLive:
    pass


def test_mock_mode_returns_mock_client(settings):
    settings.INTEGRATIONS_MODE = "mock"
    assert isinstance(get_client(FakeMock, FakeLive), FakeMock)


def test_live_mode_returns_live_client(settings):
    settings.INTEGRATIONS_MODE = "live"
    assert isinstance(get_client(FakeMock, FakeLive), FakeLive)
