from rest_framework import serializers

from .models import Lead


class CreateLeadSerializer(serializers.Serializer):
    listing = serializers.CharField(max_length=16)  # the listing reference
    channel = serializers.ChoiceField(choices=Lead.Channel.choices)
    locale = serializers.ChoiceField(choices=("ar", "en"), default="ar")
    name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    message = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")
