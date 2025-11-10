"""Tests for bulk sync endpoint."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient

from app.data.market_tickers import NASDAQ_STOCKS

# Note: These tests verify that the endpoint returns immediately after starting
# the background job. The actual sync logic is tested indirectly through the
# _sync_single_security helper function which is used by the background task.


@pytest.mark.integration
class TestBulkSyncEndpoint:
    """Tests for POST /api/v1/securities/bulk-sync endpoint."""

    @pytest.mark.asyncio
    async def test_bulk_sync_requires_authentication(self, client: AsyncClient):
        """Test that bulk sync requires authentication."""
        response = await client.post("/api/v1/securities/bulk-sync")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_bulk_sync_batch_size_validation(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Test bulk sync batch_size parameter validation."""
        # Batch size must be >= 1
        response = await client.post(
            "/api/v1/securities/bulk-sync?batch_size=0",
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Batch size must be <= 50
        response = await client.post(
            "/api/v1/securities/bulk-sync?batch_size=51",
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_bulk_sync_batch_delay_validation(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Test bulk sync batch_delay parameter validation."""
        # Batch delay must be >= 0
        response = await client.post(
            "/api/v1/securities/bulk-sync?batch_delay=-1",
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Batch delay must be <= 5
        response = await client.post(
            "/api/v1/securities/bulk-sync?batch_delay=6",
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    @patch("app.api.routes.securities.get_tickers")
    async def test_bulk_sync_returns_immediately(
        self,
        mock_get_tickers: MagicMock,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        """Test that bulk sync returns immediately with job started confirmation."""
        # Mock get_tickers to return just one ticker for testing
        mock_get_tickers.return_value = ["AAPL"]

        # Call endpoint
        response = await client.post(
            "/api/v1/securities/bulk-sync?batch_delay=0",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK

        data = response.json()

        # Check immediate response structure
        assert "message" in data
        assert data["message"] == "Bulk sync job started"
        assert "total_securities" in data
        assert data["total_securities"] == 1
        assert "status" in data
        assert data["status"] == "running"

        # Should NOT have detailed results (those are logged in background)
        assert "results" not in data
        assert "successfully_added" not in data
        assert "failed_additions" not in data

    @pytest.mark.asyncio
    @patch("app.api.routes.securities.get_tickers")
    async def test_bulk_sync_with_multiple_securities(
        self,
        mock_get_tickers: MagicMock,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        """Test bulk sync returns correct count for multiple securities."""
        # Mock get_tickers to return multiple tickers
        mock_get_tickers.return_value = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

        response = await client.post(
            "/api/v1/securities/bulk-sync?batch_delay=0",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should return immediately with correct count
        assert data["message"] == "Bulk sync job started"
        assert data["total_securities"] == 5
        assert data["status"] == "running"

    @pytest.mark.asyncio
    @patch("app.api.routes.securities.get_tickers")
    async def test_bulk_sync_with_custom_parameters(
        self,
        mock_get_tickers: MagicMock,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        """Test bulk sync accepts custom batch_size and batch_delay parameters."""
        mock_get_tickers.return_value = ["AAPL", "MSFT", "GOOGL"]

        # Test with custom parameters
        response = await client.post(
            "/api/v1/securities/bulk-sync?batch_size=2&batch_delay=1.0",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should still return immediately
        assert data["message"] == "Bulk sync job started"
        assert data["total_securities"] == 3
        assert data["status"] == "running"

    @pytest.mark.asyncio
    async def test_bulk_sync_response_structure(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Test bulk sync response has correct structure."""
        with patch("app.api.routes.securities.get_tickers") as mock_tickers:
            # Mock get_tickers to return just one ticker
            mock_tickers.return_value = ["AAPL"]

            response = await client.post(
                "/api/v1/securities/bulk-sync?batch_delay=0",
                headers=auth_headers,
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Check response structure matches BulkSyncStartResponse schema
            assert "message" in data
            assert isinstance(data["message"], str)
            assert "total_securities" in data
            assert isinstance(data["total_securities"], int)
            assert "status" in data
            assert data["status"] == "running"

            # Ensure old response fields are NOT present
            assert "total_requested" not in data
            assert "successfully_added" not in data
            assert "failed_additions" not in data
            assert "successfully_synced" not in data
            assert "failed_syncs" not in data
            assert "skipped" not in data
            assert "results" not in data


@pytest.mark.unit
class TestMarketTickersModule:
    """Tests for market_tickers module."""

    def test_get_tickers_returns_all_stocks(self):
        """Test getting all stock tickers."""
        from app.data.market_tickers import ALL_STOCKS, get_tickers

        tickers = get_tickers()
        assert len(tickers) > 0
        assert tickers == ALL_STOCKS

    def test_get_tickers_includes_nasdaq_stocks(self):
        """Test that NASDAQ stocks are included."""
        from app.data.market_tickers import get_tickers

        tickers = get_tickers()
        assert "AAPL" in tickers
        assert "MSFT" in tickers
        assert "GOOGL" in tickers
        # Verify all NASDAQ stocks are in the result
        for stock in NASDAQ_STOCKS:
            assert stock in tickers

    def test_get_tickers_includes_nyse_stocks(self):
        """Test that NYSE stocks are included."""
        from app.data.market_tickers import NYSE_STOCKS, get_tickers

        tickers = get_tickers()
        assert "JPM" in tickers
        assert "V" in tickers
        assert "WMT" in tickers
        # Verify all NYSE stocks are in the result
        for stock in NYSE_STOCKS:
            assert stock in tickers

    def test_get_tickers_includes_tsx_stocks(self):
        """Test that TSX stocks are included."""
        from app.data.market_tickers import TSX_STOCKS, get_tickers

        tickers = get_tickers()
        assert "RY.TO" in tickers
        assert "TD.TO" in tickers
        assert "ENB.TO" in tickers
        # Verify all TSX stocks are in the result
        for stock in TSX_STOCKS:
            assert stock in tickers

    def test_all_stocks_combined_correctly(self):
        """Test that ALL_STOCKS combines all exchange lists."""
        from app.data.market_tickers import (
            ALL_STOCKS,
            NYSE_STOCKS,
            TSX_STOCKS,
        )

        expected_count = len(NASDAQ_STOCKS) + len(NYSE_STOCKS) + len(TSX_STOCKS)
        assert len(ALL_STOCKS) == expected_count

    def test_no_indices_or_etfs_included(self):
        """Test that indices and ETFs are not included."""
        from app.data.market_tickers import get_tickers

        tickers = get_tickers()
        # Indices start with ^
        assert not any(ticker.startswith("^") for ticker in tickers)
        # Common ETF symbols that should not be present
        etfs = ["SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "XIU.TO", "XIC.TO"]
        for etf in etfs:
            assert etf not in tickers
