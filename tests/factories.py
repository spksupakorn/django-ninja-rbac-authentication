"""Reusable factory-boy fixtures for database-backed tests."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import factory
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.actions import AuditAction
from apps.audit.models import AuditLog
from apps.authz.models import Permission, RefreshToken, Role


class UserFactory(factory.django.DjangoModelFactory[User]):
    """Build persisted users with canonical email identities."""

    class Meta:
        model = User

    email = factory.Sequence(lambda number: f"user-{number}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "password123")


class RoleFactory(factory.django.DjangoModelFactory[Role]):
    """Build persisted RBAC roles."""

    class Meta:
        model = Role

    name = factory.Sequence(lambda number: f"role-{number}")


class PermissionFactory(factory.django.DjangoModelFactory[Permission]):
    """Build persisted permission catalog entries."""

    class Meta:
        model = Permission

    code = factory.Sequence(lambda number: f"resource-{number}.read")


class AuditLogFactory(factory.django.DjangoModelFactory[AuditLog]):
    """Build persisted audit records without coupling them to user lifecycle."""

    class Meta:
        model = AuditLog

    action = AuditAction.LOGIN_SUCCESS
    actor_id = factory.Sequence(lambda number: number + 1)
    actor_email = factory.LazyAttribute(lambda instance: f"actor-{instance.actor_id}@example.com")
    outcome = "success"
    metadata = factory.LazyFunction(dict)


class RefreshTokenFactory(factory.django.DjangoModelFactory[RefreshToken]):
    """Build a grandfathered refresh token unless a binding is explicitly supplied."""

    class Meta:
        model = RefreshToken

    user = factory.SubFactory(UserFactory)
    token_hash = factory.Sequence(lambda number: f"{number:064x}")
    family_id = factory.LazyFunction(uuid4)
    parent = None
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=7))
    device_hash = None
    issued_ip = None
