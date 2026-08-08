"""Administrative user-management endpoints."""

from django.http import HttpRequest
from ninja import Router, Status

from apps.accounts.repositories.dtos import UserDTO
from apps.accounts.services.admin import AdminService
from apps.audit.context import AuditContext
from apps.authz.api.auth import JWTAuth, Principal, require_permission
from apps.authz.api.schemas import AssignRoleIn, RegisterIn, UserOut, UsersPageOut, UserUpdateIn
from apps.common.api.schemas import BuildResponse, success_response

router = Router(tags=["admin-users"])


def _user_out(user: UserDTO) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_staff=user.is_staff,
        date_joined=user.date_joined,
    )


def _pagination(offset: int, limit: int) -> tuple[int, int]:
    """Keep page sizes bounded even when handlers are called directly."""
    return max(offset, 0), min(max(limit, 1), 100)


def _audit_context(request: HttpRequest) -> AuditContext:
    principal = request.auth
    if not isinstance(principal, Principal):
        raise RuntimeError("JWTAuth did not supply a principal")
    return AuditContext.from_request(request, principal)


@router.get("", auth=JWTAuth(), response=BuildResponse[UsersPageOut])
@require_permission("user.read")
async def list_users(
    request: HttpRequest,
    offset: int = 0,
    limit: int = 20,
) -> BuildResponse[UsersPageOut]:
    """List users with offset pagination."""
    del request
    offset, limit = _pagination(offset, limit)
    users, total = await AdminService().list_users(offset=offset, limit=limit)
    return success_response(
        UsersPageOut(
            items=[_user_out(user) for user in users], total=total, offset=offset, limit=limit
        ),
        message="Users fetched.",
    )


@router.post("", auth=JWTAuth(), response={201: BuildResponse[UserOut]})
@require_permission("user.create")
async def create_user(
    request: HttpRequest, payload: RegisterIn
) -> Status[BuildResponse[UserOut]]:
    """Create a user with the default role."""
    user = await AdminService().create_user(
        email=str(payload.email),
        password=payload.password,
        context=_audit_context(request),
    )
    return Status(201, success_response(_user_out(user), code=201, message="User created."))


@router.get("/{user_id}", auth=JWTAuth(), response=BuildResponse[UserOut])
@require_permission("user.read")
async def get_user(request: HttpRequest, user_id: int) -> BuildResponse[UserOut]:
    """Return one user."""
    del request
    return success_response(
        _user_out(await AdminService().get_user(user_id)), message="User fetched."
    )


@router.patch("/{user_id}", auth=JWTAuth(), response=BuildResponse[UserOut])
@require_permission("user.update")
async def update_user(
    request: HttpRequest, user_id: int, payload: UserUpdateIn
) -> BuildResponse[UserOut]:
    """Update selected safe user fields."""
    user = await AdminService().update_user(
        user_id=user_id,
        email=str(payload.email) if payload.email is not None else None,
        password=payload.password,
        is_active=payload.is_active,
        context=_audit_context(request),
    )
    return success_response(_user_out(user), message="User updated.")


@router.delete("/{user_id}", auth=JWTAuth(), response=BuildResponse[None])
@require_permission("user.delete")
async def delete_user(request: HttpRequest, user_id: int) -> BuildResponse[None]:
    """Delete one user."""
    await AdminService().delete_user(user_id, context=_audit_context(request))
    return success_response(None, message="User deleted.")


@router.post("/{user_id}/roles", auth=JWTAuth(), response=BuildResponse[None])
@require_permission("role.assign")
async def assign_role(
    request: HttpRequest, user_id: int, payload: AssignRoleIn
) -> BuildResponse[None]:
    """Assign a role idempotently."""
    await AdminService().assign_role(
        user_id=user_id, role_id=payload.role_id, context=_audit_context(request)
    )
    return success_response(None, message="Role assigned.")
