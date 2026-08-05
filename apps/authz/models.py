"""Role-based access-control models."""

from __future__ import annotations

from uuid import uuid4

from django.conf import settings
from django.db import models


class Permission(models.Model):
    """An atomic capability identified by a stable ``resource.action`` code."""

    code = models.CharField(max_length=100, unique=True)

    def __str__(self) -> str:
        return self.code


class Role(models.Model):
    """A named collection of permissions."""

    name = models.CharField(max_length=50, unique=True)

    def __str__(self) -> str:
        return self.name


class UserRole(models.Model):
    """Assign a role to a user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="role_links"
    )
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="user_links")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "role"], name="authz_user_role_unique"),
        ]


class RolePermission(models.Model):
    """Grant a permission to a role."""

    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="permission_links")
    permission = models.ForeignKey(
        Permission, on_delete=models.CASCADE, related_name="role_links"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission"], name="authz_role_permission_unique"
            ),
        ]


class RefreshToken(models.Model):
    """A hashed, revocable refresh token belonging to a rotation family."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="refresh_tokens"
    )
    token_hash = models.CharField(max_length=64, unique=True)
    family_id = models.UUIDField(default=uuid4, db_index=True)
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children"
    )
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["family_id", "revoked_at"], name="authz_refresh_family_rev_idx"
            ),
        ]
