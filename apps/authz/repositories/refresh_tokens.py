"""Async persistence operations for hashed refresh tokens."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import transaction

from apps.authz.models import RefreshToken


@dataclass(frozen=True)
class RefreshRotationResult:
    """The outcome of an atomic refresh-token rotation attempt."""

    outcome: Literal["rotated", "missing", "expired", "reused", "binding_mismatch"]
    refresh_token: RefreshToken | None = None
    previous_issued_ip: str | None = None


class RefreshTokenRepository:
    """Persist and revoke refresh-token rotation families."""

    async def aget_by_hash(self, token_hash: str) -> RefreshToken | None:
        """Look up a refresh token by its one-way hash."""
        try:
            return await RefreshToken.objects.aget(token_hash=token_hash)
        except RefreshToken.DoesNotExist:
            return None

    async def acreate(
        self,
        *,
        user_id: int,
        token_hash: str,
        family_id: UUID,
        parent_id: int | None,
        expires_at: datetime,
        device_hash: str | None = None,
        issued_ip: str | None = None,
    ) -> RefreshToken:
        """Store a newly issued refresh token."""
        return await RefreshToken.objects.acreate(
            user_id=user_id,
            token_hash=token_hash,
            family_id=family_id,
            parent_id=parent_id,
            expires_at=expires_at,
            device_hash=device_hash,
            issued_ip=issued_ip,
        )

    async def arevoke(self, token_id: int, revoked_at: datetime) -> None:
        """Revoke one refresh token if it is still active."""
        await RefreshToken.objects.filter(id=token_id, revoked_at__isnull=True).aupdate(
            revoked_at=revoked_at
        )

    async def arevoke_family(self, family_id: UUID, revoked_at: datetime) -> None:
        """Revoke every active token in a suspected-compromised family."""
        await RefreshToken.objects.filter(
            family_id=family_id, revoked_at__isnull=True
        ).aupdate(revoked_at=revoked_at)

    async def arevoke_user(self, user_id: int, revoked_at: datetime) -> None:
        """Revoke every active refresh token for a user."""
        await RefreshToken.objects.filter(user_id=user_id, revoked_at__isnull=True).aupdate(
            revoked_at=revoked_at
        )

    async def arotate(
        self,
        *,
        token_hash: str,
        replacement_hash: str,
        replacement_expires_at: datetime,
        rotated_at: datetime,
        presented_device_hash: str | None = None,
        presented_ip: str | None = None,
    ) -> RefreshRotationResult:
        """Atomically consume a refresh token and create its replacement."""
        return await sync_to_async(self._rotate, thread_sensitive=True)(
            token_hash=token_hash,
            replacement_hash=replacement_hash,
            replacement_expires_at=replacement_expires_at,
            rotated_at=rotated_at,
            presented_device_hash=presented_device_hash,
            presented_ip=presented_ip,
        )

    def _rotate(
        self,
        *,
        token_hash: str,
        replacement_hash: str,
        replacement_expires_at: datetime,
        rotated_at: datetime,
        presented_device_hash: str | None = None,
        presented_ip: str | None = None,
    ) -> RefreshRotationResult:
        """Run rotation under a row lock to make reuse detection race-safe."""
        with transaction.atomic():
            try:
                refresh_token = RefreshToken.objects.select_for_update().get(token_hash=token_hash)
            except RefreshToken.DoesNotExist:
                return RefreshRotationResult(outcome="missing")

            if refresh_token.revoked_at is not None:
                RefreshToken.objects.filter(
                    family_id=refresh_token.family_id, revoked_at__isnull=True
                ).update(revoked_at=rotated_at)
                return RefreshRotationResult(outcome="reused", refresh_token=refresh_token)
            if refresh_token.expires_at <= rotated_at:
                return RefreshRotationResult(outcome="expired")
            if (
                settings.REFRESH_BIND_DEVICE
                and refresh_token.device_hash is not None
                and refresh_token.device_hash != presented_device_hash
            ):
                RefreshToken.objects.filter(
                    family_id=refresh_token.family_id, revoked_at__isnull=True
                ).update(revoked_at=rotated_at)
                return RefreshRotationResult(
                    outcome="binding_mismatch", refresh_token=refresh_token
                )

            refresh_token.revoked_at = rotated_at
            refresh_token.save(update_fields=["revoked_at"])
            replacement = RefreshToken.objects.create(
                user_id=refresh_token.user_id,
                token_hash=replacement_hash,
                family_id=refresh_token.family_id,
                parent_id=refresh_token.id,
                expires_at=replacement_expires_at,
                device_hash=refresh_token.device_hash or presented_device_hash,
                issued_ip=presented_ip,
            )
            return RefreshRotationResult(
                outcome="rotated",
                refresh_token=replacement,
                previous_issued_ip=refresh_token.issued_ip,
            )
