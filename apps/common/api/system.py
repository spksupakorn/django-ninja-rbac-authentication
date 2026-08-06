"""System health endpoints."""

from django.http import HttpRequest
from ninja import Router

from apps.common.api.schemas import BuildResponse, success_response

router = Router(tags=["system"])


@router.get("/health", response=BuildResponse[dict[str, str]])
async def health(request: HttpRequest) -> BuildResponse[dict[str, str]]:
    """Return service liveness without requiring a database query."""
    del request
    return success_response({"status": "ok"}, message="Service is healthy.")
