"""Administrative user-management endpoints."""

from django.http import HttpRequest
from ninja import Router, Status

from apps.accounts.models import User
from apps.accounts.services.admin import AdminService
from apps.authz.api.auth import JWTAuth, require_permission
from apps.authz.api.schemas import AssignRoleIn, RegisterIn, UserOut, UsersPageOut, UserUpdateIn

router = Router(tags=["admin-users"])


def _user_out(user: User) -> UserOut:
    return UserOut.model_validate(user)


def _pagination(offset: int, limit: int) -> tuple[int, int]:
    """Keep page sizes bounded even when handlers are called directly."""
    return max(offset, 0), min(max(limit, 1), 100)


@router.get("", auth=JWTAuth(), response=UsersPageOut)
@require_permission("user.read")
async def list_users(
    request: HttpRequest,
    offset: int = 0,
    limit: int = 20,
) -> UsersPageOut:
    """List users with offset pagination."""
    del request
    offset, limit = _pagination(offset, limit)
    users, total = await AdminService().list_users(offset=offset, limit=limit)
    return UsersPageOut(
        items=[_user_out(user) for user in users], total=total, offset=offset, limit=limit
    )


@router.post("", auth=JWTAuth(), response={201: UserOut})
@require_permission("user.create")
async def create_user(request: HttpRequest, payload: RegisterIn) -> Status[UserOut]:
    """Create a user with the default role."""
    del request
    user = await AdminService().create_user(email=str(payload.email), password=payload.password)
    return Status(201, _user_out(user))


@router.get("/{user_id}", auth=JWTAuth(), response=UserOut)
@require_permission("user.read")
async def get_user(request: HttpRequest, user_id: int) -> UserOut:
    """Return one user."""
    del request
    return _user_out(await AdminService().get_user(user_id))


@router.patch("/{user_id}", auth=JWTAuth(), response=UserOut)
@require_permission("user.update")
async def update_user(request: HttpRequest, user_id: int, payload: UserUpdateIn) -> UserOut:
    """Update selected safe user fields."""
    del request
    user = await AdminService().update_user(
        user_id=user_id,
        email=str(payload.email) if payload.email is not None else None,
        password=payload.password,
        is_active=payload.is_active,
    )
    return _user_out(user)


@router.delete("/{user_id}", auth=JWTAuth(), response={204: None})
@require_permission("user.delete")
async def delete_user(request: HttpRequest, user_id: int) -> Status[None]:
    """Delete one user."""
    del request
    await AdminService().delete_user(user_id)
    return Status(204, None)


@router.post("/{user_id}/roles", auth=JWTAuth(), response={204: None})
@require_permission("role.assign")
async def assign_role(
    request: HttpRequest, user_id: int, payload: AssignRoleIn
) -> Status[None]:
    """Assign a role idempotently."""
    del request
    await AdminService().assign_role(user_id=user_id, role_id=payload.role_id)
    return Status(204, None)
