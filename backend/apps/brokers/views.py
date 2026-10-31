from django.http import Http404
from rest_framework import status
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsNafathVerified

from . import services
from .models import Agency, BrokerProfile
from .serializers import (
    AddMemberSerializer,
    AgencyMemberSerializer,
    AgencySerializer,
    BrokerProfileSerializer,
    PublicAgencySerializer,
    PublicBrokerSerializer,
)


def _not_found():
    return Response({"code": "not_found"}, status=status.HTTP_404_NOT_FOUND)


class BrokerMeView(APIView):
    """GET: my broker profile (404 if I don't have one yet). PUT: create or update it."""

    permission_classes = [IsNafathVerified]

    def get(self, request):
        profile = BrokerProfile.objects.filter(user=request.user).first()
        if profile is None:
            return _not_found()
        return Response(BrokerProfileSerializer(profile).data)

    def put(self, request):
        profile = BrokerProfile.objects.filter(user=request.user).first()
        serializer = BrokerProfileSerializer(profile, data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = services.save_broker_profile(request.user, **serializer.validated_data)
        return Response(
            BrokerProfileSerializer(profile).data,
            status=status.HTTP_200_OK if serializer.instance else status.HTTP_201_CREATED,
        )


class BrokerDetailView(RetrieveAPIView):
    """Public broker profile."""

    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = PublicBrokerSerializer
    queryset = BrokerProfile.objects.filter(user__is_active=True).select_related("agency")


class AgencyMeView(APIView):
    """GET: the agency I run (404 if none). PUT: create or update it."""

    permission_classes = [IsNafathVerified]

    def get(self, request):
        agency = Agency.objects.filter(admin=request.user).first()
        if agency is None:
            return _not_found()
        return Response(AgencySerializer(agency).data)

    def put(self, request):
        agency = Agency.objects.filter(admin=request.user).first()
        serializer = AgencySerializer(agency, data=request.data)
        serializer.is_valid(raise_exception=True)
        agency = services.save_agency(request.user, **serializer.validated_data)
        return Response(
            AgencySerializer(agency).data,
            status=status.HTTP_200_OK if serializer.instance else status.HTTP_201_CREATED,
        )


class AgencyMembersMixin:
    permission_classes = [IsNafathVerified]

    def get_agency(self):
        agency = Agency.objects.filter(admin=self.request.user).first()
        if agency is None:
            raise Http404
        return agency


class AgencyMembersView(AgencyMembersMixin, APIView):
    """GET: brokers in my agency. POST {phone}: add a broker who already has a profile."""

    def get(self, request):
        members = self.get_agency().members.all()
        return Response(AgencyMemberSerializer(members, many=True).data)

    def post(self, request):
        agency = self.get_agency()
        serializer = AddMemberSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"code": "invalid_phone"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            profile = services.add_agency_member(agency, serializer.validated_data["phone"])
        except services.BrokerError as exc:
            return Response({"code": exc.code}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AgencyMemberSerializer(profile).data, status=status.HTTP_201_CREATED)


class AgencyMemberDetailView(AgencyMembersMixin, APIView):
    """DELETE: remove a broker from my agency (their profile stays)."""

    def delete(self, request, pk):
        try:
            services.remove_agency_member(self.get_agency(), pk)
        except services.BrokerError:
            return _not_found()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AgencyDetailView(RetrieveAPIView):
    """Public agency page with its brokers."""

    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = PublicAgencySerializer
    queryset = Agency.objects.prefetch_related("members")
