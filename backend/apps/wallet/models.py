"""Credits wallet: one wallet per broker or agency, and an append-only ledger.

The balance is the sum of the ledger. `Wallet.balance` is only a cached copy, updated by
services.py inside a locked transaction whenever a ledger row is added.
CreditTransaction rows are never edited or deleted; mistakes are fixed with new rows.
"""

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class Wallet(models.Model):
    broker = models.OneToOneField(
        "brokers.BrokerProfile",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="wallet",
        verbose_name=_("broker"),
    )
    agency = models.OneToOneField(
        "brokers.Agency",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="wallet",
        verbose_name=_("agency"),
    )
    balance = models.IntegerField(_("balance (credits)"), default=0)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("wallet")
        verbose_name_plural = _("wallets")
        ordering = ("-updated_at",)
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(broker__isnull=False, agency__isnull=True)
                    | Q(broker__isnull=True, agency__isnull=False)
                ),
                name="wallet_has_one_holder",
            ),
            models.CheckConstraint(condition=Q(balance__gte=0), name="wallet_balance_not_negative"),
        ]

    def __str__(self):
        holder = self.broker or self.agency
        return f"{holder} ({self.balance})"

    @property
    def holder_name(self) -> str:
        holder = self.broker or self.agency
        return holder.name_en or holder.name_ar if holder else ""


class AppendOnlyError(Exception):
    """Raised when code tries to change or delete a ledger row."""


class CreditTransaction(models.Model):
    class Kind(models.TextChoices):
        GRANT = "grant", _("Free grant")
        TOPUP = "topup", _("Top-up")
        SPEND = "spend", _("Spend")
        REFUND = "refund", _("Refund")
        ADJUSTMENT = "adjustment", _("Staff adjustment")

    class Action(models.TextChoices):
        POST = "post", _("Post a listing")
        REFRESH = "refresh", _("Refresh a listing")
        FEATURE = "feature", _("Feature a listing")

    wallet = models.ForeignKey(
        Wallet, on_delete=models.PROTECT, related_name="transactions", verbose_name=_("wallet")
    )
    kind = models.CharField(_("kind"), max_length=20, choices=Kind.choices)
    action = models.CharField(_("action"), max_length=20, choices=Action.choices, blank=True)
    amount = models.IntegerField(
        _("amount (credits)"), help_text=_("Positive adds, negative takes.")
    )
    balance_after = models.IntegerField(_("balance after"))
    listing = models.ForeignKey(
        "listings.Listing",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="credit_transactions",
        verbose_name=_("listing"),
    )
    reverses = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversed_by",
        verbose_name=_("reverses"),
    )
    note = models.CharField(_("note"), max_length=500, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("created by"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("credit transaction")
        verbose_name_plural = _("credit transactions")
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["wallet", "-created_at"], name="credit_tx_wallet_idx"),
            models.Index(fields=["listing", "action"], name="credit_tx_listing_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=~Q(amount=0), name="credit_tx_amount_not_zero"),
            models.CheckConstraint(
                condition=Q(balance_after__gte=0), name="credit_tx_balance_not_negative"
            ),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} {self.amount:+d}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise AppendOnlyError("Credit transactions cannot be changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AppendOnlyError("Credit transactions cannot be deleted.")


class CreditPrice(models.Model):
    """What each paid action costs. Edited by staff in the admin; 0 means free."""

    action = models.CharField(
        _("action"), max_length=20, choices=CreditTransaction.Action.choices, unique=True
    )
    credits = models.PositiveIntegerField(_("credits"), default=0)
    days = models.PositiveIntegerField(
        _("days"),
        default=0,
        validators=[MinValueValidator(0)],
        help_text=_("How long the action lasts (used by 'feature')."),
    )
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("credit price")
        verbose_name_plural = _("credit prices")
        ordering = ("action",)

    def __str__(self):
        return f"{self.get_action_display()}: {self.credits}"
