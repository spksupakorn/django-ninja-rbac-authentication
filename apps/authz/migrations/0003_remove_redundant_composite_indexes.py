from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("authz", "0002_seed_roles_and_permissions"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="userrole",
            name="authz_userrole_user_role_idx",
        ),
        migrations.RemoveIndex(
            model_name="rolepermission",
            name="authz_roleperm_role_perm_idx",
        ),
    ]
