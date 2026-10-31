from unittest import mock

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_health_ok(settings):
    settings.PORTAL_NAME = "Test Portal"
    with mock.patch("apps.core.views._check_redis"):
        response = APIClient().get(reverse("health"))

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "portal_name": "Test Portal",
        "checks": {"database": "ok", "redis": "ok"},
    }


def test_health_reports_failed_service():
    with mock.patch("apps.core.views._check_redis", side_effect=ConnectionError):
        response = APIClient().get(reverse("health"))

    assert response.status_code == 503
    assert response.json()["status"] == "error"
    assert response.json()["checks"]["redis"] == "error"
