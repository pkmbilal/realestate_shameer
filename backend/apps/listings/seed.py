"""Launch amenities and local demo listings (used by `seed_amenities` and `seed_demo`)."""

from django.db import transaction

from apps.accounts.models import NafathVerification, User

from . import services
from .models import Amenity, Listing

AMENITIES = [
    ("parking", "موقف سيارات", "Parking"),
    ("elevator", "مصعد", "Elevator"),
    ("central-ac", "تكييف مركزي", "Central A/C"),
    ("maids-room", "غرفة خادمة", "Maid's room"),
    ("drivers-room", "غرفة سائق", "Driver's room"),
    ("private-pool", "مسبح خاص", "Private pool"),
    ("garden", "حديقة", "Garden"),
    ("balcony", "شرفة", "Balcony"),
    ("kitchen-fitted", "مطبخ راكب", "Fitted kitchen"),
    ("security", "حراسة أمنية", "Security"),
    ("gym", "نادي رياضي", "Gym"),
    ("near-mosque", "قريب من مسجد", "Near a mosque"),
    ("near-school", "قريب من مدرسة", "Near a school"),
    ("sea-view", "إطلالة بحرية", "Sea view"),
]


def seed_amenities() -> int:
    for order, (slug, name_ar, name_en) in enumerate(AMENITIES):
        Amenity.objects.update_or_create(
            slug=slug, defaults={"name_ar": name_ar, "name_en": name_en, "sort_order": order}
        )
    return len(AMENITIES)


TYPE_NAMES_AR = {
    "apartment": "شقة",
    "villa": "فيلا",
    "floor": "دور",
    "duplex": "دوبلكس",
    "townhouse": "تاون هاوس",
    "land": "أرض",
    "building": "عمارة",
}

# Mock REGA licence numbers (see integrations/rega/mock.py), so every place gets a listing.
DEMO_LICENCES = [f"71000000{n:02d}" for n in range(1, 13)]
DEMO_OWNER_PHONE = "+966500000101"


def seed_demo_listings() -> int:
    """Active demo listings for a demo owner. Local development only (mock REGA data).

    They have no photos, so they skip the normal submit step; never do this in real code.
    """
    owner, _ = User.objects.get_or_create(phone=DEMO_OWNER_PHONE, defaults={"role": "owner"})
    NafathVerification.objects.get_or_create(
        user=owner,
        transaction_ref="demo-owner",
        defaults={"status": NafathVerification.Status.APPROVED},
    )
    amenities = list(Amenity.objects.all()[:4])
    created = 0
    for i, number in enumerate(DEMO_LICENCES):
        if Listing.objects.filter(licence_number=number).exists():
            continue
        with transaction.atomic():
            listing = services.start_listing_from_licence(owner, number)
            is_rent = listing.purpose == Listing.Purpose.RENT
            price_sar = (40_000 + i * 7_500) if is_rent else (650_000 + i * 120_000)
            services.update_listing(
                listing,
                owner,
                amenities=amenities,
                price_halalas=price_sar * 100,
                bedrooms=None if listing.property_type == "land" else 2 + i % 4,
                bathrooms=None if listing.property_type == "land" else 2 + i % 3,
                title_ar=f"{TYPE_NAMES_AR[listing.property_type]} في {listing.city.name_ar}",
                title_en=f"{listing.get_property_type_display()} in {listing.city.name_en}",
                description_ar="إعلان تجريبي لأغراض التطوير.",
                description_en="Demo listing for local development.",
            )
            services._transition(
                listing,
                Listing.Status.PENDING_REVIEW,
                allowed_from={Listing.Status.DRAFT},
                by=None,
                reason="demo seed",
            )
            services.approve(listing, by=None)
        created += 1
    return created
