"""ZATCA simplified tax invoices, one per paid top-up.

Everything printed on the invoice is copied onto the row when it is issued, so the PDF can be
re-created exactly at any time (the PDF itself is rendered on request, not stored in the
public file bucket). Money in halalas.
"""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class InvoiceCounter(models.Model):
    """The last invoice number used in each year. Locked while a number is taken."""

    year = models.PositiveIntegerField(primary_key=True)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = _("invoice counter")
        verbose_name_plural = _("invoice counters")

    def __str__(self):
        return f"{self.year}: {self.last_number}"


class Invoice(models.Model):
    class ZatcaStatus(models.TextChoices):
        PENDING = "pending", _("Not reported yet")
        REPORTED = "reported", _("Reported to ZATCA")

    payment = models.OneToOneField(
        "payments.Payment",
        on_delete=models.PROTECT,
        related_name="invoice",
        verbose_name=_("payment"),
    )
    number = models.CharField(_("invoice number"), max_length=30, unique=True)
    uuid = models.UUIDField(_("UUID"), default=uuid.uuid4, unique=True, editable=False)
    issued_at = models.DateTimeField(_("issued at"))

    seller_name_ar = models.CharField(_("seller name (Arabic)"), max_length=200)
    seller_name_en = models.CharField(_("seller name (English)"), max_length=200)
    seller_vat_number = models.CharField(_("seller VAT number"), max_length=15)
    seller_cr_number = models.CharField(_("seller CR number"), max_length=20, blank=True)
    seller_address = models.CharField(_("seller address"), max_length=300, blank=True)
    buyer_name = models.CharField(_("buyer name"), max_length=200, blank=True)

    description_ar = models.CharField(_("description (Arabic)"), max_length=200)
    description_en = models.CharField(_("description (English)"), max_length=200)
    credits = models.PositiveIntegerField(_("credits"))
    vat_rate_bp = models.PositiveIntegerField(_("VAT rate (basis points)"))
    subtotal_halalas = models.PositiveIntegerField(_("amount before VAT (halalas)"))
    vat_halalas = models.PositiveIntegerField(_("VAT (halalas)"))
    total_halalas = models.PositiveIntegerField(_("total with VAT (halalas)"))

    zatca_status = models.CharField(
        _("ZATCA status"), max_length=20, choices=ZatcaStatus.choices, default=ZatcaStatus.PENDING
    )
    zatca_hash = models.CharField(_("ZATCA invoice hash"), max_length=100, blank=True)
    qr_base64 = models.TextField(_("QR code payload"), blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("invoice")
        verbose_name_plural = _("invoices")
        ordering = ("-issued_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    subtotal_halalas=models.F("total_halalas") - models.F("vat_halalas")
                ),
                name="invoice_amounts_add_up",
            ),
        ]

    def __str__(self):
        return self.number
