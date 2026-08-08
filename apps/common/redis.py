"""Async Redis client shared by security services."""

from __future__ import annotations

import asyncio
from weakref import WeakKeyDictionary

from django.conf import settings
from redis.asyncio import Redis, from_url

_clients: WeakKeyDictionary[asyncio.AbstractEventLoop, Redis] = WeakKeyDictionary()


def get_redis_client() -> Redis:
    """Return an async Redis client scoped to the current event loop.

    redis-py's async connections are bound to the event loop that opens them.
    Keeping one client per loop preserves connection reuse in ASGI while making
    synchronous Django adapters, which create short-lived loops, safe too.
    """
    loop = asyncio.get_running_loop()
    client = _clients.get(loop)
    if client is None:
        client = from_url(settings.REDIS_URL, decode_responses=True)
        _clients[loop] = client
    return client
