"""Securities endpoints for tracking stocks and financial instruments."""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentActiveUser
from app.db.session import get_db
from app.models.security import Security
from app.models.security_price import SecurityPrice
from app.schemas.security import (
    PriceData,
    SecurityPricesResponse,
    SecurityResponse,
    SyncResponse,
)
from app.services.yfinance_service import (
    APIError,
    InvalidSymbolError,
    fetch_historical_prices,
    fetch_price_range,
    fetch_security_info,
    parse_yfinance_data,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/search", response_model=list[SecurityResponse])
async def search_securities(
    q: Annotated[str, Query(min_length=1, max_length=50)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 20,
) -> list[Security]:
    """
    Search securities by symbol or name (case-insensitive).

    Args:
        q: Search query (searches symbol and name)
        db: Database session
        limit: Maximum number of results to return (default: 20)

    Returns:
        List of matching securities ordered by symbol

    Example:
        GET /api/v1/securities/search?q=apple
        GET /api/v1/securities/search?q=AAPL&limit=10
    """
    search_pattern = f"%{q}%"

    result = await db.execute(
        select(Security)
        .where(
            (Security.symbol.ilike(search_pattern))
            | (Security.name.ilike(search_pattern))
        )
        .order_by(Security.symbol)
        .limit(limit)
    )

    return list(result.scalars().all())


@router.get("/{symbol}", response_model=SecurityResponse)
async def get_security(
    symbol: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Security:
    """
    Get security by symbol.

    Args:
        symbol: Stock symbol (e.g., "AAPL", "MSFT")
        db: Database session

    Returns:
        Security information including sync status

    Raises:
        HTTPException: 404 if security not found
    """
    result = await db.execute(
        select(Security).where(Security.symbol == symbol.upper())
    )
    security = result.scalar_one_or_none()

    if not security:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Security with symbol '{symbol}' not found",
        )

    return security


@router.post("/{symbol}/sync", response_model=SyncResponse)
async def sync_security(
    symbol: str,
    current_user: CurrentActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SyncResponse:
    """
    Sync security data from Yahoo Finance.

    Fetches security metadata and historical price data (daily and intraday if available).
    Creates the security if it doesn't exist, updates if it does.

    Args:
        symbol: Stock symbol to sync (e.g., "AAPL", "MSFT")
        current_user: Authenticated user (required)
        db: Database session

    Returns:
        Sync status with security details and count of prices synced

    Raises:
        HTTPException:
            - 404: Symbol not found in Yahoo Finance
            - 409: Sync already in progress
            - 503: Yahoo Finance API error

    Example:
        POST /api/v1/securities/AAPL/sync
    """
    symbol = symbol.upper()

    # Check if security exists and if sync is already in progress
    result = await db.execute(select(Security).where(Security.symbol == symbol))
    security = result.scalar_one_or_none()

    if security and security.is_syncing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Sync already in progress for '{symbol}'",
        )

    try:
        # Fetch security info from yfinance
        logger.info(f"Fetching security info for {symbol}")
        try:
            security_info = fetch_security_info(symbol)
        except InvalidSymbolError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            ) from e
        except APIError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Yahoo Finance API error: {str(e)}",
            ) from e

        # Create or update security
        if security:
            # Update existing security
            security.is_syncing = True
            await db.commit()
            await db.refresh(security)

            # Update fields
            for field, value in security_info.items():
                setattr(security, field, value)
        else:
            # Create new security
            security = Security(
                id=uuid.uuid4(),
                symbol=symbol,
                is_syncing=True,
                **security_info,
            )
            db.add(security)
            await db.commit()
            await db.refresh(security)

        total_prices_synced = 0

        # Fetch daily historical data (max period)
        logger.info(f"Fetching daily historical data for {symbol}")
        try:
            daily_df = fetch_historical_prices(symbol, period="max", interval="1d")
            daily_prices = parse_yfinance_data(daily_df, security.id, "1d")

            # Bulk insert daily prices
            if daily_prices:
                db.add_all(daily_prices)
                await db.commit()
                total_prices_synced += len(daily_prices)
                logger.info(f"Synced {len(daily_prices)} daily prices for {symbol}")
        except (InvalidSymbolError, APIError) as e:
            logger.warning(f"Could not fetch daily data for {symbol}: {e}")

        # Fetch today's intraday minute data (last 7 days available)
        logger.info(f"Fetching intraday data for {symbol}")
        try:
            intraday_df = fetch_historical_prices(symbol, period="7d", interval="1m")
            intraday_prices = parse_yfinance_data(intraday_df, security.id, "1m")

            # Bulk insert intraday prices
            if intraday_prices:
                db.add_all(intraday_prices)
                await db.commit()
                total_prices_synced += len(intraday_prices)
                logger.info(
                    f"Synced {len(intraday_prices)} intraday prices for {symbol}"
                )
        except (InvalidSymbolError, APIError) as e:
            logger.warning(f"Could not fetch intraday data for {symbol}: {e}")

        # Update sync status
        security.last_synced_at = datetime.now(timezone.utc)
        security.is_syncing = False
        await db.commit()
        await db.refresh(security)

        return SyncResponse(
            security=security,
            prices_synced=total_prices_synced,
            message=f"Successfully synced {total_prices_synced} price records for {symbol}",
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        if security:
            security.is_syncing = False
            await db.commit()
        raise

    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Unexpected error syncing {symbol}: {e}", exc_info=True)
        if security:
            security.is_syncing = False
            await db.commit()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync security: {str(e)}",
        ) from e


@router.get("/{symbol}/prices", response_model=SecurityPricesResponse)
async def get_security_prices(
    symbol: str,
    current_user: CurrentActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    start: datetime | None = None,
    end: datetime | None = None,
    interval: str = Query("1d", pattern="^(1m|1h|1d|1wk)$"),
) -> SecurityPricesResponse:
    """
    Get price data for a security within a time range.

    If no data is found and security exists, returns empty array with suggestion to sync.

    Args:
        symbol: Stock symbol (e.g., "AAPL", "MSFT")
        current_user: Authenticated user (required)
        db: Database session
        start: Start datetime (optional, defaults based on interval)
        end: End datetime (optional, defaults to now)
        interval: Price interval - "1m", "1h", "1d", or "1wk" (default: "1d")

    Returns:
        Security info and price data for the requested time range

    Raises:
        HTTPException: 404 if security not found

    Example:
        GET /api/v1/securities/AAPL/prices?interval=1d
        GET /api/v1/securities/AAPL/prices?start=2024-01-01T00:00:00Z&end=2024-12-31T23:59:59Z&interval=1d
    """
    # Get security
    result = await db.execute(
        select(Security).where(Security.symbol == symbol.upper())
    )
    security = result.scalar_one_or_none()

    if not security:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Security with symbol '{symbol}' not found. Try syncing it first.",
        )

    # Set default time range based on interval if not provided
    now = datetime.now(timezone.utc)
    if end is None:
        end = now

    if start is None:
        if interval == "1m":
            # Last 24 hours for minute data
            start = now - timedelta(days=1)
        else:
            # Last 30 days for other intervals
            start = now - timedelta(days=30)

    # Ensure timezone awareness
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    # Query prices
    query = (
        select(SecurityPrice)
        .where(
            (SecurityPrice.security_id == security.id)
            & (SecurityPrice.interval_type == interval)
            & (SecurityPrice.timestamp >= start)
            & (SecurityPrice.timestamp <= end)
        )
        .order_by(SecurityPrice.timestamp.asc())
    )

    result = await db.execute(query)
    prices = list(result.scalars().all())

    # Convert to PriceData schema
    price_data = [
        PriceData(
            timestamp=price.timestamp,
            open=price.open,
            high=price.high,
            low=price.low,
            close=price.close,
            volume=price.volume,
        )
        for price in prices
    ]

    return SecurityPricesResponse(
        security=security,
        prices=price_data,
        interval_type=interval,
        count=len(price_data),
    )
