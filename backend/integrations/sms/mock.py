import logging

from apps.accounts.phone import mask_phone

from .base import SmsClient

logger = logging.getLogger(__name__)


class MockSmsClient(SmsClient):
    """Local development: prints the message to the api logs instead of sending it.

    The text (with the OTP code) is shown so developers can log in; the phone stays masked.
    """

    def send(self, phone: str, text: str) -> None:
        logger.info("[mock sms] to %s: %s", mask_phone(phone), text)
