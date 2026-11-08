"""Issuing ZATCA invoices for paid top-ups, and rendering them as PDFs."""

import base64
import io
import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.utils import timezone

from apps.payments.models import Payment
from integrations.zatca import InvoiceData, get_zatca_client
from integrations.zatca.base import halalas_to_sar

from .models import Invoice, InvoiceCounter

logger = logging.getLogger(__name__)


class InvoiceError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def split_vat(total_halalas: int, rate_bp: int) -> tuple[int, int]:
    """Split a VAT-inclusive total into (amount before VAT, VAT), rounding VAT half-up.

    SAR 100.00 at 15% -> (8696, 1304). Integers only.
    """
    denominator = 10000 + rate_bp
    vat = (2 * total_halalas * rate_bp + denominator) // (2 * denominator)
    return total_halalas - vat, vat


def _next_number(year: int) -> str:
    """INV-2026-000001, INV-2026-000002, … with no gaps or repeats (caller holds a transaction)."""
    InvoiceCounter.objects.get_or_create(year=year)
    counter = InvoiceCounter.objects.select_for_update().get(year=year)
    counter.last_number += 1
    counter.save(update_fields=["last_number"])
    return f"INV-{year}-{counter.last_number:06d}"


def _create(payment: Payment) -> Invoice:
    issued_at = payment.paid_at or timezone.now()
    subtotal, vat = split_vat(payment.amount_halalas, settings.VAT_RATE_BP)
    wallet = payment.wallet
    with transaction.atomic():
        return Invoice.objects.create(
            payment=payment,
            number=_next_number(timezone.localtime(issued_at).year),
            issued_at=issued_at,
            seller_name_ar=settings.SELLER_NAME_AR,
            seller_name_en=settings.SELLER_NAME_EN,
            seller_vat_number=settings.SELLER_VAT_NUMBER,
            seller_cr_number=settings.SELLER_CR_NUMBER,
            seller_address=settings.SELLER_ADDRESS,
            buyer_name=wallet.holder_name[:200],
            description_ar=f"شحن رصيد: {payment.credits} رصيد",
            description_en=f"Credit top-up: {payment.credits} credits",
            credits=payment.credits,
            vat_rate_bp=settings.VAT_RATE_BP,
            subtotal_halalas=subtotal,
            vat_halalas=vat,
            total_halalas=payment.amount_halalas,
        )


def issue_invoice(payment: Payment) -> Invoice:
    """Create the invoice for a paid top-up (once) and report it to ZATCA (until it succeeds)."""
    if payment.status != Payment.Status.PAID:
        raise InvoiceError("payment_not_paid")

    invoice = Invoice.objects.filter(payment=payment).first()
    if invoice is None:
        try:
            invoice = _create(payment)
        except IntegrityError:
            invoice = Invoice.objects.get(payment=payment)  # created at the same moment

    if invoice.zatca_status != Invoice.ZatcaStatus.REPORTED:
        result = get_zatca_client().report_simplified(
            InvoiceData(
                number=invoice.number,
                uuid=str(invoice.uuid),
                issued_at=invoice.issued_at,
                seller_name=invoice.seller_name_ar,
                seller_vat_number=invoice.seller_vat_number,
                total_halalas=invoice.total_halalas,
                vat_halalas=invoice.vat_halalas,
            )
        )
        invoice.zatca_status = Invoice.ZatcaStatus.REPORTED
        invoice.zatca_hash = result.invoice_hash
        invoice.qr_base64 = result.qr_base64
        invoice.save(update_fields=["zatca_status", "zatca_hash", "qr_base64", "updated_at"])
        logger.info("invoice %s reported to ZATCA", invoice.number)
    return invoice


def invoices_for_user(user):
    from apps.wallet import services as wallet_services

    wallet = wallet_services.wallet_for_user(user)
    if wallet is None:
        return Invoice.objects.none()
    return Invoice.objects.filter(payment__wallet=wallet, zatca_status=Invoice.ZatcaStatus.REPORTED)


# --- PDF -----------------------------------------------------------------------------


def _qr_svg_data_uri(payload: str) -> str:
    import qrcode
    import qrcode.image.svg

    image = qrcode.make(payload, image_factory=qrcode.image.svg.SvgPathImage, box_size=10)
    buffer = io.BytesIO()
    image.save(buffer)
    return "data:image/svg+xml;base64," + base64.b64encode(buffer.getvalue()).decode()


def render_pdf(invoice: Invoice) -> bytes:
    """The bilingual (Arabic/English) invoice as PDF bytes."""
    from weasyprint import HTML

    issued_local = timezone.localtime(invoice.issued_at, timezone=_riyadh())
    html = render_to_string(
        "invoicing/invoice.html",
        {
            "invoice": invoice,
            "issued": issued_local,
            "subtotal": halalas_to_sar(invoice.subtotal_halalas),
            "vat": halalas_to_sar(invoice.vat_halalas),
            "total": halalas_to_sar(invoice.total_halalas),
            "vat_percent": f"{invoice.vat_rate_bp // 100}",
            "qr": _qr_svg_data_uri(invoice.qr_base64) if invoice.qr_base64 else "",
        },
    )
    return HTML(string=html).write_pdf()


def _riyadh():
    from zoneinfo import ZoneInfo

    return ZoneInfo(settings.DISPLAY_TIME_ZONE)
