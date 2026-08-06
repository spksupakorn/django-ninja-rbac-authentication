"""ASGI entry point that refuses startup before the database is reachable."""

import os
from collections.abc import Awaitable, Callable
from typing import Any

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

from asgiref.sync import sync_to_async
from django.core.asgi import get_asgi_application
from django.db import connections
from django.db.utils import OperationalError

django_application = get_asgi_application()


def _ensure_database_connection() -> None:
    """Open and close one connection to verify the configured database is ready."""
    connection = connections["default"]
    connection.ensure_connection()
    connection.close()


async def _database_is_ready() -> None:
    """Run Django's synchronous connection check outside the event loop."""
    await sync_to_async(_ensure_database_connection, thread_sensitive=True)()


async def application(
    scope: dict[str, Any],
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    """Serve HTTP normally and fail ASGI lifespan startup when the DB is unavailable."""
    if scope["type"] != "lifespan":
        await django_application(scope, receive, send)
        return

    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            try:
                await _database_is_ready()
            except OperationalError:
                await send(
                    {
                        "type": "lifespan.startup.failed",
                        "message": "Database connection is unavailable.",
                    }
                )
                return
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return
