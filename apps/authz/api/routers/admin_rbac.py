"""Administrative RBAC catalog endpoints."""

from datetime import datetime

from django.http import HttpRequest
from ninja import Query, Router

from apps.accounts.services.admin import AdminService
from apps.audit.actions import AuditAction
from apps.audit.dtos import AuditLogDTO
from apps.authz.api.auth import JWTAuth, require_permission
from apps.authz.api.schemas import (
    AuditLogOut,
    AuditLogsPageOut,
    PermissionOut,
    PermissionsPageOut,
    RoleOut,
    RolesPageOut,
)
from apps.authz.repositories.dtos import PermissionDTO, RoleDTO
from apps.common.api.schemas import BuildResponse, success_response

router = Router(tags=["admin-rbac"])


def _role_out(role: RoleDTO) -> RoleOut:
    return RoleOut(id=role.id, name=role.name)


def _permission_out(permission: PermissionDTO) -> PermissionOut:
    return PermissionOut(id=permission.id, code=permission.code)


def _audit_log_out(audit_log: AuditLogDTO) -> AuditLogOut:
    return AuditLogOut(
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
        metadata=audit_log.metadata,
    )


def _pagination(offset: int, limit: int) -> tuple[int, int]:
    """Keep page sizes bounded even when handlers are called directly."""
    return max(offset, 0), min(max(limit, 1), 100)


@router.get("/roles", auth=JWTAuth(), response=BuildResponse[RolesPageOut])
@require_permission("role.read")
async def list_roles(
    request: HttpRequest,
    offset: int = 0,
    limit: int = 20,
) -> BuildResponse[RolesPageOut]:
    """List roles with offset pagination."""
    del request
    offset, limit = _pagination(offset, limit)
    roles, total = await AdminService().list_roles(offset=offset, limit=limit)
    return success_response(
        RolesPageOut(
            items=[_role_out(role) for role in roles], total=total, offset=offset, limit=limit
        ),
        message="Roles fetched.",
    )


@router.get("/permissions", auth=JWTAuth(), response=BuildResponse[PermissionsPageOut])
@require_permission("permission.read")
async def list_permissions(
    request: HttpRequest,
    offset: int = 0,
    limit: int = 20,
) -> BuildResponse[PermissionsPageOut]:
    """List permission catalog rows with offset pagination."""
    del request
    offset, limit = _pagination(offset, limit)
    permissions, total = await AdminService().list_permissions(offset=offset, limit=limit)
    return success_response(
        PermissionsPageOut(
            items=[_permission_out(permission) for permission in permissions],
            total=total,
            offset=offset,
            limit=limit,
        ),
        message="Permissions fetched.",
    )


@router.get("/audit-logs", auth=JWTAuth(), response=BuildResponse[AuditLogsPageOut])
@require_permission("audit.read")
async def list_audit_logs(
    request: HttpRequest,
    offset: int = 0,
    limit: int = 20,
    actor_id: int | None = None,
    action: AuditAction | None = None,
    outcome: str | None = None,
    from_at: datetime | None = Query(None, alias="from"),  # type: ignore[type-arg]  # noqa: B008
    to_at: datetime | None = Query(None, alias="to"),  # type: ignore[type-arg]  # noqa: B008
) -> BuildResponse[AuditLogsPageOut]:
    """List audit records with pagination and investigation filters."""
    del request
    offset, limit = _pagination(offset, limit)
    audit_logs, total = await AdminService().list_audit_logs(
        offset=offset,
        limit=limit,
        actor_id=actor_id,
        action=str(action) if action is not None else None,
        outcome=outcome,
        from_at=from_at,
        to_at=to_at,
    )
    return success_response(
        AuditLogsPageOut(
            items=[_audit_log_out(audit_log) for audit_log in audit_logs],
            total=total,
            offset=offset,
            limit=limit,
        ),
        message="Audit logs fetched.",
    )
