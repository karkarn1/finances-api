"""Tests for user service functions."""

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.user import User
from app.services.user_service import (
    authenticate_user,
    email_exists,
    get_user_by_email,
    get_user_by_username,
    get_user_by_username_or_email,
    username_exists,
)


@pytest.mark.integration
async def test_authenticate_user_success_with_username(
    test_db: AsyncSession, test_user: User
) -> None:
    """Test successful authentication using username."""
    # Authenticate with username
    authenticated_user = await authenticate_user(test_db, "testuser", "TestPass123")

    assert authenticated_user is not None
    assert authenticated_user.id == test_user.id
    assert authenticated_user.username == test_user.username
    assert authenticated_user.email == test_user.email


@pytest.mark.integration
async def test_authenticate_user_success_with_email(
    test_db: AsyncSession, test_user: User
) -> None:
    """Test successful authentication using email."""
    # Authenticate with email
    authenticated_user = await authenticate_user(test_db, "test@example.com", "TestPass123")

    assert authenticated_user is not None
    assert authenticated_user.id == test_user.id
    assert authenticated_user.username == test_user.username
    assert authenticated_user.email == test_user.email


@pytest.mark.integration
async def test_authenticate_user_invalid_username(test_db: AsyncSession) -> None:
    """Test authentication with non-existent username."""
    with pytest.raises(HTTPException) as exc_info:
        await authenticate_user(test_db, "nonexistent", "password")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Incorrect username or password"
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


@pytest.mark.integration
async def test_authenticate_user_invalid_password(
    test_db: AsyncSession, test_user: User
) -> None:
    """Test authentication with incorrect password."""
    with pytest.raises(HTTPException) as exc_info:
        await authenticate_user(test_db, "testuser", "WrongPassword")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Incorrect username or password"
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


@pytest.mark.integration
async def test_authenticate_user_inactive_user(
    test_db: AsyncSession, test_inactive_user: User
) -> None:
    """Test authentication with inactive user."""
    with pytest.raises(HTTPException) as exc_info:
        await authenticate_user(test_db, "inactiveuser", "InactivePass123")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Inactive user"


@pytest.mark.integration
async def test_authenticate_user_empty_username(test_db: AsyncSession) -> None:
    """Test authentication with empty username."""
    with pytest.raises(HTTPException) as exc_info:
        await authenticate_user(test_db, "", "password")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Incorrect username or password"


@pytest.mark.integration
async def test_authenticate_user_none_password(
    test_db: AsyncSession, test_user: User
) -> None:
    """Test authentication ensures password verification is called."""
    # Create user with known password
    user = User(
        email="verify@example.com",
        username="verifyuser",
        hashed_password=get_password_hash("CorrectPassword"),
        is_active=True,
        is_superuser=False,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)

    # Test with correct password
    authenticated = await authenticate_user(test_db, "verifyuser", "CorrectPassword")
    assert authenticated.id == user.id

    # Test with wrong password
    with pytest.raises(HTTPException) as exc_info:
        await authenticate_user(test_db, "verifyuser", "WrongPassword")
    assert exc_info.value.status_code == 401


@pytest.mark.integration
async def test_get_user_by_email_exists(test_db: AsyncSession, test_user: User) -> None:
    """Test retrieving user by email when user exists."""
    user = await get_user_by_email(test_db, "test@example.com")

    assert user is not None
    assert user.id == test_user.id
    assert user.email == "test@example.com"


@pytest.mark.integration
async def test_get_user_by_email_not_exists(test_db: AsyncSession) -> None:
    """Test retrieving user by email when user doesn't exist."""
    user = await get_user_by_email(test_db, "nonexistent@example.com")

    assert user is None


@pytest.mark.integration
async def test_get_user_by_username_exists(test_db: AsyncSession, test_user: User) -> None:
    """Test retrieving user by username when user exists."""
    user = await get_user_by_username(test_db, "testuser")

    assert user is not None
    assert user.id == test_user.id
    assert user.username == "testuser"


@pytest.mark.integration
async def test_get_user_by_username_not_exists(test_db: AsyncSession) -> None:
    """Test retrieving user by username when user doesn't exist."""
    user = await get_user_by_username(test_db, "nonexistent")

    assert user is None


@pytest.mark.integration
async def test_get_user_by_username_or_email_with_username(
    test_db: AsyncSession, test_user: User
) -> None:
    """Test retrieving user by username using username_or_email function."""
    user = await get_user_by_username_or_email(test_db, "testuser")

    assert user is not None
    assert user.id == test_user.id
    assert user.username == "testuser"


@pytest.mark.integration
async def test_get_user_by_username_or_email_with_email(
    test_db: AsyncSession, test_user: User
) -> None:
    """Test retrieving user by email using username_or_email function."""
    user = await get_user_by_username_or_email(test_db, "test@example.com")

    assert user is not None
    assert user.id == test_user.id
    assert user.email == "test@example.com"


@pytest.mark.integration
async def test_get_user_by_username_or_email_not_exists(test_db: AsyncSession) -> None:
    """Test retrieving user when neither username nor email exists."""
    user = await get_user_by_username_or_email(test_db, "nonexistent")

    assert user is None


@pytest.mark.integration
async def test_email_exists_true(test_db: AsyncSession, test_user: User) -> None:
    """Test checking if email exists when it does."""
    exists = await email_exists(test_db, "test@example.com")

    assert exists is True


@pytest.mark.integration
async def test_email_exists_false(test_db: AsyncSession) -> None:
    """Test checking if email exists when it doesn't."""
    exists = await email_exists(test_db, "nonexistent@example.com")

    assert exists is False


@pytest.mark.integration
async def test_username_exists_true(test_db: AsyncSession, test_user: User) -> None:
    """Test checking if username exists when it does."""
    exists = await username_exists(test_db, "testuser")

    assert exists is True


@pytest.mark.integration
async def test_username_exists_false(test_db: AsyncSession) -> None:
    """Test checking if username exists when it doesn't."""
    exists = await username_exists(test_db, "nonexistent")

    assert exists is False
