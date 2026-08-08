"""Regression checks for async database connection lifecycle settings."""

from __future__ import annotations

import asyncio
import json

import pytest
from django.conf import settings
from django.test import AsyncClient

from apps.audit.context import AuditContext
from apps.authz.models import Role
from apps.authz.services.auth import AuthService


def test_async_database_connections_do_not_persist_between_requests() -> None:
    database = settings.DATABASES["default"]

    assert database["CONN_MAX_AGE"] == 0
    assert database["CONN_HEALTH_CHECKS"] is False


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_concurrent_login_requests_share_no_broken_database_connection() -> None:
    """Concurrent ASGI logins must complete without connection lifecycle errors."""
    await Role.objects.aget_or_create(name="user")
    await AuthService().register(
        email="concurrent@example.com", password="password123", context=AuditContext()
    )

    async def login() -> object:
        return await AsyncClient().post(
            "/api/v1/auth/login",
            data=json.dumps({"email": "concurrent@example.com", "password": "password123"}),
            content_type="application/json",
        )

    responses = await asyncio.gather(*(login() for _ in range(4)))

    assert all(getattr(response, "status_code", None) == 200 for response in responses)
