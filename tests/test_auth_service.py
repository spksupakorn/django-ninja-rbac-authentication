from unittest.mock import AsyncMock

import pytest
from django.test import override_settings

from apps.audit.actions import AuditAction
from apps.audit.context import AuditContext
from apps.audit.models import AuditLog
from apps.authz.models import RefreshToken, Role
from apps.authz.security.jwt import decode_access_token
from apps.authz.services.auth import AuthService
from apps.common.exceptions import (
    EmailAlreadyExists,
    InvalidToken,
    RefreshTokenBindingMismatch,
    TokenReused,
)

CONTEXT = AuditContext()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_register_assigns_default_role_and_rejects_duplicate_email() -> None:
    await Role.objects.aget_or_create(name="user")
    service = AuthService()

    user = await service.register(email="User@Example.com", password="password", context=CONTEXT)

    assert user.email == "user@example.com"
    assert await service.authz.aget_user_role_names(user.id) == {"user"}
    with pytest.raises(EmailAlreadyExists):
        await service.register(email="user@example.com", password="password", context=CONTEXT)


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_refresh_rotates_a_token_within_its_family() -> None:
    await Role.objects.aget_or_create(name="user")
    service = AuthService()
    user = await service.register(email="user@example.com", password="password", context=CONTEXT)
    initial_pair = await service.login(
        email="user@example.com", password="password", context=CONTEXT
    )

    rotated_pair = await service.refresh(
        raw_refresh_token=initial_pair.refresh_token, context=CONTEXT
    )

    claims = decode_access_token(rotated_pair.access_token)
    tokens = [
        token async for token in RefreshToken.objects.filter(user_id=user.id).order_by("id")
    ]
    assert claims.subject == str(user.id)
    assert initial_pair.refresh_token != rotated_pair.refresh_token
    assert len(tokens) == 2
    assert tokens[0].revoked_at is not None
    assert tokens[1].parent_id == tokens[0].id
    assert tokens[1].family_id == tokens[0].family_id


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_reuse_of_a_rotated_token_revokes_its_full_family() -> None:
    await Role.objects.aget_or_create(name="user")
    service = AuthService()
    await service.register(email="user@example.com", password="password", context=CONTEXT)
    initial_pair = await service.login(
        email="user@example.com", password="password", context=CONTEXT
    )
    await service.refresh(raw_refresh_token=initial_pair.refresh_token, context=CONTEXT)

    with pytest.raises(TokenReused):
        await service.refresh(raw_refresh_token=initial_pair.refresh_token, context=CONTEXT)

    tokens = [token async for token in RefreshToken.objects.all()]
    assert len(tokens) == 2
    assert all(token.revoked_at is not None for token in tokens)


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_logout_revokes_the_presented_refresh_token() -> None:
    await Role.objects.aget_or_create(name="user")
    service = AuthService()
    await service.register(email="user@example.com", password="password", context=CONTEXT)
    token_pair = await service.login(
        email="user@example.com", password="password", context=CONTEXT
    )

    await service.logout(raw_refresh_token=token_pair.refresh_token, context=CONTEXT)

    stored_tokens = [token async for token in RefreshToken.objects.all()]
    assert len(stored_tokens) == 1
    assert stored_tokens[0].revoked_at is not None


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_refresh_rejects_an_unknown_token_and_logout_is_idempotent() -> None:
    service = AuthService()

    with pytest.raises(InvalidToken):
        await service.refresh(raw_refresh_token="unknown-token", context=CONTEXT)

    await service.logout(raw_refresh_token="unknown-token", context=CONTEXT)


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_refresh_device_mismatch_revokes_family_and_records_audit_event() -> None:
    await Role.objects.aget_or_create(name="user")
    blocklist = AsyncMock()
    service = AuthService(blocklist=blocklist)
    await service.register(email="user@example.com", password="password", context=CONTEXT)
    login_context = AuditContext(ip="192.0.2.1", user_agent="device-a")
    token_pair = await service.login(
        email="user@example.com", password="password", context=login_context
    )

    with pytest.raises(RefreshTokenBindingMismatch):
        await service.refresh(
            raw_refresh_token=token_pair.refresh_token,
            context=AuditContext(ip="192.0.2.2", user_agent="device-b"),
        )

    tokens = [token async for token in RefreshToken.objects.all()]
    audit_log = await AuditLog.objects.aget(action=AuditAction.TOKEN_BINDING_MISMATCH)
    assert all(token.revoked_at is not None for token in tokens)
    blocklist.revoke_user.assert_awaited_once()
    assert audit_log.outcome == "failure"
    assert set(audit_log.metadata) == {"family_id"}


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_refresh_ip_change_is_audited_without_revoking_access_tokens() -> None:
    await Role.objects.aget_or_create(name="user")
    blocklist = AsyncMock()
    service = AuthService(blocklist=blocklist)
    await service.register(email="user@example.com", password="password", context=CONTEXT)
    token_pair = await service.login(
        email="user@example.com",
        password="password",
        context=AuditContext(ip="192.0.2.1", user_agent="device-a"),
    )

    with override_settings(REFRESH_BIND_IP=True):
        await service.refresh(
            raw_refresh_token=token_pair.refresh_token,
            context=AuditContext(ip="198.51.100.2", user_agent="device-a"),
        )

    audit_log = await AuditLog.objects.aget(action=AuditAction.TOKEN_IP_CHANGED)
    blocklist.revoke_user.assert_not_awaited()
    assert audit_log.metadata == {
        "previous_ip": "192.0.2.0/24",
        "presented_ip": "198.51.100.0/24",
    }
