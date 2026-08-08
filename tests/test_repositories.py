import pytest
from django.db import IntegrityError

from apps.accounts.models import User
from apps.accounts.repositories.users import UserRepository
from apps.authz.models import Permission, Role
from apps.authz.repositories.rbac import AuthzRepository


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_user_repository_creates_and_finds_canonical_email() -> None:
    repository = UserRepository()

    created = await repository.acreate(email="user@example.com", password="encoded-password")
    credentials = await repository.aget_credentials("USER@EXAMPLE.COM")

    assert await repository.aget_by_id(created.id) == created
    assert await repository.aget_by_id(999_999) is None
    assert credentials is not None
    assert credentials.email == "user@example.com"
    assert credentials.password_hash == "encoded-password"
    assert not hasattr(created, "password")


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_create_user_with_role_rolls_back_when_role_link_fails() -> None:
    with pytest.raises(IntegrityError):
        await AuthzRepository().acreate_user_with_role(
            email="orphan@example.com", password_hash="hash", role_id=999_999
        )

    assert not await User.objects.filter(email="orphan@example.com").aexists()


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
