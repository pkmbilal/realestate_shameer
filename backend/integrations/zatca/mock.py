import base64
import hashlib
import logging

from .base import InvoiceData, ZatcaClient, ZatcaResult, build_qr_tlv

logger = logging.getLogger(__name__)


class MockZatcaClient(ZatcaClient):
    """Local development: pretends ZATCA accepted the invoice. Builds a real Phase-1 QR."""

    def report_simplified(self, data: InvoiceData) -> ZatcaResult:
        digest = hashlib.sha256(f"{data.uuid}:{data.number}:{data.total_halalas}".encode())
        logger.info("[mock zatca] reported invoice %s", data.number)
        return ZatcaResult(
            status="reported",
            invoice_hash=base64.b64encode(digest.digest()).decode(),
            qr_base64=build_qr_tlv(data),
        )
