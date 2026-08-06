"""Administrative user-management use cases."""

from __future__ import annotations

from django.db import IntegrityError

from apps.accounts.models import User
from apps.accounts.repositories.users import UserRepository
from apps.authz.models import Permission, Role
from apps.authz.repositories.rbac import AuthzRepository
from apps.authz.security.passwords import hash_password
from apps.authz.services.auth import AuthService
from apps.common.exceptions import EmailAlreadyExists, ResourceNotFound


class AdminService:
    """Manage users and RBAC assignments without coupling to HTTP."""

    def __init__(
        self,
        *,
        users: UserRepository | None = None,
        authz: AuthzRepository | None = None,
        auth: AuthService | None = None,
    ) -> None:
        self.users = users or UserRepository()
        self.authz = authz or AuthzRepository()
        self.auth = auth or AuthService(users=self.users, authz=self.authz)

    async def create_user(self, *, email: str, password: str) -> User:
        """Create a user with the default role."""
        return await self.auth.register(email=email, password=password)

    async def get_user(self, user_id: int) -> User:
        """Return a user or raise a domain-level not-found error."""
        user = await self.users.aget_by_id(user_id)
        if user is None:
            raise ResourceNotFound("User not found.")
        return user

    async def list_users(self, *, offset: int, limit: int) -> tuple[list[User], int]:
        """Return a page of users and the total count."""
        return await self.users.alist(offset=offset, limit=limit), await self.users.acount()

    async def list_roles(self, *, offset: int, limit: int) -> tuple[list[Role], int]:
        """Return a page of roles and the total count."""
        return (
            await self.authz.alist_roles(offset=offset, limit=limit),
            await self.authz.acount_roles(),
        )

    async def list_permissions(
        self, *, offset: int, limit: int
    ) -> tuple[list[Permission], int]:
        """Return a page of permission catalog rows and the total count."""
        return (
            await self.authz.alist_permissions(offset=offset, limit=limit),
            await self.authz.acount_permissions(),
        )

    async def update_user(
        self,
        *,
        user_id: int,
        email: str | None = None,
        password: str | None = None,
        is_active: bool | None = None,
    ) -> User:
        """Update permitted user fields."""
        fields: dict[str, object] = {}
        if email is not None:
            fields["email"] = email
        if password is not None:
            fields["password"] = await hash_password(password)
        if is_active is not None:
            fields["is_active"] = is_active
        if not fields:
            return await self.get_user(user_id)
        try:
            user = await self.users.aupdate(user_id, **fields)
        except IntegrityError as exc:
            raise EmailAlreadyExists() from exc
        if user is None:
            raise ResourceNotFound("User not found.")
        return user

    async def delete_user(self, user_id: int) -> None:
        """Delete a user or signal that it did not exist."""
        if not await self.users.adelete(user_id):
            raise ResourceNotFound("User not found.")

    async def assign_role(self, *, user_id: int, role_id: int) -> None:
        """Assign a role to an existing user."""
        await self.get_user(user_id)
        role = await self.authz.aget_role_by_id(role_id)
        if role is None:
            raise ResourceNotFound("Role not found.")
        await self.authz.aassign_role(user_id=user_id, role_id=role.id)
