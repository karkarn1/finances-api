"""Holding endpoints."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentActiveUser, verify_account_access
from app.db.session import get_db
from app.models.account import Account
from app.models.holding import Holding
from app.models.security import Security
from app.schemas.holding import HoldingCreate, HoldingResponse, HoldingUpdate
from app.services.yfinance_service import (
    APIError,
    InvalidSymbolError,
    fetch_historical_prices,
    fetch_security_info,
    parse_yfinance_data,
)

router = APIRouter()
logger = logging.getLogger(__name__)


async def get_or_create_security(security_id_or_symbol: UUID | str, db: AsyncSession) -> Security:
    """
    Get security by ID or symbol, creating it from Yahoo Finance if needed.

    This function handles both UUID lookups (for existing securities) and symbol
    lookups (for securities not yet in the database). If a symbol is provided and
    not found in the database, it automatically fetches and syncs the security
    from Yahoo Finance.

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
    # Try to parse as UUID first
    try:
        security_uuid = UUID(str(security_id_or_symbol))
        # Look up by UUID
        result = await db.execute(select(Security).where(Security.id == security_uuid))
        security = result.scalar_one_or_none()

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

        # Try to find by symbol in database
        result = await db.execute(select(Security).where(Security.symbol == symbol))
        security = result.scalar_one_or_none()

        if security:
            return security

        # Security doesn't exist - fetch from Yahoo Finance and create it
        logger.info(f"Security '{symbol}' not found in database, fetching from Yahoo Finance")

        try:
            # Fetch security info from yfinance
            security_info = fetch_security_info(symbol)
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

        # Create new security with is_syncing=True
        security = Security(
            id=uuid.uuid4(),
            symbol=symbol,
            is_syncing=True,
            **security_info,
        )
        db.add(security)
        await db.commit()
        await db.refresh(security)

        # Sync historical prices in background
        try:
            # Fetch daily historical data (max period)
            logger.info(f"Fetching daily historical data for {symbol}")
            try:
                daily_df = fetch_historical_prices(symbol, period="max", interval="1d")
                daily_prices = parse_yfinance_data(daily_df, security.id, "1d")

                # Bulk insert daily prices
                if daily_prices:
                    db.add_all(daily_prices)
                    await db.commit()
                    logger.info(f"Synced {len(daily_prices)} daily prices for {symbol}")
            except (InvalidSymbolError, APIError) as e:
                logger.warning(f"Could not fetch daily data for {symbol}: {e}")

            # Fetch intraday minute data (last 7 days)
            logger.info(f"Fetching intraday data for {symbol}")
            try:
                intraday_df = fetch_historical_prices(symbol, period="7d", interval="1m")
                intraday_prices = parse_yfinance_data(intraday_df, security.id, "1m")

                # Bulk insert intraday prices
                if intraday_prices:
                    db.add_all(intraday_prices)
                    await db.commit()
                    logger.info(f"Synced {len(intraday_prices)} intraday prices for {symbol}")
            except (InvalidSymbolError, APIError) as e:
                logger.warning(f"Could not fetch intraday data for {symbol}: {e}")

            # Update sync status
            security.last_synced_at = datetime.now(UTC)
            security.is_syncing = False
            await db.commit()
            await db.refresh(security)

            logger.info(f"Successfully created and synced security '{symbol}'")

        except Exception as e:
            # Handle unexpected errors - mark sync as failed but still return the security
            logger.error(f"Unexpected error syncing prices for {symbol}: {e}", exc_info=True)
            security.is_syncing = False
            await db.commit()
            await db.refresh(security)

        return security


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
    result = await db.execute(
        select(Holding)
        .options(selectinload(Holding.security))
        .where(Holding.account_id == account.id)
        .order_by(Holding.timestamp.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


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
        holding: Holding data (security_id can be UUID or symbol string)
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
    db_holding = Holding(
        account_id=account.id,
        security_id=security.id,  # Use the actual UUID from DB
        shares=holding.shares,
        average_price_per_share=holding.average_price_per_share,
        timestamp=holding.timestamp,
    )
    db.add(db_holding)
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
    result = await db.execute(
        select(Holding)
        .options(selectinload(Holding.security))
        .where(Holding.id == holding_id, Holding.account_id == account.id)
    )
    holding = result.scalar_one_or_none()

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
        holding_update: Updated holding data
        db: Database session

    Returns:
        The updated holding

    Raises:
        HTTPException: If account/holding not found or access denied
    """
    result = await db.execute(
        select(Holding).where(Holding.id == holding_id, Holding.account_id == account.id)
    )
    holding = result.scalar_one_or_none()

    if not holding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Holding not found",
        )

    # If updating security_id, get or create security (auto-syncs if needed)
    update_data = holding_update.model_dump(exclude_unset=True)
    if "security_id" in update_data:
        security = await get_or_create_security(update_data["security_id"], db)
        # Use the actual security UUID
        update_data["security_id"] = security.id

    # Update fields
    for field, value in update_data.items():
        setattr(holding, field, value)

    await db.commit()
    await db.refresh(holding)

    # Load security relationship for response
    await db.refresh(holding, attribute_names=["security"])

    return holding


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
    result = await db.execute(
        select(Holding).where(Holding.id == holding_id, Holding.account_id == account.id)
    )
    holding = result.scalar_one_or_none()

    if not holding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Holding not found",
        )

    await db.delete(holding)
    await db.commit()
