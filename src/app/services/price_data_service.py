"""Price data business logic service.

This service encapsulates all business logic related to security price data processing,
including date range normalization, data completeness calculations, and filtering.
It is designed to be framework-agnostic and reusable across different contexts.
"""

from datetime import datetime, timedelta
from typing import Literal

from app.core.constants import (
    COMPLETENESS_THRESHOLD_COMPLETE,
    COMPLETENESS_THRESHOLD_PARTIAL,
    DEFAULT_RANGE_MINUTE_INTERVAL_DAYS,
    DEFAULT_RANGE_OTHER_INTERVALS_DAYS,
    SEARCH_BUFFER_DAYS,
    TRADING_DAYS_PER_WEEK,
    TRADING_HOURS_PER_DAY,
    TRADING_MINUTES_PER_DAY,
)
from app.models.security_price import SecurityPrice

# Type alias for supported intervals
IntervalType = Literal["1m", "1h", "1d", "1wk"]

# Type alias for completeness status
CompletenessStatus = Literal["complete", "partial", "sparse", "empty"]


class PriceDataService:
    """Business logic service for price data operations.

    This service handles:
    - Date range normalization and defaults
    - Date range expansion for searching nearby data
    - Price filtering by date range
    - Expected data point calculations
    - Data completeness status determination

    All methods are stateless and can be called independently.
    """

    @staticmethod
    def normalize_and_default_date_range(
        start: datetime | None,
        end: datetime | None,
        interval: IntervalType,
    ) -> tuple[datetime, datetime]:
        """
        Normalize and set default values for date range in price queries.

        Converts naive datetimes to UTC-aware and sets sensible defaults when
        dates are not provided based on the interval type.

        Args:
            start: Optional start datetime (may be naive or aware)
            end: Optional end datetime (may be naive or aware)
            interval: Price interval (e.g., "1m", "1h", "1d", "1wk")

        Returns:
            Tuple of (start_date, end_date) both timezone-aware (UTC)

        Example:
            >>> from datetime import datetime, UTC
            >>> start, end = PriceDataService.normalize_and_default_date_range(
            ...     None, None, "1d"
            ... )
            >>> # Returns: (30 days ago, now) - both UTC-aware
            >>> start, end = PriceDataService.normalize_and_default_date_range(
            ...     datetime(2024, 1, 1),  # Naive
            ...     datetime(2024, 1, 31),  # Naive
            ...     "1d"
            ... )
            >>> # Returns: Both dates converted to UTC-aware
        """
        from datetime import UTC

        now = datetime.now(UTC)

        # Handle end datetime
        if end is None:
            requested_end = now
        elif end.tzinfo is None:
            requested_end = end.replace(tzinfo=UTC)
        else:
            requested_end = end

        # Handle start datetime with defaults based on interval
        if start is None:
            if interval == "1m":
                # Last 24 hours for minute data
                requested_start = now - timedelta(days=DEFAULT_RANGE_MINUTE_INTERVAL_DAYS)
            else:
                # Last 30 days for other intervals
                requested_start = now - timedelta(days=DEFAULT_RANGE_OTHER_INTERVALS_DAYS)
        elif start.tzinfo is None:
            requested_start = start.replace(tzinfo=UTC)
        else:
            requested_start = start

        return requested_start, requested_end

    @staticmethod
    def expand_date_range_for_search(
        start: datetime,
        end: datetime,
        buffer_days: int = SEARCH_BUFFER_DAYS,
    ) -> tuple[datetime, datetime]:
        """
        Expand date range to find nearby data if exact range has gaps.

        This handles weekends, holidays, and sparse trading data by searching
        a broader time window around the requested range.

        Args:
            start: Start datetime (timezone-aware)
            end: End datetime (timezone-aware)
            buffer_days: Number of days to expand before/after (default: 7)

        Returns:
            Tuple of (expanded_start, expanded_end)

        Example:
            >>> from datetime import datetime, UTC
            >>> start = datetime(2024, 1, 15, tzinfo=UTC)
            >>> end = datetime(2024, 1, 20, tzinfo=UTC)
            >>> expanded_start, expanded_end = (
            ...     PriceDataService.expand_date_range_for_search(start, end)
            ... )
            >>> # Returns: (2024-01-08, 2024-01-27) with 7-day buffer
        """
        expanded_start = start - timedelta(days=buffer_days)
        expanded_end = end + timedelta(days=buffer_days)
        return expanded_start, expanded_end

    @staticmethod
    def filter_prices_to_date_range(
        prices: list[SecurityPrice],
        start: datetime,
        end: datetime,
    ) -> list[SecurityPrice]:
        """
        Filter security prices to those within the specified date range.

        Ensures all timestamps are timezone-aware before comparison.

        Args:
            prices: List of SecurityPrice objects (may have naive or aware timestamps)
            start: Start datetime (timezone-aware)
            end: End datetime (timezone-aware)

        Returns:
            Filtered list of SecurityPrice objects within the range

        Example:
            >>> from datetime import datetime, UTC
            >>> prices = [...]  # List of SecurityPrice objects
            >>> start = datetime(2024, 1, 1, tzinfo=UTC)
            >>> end = datetime(2024, 1, 31, tzinfo=UTC)
            >>> filtered = PriceDataService.filter_prices_to_date_range(
            ...     prices, start, end
            ... )
            >>> # Returns only prices between start and end
        """
        from datetime import UTC

        return [
            p
            for p in prices
            if start
            <= (p.timestamp.replace(tzinfo=UTC) if p.timestamp.tzinfo is None else p.timestamp)
            <= end
        ]

    @staticmethod
    def calculate_expected_data_points(
        start: datetime,
        end: datetime,
        interval: IntervalType,
    ) -> int:
        """
        Calculate expected number of data points for a date range and interval.

        Takes into account typical trading patterns (weekends, trading hours)
        to estimate realistic expected data points.

        Args:
            start: Start datetime (timezone-aware)
            end: End datetime (timezone-aware)
            interval: Price interval ("1m", "1h", "1d", "1wk")

        Returns:
            Expected number of data points (minimum 1)

        Example:
            >>> from datetime import datetime, UTC
            >>> start = datetime(2024, 1, 1, tzinfo=UTC)
            >>> end = datetime(2024, 1, 10, tzinfo=UTC)  # 9 days
            >>> expected = PriceDataService.calculate_expected_data_points(
            ...     start, end, "1d"
            ... )
            >>> # Returns: ~6 (9 days * 5 trading days / 7 days per week)
        """
        time_span_days = (end - start).days

        if interval == "1d":
            # Daily data: expect ~5 trading days per week
            return max(1, int(time_span_days * TRADING_DAYS_PER_WEEK / 7))
        elif interval == "1wk":
            # Weekly data: expect ~1 point per week
            return max(1, time_span_days // 7)
        elif interval == "1h":
            # Hourly data: expect ~6.5 trading hours per day
            return max(1, int(time_span_days * TRADING_HOURS_PER_DAY))
        else:  # "1m"
            # Minute data: expect ~390 minutes per trading day
            return max(1, int(time_span_days * TRADING_MINUTES_PER_DAY))

    @staticmethod
    def calculate_data_completeness(
        actual_points: int,
        expected_points: int,
        has_data_in_range: bool,
    ) -> CompletenessStatus:
        """
        Calculate data completeness status based on actual vs expected points.

        Args:
            actual_points: Number of actual data points received
            expected_points: Number of expected data points in the range
            has_data_in_range: Whether any data exists in the requested range

        Returns:
            Completeness status: "complete", "partial", "sparse", or "empty"

        Example:
            >>> # 90 out of 100 points = complete
            >>> PriceDataService.calculate_data_completeness(90, 100, True)
            'complete'
            >>> # 50 out of 100 points = partial
            >>> PriceDataService.calculate_data_completeness(50, 100, True)
            'partial'
            >>> # 10 out of 100 points = sparse
            >>> PriceDataService.calculate_data_completeness(10, 100, True)
            'sparse'
            >>> # No data = partial (data exists but outside range)
            >>> PriceDataService.calculate_data_completeness(0, 100, False)
            'partial'
        """
        if not has_data_in_range:
            # Data exists but outside requested range
            return "partial"

        if expected_points == 0:
            return "complete"

        completeness_ratio = actual_points / expected_points

        if completeness_ratio >= COMPLETENESS_THRESHOLD_COMPLETE:
            return "complete"
        elif completeness_ratio >= COMPLETENESS_THRESHOLD_PARTIAL:
            return "partial"
        else:
            return "sparse"
