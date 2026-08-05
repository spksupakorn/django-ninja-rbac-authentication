"""HS256 access-token encoding and validation."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from django.conf import settings
from jwt import InvalidTokenError

from apps.common.exceptions import InvalidToken


@dataclass(frozen=True)
class AccessTokenClaims:
    """Validated claims used by the authorization layer."""

    subject: str
    expires_at: datetime
    issued_at: datetime
    token_id: str
    roles: frozenset[str]
    permissions: frozenset[str]


def encode_access_token(
    *,
    subject: int | str,
    roles: Collection[str],
    permissions: Collection[str],
    secret: str | None = None,
    lifetime: timedelta | None = None,
    now: datetime | None = None,
) -> str:
    """Create a short-lived HS256 access token with RBAC claims."""
    issued_at = now or datetime.now(UTC)
    if issued_at.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    payload = {
        "sub": str(subject),
        "exp": issued_at + (lifetime or settings.ACCESS_TOKEN_LIFETIME),
        "iat": issued_at,
        "jti": str(uuid4()),
        "roles": sorted(set(roles)),
        "perms": sorted(set(permissions)),
    }
    signing_secret = secret if secret is not None else settings.JWT_SECRET.get_secret_value()
    return jwt.encode(payload, signing_secret, algorithm="HS256")


def decode_access_token(token: str, *, secret: str | None = None) -> AccessTokenClaims:
    """Validate an HS256 access token and return its typed claims."""
    signing_secret = secret if secret is not None else settings.JWT_SECRET.get_secret_value()
    try:
        payload = jwt.decode(
            token,
            signing_secret,
            algorithms=["HS256"],
            options={"require": ["sub", "exp", "iat", "jti", "roles", "perms"]},
        )
        return _parse_claims(payload)
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise InvalidToken() from exc


def _parse_claims(payload: dict[str, object]) -> AccessTokenClaims:
    """Check non-standard claims after PyJWT validates registered claims."""
    subject = payload["sub"]
    token_id = payload["jti"]
    roles = payload["roles"]
    permissions = payload["perms"]
    issued_at = payload["iat"]
    expires_at = payload["exp"]

    if not isinstance(subject, str) or not subject:
        raise ValueError("sub must be a non-empty string")
    if not isinstance(token_id, str) or not token_id:
        raise ValueError("jti must be a non-empty string")
    if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
        raise ValueError("roles must be a list of strings")
    if not isinstance(permissions, list) or not all(
        isinstance(permission, str) for permission in permissions
    ):
        raise ValueError("perms must be a list of strings")
    if not isinstance(issued_at, int) or not isinstance(expires_at, int):
        raise ValueError("iat and exp must be integer timestamps")

    return AccessTokenClaims(
        subject=subject,
        expires_at=datetime.fromtimestamp(expires_at, UTC),
        issued_at=datetime.fromtimestamp(issued_at, UTC),
        token_id=token_id,
        roles=frozenset(roles),
        permissions=frozenset(permissions),
    )
