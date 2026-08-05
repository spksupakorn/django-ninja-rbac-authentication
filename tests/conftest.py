"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from asgiref.sync import sync_to_async
from django.db import connections


@pytest.fixture(autouse=True)
async def close_database_connections_after_test() -> AsyncIterator[None]:
    """Close connections opened by async ORM work before pytest-django teardown."""
    yield
    await sync_to_async(connections.close_all, thread_sensitive=True)()
