"""Tests for atomic refresh-token rotation and device binding."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone

from apps.authz.models import RefreshToken
from apps.authz.repositories.refresh_tokens import RefreshTokenRepository
from apps.authz.security.binding import device_hash
from tests.factories import RefreshTokenFactory


def test_device_hash_normalizes_user_agent() -> None:
    assert device_hash(None) is None
    assert device_hash("") is None
    assert device_hash("  ") is None
    assert device_hash("  Mozilla/5.0  ") == device_hash("mozilla/5.0")


def test_refresh_token_factory_hash_fits_model_column() -> None:
    assert len(RefreshTokenFactory.build().token_hash) == 64


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_rotate_matching_device_preserves_binding() -> None:
    repository = RefreshTokenRepository()
    user = await sync_to_async(get_user_model().objects.create_user)(
        email="user@example.com", password="password"
    )
    now = timezone.now()
    original_hash = "original"
    bound_device = device_hash("Mozilla/5.0")
    await repository.acreate(
        user_id=user.id,
        token_hash=original_hash,
        family_id=uuid4(),
        parent_id=None,
        expires_at=now + timedelta(days=1),
        device_hash=bound_device,
        issued_ip="192.0.2.1",
    )

    result = await repository.arotate(
        token_hash=original_hash,
        replacement_hash="replacement",
        replacement_expires_at=now + timedelta(days=1),
        rotated_at=now,
        presented_device_hash=bound_device,
        presented_ip="192.0.2.2",
    )

    assert result.outcome == "rotated"
    assert result.refresh_token is not None
    assert result.refresh_token.device_hash == bound_device
    assert result.refresh_token.issued_ip == "192.0.2.2"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_rotate_mismatched_device_revokes_entire_family() -> None:
    repository = RefreshTokenRepository()
    user = await sync_to_async(get_user_model().objects.create_user)(
        email="user@example.com", password="password"
    )
    now = timezone.now()
    family_id = uuid4()
    stored = await repository.acreate(
        user_id=user.id,
        token_hash="original",
        family_id=family_id,
        parent_id=None,
        expires_at=now + timedelta(days=1),
        device_hash=device_hash("device-a"),
    )
    await repository.acreate(
        user_id=user.id,
        token_hash="active-sibling",
        family_id=family_id,
        parent_id=stored.id,
        expires_at=now + timedelta(days=1),
        device_hash=device_hash("device-a"),
    )

    result = await repository.arotate(
        token_hash="original",
        replacement_hash="replacement",
        replacement_expires_at=now + timedelta(days=1),
        rotated_at=now,
        presented_device_hash=device_hash("device-b"),
    )

    tokens = [token async for token in RefreshToken.objects.filter(family_id=family_id)]
    assert result.outcome == "binding_mismatch"
    assert result.refresh_token is not None
    assert all(token.revoked_at is not None for token in tokens)


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_rotate_grandfathered_token_binds_replacement() -> None:
    repository = RefreshTokenRepository()
    user = await sync_to_async(get_user_model().objects.create_user)(
        email="user@example.com", password="password"
    )
    now = timezone.now()
    await repository.acreate(
        user_id=user.id,
        token_hash="original",
        family_id=uuid4(),
        parent_id=None,
        expires_at=now + timedelta(days=1),
    )
    presented_device = device_hash("device-a")

    result = await repository.arotate(
        token_hash="original",
        replacement_hash="replacement",
        replacement_expires_at=now + timedelta(days=1),
        rotated_at=now,
        presented_device_hash=presented_device,
        presented_ip="192.0.2.1",
    )

    assert result.outcome == "rotated"
    assert result.refresh_token is not None
    assert result.refresh_token.device_hash == presented_device
    assert result.refresh_token.issued_ip == "192.0.2.1"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_rotate_permits_mismatch_when_device_binding_is_disabled() -> None:
    repository = RefreshTokenRepository()
    user = await sync_to_async(get_user_model().objects.create_user)(
        email="user@example.com", password="password"
    )
    now = timezone.now()
    original = await repository.acreate(
        user_id=user.id,
        token_hash="original",
        family_id=uuid4(),
        parent_id=None,
        expires_at=now + timedelta(days=1),
        device_hash=device_hash("device-a"),
    )

    with override_settings(REFRESH_BIND_DEVICE=False):
        result = await repository.arotate(
            token_hash="original",
            replacement_hash="replacement",
            replacement_expires_at=now + timedelta(days=1),
            rotated_at=now,
            presented_device_hash=device_hash("device-b"),
        )

    assert result.outcome == "rotated"
    assert result.refresh_token is not None
    assert result.refresh_token.parent_id == original.id
