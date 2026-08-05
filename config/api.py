"""Root Django Ninja API instance."""

from django.http import HttpRequest, HttpResponse
from ninja import NinjaAPI

from apps.authz.api.routers.admin_rbac import router as admin_rbac_router
from apps.authz.api.routers.admin_users import router as admin_users_router
from apps.authz.api.routers.auth import router as auth_router
from apps.common.api.system import router as system_router
from apps.common.exceptions import DomainError

api = NinjaAPI(title="RBAC Authentication API", version="1.0.0")
api.add_router("/v1/auth", auth_router)
api.add_router("/v1/admin/users", admin_users_router)
api.add_router("/v1/admin", admin_rbac_router)
api.add_router("/v1", system_router)


@api.exception_handler(DomainError)
def handle_domain_error(request: HttpRequest, exc: DomainError) -> HttpResponse:
    """Translate service-layer failures to a consistent API response."""
    return api.create_response(
        request,
        {"detail": exc.detail, "code": exc.code},
        status=exc.status_code,
    )
