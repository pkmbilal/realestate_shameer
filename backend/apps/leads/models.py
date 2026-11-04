"""Leads: every time a visitor contacts an advertiser about a listing."""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.phone import mask_phone


class Lead(models.Model):
    class Channel(models.TextChoices):
        WHATSAPP = "whatsapp", _("WhatsApp")
        CALL = "call", _("Call")
        FORM = "form", _("Enquiry form")

    class NotifyStatus(models.TextChoices):
        PENDING = "pending", _("Pending")
        SENT = "sent", _("Sent")
        FAILED = "failed", _("Failed")
        SKIPPED = "skipped", _("Skipped")  # nobody to notify on WhatsApp (e.g. owner listing)

    listing = models.ForeignKey(
        "listings.Listing",
        on_delete=models.PROTECT,
        related_name="leads",
        verbose_name=_("listing"),
    )
    # Who the listing belonged to when the lead came in.
    broker = models.ForeignKey(
        "brokers.BrokerProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads",
        verbose_name=_("broker"),
    )
    agency = models.ForeignKey(
        "brokers.Agency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads",
        verbose_name=_("agency"),
    )
    channel = models.CharField(_("channel"), max_length=10, choices=Channel.choices)
    # The signed-in visitor, if any.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads",
        verbose_name=_("visitor"),
    )
    # Enquiry form only. Phone in E.164; only ever shown masked in admin.
    name = models.CharField(_("name"), max_length=100, blank=True)
    phone = models.CharField(_("phone"), max_length=16, blank=True)
    message = models.TextField(_("message"), max_length=1000, blank=True)
    # Salted hash of IP + browser, only to stop repeat clicks counting twice. Not reversible.
    client_hash = models.CharField(_("visitor fingerprint"), max_length=64, blank=True)
    notify_status = models.CharField(
        _("notification"),
        max_length=10,
        choices=NotifyStatus.choices,
        default=NotifyStatus.PENDING,
    )
    notified_at = models.DateTimeField(_("notified at"), null=True, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("lead")
        verbose_name_plural = _("leads")
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("listing", "created_at"))]

    def __str__(self):
        return f"{self.listing.reference} · {self.get_channel_display()}"

    @property
    def masked_phone(self):
        return mask_phone(self.phone)
