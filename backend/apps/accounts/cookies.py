"""Puts JWTs in httpOnly cookies so JavaScript (and any XSS) can never read them."""

from django.conf import settings

# The refresh cookie is only sent to the auth endpoints, never to the rest of the API.
REFRESH_COOKIE_PATH = "/api/auth/"


def _options(path: str) -> dict:
    return {
        "httponly": True,
        "secure": settings.AUTH_COOKIE_SECURE,
        "samesite": "Lax",
        "domain": settings.AUTH_COOKIE_DOMAIN,
        "path": path,
    }


def _lifetime(name: str) -> int:
    return int(settings.SIMPLE_JWT[name].total_seconds())


def set_access_cookie(response, access: str) -> None:
    response.set_cookie(
        settings.AUTH_COOKIE_ACCESS,
        access,
        max_age=_lifetime("ACCESS_TOKEN_LIFETIME"),
        **_options("/"),
    )


def set_auth_cookies(response, access: str, refresh: str) -> None:
    set_access_cookie(response, access)
    response.set_cookie(
        settings.AUTH_COOKIE_REFRESH,
        refresh,
        max_age=_lifetime("REFRESH_TOKEN_LIFETIME"),
        **_options(REFRESH_COOKIE_PATH),
    )


def clear_auth_cookies(response) -> None:
    domain = settings.AUTH_COOKIE_DOMAIN
    response.delete_cookie(settings.AUTH_COOKIE_ACCESS, path="/", domain=domain)
    response.delete_cookie(settings.AUTH_COOKIE_REFRESH, path=REFRESH_COOKIE_PATH, domain=domain)
