from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date


class RegaError(Exception):
    """REGA could not give us a licence. `code` is a stable key the frontend translates:
    `not_found` (no such ad licence) or `unavailable` (REGA did not answer)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class RegaAdLicence:
    """The facts REGA holds about one advertising licence. Advertisers may not change these."""

    licence_number: str
    expires_on: date
    purpose: str  # "sale" or "rent"
    property_type: str  # see apps.listings.models.Listing.PropertyType
    city_name_ar: str
    city_name_en: str
    district_name_ar: str
    district_name_en: str
    area_m2: int
    latitude: float
    longitude: float
    # FAL licence of the broker/agency the ad licence was issued to; empty for owners.
    advertiser_fal: str = ""
    # Everything REGA sent, kept for audit. Must not contain personal data.
    raw: dict = field(default_factory=dict)


class RegaClient(ABC):
    """Reads advertising licences from REGA's platform API."""

    @abstractmethod
    def fetch_ad_licence(self, licence_number: str) -> RegaAdLicence: ...
