import pytest
from django.core.exceptions import ValidationError

from apps.accounts.phone import mask_phone, normalize_phone


@pytest.mark.parametrize(
    "raw",
    ["0512345678", "512345678", "966512345678", "+966512345678", "00966512345678", "051 234 5678"],
)
def test_normalize_saudi_formats(raw):
    assert normalize_phone(raw) == "+966512345678"


def test_normalize_keeps_foreign_e164():
    assert normalize_phone("+971501234567") == "+971501234567"


@pytest.mark.parametrize("raw", ["", "abc", "12", "+0123456789"])
def test_normalize_rejects_invalid(raw):
    with pytest.raises(ValidationError):
        normalize_phone(raw)


def test_mask_phone_hides_middle_digits():
    assert mask_phone("+966512345678") == "+9665•••••678"


def test_mask_phone_handles_empty():
    assert mask_phone("") == ""
