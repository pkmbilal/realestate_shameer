import pytest

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


def test_create_user_normalizes_phone_and_has_no_password():
    user = User.objects.create_user("0512345678")
    assert user.phone == "+966512345678"
    assert user.role == User.Role.BUYER
    assert not user.has_usable_password()
    assert not user.is_staff


def test_create_superuser_is_staff_with_password():
    user = User.objects.create_superuser("0512345679", password="a-strong-pass-123")
    assert user.is_staff and user.is_superuser
    assert user.role == User.Role.STAFF
    assert user.check_password("a-strong-pass-123")


def test_create_superuser_requires_password():
    with pytest.raises(ValueError):
        User.objects.create_superuser("0512345670")


def test_str_is_masked():
    user = User.objects.create_user("+966512345678")
    assert str(user) == "+9665•••••678"
