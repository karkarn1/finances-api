"""Tests for securities endpoint helper functions."""

from datetime import UTC, datetime

import pytest

from app.core.constants import (
    COMPLETENESS_THRESHOLD_COMPLETE,
    COMPLETENESS_THRESHOLD_PARTIAL,
    DEFAULT_RANGE_MINUTE_INTERVAL_DAYS,
    DEFAULT_RANGE_OTHER_INTERVALS_DAYS,
    TRADING_DAYS_PER_WEEK,
    TRADING_HOURS_PER_DAY,
    TRADING_MINUTES_PER_DAY,
)
from app.models.security_price import SecurityPrice
from app.services.price_data_service import PriceDataService

pytestmark = pytest.mark.unit


class TestNormalizeAndDefaultDateRange:
    """Tests for normalize_and_default_date_range function."""

    def test_both_dates_provided_aware(self):
        """Test when both dates are provided and timezone-aware."""
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 1, 31, tzinfo=UTC)

        result_start, result_end = PriceDataService.normalize_and_default_date_range(
            start, end, "1d"
        )

        assert result_start == start
        assert result_end == end
        assert result_start.tzinfo is not None
        assert result_end.tzinfo is not None

    def test_both_dates_provided_naive(self):
        """Test when both dates are naive (no timezone)."""
        start = datetime(2024, 1, 1)  # Naive
        end = datetime(2024, 1, 31)  # Naive

        result_start, result_end = PriceDataService.normalize_and_default_date_range(
            start, end, "1d"
        )

        # Should be converted to UTC-aware
        assert result_start.tzinfo is not None
        assert result_end.tzinfo is not None
        assert result_start.year == 2024
        assert result_start.month == 1
        assert result_start.day == 1

    def test_none_dates_daily_interval(self):
        """Test default range for daily interval."""
        result_start, result_end = PriceDataService.normalize_and_default_date_range(
            None, None, "1d"
        )

        # Should default to DEFAULT_RANGE_OTHER_INTERVALS_DAYS days ago to now
        assert result_start.tzinfo is not None
        assert result_end.tzinfo is not None
        delta = result_end - result_start
        assert delta.days == DEFAULT_RANGE_OTHER_INTERVALS_DAYS

    def test_none_dates_minute_interval(self):
        """Test default range for minute interval."""
        result_start, result_end = PriceDataService.normalize_and_default_date_range(
            None, None, "1m"
        )

        # Should default to DEFAULT_RANGE_MINUTE_INTERVAL_DAYS day ago to now
        assert result_start.tzinfo is not None
        assert result_end.tzinfo is not None
        delta = result_end - result_start
        assert delta.days == DEFAULT_RANGE_MINUTE_INTERVAL_DAYS

    def test_end_none_start_provided(self):
        """Test when only start date is provided."""
        start = datetime(2024, 1, 1, tzinfo=UTC)

        result_start, result_end = PriceDataService.normalize_and_default_date_range(
            start, None, "1d"
        )

        assert result_start == start
        assert result_end.tzinfo is not None
        # End should default to now


class TestExpandDateRangeForSearch:
    """Tests for expand_date_range_for_search function."""

    def test_default_buffer(self):
        """Test expansion with default 7-day buffer."""
        start = datetime(2024, 1, 15, tzinfo=UTC)
        end = datetime(2024, 1, 20, tzinfo=UTC)

        expanded_start, expanded_end = PriceDataService.expand_date_range_for_search(start, end)

        assert expanded_start == datetime(2024, 1, 8, tzinfo=UTC)  # 7 days before
        assert expanded_end == datetime(2024, 1, 27, tzinfo=UTC)  # 7 days after

    def test_custom_buffer(self):
        """Test expansion with custom buffer."""
        start = datetime(2024, 1, 15, tzinfo=UTC)
        end = datetime(2024, 1, 20, tzinfo=UTC)

        expanded_start, expanded_end = PriceDataService.expand_date_range_for_search(
            start, end, buffer_days=3
        )

        assert expanded_start == datetime(2024, 1, 12, tzinfo=UTC)  # 3 days before
        assert expanded_end == datetime(2024, 1, 23, tzinfo=UTC)  # 3 days after

    def test_zero_buffer(self):
        """Test with zero buffer (no expansion)."""
        start = datetime(2024, 1, 15, tzinfo=UTC)
        end = datetime(2024, 1, 20, tzinfo=UTC)

        expanded_start, expanded_end = PriceDataService.expand_date_range_for_search(
            start, end, buffer_days=0
        )

        assert expanded_start == start
        assert expanded_end == end


class TestFilterPricesToDateRange:
    """Tests for filter_prices_to_date_range function."""

    def test_filter_prices_within_range(self):
        """Test filtering prices within date range."""
        start = datetime(2024, 1, 5, tzinfo=UTC)
        end = datetime(2024, 1, 15, tzinfo=UTC)

        prices = [
            SecurityPrice(
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1000,
                interval_type="1d",
            ),
            SecurityPrice(
                timestamp=datetime(2024, 1, 10, tzinfo=UTC),
                open=102.0,
                high=103.0,
                low=101.0,
                close=102.5,
                volume=2000,
                interval_type="1d",
            ),
            SecurityPrice(
                timestamp=datetime(2024, 1, 20, tzinfo=UTC),
                open=105.0,
                high=106.0,
                low=104.0,
                close=105.5,
                volume=3000,
                interval_type="1d",
            ),
        ]

        filtered = PriceDataService.filter_prices_to_date_range(prices, start, end)

        # Only middle price should be in range
        assert len(filtered) == 1
        assert filtered[0].timestamp == datetime(2024, 1, 10, tzinfo=UTC)

    def test_filter_all_prices_in_range(self):
        """Test when all prices are within range."""
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 1, 31, tzinfo=UTC)

        prices = [
            SecurityPrice(
                timestamp=datetime(2024, 1, 5, tzinfo=UTC),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1000,
                interval_type="1d",
            ),
            SecurityPrice(
                timestamp=datetime(2024, 1, 15, tzinfo=UTC),
                open=102.0,
                high=103.0,
                low=101.0,
                close=102.5,
                volume=2000,
                interval_type="1d",
            ),
            SecurityPrice(
                timestamp=datetime(2024, 1, 25, tzinfo=UTC),
                open=105.0,
                high=106.0,
                low=104.0,
                close=105.5,
                volume=3000,
                interval_type="1d",
            ),
        ]

        filtered = PriceDataService.filter_prices_to_date_range(prices, start, end)

        assert len(filtered) == 3

    def test_filter_no_prices_in_range(self):
        """Test when no prices are within range."""
        start = datetime(2024, 6, 1, tzinfo=UTC)
        end = datetime(2024, 6, 30, tzinfo=UTC)

        prices = [
            SecurityPrice(
                timestamp=datetime(2024, 1, 5, tzinfo=UTC),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1000,
                interval_type="1d",
            ),
            SecurityPrice(
                timestamp=datetime(2024, 1, 15, tzinfo=UTC),
                open=102.0,
                high=103.0,
                low=101.0,
                close=102.5,
                volume=2000,
                interval_type="1d",
            ),
        ]

        filtered = PriceDataService.filter_prices_to_date_range(prices, start, end)

        assert len(filtered) == 0

    def test_filter_boundary_dates(self):
        """Test filtering with boundary dates (inclusive)."""
        start = datetime(2024, 1, 10, tzinfo=UTC)
        end = datetime(2024, 1, 10, tzinfo=UTC)  # Same day

        prices = [
            SecurityPrice(
                timestamp=datetime(2024, 1, 9, tzinfo=UTC),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1000,
                interval_type="1d",
            ),
            SecurityPrice(
                timestamp=datetime(2024, 1, 10, tzinfo=UTC),
                open=102.0,
                high=103.0,
                low=101.0,
                close=102.5,
                volume=2000,
                interval_type="1d",
            ),
            SecurityPrice(
                timestamp=datetime(2024, 1, 11, tzinfo=UTC),
                open=105.0,
                high=106.0,
                low=104.0,
                close=105.5,
                volume=3000,
                interval_type="1d",
            ),
        ]

        filtered = PriceDataService.filter_prices_to_date_range(prices, start, end)

        # Should include boundary date
        assert len(filtered) == 1
        assert filtered[0].timestamp == datetime(2024, 1, 10, tzinfo=UTC)


class TestCalculateExpectedDataPoints:
    """Tests for calculate_expected_data_points function."""

    def test_daily_interval_one_week(self):
        """Test daily interval for one week (trading days)."""
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 1, 8, tzinfo=UTC)  # 7 days

        expected = PriceDataService.calculate_expected_data_points(start, end, "1d")

        # 7 days * TRADING_DAYS_PER_WEEK / 7 = TRADING_DAYS_PER_WEEK trading days
        assert expected == TRADING_DAYS_PER_WEEK

    def test_daily_interval_30_days(self):
        """Test daily interval for 30 days (trading days)."""
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 1, 31, tzinfo=UTC)  # 30 days

        expected = PriceDataService.calculate_expected_data_points(start, end, "1d")

        # 30 days * TRADING_DAYS_PER_WEEK / 7 ≈ 21 trading days
        assert expected == 21

    def test_weekly_interval(self):
        """Test weekly interval."""
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 1, 29, tzinfo=UTC)  # 28 days = 4 weeks

        expected = PriceDataService.calculate_expected_data_points(start, end, "1wk")

        # 28 days / 7 = 4 weeks
        assert expected == 4

    def test_hourly_interval(self):
        """Test hourly interval (trading hours per day)."""
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 1, 3, tzinfo=UTC)  # 2 days

        expected = PriceDataService.calculate_expected_data_points(start, end, "1h")

        # 2 days * TRADING_HOURS_PER_DAY = 13 hours
        assert expected == int(2 * TRADING_HOURS_PER_DAY)

    def test_minute_interval(self):
        """Test minute interval (trading minutes per day)."""
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 1, 3, tzinfo=UTC)  # 2 days

        expected = PriceDataService.calculate_expected_data_points(start, end, "1m")

        # 2 days * TRADING_MINUTES_PER_DAY = 780 minutes
        assert expected == int(2 * TRADING_MINUTES_PER_DAY)

    def test_minimum_one_point(self):
        """Test that minimum is always 1 even for very short ranges."""
        start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        end = datetime(2024, 1, 1, 0, 1, tzinfo=UTC)  # 1 minute

        expected = PriceDataService.calculate_expected_data_points(start, end, "1d")

        # Should always return at least 1
        assert expected == 1


class TestCalculateDataCompleteness:
    """Tests for calculate_data_completeness function."""

    def test_complete_data(self):
        """Test when data is complete (>= COMPLETENESS_THRESHOLD_COMPLETE)."""
        result = PriceDataService.calculate_data_completeness(90, 100, True)
        assert result == "complete"

        # Exactly at threshold
        result = PriceDataService.calculate_data_completeness(
            int(100 * COMPLETENESS_THRESHOLD_COMPLETE), 100, True
        )
        assert result == "complete"

        result = PriceDataService.calculate_data_completeness(100, 100, True)
        assert result == "complete"

    def test_partial_data(self):
        """Test when data is partial (COMPLETENESS_THRESHOLD_PARTIAL to COMPLETENESS_THRESHOLD_COMPLETE)."""
        result = PriceDataService.calculate_data_completeness(50, 100, True)
        assert result == "partial"

        # Exactly at lower threshold
        result = PriceDataService.calculate_data_completeness(
            int(100 * COMPLETENESS_THRESHOLD_PARTIAL), 100, True
        )
        assert result == "partial"

        # Just below upper threshold
        result = PriceDataService.calculate_data_completeness(
            int(100 * COMPLETENESS_THRESHOLD_COMPLETE) - 1, 100, True
        )
        assert result == "partial"

    def test_sparse_data(self):
        """Test when data is sparse (< COMPLETENESS_THRESHOLD_PARTIAL)."""
        result = PriceDataService.calculate_data_completeness(10, 100, True)
        assert result == "sparse"

        # Just below partial threshold
        result = PriceDataService.calculate_data_completeness(
            int(100 * COMPLETENESS_THRESHOLD_PARTIAL) - 1, 100, True
        )
        assert result == "sparse"

        result = PriceDataService.calculate_data_completeness(1, 100, True)
        assert result == "sparse"

    def test_no_data_in_range(self):
        """Test when data exists but outside requested range."""
        result = PriceDataService.calculate_data_completeness(0, 100, False)
        assert result == "partial"

        # Even with data points, if not in range, should be partial
        result = PriceDataService.calculate_data_completeness(50, 100, False)
        assert result == "partial"

    def test_zero_expected_points(self):
        """Test when expected points is zero."""
        result = PriceDataService.calculate_data_completeness(10, 0, True)
        assert result == "complete"

    def test_edge_case_thresholds(self):
        """Test edge cases at threshold boundaries using constants."""
        # Exactly at COMPLETENESS_THRESHOLD_COMPLETE
        result = PriceDataService.calculate_data_completeness(
            int(100 * COMPLETENESS_THRESHOLD_COMPLETE), 100, True
        )
        assert result == "complete"

        # Just below COMPLETENESS_THRESHOLD_COMPLETE
        result = PriceDataService.calculate_data_completeness(
            int(100 * COMPLETENESS_THRESHOLD_COMPLETE) - 1, 100, True
        )
        assert result == "partial"

        # Exactly at COMPLETENESS_THRESHOLD_PARTIAL
        result = PriceDataService.calculate_data_completeness(
            int(100 * COMPLETENESS_THRESHOLD_PARTIAL), 100, True
        )
        assert result == "partial"

        # Just below COMPLETENESS_THRESHOLD_PARTIAL
        result = PriceDataService.calculate_data_completeness(
            int(100 * COMPLETENESS_THRESHOLD_PARTIAL) - 1, 100, True
        )
        assert result == "sparse"
