"""Service layer for user-related operations.

This service centralizes common user database operations to avoid duplication
across different route handlers. Now uses UserRepository for all data access.
"""

import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.models.user import User
from app.repositories.user import UserRepository

logger = logging.getLogger(__name__)


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Retrieve a user by their email address.

    Args:
        db: Async database session
        email: User's email address

    Returns:
        User model instance if found, None otherwise

    Example:
        >>> user = await get_user_by_email(db, "user@example.com")
        >>> if user:
        ...     print(user.username)
    """
    repo = UserRepository(User, db)
    return await repo.get_by_email(email)


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    """Retrieve a user by their username.

    Args:
        db: Async database session
        username: User's username

    Returns:
        User model instance if found, None otherwise

    Example:
        >>> user = await get_user_by_username(db, "johndoe")
        >>> if user:
        ...     print(user.email)
    """
    repo = UserRepository(User, db)
    return await repo.get_by_username(username)


async def get_user_by_username_or_email(db: AsyncSession, identifier: str) -> User | None:
    """Retrieve a user by username or email address.

    Tries username first, then falls back to email lookup if not found.
    This is useful for login flows where users can authenticate with either.

    Args:
        db: Async database session
        identifier: Username or email address

    Returns:
        User model instance if found, None otherwise

    Example:
        >>> # Can use username
        >>> user = await get_user_by_username_or_email(db, "johndoe")
        >>> # Or email
        >>> user = await get_user_by_username_or_email(db, "john@example.com")
    """
    repo = UserRepository(User, db)
    return await repo.get_by_username_or_email(identifier)


async def email_exists(db: AsyncSession, email: str) -> bool:
    """Check if an email address is already registered.

    Args:
        db: Async database session
        email: Email address to check

    Returns:
        True if email exists, False otherwise

    Example:
        >>> if await email_exists(db, "user@example.com"):
        ...     raise ValueError("Email already registered")
    """
    repo = UserRepository(User, db)
    return await repo.exists_by_email(email)


async def username_exists(db: AsyncSession, username: str) -> bool:
    """Check if a username is already registered.

    Args:
        db: Async database session
        username: Username to check

    Returns:
        True if username exists, False otherwise

    Example:
        >>> if await username_exists(db, "johndoe"):
        ...     raise ValueError("Username already taken")
    """
    repo = UserRepository(User, db)
    return await repo.exists_by_username(username)


async def authenticate_user(
    db: AsyncSession,
    username_or_email: str,
    password: str,
) -> User:
    """Authenticate a user by username/email and password.

    Verifies user credentials and ensures the user is active.
    This function consolidates authentication logic to avoid duplication
    across login endpoints.

    Args:
        db: Async database session
        username_or_email: Username or email address
        password: Plain text password to verify

    Returns:
        User: Authenticated user instance

    Raises:
        HTTPException: 401 if credentials invalid, 400 if user inactive

    Example:
        >>> user = await authenticate_user(db, "john@example.com", "secret123")
        >>> print(user.username)
        johndoe
    """
    # Try to find user by username or email
    user = await get_user_by_username_or_email(db, username_or_email)

    # Verify user exists and password is correct
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    return user
