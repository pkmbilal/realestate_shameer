from datetime import timedelta

import factory
from django.utils import timezone

from apps.accounts.models import User
from apps.brokers.tests.factories import VerifiedUserFactory
from apps.core.dates import riyadh_today
from apps.listings.models import Listing, ListingPhoto
from apps.locations.models import City
from integrations.rega.mock import MockRegaClient


class ListingFactory(factory.django.DjangoModelFactory):
    """A draft listing in Dammam with all advertiser fields filled (photos not included)."""

    class Meta:
        model = Listing

    created_by = factory.SubFactory(VerifiedUserFactory, role=User.Role.OWNER)
    licence_number = factory.Sequence(lambda n: f"72{n:08d}")
    licence_expires_on = factory.LazyFunction(lambda: riyadh_today() + timedelta(days=90))
    purpose = Listing.Purpose.SALE
    property_type = Listing.PropertyType.APARTMENT
    city = factory.LazyFunction(lambda: City.objects.get(slug_en="dammam"))
    area_m2 = 150
    location = "POINT(50.0372 26.3929)"
    rega_synced_at = factory.LazyFunction(timezone.now)
    price_halalas = 85_000_000
    bedrooms = 3
    bathrooms = 2
    title_ar = "شقة للبيع"
    title_en = "Apartment for sale"


class ListingPhotoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ListingPhoto

    listing = factory.SubFactory(ListingFactory)
    key = factory.LazyAttributeSequence(lambda o, n: f"listings/{o.listing.reference}/p{n}.jpg")
    position = factory.Sequence(lambda n: n)
    size_bytes = 1000


def licence_for(purpose: str, start: int = 7300000001) -> str:
    """A mock REGA licence number whose data has the given purpose."""
    client = MockRegaClient()
    n = start
    while client.fetch_ad_licence(str(n)).purpose != purpose:
        n += 1
    return str(n)
