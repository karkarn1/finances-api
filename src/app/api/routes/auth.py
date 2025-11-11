"""Authentication routes."""

import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import CurrentActiveUser
from app.core.rate_limit import limiter
from app.core.security import get_password_hash, verify_password
from app.db.session import get_db, transactional
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import (
    ForgotPasswordRequest,
    MessageResponse,
    ResetPasswordRequest,
    Token,
    TokenPair,
    UserRegister,
)
from app.schemas.user import UserResponse
from app.services import user_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.AUTH_RATE_LIMIT)
async def register(
    request: Request,
    user_data: UserRegister,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Register a new user.

    Uses transactional context manager for atomic user creation with automatic
    rollback on validation errors.

    Args:
        user_data: User registration data
        db: Database session

    Returns:
        The created user

    Raises:
        HTTPException: 400 if username or email already exists
    """
    # Check if username already exists
    if await user_service.username_exists(db, user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Check if email already exists
    if await user_service.email_exists(db, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user within transaction
    async with transactional(db):
        hashed_password = get_password_hash(user_data.password)
        new_user = User(
            email=user_data.email,
            username=user_data.username,
            hashed_password=hashed_password,
            is_active=True,
            is_superuser=False,
        )
        db.add(new_user)

    # Refresh outside transaction to ensure we have committed data
    await db.refresh(new_user)
    return new_user


@router.post("/login", response_model=Token)
@limiter.limit(settings.AUTH_RATE_LIMIT)
async def login(
    request: Request,
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
    tokens = await user_service.create_user_tokens(
        db, form_data.username, form_data.password, include_refresh=False
    )
    return Token(access_token=tokens["access_token"])


@router.post("/login/tokens", response_model=TokenPair)
@limiter.limit(settings.AUTH_RATE_LIMIT)
async def login_with_refresh(
    request: Request,
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
    tokens = await user_service.create_user_tokens(
        db, form_data.username, form_data.password, include_refresh=True
    )
    return TokenPair(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
    )


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
@limiter.limit(settings.AUTH_RATE_LIMIT)
async def forgot_password(
    request: Request,
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
    user = await user_service.get_user_by_email(db, request_data.email)

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
            logger.info(f"Password reset token for {user.email}: {plaintext_token}")
            logger.info(f"Token expires at: {token_expires.isoformat()}")

    # Always return success (don't reveal if email exists)
    return MessageResponse(message="If the email exists, a password reset link has been sent.")


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
    # Get all users with non-null reset tokens using repository
    user_repo = UserRepository(User, db)
    users_with_tokens = await user_repo.get_users_with_reset_tokens()

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
