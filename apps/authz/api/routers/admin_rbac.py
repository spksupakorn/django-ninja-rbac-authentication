"""Administrative RBAC catalog endpoints."""

from django.http import HttpRequest
from ninja import Router

from apps.authz.api.auth import JWTAuth, require_permission
from apps.authz.api.schemas import PermissionOut, PermissionsPageOut, RoleOut, RolesPageOut
from apps.authz.models import Permission, Role
from apps.authz.repositories.rbac import AuthzRepository

router = Router(tags=["admin-rbac"])


def _role_out(role: Role) -> RoleOut:
    return RoleOut.model_validate(role)


def _permission_out(permission: Permission) -> PermissionOut:
    return PermissionOut.model_validate(permission)


def _pagination(offset: int, limit: int) -> tuple[int, int]:
    """Keep page sizes bounded even when handlers are called directly."""
    return max(offset, 0), min(max(limit, 1), 100)


@router.get("/roles", auth=JWTAuth(), response=RolesPageOut)
@require_permission("role.read")
async def list_roles(
    request: HttpRequest,
    offset: int = 0,
    limit: int = 20,
) -> RolesPageOut:
    """List roles with offset pagination."""
    del request
    offset, limit = _pagination(offset, limit)
    repository = AuthzRepository()
    roles = await repository.alist_roles(offset=offset, limit=limit)
    return RolesPageOut(
        items=[_role_out(role) for role in roles],
        total=await repository.acount_roles(),
        offset=offset,
        limit=limit,
    )


@router.get("/permissions", auth=JWTAuth(), response=PermissionsPageOut)
@require_permission("permission.read")
async def list_permissions(
    request: HttpRequest,
    offset: int = 0,
    limit: int = 20,
) -> PermissionsPageOut:
    """List permission catalog rows with offset pagination."""
    del request
    offset, limit = _pagination(offset, limit)
    repository = AuthzRepository()
    permissions = await repository.alist_permissions(offset=offset, limit=limit)
    return PermissionsPageOut(
        items=[_permission_out(permission) for permission in permissions],
        total=await repository.acount_permissions(),
        offset=offset,
        limit=limit,
    )
