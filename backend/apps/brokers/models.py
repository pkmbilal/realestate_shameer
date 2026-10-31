"""Broker and agency profiles. Only Nafath-verified users can create them."""

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.phone import mask_phone

# Commercial Registration number: 10 digits.
cr_number_validator = RegexValidator(r"^\d{10}$", _("Enter the 10-digit CR number."))
# FAL licence numbers issued by REGA are numeric; the exact length is not fixed yet.
fal_licence_validator = RegexValidator(
    r"^\d{4,20}$", _("Enter the FAL licence number (digits only).")
)


class Agency(models.Model):
    """A brokerage office. Its admin adds brokers as members."""

    admin = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="agency",
        verbose_name=_("agency admin"),
    )
    name_ar = models.CharField(_("name (Arabic)"), max_length=150)
    name_en = models.CharField(_("name (English)"), max_length=150)
    # Plain URL for now; direct S3 uploads arrive with listing photos.
    logo_url = models.URLField(_("logo URL"), blank=True)
    cr_number = models.CharField(
        _("CR number"), max_length=10, unique=True, validators=[cr_number_validator]
    )
    fal_licence = models.CharField(
        _("FAL licence"), max_length=20, unique=True, validators=[fal_licence_validator]
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("agency")
        verbose_name_plural = _("agencies")
        ordering = ("name_en",)

    def __str__(self):
        return f"{self.name_en} / {self.name_ar}"


class BrokerProfile(models.Model):
    """The public face of a broker: shown on their listings and profile page."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="broker_profile",
        verbose_name=_("user"),
    )
    name_ar = models.CharField(_("name (Arabic)"), max_length=150)
    name_en = models.CharField(_("name (English)"), max_length=150)
    photo_url = models.URLField(_("photo URL"), blank=True)
    fal_licence = models.CharField(
        _("FAL licence"), max_length=20, unique=True, validators=[fal_licence_validator]
    )
    # Set by the agency admin, never by the broker.
    agency = models.ForeignKey(
        Agency,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members",
        verbose_name=_("agency"),
    )
    # E.164, e.g. +966512345678. Used for lead notifications and the WhatsApp button.
    whatsapp = models.CharField(_("WhatsApp number"), max_length=16)
    cities_served = models.ManyToManyField(
        "locations.City", blank=True, related_name="brokers", verbose_name=_("cities served")
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("broker profile")
        verbose_name_plural = _("broker profiles")
        ordering = ("name_en",)

    def __str__(self):
        return f"{self.name_en} / {self.name_ar}"

    @property
    def masked_whatsapp(self):
        return mask_phone(self.whatsapp)
