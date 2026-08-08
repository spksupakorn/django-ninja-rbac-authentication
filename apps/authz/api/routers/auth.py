"""Authentication endpoints."""

from math import ceil

from django.http import HttpRequest
from django.utils import timezone
from ninja import Router, Status

from apps.accounts.models import User
from apps.audit.context import AuditContext
from apps.authz.api.auth import JWTAuth, Principal
from apps.authz.api.schemas import (
    LoginIn,
    LogoutIn,
    MeOut,
    RefreshIn,
    RegisterIn,
    TokenPairOut,
    UserOut,
)
from apps.authz.services.auth import AuthService, TokenPair
from apps.common.api.schemas import BuildResponse, success_response
from apps.common.throttling import LoginRateThrottle, RegisterRateThrottle

router = Router(tags=["auth"])


def _token_pair_response(token_pair: TokenPair) -> TokenPairOut:
    return TokenPairOut(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
    )


def _user_out(user: User) -> UserOut:
    return UserOut.model_validate(user)


def _principal(request: HttpRequest) -> Principal:
    principal = request.auth
    if not isinstance(principal, Principal):
        raise RuntimeError("JWTAuth did not supply a principal")
    return principal


def _remaining_access_ttl(principal: Principal) -> int:
    return max(0, ceil((principal.expires_at - timezone.now()).total_seconds()))


@router.post(
    "/register", response={201: BuildResponse[UserOut]}, throttle=RegisterRateThrottle()
)
async def register(
    request: HttpRequest, payload: RegisterIn
) -> Status[BuildResponse[UserOut]]:
    """Register an account with the default RBAC role."""
    user = await AuthService().register(
        email=str(payload.email),
        password=payload.password,
        context=AuditContext.from_request(request),
    )
    return Status(201, success_response(_user_out(user), code=201, message="User registered."))


@router.post("/login", response=BuildResponse[TokenPairOut], throttle=LoginRateThrottle())
async def login(request: HttpRequest, payload: LoginIn) -> BuildResponse[TokenPairOut]:
    """Authenticate an account and issue an access/refresh pair."""
    token_pair = await AuthService().login(
        email=str(payload.email),
        password=payload.password,
        context=AuditContext.from_request(request),
    )
    return success_response(_token_pair_response(token_pair), message="Authenticated.")


@router.post("/refresh", response=BuildResponse[TokenPairOut], throttle=LoginRateThrottle())
async def refresh(request: HttpRequest, payload: RefreshIn) -> BuildResponse[TokenPairOut]:
    """Rotate a refresh token and issue a new access/refresh pair."""
    token_pair = await AuthService().refresh(
        raw_refresh_token=payload.refresh_token, context=AuditContext.from_request(request)
    )
    return success_response(_token_pair_response(token_pair), message="Token refreshed.")


@router.post("/logout", auth=JWTAuth(), response=BuildResponse[None])
async def logout(request: HttpRequest, payload: LogoutIn) -> BuildResponse[None]:
    """Revoke the current access token and the supplied refresh token."""
    principal = _principal(request)
    await AuthService().logout(
        raw_refresh_token=payload.refresh_token,
        context=AuditContext.from_request(request, principal),
        access_token_jti=principal.jti,
        access_token_ttl=_remaining_access_ttl(principal),
    )
    return success_response(None, message="Logged out.")


@router.post("/logout-all", auth=JWTAuth(), response=BuildResponse[None])
async def logout_all(request: HttpRequest) -> BuildResponse[None]:
    """Revoke all access and refresh tokens for the current user."""
    principal = _principal(request)
    await AuthService().logout_all(
        user_id=principal.user_id,
        context=AuditContext.from_request(request, principal),
    )
    return success_response(None, message="Logged out from all sessions.")


@router.get("/me", auth=JWTAuth(), response=BuildResponse[MeOut])
async def me(request: HttpRequest) -> BuildResponse[MeOut]:
    """Return the identity and RBAC claims carried by the access token."""
    principal = request.auth
    if not isinstance(principal, Principal):
        raise RuntimeError("JWTAuth did not supply a principal")
    email = await AuthService().aget_active_email(principal.user_id)
    return success_response(
        MeOut(
            id=principal.user_id,
            email=email,
            roles=sorted(principal.roles),
            permissions=sorted(principal.permissions),
        ),
        message="Profile fetched.",
    )
