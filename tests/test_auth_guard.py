from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory
from ninja import NinjaAPI
from ninja.testing import TestAsyncClient, TestClient

from apps.authz.api.auth import JWTAuth, Principal, require_permission
from apps.authz.security.jwt import encode_access_token
from apps.common.exceptions import DomainError, InvalidToken, PermissionDenied


def _protected_api() -> NinjaAPI:
    api = NinjaAPI(urls_namespace="auth-guard-test")

    @api.exception_handler(DomainError)
    def handle_domain_error(request: HttpRequest, exc: DomainError) -> HttpResponse:
        return api.create_response(request, {"code": exc.code}, status=exc.status_code)

    @api.get("/protected", auth=JWTAuth())
    @require_permission("user.read")
    def protected(request: HttpRequest) -> dict[str, bool]:
        del request
        return {"ok": True}

    @api.get("/async-protected", auth=JWTAuth())
    @require_permission("user.read")
    async def async_protected(request: HttpRequest) -> dict[str, bool]:
        del request
        return {"ok": True}

    return api


@pytest.mark.asyncio
async def test_jwt_auth_returns_principal_from_bearer_token() -> None:
    token = encode_access_token(subject=42, roles={"user"}, permissions={"user.read"})
    request = RequestFactory().get("/api/protected")
    blocklist = AsyncMock()
    blocklist.is_blocked.return_value = False

    principal = await JWTAuth(blocklist=blocklist).authenticate(request, token)

    assert principal.user_id == 42
    assert principal.roles == frozenset({"user"})
    assert principal.permissions == frozenset({"user.read"})
    assert principal.jti
    assert principal.issued_at.tzinfo is UTC
    assert principal.expires_at > principal.issued_at
    blocklist.is_blocked.assert_awaited_once_with(principal.jti, 42, principal.issued_at)


@pytest.mark.asyncio
async def test_jwt_auth_rejects_non_numeric_subject() -> None:
    token = encode_access_token(subject="not-a-user-id", roles=[], permissions=[])

    with pytest.raises(InvalidToken):
        await JWTAuth().authenticate(RequestFactory().get("/api/protected"), token)


@pytest.mark.asyncio
async def test_jwt_auth_rejects_a_blocked_token() -> None:
    token = encode_access_token(subject=42, roles={"user"}, permissions={"user.read"})
    blocklist = AsyncMock()
    blocklist.is_blocked.return_value = True

    with pytest.raises(InvalidToken):
        await JWTAuth(blocklist=blocklist).authenticate(
            RequestFactory().get("/api/protected"), token
        )


@pytest.mark.asyncio
async def test_jwt_auth_allows_when_blocklist_fails_open() -> None:
    token = encode_access_token(subject=42, roles={"user"}, permissions={"user.read"})
    blocklist = AsyncMock()
    blocklist.is_blocked.return_value = False

    principal = await JWTAuth(blocklist=blocklist).authenticate(
        RequestFactory().get("/api/protected"), token
    )

    assert principal.user_id == 42


def test_permission_guard_rejects_missing_permission() -> None:
    @require_permission("user.read")
    def protected(request: HttpRequest) -> dict[str, bool]:
        return {"ok": True}

    request = RequestFactory().get("/api/protected")
    request.auth = Principal(
        user_id=42,
        jti="token-1",
        issued_at=datetime(2026, 8, 8, tzinfo=UTC),
        expires_at=datetime(2026, 8, 8, 1, tzinfo=UTC),
        roles=frozenset({"user"}),
        permissions=frozenset(),
    )

    with pytest.raises(PermissionDenied):
        protected(request)


def test_permission_guard_allows_granted_permission() -> None:
    @require_permission("user.read")
    def protected(request: HttpRequest) -> dict[str, bool]:
        return {"ok": True}

    request = RequestFactory().get("/api/protected")
    request.auth = Principal(
        user_id=42,
        jti="token-1",
        issued_at=datetime(2026, 8, 8, tzinfo=UTC),
        expires_at=datetime(2026, 8, 8, 1, tzinfo=UTC),
        roles=frozenset({"user"}),
        permissions=frozenset({"user.read"}),
    )

    assert protected(request) == {"ok": True}


def test_protected_route_returns_401_without_a_bearer_token() -> None:
    response = TestClient(_protected_api()).get("/protected")

    assert response.status_code == 401


def test_protected_route_returns_403_without_required_permission() -> None:
    token = encode_access_token(subject=42, roles={"user"}, permissions=[])
    response = TestClient(_protected_api()).get(
        "/protected", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_async_protected_route_allows_granted_permission() -> None:
    token = encode_access_token(subject=42, roles={"user"}, permissions={"user.read"})
    response = await cast(
        Awaitable[Any],
        TestAsyncClient(_protected_api()).get(
            "/async-protected", headers={"Authorization": f"Bearer {token}"}
        ),
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


@pytest.mark.asyncio
async def test_async_protected_route_returns_403_without_required_permission() -> None:
    token = encode_access_token(subject=42, roles={"user"}, permissions=[])
    response = await cast(
        Awaitable[Any],
        TestAsyncClient(_protected_api()).get(
            "/async-protected", headers={"Authorization": f"Bearer {token}"}
        ),
    )

    assert response.status_code == 403
