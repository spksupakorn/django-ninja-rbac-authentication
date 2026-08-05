"""JWT Bearer authentication and permission enforcement for Ninja routes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any

from django.http import HttpRequest
from ninja.security import HttpBearer

from apps.authz.security.jwt import decode_access_token
from apps.common.exceptions import InvalidToken, PermissionDenied


@dataclass(frozen=True)
class Principal:
    """Authenticated identity made available as ``request.auth``."""

    user_id: int
    roles: frozenset[str]
    permissions: frozenset[str]


class JWTAuth(HttpBearer):
    """Authenticate an HS256 access token without a database lookup."""

    def authenticate(self, request: HttpRequest, token: str) -> Principal:
        """Decode a bearer token into an authorization principal."""
        del request
        claims = decode_access_token(token)
        try:
            user_id = int(claims.subject)
        except ValueError as exc:
            raise InvalidToken() from exc
        if user_id <= 0:
            raise InvalidToken()
        return Principal(
            user_id=user_id,
            roles=claims.roles,
            permissions=claims.permissions,
        )


def require_permission(permission_code: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Guard a Ninja operation using permissions embedded in ``request.auth``."""

    def decorator(view: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view)
        def guarded_view(request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
            principal = request.auth
            if not isinstance(principal, Principal) or permission_code not in principal.permissions:
                raise PermissionDenied()
            return view(request, *args, **kwargs)

        return guarded_view

    return decorator
