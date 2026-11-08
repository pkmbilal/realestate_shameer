from rest_framework import serializers

from .models import Invoice


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = ("id", "number", "issued_at", "credits", "total_halalas", "vat_halalas")
        read_only_fields = fields
