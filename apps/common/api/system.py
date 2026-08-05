"""System health endpoints."""

from django.http import HttpRequest
from ninja import Router

router = Router(tags=["system"])


@router.get("/health")
async def health(request: HttpRequest) -> dict[str, str]:
    """Return service liveness without requiring a database query."""
    del request
    return {"status": "ok"}
