"""Unit tests for security utilities."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)


@pytest.mark.unit
def test_password_hashing():
    """Test password hashing creates a valid hash."""
    password = "TestPassword123"
    hashed = get_password_hash(password)

    assert hashed is not None
    assert hashed != password
    assert len(hashed) > 0


@pytest.mark.unit
def test_password_verification_with_correct_password():
    """Test password verification succeeds with correct password."""
    password = "TestPassword123"
    hashed = get_password_hash(password)

    assert verify_password(password, hashed) is True


@pytest.mark.unit
def test_password_verification_with_incorrect_password():
    """Test password verification fails with incorrect password."""
    password = "TestPassword123"
    wrong_password = "WrongPassword456"
    hashed = get_password_hash(password)

    assert verify_password(wrong_password, hashed) is False


@pytest.mark.unit
def test_password_hashing_is_not_deterministic():
    """Test that hashing the same password twice produces different hashes."""
    password = "TestPassword123"
    hash1 = get_password_hash(password)
    hash2 = get_password_hash(password)

    assert hash1 != hash2
    assert verify_password(password, hash1) is True
    assert verify_password(password, hash2) is True


@pytest.mark.unit
def test_create_access_token_with_default_expiration():
    """Test creating an access token with default expiration."""
    data = {"sub": "testuser"}
    token = create_access_token(data)

    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 0


@pytest.mark.unit
def test_create_access_token_with_custom_expiration():
    """Test creating an access token with custom expiration."""
    data = {"sub": "testuser"}
    expires_delta = timedelta(minutes=15)
    token = create_access_token(data, expires_delta)

    assert token is not None
    decoded = decode_token(token)
    assert decoded["sub"] == "testuser"


@pytest.mark.unit
def test_create_refresh_token():
    """Test creating a refresh token."""
    data = {"sub": "testuser"}
    token = create_refresh_token(data)

    assert token is not None
    assert isinstance(token, str)

    decoded = decode_token(token)
    assert decoded["sub"] == "testuser"
    assert decoded["type"] == "refresh"


@pytest.mark.unit
def test_decode_valid_token():
    """Test decoding a valid token."""
    data = {"sub": "testuser"}
    token = create_access_token(data)
    decoded = decode_token(token)

    assert decoded["sub"] == "testuser"
    assert "exp" in decoded
    assert "iat" in decoded


@pytest.mark.unit
def test_decode_token_contains_expiration():
    """Test that decoded token contains expiration time."""
    data = {"sub": "testuser"}
    token = create_access_token(data)
    decoded = decode_token(token)

    exp_timestamp = decoded["exp"]
    exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=UTC)
    now = datetime.now(UTC)

    # Expiration should be in the future
    assert exp_datetime > now


@pytest.mark.unit
def test_decode_token_with_invalid_signature():
    """Test decoding a token with invalid signature raises error."""
    data = {"sub": "testuser"}
    # Create token with different secret
    token = jwt.encode(data, "wrong-secret", algorithm=settings.ALGORITHM)

    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token)


@pytest.mark.unit
def test_decode_expired_token():
    """Test decoding an expired token raises error."""
    data = {"sub": "testuser"}
    # Create token that expired 1 minute ago
    expires_delta = timedelta(minutes=-1)
    token = create_access_token(data, expires_delta)

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token)


@pytest.mark.unit
def test_decode_malformed_token():
    """Test decoding a malformed token raises error."""
    malformed_token = "not.a.valid.jwt.token"

    with pytest.raises(jwt.InvalidTokenError):
        decode_token(malformed_token)


@pytest.mark.unit
def test_decode_token_with_missing_segments():
    """Test decoding a token with missing segments raises error."""
    incomplete_token = "header.payload"  # Missing signature

    with pytest.raises(jwt.InvalidTokenError):
        decode_token(incomplete_token)


@pytest.mark.unit
def test_token_includes_issued_at_time():
    """Test that created tokens include issued at (iat) claim."""
    data = {"sub": "testuser"}
    token = create_access_token(data)
    decoded = decode_token(token)

    assert "iat" in decoded
    iat_timestamp = decoded["iat"]
    iat_datetime = datetime.fromtimestamp(iat_timestamp, tz=UTC)
    now = datetime.now(UTC)

    # Issued time should be recent (within last minute)
    time_diff = (now - iat_datetime).total_seconds()
    assert time_diff < 60  # Less than 1 minute ago


@pytest.mark.unit
def test_refresh_token_has_longer_expiration():
    """Test that refresh tokens have longer expiration than access tokens."""
    data = {"sub": "testuser"}
    access_token = create_access_token(data)
    refresh_token = create_refresh_token(data)

    access_decoded = decode_token(access_token)
    refresh_decoded = decode_token(refresh_token)

    access_exp = access_decoded["exp"]
    refresh_exp = refresh_decoded["exp"]

    # Refresh token should expire later than access token
    assert refresh_exp > access_exp
