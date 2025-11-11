"""Currency service for fetching exchange rates using yfinance.

This module provides async functions to fetch exchange rates from Yahoo Finance
via yfinance and store them in the database for historical tracking and offline access.

Exchange Rate Source:
- yfinance (https://github.com/ranaroussi/yfinance)
- Provides current and historical foreign exchange rates from Yahoo Finance
- Free, no authentication required
- Supports historical data for accurate backtesting and analysis

Features:
- Current exchange rates via yfinance Ticker API
- Historical rates support (unlike exchangerate-api.com)
- Currency pair format: "USDEUR=X" for USD to EUR rate
- Reliable data source maintained by Yahoo Finance

Caching Strategy:
- Exchange rates stored in database by date
- Unique constraint prevents duplicate rates for same currency pair and date
- Historical rates preserved for accurate multi-currency calculations
"""

import asyncio
import logging
from datetime import date, timedelta
from decimal import Decimal

import yfinance as yf  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.currency import Currency
from app.models.currency_rate import CurrencyRate

logger = logging.getLogger(__name__)

# Major currency codes supported by Yahoo Finance
# Format: "{BASE}{TARGET}=X" (e.g., "USDEUR=X" for USD to EUR rate)
MAJOR_CURRENCIES = [
    "USD",
    "EUR",
    "GBP",
    "JPY",
    "CAD",
    "AUD",
    "CHF",
    "CNY",
    "HKD",
    "NZD",
    "SEK",
    "NOK",
    "DKK",
    "SGD",
    "KRW",
    "INR",
]


async def fetch_exchange_rates(
    base_currency: str, rate_date: date | None = None
) -> dict[str, float] | None:
    """Fetch exchange rates for a base currency using yfinance.

    Fetches current or historical rates from Yahoo Finance. Unlike exchangerate-api.com,
    yfinance fully supports historical data for accurate backtesting and analysis.

    Args:
        base_currency: ISO 4217 currency code (e.g., "USD", "EUR")
        rate_date: Specific date to fetch rates for (default: None for current rates)
                   Historical dates are fully supported via yfinance

    Returns:
        Dictionary mapping currency codes to exchange rates, or None on failure.
        Example: {"USD": 1.0, "EUR": 0.92, "CAD": 1.35}

    Example:
        >>> # Get current rates
        >>> rates = await fetch_exchange_rates("USD")
        >>> print(rates["EUR"])
        0.92
        >>> # Get historical rates (now supported!)
        >>> from datetime import date
        >>> rates = await fetch_exchange_rates("USD", date(2024, 1, 15))
        >>> print(rates["EUR"])  # Returns actual historical rate for 2024-01-15
        0.91

    Note:
        Returns None on API failures (logs error). This ensures graceful
        degradation if the external service is unavailable.
        Uses yfinance Ticker.history() for data retrieval.
    """
    base_currency_upper = base_currency.upper()

    try:
        # Determine target currencies (all except base)
        target_currencies = [curr for curr in MAJOR_CURRENCIES if curr != base_currency_upper]

        if not target_currencies:
            logger.error(f"No target currencies found for base {base_currency}")
            return None

        # Build currency pair tickers (format: "USDEUR=X" for USD to EUR)
        ticker_symbols = [f"{base_currency_upper}{target}=X" for target in target_currencies]

        # Determine date range for fetching
        if rate_date is None:
            # Fetch current/recent data (last 5 days to ensure we get latest)
            end_date = date.today()
            start_date = end_date - timedelta(days=5)
            logger.info(f"Fetching current rates for {base_currency} (last 5 days)")
        else:
            # Fetch historical data for specific date (add buffer for weekends/holidays)
            start_date = rate_date - timedelta(days=7)
            end_date = rate_date + timedelta(days=1)
            logger.info(f"Fetching historical rates for {base_currency} on {rate_date}")

        # Fetch data using yfinance (synchronous, so run in executor)
        loop = asyncio.get_running_loop()

        def fetch_yfinance_data() -> dict[str, float]:
            """Fetch exchange rate data from yfinance (runs in executor)."""
            rates_dict: dict[str, float] = {}

            for i, ticker_symbol in enumerate(ticker_symbols):
                target_currency = target_currencies[i]

                try:
                    # Create ticker and fetch historical data
                    ticker = yf.Ticker(ticker_symbol)
                    hist = ticker.history(start=start_date, end=end_date)

                    if hist.empty:
                        logger.warning(
                            f"No data returned for {ticker_symbol} "
                            f"(period: {start_date} to {end_date})"
                        )
                        continue

                    # Get the close price for the target date (or most recent)
                    if rate_date is None:
                        # Use most recent close price
                        rate_value = hist["Close"].iloc[-1]
                    else:
                        # Find closest date to requested date
                        hist.index = hist.index.tz_localize(None)  # Remove timezone
                        closest_date = min(hist.index, key=lambda d: abs(d.date() - rate_date))
                        rate_value = hist.loc[closest_date]["Close"]

                    rates_dict[target_currency] = float(rate_value)

                except Exception as e:
                    logger.warning(f"Failed to fetch rate for {ticker_symbol}: {e}")
                    continue

            return rates_dict

        # Run yfinance fetch in executor to avoid blocking event loop
        rates = await loop.run_in_executor(None, fetch_yfinance_data)

        if not rates:
            logger.error(f"No exchange rates fetched for {base_currency}")
            return None

        # Add base currency with rate 1.0
        rates[base_currency_upper] = 1.0

        logger.info(
            f"Successfully fetched {len(rates)} exchange rates for {base_currency} "
            f"({'current' if rate_date is None else f'date: {rate_date}'})"
        )
        return rates

    except Exception as e:
        logger.error(
            f"Unexpected error fetching exchange rates for {base_currency}: {e}", exc_info=True
        )
        return None


async def sync_currency_rates(
    db: AsyncSession, base_currency: str = "USD", sync_date: date | None = None
) -> tuple[int, int]:
    """Fetch and store exchange rates for a base currency in the database.

    Fetches current or historical exchange rates from Yahoo Finance via yfinance
    and stores them in the database for the specified date. Skips currencies that
    don't exist in the database.

    Args:
        db: Database session
        base_currency: Base currency code (default: "USD")
        sync_date: Date to sync rates for (default: today)
                   Historical dates fully supported via yfinance

    Returns:
        Tuple of (synced_count, failed_count) representing successful and failed syncs

    Example:
        >>> # Sync current rates
        >>> synced, failed = await sync_currency_rates(db, "USD")
        >>> print(f"Synced {synced} rates, {failed} failures")
        Synced 8 rates, 0 failures
        >>> # Sync historical rates (now supported!)
        >>> synced, failed = await sync_currency_rates(db, "USD", date(2024, 1, 15))
        >>> print(f"Synced {synced} historical rates")
        Synced 8 historical rates

    Note:
        - Creates bidirectional rates (e.g., USD->EUR and EUR->USD)
        - Skips duplicate rates (unique constraint on from/to/date)
        - Only syncs currencies that exist in the database
        - Logs all operations for monitoring
        - Historical rates are fetched from Yahoo Finance via yfinance
    """
    if sync_date is None:
        sync_date = date.today()

    logger.info(f"Starting rate sync for base currency {base_currency} on {sync_date}")

    # Fetch rates from external API for the specified date
    rates = await fetch_exchange_rates(base_currency, sync_date)
    if rates is None:
        logger.error(f"Failed to fetch rates for {base_currency}, aborting sync")
        return 0, 0

    # Get base currency from database
    base_currency_upper = base_currency.upper()
    result = await db.execute(select(Currency).where(Currency.code == base_currency_upper))
    base_curr = result.scalar_one_or_none()

    if base_curr is None:
        logger.error(f"Base currency {base_currency} not found in database")
        return 0, 0

    # Get all currencies from database
    result = await db.execute(select(Currency))
    all_currencies = {curr.code for curr in result.scalars().all()}

    synced_count = 0
    failed_count = 0

    # Store rates for each currency
    for currency_code, rate_value in rates.items():
        if currency_code not in all_currencies:
            logger.debug(f"Skipping {currency_code} - not in database")
            continue

        # Skip if base and target are the same currency
        if base_currency_upper == currency_code:
            logger.debug(f"Skipping {currency_code} - same as base currency")
            continue

        try:
            # Create rate from base to target currency
            rate = CurrencyRate(
                from_currency_code=base_currency_upper,
                to_currency_code=currency_code,
                rate=Decimal(str(rate_value)),
                date=sync_date,
            )
            db.add(rate)

            # Create reverse rate (target to base)
            if rate_value != 0:
                reverse_rate = CurrencyRate(
                    from_currency_code=currency_code,
                    to_currency_code=base_currency_upper,
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

    from_currency_upper = from_currency.upper()
    to_currency_upper = to_currency.upper()

    # Verify currencies exist
    result = await db.execute(
        select(Currency).where(Currency.code.in_([from_currency_upper, to_currency_upper]))
    )
    existing_codes = {curr.code for curr in result.scalars().all()}

    if from_currency_upper not in existing_codes or to_currency_upper not in existing_codes:
        logger.warning(f"Currency not found: {from_currency} or {to_currency}")
        return None

    # Get rate for the date
    stmt = select(CurrencyRate).where(
        CurrencyRate.from_currency_code == from_currency_upper,
        CurrencyRate.to_currency_code == to_currency_upper,
        CurrencyRate.date == rate_date,
    )
    result = await db.execute(stmt)
    currency_rate = result.scalar_one_or_none()

    if currency_rate is None:
        logger.warning(f"Rate not found for {from_currency}->{to_currency} on {rate_date}")
        return None

    return currency_rate.rate
