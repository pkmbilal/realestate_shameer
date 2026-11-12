"""Shared operational records that belong to no single domain app."""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class IntegrationError(models.Model):
    """A failure talking to an outside system (REGA, Nafath, SMS, ZATCA, payments, WhatsApp).

    Shown to staff in admin so problems are noticed. Messages are cleaned before saving:
    long digit runs (phone numbers, national IDs) are masked (PDPL). Rows are never edited,
    except that staff can mark one resolved.
    """

    class Integration(models.TextChoices):
        REGA = "rega", "REGA"
        NAFATH = "nafath", "Nafath"
        SMS = "sms", "SMS"
        ZATCA = "zatca", "ZATCA"
        PAYMENTS = "payments", _("Payments")
        WHATSAPP = "whatsapp", "WhatsApp"

    integration = models.CharField(_("integration"), max_length=20, choices=Integration.choices)
    operation = models.CharField(_("operation"), max_length=50)
    error_code = models.CharField(_("error"), max_length=100, blank=True)
    message = models.CharField(_("message"), max_length=500, blank=True)
    # What it was about, e.g. "listing:AB12CD34" or "payment:42". Never a phone number.
    reference = models.CharField(_("reference"), max_length=100, blank=True)
    created_at = models.DateTimeField(_("at"), auto_now_add=True, db_index=True)
    resolved_at = models.DateTimeField(_("resolved at"), null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("resolved by"),
    )

    class Meta:
        verbose_name = _("integration error")
        verbose_name_plural = _("integration errors")
        ordering = ("-created_at", "-id")

    def __str__(self):
        return f"{self.integration}.{self.operation}: {self.error_code}"
