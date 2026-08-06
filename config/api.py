"""Root Django Ninja API instance."""

from django.http import HttpRequest, HttpResponse
from ninja import NinjaAPI
from ninja.errors import HttpError, ValidationError

from apps.authz.api.routers.admin_rbac import router as admin_rbac_router
from apps.authz.api.routers.admin_users import router as admin_users_router
from apps.authz.api.routers.auth import router as auth_router
from apps.common.api.schemas import BuildResponse
from apps.common.api.system import router as system_router
from apps.common.exceptions import DomainError

api = NinjaAPI(title="RBAC Authentication API", version="1.0.0")
api.add_router("/v1/auth", auth_router)
api.add_router("/v1/admin/users", admin_users_router)
api.add_router("/v1/admin", admin_rbac_router)
api.add_router("/v1", system_router)


_SAFE_ERROR_MESSAGES = {
    400: "Request could not be completed.",
    401: "Authentication failed.",
    403: "Access denied.",
    404: "Request could not be completed.",
    409: "Request could not be completed.",
    422: "Invalid request.",
    429: "Too many requests.",
}


def _safe_error_message(status_code: int) -> str:
    """Return an API-safe message without exposing domain internals."""
    return _SAFE_ERROR_MESSAGES.get(status_code, "Request could not be completed.")


@api.exception_handler(DomainError)
def handle_domain_error(request: HttpRequest, exc: DomainError) -> HttpResponse:
    """Translate service-layer failures to a consistent API response."""
    return api.create_response(
        request,
        BuildResponse[None](
            success=False,
            code=exc.status_code,
            message=_safe_error_message(exc.status_code),
        ).model_dump(),
        status=exc.status_code,
    )


@api.exception_handler(HttpError)
def handle_http_error(request: HttpRequest, exc: HttpError) -> HttpResponse:
    """Envelope Ninja authentication, throttling, and other HTTP errors."""
    return api.create_response(
        request,
        BuildResponse[None](
            success=False,
            code=exc.status_code,
            message=_safe_error_message(exc.status_code),
        ).model_dump(),
        status=exc.status_code,
    )


@api.exception_handler(ValidationError)
def handle_validation_error(request: HttpRequest, exc: ValidationError) -> HttpResponse:
    """Envelope request-validation failures for frontend consumers."""
    return api.create_response(
        request,
        BuildResponse[None](
            success=False,
            code=422,
            message=_safe_error_message(422),
        ).model_dump(),
        status=422,
    )
