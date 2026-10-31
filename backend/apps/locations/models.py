"""Cities and districts. Names are bilingual; slugs are used in SEO area-page URLs."""

from django.contrib.gis.db import models
from django.utils.translation import gettext_lazy as _


class City(models.Model):
    class Region(models.TextChoices):
        EASTERN = "eastern", _("Eastern Province")

    name_ar = models.CharField(_("name (Arabic)"), max_length=100)
    name_en = models.CharField(_("name (English)"), max_length=100)
    # Used in URLs: /en/rent/apartments/dammam/… and /ar/للإيجار/شقق/الدمام/…
    slug_en = models.SlugField(_("slug (English)"), max_length=100, unique=True)
    slug_ar = models.SlugField(_("slug (Arabic)"), max_length=100, unique=True, allow_unicode=True)
    region = models.CharField(_("region"), max_length=20, choices=Region.choices)
    center = models.PointField(_("centre point"), srid=4326, null=True, blank=True)
    is_active = models.BooleanField(_("active"), default=True)
    sort_order = models.PositiveSmallIntegerField(_("sort order"), default=0)

    class Meta:
        verbose_name = _("city")
        verbose_name_plural = _("cities")
        ordering = ("sort_order", "name_en")

    def __str__(self):
        return f"{self.name_en} / {self.name_ar}"


class District(models.Model):
    city = models.ForeignKey(
        City, on_delete=models.PROTECT, related_name="districts", verbose_name=_("city")
    )
    name_ar = models.CharField(_("name (Arabic)"), max_length=100)
    name_en = models.CharField(_("name (English)"), max_length=100)
    slug_en = models.SlugField(_("slug (English)"), max_length=100)
    slug_ar = models.SlugField(_("slug (Arabic)"), max_length=100, allow_unicode=True)
    center = models.PointField(_("centre point"), srid=4326, null=True, blank=True)
    # Exact district shape, for later (map search by district). Empty for now.
    boundary = models.MultiPolygonField(_("boundary"), srid=4326, null=True, blank=True)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("district")
        verbose_name_plural = _("districts")
        ordering = ("city", "name_en")
        constraints = [
            models.UniqueConstraint(fields=["city", "slug_en"], name="district_unique_slug_en"),
            models.UniqueConstraint(fields=["city", "slug_ar"], name="district_unique_slug_ar"),
        ]

    def __str__(self):
        return f"{self.name_en} / {self.name_ar} ({self.city.name_en})"
