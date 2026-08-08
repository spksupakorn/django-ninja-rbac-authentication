"""Best-effort audit recording."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import replace
from ipaddress import ip_address, ip_network
from typing import Literal, Protocol

from apps.accounts.repositories.users import UserRepository
from apps.audit.actions import AuditAction
from apps.audit.context import AuditContext
from apps.audit.repositories import AuditRepository

logger = logging.getLogger(__name__)

_SENSITIVE_METADATA_KEY = re.compile(
    r"(?:^|[_-])(password|token|secret|authorization|credential)(?:$|[_-])", re.IGNORECASE
)


class AuditService:
    """Record audit events without allowing audit failures to fail the caller."""

    def __init__(
        self,
        *,
        repository: AuditWriter | None = None,
        users: UserRepository | None = None,
    ) -> None:
        self.repository = repository or AuditRepository()
        self.users = users or UserRepository()

    async def record(
        self,
        action: AuditAction | str,
        *,
        context: AuditContext,
        target_type: str | None = None,
        target_id: str | int | None = None,
        outcome: Literal["success", "failure"] = "success",
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        """Append an event, logging but suppressing persistence failures."""
        action_code = str(action)
        try:
            context = await self._with_actor_email(context)
            sanitized_metadata = sanitize_metadata(metadata)
            if context.request_id is not None:
                sanitized_metadata["request_id"] = context.request_id
            await self.repository.acreate(
                action=action_code,
                actor_id=context.actor_id,
                actor_email=context.actor_email,
                target_type=target_type,
                target_id=str(target_id) if target_id is not None else None,
                outcome=outcome,
                ip=context.ip,
                user_agent=_truncate_user_agent(context.user_agent),
                metadata=sanitized_metadata,
            )
        except Exception:
            logger.warning(
                "Unable to record audit event", extra={"action": action_code}, exc_info=True
            )

    async def _with_actor_email(self, context: AuditContext) -> AuditContext:
        """Fill a missing actor email without making audit lookup failures fatal."""
        if context.actor_id is None or context.actor_email is not None:
            return context
        try:
            user = await self.users.aget_by_id(context.actor_id)
        except Exception:
            logger.warning("Unable to resolve audit actor email", exc_info=True)
            return context
        if user is None:
            return context
        return replace(context, actor_email=user.email)


def sanitize_metadata(metadata: Mapping[str, object] | None) -> dict[str, object]:
    """Copy metadata while omitting fields that could carry credentials or tokens."""
    if metadata is None:
        return {}
    return {
        key: _sanitize_value(value)
        for key, value in metadata.items()
        if not _is_sensitive_metadata_key(key)
    }


def mask_ip(value: str | None) -> str | None:
    """Return a privacy-preserving network prefix for a valid IP address."""
    if value is None:
        return None
    try:
        parsed = ip_address(value)
    except ValueError:
        return None
    prefix_length = 24 if parsed.version == 4 else 64
    return str(ip_network(f"{parsed}/{prefix_length}", strict=False))


def _sanitize_value(value: object) -> object:
    if isinstance(value, Mapping):
        return sanitize_metadata(value)
    if isinstance(value, list | tuple):
        return [_sanitize_value(item) for item in value]
    return value


def _truncate_user_agent(user_agent: str | None) -> str | None:
    return user_agent[:512] if user_agent else None


def _is_sensitive_metadata_key(key: str) -> bool:
    normalized_key = re.sub(r"([a-z])([A-Z])", r"\1_\2", key)
    return bool(_SENSITIVE_METADATA_KEY.search(normalized_key))


class AuditWriter(Protocol):
    """The write capability needed by ``AuditService``."""

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
    ) -> object: ...
