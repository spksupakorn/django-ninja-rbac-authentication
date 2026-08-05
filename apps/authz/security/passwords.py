"""Async-safe password hashing helpers."""

from __future__ import annotations

from asgiref.sync import sync_to_async
from django.contrib.auth.hashers import check_password, make_password

_DUMMY_PASSWORD_HASH = make_password("not-a-real-password")


async def hash_password(password: str) -> str:
    """Hash a password off the event loop using Django's configured hasher."""
    return await sync_to_async(make_password, thread_sensitive=False)(password)


async def verify_password(password: str, encoded: str | None) -> bool:
    """Verify a password, performing a dummy check when no hash is available."""
    password_hash = encoded or _DUMMY_PASSWORD_HASH
    is_valid = await sync_to_async(check_password, thread_sensitive=False)(
        password, password_hash
    )
    return is_valid if encoded else False
