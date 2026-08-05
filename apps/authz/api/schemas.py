"""HTTP schemas for authentication and administrative RBAC APIs."""

from __future__ import annotations

from ninja import Field, ModelSchema, Schema
from pydantic import EmailStr

from apps.accounts.models import User
from apps.authz.models import Permission, Role


class RegisterIn(Schema):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(RegisterIn):
    pass


class RefreshIn(Schema):
    refresh_token: str = Field(min_length=1)


class LogoutIn(RefreshIn):
    pass


class UserUpdateIn(Schema):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    is_active: bool | None = None


class AssignRoleIn(Schema):
    role_id: int = Field(gt=0)


class TokenPairOut(Schema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MeOut(Schema):
    id: int
    roles: list[str]
    permissions: list[str]


class UserOut(ModelSchema):
    class Meta:
        model = User
        fields = ["id", "email", "is_active", "is_staff", "date_joined"]


class RoleOut(ModelSchema):
    class Meta:
        model = Role
        fields = ["id", "name"]


class PermissionOut(ModelSchema):
    class Meta:
        model = Permission
        fields = ["id", "code"]


class UsersPageOut(Schema):
    items: list[UserOut]
    total: int
    offset: int
    limit: int


class RolesPageOut(Schema):
    items: list[RoleOut]
    total: int
    offset: int
    limit: int


class PermissionsPageOut(Schema):
    items: list[PermissionOut]
    total: int
    offset: int
    limit: int
