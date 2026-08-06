import json
from typing import cast

import pytest
from django.core.cache import cache
from django.http import HttpResponse
from django.test import Client

from apps.authz.models import Role
from apps.authz.permissions import PERMISSION_CATALOG
from apps.authz.security.jwt import encode_access_token
from tests.factories import RoleFactory


def _json_post(
    client: Client, path: str, payload: dict[str, object], **headers: str
) -> HttpResponse:
    return client.post(
        path,
        data=json.dumps(payload),
        content_type="application/json",
        **headers,
    )


@pytest.mark.django_db(transaction=True)
def test_auth_api_register_login_refresh_logout_and_me() -> None:
    cache.clear()
    Role.objects.get_or_create(name="user")
    client = Client()

    registered = _json_post(
        client,
        "/api/v1/auth/register",
        {"email": "user@example.com", "password": "password123"},
    )
    assert registered.status_code == 201
    assert registered.json()["email"] == "user@example.com"

    logged_in = _json_post(
        client,
        "/api/v1/auth/login",
        {"email": "USER@example.com", "password": "password123"},
    )
    assert logged_in.status_code == 200
    token_pair = logged_in.json()

    me = client.get(
        "/api/v1/auth/me",
        HTTP_AUTHORIZATION=f"Bearer {token_pair['access_token']}",
    )
    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"
    assert me.json()["roles"] == ["user"]
    assert me.json()["permissions"] == []

    refreshed = _json_post(
        client,
        "/api/v1/auth/refresh",
        {"refresh_token": token_pair["refresh_token"]},
    )
    assert refreshed.status_code == 200

    logged_out = _json_post(
        client,
        "/api/v1/auth/logout",
        {"refresh_token": refreshed.json()["refresh_token"]},
    )
    assert logged_out.status_code == 204


@pytest.mark.django_db(transaction=True)
def test_admin_api_enforces_claim_permissions_and_manages_users() -> None:
    Role.objects.get_or_create(name="user")
    client = Client()
    admin_token = encode_access_token(
        subject=1,
        roles={"admin"},
        permissions=PERMISSION_CATALOG,
    )
    admin_headers = {"HTTP_AUTHORIZATION": f"Bearer {admin_token}"}

    created = _json_post(
        client,
        "/api/v1/admin/users",
        {"email": "managed@example.com", "password": "password123"},
        **admin_headers,
    )
    assert created.status_code == 201
    user_id = created.json()["id"]

    users = client.get("/api/v1/admin/users", **admin_headers)
    assert users.status_code == 200
    assert users.json()["total"] == 1

    updated = client.patch(
        f"/api/v1/admin/users/{user_id}",
        data=json.dumps({"is_active": False}),
        content_type="application/json",
        **admin_headers,
    )
    assert updated.status_code == 200
    assert not updated.json()["is_active"]

    reviewer = cast(Role, RoleFactory(name="reviewer"))
    assigned = _json_post(
        client,
        f"/api/v1/admin/users/{user_id}/roles",
        {"role_id": reviewer.id},
        **admin_headers,
    )
    assert assigned.status_code == 204
    assert client.get("/api/v1/admin/roles", **admin_headers).status_code == 200
    assert client.get("/api/v1/admin/permissions", **admin_headers).status_code == 200
    assert client.delete(f"/api/v1/admin/users/{user_id}", **admin_headers).status_code == 204

    user_token = encode_access_token(subject=2, roles={"user"}, permissions=[])
    denied = client.get("/api/v1/admin/users", HTTP_AUTHORIZATION=f"Bearer {user_token}")
    assert denied.status_code == 403


@pytest.mark.django_db(transaction=True)
def test_auth_api_login_failure_has_one_generic_response() -> None:
    Role.objects.get_or_create(name="user")
    client = Client()
    _json_post(
        client,
        "/api/v1/auth/register",
        {"email": "known@example.com", "password": "password123"},
    )

    wrong_password = _json_post(
        client,
        "/api/v1/auth/login",
        {"email": "known@example.com", "password": "incorrect-password"},
    )
    missing_account = _json_post(
        client,
        "/api/v1/auth/login",
        {"email": "missing@example.com", "password": "incorrect-password"},
    )

    assert wrong_password.status_code == missing_account.status_code == 401
    assert wrong_password.json() == missing_account.json() == {
        "detail": "Invalid email or password.",
        "code": "invalid_credentials",
    }


@pytest.mark.django_db(transaction=True)
def test_register_endpoint_is_rate_limited() -> None:
    cache.clear()
    Role.objects.get_or_create(name="user")
    client = Client()

    statuses = [
        _json_post(
            client,
            "/api/v1/auth/register",
            {"email": f"user{i}@example.com", "password": "password123"},
        ).status_code
        for i in range(6)
    ]

    assert statuses[:5] == [201, 201, 201, 201, 201]
    assert statuses[5] == 429
