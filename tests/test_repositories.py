import pytest

from apps.accounts.repositories.users import UserRepository
from apps.authz.models import Permission, Role
from apps.authz.repositories.rbac import AuthzRepository


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_user_repository_creates_and_finds_canonical_email() -> None:
    repository = UserRepository()

    created = await repository.acreate(email="user@example.com")

    assert await repository.aget_by_email("USER@EXAMPLE.COM") == created
    assert await repository.aget_or_none(email="missing@example.com") is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_authz_repository_assigns_roles_and_grants_permissions() -> None:
    user = await UserRepository().acreate(email="user@example.com")
    repository = AuthzRepository()
    role = await Role.objects.acreate(name="reviewer")
    permission = await Permission.objects.acreate(code="document.read")

    first_assignment = await repository.aassign_role(user_id=user.id, role_id=role.id)
    second_assignment = await repository.aassign_role(user_id=user.id, role_id=role.id)
    first_grant = await repository.agrant_permission(role_id=role.id, permission_id=permission.id)
    second_grant = await repository.agrant_permission(role_id=role.id, permission_id=permission.id)

    assert first_assignment == second_assignment
    assert first_grant == second_grant
    assert await repository.aget_user_permission_codes(user.id) == {"document.read"}
