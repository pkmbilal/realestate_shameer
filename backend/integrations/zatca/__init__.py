"""ZATCA e-invoicing adapter. The live client needs ZATCA onboarding (see live.py)."""

from integrations.base import get_client

from .base import InvoiceData, ZatcaClient, ZatcaResult, build_qr_tlv, parse_qr_tlv
from .live import LiveZatcaClient
from .mock import MockZatcaClient


def get_zatca_client() -> ZatcaClient:
    return get_client(MockZatcaClient, LiveZatcaClient)


__all__ = [
    "InvoiceData",
    "ZatcaClient",
    "ZatcaResult",
    "build_qr_tlv",
    "get_zatca_client",
    "parse_qr_tlv",
]
