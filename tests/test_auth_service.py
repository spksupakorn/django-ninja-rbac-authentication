import pytest

from apps.audit.context import AuditContext
from apps.authz.models import RefreshToken, Role
from apps.authz.security.jwt import decode_access_token
from apps.authz.services.auth import AuthService
from apps.common.exceptions import EmailAlreadyExists, InvalidToken, TokenReused

CONTEXT = AuditContext()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_register_assigns_default_role_and_rejects_duplicate_email() -> None:
    await Role.objects.aget_or_create(name="user")
    service = AuthService()

    user = await service.register(email="User@Example.com", password="password", context=CONTEXT)

    assert user.email == "user@example.com"
    assert await service.authz.aget_user_role_names(user.id) == {"user"}
    with pytest.raises(EmailAlreadyExists):
        await service.register(email="user@example.com", password="password", context=CONTEXT)


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_refresh_rotates_a_token_within_its_family() -> None:
    await Role.objects.aget_or_create(name="user")
    service = AuthService()
    user = await service.register(email="user@example.com", password="password", context=CONTEXT)
    initial_pair = await service.login(
        email="user@example.com", password="password", context=CONTEXT
    )

    rotated_pair = await service.refresh(
        raw_refresh_token=initial_pair.refresh_token, context=CONTEXT
    )

    claims = decode_access_token(rotated_pair.access_token)
    tokens = [
        token async for token in RefreshToken.objects.filter(user_id=user.id).order_by("id")
    ]
    assert claims.subject == str(user.id)
    assert initial_pair.refresh_token != rotated_pair.refresh_token
    assert len(tokens) == 2
    assert tokens[0].revoked_at is not None
    assert tokens[1].parent_id == tokens[0].id
    assert tokens[1].family_id == tokens[0].family_id


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_reuse_of_a_rotated_token_revokes_its_full_family() -> None:
    await Role.objects.aget_or_create(name="user")
    service = AuthService()
    await service.register(email="user@example.com", password="password", context=CONTEXT)
    initial_pair = await service.login(
        email="user@example.com", password="password", context=CONTEXT
    )
    await service.refresh(raw_refresh_token=initial_pair.refresh_token, context=CONTEXT)

    with pytest.raises(TokenReused):
        await service.refresh(raw_refresh_token=initial_pair.refresh_token, context=CONTEXT)

    tokens = [token async for token in RefreshToken.objects.all()]
    assert len(tokens) == 2
    assert all(token.revoked_at is not None for token in tokens)


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_logout_revokes_the_presented_refresh_token() -> None:
    await Role.objects.aget_or_create(name="user")
    service = AuthService()
    await service.register(email="user@example.com", password="password", context=CONTEXT)
    token_pair = await service.login(
        email="user@example.com", password="password", context=CONTEXT
    )

    await service.logout(raw_refresh_token=token_pair.refresh_token, context=CONTEXT)

    stored_tokens = [token async for token in RefreshToken.objects.all()]
    assert len(stored_tokens) == 1
    assert stored_tokens[0].revoked_at is not None


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_refresh_rejects_an_unknown_token_and_logout_is_idempotent() -> None:
    service = AuthService()

    with pytest.raises(InvalidToken):
        await service.refresh(raw_refresh_token="unknown-token", context=CONTEXT)

    await service.logout(raw_refresh_token="unknown-token", context=CONTEXT)
