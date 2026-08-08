"""Helpers for binding refresh-token families to request context."""

from __future__ import annotations

from hashlib import sha256


def device_hash(user_agent: str | None) -> str | None:
    """Return a stable hash for a non-empty normalized User-Agent."""
    if not user_agent or not (normalized := user_agent.strip().lower()):
        return None
    return sha256(normalized.encode()).hexdigest()
