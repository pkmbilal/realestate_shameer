"""Credit top-ups: packages brokers can buy, and one Payment row per checkout.

Money is stored in halalas (1 SAR = 100). Package prices include 15% VAT.
"""

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class TopUpPackage(models.Model):
    """A credit pack. Edited by staff in the admin; switch off with is_active."""

    name_ar = models.CharField(_("name (Arabic)"), max_length=100)
    name_en = models.CharField(_("name (English)"), max_length=100)
    credits = models.PositiveIntegerField(_("credits"), validators=[MinValueValidator(1)])
    price_halalas = models.PositiveIntegerField(
        _("price (halalas, VAT included)"),
        validators=[MinValueValidator(100)],
        help_text=_("1 SAR = 100 halalas. Example: 10000 = SAR 100.00."),
    )
    is_active = models.BooleanField(_("on sale"), default=True)
    sort_order = models.PositiveIntegerField(_("sort order"), default=0)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("top-up package")
        verbose_name_plural = _("top-up packages")
        ordering = ("sort_order", "price_halalas")
        constraints = [
            models.CheckConstraint(condition=Q(credits__gt=0), name="package_credits_positive"),
            models.CheckConstraint(
                condition=Q(price_halalas__gte=100), name="package_price_at_least_1_sar"
            ),
        ]

    def __str__(self):
        return f"{self.name_en} ({self.credits} credits)"


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", _("Waiting for payment")
        PAID = "paid", _("Paid")
        FAILED = "failed", _("Failed")
        EXPIRED = "expired", _("Expired")

    wallet = models.ForeignKey(
        "wallet.Wallet", on_delete=models.PROTECT, related_name="payments", verbose_name=_("wallet")
    )
    package = models.ForeignKey(
        TopUpPackage, on_delete=models.PROTECT, related_name="payments", verbose_name=_("package")
    )
    # Copied from the package when the checkout starts, so later price edits change nothing.
    credits = models.PositiveIntegerField(_("credits"))
    amount_halalas = models.PositiveIntegerField(_("amount (halalas, VAT included)"))
    status = models.CharField(
        _("status"), max_length=20, choices=Status.choices, default=Status.PENDING
    )
    gateway = models.CharField(_("gateway"), max_length=20, default="moyasar")
    gateway_ref = models.CharField(
        _("gateway reference"), max_length=100, unique=True, null=True, blank=True
    )
    credit_transaction = models.OneToOneField(
        "wallet.CreditTransaction",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payment",
        verbose_name=_("ledger entry"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name=_("created by"),
    )
    paid_at = models.DateTimeField(_("paid at"), null=True, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("payment")
        verbose_name_plural = _("payments")
        ordering = ("-created_at", "-id")
        indexes = [models.Index(fields=["status", "created_at"], name="payment_status_idx")]
        constraints = [
            models.CheckConstraint(
                condition=~Q(status="paid") | Q(credit_transaction__isnull=False),
                name="payment_paid_has_ledger_entry",
            ),
        ]

    def __str__(self):
        return f"Payment #{self.pk} ({self.get_status_display()})"
