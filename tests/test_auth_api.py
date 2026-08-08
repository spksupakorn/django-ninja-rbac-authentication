import json
from typing import cast

import pytest
from django.core.cache import cache
from django.http import HttpResponse
from django.test import Client

from apps.audit.actions import AuditAction
from apps.audit.models import AuditLog
from apps.authz.models import Role
from apps.authz.permissions import PERMISSION_CATALOG
from apps.authz.security.jwt import encode_access_token
from tests.factories import AuditLogFactory, RoleFactory


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
    assert registered.json()["success"]
    assert registered.json()["code"] == 201
    assert registered.json()["data"]["email"] == "user@example.com"

    logged_in = _json_post(
        client,
        "/api/v1/auth/login",
        {"email": "USER@example.com", "password": "password123"},
    )
    assert logged_in.status_code == 200
    token_pair = logged_in.json()["data"]

    me = client.get(
        "/api/v1/auth/me",
        HTTP_AUTHORIZATION=f"Bearer {token_pair['access_token']}",
    )
    assert me.status_code == 200
    assert me.json()["data"]["email"] == "user@example.com"
    assert me.json()["data"]["roles"] == ["user"]
    assert me.json()["data"]["permissions"] == []

    refreshed = _json_post(
        client,
        "/api/v1/auth/refresh",
        {"refresh_token": token_pair["refresh_token"]},
    )
    assert refreshed.status_code == 200

    logged_out = _json_post(
        client,
        "/api/v1/auth/logout",
        {"refresh_token": refreshed.json()["data"]["refresh_token"]},
        HTTP_AUTHORIZATION=f"Bearer {refreshed.json()['data']['access_token']}",
    )
    assert logged_out.status_code == 200
    assert logged_out.json()["data"] is None
    assert client.get(
        "/api/v1/auth/me",
        HTTP_AUTHORIZATION=f"Bearer {refreshed.json()['data']['access_token']}",
    ).status_code == 401


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
    user_id = created.json()["data"]["id"]

    users = client.get("/api/v1/admin/users", **admin_headers)
    assert users.status_code == 200
    assert users.json()["data"]["total"] == 1

    updated = client.patch(
        f"/api/v1/admin/users/{user_id}",
        data=json.dumps({"is_active": False}),
        content_type="application/json",
        **admin_headers,
    )
    assert updated.status_code == 200
    assert not updated.json()["data"]["is_active"]

    reviewer = cast(Role, RoleFactory(name="reviewer"))
    assigned = _json_post(
        client,
        f"/api/v1/admin/users/{user_id}/roles",
        {"role_id": reviewer.id},
        **admin_headers,
    )
    assert assigned.status_code == 200
    assert client.get("/api/v1/admin/roles", **admin_headers).status_code == 200
    assert client.get("/api/v1/admin/permissions", **admin_headers).status_code == 200
    assert client.delete(f"/api/v1/admin/users/{user_id}", **admin_headers).status_code == 200

    user_token = encode_access_token(subject=2, roles={"user"}, permissions=[])
    denied = client.get("/api/v1/admin/users", HTTP_AUTHORIZATION=f"Bearer {user_token}")
    assert denied.status_code == 403
    assert denied.json()["message"] == "Access denied."


@pytest.mark.django_db(transaction=True)
def test_admin_api_records_audit_events_for_mutations() -> None:
    Role.objects.get_or_create(name="user")
    reviewer = Role.objects.create(name="reviewer")
    client = Client()
    admin_headers = {
        "HTTP_AUTHORIZATION": "Bearer "
        + encode_access_token(
            subject=77,
            roles={"admin"},
            permissions=PERMISSION_CATALOG,
        )
    }

    created = _json_post(
        client,
        "/api/v1/admin/users",
        {"email": "managed@example.com", "password": "password123"},
        **admin_headers,
    )
    user_id = created.json()["data"]["id"]
    updated = client.patch(
        f"/api/v1/admin/users/{user_id}",
        data=json.dumps({"email": "updated@example.com", "is_active": False}),
        content_type="application/json",
        **admin_headers,
    )
    assigned = _json_post(
        client,
        f"/api/v1/admin/users/{user_id}/roles",
        {"role_id": reviewer.id},
        **admin_headers,
    )
    deleted = client.delete(f"/api/v1/admin/users/{user_id}", **admin_headers)

    status_codes = [
        created.status_code,
        updated.status_code,
        assigned.status_code,
        deleted.status_code,
    ]
    assert status_codes == [
        201,
        200,
        200,
        200,
    ]
    audit_logs = {audit_log.action: audit_log for audit_log in AuditLog.objects.all()}
    assert set(audit_logs) == {
        AuditAction.USER_CREATE,
        AuditAction.USER_UPDATE,
        AuditAction.USER_DELETE,
        AuditAction.ROLE_ASSIGN,
    }
    assert all(audit_log.actor_id == 77 for audit_log in audit_logs.values())
    assert all(audit_log.target_type == "user" for audit_log in audit_logs.values())
    assert all(audit_log.target_id == str(user_id) for audit_log in audit_logs.values())
    assert audit_logs[AuditAction.USER_UPDATE].metadata == {
        "changed_fields": ["email", "is_active"]
    }
    assert audit_logs[AuditAction.ROLE_ASSIGN].metadata == {
        "role_id": reviewer.id,
        "role_name": "reviewer",
    }


@pytest.mark.django_db(transaction=True)
def test_admin_api_lists_filtered_audit_logs_with_audit_permission() -> None:
    AuditLogFactory(action=AuditAction.LOGIN_SUCCESS, actor_id=11)
    expected_log = cast(
        AuditLog,
        AuditLogFactory(
            action=AuditAction.LOGIN_FAILURE,
            actor_id=22,
            outcome="failure",
            metadata={"email": "attempt@example.com"},
        ),
    )
    client = Client()
    admin_headers = {
        "HTTP_AUTHORIZATION": "Bearer "
        + encode_access_token(
            subject=1,
            roles={"admin"},
            permissions={"audit.read"},
        )
    }

    response = client.get(
        "/api/v1/admin/audit-logs?action=login.failure&actor_id=22&outcome=failure",
        **admin_headers,
    )
    user_token = encode_access_token(subject=2, roles={"user"}, permissions=[])
    denied = client.get(
        "/api/v1/admin/audit-logs",
        HTTP_AUTHORIZATION=f"Bearer {user_token}",
    )

    assert response.status_code == 200
    response_data = response.json()["data"]
    assert response_data["total"] == 1
    assert response_data["offset"] == 0
    assert response_data["limit"] == 20
    audit_log = response_data["items"][0]
    assert audit_log["id"] == expected_log.id
    assert audit_log["created_at"].endswith("Z")
    assert audit_log["action"] == "login.failure"
    assert audit_log["actor_id"] == 22
    assert audit_log["actor_email"] == expected_log.actor_email
    assert audit_log["target_type"] is None
    assert audit_log["target_id"] is None
    assert audit_log["outcome"] == "failure"
    assert audit_log["ip"] is None
    assert audit_log["user_agent"] is None
    assert audit_log["metadata"] == {"email": "attempt@example.com"}
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
        "success": False,
        "code": 401,
        "message": "Authentication failed.",
        "data": None,
    }


@pytest.mark.django_db(transaction=True)
def test_auth_api_records_login_and_refresh_security_events() -> None:
    cache.clear()
    Role.objects.get_or_create(name="user")
    client = Client()
    registration = _json_post(
        client,
        "/api/v1/auth/register",
        {"email": "audit@example.com", "password": "password123"},
    )
    user_id = registration.json()["data"]["id"]

    logged_in = _json_post(
        client,
        "/api/v1/auth/login",
        {"email": "audit@example.com", "password": "password123"},
    )
    initial_refresh_token = logged_in.json()["data"]["refresh_token"]
    failed_login = _json_post(
        client,
        "/api/v1/auth/login",
        {"email": "audit@example.com", "password": "wrong-password"},
    )
    refreshed = _json_post(
        client,
        "/api/v1/auth/refresh",
        {"refresh_token": initial_refresh_token},
    )
    reused = _json_post(
        client,
        "/api/v1/auth/refresh",
        {"refresh_token": initial_refresh_token},
    )

    assert failed_login.status_code == 401
    assert refreshed.status_code == 200
    assert reused.status_code == 401

    login_success = AuditLog.objects.get(action=AuditAction.LOGIN_SUCCESS)
    login_failure = AuditLog.objects.get(action=AuditAction.LOGIN_FAILURE)
    reuse_detected = AuditLog.objects.get(action=AuditAction.TOKEN_REUSE_DETECTED)
    assert login_success.outcome == "success"
    assert login_success.actor_id == user_id
    assert login_success.actor_email == "audit@example.com"
    assert login_failure.outcome == "failure"
    assert login_failure.actor_id is None
    assert login_failure.metadata == {"email": "audit@example.com"}
    assert reuse_detected.outcome == "failure"
    assert reuse_detected.actor_id == user_id
    assert set(reuse_detected.metadata) == {"family_id"}


@pytest.mark.django_db(transaction=True)
def test_register_endpoint_is_rate_limited() -> None:
    cache.clear()
    Role.objects.get_or_create(name="user")
    client = Client()

    responses = [
        _json_post(
            client,
            "/api/v1/auth/register",
            {"email": f"user{i}@example.com", "password": "password123"},
        )
        for i in range(6)
    ]

    assert [response.status_code for response in responses[:5]] == [201, 201, 201, 201, 201]
    assert responses[5].status_code == 429
    assert responses[5].json()["message"] == "Too many requests."


def test_auth_api_envelopes_unauthorized_and_validation_errors() -> None:
    cache.clear()
    client = Client()

    unauthorized = client.get("/api/v1/auth/me")
    invalid_request = _json_post(
        client,
        "/api/v1/auth/register",
        {"email": "invalid-email", "password": "short"},
    )

    assert unauthorized.status_code == 401
    assert unauthorized.json()["message"] == "Authentication failed."
    assert invalid_request.status_code == 422
    assert invalid_request.json()["message"] == "Invalid request."
