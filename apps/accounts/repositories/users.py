"""Async persistence operations for users."""

from __future__ import annotations

from apps.accounts.models import User
from apps.accounts.repositories.dtos import (
    CredentialsDTO,
    UserDTO,
    credentials_dto_from_model,
    user_dto_from_model,
)


class UserRepository:
    """Read and write users without leaking ORM queries to services."""

    async def aget_credentials(self, email: str) -> CredentialsDTO | None:
        """Return only the credential fields needed by the login use case."""
        canonical_email = User.objects.normalize_email(email)
        try:
            return credentials_dto_from_model(await User.objects.aget(email=canonical_email))
        except User.DoesNotExist:
            return None

    async def acreate_user(self, *, email: str, password_hash: str) -> UserDTO:
        """Persist a user with a password hash produced by the security layer."""
        canonical_email = User.objects.normalize_email(email)
        user = await User.objects.acreate(email=canonical_email, password=password_hash)
        return user_dto_from_model(user)

    async def acreate(self, **fields: object) -> UserDTO:
        """Create a user for repository callers that provide complete fields."""
        if "email" in fields:
            fields["email"] = User.objects.normalize_email(str(fields["email"]))
        return user_dto_from_model(await User.objects.acreate(**fields))

    async def aget_by_id(self, user_id: int) -> UserDTO | None:
        """Find a user by its primary key."""
        try:
            return user_dto_from_model(await User.objects.aget(id=user_id))
        except User.DoesNotExist:
            return None

    async def alist(self, *, offset: int, limit: int) -> list[UserDTO]:
        """Return a stable page of users."""
        users = User.objects.order_by("id")[offset : offset + limit]
        return [user_dto_from_model(user) async for user in users]

    async def acount(self) -> int:
        """Count all users for pagination metadata."""
        return await User.objects.acount()

    async def aupdate(self, user_id: int, **fields: object) -> UserDTO | None:
        """Update a user and return its current state."""
        if "email" in fields:
            fields["email"] = User.objects.normalize_email(str(fields["email"]))
        updated = await User.objects.filter(id=user_id).aupdate(**fields)
        if not updated:
            return None
        return await self.aget_by_id(user_id)

    async def adelete(self, user_id: int) -> bool:
        """Delete a user by primary key."""
        deleted, _ = await User.objects.filter(id=user_id).adelete()
        return deleted > 0
