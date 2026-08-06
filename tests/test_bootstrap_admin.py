import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import User
from apps.authz.models import Role, UserRole


@pytest.mark.django_db
def test_bootstrap_admin_creates_a_django_and_authz_administrator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    Role.objects.get_or_create(name="admin")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "bootstrap-password123")

    call_command("bootstrap_admin", email="ADMIN@Example.com")
    call_command("bootstrap_admin", email="admin@example.com")

    user = User.objects.get(email="admin@example.com")
    assert user.is_active
    assert user.is_staff
    assert user.is_superuser
    assert user.check_password("bootstrap-password123")
    assert UserRole.objects.filter(user=user, role__name="admin").count() == 1


@pytest.mark.django_db
def test_bootstrap_admin_requires_password_only_when_creating_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    Role.objects.get_or_create(name="admin")
    monkeypatch.delenv("BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    with pytest.raises(CommandError, match="BOOTSTRAP_ADMIN_PASSWORD"):
        call_command("bootstrap_admin", email="admin@example.com")
