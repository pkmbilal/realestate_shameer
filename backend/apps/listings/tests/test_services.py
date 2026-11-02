import dataclasses
from datetime import timedelta

import pytest
from botocore.exceptions import ClientError
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory
from apps.brokers.tests.factories import AgencyFactory, BrokerProfileFactory, VerifiedUserFactory
from apps.core.dates import riyadh_today
from apps.listings import services
from apps.listings.models import Listing, ListingStatusChange
from apps.listings.services import ListingError
from integrations.rega.mock import MockRegaClient

from .factories import ListingFactory, ListingPhotoFactory, licence_for

pytestmark = pytest.mark.django_db
Status = Listing.Status


def owner():
    return VerifiedUserFactory(role=User.Role.OWNER)


def staff():
    return UserFactory(role=User.Role.STAFF, is_staff=True)


def error_code(func, *args, **kwargs):
    with pytest.raises(ListingError) as exc:
        func(*args, **kwargs)
    return exc.value.code


def ready_listing(**kwargs):
    listing = ListingFactory(**kwargs)
    ListingPhotoFactory(listing=listing)
    return listing


def active_listing(**kwargs):
    listing = ready_listing(**kwargs)
    services.submit_for_review(listing, listing.created_by)
    return services.approve(listing, staff())


# --- Starting from a licence -----------------------------------------------------------


def test_owner_starts_draft_from_rega_licence():
    number = licence_for("rent")
    user = owner()
    listing = services.start_listing_from_licence(user, f" {number[:4]}-{number[4:]} ")

    licence = MockRegaClient().fetch_ad_licence(number)
    assert listing.status == Status.DRAFT
    assert listing.licence_number == number
    assert listing.licence_expires_on == licence.expires_on
    assert listing.purpose == "rent"
    assert listing.rent_period == Listing.RentPeriod.YEARLY
    assert listing.property_type == licence.property_type
    assert listing.area_m2 == licence.area_m2
    assert listing.city.name_en == licence.city_name_en
    assert listing.district.name_en == licence.district_name_en
    assert listing.location.y == pytest.approx(licence.latitude)
    assert listing.broker is None and listing.agency is None
    assert len(listing.reference) == 8


def test_broker_listing_is_linked_to_broker_and_agency():
    agency = AgencyFactory()
    profile = BrokerProfileFactory(agency=agency)
    listing = services.start_listing_from_licence(profile.user, "7300000101")
    assert listing.broker == profile
    assert listing.agency == agency


def test_agency_admin_listing_is_linked_to_agency():
    agency = AgencyFactory()
    listing = services.start_listing_from_licence(agency.admin, "7300000102")
    assert listing.agency == agency and listing.broker is None


@pytest.mark.parametrize(
    "number, code",
    [
        ("12ab", "invalid_licence_number"),
        ("7300010000", "not_found"),
        ("7300019999", "licence_expired"),
        ("7300018888", "licence_not_yours"),
    ],
)
def test_start_rejects_bad_licences(number, code):
    assert error_code(services.start_listing_from_licence, owner(), number) == code


def test_licence_matching_broker_fal_is_accepted(monkeypatch):
    profile = BrokerProfileFactory()
    real = MockRegaClient.fetch_ad_licence
    monkeypatch.setattr(
        MockRegaClient,
        "fetch_ad_licence",
        lambda self, n: dataclasses.replace(real(self, n), advertiser_fal=profile.fal_licence),
    )
    assert services.start_listing_from_licence(profile.user, "7300000103").broker == profile


def test_unknown_city_is_rejected(monkeypatch):
    real = MockRegaClient.fetch_ad_licence
    monkeypatch.setattr(
        MockRegaClient,
        "fetch_ad_licence",
        lambda self, n: dataclasses.replace(
            real(self, n), city_name_ar="الرياض", city_name_en="Riyadh"
        ),
    )
    assert error_code(services.start_listing_from_licence, owner(), "7300000104") == (
        "unsupported_city"
    )


def test_licence_can_only_be_used_by_one_live_listing():
    user = owner()
    listing = services.start_listing_from_licence(user, "7300000105")
    assert error_code(services.start_listing_from_licence, user, "7300000105") == "licence_in_use"
    services.archive(listing, user)
    assert services.start_listing_from_licence(user, "7300000105").pk != listing.pk


@pytest.mark.parametrize(
    "user_factory, code",
    [
        (lambda: UserFactory(role=User.Role.OWNER), "nafath_required"),
        (lambda: VerifiedUserFactory(role=User.Role.BUYER), "not_an_advertiser"),
        (lambda: VerifiedUserFactory(role=User.Role.BROKER), "broker_profile_required"),
        (lambda: VerifiedUserFactory(role=User.Role.AGENCY_ADMIN), "agency_profile_required"),
    ],
)
def test_only_set_up_advertisers_may_start(user_factory, code):
    assert error_code(services.start_listing_from_licence, user_factory(), "7300000106") == code


# --- Editing ---------------------------------------------------------------------------


def test_update_ignores_rega_fields_and_clears_rent_period_for_sale():
    listing = ListingFactory(rent_period="yearly")
    services.update_listing(
        listing,
        listing.created_by,
        price_halalas=100,
        area_m2=99999,
        licence_number="1",
        purpose="rent",
    )
    listing.refresh_from_db()
    assert listing.price_halalas == 100
    assert listing.area_m2 == 150
    assert listing.purpose == "sale"
    assert listing.rent_period == ""


def test_editing_active_listing_sends_it_back_to_review():
    listing = active_listing()
    services.update_listing(listing, listing.created_by, title_en="New title")
    listing.refresh_from_db()
    assert listing.status == Status.PENDING_REVIEW
    assert listing.status_changes.first().reason == "edited"


def test_archived_listing_cannot_be_edited():
    listing = ListingFactory(status=Status.ARCHIVED)
    assert error_code(services.update_listing, listing, listing.created_by) == "not_editable"


# --- Moderation --------------------------------------------------------------------------


def test_submit_lists_missing_fields():
    listing = ListingFactory(
        purpose="rent", rent_period="", price_halalas=None, title_ar="", title_en=""
    )
    with pytest.raises(ListingError) as exc:
        services.submit_for_review(listing, listing.created_by)
    assert exc.value.code == "incomplete"
    assert exc.value.fields == ["price_halalas", "rent_period", "title", "photos"]


def test_full_moderation_flow_is_logged():
    listing = ready_listing()
    user, moderator = listing.created_by, staff()

    services.submit_for_review(listing, user)
    services.reject(listing, moderator, "Photos are blurry")
    assert listing.status == Status.DRAFT
    assert listing.moderation_note == "Photos are blurry"

    services.submit_for_review(listing, user)
    assert listing.moderation_note == ""
    services.approve(listing, moderator)
    assert listing.status == Status.ACTIVE
    assert listing.published_at is not None
    expected_end = listing.published_at + timedelta(days=30)
    assert abs(listing.post_expires_at - expected_end) < timedelta(seconds=5)

    log = list(listing.status_changes.order_by("id").values_list("to_status", "changed_by"))
    assert log == [
        ("pending_review", user.pk),
        ("draft", moderator.pk),
        ("pending_review", user.pk),
        ("active", moderator.pk),
    ]


def test_reapproval_keeps_post_period():
    listing = active_listing()
    first_end = listing.post_expires_at
    services.update_listing(listing, listing.created_by, title_en="Changed")
    services.approve(listing, staff())
    assert listing.post_expires_at == first_end


def test_reject_and_take_down_need_a_reason():
    listing = ready_listing()
    services.submit_for_review(listing, listing.created_by)
    assert error_code(services.reject, listing, staff(), "  ") == "reason_required"
    assert error_code(services.take_down, listing, staff(), "") == "reason_required"


def test_take_down_is_logged_with_reason():
    listing = active_listing()
    moderator = staff()
    services.take_down(listing, moderator, "Licence revoked by REGA")
    assert listing.status == Status.TAKEN_DOWN
    change = listing.status_changes.first()
    assert (change.to_status, change.changed_by, change.reason) == (
        "taken_down",
        moderator,
        "Licence revoked by REGA",
    )


def test_invalid_transitions_are_refused():
    listing = ListingFactory()
    assert error_code(services.approve, listing, staff()) == "invalid_status"
    services.archive(listing, listing.created_by)
    assert error_code(services.archive, listing, listing.created_by) == "invalid_status"
    assert ListingStatusChange.objects.filter(listing=listing).count() == 1


def test_expired_licence_cannot_be_submitted_or_approved():
    listing = ready_listing()
    services.submit_for_review(listing, listing.created_by)
    Listing.objects.filter(pk=listing.pk).update(
        licence_expires_on=riyadh_today() - timedelta(days=1)
    )
    listing.refresh_from_db()
    assert error_code(services.approve, listing, staff()) == "licence_expired"


# --- Nightly expiry -------------------------------------------------------------------------


def test_expiry_job_hides_due_listings_and_is_idempotent():
    licence_gone = active_listing()
    period_over = active_listing()
    still_fine = active_listing()
    draft = ListingFactory(licence_expires_on=riyadh_today() - timedelta(days=3))
    Listing.objects.filter(pk=licence_gone.pk).update(
        licence_expires_on=riyadh_today() - timedelta(days=1)
    )
    Listing.objects.filter(pk=period_over.pk).update(
        post_expires_at=timezone.now() - timedelta(minutes=1)
    )

    assert services.expire_due_listings() == 2
    assert services.expire_due_listings() == 0

    statuses = dict(Listing.objects.values_list("pk", "status"))
    assert statuses[licence_gone.pk] == Status.EXPIRED
    assert statuses[period_over.pk] == Status.EXPIRED
    assert statuses[still_fine.pk] == Status.ACTIVE
    assert statuses[draft.pk] == Status.DRAFT
    reasons = set(
        ListingStatusChange.objects.filter(to_status="expired").values_list("reason", flat=True)
    )
    assert reasons == {"licence_expired", "post_period_ended"}


def test_licence_expiring_today_stays_live():
    listing = active_listing()
    Listing.objects.filter(pk=listing.pk).update(licence_expires_on=riyadh_today())
    assert services.expire_due_listings() == 0


# --- Photos ----------------------------------------------------------------------------------


def test_presign_returns_browser_url(s3):
    listing = ListingFactory()
    upload = services.presign_photo_upload(listing, "image/jpeg", 2048)
    assert upload["key"].startswith(f"listings/{listing.reference}/")
    assert upload["key"].endswith(".jpg")
    assert upload["upload_url"].startswith("http://localhost:8333/")
    assert upload["method"] == "PUT"
    assert upload["headers"] == {"Content-Type": "image/jpeg"}


@pytest.mark.parametrize(
    "content_type, size, code",
    [
        ("image/gif", 100, "unsupported_photo_type"),
        ("image/png", 0, "photo_too_large"),
        ("image/png", 11 * 1024 * 1024, "photo_too_large"),
    ],
)
def test_presign_checks_type_and_size(s3, content_type, size, code):
    listing = ListingFactory()
    assert error_code(services.presign_photo_upload, listing, content_type, size) == code


def test_presign_limits_photo_count(s3, settings):
    settings.LISTING_PHOTO_MAX_COUNT = 1
    listing = ready_listing()
    assert error_code(services.presign_photo_upload, listing, "image/png", 10) == (
        "too_many_photos"
    )


def test_confirm_adds_photos_in_order(s3):
    listing = ListingFactory()
    prefix = f"listings/{listing.reference}/"
    first = services.confirm_photo(listing, listing.created_by, prefix + "a.jpg")
    second = services.confirm_photo(listing, listing.created_by, prefix + "b.jpg")
    assert (first.position, second.position) == (0, 1)
    assert first.size_bytes == 2048


def test_confirm_rejects_foreign_or_missing_keys(s3):
    listing = ListingFactory()
    user = listing.created_by
    assert error_code(services.confirm_photo, listing, user, "listings/OTHER/a.jpg") == (
        "invalid_photo_key"
    )
    s3.head_object.side_effect = ClientError({"Error": {"Code": "404"}}, "HeadObject")
    key = f"listings/{listing.reference}/a.jpg"
    assert error_code(services.confirm_photo, listing, user, key) == "photo_not_uploaded"


def test_confirm_deletes_oversized_upload(s3):
    listing = ListingFactory()
    s3.head_object.return_value = {"ContentLength": 50 * 1024 * 1024, "ContentType": "image/jpeg"}
    key = f"listings/{listing.reference}/big.jpg"
    assert error_code(services.confirm_photo, listing, listing.created_by, key) == (
        "photo_too_large"
    )
    s3.delete_object.assert_called_once()
    assert not listing.photos.exists()


def test_new_photo_on_active_listing_needs_review(s3):
    listing = active_listing()
    services.confirm_photo(listing, listing.created_by, f"listings/{listing.reference}/n.jpg")
    listing.refresh_from_db()
    assert listing.status == Status.PENDING_REVIEW


def test_reorder_and_delete_photos(s3, django_capture_on_commit_callbacks):
    listing = ListingFactory()
    a, b, c = (ListingPhotoFactory(listing=listing, position=i) for i in range(3))

    services.reorder_photos(listing, [c.pk, a.pk, b.pk])
    assert list(listing.photos.values_list("pk", flat=True)) == [c.pk, a.pk, b.pk]
    assert error_code(services.reorder_photos, listing, [a.pk, b.pk]) == "invalid_photo_order"

    with django_capture_on_commit_callbacks(execute=True):
        services.delete_photo(listing, listing.created_by, c.pk)
    assert list(listing.photos.values_list("pk", "position")) == [(a.pk, 0), (b.pk, 1)]
    s3.delete_object.assert_called_once_with(Bucket="portal-media", Key=c.key)
    assert error_code(services.delete_photo, listing, listing.created_by, c.pk) == (
        "photo_not_found"
    )


def test_record_view_counts():
    listing = ListingFactory()
    services.record_view(listing)
    services.record_view(listing)
    listing.refresh_from_db()
    assert listing.view_count == 2
