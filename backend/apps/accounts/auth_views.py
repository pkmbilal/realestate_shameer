"""Login endpoints: phone OTP -> JWT in httpOnly cookies. The logic lives in services.py."""

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from . import services
from .cookies import clear_auth_cookies, set_access_cookie, set_auth_cookies
from .serializers import MeSerializer, OtpRequestSerializer, OtpVerifySerializer


def _error(code: str, http_status: int, **extra) -> Response:
    """Errors carry a stable `code` that the frontend translates."""
    return Response({"code": code, **extra}, status=http_status)


class PublicAuthView(APIView):
    # For people who are not logged in, or whose access token has expired.
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]


class OtpRequestView(PublicAuthView):
    throttle_scope = "otp_request"

    def post(self, request):
        serializer = OtpRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return _error("invalid_phone", status.HTTP_400_BAD_REQUEST)
        try:
            services.request_otp(serializer.validated_data["phone"])
        except ValidationError:
            return _error("invalid_phone", status.HTTP_400_BAD_REQUEST)
        except services.OtpError as exc:
            return _error(exc.code, status.HTTP_429_TOO_MANY_REQUESTS, retry_after=exc.retry_after)
        return Response(
            {"resend_after": settings.OTP_RESEND_SECONDS}, status=status.HTTP_202_ACCEPTED
        )


class OtpVerifyView(PublicAuthView):
    throttle_scope = "otp_verify"

    def post(self, request):
        serializer = OtpVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return _error("invalid_code", status.HTTP_400_BAD_REQUEST)
        try:
            user = services.verify_otp(
                serializer.validated_data["phone"], serializer.validated_data["code"]
            )
        except ValidationError:
            return _error("invalid_phone", status.HTTP_400_BAD_REQUEST)
        except services.OtpError as exc:
            return _error(exc.code, status.HTTP_400_BAD_REQUEST)

        refresh = RefreshToken.for_user(user)
        response = Response(MeSerializer(user).data)
        set_auth_cookies(response, str(refresh.access_token), str(refresh))
        return response


class RefreshView(PublicAuthView):
    throttle_scope = "auth_session"

    def post(self, request):
        serializer = TokenRefreshSerializer(
            data={"refresh": request.COOKIES.get(settings.AUTH_COOKIE_REFRESH, "")}
        )
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            response = _error("not_authenticated", status.HTTP_401_UNAUTHORIZED)
            clear_auth_cookies(response)
            return response

        tokens = serializer.validated_data
        response = Response(status=status.HTTP_204_NO_CONTENT)
        if "refresh" in tokens:  # only when ROTATE_REFRESH_TOKENS is switched on
            set_auth_cookies(response, tokens["access"], tokens["refresh"])
        else:
            set_access_cookie(response, tokens["access"])
        return response


class LogoutView(PublicAuthView):
    throttle_scope = "auth_session"

    def post(self, request):
        raw_refresh = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)
        if raw_refresh:
            try:
                RefreshToken(raw_refresh).blacklist()
            except TokenError:
                pass  # already invalid or expired: nothing to revoke
        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_auth_cookies(response)
        return response
