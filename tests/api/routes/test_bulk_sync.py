"""Tests for bulk sync endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient

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

        # Batch size must be <= 100 (updated from 50)
        response = await client.post(
            "/api/v1/securities/bulk-sync?batch_size=101",
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

        # Batch delay must be <= 10 (updated from 5)
        response = await client.post(
            "/api/v1/securities/bulk-sync?batch_delay=11",
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_bulk_sync_returns_immediately(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        """Test that bulk sync returns immediately with job started confirmation."""
        # Mock get_tickers to return just one ticker for testing
        with patch("app.api.routes.securities.get_tickers", new_callable=AsyncMock) as mock_get_tickers:
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
    async def test_bulk_sync_with_multiple_securities(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        """Test bulk sync returns correct count for multiple securities."""
        # Mock get_tickers to return multiple tickers
        with patch("app.api.routes.securities.get_tickers", new_callable=AsyncMock) as mock_get_tickers:
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
    async def test_bulk_sync_with_custom_parameters(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        """Test bulk sync accepts custom batch_size and batch_delay parameters."""
        with patch("app.api.routes.securities.get_tickers", new_callable=AsyncMock) as mock_get_tickers:
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
        with patch("app.api.routes.securities.get_tickers", new_callable=AsyncMock) as mock_tickers:
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

    @pytest.mark.asyncio
    async def test_bulk_sync_with_large_ticker_count(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        """Test bulk sync handles large ticker counts (6000+)."""
        # Mock get_tickers to return a large list (simulating real exchanges)
        with patch("app.api.routes.securities.get_tickers", new_callable=AsyncMock) as mock_get_tickers:
            # Create a list of 6000+ mock tickers
            large_ticker_list = [f"TICKER{i}" for i in range(6500)]
            mock_get_tickers.return_value = large_ticker_list

            response = await client.post(
                "/api/v1/securities/bulk-sync?batch_delay=0",
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should handle large count correctly
        assert data["message"] == "Bulk sync job started"
        assert data["total_securities"] == 6500
        assert data["status"] == "running"


@pytest.mark.unit
class TestMarketTickersModule:
    """Tests for market_tickers module - now using dynamic fetching."""

    @pytest.mark.asyncio
    async def test_get_tickers_returns_combined_exchanges(self):
        """Test getting all stock tickers from all exchanges."""
        # Mock the exchange service to return known tickers
        with patch("app.data.market_tickers.fetch_all_exchange_tickers", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {
                "NASDAQ": ["AAPL", "MSFT", "GOOGL"],
                "NYSE": ["JPM", "BAC", "WFC"],
                "TSX": ["RY.TO", "TD.TO", "ENB.TO"],
            }

            from app.data.market_tickers import get_tickers

            tickers = await get_tickers()

        # Should combine all exchanges
        assert len(tickers) == 9
        assert "AAPL" in tickers
        assert "MSFT" in tickers
        assert "JPM" in tickers
        assert "RY.TO" in tickers

    @pytest.mark.asyncio
    async def test_get_tickers_includes_nasdaq_stocks(self):
        """Test that NASDAQ stocks are included."""
        with patch("app.data.market_tickers.fetch_all_exchange_tickers", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {
                "NASDAQ": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"],
                "NYSE": ["JPM"],
                "TSX": ["RY.TO"],
            }

            from app.data.market_tickers import get_tickers

            tickers = await get_tickers()

        # Verify NASDAQ stocks are included
        assert "AAPL" in tickers
        assert "MSFT" in tickers
        assert "GOOGL" in tickers
        assert "AMZN" in tickers
        assert "NVDA" in tickers

    @pytest.mark.asyncio
    async def test_get_tickers_includes_nyse_stocks(self):
        """Test that NYSE stocks are included."""
        with patch("app.data.market_tickers.fetch_all_exchange_tickers", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {
                "NASDAQ": ["AAPL"],
                "NYSE": ["JPM", "V", "WMT", "BAC", "WFC"],
                "TSX": ["RY.TO"],
            }

            from app.data.market_tickers import get_tickers

            tickers = await get_tickers()

        # Verify NYSE stocks are included
        assert "JPM" in tickers
        assert "V" in tickers
        assert "WMT" in tickers
        assert "BAC" in tickers
        assert "WFC" in tickers

    @pytest.mark.asyncio
    async def test_get_tickers_includes_tsx_stocks(self):
        """Test that TSX stocks are included."""
        with patch("app.data.market_tickers.fetch_all_exchange_tickers", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {
                "NASDAQ": ["AAPL"],
                "NYSE": ["JPM"],
                "TSX": ["RY.TO", "TD.TO", "ENB.TO", "SHOP.TO", "CNR.TO"],
            }

            from app.data.market_tickers import get_tickers

            tickers = await get_tickers()

        # Verify TSX stocks are included
        assert "RY.TO" in tickers
        assert "TD.TO" in tickers
        assert "ENB.TO" in tickers
        assert "SHOP.TO" in tickers
        assert "CNR.TO" in tickers

    @pytest.mark.asyncio
    async def test_get_tickers_combines_all_exchanges(self):
        """Test that get_tickers combines all exchange lists correctly."""
        with patch("app.data.market_tickers.fetch_all_exchange_tickers", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {
                "NASDAQ": ["AAPL", "MSFT"],  # 2 tickers
                "NYSE": ["JPM", "BAC", "WFC"],  # 3 tickers
                "TSX": ["RY.TO", "TD.TO"],  # 2 tickers
            }

            from app.data.market_tickers import get_tickers

            tickers = await get_tickers()

        # Should have 7 total tickers
        assert len(tickers) == 7

    @pytest.mark.asyncio
    async def test_get_tickers_handles_empty_exchanges(self):
        """Test that get_tickers handles exchanges with no tickers gracefully."""
        with patch("app.data.market_tickers.fetch_all_exchange_tickers", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {
                "NASDAQ": ["AAPL", "MSFT"],
                "NYSE": [],  # Empty exchange
                "TSX": ["RY.TO"],
            }

            from app.data.market_tickers import get_tickers

            tickers = await get_tickers()

        # Should still work with empty exchanges
        assert len(tickers) == 3
        assert "AAPL" in tickers
        assert "MSFT" in tickers
        assert "RY.TO" in tickers

    @pytest.mark.asyncio
    async def test_get_tickers_realistic_scale(self):
        """Test that get_tickers can handle realistic scale (6000+ tickers)."""
        with patch("app.data.market_tickers.fetch_all_exchange_tickers", new_callable=AsyncMock) as mock_fetch:
            # Simulate realistic ticker counts
            nasdaq_tickers = [f"NDAQ{i}" for i in range(2500)]
            nyse_tickers = [f"NYSE{i}" for i in range(1800)]
            tsx_tickers = [f"TSX{i}.TO" for i in range(250)]

            mock_fetch.return_value = {
                "NASDAQ": nasdaq_tickers,
                "NYSE": nyse_tickers,
                "TSX": tsx_tickers,
            }

            from app.data.market_tickers import get_tickers

            tickers = await get_tickers()

        # Should handle large scale
        assert len(tickers) == 4550  # 2500 + 1800 + 250
        assert len([t for t in tickers if t.startswith("NDAQ")]) == 2500
        assert len([t for t in tickers if t.startswith("NYSE")]) == 1800
        assert len([t for t in tickers if t.endswith(".TO")]) == 250
