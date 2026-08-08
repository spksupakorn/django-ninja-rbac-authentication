from typing import Any

from django.db import migrations


AUDIT_READ = "audit.read"
ADMIN_ROLE = "admin"


def add_audit_read_permission(apps: Any, schema_editor: Any) -> None:
    """Grant audit-log access to the built-in administrator role."""
    del schema_editor
    Permission = apps.get_model("authz", "Permission")
    Role = apps.get_model("authz", "Role")
    RolePermission = apps.get_model("authz", "RolePermission")
    permission, _ = Permission.objects.get_or_create(code=AUDIT_READ)
    role = Role.objects.filter(name=ADMIN_ROLE).first()
    if role is not None:
        RolePermission.objects.get_or_create(role=role, permission=permission)


def remove_audit_read_permission(apps: Any, schema_editor: Any) -> None:
    """Reverse the permission seed without altering older migrations."""
    del schema_editor
    Permission = apps.get_model("authz", "Permission")
    RolePermission = apps.get_model("authz", "RolePermission")
    permission = Permission.objects.filter(code=AUDIT_READ).first()
    if permission is not None:
        RolePermission.objects.filter(permission=permission).delete()
        permission.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("authz", "0005_remove_default_user_admin_permission"),
    ]

    operations = [
        migrations.RunPython(add_audit_read_permission, remove_audit_read_permission, elidable=False),
    ]
