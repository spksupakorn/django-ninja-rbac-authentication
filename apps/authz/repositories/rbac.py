"""Async persistence operations for roles and permissions."""

from __future__ import annotations

from apps.authz.models import Permission, Role, RolePermission, UserRole
from apps.common.repositories import BaseRepository


class AuthzRepository(BaseRepository[Role]):
    """Provide RBAC queries without exposing ORM traversal to services."""

    def __init__(self) -> None:
        super().__init__(Role)

    async def aget_role_by_name(self, name: str) -> Role | None:
        """Find a role by its stable name."""
        return await self.aget_or_none(name=name)

    async def aget_user_permission_codes(self, user_id: int) -> set[str]:
        """Return all distinct permission codes inherited by a user through roles."""
        permission_codes = Permission.objects.filter(
            role_links__role__user_links__user_id=user_id
        ).values_list("code", flat=True).distinct()
        return {code async for code in permission_codes}

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
