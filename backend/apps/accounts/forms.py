from django.contrib.auth.forms import UserChangeForm as BaseUserChangeForm
from django.contrib.auth.forms import UserCreationForm as BaseUserCreationForm

from .models import User
from .phone import normalize_phone


class PhoneCleanMixin:
    def clean_phone(self):
        return normalize_phone(self.cleaned_data["phone"])


class UserCreationForm(PhoneCleanMixin, BaseUserCreationForm):
    class Meta:
        model = User
        fields = ("phone", "role")


class UserChangeForm(PhoneCleanMixin, BaseUserChangeForm):
    class Meta:
        model = User
        fields = "__all__"
