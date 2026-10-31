from rest_framework import serializers

from .models import User


class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "masked_phone", "role", "date_joined")
        read_only_fields = fields
