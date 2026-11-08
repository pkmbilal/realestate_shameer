from rest_framework import serializers

from .models import Payment, TopUpPackage


class TopUpPackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = TopUpPackage
        fields = ("id", "name_ar", "name_en", "credits", "price_halalas")
        read_only_fields = fields


class StartTopUpSerializer(serializers.Serializer):
    package_id = serializers.IntegerField(min_value=1)
    locale = serializers.ChoiceField(choices=["ar", "en"], default="ar")


class PaymentSerializer(serializers.ModelSerializer):
    package_name_ar = serializers.CharField(source="package.name_ar", read_only=True)
    package_name_en = serializers.CharField(source="package.name_en", read_only=True)
    balance = serializers.IntegerField(source="wallet.balance", read_only=True)
    invoice_id = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = (
            "id",
            "status",
            "credits",
            "amount_halalas",
            "package_name_ar",
            "package_name_en",
            "balance",
            "invoice_id",
            "paid_at",
            "created_at",
        )
        read_only_fields = fields

    def get_invoice_id(self, obj) -> int | None:
        """The invoice, once it has been issued and reported (it follows the payment shortly)."""
        invoice = getattr(obj, "invoice", None)
        return invoice.pk if invoice and invoice.zatca_status == "reported" else None
