"""Shared API response contracts."""

from ninja import Schema


class BuildResponse[T](Schema):
    """Stable envelope returned by every API endpoint."""

    success: bool = True
    code: int
    message: str
    data: T | None = None


def success_response[T](
    data: T | None, *, code: int = 200, message: str = "Success"
) -> BuildResponse[T]:
    """Build a successful response without duplicating envelope fields."""
    return BuildResponse[T](code=code, message=message, data=data)
