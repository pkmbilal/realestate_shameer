from django.urls import path

from . import views

urlpatterns = [
    path("", views.InvoicesView.as_view(), name="invoices"),
    path("<int:pk>/pdf/", views.InvoicePdfView.as_view(), name="invoice-pdf"),
]
