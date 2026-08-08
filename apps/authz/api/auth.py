"""JWT Bearer authentication and permission enforcement for Ninja routes."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from typing import Any

from asgiref.sync import async_to_sync
from django.http import HttpRequest
from ninja.security import HttpBearer

from apps.authz.security.blocklist import BlocklistService
from apps.authz.security.jwt import decode_access_token
from apps.common.exceptions import InvalidToken, PermissionDenied


@dataclass(frozen=True)
class Principal:
    """Authenticated identity made available as ``request.auth``."""

    user_id: int
    jti: str
    issued_at: datetime
    expires_at: datetime
    roles: frozenset[str]
    permissions: frozenset[str]


class JWTAuth(HttpBearer):
    """Authenticate an HS256 access token and reject access-token revocations."""

    def __init__(self, blocklist: BlocklistService | None = None) -> None:
        self._blocklist = blocklist or BlocklistService()

    def __call__(self, request: HttpRequest) -> Principal | None:
        """Bridge Ninja's synchronous auth callback interface to async checks."""
        auth_value = request.headers.get(self.header)
        if not auth_value:
            return None
        parts = auth_value.split(" ")
        if parts[0].lower() != self.openapi_scheme:
            return None
        return async_to_sync(self.authenticate)(request, " ".join(parts[1:]))

    async def authenticate(self, request: HttpRequest, token: str) -> Principal:
        """Decode a bearer token into an authorization principal."""
        del request
        claims = decode_access_token(token)
        try:
            user_id = int(claims.subject)
        except ValueError as exc:
            raise InvalidToken() from exc
        if user_id <= 0:
            raise InvalidToken()
        if await self._blocklist.is_blocked(claims.token_id, user_id, claims.issued_at):
            raise InvalidToken()
        return Principal(
            user_id=user_id,
            jti=claims.token_id,
            issued_at=claims.issued_at,
            expires_at=claims.expires_at,
            roles=claims.roles,
            permissions=claims.permissions,
        )


def require_permission(permission_code: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Guard a Ninja operation using permissions embedded in ``request.auth``."""

    def _check(request: HttpRequest) -> None:
        principal = getattr(request, "auth", None)
        if not isinstance(principal, Principal) or permission_code not in principal.permissions:
            raise PermissionDenied()

    def decorator(view: Callable[..., Any]) -> Callable[..., Any]:
        if inspect.iscoroutinefunction(view):

            @wraps(view)
            async def async_guarded_view(request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
                _check(request)
                return await view(request, *args, **kwargs)

            return async_guarded_view

        @wraps(view)
        def guarded_view(request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
            _check(request)
            return view(request, *args, **kwargs)

        return guarded_view

    return decorator
