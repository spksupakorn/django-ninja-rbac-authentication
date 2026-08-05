"""Authentication endpoints."""

from django.http import HttpRequest
from ninja import Router, Status

from apps.accounts.models import User
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
from apps.common.throttling import LoginRateThrottle

router = Router(tags=["auth"])


def _token_pair_response(token_pair: TokenPair) -> TokenPairOut:
    return TokenPairOut(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
    )


def _user_out(user: User) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/register", response={201: UserOut})
async def register(request: HttpRequest, payload: RegisterIn) -> Status[UserOut]:
    """Register an account with the default RBAC role."""
    del request
    user = await AuthService().register(email=str(payload.email), password=payload.password)
    return Status(201, _user_out(user))


@router.post("/login", response=TokenPairOut, throttle=LoginRateThrottle())
async def login(request: HttpRequest, payload: LoginIn) -> TokenPairOut:
    """Authenticate an account and issue an access/refresh pair."""
    del request
    token_pair = await AuthService().login(email=str(payload.email), password=payload.password)
    return _token_pair_response(token_pair)


@router.post("/refresh", response=TokenPairOut, throttle=LoginRateThrottle())
async def refresh(request: HttpRequest, payload: RefreshIn) -> TokenPairOut:
    """Rotate a refresh token and issue a new access/refresh pair."""
    del request
    token_pair = await AuthService().refresh(raw_refresh_token=payload.refresh_token)
    return _token_pair_response(token_pair)


@router.post("/logout", response={204: None})
async def logout(request: HttpRequest, payload: LogoutIn) -> Status[None]:
    """Revoke the supplied refresh token."""
    del request
    await AuthService().logout(raw_refresh_token=payload.refresh_token)
    return Status(204, None)


@router.get("/me", auth=JWTAuth(), response=MeOut)
async def me(request: HttpRequest) -> MeOut:
    """Return the identity and RBAC claims carried by the access token."""
    principal = request.auth
    if not isinstance(principal, Principal):
        raise RuntimeError("JWTAuth did not supply a principal")
    return MeOut(
        id=principal.user_id,
        roles=sorted(principal.roles),
        permissions=sorted(principal.permissions),
    )
