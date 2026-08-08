"""Authentication use cases built from repositories and security primitives."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, replace
from uuid import UUID, uuid4

from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.repositories.dtos import UserDTO
from apps.accounts.repositories.users import UserRepository
from apps.audit.actions import AuditAction
from apps.audit.context import AuditContext
from apps.audit.services import AuditService, mask_ip
from apps.authz.repositories.rbac import AuthzRepository
from apps.authz.repositories.refresh_tokens import RefreshTokenRepository
from apps.authz.security.binding import device_hash
from apps.authz.security.blocklist import BlocklistService
from apps.authz.security.jwt import encode_access_token
from apps.authz.security.passwords import hash_password, verify_password
from apps.common.exceptions import (
    EmailAlreadyExists,
    InvalidCredentials,
    InvalidToken,
    RefreshTokenBindingMismatch,
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
        audit: AuditService | None = None,
        blocklist: BlocklistService | None = None,
    ) -> None:
        self.users = users or UserRepository()
        self.authz = authz or AuthzRepository()
        self.refresh_tokens = refresh_tokens or RefreshTokenRepository()
        self.audit = audit or AuditService()
        self.blocklist = blocklist or BlocklistService()

    async def register(
        self,
        *,
        email: str,
        password: str,
        context: AuditContext,
        record_registration: bool = True,
    ) -> UserDTO:
        """Register a user and assign the configured default role."""
        default_role = await self.authz.aget_role_by_name(settings.DEFAULT_USER_ROLE)
        if default_role is None:
            raise RuntimeError("The configured default user role does not exist")

        password_hash = await hash_password(password)
        try:
            user = await self.authz.acreate_user_with_role(
                email=email, password_hash=password_hash, role_id=default_role.id
            )
        except IntegrityError as exc:
            raise EmailAlreadyExists() from exc
        if record_registration:
            await self.audit.record(AuditAction.REGISTER, context=_context_for_user(context, user))
        return user

    async def login(self, *, email: str, password: str, context: AuditContext) -> TokenPair:
        """Verify credentials and issue a new refresh-token family."""
        credentials = await self.users.aget_credentials(email)
        is_valid = await verify_password(
            password, credentials.password_hash if credentials else None
        )
        if credentials is None or not credentials.is_active or not is_valid:
            await self.audit.record(
                AuditAction.LOGIN_FAILURE,
                context=context,
                outcome="failure",
                metadata={"email": email},
            )
            raise InvalidCredentials()
        token_pair = await self._issue_token_pair(
            user_id=credentials.id, family_id=uuid4(), parent_id=None, context=context
        )
        await self.audit.record(
            AuditAction.LOGIN_SUCCESS,
            context=replace(context, actor_id=credentials.id, actor_email=credentials.email),
        )
        return token_pair

    async def refresh(self, *, raw_refresh_token: str, context: AuditContext) -> TokenPair:
        """Rotate a refresh token, revoking its full family on detected reuse."""
        now = timezone.now()
        replacement_refresh_token = secrets.token_urlsafe(48)
        rotation = await self.refresh_tokens.arotate(
            token_hash=_hash_refresh_token(raw_refresh_token),
            replacement_hash=_hash_refresh_token(replacement_refresh_token),
            replacement_expires_at=now + settings.REFRESH_TOKEN_LIFETIME,
            rotated_at=now,
            presented_device_hash=device_hash(context.user_agent),
            presented_ip=context.ip,
        )
        if rotation.outcome == "binding_mismatch":
            if rotation.refresh_token is not None:
                await self.blocklist.revoke_user(
                    rotation.refresh_token.user_id,
                    now,
                    ttl=_access_token_ttl_seconds(),
                )
                await self.audit.record(
                    AuditAction.TOKEN_BINDING_MISMATCH,
                    context=replace(context, actor_id=rotation.refresh_token.user_id),
                    outcome="failure",
                    metadata={"family_id": str(rotation.refresh_token.family_id)},
                )
            raise RefreshTokenBindingMismatch()
        if rotation.outcome == "reused":
            if rotation.refresh_token is not None:
                await self.blocklist.revoke_user(
                    rotation.refresh_token.user_id,
                    now,
                    ttl=_access_token_ttl_seconds(),
                )
                await self.audit.record(
                    AuditAction.TOKEN_REUSE_DETECTED,
                    context=replace(context, actor_id=rotation.refresh_token.user_id),
                    outcome="failure",
                    metadata={"family_id": str(rotation.refresh_token.family_id)},
                )
            raise TokenReused()
        if rotation.outcome in {"missing", "expired"}:
            raise InvalidToken()
        if rotation.refresh_token is None:
            raise RuntimeError("A successful refresh rotation must produce a token")

        if (
            settings.REFRESH_BIND_IP
            and rotation.previous_issued_ip is not None
            and rotation.previous_issued_ip != context.ip
        ):
            await self.audit.record(
                AuditAction.TOKEN_IP_CHANGED,
                context=replace(context, actor_id=rotation.refresh_token.user_id),
                metadata={
                    "previous_ip": mask_ip(rotation.previous_issued_ip),
                    "presented_ip": mask_ip(context.ip),
                },
            )

        roles = await self.authz.aget_user_role_names(rotation.refresh_token.user_id)
        permissions = await self.authz.aget_user_permission_codes(rotation.refresh_token.user_id)
        token_pair = TokenPair(
            access_token=encode_access_token(
                subject=rotation.refresh_token.user_id,
                roles=roles,
                permissions=permissions,
            ),
            refresh_token=replacement_refresh_token,
        )
        await self.audit.record(
            AuditAction.TOKEN_REFRESHED,
            context=replace(context, actor_id=rotation.refresh_token.user_id),
            metadata={"family_id": str(rotation.refresh_token.family_id)},
        )
        return token_pair

    async def logout(
        self,
        *,
        raw_refresh_token: str,
        context: AuditContext,
        access_token_jti: str | None = None,
        access_token_ttl: int | None = None,
    ) -> None:
        """Revoke one refresh token; unknown tokens make logout idempotent."""
        if access_token_jti is not None and access_token_ttl is not None:
            await self.blocklist.block_token(access_token_jti, access_token_ttl)
        token_hash = _hash_refresh_token(raw_refresh_token)
        refresh_token = await self.refresh_tokens.aget_by_hash(token_hash)
        if refresh_token is not None:
            await self.refresh_tokens.arevoke(refresh_token.id, timezone.now())
            await self.audit.record(
                AuditAction.LOGOUT,
                context=replace(context, actor_id=refresh_token.user_id),
                metadata={"family_id": str(refresh_token.family_id)},
            )

    async def logout_all(self, *, user_id: int, context: AuditContext) -> None:
        """Revoke every refresh and access token belonging to a user."""
        now = timezone.now()
        await self.blocklist.revoke_user(user_id, now, ttl=_access_token_ttl_seconds())
        await self.refresh_tokens.arevoke_user(user_id, now)
        await self.audit.record(
            AuditAction.LOGOUT,
            context=replace(context, actor_id=user_id),
            metadata={"scope": "all"},
        )

    async def aget_active_email(self, user_id: int) -> str:
        """Return the identity's email, rejecting tokens for deleted users."""
        user = await self.users.aget_by_id(user_id)
        if user is None:
            raise InvalidToken()
        return user.email

    async def _issue_token_pair(
        self, *, user_id: int, family_id: UUID, parent_id: int | None, context: AuditContext
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
            device_hash=device_hash(context.user_agent),
            issued_ip=context.ip,
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


def _access_token_ttl_seconds() -> int:
    """Return the maximum useful Redis lifetime for access-token revocations."""
    return max(1, int(settings.ACCESS_TOKEN_LIFETIME.total_seconds()))


def _context_for_user(context: AuditContext, user: UserDTO) -> AuditContext:
    """Keep the request data while snapshotting the actor that just authenticated."""
    return replace(context, actor_id=user.id, actor_email=user.email)
