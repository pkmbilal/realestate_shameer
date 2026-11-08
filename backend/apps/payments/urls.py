from django.urls import path

from . import views

urlpatterns = [
    path("packages/", views.PackagesView.as_view(), name="topup-packages"),
    path("top-ups/", views.TopUpsView.as_view(), name="topups"),
    path("top-ups/<int:pk>/", views.TopUpDetailView.as_view(), name="topup-detail"),
    path("webhook/", views.WebhookView.as_view(), name="payments-webhook"),
    path("mock-checkout/<str:ref>/", views.MockCheckoutView.as_view(), name="mock-checkout"),
]
