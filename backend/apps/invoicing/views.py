from django.http import Http404, HttpResponse
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView

from apps.accounts.permissions import IsVerifiedAdvertiser

from . import services
from .serializers import InvoiceSerializer


class InvoicePagination(PageNumberPagination):
    page_size = 20


class InvoicesView(ListAPIView):
    """GET: my e-invoices, newest first."""

    permission_classes = [IsVerifiedAdvertiser]
    serializer_class = InvoiceSerializer
    pagination_class = InvoicePagination

    def get_queryset(self):
        return services.invoices_for_user(self.request.user)


class InvoicePdfView(APIView):
    """GET: download one of my invoices as a PDF."""

    permission_classes = [IsVerifiedAdvertiser]

    def get(self, request, pk):
        invoice = services.invoices_for_user(request.user).filter(pk=pk).first()
        if invoice is None:
            raise Http404
        response = HttpResponse(services.render_pdf(invoice), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{invoice.number}.pdf"'
        response["Cache-Control"] = "private, no-store"
        return response
