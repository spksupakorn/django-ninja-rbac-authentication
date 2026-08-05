"""Role-based access-control models."""

from __future__ import annotations

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
