"""Value objects returned by the accounts persistence boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.accounts.models import User


@dataclass(frozen=True)
class UserDTO:
    """The non-secret user fields services may consume without an ORM instance."""

    id: int
    email: str
    is_active: bool
    is_staff: bool
    date_joined: datetime


@dataclass(frozen=True)
class CredentialsDTO:
    """The identity and credential material needed during login."""

    id: int
    email: str
    password_hash: str
    is_active: bool


def user_dto_from_model(user: User) -> UserDTO:
    """Detach the selected user fields from a Django model instance."""
    return UserDTO(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_staff=user.is_staff,
        date_joined=user.date_joined,
    )


def credentials_dto_from_model(user: User) -> CredentialsDTO:
    """Detach only the fields required to authenticate a user."""
    return CredentialsDTO(
        id=user.id,
        email=user.email,
        password_hash=user.password,
        is_active=user.is_active,
    )
