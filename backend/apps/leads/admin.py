"""Lead log in admin. Read-only: leads are a record of what happened, never edited."""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "listing_reference",
        "channel",
        "broker",
        "agency",
        "name",
        "masked_phone",
        "notify_status",
    )
    list_filter = ("channel", "notify_status", "created_at")
    search_fields = ("listing__reference",)
    list_select_related = ("listing", "broker", "agency")
    date_hierarchy = "created_at"
    # The raw phone and fingerprint are never shown (PDPL).
    fields = (
        "created_at",
        "listing",
        "channel",
        "broker",
        "agency",
        "user",
        "name",
        "masked_phone",
        "message",
        "notify_status",
        "notified_at",
    )
    readonly_fields = fields

    @admin.display(description=_("listing"), ordering="listing__reference")
    def listing_reference(self, obj):
        return obj.listing.reference

    @admin.display(description=_("phone"))
    def masked_phone(self, obj):
        return obj.masked_phone or "-"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
