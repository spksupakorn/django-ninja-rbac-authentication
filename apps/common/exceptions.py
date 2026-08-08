"""Domain errors that services may raise without depending on HTTP."""

from __future__ import annotations


class DomainError(Exception):
    """Base error with a stable API-safe code and HTTP mapping."""

    status_code = 400
    code = "domain_error"
    default_detail = "The request could not be completed."

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class InvalidCredentials(DomainError):
    status_code = 401
    code = "invalid_credentials"
    default_detail = "Invalid email or password."


class TokenReused(DomainError):
    status_code = 401
    code = "token_reused"
    default_detail = "This refresh token has already been used."


class RefreshTokenBindingMismatch(DomainError):
    """A refresh token was presented outside its bound device context."""

    status_code = 401
    code = "refresh_token_binding_mismatch"
    default_detail = "The token is invalid or expired."


class InvalidToken(DomainError):
    status_code = 401
    code = "invalid_token"
    default_detail = "The token is invalid or expired."


class PermissionDenied(DomainError):
    status_code = 403
    code = "permission_denied"
    default_detail = "You do not have permission to perform this action."


class EmailAlreadyExists(DomainError):
    status_code = 409
    code = "email_already_exists"
    default_detail = "An account with this email already exists."


class ResourceNotFound(DomainError):
    status_code = 404
    code = "not_found"
    default_detail = "The requested resource was not found."
