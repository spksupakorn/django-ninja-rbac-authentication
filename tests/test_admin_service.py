import pytest

from apps.accounts.services.admin import AdminService
from apps.audit.actions import AuditAction
from apps.audit.context import AuditContext
from apps.audit.models import AuditLog
from apps.authz.models import Role
from apps.authz.security.passwords import verify_password
from apps.common.exceptions import EmailAlreadyExists, ResourceNotFound

CONTEXT = AuditContext(actor_id=1, actor_email="admin@example.com")


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_admin_service_updates_user_and_keeps_empty_patch_idempotent() -> None:
    await Role.objects.aget_or_create(name="user")
    service = AdminService()
    user = await service.create_user(
        email="before@example.com", password="password123", context=CONTEXT
    )

    updated = await service.update_user(
        user_id=user.id,
        email="After@Example.com",
        password="new-password123",
        is_active=False,
        context=CONTEXT,
    )
    unchanged = await service.update_user(user_id=user.id, context=CONTEXT)

    assert updated.email == "after@example.com"
    assert not updated.is_active
    assert await verify_password("new-password123", updated.password)
    assert unchanged.id == user.id

    # Password changes are auditable by field name, but the value never persists.
    audit = await AuditLog.objects.aget(action=AuditAction.USER_UPDATE)
    assert audit.metadata == {"changed_fields": ["email", "is_active", "password"]}
    assert "new-password123" not in str(audit.metadata)
    assert updated.password not in str(audit.metadata)


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_admin_service_translates_missing_resources_and_duplicate_email() -> None:
    await Role.objects.aget_or_create(name="user")
    service = AdminService()
    first = await service.create_user(
        email="first@example.com", password="password123", context=CONTEXT
    )
    second = await service.create_user(
        email="second@example.com", password="password123", context=CONTEXT
    )

    with pytest.raises(EmailAlreadyExists):
        await service.update_user(user_id=second.id, email=first.email, context=CONTEXT)
    with pytest.raises(ResourceNotFound):
        await service.get_user(999_999)
    with pytest.raises(ResourceNotFound):
        await service.update_user(user_id=999_999, is_active=False, context=CONTEXT)
    with pytest.raises(ResourceNotFound):
        await service.delete_user(999_999, context=CONTEXT)
    with pytest.raises(ResourceNotFound):
        await service.assign_role(user_id=999_999, role_id=1, context=CONTEXT)
    with pytest.raises(ResourceNotFound):
        await service.assign_role(user_id=first.id, role_id=999_999, context=CONTEXT)
