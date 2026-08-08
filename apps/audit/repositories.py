"""Append-only persistence operations for audit records."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from apps.audit.dtos import AuditLogDTO
from apps.audit.models import AuditLog


class AuditRepository:
    """Create and retrieve audit records without mutation operations."""

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
    ) -> AuditLogDTO:
        """Append one audit record."""
        audit_log = await AuditLog.objects.acreate(
            action=action,
            actor_id=actor_id,
            actor_email=actor_email,
            target_type=target_type,
            target_id=target_id,
            outcome=outcome,
            ip=ip,
            user_agent=user_agent,
            metadata=dict(metadata),
        )
        return _audit_log_dto(audit_log)

    async def aget_by_id(self, audit_log_id: int) -> AuditLogDTO | None:
        """Return one record when it exists."""
        try:
            return _audit_log_dto(await AuditLog.objects.aget(id=audit_log_id))
        except AuditLog.DoesNotExist:
            return None

    async def alist(
        self,
        *,
        offset: int,
        limit: int,
        actor_id: int | None = None,
        action: str | None = None,
        outcome: str | None = None,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
    ) -> tuple[list[AuditLogDTO], int]:
        """Return a filtered, newest-first page of immutable audit records."""
        queryset = AuditLog.objects.all()
        if actor_id is not None:
            queryset = queryset.filter(actor_id=actor_id)
        if action is not None:
            queryset = queryset.filter(action=action)
        if outcome is not None:
            queryset = queryset.filter(outcome=outcome)
        if from_at is not None:
            queryset = queryset.filter(created_at__gte=from_at)
        if to_at is not None:
            queryset = queryset.filter(created_at__lte=to_at)

        total = await queryset.acount()
        page = queryset.order_by("-created_at", "-id")[offset : offset + limit]
        audit_logs = [_audit_log_dto(audit_log) async for audit_log in page]
        return audit_logs, total


def _audit_log_dto(audit_log: AuditLog) -> AuditLogDTO:
    return AuditLogDTO(
        id=audit_log.id,
        created_at=audit_log.created_at,
        action=audit_log.action,
        actor_id=audit_log.actor_id,
        actor_email=audit_log.actor_email,
        target_type=audit_log.target_type,
        target_id=audit_log.target_id,
        outcome=audit_log.outcome,
        ip=audit_log.ip,
        user_agent=audit_log.user_agent,
        metadata=dict(audit_log.metadata),
    )
