"""Securities endpoints for tracking stocks and financial instruments."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentActiveUser
from app.db.session import get_db
from app.models.security import Security
from app.models.security_price import SecurityPrice
from app.repositories.security import SecurityRepository
from app.repositories.security_price import SecurityPriceRepository
from app.schemas.security import (
    PriceData,
    SecurityPricesResponse,
    SecurityResponse,
    SyncResponse,
)
from app.services.yfinance_service import (
    APIError,
    InvalidSymbolError,
    fetch_security_info,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/search", response_model=list[SecurityResponse])
async def search_securities(
    q: Annotated[str, Query(min_length=1, max_length=50)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 20,
) -> list[SecurityResponse]:
    """
    Search securities by symbol or name (case-insensitive).

    Searches local database first, then queries Yahoo Finance for exact symbol matches
    if fewer results than limit are found. Results from yfinance are marked with
    in_database=False and can be synced using the /securities/{symbol}/sync endpoint.

    Args:
        q: Search query (searches symbol and name)
        db: Database session
        limit: Maximum number of results to return (default: 20)

    Returns:
        List of matching securities ordered by symbol, with in_database flag

    Example:
        GET /api/v1/securities/search?q=apple
        GET /api/v1/securities/search?q=AAPL&limit=10
    """
    # Search local database first using repository
    security_repo = SecurityRepository(Security, db)
    db_securities = await security_repo.search(q, limit=limit)

    # Convert DB results to response models
    response_securities: list[SecurityResponse] = [
        SecurityResponse(
            id=security.id,
            symbol=security.symbol,
            name=security.name,
            exchange=security.exchange,
            currency=security.currency,
            security_type=security.security_type,
            sector=security.sector,
            industry=security.industry,
            market_cap=security.market_cap,
            last_synced_at=security.last_synced_at,
            is_syncing=security.is_syncing,
            created_at=security.created_at,
            updated_at=security.updated_at,
            in_database=True,
        )
        for security in db_securities
    ]

    # If we have fewer results than the limit, try yfinance for exact symbol match
    if len(response_securities) < limit and len(q.strip()) > 0:
        # Check if the query looks like a symbol (short, uppercase-friendly)
        # and we don't already have an exact match in DB
        query_upper = q.strip().upper()
        has_exact_match = any(sec.symbol.upper() == query_upper for sec in db_securities)

        if not has_exact_match and len(query_upper) <= 10:
            # Try to fetch from yfinance
            try:
                logger.info(f"Attempting to fetch symbol '{query_upper}' from yfinance")
                security_info = fetch_security_info(query_upper)

                # Create a temporary SecurityResponse from yfinance data
                # Use a temporary UUID since it's not in DB yet
                now = datetime.now(UTC)
                yfinance_security = SecurityResponse(
                    id=uuid.uuid4(),  # Temporary ID
                    symbol=query_upper,
                    name=security_info.get("name", query_upper),
                    exchange=security_info.get("exchange"),
                    currency=security_info.get("currency"),
                    security_type=security_info.get("security_type"),
                    sector=security_info.get("sector"),
                    industry=security_info.get("industry"),
                    market_cap=security_info.get("market_cap"),
                    last_synced_at=None,
                    is_syncing=False,
                    created_at=now,
                    updated_at=now,
                    in_database=False,  # Mark as not in DB
                )

                # Add to results (prepend for visibility since it's likely what user wants)
                response_securities.insert(0, yfinance_security)
                logger.info(f"Successfully fetched '{query_upper}' from yfinance")

            except InvalidSymbolError:
                # Symbol not found in yfinance, which is expected for invalid symbols
                logger.debug(f"Symbol '{query_upper}' not found in yfinance")
            except APIError as e:
                # yfinance API error - log but don't fail the request
                logger.warning(f"yfinance API error for '{query_upper}': {e}")
            except Exception as e:
                # Unexpected error - log but don't fail the request
                logger.error(f"Unexpected error fetching '{query_upper}' from yfinance: {e}")

    return response_securities


@router.get("/{symbol}", response_model=SecurityResponse)
async def get_security(
    symbol: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Security:
    """
    Get security by symbol.

    If the security doesn't exist in the database, automatically fetches it from
    Yahoo Finance, creates the database record, and syncs historical price data.

    Args:
        symbol: Stock symbol (e.g., "AAPL", "MSFT")
        db: Database session

    Returns:
        Security information including sync status

    Raises:
        HTTPException:
            - 404: Symbol not found in Yahoo Finance
            - 503: Yahoo Finance API error

    Example:
        GET /api/v1/securities/AAPL
    """
    from app.services.security_service import (
        get_security_by_symbol,
        sync_security_data,
    )

    symbol = symbol.upper()

    # Try to get security from database
    security = await get_security_by_symbol(db, symbol)

    # If security exists, return it
    if security:
        return security

    # Security doesn't exist - fetch from Yahoo Finance and create it
    logger.info(f"Security '{symbol}' not found in database, fetching from Yahoo Finance")

    try:
        # Sync security data from yfinance (create + fetch prices)
        security, _ = await sync_security_data(db, symbol)
        return security

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
    except Exception as e:
        # Handle unexpected errors - log and return 500
        logger.error(f"Unexpected error fetching security {symbol}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch security: {str(e)}",
        ) from e


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
    from app.services.security_service import (
        ConcurrentSyncError,
        sync_security_data,
    )

    symbol = symbol.upper()

    try:
        # Sync security with concurrent check enabled
        security, total_prices_synced = await sync_security_data(db, symbol, check_concurrent=True)

        return SyncResponse(
            security=security,
            prices_synced=total_prices_synced,
            message=f"Successfully synced {total_prices_synced} price records for {symbol}",
        )

    except ConcurrentSyncError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
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
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Unexpected error syncing {symbol}: {e}", exc_info=True)
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

    Returns available price data even if sparse or outside exact range.
    Handles weekends, holidays, and non-trading days gracefully.

    Args:
        symbol: Stock symbol (e.g., "AAPL", "MSFT")
        current_user: Authenticated user (required)
        db: Database session
        start: Start datetime (optional, defaults based on interval)
        end: End datetime (optional, defaults to now)
        interval: Price interval - "1m", "1h", "1d", or "1wk" (default: "1d")

    Returns:
        Security info and price data for the requested time range,
        with metadata about data completeness and actual date range

    Raises:
        HTTPException: 404 if security not found

    Example:
        GET /api/v1/securities/AAPL/prices?interval=1d
        GET /api/v1/securities/AAPL/prices?start=2024-01-01T00:00:00Z
            &end=2024-12-31T23:59:59Z&interval=1d
    """
    # Get security using repository
    security_repo = SecurityRepository(Security, db)
    security = await security_repo.get_by_symbol(symbol.upper())

    if not security:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Security with symbol '{symbol}' not found. Try syncing it first.",
        )

    # Set default time range based on interval if not provided
    now = datetime.now(UTC)

    # Handle end datetime
    if end is None:
        requested_end = now
    elif end.tzinfo is None:
        requested_end = end.replace(tzinfo=UTC)
    else:
        requested_end = end

    # Handle start datetime
    if start is None:
        if interval == "1m":
            # Last 24 hours for minute data
            requested_start = now - timedelta(days=1)
        else:
            # Last 30 days for other intervals
            requested_start = now - timedelta(days=30)
    elif start.tzinfo is None:
        requested_start = start.replace(tzinfo=UTC)
    else:
        requested_start = start

    # Expand search range to find nearby data if exact range has gaps
    # This handles weekends, holidays, and sparse trading data
    search_buffer_days = 7  # Look 7 days before/after for data
    expanded_start = requested_start - timedelta(days=search_buffer_days)
    expanded_end = requested_end + timedelta(days=search_buffer_days)

    # Query prices with expanded range using repository
    price_repo = SecurityPriceRepository(SecurityPrice, db)
    all_prices = await price_repo.get_by_security_and_date_range(
        security.id,
        expanded_start,
        expanded_end,
        interval=interval,
    )

    # Filter to get prices closest to requested range
    # Prioritize data within requested range, then nearby data
    # Ensure all timestamps are timezone-aware for comparison
    prices_in_range = [
        p
        for p in all_prices
        if requested_start
        <= (p.timestamp.replace(tzinfo=UTC) if p.timestamp.tzinfo is None else p.timestamp)
        <= requested_end
    ]

    # If no data in exact range, use all available data from expanded search
    prices_to_return = prices_in_range if prices_in_range else all_prices

    # Calculate actual date range and data completeness
    actual_start = None
    actual_end = None
    data_completeness = "empty"

    if prices_to_return:
        actual_start = prices_to_return[0].timestamp
        actual_end = prices_to_return[-1].timestamp

        # Determine data completeness
        if not prices_in_range:
            # Data exists but outside requested range
            data_completeness = "partial"
        else:
            # Calculate expected vs actual data points based on interval
            time_span_days = (requested_end - requested_start).days

            if interval == "1d":
                # Daily data: expect ~5 trading days per week
                expected_points = max(1, int(time_span_days * 5 / 7))
            elif interval == "1wk":
                # Weekly data: expect ~1 point per week
                expected_points = max(1, time_span_days // 7)
            elif interval == "1h":
                # Hourly data: expect ~6.5 trading hours per day
                expected_points = max(1, int(time_span_days * 6.5))
            else:  # "1m"
                # Minute data: expect ~390 minutes per trading day
                expected_points = max(1, int(time_span_days * 390))

            actual_points = len(prices_in_range)
            completeness_ratio = actual_points / expected_points if expected_points > 0 else 0

            if completeness_ratio >= 0.8:
                data_completeness = "complete"
            elif completeness_ratio >= 0.4:
                data_completeness = "partial"
            else:
                data_completeness = "sparse"

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
        for price in prices_to_return
    ]

    return SecurityPricesResponse(
        security=security,
        prices=price_data,
        interval_type=interval,
        count=len(price_data),
        requested_start=requested_start,
        requested_end=requested_end,
        actual_start=actual_start,
        actual_end=actual_end,
        data_completeness=data_completeness,
    )
