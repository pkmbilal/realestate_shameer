from django.conf import settings
from rest_framework import serializers

from .models import CreditPrice, CreditTransaction


class CreditPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditPrice
        fields = ("action", "credits", "days")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.action == CreditTransaction.Action.POST:
            # The post period is a setting, not a price; show it so brokers know what they get.
            data["days"] = settings.LISTING_POST_DAYS
        return data


class CreditTransactionSerializer(serializers.ModelSerializer):
    listing = serializers.CharField(source="listing.reference", default=None, read_only=True)

    class Meta:
        model = CreditTransaction
        fields = (
            "id",
            "kind",
            "action",
            "amount",
            "balance_after",
            "listing",
            "note",
            "created_at",
        )
        read_only_fields = fields
