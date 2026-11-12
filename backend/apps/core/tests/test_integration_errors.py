from unittest.mock import patch

import pytest

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory
from apps.core.models import IntegrationError
from apps.core.services import clean_message, record_integration_error, resolve_errors
from integrations.rega import RegaError

pytestmark = pytest.mark.django_db


def test_clean_message_masks_phones_and_ids():
    text = "failed for +966512345678 and id 1012345678, ref AB12CD34, code 42"
    cleaned = clean_message(text)
    assert "966512345678" not in cleaned
    assert "1012345678" not in cleaned
    assert "AB12CD34" in cleaned and "42" in cleaned
    assert len(clean_message("x" * 2000)) == 500


def test_records_code_from_exception():
    row = record_integration_error("rega", "fetch_ad_licence", RegaError("unavailable"))
    assert row.error_code == "unavailable"
    row = record_integration_error("sms", "send_otp", TimeoutError("timed out"))
    assert row.error_code == "TimeoutError"
    assert row.message == "timed out"


def test_once_keeps_one_open_row():
    first = record_integration_error("payments", "webhook_verification", once=True)
    again = record_integration_error("payments", "webhook_verification", once=True)
    assert first.pk == again.pk
    resolve_errors(IntegrationError.objects.all(), UserFactory(role=User.Role.STAFF))
    later = record_integration_error("payments", "webhook_verification", once=True)
    assert later.pk != first.pk


def test_never_raises():
    with patch.object(IntegrationError.objects, "create", side_effect=RuntimeError("db down")):
        assert record_integration_error("sms", "send_otp", RuntimeError("x")) is None


def test_resolve_marks_only_open_rows():
    staff = UserFactory(role=User.Role.STAFF)
    record_integration_error("zatca", "report_simplified")
    record_integration_error("zatca", "report_simplified")
    assert resolve_errors(IntegrationError.objects.all(), staff) == 2
    assert resolve_errors(IntegrationError.objects.all(), staff) == 0
    assert IntegrationError.objects.filter(resolved_by=staff).count() == 2
