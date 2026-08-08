"""Value objects returned by the authorization persistence boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class RoleDTO:
    id: int
    name: str


@dataclass(frozen=True)
class PermissionDTO:
    id: int
    code: str


@dataclass(frozen=True)
class UserRoleDTO:
    user_id: int
    role_id: int


@dataclass(frozen=True)
class RolePermissionDTO:
    role_id: int
    permission_id: int


@dataclass(frozen=True)
class RefreshTokenDTO:
    id: int
    user_id: int
    token_hash: str
    family_id: UUID
    parent_id: int | None
    device_hash: str | None
    issued_ip: str | None
    expires_at: datetime
    revoked_at: datetime | None
