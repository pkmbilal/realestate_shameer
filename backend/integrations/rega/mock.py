import hashlib
import logging
from datetime import timedelta

from apps.core.dates import riyadh_today

from .base import RegaAdLicence, RegaClient, RegaError

logger = logging.getLogger(__name__)

# Real launch-market places (they exist in apps/locations/data/eastern_province.json).
_PLACES = [
    ("الدمام", "Dammam", "الشعلة", "Al Shulah", 26.3929, 50.0372),
    ("الدمام", "Dammam", "الفيصلية", "Al Faisaliyah", 26.4282, 50.0688),
    ("الخبر", "Khobar", "الراكة الشمالية", "Al Rakah Al Shamaliyah", 26.3542, 50.1922),
    ("الخبر", "Khobar", "الراكة الجنوبية", "Al Rakah Al Janubiyah", 26.3402, 50.1956),
    ("الظهران", "Dhahran", "الدوحة الشمالية", "Al Doha Al Shamaliyah", 26.3195, 50.1501),
    ("الجبيل", "Jubail", "الدفي", "Al Deffi", 27.0153, 49.6421),
]
_TYPES = ["apartment", "apartment", "villa", "floor", "duplex", "townhouse", "land", "building"]

# Licence numbers with these endings trigger special cases, for tests and demos.
NOT_FOUND_SUFFIX = "0000"
EXPIRED_SUFFIX = "9999"
OTHER_ADVERTISER_SUFFIX = "8888"
OTHER_ADVERTISER_FAL = "1199999999"


class MockRegaClient(RegaClient):
    """Local development: invents stable licence data from the number itself.

    The same number always gives the same answer. Endings: 0000 = not found,
    9999 = expired yesterday, 8888 = issued to another broker's FAL licence.
    """

    def fetch_ad_licence(self, licence_number: str) -> RegaAdLicence:
        if licence_number.endswith(NOT_FOUND_SUFFIX):
            raise RegaError("not_found")

        seed = int(hashlib.sha256(licence_number.encode()).hexdigest(), 16)
        city_ar, city_en, district_ar, district_en, lat, lng = _PLACES[seed % len(_PLACES)]
        today = riyadh_today()
        if licence_number.endswith(EXPIRED_SUFFIX):
            expires_on = today - timedelta(days=1)
        else:
            expires_on = today + timedelta(days=90 + seed % 180)
        property_type = _TYPES[(seed >> 8) % len(_TYPES)]
        purpose = "rent" if (seed >> 16) % 3 == 0 else "sale"
        area_m2 = 80 + (seed >> 24) % 520
        # Spread points a little so map pins don't stack.
        lat += ((seed >> 32) % 200 - 100) / 20000
        lng += ((seed >> 40) % 200 - 100) / 20000
        fal = OTHER_ADVERTISER_FAL if licence_number.endswith(OTHER_ADVERTISER_SUFFIX) else ""

        logger.info("[mock rega] licence %s looked up", licence_number)
        return RegaAdLicence(
            licence_number=licence_number,
            expires_on=expires_on,
            purpose=purpose,
            property_type=property_type,
            city_name_ar=city_ar,
            city_name_en=city_en,
            district_name_ar=district_ar,
            district_name_en=district_en,
            area_m2=area_m2,
            latitude=round(lat, 6),
            longitude=round(lng, 6),
            advertiser_fal=fal,
            raw={"source": "mock", "licence_number": licence_number},
        )
