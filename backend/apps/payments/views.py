from django.conf import settings
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.views import View
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import IsVerifiedAdvertiser
from apps.core.models import IntegrationError
from apps.core.services import record_integration_error
from integrations.payments import GatewayStatus, WebhookError, get_payments_client
from integrations.payments.mock import MockPaymentsClient
from integrations.zatca.base import halalas_to_sar

from . import services
from .serializers import PaymentSerializer, StartTopUpSerializer, TopUpPackageSerializer


class PackagesView(ListAPIView):
    """GET: the credit packages on sale."""

    permission_classes = [IsVerifiedAdvertiser]
    serializer_class = TopUpPackageSerializer
    pagination_class = None

    def get_queryset(self):
        return services.active_packages()


class PaymentPagination(PageNumberPagination):
    page_size = 20


class TopUpsView(ListAPIView):
    """GET: my top-ups, newest first. POST {package_id, locale}: start a checkout."""

    permission_classes = [IsVerifiedAdvertiser]
    serializer_class = PaymentSerializer
    pagination_class = PaymentPagination
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "topup_start"

    def get_throttles(self):
        # Only starting a checkout is rate-limited; reading the list is not.
        return super().get_throttles() if self.request.method == "POST" else []

    def get_queryset(self):
        return services.payments_for_user(self.request.user)

    def post(self, request):
        data = StartTopUpSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            payment, checkout_url = services.start_top_up(
                request.user, data.validated_data["package_id"], data.validated_data["locale"]
            )
        except services.PaymentError as exc:
            code = status.HTTP_502_BAD_GATEWAY if exc.code == "gateway_unavailable" else 400
            return Response({"code": exc.code}, status=code)
        return Response(
            {"payment_id": payment.pk, "checkout_url": checkout_url},
            status=status.HTTP_201_CREATED,
        )


class TopUpDetailView(APIView):
    """GET: one of my top-ups. Asks the gateway first if it is still waiting for payment."""

    permission_classes = [IsVerifiedAdvertiser]

    def get(self, request, pk):
        payment = services.payments_for_user(request.user).filter(pk=pk).first()
        if payment is None:
            raise Http404
        payment = services.confirm_payment(payment)
        payment = services.payments_for_user(request.user).get(pk=payment.pk)
        return Response(PaymentSerializer(payment).data)


class WebhookView(APIView):
    """POST from Moyasar when a payment changes. Checked with the shared secret."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        try:
            ref = get_payments_client().parse_webhook(request.data)
        except WebhookError as exc:
            # Could be an attack or a wrong webhook secret; either way staff should know.
            # `once` keeps a flood of bad requests from flooding the table.
            record_integration_error(
                IntegrationError.Integration.PAYMENTS, "webhook_verification", exc, once=True
            )
            return Response({"code": "forbidden"}, status=status.HTTP_403_FORBIDDEN)
        services.confirm_by_ref(ref)
        return Response({"ok": True})


class MockCheckoutView(View):
    """INTEGRATIONS_MODE=mock only: a fake payment page with "Pay" and "Fail" buttons."""

    def dispatch(self, request, *args, **kwargs):
        if settings.INTEGRATIONS_MODE != "mock":
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, ref):
        state = MockPaymentsClient.get_state(ref)
        if state is None:
            raise Http404
        return render(
            request,
            "payments/mock_checkout.html",
            {"ref": ref, "state": state, "sar": halalas_to_sar(state["amount"])},
        )

    def post(self, request, ref):
        outcome = request.POST.get("outcome")
        new_status = GatewayStatus.PAID if outcome == "pay" else GatewayStatus.FAILED
        back = MockPaymentsClient.set_status(ref, new_status)
        if back is None:
            raise Http404
        return HttpResponseRedirect(back)
