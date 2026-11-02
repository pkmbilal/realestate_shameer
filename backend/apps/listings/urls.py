from django.urls import path, register_converter

from . import views
from .models import REFERENCE_ALPHABET, REFERENCE_LENGTH


class ReferenceConverter:
    """Listing references are 8 upper-case letters/digits, so they never clash with 'mine'."""

    regex = f"[{REFERENCE_ALPHABET}]{{{REFERENCE_LENGTH}}}"

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value


register_converter(ReferenceConverter, "ref")

mine = "mine/<ref:reference>/"

urlpatterns = [
    path("", views.PublicListingsView.as_view(), name="listing-list"),
    path("amenities/", views.AmenitiesView.as_view(), name="amenity-list"),
    path("mine/", views.MyListingsView.as_view(), name="my-listings"),
    path(mine, views.MyListingDetailView.as_view(), name="my-listing"),
    path(f"{mine}submit/", views.SubmitListingView.as_view(), name="my-listing-submit"),
    path(f"{mine}archive/", views.ArchiveListingView.as_view(), name="my-listing-archive"),
    path(
        f"{mine}photos/presign/", views.PresignPhotoView.as_view(), name="my-listing-photo-presign"
    ),
    path(f"{mine}photos/", views.PhotosView.as_view(), name="my-listing-photos"),
    path(f"{mine}photos/<int:photo_id>/", views.PhotoDetailView.as_view(), name="my-listing-photo"),
    path("<ref:reference>/", views.PublicListingDetailView.as_view(), name="listing-detail"),
]
