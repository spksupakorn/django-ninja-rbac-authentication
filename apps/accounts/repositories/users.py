"""Async persistence operations for users."""

from __future__ import annotations

from apps.accounts.models import User
from apps.common.repositories import BaseRepository


class UserRepository(BaseRepository[User]):
    """Read and write users without leaking ORM queries to services."""

    def __init__(self) -> None:
        super().__init__(User)

    async def aget_by_email(self, email: str) -> User | None:
        """Look up an email identity without making callers know ORM syntax."""
        canonical_email = User.objects.normalize_email(email)
        return await self.aget_or_none(email=canonical_email)

    async def acreate_user(self, *, email: str, password_hash: str) -> User:
        """Persist a user with a password hash produced by the security layer."""
        canonical_email = User.objects.normalize_email(email)
        return await self.acreate(email=canonical_email, password=password_hash)

    async def aget_by_id(self, user_id: int) -> User | None:
        """Find a user by its primary key."""
        return await self.aget_or_none(id=user_id)

    async def alist(self, *, offset: int, limit: int) -> list[User]:
        """Return a stable page of users."""
        users = User.objects.order_by("id")[offset : offset + limit]
        return [user async for user in users]

    async def acount(self) -> int:
        """Count all users for pagination metadata."""
        return await User.objects.acount()

    async def aupdate(self, user_id: int, **fields: object) -> User | None:
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
