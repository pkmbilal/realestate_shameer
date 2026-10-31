import re

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts import services

pytestmark = pytest.mark.django_db

PHONE = "+966512345678"


@pytest.fixture
def sent(monkeypatch):
    messages = []

    class FakeSms:
        def send(self, phone, text):
            messages.append(text)

    monkeypatch.setattr(services, "get_sms_client", FakeSms)
    return messages


def log_in(client, sent):
    client.post(reverse("auth-otp-request"), {"phone": "0512345678"}, format="json")
    code = re.search(r"\d{6}", sent[-1]).group()
    return client.post(reverse("auth-otp-verify"), {"phone": PHONE, "code": code}, format="json")


def test_request_returns_202(sent):
    response = APIClient().post(reverse("auth-otp-request"), {"phone": PHONE}, format="json")
    assert response.status_code == 202
    assert response.json()["resend_after"] == 60


def test_request_bad_phone(sent):
    response = APIClient().post(reverse("auth-otp-request"), {"phone": "abc"}, format="json")
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_phone"


def test_request_rate_limited(sent):
    client = APIClient()
    client.post(reverse("auth-otp-request"), {"phone": PHONE}, format="json")
    response = client.post(reverse("auth-otp-request"), {"phone": PHONE}, format="json")
    assert response.status_code == 429
    assert response.json()["code"] == "rate_limited"


def test_verify_sets_httponly_cookies_and_me_works(sent):
    client = APIClient()
    response = log_in(client, sent)

    assert response.status_code == 200
    assert response.json()["masked_phone"] == "+9665•••••678"
    access = response.cookies["access_token"]
    refresh = response.cookies["refresh_token"]
    assert access["httponly"] and refresh["httponly"]
    assert access["samesite"] == "Lax"
    assert refresh["path"] == "/api/auth/"

    me = client.get(reverse("accounts-me"))
    assert me.status_code == 200
    assert me.json()["masked_phone"] == "+9665•••••678"


def test_verify_wrong_code(sent):
    client = APIClient()
    client.post(reverse("auth-otp-request"), {"phone": PHONE}, format="json")
    code = re.search(r"\d{6}", sent[-1]).group()
    wrong = "000000" if code != "000000" else "111111"

    response = client.post(
        reverse("auth-otp-verify"), {"phone": PHONE, "code": wrong}, format="json"
    )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_code"
    assert "access_token" not in response.cookies


def test_bad_access_cookie_is_treated_as_logged_out(sent):
    client = APIClient()
    client.cookies["access_token"] = "garbage"

    assert client.get(reverse("health")).status_code in (200, 503)
    assert client.get(reverse("accounts-me")).status_code == 401


def test_refresh_issues_new_access_cookie(sent):
    client = APIClient()
    log_in(client, sent)
    del client.cookies["access_token"]

    response = client.post(reverse("auth-refresh"))

    assert response.status_code == 204
    assert response.cookies["access_token"].value
    assert client.get(reverse("accounts-me")).status_code == 200


def test_refresh_without_cookie_is_401(sent):
    assert APIClient().post(reverse("auth-refresh")).status_code == 401


def test_logout_clears_cookies_and_revokes_refresh(sent):
    client = APIClient()
    log_in(client, sent)
    old_refresh = client.cookies["refresh_token"].value

    response = client.post(reverse("auth-logout"))

    assert response.status_code == 204
    assert response.cookies["access_token"].value == ""
    assert client.get(reverse("accounts-me")).status_code == 401

    client.cookies["refresh_token"] = old_refresh
    assert client.post(reverse("auth-refresh")).status_code == 401
