import logging

import redis
from django.conf import settings
from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger(__name__)


def _check_database():
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")


def _check_redis():
    redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2).ping()


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """Used by Docker, Coolify and Uptime Kuma to see whether the API and its services are up."""
    checks = {}
    for name, check in (("database", _check_database), ("redis", _check_redis)):
        try:
            check()
            checks[name] = "ok"
        except Exception:
            logger.exception("Health check failed: %s", name)
            checks[name] = "error"

    healthy = all(value == "ok" for value in checks.values())
    return Response(
        {
            "status": "ok" if healthy else "error",
            "portal_name": settings.PORTAL_NAME,
            "checks": checks,
        },
        status=200 if healthy else 503,
    )
