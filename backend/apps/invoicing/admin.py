"""Invoices are a legal record: read-only in the admin, with a PDF download link."""

from django.contrib import admin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from . import services
from .models import Invoice


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "issued_at", "buyer_name", "total_halalas", "zatca_status", "pdf")
    list_filter = ("zatca_status",)
    search_fields = ("number", "buyer_name")
    readonly_fields = [f.name for f in Invoice._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description=_("PDF"))
    def pdf(self, obj):
        url = reverse("admin:invoicing_invoice_pdf", args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, _("Download"))

    def get_urls(self):
        extra = [
            path(
                "<int:pk>/pdf/",
                self.admin_site.admin_view(self.pdf_view),
                name="invoicing_invoice_pdf",
            )
        ]
        return extra + super().get_urls()

    def pdf_view(self, request, pk):
        if not self.has_view_permission(request):
            return HttpResponse(status=403)
        invoice = get_object_or_404(Invoice, pk=pk)
        response = HttpResponse(services.render_pdf(invoice), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{invoice.number}.pdf"'
        return response
