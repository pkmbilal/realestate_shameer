from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsVerifiedAdvertiser

from . import services
from .models import Amenity, Listing
from .serializers import (
    AmenitySerializer,
    ConfirmPhotoSerializer,
    MapPinSerializer,
    MyListingSerializer,
    PhotoSerializer,
    PresignPhotoSerializer,
    PublicListingCardSerializer,
    PublicListingSerializer,
    ReorderPhotosSerializer,
    SearchParamsSerializer,
    StartListingSerializer,
)


def _error(exc: services.ListingError):
    body = {"code": exc.code}
    if exc.fields:
        body["fields"] = exc.fields
    code = status.HTTP_403_FORBIDDEN if exc.code == "nafath_required" else 400
    return Response(body, status=code)


def _my_listings(user):
    """Listings this user may manage: ones they created, plus their agency's if they run it."""
    return (
        Listing.objects.filter(Q(created_by=user) | Q(agency__admin=user))
        .select_related("city", "district")
        .prefetch_related("photos", "amenities")
        .annotate(lead_count=Count("leads", distinct=True))
        .distinct()
    )


class AdvertiserView(APIView):
    permission_classes = [IsVerifiedAdvertiser]

    def get_listing(self, reference) -> Listing:
        return get_object_or_404(_my_listings(self.request.user), reference=reference)

    def listing_response(self, listing, code=status.HTTP_200_OK):
        listing = self.get_listing(listing.reference)  # fresh, with photos prefetched
        return Response(MyListingSerializer(listing).data, status=code)


class MyListingsView(AdvertiserView):
    """GET: my listings. POST {licence_number}: start a draft from a REGA licence."""

    def get(self, request):
        listings = _my_listings(request.user)
        return Response(MyListingSerializer(listings, many=True).data)

    def post(self, request):
        serializer = StartListingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            listing = services.start_listing_from_licence(
                request.user, serializer.validated_data["licence_number"]
            )
        except services.ListingError as exc:
            return _error(exc)
        return self.listing_response(listing, status.HTTP_201_CREATED)


class MyListingDetailView(AdvertiserView):
    """GET or PATCH one of my listings (only the fields the advertiser owns)."""

    def get(self, request, reference):
        return Response(MyListingSerializer(self.get_listing(reference)).data)

    def patch(self, request, reference):
        listing = self.get_listing(reference)
        serializer = MyListingSerializer(listing, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields = dict(serializer.validated_data)
        amenities = fields.pop("amenities", None)
        try:
            services.update_listing(listing, request.user, amenities=amenities, **fields)
        except services.ListingError as exc:
            return _error(exc)
        return self.listing_response(listing)


class SubmitListingView(AdvertiserView):
    def post(self, request, reference):
        listing = self.get_listing(reference)
        try:
            services.submit_for_review(listing, request.user)
        except services.ListingError as exc:
            return _error(exc)
        return self.listing_response(listing)


class ArchiveListingView(AdvertiserView):
    def post(self, request, reference):
        listing = self.get_listing(reference)
        try:
            services.archive(listing, request.user)
        except services.ListingError as exc:
            return _error(exc)
        return self.listing_response(listing)


class PresignPhotoView(AdvertiserView):
    """POST {content_type, size_bytes}: a URL to PUT one photo straight into storage."""

    def post(self, request, reference):
        listing = self.get_listing(reference)
        serializer = PresignPhotoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            upload = services.presign_photo_upload(listing, **serializer.validated_data)
        except services.ListingError as exc:
            return _error(exc)
        return Response(upload)


class PhotosView(AdvertiserView):
    """POST {key}: record an uploaded photo. PUT {photo_ids}: set the order (first = cover)."""

    def post(self, request, reference):
        listing = self.get_listing(reference)
        serializer = ConfirmPhotoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            photo = services.confirm_photo(listing, request.user, serializer.validated_data["key"])
        except services.ListingError as exc:
            return _error(exc)
        return Response(PhotoSerializer(photo).data, status=status.HTTP_201_CREATED)

    def put(self, request, reference):
        listing = self.get_listing(reference)
        serializer = ReorderPhotosSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.reorder_photos(listing, serializer.validated_data["photo_ids"])
        except services.ListingError as exc:
            return _error(exc)
        return self.listing_response(listing)


class PhotoDetailView(AdvertiserView):
    def delete(self, request, reference, photo_id):
        listing = self.get_listing(reference)
        try:
            services.delete_photo(listing, request.user, photo_id)
        except services.ListingError as exc:
            return _error(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Public ----------------------------------------------------------------------


class ListingPagination(PageNumberPagination):
    page_size = 20


def _search_params(request) -> dict:
    serializer = SearchParamsSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


class PublicListingsView(ListAPIView):
    """Search active listings. Featured listings come first, then the chosen sort.

    Query params are documented on SearchParamsSerializer (purpose, type, city, district,
    price_min/max in SAR, beds_min, baths_min, area_min/max, completion, furnishing,
    rent_period, sort, bbox, page).
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = PublicListingCardSerializer
    pagination_class = ListingPagination

    def get_queryset(self):
        return services.search_listings(_search_params(self.request))


class ListingMapView(APIView):
    """Light map pins for the visible map area. Same filters as search; `bbox` is required."""

    permission_classes = [AllowAny]
    authentication_classes = []
    MAX_PINS = 500

    def get(self, request):
        params = _search_params(request)
        if not params.get("bbox"):
            return Response({"bbox": ["This field is required."]}, status=400)
        qs = (
            services.search_listings(params)
            .select_related(None)
            .prefetch_related(None)
            .only(
                "reference",
                "location",
                "price_halalas",
                "purpose",
                "rent_period",
                "featured_until",
            )
        )
        pins = list(qs[: self.MAX_PINS + 1])
        return Response(
            {
                "results": MapPinSerializer(pins[: self.MAX_PINS], many=True).data,
                "truncated": len(pins) > self.MAX_PINS,
            }
        )


class PublicListingDetailView(RetrieveAPIView):
    """One active listing by its reference. Each request counts as a view."""

    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = PublicListingSerializer
    lookup_field = "reference"

    def get_queryset(self):
        return services.public_listings().prefetch_related("amenities")

    def retrieve(self, request, *args, **kwargs):
        listing = self.get_object()
        services.record_view(listing)
        listing.view_count += 1
        return Response(self.get_serializer(listing).data)


class AmenitiesView(ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = AmenitySerializer
    queryset = Amenity.objects.all()
    pagination_class = None


# --- Favourites (signed-in users) ------------------------------------------------------


class FavouritesView(ListAPIView):
    """The signed-in user's saved listings that are still active."""

    permission_classes = [IsAuthenticated]
    serializer_class = PublicListingCardSerializer
    pagination_class = ListingPagination

    def get_queryset(self):
        return services.favourite_listings(self.request.user)


class FavouriteIdsView(APIView):
    """References of the user's saved listings, so cards can show a filled heart."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"references": services.favourite_references(request.user)})


class FavouriteView(APIView):
    """PUT saves the listing, DELETE un-saves it. Both are safe to repeat."""

    permission_classes = [IsAuthenticated]

    def put(self, request, reference):
        listing = get_object_or_404(services.public_listings(), reference=reference)
        try:
            services.add_favourite(request.user, listing)
        except services.ListingError as exc:
            return _error(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request, reference):
        listing = get_object_or_404(Listing, reference=reference)
        services.remove_favourite(request.user, listing)
        return Response(status=status.HTTP_204_NO_CONTENT)
