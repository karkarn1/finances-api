"""Service layer for security synchronization and management.

This service centralizes the logic for syncing securities from Yahoo Finance,
including metadata and historical price data. Now uses repository pattern
for all database operations and transactional context managers for
explicit transaction control.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.session import read_only_transaction, transactional, with_savepoint
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


# Legacy exception aliases for backward compatibility
# These will be removed in a future version
class SecuritySyncError(ConflictError):
    """Deprecated: Use ConflictError instead."""

    pass


class ConcurrentSyncError(ConflictError):
    """Deprecated: Use ConflictError instead."""

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

    Uses transactional context manager to ensure atomic create/update operations.

    Args:
        db: Database session
        symbol: Stock symbol (will be uppercased)
        security_info: Dictionary containing security metadata from yfinance
        set_syncing: Whether to set is_syncing=True (default: False)

    Returns:
        Created or updated Security instance (refreshed from database)

    Raises:
        Exception: Any database or validation errors (with automatic rollback)

    Example:
        ```python
        info = {"name": "Apple Inc.", "currency": "USD", "exchange": "NASDAQ"}
        security = await create_or_update_security(
            db, "AAPL", info, set_syncing=True
        )
        ```

    Note:
        - Automatically commits changes on success
        - Automatically rolls back on any exception
        - Returns refreshed instance reflecting database state
    """
    symbol = symbol.upper()

    async with transactional(db):
        repo = SecurityRepository(Security, db)
        security = await repo.get_by_symbol(symbol)

        if security:
            # Update existing security
            if set_syncing:
                security.is_syncing = True
                # Flush to persist changes before update
                await db.flush()

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

    # Refresh outside transaction to ensure we have committed data
    await db.refresh(security)
    return security


async def sync_price_history(
    db: AsyncSession,
    security: Security,
) -> int:
    """Fetch and store historical price data for a security.

    Fetches both daily historical data (max period) and recent intraday data (7 days).
    Handles errors gracefully using savepoints to allow partial success.
    Each price type (daily/intraday) commits independently.

    Args:
        db: Database session
        security: Security instance to sync prices for

    Returns:
        Total count of price records synced (daily + intraday)

    Raises:
        Does not raise exceptions - logs warnings and continues on partial failures

    Example:
        ```python
        security = await get_security_by_symbol(db, "AAPL")
        count = await sync_price_history(db, security)
        print(f"Synced {count} price records")
        ```

    Note:
        - Fetches daily data (period="max", interval="1d")
        - Fetches intraday data (period="7d", interval="1m")
        - Uses bulk insert for performance
        - Each price type commits independently
        - Partial failures don't prevent overall sync completion
    """
    total_synced = 0
    symbol = security.symbol
    price_repo = SecurityPriceRepository(SecurityPrice, db)

    # Fetch daily historical data (max period)
    logger.info(f"Fetching daily historical data for {symbol}")
    try:
        async with transactional(db):
            daily_df = fetch_historical_prices(symbol, period="max", interval="1d")
            daily_prices = parse_yfinance_data(daily_df, security.id, "1d")

            if daily_prices:
                await price_repo.bulk_create(daily_prices)
                total_synced += len(daily_prices)
                logger.info(f"Synced {len(daily_prices)} daily prices for {symbol}")
    except (InvalidSymbolError, APIError) as e:
        logger.warning(f"Could not fetch daily data for {symbol}: {e}")

    # Fetch intraday minute data (last 7 days)
    logger.info(f"Fetching intraday data for {symbol}")
    try:
        async with transactional(db):
            intraday_df = fetch_historical_prices(symbol, period="7d", interval="1m")
            intraday_prices = parse_yfinance_data(intraday_df, security.id, "1m")

            if intraday_prices:
                await price_repo.bulk_create(intraday_prices)
                total_synced += len(intraday_prices)
                logger.info(f"Synced {len(intraday_prices)} intraday prices for {symbol}")
    except (InvalidSymbolError, APIError) as e:
        logger.warning(f"Could not fetch intraday data for {symbol}: {e}")

    return total_synced


async def get_or_create_security(
    db: AsyncSession,
    symbol: str,
    *,
    sync_prices: bool = True,
    sync_daily: bool = True,
    sync_intraday: bool = False,
) -> Security:
    """Get existing security or create new one with optional price sync.

    This is the central function for ensuring a security exists in the database.
    All routes should use this function instead of creating securities directly.
    Uses transactional context managers to ensure atomic operations.

    Args:
        db: Database session
        symbol: Security symbol (e.g., "AAPL", "MSFT")
        sync_prices: Whether to sync price data after creation
        sync_daily: Whether to sync daily prices (if sync_prices is True)
        sync_intraday: Whether to sync intraday prices (if sync_prices is True)

    Returns:
        Security: The existing or newly created security

    Raises:
        InvalidSymbolError: If symbol is not found in Yahoo Finance
        APIError: If Yahoo Finance API fails

    Example:
        # Create security and sync both price types
        security = await get_or_create_security(
            db,
            "AAPL",
            sync_prices=True,
            sync_daily=True,
            sync_intraday=True
        )

        # Just ensure security exists, no sync
        security = await get_or_create_security(db, "AAPL", sync_prices=False)
    """
    symbol = symbol.upper()
    repo = SecurityRepository(Security, db)

    # Use read-only transaction to check existence
    async with read_only_transaction(db):
        security = await repo.get_by_symbol(symbol)

    if security:
        logger.info(f"Security {symbol} already exists, returning existing")
        return security

    # Fetch info from yfinance
    logger.info(f"Fetching info for new security: {symbol}")
    security_info = fetch_security_info(symbol)

    # Create the security within transaction
    logger.info(f"Creating new security: {symbol}")
    async with transactional(db):
        security = Security(
            id=uuid.uuid4(),
            symbol=symbol,
            name=security_info.get("longName") or security_info.get("shortName") or symbol,
            currency=security_info.get("currency", "USD"),
            exchange=security_info.get("exchange"),
            security_type=security_info.get("quoteType", "EQUITY"),
        )
        db.add(security)

    # Refresh outside transaction
    await db.refresh(security)

    # Optionally sync prices
    if sync_prices:
        logger.info(f"Syncing prices for new security: {symbol}")

        if sync_daily:
            try:
                logger.info(f"Fetching daily historical data for {symbol}")
                daily_df = fetch_historical_prices(symbol, period="max", interval="1d")
                daily_prices = parse_yfinance_data(daily_df, security.id, "1d")

                if daily_prices:
                    async with transactional(db):
                        price_repo = SecurityPriceRepository(SecurityPrice, db)
                        await price_repo.bulk_create(daily_prices)
                        logger.info(f"Synced {len(daily_prices)} daily prices for {symbol}")
            except (InvalidSymbolError, APIError) as e:
                logger.warning(f"Failed to sync daily prices for {symbol}: {e}")

        if sync_intraday:
            try:
                logger.info(f"Fetching intraday data for {symbol}")
                intraday_df = fetch_historical_prices(symbol, period="7d", interval="1m")
                intraday_prices = parse_yfinance_data(intraday_df, security.id, "1m")

                if intraday_prices:
                    async with transactional(db):
                        price_repo = SecurityPriceRepository(SecurityPrice, db)
                        await price_repo.bulk_create(intraday_prices)
                        logger.info(f"Synced {len(intraday_prices)} intraday prices for {symbol}")
            except (InvalidSymbolError, APIError) as e:
                logger.warning(f"Failed to sync intraday prices for {symbol}: {e}")

        # Update last_synced_at timestamp within transaction
        async with transactional(db):
            security.last_synced_at = datetime.now(UTC)

    return security


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

    Uses transactional context managers for atomic operations and proper
    error handling with automatic rollback on failure.

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

    Note:
        - Automatically resets is_syncing flag on error
        - All sync status updates are atomic transactions
        - Price fetch failures log warnings but don't fail entire sync
    """
    symbol = symbol.upper()
    repo = SecurityRepository(Security, db)
    security = None

    # Check for concurrent sync if requested
    if check_concurrent:
        async with read_only_transaction(db):
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

        # Update sync status using transaction
        async with transactional(db):
            await repo.update_sync_status(
                symbol,
                is_syncing=False,
                last_synced_at=datetime.now(UTC),
            )

        await db.refresh(security)
        logger.info(f"Successfully synced {total_synced} price records for {symbol}")
        return security, total_synced

    except Exception as e:
        # Ensure is_syncing is reset on error using transaction
        if security := await repo.get_by_symbol(symbol):
            try:
                async with transactional(db):
                    await repo.update_sync_status(symbol, is_syncing=False)
            except Exception as rollback_error:
                logger.error(f"Failed to reset is_syncing flag for {symbol}: {rollback_error}")

        # Re-raise the original exception for caller to handle
        logger.error(f"Error syncing security {symbol}: {e}", exc_info=True)
        raise
