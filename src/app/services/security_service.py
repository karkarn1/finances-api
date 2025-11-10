"""Service layer for security synchronization and management.

This service centralizes the logic for syncing securities from Yahoo Finance,
including metadata and historical price data. Now uses repository pattern
for all database operations.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security import Security
from app.models.security_price import SecurityPrice
from app.repositories.security import SecurityRepository
from app.repositories.security_price import SecurityPriceRepository
from app.services.yfinance_service import (
    APIError,
    InvalidSymbolError,
    fetch_historical_prices,
    fetch_security_info,
    parse_yfinance_data,
)

logger = logging.getLogger(__name__)


class SecuritySyncError(Exception):
    """Base exception for security sync errors."""

    pass


class ConcurrentSyncError(SecuritySyncError):
    """Raised when attempting to sync a security that is already syncing."""

    pass


async def get_security_by_symbol(db: AsyncSession, symbol: str) -> Security | None:
    """Get security by symbol from database.

    Args:
        db: Database session
        symbol: Stock symbol (will be uppercased)

    Returns:
        Security if found, None otherwise

    Example:
        >>> security = await get_security_by_symbol(db, "AAPL")
    """
    repo = SecurityRepository(Security, db)
    return await repo.get_by_symbol(symbol)


async def create_or_update_security(
    db: AsyncSession,
    symbol: str,
    security_info: dict[str, str | float | None],
    *,
    set_syncing: bool = False,
) -> Security:
    """Create a new security or update an existing one with yfinance data.

    Args:
        db: Database session
        symbol: Stock symbol (will be uppercased)
        security_info: Dictionary containing security metadata from yfinance
        set_syncing: Whether to set is_syncing=True (default: False)

    Returns:
        Created or updated Security instance

    Note:
        - Commits changes to database
        - Returns refreshed security instance
    """
    symbol = symbol.upper()
    repo = SecurityRepository(Security, db)
    security = await repo.get_by_symbol(symbol)

    if security:
        # Update existing security
        if set_syncing:
            security.is_syncing = True
            await db.commit()
            await db.refresh(security)

        # Update metadata fields
        for field, value in security_info.items():
            setattr(security, field, value)

        logger.info(f"Updated security metadata for {symbol}")
    else:
        # Create new security
        security = Security(
            id=uuid.uuid4(),
            symbol=symbol,
            is_syncing=set_syncing,
            **security_info,
        )
        db.add(security)
        logger.info(f"Created new security record for {symbol}")

    await db.commit()
    await db.refresh(security)
    return security


async def sync_price_history(
    db: AsyncSession,
    security: Security,
) -> int:
    """Fetch and store historical price data for a security.

    Fetches both daily historical data (max period) and recent intraday data (7 days).
    Handles errors gracefully and logs warnings for partial failures.

    Args:
        db: Database session
        security: Security instance to sync prices for

    Returns:
        Total count of price records synced (daily + intraday)

    Raises:
        Does not raise exceptions - logs warnings and continues on partial failures

    Note:
        - Fetches daily data (period="max", interval="1d")
        - Fetches intraday data (period="7d", interval="1m")
        - Uses bulk insert for performance
        - Commits after each data type (daily, intraday)
    """
    total_synced = 0
    symbol = security.symbol
    price_repo = SecurityPriceRepository(SecurityPrice, db)

    # Fetch daily historical data (max period)
    logger.info(f"Fetching daily historical data for {symbol}")
    try:
        daily_df = fetch_historical_prices(symbol, period="max", interval="1d")
        daily_prices = parse_yfinance_data(daily_df, security.id, "1d")

        if daily_prices:
            await price_repo.bulk_create(daily_prices)
            await db.commit()
            total_synced += len(daily_prices)
            logger.info(f"Synced {len(daily_prices)} daily prices for {symbol}")
    except (InvalidSymbolError, APIError) as e:
        logger.warning(f"Could not fetch daily data for {symbol}: {e}")

    # Fetch intraday minute data (last 7 days)
    logger.info(f"Fetching intraday data for {symbol}")
    try:
        intraday_df = fetch_historical_prices(symbol, period="7d", interval="1m")
        intraday_prices = parse_yfinance_data(intraday_df, security.id, "1m")

        if intraday_prices:
            await price_repo.bulk_create(intraday_prices)
            await db.commit()
            total_synced += len(intraday_prices)
            logger.info(f"Synced {len(intraday_prices)} intraday prices for {symbol}")
    except (InvalidSymbolError, APIError) as e:
        logger.warning(f"Could not fetch intraday data for {symbol}: {e}")

    return total_synced


async def sync_security_data(
    db: AsyncSession,
    symbol: str,
    *,
    check_concurrent: bool = False,
) -> tuple[Security, int]:
    """Synchronize security metadata and price data from Yahoo Finance.

    This is the main entry point for syncing securities. It:
    1. Fetches security metadata from yfinance
    2. Creates or updates the Security record
    3. Fetches and stores historical price data (daily + intraday)
    4. Updates sync status and timestamp

    Args:
        db: Database session
        symbol: Stock symbol to sync
        check_concurrent: If True, raises error if sync already in progress

    Returns:
        Tuple of (security, prices_synced_count)

    Raises:
        ConcurrentSyncError: If check_concurrent=True and sync is in progress
        InvalidSymbolError: If symbol not found in Yahoo Finance
        APIError: If Yahoo Finance API fails
        Exception: For unexpected errors

    Example:
        >>> security, count = await sync_security_data(db, "AAPL")
        >>> print(f"Synced {count} prices for {security.symbol}")
    """
    symbol = symbol.upper()
    repo = SecurityRepository(Security, db)

    # Check for concurrent sync if requested
    if check_concurrent:
        security = await repo.get_by_symbol(symbol)
        if security and security.is_syncing:
            raise ConcurrentSyncError(f"Sync already in progress for '{symbol}'")

    try:
        # Fetch security info from yfinance
        logger.info(f"Fetching security info for {symbol}")
        security_info = fetch_security_info(symbol)

        # Create or update security with is_syncing=True
        security = await create_or_update_security(db, symbol, security_info, set_syncing=True)

        # Fetch and store price history
        total_synced = await sync_price_history(db, security)

        # Update sync status using repository
        await repo.update_sync_status(
            symbol,
            is_syncing=False,
            last_synced_at=datetime.now(UTC),
        )
        await db.commit()
        await db.refresh(security)

        logger.info(f"Successfully synced {total_synced} price records for {symbol}")
        return security, total_synced

    except Exception as e:
        # Ensure is_syncing is reset on error
        if security := await repo.get_by_symbol(symbol):
            await repo.update_sync_status(symbol, is_syncing=False)
            await db.commit()

        # Re-raise the exception for caller to handle
        logger.error(f"Error syncing security {symbol}: {e}", exc_info=True)
        raise
