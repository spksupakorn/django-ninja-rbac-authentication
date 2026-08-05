import pytest

from apps.accounts.models import User
from apps.authz.models import Permission, Role, RolePermission, UserRole
from apps.authz.permissions import DEFAULT_ROLE_PERMISSIONS, PERMISSION_CATALOG, RoleName
from apps.authz.repositories.rbac import AuthzRepository


def test_seed_catalog_grants_every_permission_to_admin() -> None:
    assert DEFAULT_ROLE_PERMISSIONS[RoleName.ADMIN] == PERMISSION_CATALOG


def test_seed_catalog_grants_minimum_permission_to_default_user() -> None:
    assert DEFAULT_ROLE_PERMISSIONS[RoleName.USER] == ()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_user_permissions_returns_codes_granted_through_roles() -> None:
    user = await User.objects.acreate(email="user@example.com")
    role = await Role.objects.acreate(name="reviewer")
    read_permission = await Permission.objects.acreate(code="document.read")
    write_permission = await Permission.objects.acreate(code="document.write")
    await UserRole.objects.acreate(user=user, role=role)
    await RolePermission.objects.acreate(role=role, permission=read_permission)
    await RolePermission.objects.acreate(role=role, permission=write_permission)

    assert await AuthzRepository().aget_user_permission_codes(user.id) == {
        "document.read",
        "document.write",
    }


@pytest.mark.django_db
def test_seeded_admin_role_has_every_catalog_permission() -> None:
    admin_role = Role.objects.get(name=RoleName.ADMIN)

    assert set(
        Permission.objects.filter(role_links__role=admin_role).values_list("code", flat=True)
    ) == set(PERMISSION_CATALOG)
