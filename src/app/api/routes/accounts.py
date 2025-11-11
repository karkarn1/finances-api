"""Account endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentActiveUser, verify_account_access
from app.db.session import get_db
from app.models.account import Account
from app.models.account_value import AccountValue
from app.repositories.account import AccountRepository
from app.repositories.account_value import AccountValueRepository
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
    repo = AccountRepository(Account, db)
    return await repo.get_by_user_id(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )


@router.post("/", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    account: AccountCreate,
    current_user: CurrentActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Account:
    """
    Create a new account.

    Args:
        account: Account data (validated Pydantic model)
        current_user: The authenticated user (from dependency)
        db: Database session

    Returns:
        The created account
    """
    repo = AccountRepository(Account, db)

    # Extract data from Pydantic model and add user_id
    account_data = account.model_dump()
    account_data["user_id"] = current_user.id

    # Create using Pydantic model (already validated by FastAPI)
    db_account = await repo.create(obj_in=account_data)
    await db.commit()
    await db.refresh(db_account)

    return db_account


@router.get("/{account_id}", response_model=AccountWithBalance)
async def get_account(
    account: Annotated[Account, Depends(verify_account_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
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
    value_repo = AccountValueRepository(AccountValue, db)
    latest_value = await value_repo.get_latest_by_account(account.id)

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
        account_update: Updated account data (validated Pydantic model)
        db: Database session

    Returns:
        The updated account

    Raises:
        HTTPException: If account not found or access denied
    """
    # Update with type-safe Pydantic validation
    repo = AccountRepository(Account, db)
    updated_account = await repo.update(
        db_obj=account,
        obj_in=account_update,  # Pass Pydantic model directly
    )

    await db.commit()
    await db.refresh(updated_account)

    return updated_account


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
    repo = AccountRepository(Account, db)
    await repo.delete(id=account.id)
    await db.commit()
