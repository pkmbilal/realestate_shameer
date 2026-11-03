from unittest.mock import MagicMock

import pytest

from apps.locations.services import load_locations_file


@pytest.fixture(autouse=True)
def places(db):
    """The real launch cities and districts that listing factories refer to."""
    load_locations_file()


@pytest.fixture
def queued(monkeypatch):
    """Capture notification tasks instead of sending them to Celery."""
    delay = MagicMock()
    monkeypatch.setattr("apps.leads.tasks.notify_advertiser_of_lead.delay", delay)
    return delay
