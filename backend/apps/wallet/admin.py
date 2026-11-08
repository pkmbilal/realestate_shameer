"""Wallet admin. Balances are never typed in: staff grant or adjust credits through actions
that add a ledger row via services.py. The ledger itself is read-only."""

from django import forms
from django.contrib import admin, messages
from django.template.response import TemplateResponse
from django.utils.translation import gettext_lazy as _

from . import services
from .models import CreditPrice, CreditTransaction, Wallet


class GrantForm(forms.Form):
    credits = forms.IntegerField(label=_("Credits to add"), min_value=1)
    note = forms.CharField(label=_("Note"), max_length=500, initial=_("Launch promotion"))


class AdjustForm(forms.Form):
    amount = forms.IntegerField(
        label=_("Amount"), help_text=_("Positive adds credits, negative removes them.")
    )
    note = forms.CharField(label=_("Reason"), max_length=500, widget=forms.Textarea)

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount == 0:
            raise forms.ValidationError(_("Enter an amount other than 0."))
        return amount


class TransactionInline(admin.TabularInline):
    model = CreditTransaction
    fk_name = "wallet"
    fields = ("created_at", "kind", "action", "amount", "balance_after", "listing", "note")
    readonly_fields = fields
    extra = 0
    max_num = 0
    can_delete = False
    show_change_link = True
    ordering = ("-created_at", "-id")

    def has_add_permission(self, request, obj=None):
        return False


def _amount_action(modeladmin, request, queryset, form_class, apply, title, action_name):
    """Ask for an amount and note on an intermediate page, then apply it to each wallet."""
    form = form_class(request.POST if "apply" in request.POST else None)
    if "apply" in request.POST and form.is_valid():
        done = 0
        for wallet in queryset:
            try:
                apply(wallet, request.user, form.cleaned_data)
                done += 1
            except services.WalletError as exc:
                modeladmin.message_user(request, f"{wallet}: {exc.code}", level=messages.ERROR)
        if done:
            modeladmin.message_user(request, f"{title}: {done}", level=messages.SUCCESS)
        return None
    return TemplateResponse(
        request,
        "admin/wallet/amount_form.html",
        {
            **modeladmin.admin_site.each_context(request),
            "title": title,
            "form": form,
            "wallets": queryset,
            "action_name": action_name,
            "opts": modeladmin.model._meta,
            "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
        },
    )


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("id", "holder_name", "broker", "agency", "balance", "updated_at")
    search_fields = ("broker__name_en", "broker__name_ar", "agency__name_en", "agency__name_ar")
    autocomplete_fields = ("broker", "agency")
    inlines = (TransactionInline,)
    actions = ("grant_credits", "adjust_balance", "check_balance")

    def get_readonly_fields(self, request, obj=None):
        # A new wallet only picks its holder; the balance comes from the ledger.
        if obj is None:
            return ("balance",)
        return ("broker", "agency", "balance", "created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description=_("Grant free credits"))
    def grant_credits(self, request, queryset):
        return _amount_action(
            self,
            request,
            queryset,
            GrantForm,
            lambda w, by, d: services.grant(w, d["credits"], by, d["note"]),
            _("Grant free credits"),
            "grant_credits",
        )

    @admin.action(description=_("Adjust balance (correction)"))
    def adjust_balance(self, request, queryset):
        return _amount_action(
            self,
            request,
            queryset,
            AdjustForm,
            lambda w, by, d: services.adjust(w, d["amount"], by, d["note"]),
            _("Adjust balance"),
            "adjust_balance",
        )

    @admin.action(description=_("Check balance against the ledger"))
    def check_balance(self, request, queryset):
        bad = [str(w) for w in queryset if not services.balance_matches_ledger(w)]
        if bad:
            self.message_user(request, f"Mismatch: {', '.join(bad)}", level=messages.ERROR)
        else:
            self.message_user(request, _("All balances match the ledger."), messages.SUCCESS)


@admin.register(CreditTransaction)
class CreditTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "wallet",
        "kind",
        "action",
        "amount",
        "balance_after",
        "listing",
        "created_by",
    )
    list_filter = ("kind", "action", "created_at")
    search_fields = ("listing__reference", "note")
    list_select_related = ("wallet__broker", "wallet__agency", "listing", "created_by")
    date_hierarchy = "created_at"

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CreditPrice)
class CreditPriceAdmin(admin.ModelAdmin):
    list_display = ("action", "credits", "days", "updated_at")
    list_editable = ("credits", "days")

    def has_delete_permission(self, request, obj=None):
        return False
