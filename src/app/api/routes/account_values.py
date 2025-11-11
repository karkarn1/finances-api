"""Account value endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import verify_account_access
from app.db.session import get_db
from app.models.account import Account
from app.models.account_value import AccountValue
from app.repositories.account_value import AccountValueRepository
from app.schemas.account_value import (
    AccountValueCreate,
    AccountValueResponse,
    AccountValueUpdate,
)

router = APIRouter()


@router.get("/", response_model=list[AccountValueResponse])
async def get_account_values(
    account: Annotated[Account, Depends(verify_account_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 100,
) -> list[AccountValue]:
    """
    Get balance history for an account.

    Args:
        account: The verified account (from dependency)
        db: Database session
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return

    Returns:
        List of account value entries

    Raises:
        HTTPException: If account not found or access denied
    """
    repo = AccountValueRepository(AccountValue, db)
    return await repo.get_by_account_id(
        account_id=account.id,
        skip=skip,
        limit=limit,
    )


@router.post("/", response_model=AccountValueResponse, status_code=status.HTTP_201_CREATED)
async def create_account_value(
    account: Annotated[Account, Depends(verify_account_access)],
    account_value: AccountValueCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccountValue:
    """
    Add a balance entry for an account.

    Args:
        account: The verified account (from dependency)
        account_value: Account value data (validated Pydantic model)
        db: Database session

    Returns:
        The created account value entry

    Raises:
        HTTPException: If account not found, access denied, or validation fails
    """
    # Validate cash_balance for investment accounts
    if account.is_investment_account and account_value.cash_balance is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cash balance is required for investment accounts",
        )

    repo = AccountValueRepository(AccountValue, db)

    # Extract data from Pydantic model and add account_id
    value_data = account_value.model_dump()
    value_data["account_id"] = account.id

    # Create using Pydantic model (already validated by FastAPI)
    db_account_value = await repo.create(obj_in=value_data)
    await db.commit()
    await db.refresh(db_account_value)

    return db_account_value


@router.put("/{value_id}", response_model=AccountValueResponse)
async def update_account_value(
    account: Annotated[Account, Depends(verify_account_access)],
    value_id: UUID,
    account_value_update: AccountValueUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccountValue:
    """
    Update a balance entry.

    Args:
        account: The verified account (from dependency)
        value_id: The account value ID
        account_value_update: Updated account value data (validated Pydantic model)
        db: Database session

    Returns:
        The updated account value entry

    Raises:
        HTTPException: If account/value not found or access denied
    """
    repo = AccountValueRepository(AccountValue, db)
    account_value = await repo.get_by_id_and_account(
        value_id=value_id,
        account_id=account.id,
    )

    if not account_value:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account value entry not found",
        )

    # Update with type-safe Pydantic validation
    updated_value = await repo.update(
        db_obj=account_value,
        obj_in=account_value_update,  # Pass Pydantic model directly
    )

    await db.commit()
    await db.refresh(updated_value)

    return updated_value


@router.delete("/{value_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account_value(
    account: Annotated[Account, Depends(verify_account_access)],
    value_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """
    Delete a balance entry.

    Args:
        account: The verified account (from dependency)
        value_id: The account value ID
        db: Database session

    Raises:
        HTTPException: If account/value not found or access denied
    """
    repo = AccountValueRepository(AccountValue, db)
    account_value = await repo.get_by_id_and_account(
        value_id=value_id,
        account_id=account.id,
    )

    if not account_value:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account value entry not found",
        )

    await repo.delete(id=value_id)
    await db.commit()
