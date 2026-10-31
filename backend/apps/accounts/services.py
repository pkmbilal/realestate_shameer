"""Phone OTP login: request a code by SMS, then exchange it for a logged-in user."""

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import update_last_login
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from integrations.sms import get_sms_client

from .models import OtpCode, User
from .phone import normalize_phone


class OtpError(Exception):
    """A login problem the user can see. `code` is a stable key the frontend translates."""

    def __init__(self, code: str, retry_after: int | None = None):
        super().__init__(code)
        self.code = code
        self.retry_after = retry_after


def _cache_key(kind: str, phone: str) -> str:
    # Hash the phone so raw numbers never appear in Redis keys.
    return f"otp:{kind}:{hashlib.sha256(phone.encode()).hexdigest()}"


def _check_rate_limit(phone: str) -> None:
    """At most one code per OTP_RESEND_SECONDS and OTP_MAX_PER_HOUR codes per hour, per phone."""
    if not cache.add(_cache_key("cooldown", phone), 1, timeout=settings.OTP_RESEND_SECONDS):
        raise OtpError("rate_limited", retry_after=settings.OTP_RESEND_SECONDS)

    hour_key = _cache_key("hour", phone)
    cache.add(hour_key, 0, timeout=3600)
    if cache.incr(hour_key) > settings.OTP_MAX_PER_HOUR:
        raise OtpError("rate_limited", retry_after=3600)


def request_otp(raw_phone: str) -> None:
    """Send a fresh 6-digit login code to the phone. Raises ValidationError or OtpError."""
    phone = normalize_phone(raw_phone)
    _check_rate_limit(phone)

    code = f"{secrets.randbelow(1_000_000):06d}"
    now = timezone.now()
    with transaction.atomic():
        # Only the newest code works.
        OtpCode.objects.filter(phone=phone, used_at__isnull=True, expires_at__gt=now).update(
            expires_at=now
        )
        OtpCode.objects.create(
            phone=phone,
            code_hash=make_password(code),
            expires_at=now + timedelta(seconds=settings.OTP_TTL_SECONDS),
        )

    text = _("%(portal)s login code: %(code)s") % {"portal": settings.PORTAL_NAME, "code": code}
    get_sms_client().send(phone, text)


def verify_otp(raw_phone: str, code: str) -> User:
    """Check the code and return the user, creating a buyer account on first login."""
    phone = normalize_phone(raw_phone)
    now = timezone.now()

    # Decide inside the transaction but raise after it, so the attempt counter is saved.
    with transaction.atomic():
        otp = (
            OtpCode.objects.select_for_update()
            .filter(phone=phone, used_at__isnull=True, expires_at__gt=now)
            .order_by("-created_at")
            .first()
        )
        if otp is None:
            error = "invalid_code"
        elif otp.attempts >= settings.OTP_MAX_ATTEMPTS:
            error = "too_many_attempts"
        else:
            otp.attempts += 1
            error = None if check_password(code, otp.code_hash) else "invalid_code"
            if error is None:
                otp.used_at = now
            otp.save(update_fields=["attempts", "used_at"])
    if error:
        raise OtpError(error)

    user = User.objects.filter(phone=phone).first() or User.objects.create_user(phone)
    if not user.is_active:
        raise OtpError("account_disabled")
    update_last_login(None, user)
    return user
