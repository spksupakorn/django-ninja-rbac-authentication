"""Authentication use cases built from repositories and security primitives."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from uuid import UUID, uuid4

from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.repositories.users import UserRepository
from apps.authz.repositories.rbac import AuthzRepository
from apps.authz.repositories.refresh_tokens import RefreshTokenRepository
from apps.authz.security.jwt import encode_access_token
from apps.authz.security.passwords import hash_password, verify_password
from apps.common.exceptions import (
    EmailAlreadyExists,
    InvalidCredentials,
    InvalidToken,
    TokenReused,
)


@dataclass(frozen=True)
class TokenPair:
    """The access and refresh values returned by authentication use cases."""

    access_token: str
    refresh_token: str


class AuthService:
    """Register users and manage login, refresh rotation, and logout."""

    def __init__(
        self,
        *,
        users: UserRepository | None = None,
        authz: AuthzRepository | None = None,
        refresh_tokens: RefreshTokenRepository | None = None,
    ) -> None:
        self.users = users or UserRepository()
        self.authz = authz or AuthzRepository()
        self.refresh_tokens = refresh_tokens or RefreshTokenRepository()

    async def register(self, *, email: str, password: str) -> User:
        """Register a user and assign the configured default role."""
        default_role = await self.authz.aget_role_by_name(settings.DEFAULT_USER_ROLE)
        if default_role is None:
            raise RuntimeError("The configured default user role does not exist")

        password_hash = await hash_password(password)
        try:
            return await self.authz.acreate_user_with_role(
                email=email, password_hash=password_hash, role_id=default_role.id
            )
        except IntegrityError as exc:
            raise EmailAlreadyExists() from exc

    async def login(self, *, email: str, password: str) -> TokenPair:
        """Verify credentials and issue a new refresh-token family."""
        user = await self.users.aget_by_email(email)
        is_valid = await verify_password(password, user.password if user else None)
        if user is None or not user.is_active or not is_valid:
            raise InvalidCredentials()
        return await self._issue_token_pair(user_id=user.id, family_id=uuid4(), parent_id=None)

    async def refresh(self, *, raw_refresh_token: str) -> TokenPair:
        """Rotate a refresh token, revoking its full family on detected reuse."""
        now = timezone.now()
        replacement_refresh_token = secrets.token_urlsafe(48)
        rotation = await self.refresh_tokens.arotate(
            token_hash=_hash_refresh_token(raw_refresh_token),
            replacement_hash=_hash_refresh_token(replacement_refresh_token),
            replacement_expires_at=now + settings.REFRESH_TOKEN_LIFETIME,
            rotated_at=now,
        )
        if rotation.outcome == "reused":
            raise TokenReused()
        if rotation.outcome in {"missing", "expired"}:
            raise InvalidToken()
        if rotation.refresh_token is None:
            raise RuntimeError("A successful refresh rotation must produce a token")

        roles = await self.authz.aget_user_role_names(rotation.refresh_token.user_id)
        permissions = await self.authz.aget_user_permission_codes(rotation.refresh_token.user_id)
        return TokenPair(
            access_token=encode_access_token(
                subject=rotation.refresh_token.user_id,
                roles=roles,
                permissions=permissions,
            ),
            refresh_token=replacement_refresh_token,
        )

    async def logout(self, *, raw_refresh_token: str) -> None:
        """Revoke one refresh token; unknown tokens make logout idempotent."""
        token_hash = _hash_refresh_token(raw_refresh_token)
        refresh_token = await self.refresh_tokens.aget_by_hash(token_hash)
        if refresh_token is not None:
            await self.refresh_tokens.arevoke(refresh_token.id, timezone.now())

    async def _issue_token_pair(
        self, *, user_id: int, family_id: UUID, parent_id: int | None
    ) -> TokenPair:
        roles = await self.authz.aget_user_role_names(user_id)
        permissions = await self.authz.aget_user_permission_codes(user_id)
        raw_refresh_token = secrets.token_urlsafe(48)
        await self.refresh_tokens.acreate(
            user_id=user_id,
            token_hash=_hash_refresh_token(raw_refresh_token),
            family_id=family_id,
            parent_id=parent_id,
            expires_at=timezone.now() + settings.REFRESH_TOKEN_LIFETIME,
        )
        return TokenPair(
            access_token=encode_access_token(
                subject=user_id,
                roles=roles,
                permissions=permissions,
            ),
            refresh_token=raw_refresh_token,
        )


def _hash_refresh_token(raw_refresh_token: str) -> str:
    """Return the fixed-size, one-way database representation of a token."""
    return hashlib.sha256(raw_refresh_token.encode("utf-8")).hexdigest()
