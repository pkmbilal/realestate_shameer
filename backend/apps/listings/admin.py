"""Listing admin: the moderation queue, approve / reject / take down with a reason.

Status is never edited directly here; every change goes through services.py so it is logged.
"""

from django import forms
from django.contrib import admin, messages
from django.template.response import TemplateResponse
from django.utils.translation import gettext_lazy as _

from . import services
from .models import Amenity, Listing, ListingPhoto, ListingStatusChange, PendingListing


class ReasonForm(forms.Form):
    reason = forms.CharField(label=_("Reason"), max_length=500, widget=forms.Textarea)


class StatusChangeInline(admin.TabularInline):
    model = ListingStatusChange
    fields = ("created_at", "from_status", "to_status", "changed_by", "reason")
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class PhotoInline(admin.TabularInline):
    model = ListingPhoto
    fields = ("position", "key", "size_bytes")
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


def _run(modeladmin, request, queryset, action, label, **kwargs):
    done = 0
    for listing in queryset:
        try:
            action(listing, request.user, **kwargs)
            done += 1
        except services.ListingError as exc:
            modeladmin.message_user(
                request, f"{listing.reference}: {exc.code}", level=messages.ERROR
            )
    if done:
        modeladmin.message_user(request, f"{label}: {done}", level=messages.SUCCESS)


def _with_reason(modeladmin, request, queryset, action, label, action_name):
    """Ask for a reason on an intermediate page, then apply the action to each listing."""
    form = ReasonForm(request.POST if "apply" in request.POST else None)
    if "apply" in request.POST and form.is_valid():
        _run(modeladmin, request, queryset, action, label, reason=form.cleaned_data["reason"])
        return None
    return TemplateResponse(
        request,
        "admin/listings/reason_form.html",
        {
            **modeladmin.admin_site.each_context(request),
            "title": label,
            "form": form,
            "listings": queryset,
            "action_name": action_name,
            "opts": modeladmin.model._meta,
            "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
        },
    )


@admin.action(description=_("Approve and publish"))
def approve_listings(modeladmin, request, queryset):
    _run(modeladmin, request, queryset, services.approve, _("Approved"))


@admin.action(description=_("Reject (send back to advertiser)…"))
def reject_listings(modeladmin, request, queryset):
    return _with_reason(
        modeladmin, request, queryset, services.reject, _("Rejected"), "reject_listings"
    )


@admin.action(description=_("Take down…"))
def take_down_listings(modeladmin, request, queryset):
    return _with_reason(
        modeladmin, request, queryset, services.take_down, _("Taken down"), "take_down_listings"
    )


READONLY = (
    "reference",
    "status",
    "moderation_note",
    "created_by",
    "broker",
    "agency",
    "licence_number",
    "licence_expires_on",
    "purpose",
    "property_type",
    "city",
    "district",
    "area_m2",
    "location",
    "rega_data",
    "rega_synced_at",
    "price_halalas",
    "rent_period",
    "bedrooms",
    "bathrooms",
    "furnishing",
    "completion",
    "title_ar",
    "title_en",
    "description_ar",
    "description_en",
    "amenities",
    "published_at",
    "post_expires_at",
    "refreshed_at",
    "featured_until",
    "view_count",
    "created_at",
    "updated_at",
)


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    """All listings, read-only. Use the actions to change status (each change is logged)."""

    list_display = (
        "reference",
        "status",
        "purpose",
        "property_type",
        "city",
        "district",
        "price_halalas",
        "licence_number",
        "licence_expires_on",
        "broker",
        "view_count",
        "created_at",
    )
    list_filter = ("status", "purpose", "property_type", "city")
    list_select_related = ("city", "district", "broker")
    search_fields = ("reference", "licence_number", "title_ar", "title_en")
    readonly_fields = READONLY
    fields = READONLY
    inlines = (PhotoInline, StatusChangeInline)
    actions = (approve_listings, reject_listings, take_down_listings)
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False  # Listings start from a REGA licence in the broker dashboard.

    def has_delete_permission(self, request, obj=None):
        return False  # Use "Take down" so there is a logged reason.


@admin.register(PendingListing)
class ModerationQueueAdmin(ListingAdmin):
    """Listings waiting for review, oldest first."""

    list_filter = ("purpose", "property_type", "city")
    actions = (approve_listings, reject_listings, take_down_listings)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(status=Listing.Status.PENDING_REVIEW)
            .order_by("updated_at")
        )


@admin.register(ListingStatusChange)
class ListingStatusChangeAdmin(admin.ModelAdmin):
    """Takedown and moderation log. Read-only."""

    list_display = ("created_at", "listing", "from_status", "to_status", "changed_by", "reason")
    list_filter = ("to_status",)
    list_select_related = ("listing", "changed_by")
    search_fields = ("listing__reference", "reason")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ("name_en", "name_ar", "slug", "sort_order")
    list_editable = ("sort_order",)
    prepopulated_fields = {"slug": ("name_en",)}
