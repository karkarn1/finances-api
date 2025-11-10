"""Tests for UserRepository."""

import pytest

from app.core.security import get_password_hash
from app.models.user import User
from app.repositories.user import UserRepository


@pytest.mark.asyncio
async def test_get_by_email(test_db, test_user):
    """Test getting user by email."""
    repo = UserRepository(User, test_db)
    user = await repo.get_by_email(test_user.email)

    assert user is not None
    assert user.id == test_user.id
    assert user.email == test_user.email


@pytest.mark.asyncio
async def test_get_by_email_not_found(test_db):
    """Test getting user by email when user doesn't exist."""
    repo = UserRepository(User, test_db)
    user = await repo.get_by_email("nonexistent@example.com")

    assert user is None


@pytest.mark.asyncio
async def test_get_by_username(test_db, test_user):
    """Test getting user by username."""
    repo = UserRepository(User, test_db)
    user = await repo.get_by_username(test_user.username)

    assert user is not None
    assert user.id == test_user.id
    assert user.username == test_user.username


@pytest.mark.asyncio
async def test_get_by_username_or_email_with_username(test_db, test_user):
    """Test getting user by username or email using username."""
    repo = UserRepository(User, test_db)
    user = await repo.get_by_username_or_email(test_user.username)

    assert user is not None
    assert user.id == test_user.id


@pytest.mark.asyncio
async def test_get_by_username_or_email_with_email(test_db, test_user):
    """Test getting user by username or email using email."""
    repo = UserRepository(User, test_db)
    user = await repo.get_by_username_or_email(test_user.email)

    assert user is not None
    assert user.id == test_user.id


@pytest.mark.asyncio
async def test_exists_by_email(test_db, test_user):
    """Test checking if email exists."""
    repo = UserRepository(User, test_db)

    assert await repo.exists_by_email(test_user.email) is True
    assert await repo.exists_by_email("nonexistent@example.com") is False


@pytest.mark.asyncio
async def test_exists_by_username(test_db, test_user):
    """Test checking if username exists."""
    repo = UserRepository(User, test_db)

    assert await repo.exists_by_username(test_user.username) is True
    assert await repo.exists_by_username("nonexistent") is False


@pytest.mark.asyncio
async def test_get_active_users(test_db, test_user, test_inactive_user):
    """Test getting active users only."""
    repo = UserRepository(User, test_db)
    active_users = await repo.get_active_users()

    # Should include active user
    assert any(u.id == test_user.id for u in active_users)

    # Should NOT include inactive user
    assert not any(u.id == test_inactive_user.id for u in active_users)


@pytest.mark.asyncio
async def test_get_users_with_reset_tokens(test_db):
    """Test getting users with reset tokens."""
    repo = UserRepository(User, test_db)

    # Create user with reset token
    user = User(
        email="reset@example.com",
        username="resetuser",
        hashed_password=get_password_hash("Password123"),
        is_active=True,
        is_superuser=False,
        reset_token="some_token_hash",
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)

    users = await repo.get_users_with_reset_tokens()

    # Should find user with reset token
    assert any(u.id == user.id for u in users)
