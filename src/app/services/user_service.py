"""Service layer for user-related operations.

This service centralizes common user database operations to avoid duplication
across different route handlers. Now uses UserRepository for all data access.
"""

import logging
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, verify_password
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


async def create_user_tokens(
    db: AsyncSession,
    username_or_email: str,
    password: str,
    *,
    include_refresh: bool = False,
) -> dict[str, str]:
    """Authenticate user and create JWT tokens.

    Centralizes token creation logic to eliminate duplication between
    login endpoints. Handles both single token (access only) and dual
    token (access + refresh) scenarios.

    Args:
        db: Async database session
        username_or_email: Username or email address
        password: Plain text password to verify
        include_refresh: Whether to include refresh token in response

    Returns:
        Dictionary containing:
        - access_token: JWT access token
        - refresh_token: JWT refresh token (only if include_refresh=True)

    Raises:
        HTTPException: 401 if credentials invalid, 400 if user inactive

    Example:
        >>> # Get access token only
        >>> tokens = await create_user_tokens(db, "john@example.com", "secret123")
        >>> print(tokens['access_token'])

        >>> # Get both access and refresh tokens
        >>> tokens = await create_user_tokens(
        ...     db, "john@example.com", "secret123", include_refresh=True
        ... )
        >>> print(tokens['refresh_token'])
    """
    # Authenticate user (will raise HTTPException if invalid)
    user = await authenticate_user(db, username_or_email, password)

    # Create access token with configured expiration
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires,
    )

    tokens = {"access_token": access_token}

    # Create refresh token if requested
    if include_refresh:
        refresh_token = create_refresh_token(data={"sub": user.username})
        tokens["refresh_token"] = refresh_token

    return tokens
