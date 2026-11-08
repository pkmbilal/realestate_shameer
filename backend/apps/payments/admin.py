"""Payments admin. Packages are editable; payments are a read-only record."""

from django.contrib import admin

from .models import Payment, TopUpPackage


@admin.register(TopUpPackage)
class TopUpPackageAdmin(admin.ModelAdmin):
    list_display = ("name_en", "name_ar", "credits", "price_halalas", "is_active", "sort_order")
    list_editable = ("is_active", "sort_order")
    list_filter = ("is_active",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "wallet",
        "credits",
        "amount_halalas",
        "status",
        "gateway_ref",
        "created_at",
        "paid_at",
    )
    list_filter = ("status", "gateway")
    search_fields = ("gateway_ref", "wallet__broker__name_en", "wallet__agency__name_en")
    readonly_fields = [f.name for f in Payment._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False
