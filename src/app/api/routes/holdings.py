"""Holding endpoints."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import verify_account_access
from app.db.session import get_db
from app.models.account import Account
from app.models.holding import Holding
from app.models.security import Security
from app.repositories.holding import HoldingRepository
from app.repositories.security import SecurityRepository
from app.schemas.holding import HoldingCreate, HoldingResponse, HoldingUpdate
from app.services import security_service
from app.services.yfinance_service import APIError, InvalidSymbolError

router = APIRouter()
logger = logging.getLogger(__name__)


async def get_or_create_security(security_id_or_symbol: UUID | str, db: AsyncSession) -> Security:
    """
    Get security by ID or symbol, creating it from Yahoo Finance if needed.

    This function handles both UUID lookups (for existing securities) and symbol
    lookups (for securities not yet in the database). If a symbol is provided and
    not found in the database, it automatically fetches and syncs the security
    from Yahoo Finance via the security service.

    Args:
        security_id_or_symbol: UUID of existing security or symbol string
        db: Database session

    Returns:
        Security instance (either existing or newly created)

    Raises:
        HTTPException:
            - 404: If UUID not found in DB or symbol not found in Yahoo Finance
            - 503: If Yahoo Finance API error occurs
    """
    repo = SecurityRepository(Security, db)

    # Try to parse as UUID first
    try:
        security_uuid = UUID(str(security_id_or_symbol))
        # Look up by UUID
        security = await repo.get(security_uuid)

        if security:
            return security

        # UUID not found - this is an error since UUIDs should always exist
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Security with ID '{security_uuid}' not found",
        )

    except (ValueError, TypeError):
        # Not a valid UUID - treat as symbol
        symbol = str(security_id_or_symbol).upper()

        # Use service layer to get or create security with price sync
        try:
            security = await security_service.get_or_create_security(
                db,
                symbol,
                sync_prices=True,
                sync_daily=True,
                sync_intraday=True,
            )
            return security
        except InvalidSymbolError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Security symbol '{symbol}' not found in Yahoo Finance",
            ) from e
        except APIError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Yahoo Finance API error: {str(e)}",
            ) from e


@router.get("/", response_model=list[HoldingResponse])
async def get_holdings(
    account: Annotated[Account, Depends(verify_account_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 100,
) -> list[Holding]:
    """
    Get all holdings for an account.

    Args:
        account: The verified account (from dependency)
        db: Database session
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return

    Returns:
        List of holdings

    Raises:
        HTTPException: If account not found or access denied
    """
    repo = HoldingRepository(Holding, db)
    return await repo.get_holdings_with_security(
        account_id=account.id,
        skip=skip,
        limit=limit,
    )


@router.post("/", response_model=HoldingResponse, status_code=status.HTTP_201_CREATED)
async def create_holding(
    account: Annotated[Account, Depends(verify_account_access)],
    holding: HoldingCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Holding:
    """
    Add a holding to an account.

    Automatically fetches and syncs the security from Yahoo Finance if it doesn't
    exist in the database. Accepts either a UUID (for existing securities) or a
    symbol string (for new securities to be auto-synced).

    Args:
        account: The verified account (from dependency)
        holding: Holding data (validated Pydantic model, security_id can be UUID or symbol string)
        db: Database session

    Returns:
        The created holding with security relationship loaded

    Raises:
        HTTPException:
            - 400: Holdings can only be added to investment accounts
            - 403: Not authorized to access this account
            - 404: Account not found, or security symbol not found in Yahoo Finance
            - 503: Yahoo Finance API error

    Example:
        POST /api/v1/accounts/{account_id}/holdings
        {
            "security_id": "AAPL",  # Symbol - will auto-sync from Yahoo Finance
            "shares": 10.5,
            "average_price_per_share": 150.25
        }
    """
    # Validate it's an investment account
    if not account.is_investment_account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Holdings can only be added to investment accounts",
        )

    # Get or create security (auto-syncs from Yahoo Finance if needed)
    security = await get_or_create_security(holding.security_id, db)

    # Create holding with the actual security UUID
    repo = HoldingRepository(Holding, db)

    # Extract data from Pydantic model and add account_id and actual security_id
    holding_data = holding.model_dump()
    holding_data["account_id"] = account.id
    holding_data["security_id"] = security.id  # Use the actual UUID from DB

    db_holding = await repo.create(obj_in=holding_data)
    await db.commit()
    await db.refresh(db_holding)

    # Load security relationship for response
    await db.refresh(db_holding, attribute_names=["security"])

    return db_holding


@router.get("/{holding_id}", response_model=HoldingResponse)
async def get_holding(
    account: Annotated[Account, Depends(verify_account_access)],
    holding_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Holding:
    """
    Get a specific holding.

    Args:
        account: The verified account (from dependency)
        holding_id: The holding ID
        db: Database session

    Returns:
        The requested holding

    Raises:
        HTTPException: If account/holding not found or access denied
    """
    repo = HoldingRepository(Holding, db)
    holding = await repo.get_by_id_and_account(
        holding_id=holding_id,
        account_id=account.id,
    )

    if not holding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Holding not found",
        )

    return holding


@router.put("/{holding_id}", response_model=HoldingResponse)
async def update_holding(
    account: Annotated[Account, Depends(verify_account_access)],
    holding_id: UUID,
    holding_update: HoldingUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Holding:
    """
    Update a holding.

    Args:
        account: The verified account (from dependency)
        holding_id: The holding ID
        holding_update: Updated holding data (validated Pydantic model)
        db: Database session

    Returns:
        The updated holding

    Raises:
        HTTPException: If account/holding not found or access denied
    """
    repo = HoldingRepository(Holding, db)
    holding = await repo.get_by_id_and_account(
        holding_id=holding_id,
        account_id=account.id,
    )

    if not holding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Holding not found",
        )

    # Extract Pydantic data and handle security_id resolution
    update_data = holding_update.model_dump(exclude_unset=True)
    if "security_id" in update_data:
        security = await get_or_create_security(update_data["security_id"], db)
        # Use the actual security UUID
        update_data["security_id"] = security.id

    # Update with type-safe Pydantic validation
    updated_holding = await repo.update(
        db_obj=holding,
        obj_in=update_data,
    )

    await db.commit()
    await db.refresh(updated_holding)

    # Load security relationship for response
    await db.refresh(updated_holding, attribute_names=["security"])

    return updated_holding


@router.delete("/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holding(
    account: Annotated[Account, Depends(verify_account_access)],
    holding_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """
    Delete a holding.

    Args:
        account: The verified account (from dependency)
        holding_id: The holding ID
        db: Database session

    Raises:
        HTTPException: If account/holding not found or access denied
    """
    repo = HoldingRepository(Holding, db)
    holding = await repo.get_by_id_and_account(
        holding_id=holding_id,
        account_id=account.id,
    )

    if not holding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Holding not found",
        )

    await repo.delete(id=holding_id)
    await db.commit()
