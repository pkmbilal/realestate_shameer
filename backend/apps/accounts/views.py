from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import services
from .serializers import MeSerializer, NafathStartSerializer, NafathStatusSerializer


class MeView(APIView):
    """The logged-in user's own profile."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(MeSerializer(request.user).data)


class NafathStartView(APIView):
    """Start a Nafath check. The response holds the number the user taps in the Nafath app."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "nafath_start"

    def post(self, request):
        serializer = NafathStartSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"code": "invalid_national_id"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            verification, number = services.start_nafath_verification(
                request.user, serializer.validated_data["national_id"]
            )
        except services.NafathError as exc:
            return Response({"code": exc.code}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "transaction_ref": verification.transaction_ref,
                "random_number": number,
                "status": verification.status,
            },
            status=status.HTTP_201_CREATED,
        )


class NafathStatusView(APIView):
    """Polled by the verify page until the check is approved, rejected or expired."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "nafath_status"

    def post(self, request):
        serializer = NafathStatusSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"code": "not_found"}, status=status.HTTP_404_NOT_FOUND)
        try:
            verification = services.check_nafath_verification(
                request.user, serializer.validated_data["transaction_ref"]
            )
        except services.NafathError as exc:
            return Response({"code": exc.code}, status=status.HTTP_404_NOT_FOUND)
        return Response({"status": verification.status})
