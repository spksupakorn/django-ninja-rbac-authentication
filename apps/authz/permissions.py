"""The permission catalog used by RBAC checks and database seed migrations."""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class PermissionCode(StrEnum):
    """Capabilities that can be granted to roles."""

    USER_CREATE = "user.create"
    USER_READ = "user.read"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    ROLE_ASSIGN = "role.assign"
    ROLE_READ = "role.read"
    PERMISSION_READ = "permission.read"
    AUDIT_READ = "audit.read"


class RoleName(StrEnum):
    """Roles seeded with every new deployment."""

    ADMIN = "admin"
    USER = "user"


PERMISSION_CATALOG: Final = tuple(permission.value for permission in PermissionCode)
DEFAULT_ROLE_PERMISSIONS: Final = {
    RoleName.ADMIN.value: PERMISSION_CATALOG,
    RoleName.USER.value: (),
}
