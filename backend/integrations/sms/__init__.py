"""SMS adapter for OTP codes. Live provider (Unifonic or Taqnyat) not chosen yet — see live.py."""

from integrations.base import get_client

from .base import SmsClient
from .live import LiveSmsClient
from .mock import MockSmsClient


def get_sms_client() -> SmsClient:
    return get_client(MockSmsClient, LiveSmsClient)


__all__ = ["SmsClient", "get_sms_client"]
