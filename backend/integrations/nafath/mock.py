import logging
import secrets
import uuid

from .base import NafathClient, NafathRequest, NafathStatus

logger = logging.getLogger(__name__)


class MockNafathClient(NafathClient):
    """Local development: every request is approved straight away. The ID is never logged."""

    def start(self, national_id: str) -> NafathRequest:
        ref = f"mock-{uuid.uuid4()}"
        number = str(secrets.randbelow(90) + 10)
        logger.info("[mock nafath] request %s started, number %s (auto-approves)", ref, number)
        return NafathRequest(transaction_ref=ref, random_number=number)

    def status(self, transaction_ref: str) -> NafathStatus:
        return NafathStatus.APPROVED
