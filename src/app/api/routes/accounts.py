"""Account endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentActiveUser, verify_account_access
from app.db.session import get_db
from app.models.account import Account
from app.models.account_value import AccountValue
from app.schemas.account import (
    AccountCreate,
    AccountResponse,
    AccountUpdate,
    AccountWithBalance,
)

router = APIRouter()


@router.get("/", response_model=list[AccountResponse])
async def get_accounts(
    current_user: CurrentActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 100,
) -> list[Account]:
    """
    Get all accounts for the current user.

    Args:
        current_user: The authenticated user (from dependency)
        db: Database session
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return

    Returns:
        List of accounts
    """
    result = await db.execute(
        select(Account).where(Account.user_id == current_user.id).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


@router.post("/", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    account: AccountCreate,
    current_user: CurrentActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Account:
    """
    Create a new account.

    Args:
        account: Account data
        current_user: The authenticated user (from dependency)
        db: Database session

    Returns:
        The created account
    """
    db_account = Account(
        user_id=current_user.id,
        **account.model_dump(),
    )
    db.add(db_account)
    await db.commit()
    await db.refresh(db_account)

    return db_account


@router.get("/{account_id}", response_model=AccountWithBalance)
async def get_account(
    account: Annotated[Account, Depends(verify_account_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """
    Get a specific account with computed current balance.

    Args:
        account: The verified account (from dependency)
        db: Database session

    Returns:
        The requested account with current balance

    Raises:
        HTTPException: If account not found or access denied
    """
    # Get most recent account value
    value_result = await db.execute(
        select(AccountValue)
        .where(AccountValue.account_id == account.id)
        .order_by(AccountValue.timestamp.desc())
        .limit(1)
    )
    latest_value = value_result.scalar_one_or_none()

    # Build response with current balance
    account_dict = {
        "id": account.id,
        "user_id": account.user_id,
        "financial_institution_id": account.financial_institution_id,
        "name": account.name,
        "account_type": account.account_type,
        "is_investment_account": account.is_investment_account,
        "interest_rate": account.interest_rate,
        "created_at": account.created_at,
        "updated_at": account.updated_at,
        "current_balance": latest_value.balance if latest_value else None,
        "current_cash_balance": latest_value.cash_balance if latest_value else None,
    }

    return account_dict


@router.put("/{account_id}", response_model=AccountResponse)
async def update_account(
    account: Annotated[Account, Depends(verify_account_access)],
    account_update: AccountUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Account:
    """
    Update an account.

    Args:
        account: The verified account (from dependency)
        account_update: Updated account data
        db: Database session

    Returns:
        The updated account

    Raises:
        HTTPException: If account not found or access denied
    """
    # Update fields
    update_data = account_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(account, field, value)

    await db.commit()
    await db.refresh(account)

    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account: Annotated[Account, Depends(verify_account_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """
    Delete an account.

    Args:
        account: The verified account (from dependency)
        db: Database session

    Raises:
        HTTPException: If account not found or access denied
    """
    await db.delete(account)
    await db.commit()
