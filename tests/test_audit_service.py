from __future__ import annotations

import logging
from collections.abc import Mapping

import pytest
from django.test import RequestFactory, override_settings

from apps.accounts.models import User
from apps.audit.actions import AuditAction
from apps.audit.context import AuditContext
from apps.audit.models import AuditLog
from apps.audit.repositories import AuditRepository
from apps.audit.services import AuditService, sanitize_metadata
from apps.authz.api.auth import Principal


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_audit_service_records_a_sanitized_event() -> None:
    context = AuditContext(
        actor_id=42,
        actor_email="admin@example.com",
        ip="203.0.113.10",
        user_agent="browser",
        request_id="request-123",
    )

    await AuditService().record(
        AuditAction.USER_UPDATE,
        context=context,
        target_type="user",
        target_id=9,
        metadata={
            "changed_fields": ["email"],
            "password": "must-not-persist",
            "nested": {"refresh_token": "must-not-persist", "safe": True},
        },
    )

    audit_log = await AuditLog.objects.aget()
    assert audit_log.action == AuditAction.USER_UPDATE
    assert audit_log.actor_id == 42
    assert audit_log.target_id == "9"
    assert audit_log.metadata == {
        "changed_fields": ["email"],
        "nested": {"safe": True},
        "request_id": "request-123",
    }


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_audit_service_truncates_user_agent_and_uses_empty_metadata() -> None:
    await AuditService().record(
        AuditAction.LOGOUT,
        context=AuditContext(user_agent="a" * 600),
    )

    audit_log = await AuditLog.objects.aget()
    assert audit_log.user_agent == "a" * 512
    assert audit_log.metadata == {}


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_audit_service_snapshots_actor_email_from_actor_id() -> None:
    user = await User.objects.acreate(email="admin@example.com")

    await AuditService().record(AuditAction.USER_DELETE, context=AuditContext(actor_id=user.id))

    audit_log = await AuditLog.objects.aget()
    assert audit_log.actor_id == user.id
    assert audit_log.actor_email == "admin@example.com"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_audit_repository_is_limited_to_create_and_read() -> None:
    repository = AuditRepository()
    created = await repository.acreate(
        action=AuditAction.LOGOUT,
        actor_id=None,
        actor_email=None,
        target_type=None,
        target_id=None,
        outcome="success",
        ip=None,
        user_agent=None,
        metadata={},
    )

    assert await repository.aget_by_id(created.id) == created
    assert not hasattr(repository, "aupdate")
    assert not hasattr(repository, "adelete")


@pytest.mark.asyncio
async def test_audit_service_suppresses_repository_failures(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class FailingAuditRepository:
        async def acreate(
            self,
            *,
            action: str,
            actor_id: int | None,
            actor_email: str | None,
            target_type: str | None,
            target_id: str | None,
            outcome: str,
            ip: str | None,
            user_agent: str | None,
            metadata: Mapping[str, object],
        ) -> None:
            del (
                action,
                actor_id,
                actor_email,
                target_type,
                target_id,
                outcome,
                ip,
                user_agent,
                metadata,
            )
            raise RuntimeError("audit database unavailable")

    with caplog.at_level(logging.WARNING, logger="apps.audit.services"):
        await AuditService(repository=FailingAuditRepository()).record(
            AuditAction.LOGIN_FAILURE,
            context=AuditContext(),
            metadata={"password": "must-not-persist"},
        )

    assert "Unable to record audit event" in caplog.messages


def test_audit_context_snapshots_request_data() -> None:
    request = RequestFactory().get(
        "/api/v1/auth/logout",
        HTTP_USER_AGENT="browser",
        HTTP_X_REQUEST_ID="request-123",
        REMOTE_ADDR="203.0.113.10",
    )
    principal = Principal(user_id=42, roles=frozenset(), permissions=frozenset())

    assert AuditContext.from_request(request, principal) == AuditContext(
        actor_id=42,
        ip="203.0.113.10",
        user_agent="browser",
        request_id="request-123",
    )


@override_settings(TRUSTED_PROXY_CIDRS=["10.0.0.0/8"])
def test_audit_context_uses_forwarded_client_ip_from_trusted_proxy() -> None:
    request = RequestFactory().get(
        "/api/v1/auth/login",
        HTTP_X_FORWARDED_FOR="198.51.100.10, 10.0.0.6",
        REMOTE_ADDR="10.0.0.5",
    )

    assert AuditContext.from_request(request).ip == "198.51.100.10"


@override_settings(TRUSTED_PROXY_CIDRS=["10.0.0.0/8"])
def test_audit_context_ignores_forwarded_ip_from_untrusted_peer() -> None:
    request = RequestFactory().get(
        "/api/v1/auth/login",
        HTTP_X_FORWARDED_FOR="198.51.100.10",
        REMOTE_ADDR="203.0.113.10",
    )

    assert AuditContext.from_request(request).ip == "203.0.113.10"


def test_sanitize_metadata_removes_sensitive_key_variants() -> None:
    assert sanitize_metadata(
        {"accessToken": "secret", "family_id": "allowed", "api-secret": "secret"}
    ) == {"family_id": "allowed"}
