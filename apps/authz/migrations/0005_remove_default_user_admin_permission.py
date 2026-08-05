from typing import Any

from django.db import migrations


def remove_default_user_admin_permission(apps: Any, schema_editor: Any) -> None:
    """Keep the default role free of collection-level admin capabilities."""
    RolePermission = apps.get_model("authz", "RolePermission")
    RolePermission.objects.filter(role__name="user", permission__code="user.read").delete()


def restore_default_user_admin_permission(apps: Any, schema_editor: Any) -> None:
    """Restore the historical seed state when reversing this migration."""
    Permission = apps.get_model("authz", "Permission")
    Role = apps.get_model("authz", "Role")
    RolePermission = apps.get_model("authz", "RolePermission")
    role = Role.objects.filter(name="user").first()
    permission = Permission.objects.filter(code="user.read").first()
    if role is not None and permission is not None:
        RolePermission.objects.get_or_create(role=role, permission=permission)


class Migration(migrations.Migration):
    dependencies = [
        ("authz", "0004_refresh_token"),
    ]

    operations = [
        migrations.RunPython(
            remove_default_user_admin_permission,
            restore_default_user_admin_permission,
            elidable=False,
        ),
    ]
