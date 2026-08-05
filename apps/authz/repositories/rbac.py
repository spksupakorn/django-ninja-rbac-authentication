"""Async persistence operations for roles and permissions."""

from __future__ import annotations

from asgiref.sync import sync_to_async
from django.db import transaction

from apps.accounts.models import User
from apps.authz.models import Permission, Role, RolePermission, UserRole


class AuthzRepository:
    """Provide RBAC queries without exposing ORM traversal to services."""

    async def acreate_user_with_role(
        self, *, email: str, password_hash: str, role_id: int
    ) -> User:
        """Create a user and its role assignment atomically (registration write)."""
        return await sync_to_async(self._create_user_with_role, thread_sensitive=True)(
            email=email, password_hash=password_hash, role_id=role_id
        )

    def _create_user_with_role(self, *, email: str, password_hash: str, role_id: int) -> User:
        """Persist the user and role link in one transaction so neither can orphan."""
        with transaction.atomic():
            user = User.objects.create(
                email=User.objects.normalize_email(email), password=password_hash
            )
            UserRole.objects.create(user_id=user.id, role_id=role_id)
        return user

    async def aget_role_by_name(self, name: str) -> Role | None:
        """Find a role by its stable name."""
        try:
            return await Role.objects.aget(name=name)
        except Role.DoesNotExist:
            return None

    async def aget_user_permission_codes(self, user_id: int) -> set[str]:
        """Return all distinct permission codes inherited by a user through roles."""
        permission_codes = Permission.objects.filter(
            role_links__role__user_links__user_id=user_id
        ).values_list("code", flat=True).distinct()
        return {code async for code in permission_codes}

    async def aget_user_role_names(self, user_id: int) -> set[str]:
        """Return all role names assigned to a user."""
        role_names = Role.objects.filter(user_links__user_id=user_id).values_list("name", flat=True)
        return {name async for name in role_names}

    async def aassign_role(self, *, user_id: int, role_id: int) -> UserRole:
        """Assign a role to a user, returning an existing assignment if present."""
        assignment, _ = await UserRole.objects.aget_or_create(user_id=user_id, role_id=role_id)
        return assignment

    async def agrant_permission(self, *, role_id: int, permission_id: int) -> RolePermission:
        """Grant a permission to a role, idempotently."""
        role_permission, _ = await RolePermission.objects.aget_or_create(
            role_id=role_id, permission_id=permission_id
        )
        return role_permission
