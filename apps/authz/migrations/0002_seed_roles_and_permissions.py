from typing import Any

from django.db import migrations

PERMISSION_CODES = (
    "user.create",
    "user.read",
    "user.update",
    "user.delete",
    "role.assign",
    "role.read",
    "permission.read",
)
DEFAULT_ROLE_PERMISSIONS = {
    "admin": PERMISSION_CODES,
    "user": ("user.read",),
}


def seed_roles_and_permissions(apps: Any, schema_editor: Any) -> None:

    Permission = apps.get_model("authz", "Permission")
    Role = apps.get_model("authz", "Role")
    RolePermission = apps.get_model("authz", "RolePermission")

    permissions = {}
    for code in PERMISSION_CODES:
        permission, _ = Permission.objects.get_or_create(code=code)
        permissions[code] = permission

    for role_name, codes in DEFAULT_ROLE_PERMISSIONS.items():
        role, _ = Role.objects.get_or_create(name=role_name)
        for code in codes:
            RolePermission.objects.get_or_create(role=role, permission=permissions[code])


def unseed_roles_and_permissions(apps: Any, schema_editor: Any) -> None:

    Permission = apps.get_model("authz", "Permission")
    Role = apps.get_model("authz", "Role")

    Role.objects.filter(name__in=DEFAULT_ROLE_PERMISSIONS).delete()
    Permission.objects.filter(code__in=PERMISSION_CODES).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("authz", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            seed_roles_and_permissions, unseed_roles_and_permissions, elidable=False
        ),
    ]
