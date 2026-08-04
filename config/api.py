"""Root Django Ninja API instance."""

from django.http import HttpRequest
from ninja import NinjaAPI

api = NinjaAPI(title="RBAC Authentication API", version="0.1.0")


@api.get("/health", tags=["system"])
async def health(request: HttpRequest) -> dict[str, str]:
    """Return service liveness without requiring a database query."""
    del request
    return {"status": "ok"}
