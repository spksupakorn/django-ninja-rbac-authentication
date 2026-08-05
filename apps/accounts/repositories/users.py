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
        return await self.aget_or_none(email__iexact=email)
