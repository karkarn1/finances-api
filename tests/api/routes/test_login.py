"""Integration tests for authentication endpoints."""

from datetime import UTC

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.user import User


@pytest.mark.integration
async def test_register_with_valid_data(client: AsyncClient, test_db: AsyncSession):
    """Test user registration with valid data."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "NewPass123",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["username"] == "newuser"
    assert "id" in data
    assert "hashed_password" not in data

    # Verify user exists in database
    result = await test_db.execute(select(User).where(User.username == "newuser"))
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.email == "newuser@example.com"


@pytest.mark.integration
async def test_register_with_duplicate_email(client: AsyncClient, test_user: User):
    """Test registration with duplicate email returns 400."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": test_user.email,
            "username": "differentuser",
            "password": "NewPass123",
        },
    )

    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


@pytest.mark.integration
async def test_register_with_duplicate_username(client: AsyncClient, test_user: User):
    """Test registration with duplicate username returns 400."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "different@example.com",
            "username": test_user.username,
            "password": "NewPass123",
        },
    )

    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


@pytest.mark.integration
async def test_register_with_invalid_email(client: AsyncClient):
    """Test registration with invalid email returns 422."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "not-an-email",
            "username": "newuser",
            "password": "NewPass123",
        },
    )

    assert response.status_code == 422


@pytest.mark.integration
async def test_register_with_short_password(client: AsyncClient):
    """Test registration with short password returns 422."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "short",
        },
    )

    assert response.status_code == 422


@pytest.mark.integration
async def test_register_with_short_username(client: AsyncClient):
    """Test registration with short username returns 422."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@example.com",
            "username": "ab",
            "password": "NewPass123",
        },
    )

    assert response.status_code == 422


@pytest.mark.integration
async def test_login_with_username(client: AsyncClient, test_user: User):
    """Test login with username and password."""
    response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": test_user.username,
            "password": "TestPass123",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.integration
async def test_login_with_email(client: AsyncClient, test_user: User):
    """Test login with email and password."""
    response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": test_user.email,
            "password": "TestPass123",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.integration
async def test_login_with_wrong_password(client: AsyncClient, test_user: User):
    """Test login with wrong password returns 401."""
    response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": test_user.username,
            "password": "WrongPassword",
        },
    )

    assert response.status_code == 401
    assert "incorrect" in response.json()["detail"].lower()


@pytest.mark.integration
async def test_login_with_nonexistent_user(client: AsyncClient):
    """Test login with nonexistent user returns 401."""
    response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "nonexistent",
            "password": "SomePassword123",
        },
    )

    assert response.status_code == 401


@pytest.mark.integration
async def test_login_with_inactive_user(client: AsyncClient, test_inactive_user: User):
    """Test login with inactive user returns 400."""
    response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": test_inactive_user.username,
            "password": "InactivePass123",
        },
    )

    assert response.status_code == 400
    assert "inactive" in response.json()["detail"].lower()


@pytest.mark.integration
async def test_login_tokens_endpoint(client: AsyncClient, test_user: User):
    """Test login/tokens endpoint returns both access and refresh tokens."""
    response = await client.post(
        "/api/v1/auth/login/tokens",
        data={
            "username": test_user.username,
            "password": "TestPass123",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.integration
async def test_get_current_user_me(client: AsyncClient, auth_headers: dict[str, str]):
    """Test /me endpoint returns current user info."""
    response = await client.get("/api/v1/auth/me", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert "hashed_password" not in data


@pytest.mark.integration
async def test_get_current_user_me_without_token(client: AsyncClient):
    """Test /me endpoint without token returns 401."""
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401


@pytest.mark.integration
async def test_get_current_user_me_with_invalid_token(client: AsyncClient):
    """Test /me endpoint with invalid token returns 401."""
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer invalid-token"}
    )

    assert response.status_code == 401


@pytest.mark.integration
async def test_get_current_user_me_with_inactive_user(
    client: AsyncClient, inactive_user_auth_headers: dict[str, str]
):
    """Test /me endpoint with inactive user token returns 400."""
    response = await client.get("/api/v1/auth/me", headers=inactive_user_auth_headers)

    assert response.status_code == 400
    assert "inactive" in response.json()["detail"].lower()


@pytest.mark.integration
async def test_test_token_endpoint_with_valid_token(
    client: AsyncClient, auth_headers: dict[str, str]
):
    """Test /test-token endpoint with valid token."""
    response = await client.post("/api/v1/auth/test-token", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"


@pytest.mark.integration
async def test_test_token_endpoint_without_token(client: AsyncClient):
    """Test /test-token endpoint without token returns 401."""
    response = await client.post("/api/v1/auth/test-token")

    assert response.status_code == 401


@pytest.mark.integration
async def test_test_token_endpoint_with_nonexistent_user(
    client: AsyncClient, test_db: AsyncSession
):
    """Test /test-token with token for deleted user returns 401."""
    # Create a token for a user that doesn't exist
    token = create_access_token(data={"sub": "deleteduser"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post("/api/v1/auth/test-token", headers=headers)

    assert response.status_code == 401


# Password Reset Tests


@pytest.mark.integration
async def test_forgot_password_with_valid_email(
    client: AsyncClient, test_user: User, test_db: AsyncSession
):
    """Test forgot password with valid email."""
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": test_user.email},
    )

    assert response.status_code == 200
    data = response.json()
    assert "password reset" in data["message"].lower()

    # Verify token was set in database
    await test_db.refresh(test_user)
    assert test_user.reset_token is not None
    assert test_user.reset_token_expires is not None


@pytest.mark.integration
async def test_forgot_password_with_nonexistent_email(client: AsyncClient):
    """Test forgot password with non-existent email returns 200 (security)."""
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nonexistent@example.com"},
    )

    # Should still return 200 to not reveal if email exists
    assert response.status_code == 200
    data = response.json()
    assert "password reset" in data["message"].lower()


@pytest.mark.integration
async def test_forgot_password_with_invalid_email(client: AsyncClient):
    """Test forgot password with invalid email format returns 422."""
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "not-an-email"},
    )

    assert response.status_code == 422


@pytest.mark.integration
async def test_reset_password_with_valid_token(
    client: AsyncClient, test_user: User, test_db: AsyncSession
):
    """Test reset password with valid token."""
    # First request a password reset
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": test_user.email},
    )
    assert response.status_code == 200

    # Get the plaintext token from the user object
    # In real scenario, this would come from email link
    # For testing, we need to extract it from logs or generate it
    import secrets

    from app.core.security import get_password_hash

    plaintext_token = secrets.token_urlsafe(32)
    hashed_token = get_password_hash(plaintext_token)

    # Update user with our known token
    test_user.reset_token = hashed_token
    from datetime import datetime, timedelta

    test_user.reset_token_expires = datetime.now(UTC) + timedelta(minutes=30)
    await test_db.commit()

    # Now reset the password
    new_password = "NewSecurePassword123"
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": plaintext_token, "new_password": new_password},
    )

    assert response.status_code == 200
    data = response.json()
    assert "successfully" in data["message"].lower()

    # Verify token was cleared
    await test_db.refresh(test_user)
    assert test_user.reset_token is None
    assert test_user.reset_token_expires is None

    # Verify can login with new password
    login_response = await client.post(
        "/api/v1/auth/login",
        data={"username": test_user.username, "password": new_password},
    )
    assert login_response.status_code == 200


@pytest.mark.integration
async def test_reset_password_with_invalid_token(client: AsyncClient):
    """Test reset password with invalid token returns 400."""
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "invalid-token-12345", "new_password": "NewPass123"},
    )

    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()


@pytest.mark.integration
async def test_reset_password_with_expired_token(
    client: AsyncClient, test_user: User, test_db: AsyncSession
):
    """Test reset password with expired token returns 400."""
    import secrets
    from datetime import datetime, timedelta

    from app.core.security import get_password_hash

    plaintext_token = secrets.token_urlsafe(32)
    hashed_token = get_password_hash(plaintext_token)

    # Set token with past expiration
    test_user.reset_token = hashed_token
    test_user.reset_token_expires = datetime.now(UTC) - timedelta(minutes=1)
    await test_db.commit()

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": plaintext_token, "new_password": "NewPass123"},
    )

    assert response.status_code == 400
    assert "expired" in response.json()["detail"].lower()

    # Verify expired token was cleared
    await test_db.refresh(test_user)
    assert test_user.reset_token is None
    assert test_user.reset_token_expires is None


@pytest.mark.integration
async def test_reset_password_token_is_single_use(
    client: AsyncClient, test_user: User, test_db: AsyncSession
):
    """Test that reset tokens can only be used once."""
    import secrets
    from datetime import datetime, timedelta

    from app.core.security import get_password_hash

    plaintext_token = secrets.token_urlsafe(32)
    hashed_token = get_password_hash(plaintext_token)

    test_user.reset_token = hashed_token
    test_user.reset_token_expires = datetime.now(UTC) + timedelta(minutes=30)
    await test_db.commit()

    # First reset should succeed
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": plaintext_token, "new_password": "FirstNewPass123"},
    )
    assert response.status_code == 200

    # Second use of same token should fail
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": plaintext_token, "new_password": "SecondNewPass123"},
    )
    assert response.status_code == 400


@pytest.mark.integration
async def test_reset_password_with_short_password(
    client: AsyncClient, test_user: User, test_db: AsyncSession
):
    """Test reset password with short password returns 422."""
    import secrets
    from datetime import datetime, timedelta

    from app.core.security import get_password_hash

    plaintext_token = secrets.token_urlsafe(32)
    hashed_token = get_password_hash(plaintext_token)

    test_user.reset_token = hashed_token
    test_user.reset_token_expires = datetime.now(UTC) + timedelta(minutes=30)
    await test_db.commit()

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": plaintext_token, "new_password": "short"},
    )

    assert response.status_code == 422
