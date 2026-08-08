"""Value objects returned by the audit persistence boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AuditLogDTO:
    id: int
    created_at: datetime
    action: str
    actor_id: int | None
    actor_email: str | None
    target_type: str | None
    target_id: str | None
    outcome: str
    ip: str | None
    user_agent: str | None
    metadata: dict[str, object]
