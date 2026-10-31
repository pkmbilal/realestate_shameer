"""
Shared helper for external-system adapters.

Each integration (rega, nafath, zatca, sms, whatsapp, payments) lives in its own package with:
  - an interface (abstract base class) describing what the rest of the code may call,
  - a MockClient used locally and in tests,
  - a LiveClient that talks to the real provider.
Views and services ask for a client via get_client(); they never call third-party APIs directly.
"""

from django.conf import settings


def get_client[T](mock_cls: type[T], live_cls: type[T]) -> T:
    """Return the mock or live client depending on the INTEGRATIONS_MODE setting."""
    if settings.INTEGRATIONS_MODE == "live":
        return live_cls()
    return mock_cls()
