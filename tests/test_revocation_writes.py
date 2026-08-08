from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import ANY, AsyncMock
from uuid import uuid4

import pytest
from django.conf import settings

from apps.accounts.services.admin import AdminService
from apps.audit.context import AuditContext
from apps.authz.models import RefreshToken
from apps.authz.repositories.refresh_tokens import RefreshRotationResult
from apps.authz.services.auth import AuthService
from apps.common.exceptions import RefreshTokenBindingMismatch, TokenReused


def _access_ttl() -> int:
    return int(settings.ACCESS_TOKEN_LIFETIME.total_seconds())


@pytest.mark.asyncio
async def test_logout_blocks_the_current_access_token() -> None:
    refresh_tokens = AsyncMock()
    refresh_tokens.aget_by_hash.return_value = SimpleNamespace(id=3, user_id=42, family_id=uuid4())
    blocklist = AsyncMock()
    service = AuthService(refresh_tokens=refresh_tokens, audit=AsyncMock(), blocklist=blocklist)

    await service.logout(
        raw_refresh_token="refresh-token",
        context=AuditContext(),
        access_token_jti="access-jti",
        access_token_ttl=123,
    )

    blocklist.block_token.assert_awaited_once_with("access-jti", 123)
    refresh_tokens.arevoke.assert_awaited_once_with(3, ANY)


@pytest.mark.asyncio
async def test_logout_all_revokes_access_and_refresh_tokens() -> None:
    refresh_tokens = AsyncMock()
    blocklist = AsyncMock()
    service = AuthService(refresh_tokens=refresh_tokens, audit=AsyncMock(), blocklist=blocklist)

    await service.logout_all(user_id=42, context=AuditContext())

    blocklist.revoke_user.assert_awaited_once_with(42, ANY, ttl=_access_ttl())
    refresh_tokens.arevoke_user.assert_awaited_once_with(42, ANY)


@pytest.mark.asyncio
async def test_refresh_reuse_revokes_all_access_tokens_for_the_user() -> None:
    refresh_tokens = AsyncMock()
    refresh_tokens.arotate.return_value = RefreshRotationResult(
        outcome="reused",
        refresh_token=cast(RefreshToken, SimpleNamespace(user_id=42, family_id=uuid4())),
    )
    blocklist = AsyncMock()
    service = AuthService(refresh_tokens=refresh_tokens, audit=AsyncMock(), blocklist=blocklist)

    with pytest.raises(TokenReused):
        await service.refresh(raw_refresh_token="reused-token", context=AuditContext())

    blocklist.revoke_user.assert_awaited_once_with(42, ANY, ttl=_access_ttl())


@pytest.mark.asyncio
async def test_refresh_binding_mismatch_revokes_all_access_tokens_for_the_user() -> None:
    refresh_tokens = AsyncMock()
    refresh_tokens.arotate.return_value = RefreshRotationResult(
        outcome="binding_mismatch",
        refresh_token=cast(RefreshToken, SimpleNamespace(user_id=42, family_id=uuid4())),
    )
    blocklist = AsyncMock()
    audit = AsyncMock()
    service = AuthService(refresh_tokens=refresh_tokens, audit=audit, blocklist=blocklist)

    with pytest.raises(RefreshTokenBindingMismatch):
        await service.refresh(raw_refresh_token="mismatched-token", context=AuditContext())

    blocklist.revoke_user.assert_awaited_once_with(42, ANY, ttl=_access_ttl())
    audit.record.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_deactivation_revokes_user_access_tokens() -> None:
    users = AsyncMock()
    users.aupdate.return_value = SimpleNamespace(id=42, is_active=False)
    blocklist = AsyncMock()
    service = AdminService(users=users, audit=AsyncMock(), blocklist=blocklist)

    user = await service.update_user(user_id=42, is_active=False, context=AuditContext())

    assert user.is_active is False
    blocklist.revoke_user.assert_awaited_once_with(42, ANY, ttl=_access_ttl())
