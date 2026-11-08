import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class InvoiceData:
    """What ZATCA needs to know about a simplified (B2C) tax invoice. Money in halalas."""

    number: str
    uuid: str
    issued_at: datetime  # timezone-aware
    seller_name: str
    seller_vat_number: str
    total_halalas: int  # VAT included
    vat_halalas: int


@dataclass(frozen=True)
class ZatcaResult:
    status: str  # "reported" once ZATCA has accepted it
    invoice_hash: str
    qr_base64: str  # the TLV payload printed as a QR code on the invoice


def halalas_to_sar(halalas: int) -> str:
    """1234 -> "12.34". Integer maths only, no floats."""
    sign = "-" if halalas < 0 else ""
    halalas = abs(halalas)
    return f"{sign}{halalas // 100}.{halalas % 100:02d}"


def build_qr_tlv(data: InvoiceData) -> str:
    """The ZATCA QR payload: tag-length-value fields 1-5, base64-encoded.

    1 seller name, 2 VAT number, 3 timestamp, 4 total with VAT, 5 VAT amount.
    """
    fields = [
        data.seller_name,
        data.seller_vat_number,
        data.issued_at.isoformat(timespec="seconds"),
        halalas_to_sar(data.total_halalas),
        halalas_to_sar(data.vat_halalas),
    ]
    out = bytearray()
    for tag, value in enumerate(fields, start=1):
        raw = value.encode("utf-8")
        if len(raw) > 255:
            raise ValueError(f"ZATCA QR field {tag} is too long")
        out += bytes([tag, len(raw)]) + raw
    return base64.b64encode(bytes(out)).decode()


def parse_qr_tlv(qr_base64: str) -> dict[int, str]:
    """Decode a TLV QR payload (used in tests and by the admin)."""
    raw = base64.b64decode(qr_base64)
    fields, i = {}, 0
    while i < len(raw):
        tag, length = raw[i], raw[i + 1]
        fields[tag] = raw[i + 2 : i + 2 + length].decode("utf-8")
        i += 2 + length
    return fields


class ZatcaClient(ABC):
    """ZATCA Fatoora: reports simplified invoices."""

    @abstractmethod
    def report_simplified(self, data: InvoiceData) -> ZatcaResult:
        """Report the invoice to ZATCA. Raise an exception if it failed (the caller retries)."""
