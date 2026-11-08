import pytest

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory
from apps.brokers.tests.factories import BrokerProfileFactory
from apps.listings.tests.factories import ListingFactory, ListingPhotoFactory
from apps.locations.services import load_locations_file
from apps.wallet import services


@pytest.fixture(autouse=True)
def places(db):
    """Listings need the real launch cities."""
    load_locations_file()


@pytest.fixture
def staff(db):
    return UserFactory(role=User.Role.STAFF, is_staff=True)


@pytest.fixture
def set_price(db):
    def _set(action, credits, days=None):
        price = services.price_for(action)
        price.credits = credits
        if days is not None:
            price.days = days
        price.save()
        return price

    return _set


@pytest.fixture
def broker(db):
    return BrokerProfileFactory()


@pytest.fixture
def funded_wallet(broker, staff):
    """The broker's wallet with 100 granted credits."""
    wallet = services.wallet_for_user(broker.user)
    services.grant(wallet, 100, staff, "Launch promotion")
    return wallet


@pytest.fixture
def broker_listing(broker):
    """A complete draft listing posted by the broker, ready to submit."""
    listing = ListingFactory(created_by=broker.user, broker=broker)
    ListingPhotoFactory(listing=listing)
    return listing
