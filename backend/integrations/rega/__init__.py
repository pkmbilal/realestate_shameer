"""REGA adapter: reads advertising licence data that every listing starts from."""

from integrations.base import get_client

from .base import RegaAdLicence, RegaClient, RegaError
from .live import LiveRegaClient
from .mock import MockRegaClient


def get_rega_client() -> RegaClient:
    return get_client(MockRegaClient, LiveRegaClient)


__all__ = ["RegaAdLicence", "RegaClient", "RegaError", "get_rega_client"]
