from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .phone import mask_phone, normalize_phone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone, password=None, **extra_fields):
        user = self.model(phone=normalize_phone(phone), **extra_fields)
        if password:
            user.set_password(password)
        else:
            # Buyers and brokers log in with a phone OTP, not a password.
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.STAFF)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if not password:
            raise ValueError("Superusers need a password to log in to the admin.")
        return self.create_user(phone, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """A person using the portal. The phone number (E.164) is the login."""

    class Role(models.TextChoices):
        BUYER = "buyer", _("Buyer / renter")
        OWNER = "owner", _("Owner")
        BROKER = "broker", _("Broker")
        AGENCY_ADMIN = "agency_admin", _("Agency admin")
        STAFF = "staff", _("Staff")

    phone = models.CharField(_("phone"), max_length=16, unique=True)
    role = models.CharField(_("role"), max_length=20, choices=Role.choices, default=Role.BUYER)
    is_active = models.BooleanField(_("active"), default=True)
    is_staff = models.BooleanField(_("staff status"), default=False)
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def __str__(self):
        return mask_phone(self.phone)

    @property
    def masked_phone(self):
        return mask_phone(self.phone)
