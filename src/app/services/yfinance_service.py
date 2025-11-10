"""Service layer for interacting with yfinance API.

Note:
    HTTP caching is configured globally via requests-cache with Redis backend.
    Cache configuration is in app.core.cache and initialized during app startup.
    All HTTP requests made by yfinance are automatically cached based on URL patterns:
    - Daily/weekly/monthly data: 24 hours
    - Intraday data (1m, 1h): 15 minutes
    - Security metadata: 6 hours
"""

import logging
import uuid
from datetime import UTC, datetime

import pandas as pd
import yfinance as yf

from app.models.security_price import SecurityPrice

logger = logging.getLogger(__name__)


class YFinanceError(Exception):
    """Base exception for yfinance service errors."""

    pass


class InvalidSymbolError(YFinanceError):
    """Raised when symbol is not found in Yahoo Finance."""

    pass


class APIError(YFinanceError):
    """Raised when Yahoo Finance API returns an error."""

    pass


def fetch_security_info(symbol: str) -> dict[str, str | float | None]:
    """
    Fetch security metadata from Yahoo Finance.

    Args:
        symbol: Stock symbol (e.g., "AAPL", "MSFT")

    Returns:
        Dictionary containing security metadata:
        - name: Company/security name
        - exchange: Exchange (e.g., "NASDAQ")
        - currency: Currency code (e.g., "USD")
        - security_type: Type (e.g., "EQUITY", "ETF")
        - sector: Business sector
        - industry: Industry
        - market_cap: Market capitalization

    Raises:
        InvalidSymbolError: If symbol is not found
        APIError: If API request fails
    """
    try:
        ticker = yf.Ticker(symbol.upper())
        info = ticker.info

        # Check if symbol is valid (yfinance returns empty dict or error message)
        if not info or "symbol" not in info:
            raise InvalidSymbolError(f"Symbol '{symbol}' not found in Yahoo Finance")

        # Extract relevant fields with fallbacks
        return {
            "name": info.get("longName") or info.get("shortName") or symbol,
            "exchange": info.get("exchange"),
            "currency": info.get("currency"),
            "security_type": info.get("quoteType"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
        }

    except Exception as e:
        if isinstance(e, (InvalidSymbolError, APIError)):
            raise
        logger.error(f"Error fetching security info for {symbol}: {e}")
        raise APIError(f"Failed to fetch security info: {str(e)}") from e


def fetch_historical_prices(
    symbol: str, period: str = "max", interval: str = "1d"
) -> pd.DataFrame:
    """
    Fetch historical price data from Yahoo Finance.

    Args:
        symbol: Stock symbol
        period: Time period (e.g., "1d", "1mo", "1y", "max")
        interval: Data interval (e.g., "1m", "1h", "1d", "1wk")

    Returns:
        DataFrame with columns: Open, High, Low, Close, Volume
        Index is datetime (timezone-aware)

    Raises:
        InvalidSymbolError: If symbol is not found
        APIError: If API request fails

    Note:
        - Minute data ("1m") only available for last 7 days
        - Data may be delayed 15-20 minutes
    """
    try:
        ticker = yf.Ticker(symbol.upper())
        df = ticker.history(period=period, interval=interval)

        if df.empty:
            raise InvalidSymbolError(
                f"No data available for symbol '{symbol}' with period={period}, interval={interval}"
            )

        return df

    except Exception as e:
        if isinstance(e, (InvalidSymbolError, APIError)):
            raise
        logger.error(
            f"Error fetching historical prices for {symbol} "
            f"(period={period}, interval={interval}): {e}"
        )
        raise APIError(f"Failed to fetch historical prices: {str(e)}") from e


def fetch_price_range(
    symbol: str, start: datetime, end: datetime, interval: str = "1d"
) -> pd.DataFrame:
    """
    Fetch price data for a specific date range.

    Args:
        symbol: Stock symbol
        start: Start datetime (timezone-aware or naive)
        end: End datetime (timezone-aware or naive)
        interval: Data interval (e.g., "1m", "1h", "1d", "1wk")

    Returns:
        DataFrame with columns: Open, High, Low, Close, Volume
        Index is datetime (timezone-aware)

    Raises:
        InvalidSymbolError: If symbol is not found
        APIError: If API request fails
    """
    try:
        ticker = yf.Ticker(symbol.upper())
        df = ticker.history(start=start, end=end, interval=interval)

        if df.empty:
            raise InvalidSymbolError(
                f"No data available for symbol '{symbol}' in date range {start} to {end}"
            )

        return df

    except Exception as e:
        if isinstance(e, (InvalidSymbolError, APIError)):
            raise
        logger.error(
            f"Error fetching price range for {symbol} ({start} to {end}): {e}"
        )
        raise APIError(f"Failed to fetch price range: {str(e)}") from e


def fetch_batch_historical_prices(
    symbols: list[str],
    period: str = "max",
    interval: str = "1d",
) -> dict[str, pd.DataFrame]:
    """
    Fetch historical price data for multiple symbols at once (batch download).

    This is significantly faster than individual requests as it uses yfinance's
    multi-ticker download with threading.

    Args:
        symbols: List of stock symbols (e.g., ["AAPL", "MSFT", "GOOGL"])
        period: Time period (e.g., "1d", "1mo", "1y", "max")
        interval: Data interval (e.g., "1m", "1h", "1d", "1wk")

    Returns:
        Dictionary mapping symbol to its DataFrame
        - For successful downloads: DataFrame with Open, High, Low, Close, Volume
        - For failed downloads: Empty DataFrame or None

    Raises:
        APIError: If batch download fails completely

    Note:
        - Uses threading for parallel downloads (much faster)
        - Handles missing/invalid symbols gracefully (returns empty DataFrame)
        - Progress bar disabled for cleaner logs
        - Single ticker is handled differently by yfinance (returns simple DataFrame)

    Example:
        >>> data = fetch_batch_historical_prices(["AAPL", "MSFT"], period="1y")
        >>> aapl_df = data.get("AAPL")
        >>> if aapl_df is not None and not aapl_df.empty:
        ...     # Process AAPL data
    """
    try:
        symbols_upper = [s.upper() for s in symbols]

        # Use yfinance's batch download with threading
        data = yf.download(
            tickers=symbols_upper,
            period=period,
            interval=interval,
            group_by="ticker",  # Group by ticker for multi-ticker downloads
            threads=True,  # Use multithreading
            progress=False,  # Disable progress bar for cleaner logs
        )

        # Handle single ticker case (yfinance returns simple DataFrame)
        if len(symbols_upper) == 1:
            symbol = symbols_upper[0]
            if data.empty:
                logger.warning(f"No data returned for {symbol}")
                return {symbol: pd.DataFrame()}
            return {symbol: data}

        # Handle multi-ticker case (yfinance returns nested structure)
        result: dict[str, pd.DataFrame] = {}
        for symbol in symbols_upper:
            try:
                # Access ticker data from grouped structure
                ticker_data = data[symbol] if symbol in data.columns.levels[0] else None

                if ticker_data is None or ticker_data.empty:
                    logger.warning(f"No data available for {symbol}")
                    result[symbol] = pd.DataFrame()
                else:
                    result[symbol] = ticker_data
            except (KeyError, AttributeError) as e:
                logger.warning(f"Could not extract data for {symbol}: {e}")
                result[symbol] = pd.DataFrame()

        return result

    except Exception as e:
        logger.error(f"Error in batch download for {len(symbols)} symbols: {e}")
        raise APIError(f"Batch download failed: {str(e)}") from e


def parse_yfinance_data(
    df: pd.DataFrame, security_id: uuid.UUID, interval_type: str
) -> list[SecurityPrice]:
    """
    Convert yfinance DataFrame to list of SecurityPrice models.

    Args:
        df: DataFrame from yfinance with Open, High, Low, Close, Volume columns
        security_id: UUID of the security
        interval_type: Interval type (e.g., "1m", "1d", "1wk")

    Returns:
        List of SecurityPrice model instances ready for database insertion

    Note:
        - Converts all timestamps to UTC
        - Handles both timezone-aware and naive timestamps
        - Skips rows with missing data
    """
    prices = []

    for timestamp, row in df.iterrows():
        # Skip rows with NaN values
        if row.isna().any():
            continue

        # Convert timestamp to UTC datetime
        if isinstance(timestamp, pd.Timestamp):
            # If timezone-aware, convert to UTC; if naive, assume UTC
            if timestamp.tz is not None:
                dt = timestamp.tz_convert(UTC).to_pydatetime()
            else:
                dt = timestamp.to_pydatetime().replace(tzinfo=UTC)
        else:
            # Handle datetime objects
            if hasattr(timestamp, "tzinfo") and timestamp.tzinfo is not None:
                dt = timestamp.astimezone(UTC)
            else:
                dt = timestamp.replace(tzinfo=UTC)

        prices.append(
            SecurityPrice(
                id=uuid.uuid4(),
                security_id=security_id,
                timestamp=dt,
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]),
                interval_type=interval_type,
            )
        )

    return prices
