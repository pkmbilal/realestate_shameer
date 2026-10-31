from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Agency, BrokerProfile


class MemberInline(admin.TabularInline):
    model = BrokerProfile
    fields = ("name_en", "name_ar", "fal_licence")
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Agency)
class AgencyAdmin(admin.ModelAdmin):
    list_display = ("name_en", "name_ar", "cr_number", "fal_licence", "admin", "created_at")
    search_fields = ("name_en", "name_ar", "cr_number", "fal_licence")
    raw_id_fields = ("admin",)
    inlines = (MemberInline,)


@admin.register(BrokerProfile)
class BrokerProfileAdmin(admin.ModelAdmin):
    # The WhatsApp number is masked in the list (PDPL); the full number is on the detail page.
    list_display = ("name_en", "name_ar", "fal_licence", "agency", "masked_whatsapp", "created_at")
    list_filter = ("agency", "cities_served")
    list_select_related = ("agency", "user")
    search_fields = ("name_en", "name_ar", "fal_licence")
    raw_id_fields = ("user",)
    filter_horizontal = ("cities_served",)

    @admin.display(description=_("WhatsApp"))
    def masked_whatsapp(self, obj):
        return obj.masked_whatsapp
