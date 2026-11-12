"""Recording integration failures so staff can see them in admin."""

import logging
import re

from django.db import transaction
from django.utils import timezone

from .models import IntegrationError

logger = logging.getLogger(__name__)

# 7+ digits in a row (optionally after +) look like a phone number or a national ID.
_LONG_NUMBER = re.compile(r"\+?\d{7,}")
MAX_MESSAGE = 500


def clean_message(text: str) -> str:
    """Mask anything that could be a phone number or national ID, then shorten (PDPL)."""
    return _LONG_NUMBER.sub("[number]", text or "")[:MAX_MESSAGE]


def record_integration_error(
    integration: str,
    operation: str,
    exc: BaseException | None = None,
    *,
    reference: str = "",
    message: str = "",
    once: bool = False,
) -> IntegrationError | None:
    """Save one failure. Never raises: a broken error log must not break the caller.

    `exc` gives the error code (its `.code`, or its class name) and, unless `message` is
    passed, the message. With `once`, nothing is added while an unresolved row for the same
    integration, operation and reference exists (for checks that repeat on a schedule).
    Call it outside any transaction that is about to roll back, or the row goes with it.
    """
    try:
        code = getattr(exc, "code", "") or (type(exc).__name__ if exc is not None else "")
        text = message or (str(exc) if exc is not None else "")
        fields = {
            "integration": integration,
            "operation": operation[:50],
            "reference": reference[:100],
        }
        with transaction.atomic():
            if once:
                existing = IntegrationError.objects.filter(
                    resolved_at__isnull=True, **fields
                ).first()
                if existing is not None:
                    return existing
            return IntegrationError.objects.create(
                **fields, error_code=str(code)[:100], message=clean_message(text)
            )
    except Exception:
        logger.exception("could not record a %s integration error", integration)
        return None


def resolve_errors(queryset, by) -> int:
    """Mark errors as dealt with. Already-resolved ones are left alone."""
    return queryset.filter(resolved_at__isnull=True).update(
        resolved_at=timezone.now(), resolved_by=by
    )
