"""Root Django Ninja API instance."""

from django.http import HttpRequest, HttpResponse
from ninja import NinjaAPI

from apps.common.exceptions import DomainError

api = NinjaAPI(title="RBAC Authentication API", version="0.1.0")


@api.exception_handler(DomainError)
def handle_domain_error(request: HttpRequest, exc: DomainError) -> HttpResponse:
    """Translate service-layer failures to a consistent API response."""
    return api.create_response(
        request,
        {"detail": exc.detail, "code": exc.code},
        status=exc.status_code,
    )


@api.get("/health", tags=["system"])
async def health(request: HttpRequest) -> dict[str, str]:
    """Return service liveness without requiring a database query."""
    del request
    return {"status": "ok"}
