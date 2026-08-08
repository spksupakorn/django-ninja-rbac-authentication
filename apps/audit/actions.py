"""Stable catalog of auditable domain events."""

from enum import StrEnum


class AuditAction(StrEnum):
    """Actions persisted in the audit trail."""

    LOGIN_SUCCESS = "login.success"
    LOGIN_FAILURE = "login.failure"
    LOGOUT = "logout"
    REGISTER = "register"
    TOKEN_REFRESHED = "token.refreshed"
    TOKEN_REUSE_DETECTED = "token.reuse_detected"
    TOKEN_BINDING_MISMATCH = "token.binding_mismatch"
    TOKEN_IP_CHANGED = "token.ip_changed"
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    ROLE_ASSIGN = "role.assign"
