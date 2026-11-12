import pytest
from django.core.cache import cache

from apps.locations.services import load_locations_file


@pytest.fixture(autouse=True)
def places(db):
    """The real launch cities and districts."""
    load_locations_file()


@pytest.fixture(autouse=True)
def clear_cache():
    """The area endpoint is cached; start every test with an empty cache."""
    cache.clear()
    yield
    cache.clear()
