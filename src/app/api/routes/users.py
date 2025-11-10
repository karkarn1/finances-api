"""User endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentActiveUser, CurrentSuperUser
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserResponse, UserUpdate

router = APIRouter()


@router.get("/", response_model=list[UserResponse])
async def get_users(
    current_user: CurrentSuperUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 100,
) -> list[User]:
    """
    Get all users (superuser only).

    Args:
        current_user: The authenticated superuser (from dependency)
        db: Database session
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return

    Returns:
        List of users
    """
    user_repo = UserRepository(User, db)
    return await user_repo.get_multi(skip=skip, limit=limit)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: CurrentActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Get user by ID.

    Users can only view their own profile unless they are a superuser.

    Args:
        user_id: The ID of the user to retrieve
        current_user: The authenticated user (from dependency)
        db: Database session

    Returns:
        The requested user

    Raises:
        HTTPException: If user not found or access denied
    """
    # Check if user is requesting their own profile or is a superuser
    if user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this user",
        )

    user_repo = UserRepository(User, db)
    user = await user_repo.get(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: CurrentActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Update user.

    Users can only update their own profile unless they are a superuser.

    Args:
        user_id: The ID of the user to update
        user_update: Updated user data
        current_user: The authenticated user (from dependency)
        db: Database session

    Returns:
        The updated user

    Raises:
        HTTPException: If user not found or access denied
    """
    # Check if user is updating their own profile or is a superuser
    if user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user",
        )

    user_repo = UserRepository(User, db)
    user = await user_repo.get(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Update user fields
    update_data = user_update.model_dump(exclude_unset=True)

    # Check for duplicate email if updating email
    if "email" in update_data and update_data["email"] != user.email:
        if await user_repo.exists_by_email(update_data["email"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

    # Check for duplicate username if updating username
    if "username" in update_data and update_data["username"] != user.username:
        if await user_repo.exists_by_username(update_data["username"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered",
            )

    # Handle password update separately
    if "password" in update_data:
        user.hashed_password = get_password_hash(update_data.pop("password"))

    # Update other fields
    for field, value in update_data.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)

    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: CurrentSuperUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """
    Delete user (superuser only).

    Args:
        user_id: The ID of the user to delete
        current_user: The authenticated superuser (from dependency)
        db: Database session

    Raises:
        HTTPException: If user not found
    """
    user_repo = UserRepository(User, db)
    user = await user_repo.get(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await db.delete(user)
    await db.commit()
