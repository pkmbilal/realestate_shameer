from unittest.mock import MagicMock

import pytest

from apps.core.storage import s3_client as real_s3_client
from apps.locations.services import load_locations_file


@pytest.fixture(autouse=True)
def places(db):
    """The real launch cities and districts, which the mock REGA client refers to."""
    load_locations_file()


@pytest.fixture
def s3(monkeypatch):
    """A fake S3 client for the photo services (presigning still uses the real one)."""
    client = MagicMock()
    client.head_object.return_value = {"ContentLength": 2048, "ContentType": "image/jpeg"}

    def fake_client(*, public=False):
        if public:
            return real_s3_client(public=True)
        return client

    monkeypatch.setattr("apps.listings.services.s3_client", fake_client)
    return client
