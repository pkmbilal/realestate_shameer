from rest_framework import serializers

from .models import User


class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "masked_phone", "role", "date_joined", "is_nafath_verified")
        read_only_fields = fields


class OtpRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)


class OtpVerifySerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    code = serializers.RegexField(r"^\d{6}$")


class NafathStartSerializer(serializers.Serializer):
    # The format is checked in services; the value is never echoed back in errors.
    national_id = serializers.CharField(max_length=10)


class NafathStatusSerializer(serializers.Serializer):
    transaction_ref = serializers.CharField(max_length=64)
