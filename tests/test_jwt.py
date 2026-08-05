from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt as pyjwt
import pytest

from apps.authz.security.jwt import decode_access_token, encode_access_token
from apps.common.exceptions import InvalidToken

_FAR_FUTURE_CLAIMS = {"sub": "1", "exp": 9_999_999_999, "iat": 1, "jti": "x"}

TEST_SECRET = "test-jwt-secret-must-be-at-least-thirty-two-characters"


def test_access_token_round_trip() -> None:
    token = encode_access_token(
        subject=42,
        roles={"admin", "user"},
        permissions={"user.read", "user.create"},
        secret=TEST_SECRET,
        lifetime=timedelta(minutes=30),
    )

    claims = decode_access_token(token, secret=TEST_SECRET)

    assert claims.subject == "42"
    assert claims.roles == {"admin", "user"}
    assert claims.permissions == {"user.read", "user.create"}
    assert claims.expires_at - claims.issued_at == timedelta(minutes=30)
    assert UUID(claims.token_id)


def test_expired_access_token_is_rejected() -> None:
    token = encode_access_token(
        subject="42",
        roles=[],
        permissions=[],
        secret=TEST_SECRET,
        lifetime=timedelta(seconds=1),
        now=datetime.now(UTC) - timedelta(minutes=1),
    )

    with pytest.raises(InvalidToken, match="invalid or expired"):
        decode_access_token(token, secret=TEST_SECRET)


def test_tampered_access_token_is_rejected() -> None:
    token = encode_access_token(
        subject="42", roles=[], permissions=[], secret=TEST_SECRET
    )

    with pytest.raises(InvalidToken, match="invalid or expired"):
        decode_access_token(f"{token}tampered", secret=TEST_SECRET)


def test_alg_none_token_is_rejected() -> None:
    """A forged ``alg=none`` token must never be accepted (algorithm confusion)."""
    forged = pyjwt.encode(
        {**_FAR_FUTURE_CLAIMS, "roles": [], "perms": []}, key="", algorithm="none"
    )

    with pytest.raises(InvalidToken):
        decode_access_token(forged, secret=TEST_SECRET)


def test_token_signed_with_wrong_secret_is_rejected() -> None:
    forged = pyjwt.encode(
        {**_FAR_FUTURE_CLAIMS, "roles": [], "perms": []},
        "a-different-secret-that-is-thirty-two-chars",
        algorithm="HS256",
    )

    with pytest.raises(InvalidToken):
        decode_access_token(forged, secret=TEST_SECRET)


def test_token_missing_required_claim_is_rejected() -> None:
    """Omitting a required claim (``perms``) must be rejected, not defaulted."""
    forged = pyjwt.encode(
        {**_FAR_FUTURE_CLAIMS, "roles": []}, TEST_SECRET, algorithm="HS256"
    )

    with pytest.raises(InvalidToken):
        decode_access_token(forged, secret=TEST_SECRET)
