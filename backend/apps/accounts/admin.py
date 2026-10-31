from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .forms import UserChangeForm, UserCreationForm
from .models import OtpCode, User


@admin.register(OtpCode)
class OtpCodeAdmin(admin.ModelAdmin):
    """Read-only, for support questions ("I never got my code"). The code hash is never shown."""

    list_display = ("masked_phone", "created_at", "expires_at", "attempts", "used_at")
    fields = ("masked_phone", "created_at", "expires_at", "attempts", "used_at")
    readonly_fields = fields
    search_fields = ("phone",)
    ordering = ("-created_at",)

    @admin.display(description=_("phone"))
    def masked_phone(self, obj):
        return obj.masked_phone

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    # Phone numbers are masked in lists (PDPL); the full number is only on the detail page.
    list_display = ("masked_phone", "role", "is_active", "is_staff", "date_joined")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("phone",)
    ordering = ("-date_joined",)
    readonly_fields = ("date_joined", "last_login")

    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        (_("Role"), {"fields": ("role",)}),
        (
            _("Permissions"),
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        (_("Dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("phone", "role", "password1", "password2")}),
    )

    @admin.display(description=_("phone"), ordering="phone")
    def masked_phone(self, obj):
        return obj.masked_phone
