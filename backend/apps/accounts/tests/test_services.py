import re
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts import services
from apps.accounts.models import OtpCode, User

from .factories import UserFactory

pytestmark = pytest.mark.django_db

PHONE = "+966512345678"


@pytest.fixture
def sent(monkeypatch):
    """Capture SMS messages instead of logging them."""
    messages = []

    class FakeSms:
        def send(self, phone, text):
            messages.append((phone, text))

    monkeypatch.setattr(services, "get_sms_client", FakeSms)
    return messages


def last_code(sent):
    return re.search(r"\d{6}", sent[-1][1]).group()


def test_request_otp_sends_code_and_stores_only_a_hash(sent):
    services.request_otp("0512345678")

    assert sent[0][0] == PHONE
    code = last_code(sent)
    otp = OtpCode.objects.get()
    assert otp.phone == PHONE
    assert code not in otp.code_hash
    assert otp.expires_at - otp.created_at <= timedelta(seconds=301)


def test_request_otp_rejects_bad_phone(sent):
    with pytest.raises(ValidationError):
        services.request_otp("12")
    assert sent == []


def test_request_otp_cooldown(sent):
    services.request_otp(PHONE)
    with pytest.raises(services.OtpError) as exc:
        services.request_otp(PHONE)
    assert exc.value.code == "rate_limited"
    assert len(sent) == 1


def test_request_otp_hourly_limit(sent, settings):
    settings.OTP_RESEND_SECONDS = 0
    settings.OTP_MAX_PER_HOUR = 2
    services.request_otp(PHONE)
    services.request_otp(PHONE)
    with pytest.raises(services.OtpError) as exc:
        services.request_otp(PHONE)
    assert exc.value.retry_after == 3600


def test_verify_otp_creates_buyer_on_first_login(sent):
    services.request_otp(PHONE)

    user = services.verify_otp("0512345678", last_code(sent))

    assert user.phone == PHONE
    assert user.role == User.Role.BUYER
    assert not user.has_usable_password()
    assert user.last_login is not None


def test_verify_otp_logs_in_existing_user(sent):
    broker = UserFactory(phone=PHONE, role=User.Role.BROKER)
    services.request_otp(PHONE)

    assert services.verify_otp(PHONE, last_code(sent)) == broker
    assert User.objects.count() == 1


def test_code_cannot_be_reused(sent):
    services.request_otp(PHONE)
    code = last_code(sent)
    services.verify_otp(PHONE, code)

    with pytest.raises(services.OtpError) as exc:
        services.verify_otp(PHONE, code)
    assert exc.value.code == "invalid_code"


def test_wrong_code_counts_attempts(sent):
    services.request_otp(PHONE)
    code = last_code(sent)
    wrong = "000000" if code != "000000" else "111111"

    with pytest.raises(services.OtpError):
        services.verify_otp(PHONE, wrong)
    assert OtpCode.objects.get().attempts == 1


def test_too_many_attempts_blocks_even_the_right_code(sent, settings):
    settings.OTP_MAX_ATTEMPTS = 2
    services.request_otp(PHONE)
    code = last_code(sent)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(2):
        with pytest.raises(services.OtpError):
            services.verify_otp(PHONE, wrong)

    with pytest.raises(services.OtpError) as exc:
        services.verify_otp(PHONE, code)
    assert exc.value.code == "too_many_attempts"


def test_expired_code_is_rejected(sent):
    services.request_otp(PHONE)
    OtpCode.objects.update(expires_at=timezone.now() - timedelta(seconds=1))

    with pytest.raises(services.OtpError) as exc:
        services.verify_otp(PHONE, last_code(sent))
    assert exc.value.code == "invalid_code"


def test_new_code_replaces_old_one(sent, settings):
    settings.OTP_RESEND_SECONDS = 0
    services.request_otp(PHONE)
    old_code = last_code(sent)
    services.request_otp(PHONE)
    new_code = last_code(sent)

    if old_code != new_code:
        with pytest.raises(services.OtpError):
            services.verify_otp(PHONE, old_code)
    assert services.verify_otp(PHONE, new_code).phone == PHONE


def test_disabled_account_cannot_log_in(sent):
    UserFactory(phone=PHONE, is_active=False)
    services.request_otp(PHONE)

    with pytest.raises(services.OtpError) as exc:
        services.verify_otp(PHONE, last_code(sent))
    assert exc.value.code == "account_disabled"
