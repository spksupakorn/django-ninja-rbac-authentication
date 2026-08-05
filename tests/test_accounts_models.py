from unittest.mock import patch

import pytest
from django.db import IntegrityError

from apps.accounts.models import User


def test_create_user_normalizes_email_and_hashes_password() -> None:
    with patch.object(User, "save") as save:
        user = User.objects.create_user("ADMIN@Example.COM", "correct horse battery staple")

    assert user.email == "admin@example.com"
    assert user.check_password("correct horse battery staple")
    assert not user.is_staff
    assert not user.is_superuser
    save.assert_called_once()


def test_create_user_requires_email() -> None:
    with pytest.raises(ValueError, match="email address"):
        User.objects.create_user("", "password")


def test_create_superuser_sets_required_flags() -> None:
    with patch.object(User, "save"):
        user = User.objects.create_superuser("admin@example.com", "password")

    assert user.is_staff
    assert user.is_superuser


def test_create_superuser_rejects_missing_staff_flag() -> None:
    with pytest.raises(ValueError, match="is_staff"):
        User.objects.create_superuser("admin@example.com", "password", is_staff=False)


@pytest.mark.django_db
def test_email_unique_constraint_is_case_insensitive() -> None:
    User.objects.create(email="Admin@example.com")

    with pytest.raises(IntegrityError):
        User.objects.create(email="admin@example.com")
