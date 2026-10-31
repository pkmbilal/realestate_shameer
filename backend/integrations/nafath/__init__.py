"""Nafath identity verification adapter, used before anyone may post listings."""

from integrations.base import get_client

from .base import NafathClient, NafathRequest, NafathStatus
from .live import LiveNafathClient
from .mock import MockNafathClient


def get_nafath_client() -> NafathClient:
    return get_client(MockNafathClient, LiveNafathClient)


__all__ = ["NafathClient", "NafathRequest", "NafathStatus", "get_nafath_client"]
