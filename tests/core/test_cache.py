"""Tests for cache configuration."""

from unittest.mock import Mock, patch

from app.core.cache import (
    CACHE_EXPIRATION,
    clear_yfinance_cache,
    configure_yfinance_cache,
    get_cache_stats,
    get_redis_connection,
)


class TestRedisConnection:
    """Tests for Redis connection management."""

    @patch("app.core.cache.Redis")
    def test_get_redis_connection_success(self, mock_redis):
        """Test successful Redis connection."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.from_url.return_value = mock_client

        conn = get_redis_connection()

        assert conn is not None
        mock_client.ping.assert_called_once()

    @patch("app.core.cache.Redis")
    def test_get_redis_connection_failure(self, mock_redis):
        """Test Redis connection failure handling."""
        from redis.exceptions import ConnectionError

        mock_redis.from_url.side_effect = ConnectionError("Connection refused")

        conn = get_redis_connection()

        assert conn is None

    @patch("app.core.cache.Redis")
    def test_get_redis_connection_timeout(self, mock_redis):
        """Test Redis connection timeout handling."""
        from redis.exceptions import TimeoutError

        mock_redis.from_url.side_effect = TimeoutError("Connection timeout")

        conn = get_redis_connection()

        assert conn is None


class TestCacheConfiguration:
    """Tests for cache configuration."""

    @patch("app.core.cache.get_redis_connection")
    @patch("app.core.cache.requests_cache.install_cache")
    def test_configure_yfinance_cache_success(self, mock_install, mock_redis_conn):
        """Test successful cache configuration."""
        mock_redis_conn.return_value = Mock()

        configure_yfinance_cache()

        mock_install.assert_called_once()
        call_kwargs = mock_install.call_args.kwargs
        assert "backend" in call_kwargs
        assert "urls_expire_after" in call_kwargs
        assert call_kwargs["allowable_methods"] == ("GET", "POST")
        assert call_kwargs["stale_if_error"] is True

    @patch("app.core.cache.get_redis_connection")
    def test_configure_yfinance_cache_redis_unavailable(self, mock_redis_conn):
        """Test cache configuration when Redis is unavailable."""
        mock_redis_conn.return_value = None

        # Should not raise an exception
        configure_yfinance_cache()

    @patch("app.core.cache.get_redis_connection")
    @patch("app.core.cache.requests_cache.install_cache")
    def test_configure_yfinance_cache_expiration_patterns(self, mock_install, mock_redis_conn):
        """Test that cache expiration patterns are configured correctly."""
        mock_redis_conn.return_value = Mock()

        configure_yfinance_cache()

        call_kwargs = mock_install.call_args.kwargs
        urls_expire_after = call_kwargs["urls_expire_after"]

        # Check that different intervals have different expiration times
        assert "*/v8/finance/chart/*interval=1d*" in urls_expire_after
        assert "*/v8/finance/chart/*interval=1m*" in urls_expire_after
        assert "*/v10/finance/quoteSummary/*" in urls_expire_after

        # Verify expiration times
        assert (
            urls_expire_after["*/v8/finance/chart/*interval=1d*"] == CACHE_EXPIRATION["daily_data"]
        )
        assert (
            urls_expire_after["*/v8/finance/chart/*interval=1m*"]
            == CACHE_EXPIRATION["intraday_data"]
        )


class TestCacheOperations:
    """Tests for cache operations."""

    @patch("app.core.cache.requests_cache.get_cache")
    def test_clear_yfinance_cache_success(self, mock_get_cache):
        """Test clearing cache successfully."""
        mock_cache = Mock()
        mock_get_cache.return_value = mock_cache

        clear_yfinance_cache()

        mock_cache.clear.assert_called_once()

    @patch("app.core.cache.requests_cache.get_cache")
    def test_clear_yfinance_cache_no_active_cache(self, mock_get_cache):
        """Test clearing cache when no cache is active."""
        mock_get_cache.return_value = None

        # Should not raise an exception
        clear_yfinance_cache()

    @patch("app.core.cache.requests_cache.get_cache")
    def test_get_cache_stats_enabled(self, mock_get_cache):
        """Test getting cache stats when cache is enabled."""
        mock_cache = Mock()
        mock_cache.responses = {"key1": "value1", "key2": "value2"}
        mock_get_cache.return_value = mock_cache

        stats = get_cache_stats()

        assert stats["enabled"] is True
        assert "backend" in stats
        assert stats["size"] == 2

    @patch("app.core.cache.requests_cache.get_cache")
    def test_get_cache_stats_disabled(self, mock_get_cache):
        """Test getting cache stats when cache is disabled."""
        mock_get_cache.return_value = None

        stats = get_cache_stats()

        assert stats["enabled"] is False

    @patch("app.core.cache.requests_cache.get_cache")
    def test_get_cache_stats_size_unavailable(self, mock_get_cache):
        """Test getting cache stats when size is unavailable."""
        mock_cache = Mock()
        # Simulate size being unavailable
        type(mock_cache).responses = property(lambda self: (_ for _ in ()).throw(Exception()))
        mock_get_cache.return_value = mock_cache

        stats = get_cache_stats()

        assert stats["enabled"] is True
        assert stats["size"] == "unavailable"


class TestCacheExpiration:
    """Tests for cache expiration settings."""

    def test_cache_expiration_constants(self):
        """Test that cache expiration constants are properly defined."""
        assert "daily_data" in CACHE_EXPIRATION
        assert "intraday_data" in CACHE_EXPIRATION
        assert "security_info" in CACHE_EXPIRATION
        assert "default" in CACHE_EXPIRATION

        # Daily data should have longer expiration than intraday
        assert CACHE_EXPIRATION["daily_data"] > CACHE_EXPIRATION["intraday_data"]

        # Security info should have moderate expiration
        assert (
            CACHE_EXPIRATION["intraday_data"]
            < CACHE_EXPIRATION["security_info"]
            < CACHE_EXPIRATION["daily_data"]
        )
