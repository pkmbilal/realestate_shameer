from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import BaseThrottle
from rest_framework.views import APIView

from apps.listings.models import Listing

from . import services
from .models import Lead
from .serializers import CreateLeadSerializer


class CreateLeadView(APIView):
    """POST: a visitor contacts the advertiser of an active listing.

    The lead is logged first and only then is the contact link returned, so the advertiser's
    number never appears in public listing pages and every contact is counted.
    """

    permission_classes = [AllowAny]
    throttle_scope = "lead_create"

    def post(self, request):
        serializer = CreateLeadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        listing = (
            Listing.objects.select_related("broker", "agency", "created_by")
            .filter(reference=data["listing"], status=Listing.Status.ACTIVE)
            .first()
        )
        if listing is None:
            return Response({"code": "listing_not_active"}, status=status.HTTP_404_NOT_FOUND)

        user = request.user if request.user.is_authenticated else None
        fingerprint = services.client_fingerprint(
            BaseThrottle().get_ident(request), request.META.get("HTTP_USER_AGENT", "")
        )
        try:
            lead = services.record_lead(
                listing,
                data["channel"],
                user=user,
                client_hash=fingerprint,
                name=data["name"],
                phone=data["phone"],
                message=data["message"],
            )
        except services.LeadError as exc:
            body = {"code": exc.code}
            if exc.fields:
                body["fields"] = exc.fields
            return Response(body, status=status.HTTP_400_BAD_REQUEST)

        body = {"id": lead.pk, "channel": lead.channel}
        if lead.channel == Lead.Channel.WHATSAPP:
            body["whatsapp_url"] = services.whatsapp_url(listing, data["locale"])
        elif lead.channel == Lead.Channel.CALL:
            body["tel_url"] = services.tel_url(listing)
        return Response(body, status=status.HTTP_201_CREATED)
