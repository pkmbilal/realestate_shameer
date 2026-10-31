from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class CookieJWTAuthentication(JWTAuthentication):
    """Reads the JWT from the Authorization header, or else from the httpOnly access cookie.

    An expired or broken cookie counts as "not logged in" rather than an error, so public
    pages keep working; protected endpoints still answer 401 and the frontend refreshes.
    """

    def authenticate(self, request):
        if self.get_header(request) is not None:
            return super().authenticate(request)

        raw_token = request.COOKIES.get(settings.AUTH_COOKIE_ACCESS)
        if not raw_token:
            return None
        try:
            validated = self.get_validated_token(raw_token)
            return self.get_user(validated), validated
        except (InvalidToken, TokenError):
            return None
