"""Redis-backed access-token revocation with availability-first failure handling."""

from __future__ import annotations

import logging
import math
from datetime import datetime

from redis.asyncio import Redis

from apps.common.redis import get_redis_client

logger = logging.getLogger(__name__)


class BlocklistService:
    """Store revoked token IDs and per-user revocation epochs in Redis.

    Redis is deliberately fail-open: an unavailable blocklist must not make all
    authenticated requests unavailable.  Each failure is logged for alerting.
    """

    def __init__(self, redis_client: Redis | None = None) -> None:
        self._redis = redis_client

    async def block_token(self, jti: str, ttl: int) -> None:
        """Block one token until it would naturally expire."""
        if ttl <= 0:
            return
        try:
            await self._client().set(self._token_key(jti), "1", ex=ttl)
        except Exception:
            logger.warning("Unable to block access token in Redis", exc_info=True)

    async def revoke_user(self, user_id: int, at: datetime, ttl: int) -> None:
        """Invalidate tokens issued before ``at`` for the duration of their lifetime."""
        if ttl <= 0:
            return
        try:
            await self._client().set(
                self._user_epoch_key(user_id), math.ceil(at.timestamp()), ex=ttl
            )
        except Exception:
            logger.warning("Unable to revoke user tokens in Redis", exc_info=True)

    async def is_blocked(self, jti: str, user_id: int, issued_at: datetime) -> bool:
        """Return whether a token ID or its user's revocation epoch invalidates it."""
        try:
            token_blocked, user_epoch = await self._client().mget(
                self._token_key(jti), self._user_epoch_key(user_id)
            )
            if token_blocked is not None:
                return True
            return user_epoch is not None and issued_at.timestamp() < int(user_epoch)
        except Exception:
            logger.warning("Unable to check access-token blocklist in Redis", exc_info=True)
            return False

    @staticmethod
    def _token_key(jti: str) -> str:
        return f"bl:jti:{jti}"

    def _client(self) -> Redis:
        return self._redis or get_redis_client()

    @staticmethod
    def _user_epoch_key(user_id: int) -> str:
        return f"user_epoch:{user_id}"
