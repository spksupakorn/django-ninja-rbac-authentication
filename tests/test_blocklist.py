from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import AsyncMock

import pytest
from redis.asyncio import Redis

from apps.authz.security.blocklist import BlocklistService


def _service(redis_client: AsyncMock) -> BlocklistService:
    return BlocklistService(redis_client=cast(Redis, redis_client))


@pytest.mark.asyncio
async def test_blocked_jti_is_rejected() -> None:
    redis_client = AsyncMock()
    redis_client.mget.return_value = ["1", None]

    blocked = await _service(redis_client).is_blocked(
        "token-1", 42, datetime(2026, 8, 8, tzinfo=UTC)
    )

    assert blocked is True
    redis_client.mget.assert_awaited_once_with("bl:jti:token-1", "user_epoch:42")


@pytest.mark.asyncio
async def test_block_token_uses_remaining_token_ttl() -> None:
    redis_client = AsyncMock()

    await _service(redis_client).block_token("token-1", ttl=60)

    redis_client.set.assert_awaited_once_with("bl:jti:token-1", "1", ex=60)


@pytest.mark.asyncio
async def test_user_epoch_blocks_only_tokens_issued_before_it() -> None:
    redis_client = AsyncMock()
    epoch = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)
    redis_client.mget.return_value = [None, str(int(epoch.timestamp()))]
    service = _service(redis_client)

    assert await service.is_blocked("old-token", 42, epoch - timedelta(seconds=1)) is True
    assert await service.is_blocked("new-token", 42, epoch) is False


@pytest.mark.asyncio
async def test_revoke_user_stores_epoch_with_ttl() -> None:
    redis_client = AsyncMock()
    epoch = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)

    await _service(redis_client).revoke_user(42, epoch, ttl=900)

    redis_client.set.assert_awaited_once_with("user_epoch:42", int(epoch.timestamp()), ex=900)


@pytest.mark.asyncio
async def test_blocklist_ignores_expired_write_requests() -> None:
    redis_client = AsyncMock()
    service = _service(redis_client)

    await service.block_token("token-1", ttl=0)
    await service.revoke_user(42, datetime(2026, 8, 8, tzinfo=UTC), ttl=0)

    redis_client.set.assert_not_awaited()


@pytest.mark.asyncio
async def test_blocklist_write_failures_are_logged_and_fail_open(
    caplog: pytest.LogCaptureFixture,
) -> None:
    redis_client = AsyncMock()
    redis_client.set.side_effect = RuntimeError("Redis unavailable")
    service = _service(redis_client)

    with caplog.at_level(logging.WARNING, logger="apps.authz.security.blocklist"):
        await service.block_token("token-1", ttl=60)
        await service.revoke_user(42, datetime(2026, 8, 8, tzinfo=UTC), ttl=60)

    assert "Unable to block access token in Redis" in caplog.text
    assert "Unable to revoke user tokens in Redis" in caplog.text


@pytest.mark.asyncio
async def test_blocklist_check_fails_open_and_logs_redis_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    redis_client = AsyncMock()
    redis_client.mget.side_effect = RuntimeError("Redis unavailable")

    with caplog.at_level(logging.WARNING, logger="apps.authz.security.blocklist"):
        blocked = await _service(redis_client).is_blocked(
            "token-1", 42, datetime(2026, 8, 8, tzinfo=UTC)
        )

    assert blocked is False
    assert "Unable to check access-token blocklist in Redis" in caplog.text
    assert caplog.records[0].exc_info is not None
