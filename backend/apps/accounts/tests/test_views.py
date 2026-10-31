import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from .factories import UserFactory

pytestmark = pytest.mark.django_db


def test_me_requires_authentication():
    response = APIClient().get(reverse("accounts-me"))
    assert response.status_code == 401


def test_me_returns_masked_phone():
    user = UserFactory(phone="+966512345678", role="broker")
    client = APIClient()
    client.force_authenticate(user)

    response = client.get(reverse("accounts-me"))

    assert response.status_code == 200
    assert response.json()["masked_phone"] == "+9665•••••678"
    assert response.json()["role"] == "broker"
    assert "phone" not in response.json()
