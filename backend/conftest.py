import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _test_settings(settings):
    # Keep rate-limit counters out of the development Redis and fresh for every test.
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    # The real hasher is deliberately slow; tests don't need that.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    settings.INTEGRATIONS_MODE = "mock"
    cache.clear()
    yield
    cache.clear()
