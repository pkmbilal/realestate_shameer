from django.urls import path

from . import views

urlpatterns = [
    path("", views.WalletView.as_view(), name="wallet"),
    path("transactions/", views.TransactionsView.as_view(), name="wallet-transactions"),
]
