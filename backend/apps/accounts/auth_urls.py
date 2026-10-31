from django.urls import path

from .auth_views import LogoutView, OtpRequestView, OtpVerifyView, RefreshView

urlpatterns = [
    path("otp/request/", OtpRequestView.as_view(), name="auth-otp-request"),
    path("otp/verify/", OtpVerifyView.as_view(), name="auth-otp-verify"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
]
