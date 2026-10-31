from rest_framework.permissions import BasePermission

from .models import User

ADVERTISER_ROLES = {User.Role.OWNER, User.Role.BROKER, User.Role.AGENCY_ADMIN}


class IsNafathVerified(BasePermission):
    """Logged in and verified through Nafath (needed for broker and agency profiles)."""

    message = "nafath_required"

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_nafath_verified)


class IsVerifiedAdvertiser(IsNafathVerified):
    """A Nafath-verified owner, broker or agency admin: the people allowed to post listings."""

    message = "advertiser_required"

    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role in ADVERTISER_ROLES
