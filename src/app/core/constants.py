"""Application-wide constants and configuration values.

This module centralizes all magic numbers and configuration constants used throughout
the application, providing:
- Clear documentation of what each constant represents
- Single source of truth for configuration values
- Easy modification of behavior across the entire codebase
- Type safety and IDE autocomplete support

Constants are organized into logical groups for easy navigation and maintenance.
"""


class PriceDataConstants:
    """Constants for price data processing and completeness calculations."""

    # Data completeness thresholds for determining data quality
    # These thresholds determine the "status" of price data based on what percentage
    # of expected data points are actually available.
    COMPLETENESS_THRESHOLD_COMPLETE = 0.8  # 80% or more = "complete" status
    COMPLETENESS_THRESHOLD_PARTIAL = 0.4  # 40-79% = "partial" status
    # Below 40% = "sparse" status

    # Trading schedule constants (typical market patterns)
    # Based on US equity market (NYSE) trading hours: 9:30 AM - 4:00 PM ET
    TRADING_DAYS_PER_WEEK = 5  # Monday through Friday
    DAYS_PER_WEEK = 7  # Calendar days
    TRADING_HOURS_PER_DAY = 6.5  # Hours of active trading per day
    TRADING_MINUTES_PER_DAY = 390  # Minutes of active trading per day (6.5 * 60)

    # Date range expansion for flexible data searching
    # When searching for data, we expand the requested range to account for
    # weekends, holidays, and sparse trading data. This helps ensure we find
    # available data even if exact dates have no trading activity.
    SEARCH_BUFFER_DAYS = 7  # Expand search by 7 days before and after requested range


class PriceIntervalConstants:
    """Constants for default date ranges by price interval type."""

    # When users don't specify a start date, these defaults are used based on
    # the requested price interval. Minute data shows recent activity, while
    # daily data shows longer-term trends.
    DEFAULT_RANGE_MINUTE_INTERVAL_DAYS = 1  # Last 24 hours for 1m prices
    DEFAULT_RANGE_OTHER_INTERVALS_DAYS = 30  # Last 30 days for 1h/1d/1wk prices


class SecuritySyncConstants:
    """Constants for security data synchronization operations."""

    # Prevent excessive API calls by enforcing minimum time between syncs
    # Users cannot sync the same security more frequently than this interval
    MIN_SYNC_INTERVAL_SECONDS = 300  # 5 minutes

    # After this duration, cached security metadata is considered stale
    # This determines when to re-fetch data from yfinance
    STALE_DATA_THRESHOLD_SECONDS = 3600  # 1 hour


class APIConstants:
    """Constants for API behavior, limits, and defaults."""

    # Pagination defaults for list endpoints
    DEFAULT_PAGE_SIZE = 100  # Default items per page
    MAX_PAGE_SIZE = 1000  # Maximum allowed items per page


class SearchConstants:
    """Constants for search functionality."""

    # Symbol search constraint to differentiate symbols from full-text searches
    # If query is short and uppercase-like, treat as potential symbol
    MAX_SYMBOL_LENGTH = 10  # Maximum length for a stock symbol query


# ============================================================================
# BACKWARD COMPATIBILITY EXPORTS
# ============================================================================
# These exports maintain compatibility with code that imports constants directly
# from this module. New code should use the class-based approach above.

# Price data completeness thresholds
COMPLETENESS_THRESHOLD_COMPLETE = PriceDataConstants.COMPLETENESS_THRESHOLD_COMPLETE
COMPLETENESS_THRESHOLD_PARTIAL = PriceDataConstants.COMPLETENESS_THRESHOLD_PARTIAL

# Trading schedule constants
TRADING_DAYS_PER_WEEK = PriceDataConstants.TRADING_DAYS_PER_WEEK
DAYS_PER_WEEK = PriceDataConstants.DAYS_PER_WEEK
TRADING_HOURS_PER_DAY = PriceDataConstants.TRADING_HOURS_PER_DAY
TRADING_MINUTES_PER_DAY = PriceDataConstants.TRADING_MINUTES_PER_DAY

# Date range expansion
SEARCH_BUFFER_DAYS = PriceDataConstants.SEARCH_BUFFER_DAYS

# Default date ranges by interval
DEFAULT_RANGE_MINUTE_INTERVAL_DAYS = PriceIntervalConstants.DEFAULT_RANGE_MINUTE_INTERVAL_DAYS
DEFAULT_RANGE_OTHER_INTERVALS_DAYS = PriceIntervalConstants.DEFAULT_RANGE_OTHER_INTERVALS_DAYS
