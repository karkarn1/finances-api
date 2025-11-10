"""Authentication routes."""

import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import CurrentActiveUser
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    MessageResponse,
    ResetPasswordRequest,
    Token,
    TokenPair,
    UserRegister,
)
from app.schemas.user import UserResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Register a new user.

    Args:
        user_data: User registration data
        db: Database session

    Returns:
        The created user

    Raises:
        HTTPException: If username or email already exists
    """
    # Check if username already exists
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Check if email already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
        is_active=True,
        is_superuser=False,
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """
    OAuth2 compatible token login.

    Get an access token for future requests using username and password.

    Args:
        form_data: OAuth2 form with username and password
        db: Database session

    Returns:
        Access token

    Raises:
        HTTPException: If credentials are invalid
    """
    # Try to find user by username
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()

    # If not found by username, try email
    if not user:
        result = await db.execute(select(User).where(User.email == form_data.username))
        user = result.scalar_one_or_none()

    # Verify user exists and password is correct
    if not user or not verify_password(form_data.password, user.hashed_password):
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

    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires,
    )

    return Token(access_token=access_token)


@router.post("/login/tokens", response_model=TokenPair)
async def login_with_refresh(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenPair:
    """
    Login and get both access and refresh tokens.

    Args:
        form_data: OAuth2 form with username and password
        db: Database session

    Returns:
        Access and refresh tokens

    Raises:
        HTTPException: If credentials are invalid
    """
    # Try to find user by username
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()

    # If not found by username, try email
    if not user:
        result = await db.execute(select(User).where(User.email == form_data.username))
        user = result.scalar_one_or_none()

    # Verify user exists and password is correct
    if not user or not verify_password(form_data.password, user.hashed_password):
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

    # Create tokens
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires,
    )
    refresh_token = create_refresh_token(data={"sub": user.username})

    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: CurrentActiveUser) -> User:
    """
    Get current authenticated user.

    Args:
        current_user: The authenticated user (from dependency)

    Returns:
        The current user
    """
    return current_user


@router.post("/test-token", response_model=UserResponse)
async def test_token(current_user: CurrentActiveUser) -> User:
    """
    Test access token validity.

    Args:
        current_user: The authenticated user (from dependency)

    Returns:
        The current user
    """
    return current_user


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    request_data: ForgotPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """
    Request a password reset token.

    Generates a secure token and stores it hashed in the database.
    Token expires in 30 minutes.

    Args:
        request_data: Email address for password reset
        db: Database session

    Returns:
        Success message (always returns 200 for security)

    Note:
        For security, this endpoint always returns success even if
        the email doesn't exist in the database.
    """
    # Try to find user by email
    result = await db.execute(select(User).where(User.email == request_data.email))
    user = result.scalar_one_or_none()

    if user:
        # Generate secure random token (32 bytes = 43 chars base64)
        plaintext_token = secrets.token_urlsafe(32)

        # Hash the token before storing (same security as passwords)
        hashed_token = get_password_hash(plaintext_token)

        # Set token expiration (30 minutes from now)
        token_expires = datetime.now(UTC) + timedelta(minutes=30)

        # Update user with hashed token and expiration
        user.reset_token = hashed_token
        user.reset_token_expires = token_expires

        await db.commit()

        # In development, log the plaintext token for testing
        if settings.ENVIRONMENT == "development":
            logger.info(
                f"Password reset token for {user.email}: {plaintext_token}"
            )
            logger.info(
                f"Token expires at: {token_expires.isoformat()}"
            )

    # Always return success (don't reveal if email exists)
    return MessageResponse(
        message="If the email exists, a password reset link has been sent."
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    request_data: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """
    Reset password using a valid reset token.

    Args:
        request_data: Reset token and new password
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If token is invalid, expired, or not found
    """
    # Get all users with non-null reset tokens
    result = await db.execute(
        select(User).where(User.reset_token.isnot(None))
    )
    users_with_tokens = result.scalars().all()

    # Find user by verifying the plaintext token against stored hashed tokens
    user = None
    for candidate_user in users_with_tokens:
        if candidate_user.reset_token and verify_password(
            request_data.token, candidate_user.reset_token
        ):
            user = candidate_user
            break

    # Verify token exists and hasn't expired
    if not user or not user.reset_token_expires:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # Check if token has expired
    if user.reset_token_expires < datetime.now(UTC):
        # Clear expired token
        user.reset_token = None
        user.reset_token_expires = None
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired",
        )

    # Hash the new password
    new_hashed_password = get_password_hash(request_data.new_password)

    # Update user password and clear reset token (single-use)
    user.hashed_password = new_hashed_password
    user.reset_token = None
    user.reset_token_expires = None

    await db.commit()

    logger.info(f"Password successfully reset for user: {user.email}")

    return MessageResponse(message="Password has been reset successfully")
