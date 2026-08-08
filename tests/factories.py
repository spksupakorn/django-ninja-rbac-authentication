"""Reusable factory-boy fixtures for database-backed tests."""

from __future__ import annotations

import factory

from apps.accounts.models import User
from apps.audit.actions import AuditAction
from apps.audit.models import AuditLog
from apps.authz.models import Permission, Role


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
