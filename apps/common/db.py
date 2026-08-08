"""Synchronous transaction bridges for async repository methods."""

from __future__ import annotations

from collections.abc import Callable

from asgiref.sync import sync_to_async
from django.db import transaction


def _run_in_transaction[Result](
    fn: Callable[..., Result], args: tuple[object, ...], kwargs: dict[str, object]
) -> Result:
    with transaction.atomic():
        return fn(*args, **kwargs)


async def run_in_transaction[Result](
    fn: Callable[..., Result], /, *args: object, **kwargs: object
) -> Result:
    """Run synchronous ORM writes atomically on Django's sensitive DB thread.

    Django has no native async ``transaction.atomic`` context manager. Keeping the
    whole transaction in one ``thread_sensitive=True`` call preserves its connection
    and row-lock semantics.
    """
    return await sync_to_async(_run_in_transaction, thread_sensitive=True)(fn, args, kwargs)
