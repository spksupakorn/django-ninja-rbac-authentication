"""Async persistence operations for roles and permissions."""

from __future__ import annotations

from apps.accounts.models import User
from apps.accounts.repositories.dtos import UserDTO, user_dto_from_model
from apps.authz.models import Permission, Role, RolePermission, UserRole
from apps.authz.repositories.dtos import PermissionDTO, RoleDTO, RolePermissionDTO, UserRoleDTO
from apps.common.db import run_in_transaction


class AuthzRepository:
    """Provide RBAC queries without exposing ORM traversal to services."""

    async def acreate_user_with_role(
        self, *, email: str, password_hash: str, role_id: int
    ) -> UserDTO:
        """Create a user and its role assignment atomically (registration write)."""
        return await run_in_transaction(
            self._create_user_with_role,
            email=email, password_hash=password_hash, role_id=role_id
        )

    def _create_user_with_role(
        self, *, email: str, password_hash: str, role_id: int
    ) -> UserDTO:
        """Persist the user and role link in one transaction so neither can orphan."""
        user = User.objects.create(
            email=User.objects.normalize_email(email), password=password_hash
        )
        UserRole.objects.create(user_id=user.id, role_id=role_id)
        return user_dto_from_model(user)

    async def aget_role_by_name(self, name: str) -> RoleDTO | None:
        """Find a role by its stable name."""
        try:
            return _role_dto(await Role.objects.aget(name=name))
        except Role.DoesNotExist:
            return None

    async def aget_role_by_id(self, role_id: int) -> RoleDTO | None:
        """Find a role by its primary key."""
        try:
            return _role_dto(await Role.objects.aget(id=role_id))
        except Role.DoesNotExist:
            return None

    async def alist_roles(self, *, offset: int, limit: int) -> list[RoleDTO]:
        """Return a stable page of roles."""
        roles = Role.objects.order_by("id")[offset : offset + limit]
        return [_role_dto(role) async for role in roles]

    async def acount_roles(self) -> int:
        """Count roles for pagination metadata."""
        return await Role.objects.acount()

    async def alist_permissions(self, *, offset: int, limit: int) -> list[PermissionDTO]:
        """Return a stable page of permissions."""
        permissions = Permission.objects.order_by("code")[offset : offset + limit]
        return [_permission_dto(permission) async for permission in permissions]

    async def acount_permissions(self) -> int:
        """Count permissions for pagination metadata."""
        return await Permission.objects.acount()

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

    async def aassign_role(self, *, user_id: int, role_id: int) -> UserRoleDTO:
        """Assign a role to a user, returning an existing assignment if present."""
        assignment, _ = await UserRole.objects.aget_or_create(user_id=user_id, role_id=role_id)
        return UserRoleDTO(user_id=assignment.user_id, role_id=assignment.role_id)

    async def agrant_permission(self, *, role_id: int, permission_id: int) -> RolePermissionDTO:
        """Grant a permission to a role, idempotently."""
        role_permission, _ = await RolePermission.objects.aget_or_create(
            role_id=role_id, permission_id=permission_id
        )
        return RolePermissionDTO(
            role_id=role_permission.role_id, permission_id=role_permission.permission_id
        )
def _role_dto(role: Role) -> RoleDTO:
    return RoleDTO(id=role.id, name=role.name)


def _permission_dto(permission: Permission) -> PermissionDTO:
    return PermissionDTO(id=permission.id, code=permission.code)
