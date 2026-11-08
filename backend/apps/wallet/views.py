from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsVerifiedAdvertiser

from . import services
from .models import CreditTransaction
from .serializers import CreditPriceSerializer, CreditTransactionSerializer


class WalletView(APIView):
    """GET: my credit balance and what each action costs.

    Owners post for free and have no wallet (`has_wallet: false`).
    """

    permission_classes = [IsVerifiedAdvertiser]

    def get(self, request):
        wallet = services.wallet_for_user(request.user)
        return Response(
            {
                "has_wallet": wallet is not None,
                "balance": wallet.balance if wallet else 0,
                "prices": CreditPriceSerializer(services.current_prices(), many=True).data,
            }
        )


class TransactionPagination(PageNumberPagination):
    page_size = 20


class TransactionsView(ListAPIView):
    """GET: my wallet history, newest first."""

    permission_classes = [IsVerifiedAdvertiser]
    serializer_class = CreditTransactionSerializer
    pagination_class = TransactionPagination

    def get_queryset(self):
        wallet = services.wallet_for_user(self.request.user)
        if wallet is None:
            return CreditTransaction.objects.none()
        return wallet.transactions.select_related("listing")
