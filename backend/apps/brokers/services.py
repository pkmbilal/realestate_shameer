"""Creating broker and agency profiles, and managing agency members."""

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import User
from apps.accounts.phone import normalize_phone

from .models import Agency, BrokerProfile

# Roles that are upgraded when someone creates a profile. Staff keep their role.
UPGRADABLE_ROLES = {User.Role.BUYER, User.Role.OWNER}


class BrokerError(Exception):
    """A problem the user can see. `code` is a stable key the frontend translates."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _set_role(user: User, role: str, upgrade_from: set) -> None:
    if user.role in upgrade_from:
        user.role = role
        user.save(update_fields=["role"])


def save_broker_profile(user: User, *, cities_served=(), **fields) -> BrokerProfile:
    """Create or update the user's broker profile. The first save makes them a broker.

    `fields` are already validated (see BrokerProfileSerializer); the agency is not
    accepted here because only the agency admin may add a broker to an agency.
    """
    fields.pop("agency", None)
    with transaction.atomic():
        profile, _created = BrokerProfile.objects.update_or_create(user=user, defaults=fields)
        profile.cities_served.set(cities_served)
        _set_role(user, User.Role.BROKER, UPGRADABLE_ROLES)
    return profile


def save_agency(user: User, **fields) -> Agency:
    """Create or update the agency this user runs. The first save makes them its admin."""
    with transaction.atomic():
        agency, _created = Agency.objects.update_or_create(admin=user, defaults=fields)
        _set_role(user, User.Role.AGENCY_ADMIN, UPGRADABLE_ROLES | {User.Role.BROKER})
    return agency


def add_agency_member(agency: Agency, raw_phone: str) -> BrokerProfile:
    """Add the broker with this phone number to the agency."""
    try:
        phone = normalize_phone(raw_phone)
    except ValidationError:
        raise BrokerError("invalid_phone") from None

    with transaction.atomic():
        profile = BrokerProfile.objects.select_for_update().filter(user__phone=phone).first()
        if profile is None:
            raise BrokerError("broker_not_found")
        if profile.agency_id not in (None, agency.pk):
            raise BrokerError("broker_in_other_agency")
        profile.agency = agency
        profile.save(update_fields=["agency", "updated_at"])
    return profile


def remove_agency_member(agency: Agency, profile_id: int) -> None:
    removed = BrokerProfile.objects.filter(pk=profile_id, agency=agency).update(agency=None)
    if not removed:
        raise BrokerError("broker_not_found")
