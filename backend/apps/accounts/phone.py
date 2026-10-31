"""Phone number helpers. Phones are stored in E.164 format, e.g. +966512345678."""

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")


def normalize_phone(raw: str) -> str:
    """Return the phone in E.164 format. Saudi local formats (05…, 5…, 9665…) become +9665…."""
    phone = re.sub(r"[\s\-()]", "", raw or "")
    if phone.startswith("00"):
        phone = "+" + phone[2:]
    elif phone.startswith("05") and len(phone) == 10:
        phone = "+966" + phone[1:]
    elif phone.startswith("5") and len(phone) == 9:
        phone = "+966" + phone
    elif phone.startswith("966"):
        phone = "+" + phone

    if not E164_RE.match(phone):
        raise ValidationError(_("Enter a valid phone number."), code="invalid_phone")
    return phone


def mask_phone(phone: str) -> str:
    """Hide the middle digits for display in admin lists and logs: +966512345678 → +9665•••••678."""
    if not phone or len(phone) < 8:
        return "•" * len(phone or "")
    return phone[:5] + "•" * (len(phone) - 8) + phone[-3:]
