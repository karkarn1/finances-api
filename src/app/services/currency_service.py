"""Currency service for fetching exchange rates from frankfurter.app API.

This module provides async functions to fetch exchange rates from frankfurter.app
and store them in the database for historical tracking and offline access.

Exchange Rate Source:
- frankfurter.app API (https://www.frankfurter.app)
- Provides current and historical foreign exchange rates from European Central Bank
- Free, no authentication required
- Reliable and well-maintained

Caching Strategy:
- Exchange rates stored in database by date
- Unique constraint prevents duplicate rates for same currency pair and date
- Historical rates preserved for accurate multi-currency calculations
"""

import logging
from datetime import date, datetime
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.currency import Currency
from app.models.currency_rate import CurrencyRate

logger = logging.getLogger(__name__)

# Frankfurter API configuration
_FRANKFURTER_API_BASE = "https://api.frankfurter.app"
_REQUEST_TIMEOUT = 30.0


async def fetch_exchange_rates(base_currency: str) -> dict[str, float] | None:
    """Fetch exchange rates for a base currency from frankfurter.app API.

    Args:
        base_currency: ISO 4217 currency code (e.g., "USD", "EUR")

    Returns:
        Dictionary mapping currency codes to exchange rates, or None on failure.
        Example: {"USD": 1.0, "EUR": 0.92, "CAD": 1.35}

    Example:
        >>> rates = await fetch_exchange_rates("USD")
        >>> print(rates["EUR"])
        0.92
        >>> print(rates["CAD"])
        1.35

    Note:
        Returns None on API failures (logs error). This ensures graceful
        degradation if the external service is unavailable.
        Uses frankfurter.app API which is free and reliable.
    """
    try:
        # frankfurter.app endpoint: /latest?from=USD
        url = f"{_FRANKFURTER_API_BASE}/latest"
        params = {"from": base_currency.upper()}

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()

        data = response.json()

        # Validate response structure
        if "rates" not in data:
            logger.error(f"Invalid API response: missing 'rates' field: {data}")
            return None

        # Get rates and add base currency with rate 1.0
        rates = data["rates"]
        rates[base_currency.upper()] = 1.0

        logger.info(
            f"Fetched {len(rates)} exchange rates for base currency {base_currency}"
        )
        return rates

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching exchange rates for {base_currency}: {e}")
        return None
    except httpx.RequestError as e:
        logger.error(f"Request error fetching exchange rates for {base_currency}: {e}")
        return None
    except KeyError as e:
        logger.error(f"Missing expected field in API response: {e}")
        return None
    except Exception as e:
        logger.error(
            f"Unexpected error fetching exchange rates for {base_currency}: {e}"
        )
        return None


async def sync_currency_rates(
    db: AsyncSession, base_currency: str = "USD", sync_date: date | None = None
) -> tuple[int, int]:
    """Fetch and store exchange rates for a base currency in the database.

    Fetches current exchange rates from external API and stores them in the database
    for the specified date. Skips currencies that don't exist in the database.

    Args:
        db: Database session
        base_currency: Base currency code (default: "USD")
        sync_date: Date to sync rates for (default: today)

    Returns:
        Tuple of (synced_count, failed_count) representing successful and failed syncs

    Example:
        >>> synced, failed = await sync_currency_rates(db, "USD")
        >>> print(f"Synced {synced} rates, {failed} failures")
        Synced 8 rates, 0 failures

    Note:
        - Creates bidirectional rates (e.g., USD->EUR and EUR->USD)
        - Skips duplicate rates (unique constraint on from/to/date)
        - Only syncs currencies that exist in the database
        - Logs all operations for monitoring
    """
    if sync_date is None:
        sync_date = date.today()

    logger.info(f"Starting rate sync for base currency {base_currency} on {sync_date}")

    # Fetch rates from external API
    rates = await fetch_exchange_rates(base_currency)
    if rates is None:
        logger.error(f"Failed to fetch rates for {base_currency}, aborting sync")
        return 0, 0

    # Get base currency from database
    result = await db.execute(
        select(Currency).where(Currency.code == base_currency.upper())
    )
    base_curr = result.scalar_one_or_none()

    if base_curr is None:
        logger.error(f"Base currency {base_currency} not found in database")
        return 0, 0

    # Get all active currencies from database
    result = await db.execute(select(Currency).where(Currency.is_active == True))  # noqa: E712
    all_currencies = {curr.code: curr for curr in result.scalars().all()}

    synced_count = 0
    failed_count = 0

    # Store rates for each currency
    for currency_code, rate_value in rates.items():
        if currency_code not in all_currencies:
            logger.debug(f"Skipping {currency_code} - not in database")
            continue

        target_curr = all_currencies[currency_code]

        # Skip if base and target are the same currency
        if base_curr.id == target_curr.id:
            logger.debug(f"Skipping {currency_code} - same as base currency")
            continue

        try:
            # Create rate from base to target currency
            rate = CurrencyRate(
                from_currency_id=base_curr.id,
                to_currency_id=target_curr.id,
                rate=Decimal(str(rate_value)),
                date=sync_date,
            )
            db.add(rate)

            # Create reverse rate (target to base)
            if rate_value != 0:
                reverse_rate = CurrencyRate(
                    from_currency_id=target_curr.id,
                    to_currency_id=base_curr.id,
                    rate=Decimal(str(1 / rate_value)),
                    date=sync_date,
                )
                db.add(reverse_rate)

            synced_count += 2  # Count both directions

        except Exception as e:
            logger.error(f"Failed to create rate for {currency_code}: {e}")
            failed_count += 1

    try:
        await db.commit()
        logger.info(
            f"Successfully synced {synced_count} rates for {base_currency} "
            f"on {sync_date} ({failed_count} failures)"
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to commit rates to database: {e}")
        return 0, failed_count

    return synced_count, failed_count


async def get_exchange_rate(
    db: AsyncSession,
    from_currency: str,
    to_currency: str,
    rate_date: date | None = None,
) -> Decimal | None:
    """Get exchange rate between two currencies for a specific date.

    Args:
        db: Database session
        from_currency: Source currency code
        to_currency: Target currency code
        rate_date: Date for the rate (default: today)

    Returns:
        Exchange rate as Decimal, or None if not found

    Example:
        >>> rate = await get_exchange_rate(db, "USD", "CAD")
        >>> print(f"1 USD = {rate} CAD")
        1 USD = 1.35 CAD
    """
    if rate_date is None:
        rate_date = date.today()

    # Get currency IDs
    result = await db.execute(
        select(Currency).where(Currency.code.in_([from_currency, to_currency]))
    )
    currencies = {curr.code: curr for curr in result.scalars().all()}

    if from_currency not in currencies or to_currency not in currencies:
        logger.warning(f"Currency not found: {from_currency} or {to_currency}")
        return None

    from_curr = currencies[from_currency]
    to_curr = currencies[to_currency]

    # Get rate for the date
    result = await db.execute(
        select(CurrencyRate).where(
            CurrencyRate.from_currency_id == from_curr.id,
            CurrencyRate.to_currency_id == to_curr.id,
            CurrencyRate.date == rate_date,
        )
    )
    rate = result.scalar_one_or_none()

    if rate is None:
        logger.warning(
            f"Rate not found for {from_currency}->{to_currency} on {rate_date}"
        )
        return None

    return rate.rate
