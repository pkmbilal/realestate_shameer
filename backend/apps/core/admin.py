from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _

from . import services
from .models import IntegrationError


class ResolvedFilter(admin.SimpleListFilter):
    title = _("resolved")
    parameter_name = "resolved"

    def lookups(self, request, model_admin):
        return (("no", _("Open")), ("yes", _("Resolved")))

    def queryset(self, request, queryset):
        if self.value() == "no":
            return queryset.filter(resolved_at__isnull=True)
        if self.value() == "yes":
            return queryset.filter(resolved_at__isnull=False)
        return queryset


@admin.action(description=_("Mark resolved"), permissions=["change"])
def mark_resolved(modeladmin, request, queryset):
    done = services.resolve_errors(queryset, request.user)
    modeladmin.message_user(request, _("Resolved: %d") % done, level=messages.SUCCESS)


@admin.register(IntegrationError)
class IntegrationErrorAdmin(admin.ModelAdmin):
    """Failures talking to REGA, Nafath, SMS, ZATCA, payments and WhatsApp. Read-only."""

    list_display = (
        "created_at",
        "integration",
        "operation",
        "error_code",
        "reference",
        "message",
        "resolved_at",
    )
    list_filter = ("integration", ResolvedFilter, "operation")
    search_fields = ("reference", "error_code", "message")
    date_hierarchy = "created_at"
    readonly_fields = (
        "created_at",
        "integration",
        "operation",
        "error_code",
        "reference",
        "message",
        "resolved_at",
        "resolved_by",
    )
    fields = readonly_fields
    actions = (mark_resolved,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
