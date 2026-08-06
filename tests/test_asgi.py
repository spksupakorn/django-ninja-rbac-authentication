from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, patch

import pytest
from django.db.utils import OperationalError

from config.asgi import application


def _lifespan_receive(
    *events: dict[str, str],
) -> Callable[[], Awaitable[dict[str, str]]]:
    event_iterator = iter(events)

    async def receive() -> dict[str, str]:
        return next(event_iterator)

    return receive


@pytest.mark.asyncio
async def test_asgi_lifespan_completes_only_after_database_check() -> None:
    send = AsyncMock()

    with patch("config.asgi._database_is_ready", new_callable=AsyncMock):
        await application(
            {"type": "lifespan"},
            _lifespan_receive({"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}),
            send,
        )

    assert send.await_args_list == [
        (({"type": "lifespan.startup.complete"},), {}),
        (({"type": "lifespan.shutdown.complete"},), {}),
    ]


@pytest.mark.asyncio
async def test_asgi_lifespan_fails_when_database_is_unavailable() -> None:
    send = AsyncMock()

    with patch(
        "config.asgi._database_is_ready",
        new_callable=AsyncMock,
        side_effect=OperationalError("database unavailable"),
    ):
        await application(
            {"type": "lifespan"},
            _lifespan_receive({"type": "lifespan.startup"}),
            send,
        )

    send.assert_awaited_once_with(
        {
            "type": "lifespan.startup.failed",
            "message": "Database connection is unavailable.",
        }
    )
