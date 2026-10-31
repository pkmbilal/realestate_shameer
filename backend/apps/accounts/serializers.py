from rest_framework import serializers

from .models import User


class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "masked_phone", "role", "date_joined")
        read_only_fields = fields


class OtpRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)


class OtpVerifySerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    code = serializers.RegexField(r"^\d{6}$")
