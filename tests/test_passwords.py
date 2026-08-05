import pytest

from apps.authz.security.passwords import hash_password, verify_password


@pytest.mark.asyncio
async def test_hash_and_verify_password() -> None:
    encoded = await hash_password("correct horse battery staple")

    assert encoded.startswith("argon2$")
    assert await verify_password("correct horse battery staple", encoded)
    assert not await verify_password("wrong password", encoded)


@pytest.mark.asyncio
async def test_verify_password_performs_dummy_check_for_missing_user() -> None:
    assert not await verify_password("password", None)
    assert not await verify_password("not-a-real-password", "")
