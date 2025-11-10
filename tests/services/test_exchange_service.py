"""Tests for exchange service ticker fetching functionality.

These tests verify dynamic fetching of securities from NASDAQ, NYSE, and TSX exchanges.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.exchange_service import (
    clear_cache,
    fetch_all_exchange_tickers,
    fetch_nasdaq_tickers,
    fetch_nyse_tickers,
    fetch_tsx_tickers,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_nasdaq_tickers_real():
    """Test fetching real NASDAQ tickers from FTP source.

    This is an integration test that actually hits the NASDAQ FTP server.
    Marked as integration to be skipped in fast test runs.
    """
    tickers = await fetch_nasdaq_tickers()

    # Verify we got a reasonable number of tickers
    assert len(tickers) > 2000, "Expected at least 2000 NASDAQ tickers"

    # Verify format (all strings, uppercase)
    assert all(isinstance(t, str) for t in tickers)
    assert all(t.isupper() for t in tickers)

    # Verify some known tickers are present
    known_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
    for ticker in known_tickers:
        assert ticker in tickers, f"Expected {ticker} to be in NASDAQ list"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_nyse_tickers_real():
    """Test fetching real NYSE tickers from FTP source.

    This is an integration test that actually hits the NASDAQ FTP server.
    """
    tickers = await fetch_nyse_tickers()

    # Verify we got a reasonable number of tickers
    assert len(tickers) > 1500, "Expected at least 1500 NYSE tickers"

    # Verify format
    assert all(isinstance(t, str) for t in tickers)

    # Verify some known tickers are present
    known_tickers = ["JPM", "BAC", "WFC", "V", "MA"]
    for ticker in known_tickers:
        assert ticker in tickers, f"Expected {ticker} to be in NYSE list"


@pytest.mark.asyncio
async def test_fetch_tsx_tickers():
    """Test fetching TSX tickers (curated list)."""
    tickers = await fetch_tsx_tickers()

    # Verify we got expected number of tickers
    assert len(tickers) > 150, "Expected at least 150 TSX tickers"

    # Verify all have .TO suffix
    assert all(t.endswith(".TO") for t in tickers)

    # Verify some known Canadian stocks
    known_tickers = ["RY.TO", "TD.TO", "ENB.TO", "SHOP.TO", "CNR.TO"]
    for ticker in known_tickers:
        assert ticker in tickers, f"Expected {ticker} to be in TSX list"


@pytest.mark.asyncio
async def test_fetch_nasdaq_tickers_with_mock():
    """Test NASDAQ fetching with mocked HTTP response."""
    mock_csv_data = """Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares
AAPL|Apple Inc. Common Stock|Q|N|N|100|N|N
MSFT|Microsoft Corporation Common Stock|Q|N|N|100|N|N
TESTISSUE|Test Issue Company|Q|Y|N|100|N|N
ETFTEST|Test ETF|Q|N|N|100|Y|N
File Creation Time: 1234567890|"""

    mock_response = MagicMock()
    mock_response.text = mock_csv_data
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("app.services.exchange_service.httpx.AsyncClient", return_value=mock_client):
        tickers = await fetch_nasdaq_tickers()

    # Should only include AAPL and MSFT (not test issue or ETF)
    assert len(tickers) == 2
    assert "AAPL" in tickers
    assert "MSFT" in tickers
    assert "TESTISSUE" not in tickers  # Test issue excluded
    assert "ETFTEST" not in tickers  # ETF excluded


@pytest.mark.asyncio
async def test_fetch_nyse_tickers_with_mock():
    """Test NYSE fetching with mocked HTTP response."""
    mock_csv_data = """ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol
JPM|JPMorgan Chase & Co. Common Stock|N|JPM|N|100|N|JPM
BAC|Bank of America Corporation Common Stock|N|BAC|N|100|N|BAC
TESTISSUE|Test Issue Company|N|TEST|N|100|Y|TEST
ETFTEST|Test ETF|N|ETF|Y|100|N|ETF
AMEX|American Stock Exchange Stock|A|AMEX|N|100|N|AMEX
File Creation Time: 1234567890|"""

    mock_response = MagicMock()
    mock_response.text = mock_csv_data
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("app.services.exchange_service.httpx.AsyncClient", return_value=mock_client):
        tickers = await fetch_nyse_tickers()

    # Should only include JPM and BAC (NYSE only, no test issues, no ETFs)
    assert len(tickers) == 2
    assert "JPM" in tickers
    assert "BAC" in tickers
    assert "TESTISSUE" not in tickers  # Test issue excluded
    assert "ETFTEST" not in tickers  # ETF excluded
    assert "AMEX" not in tickers  # Not NYSE exchange


@pytest.mark.asyncio
async def test_fetch_nasdaq_tickers_http_error():
    """Test NASDAQ fetching handles HTTP errors gracefully."""
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(side_effect=Exception("Network error"))

    with patch("app.services.exchange_service.httpx.AsyncClient", return_value=mock_client):
        tickers = await fetch_nasdaq_tickers()

    # Should return empty list on error
    assert tickers == []


@pytest.mark.asyncio
async def test_fetch_nyse_tickers_parse_error():
    """Test NYSE fetching handles parse errors gracefully."""
    mock_response = MagicMock()
    mock_response.text = "Invalid CSV data without proper headers"
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("app.services.exchange_service.httpx.AsyncClient", return_value=mock_client):
        tickers = await fetch_nyse_tickers()

    # Should return empty list on parse error
    assert tickers == []


@pytest.mark.asyncio
async def test_fetch_all_exchange_tickers_with_mock():
    """Test fetching all exchanges with mocked functions."""
    # Clear cache first
    await clear_cache()

    with (
        patch(
            "app.services.exchange_service.fetch_nasdaq_tickers", new_callable=AsyncMock
        ) as mock_nasdaq,
        patch(
            "app.services.exchange_service.fetch_nyse_tickers", new_callable=AsyncMock
        ) as mock_nyse,
        patch(
            "app.services.exchange_service.fetch_tsx_tickers", new_callable=AsyncMock
        ) as mock_tsx,
    ):
        mock_nasdaq.return_value = ["AAPL", "MSFT", "GOOGL"]
        mock_nyse.return_value = ["JPM", "BAC", "WFC"]
        mock_tsx.return_value = ["RY.TO", "TD.TO", "ENB.TO"]

        result = await fetch_all_exchange_tickers()

    # Verify structure
    assert "NASDAQ" in result
    assert "NYSE" in result
    assert "TSX" in result

    # Verify content
    assert result["NASDAQ"] == ["AAPL", "MSFT", "GOOGL"]
    assert result["NYSE"] == ["JPM", "BAC", "WFC"]
    assert result["TSX"] == ["RY.TO", "TD.TO", "ENB.TO"]

    # Verify all fetchers were called
    mock_nasdaq.assert_called_once()
    mock_nyse.assert_called_once()
    mock_tsx.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_all_exchange_tickers_partial_exchanges():
    """Test fetching only specific exchanges."""
    # Clear cache first
    await clear_cache()

    with (
        patch(
            "app.services.exchange_service.fetch_nasdaq_tickers", new_callable=AsyncMock
        ) as mock_nasdaq,
        patch(
            "app.services.exchange_service.fetch_nyse_tickers", new_callable=AsyncMock
        ) as mock_nyse,
        patch(
            "app.services.exchange_service.fetch_tsx_tickers", new_callable=AsyncMock
        ) as mock_tsx,
    ):
        mock_nasdaq.return_value = ["AAPL", "MSFT"]
        mock_nyse.return_value = ["JPM", "BAC"]

        # Only request NASDAQ and NYSE
        result = await fetch_all_exchange_tickers(exchanges=("NASDAQ", "NYSE"))

    # Should only have NASDAQ and NYSE
    assert "NASDAQ" in result
    assert "NYSE" in result
    assert "TSX" not in result

    # TSX fetcher should not be called
    mock_tsx.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_all_exchange_tickers_caching():
    """Test that caching works correctly."""
    # Clear cache first
    await clear_cache()

    with (
        patch(
            "app.services.exchange_service.fetch_nasdaq_tickers", new_callable=AsyncMock
        ) as mock_nasdaq,
        patch(
            "app.services.exchange_service.fetch_nyse_tickers", new_callable=AsyncMock
        ) as mock_nyse,
        patch(
            "app.services.exchange_service.fetch_tsx_tickers", new_callable=AsyncMock
        ) as mock_tsx,
    ):
        mock_nasdaq.return_value = ["AAPL", "MSFT"]
        mock_nyse.return_value = ["JPM", "BAC"]
        mock_tsx.return_value = ["RY.TO", "TD.TO"]

        # First call - should fetch
        result1 = await fetch_all_exchange_tickers()

        # Second call - should use cache
        result2 = await fetch_all_exchange_tickers()

    # Results should be identical
    assert result1 == result2

    # Fetchers should only be called once (cached on second call)
    assert mock_nasdaq.call_count == 1
    assert mock_nyse.call_count == 1
    assert mock_tsx.call_count == 1


@pytest.mark.asyncio
async def test_clear_cache():
    """Test cache clearing functionality."""
    # Clear cache first to ensure clean state
    await clear_cache()

    # Populate cache
    with (
        patch(
            "app.services.exchange_service.fetch_nasdaq_tickers", new_callable=AsyncMock
        ) as mock_nasdaq,
        patch(
            "app.services.exchange_service.fetch_nyse_tickers", new_callable=AsyncMock
        ) as mock_nyse,
        patch(
            "app.services.exchange_service.fetch_tsx_tickers", new_callable=AsyncMock
        ) as mock_tsx,
    ):
        mock_nasdaq.return_value = ["AAPL"]
        mock_nyse.return_value = ["JPM"]
        mock_tsx.return_value = ["RY.TO"]

        # First call - populates cache
        await fetch_all_exchange_tickers()

        # Clear cache
        await clear_cache()

        # Second call - should fetch again
        await fetch_all_exchange_tickers()

    # Fetchers should be called twice (once before clear, once after)
    assert mock_nasdaq.call_count == 2
    assert mock_nyse.call_count == 2
    assert mock_tsx.call_count == 2


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.slow
async def test_fetch_all_exchange_tickers_real():
    """Test fetching all exchanges from real sources.

    This is a slow integration test that actually fetches from FTP servers.
    Only run manually or in comprehensive test suites.
    """
    # Clear cache to ensure fresh fetch
    await clear_cache()

    result = await fetch_all_exchange_tickers()

    # Verify all exchanges present
    assert "NASDAQ" in result
    assert "NYSE" in result
    assert "TSX" in result

    # Verify reasonable counts
    assert len(result["NASDAQ"]) > 2000, "Expected at least 2000 NASDAQ tickers"
    assert len(result["NYSE"]) > 1500, "Expected at least 1500 NYSE tickers"
    assert len(result["TSX"]) > 200, "Expected at least 200 TSX tickers"

    # Verify total is substantial (6000+)
    total = sum(len(tickers) for tickers in result.values())
    assert total > 6000, f"Expected at least 6000 total tickers, got {total}"

    # Verify some known tickers are present
    assert "AAPL" in result["NASDAQ"]
    assert "MSFT" in result["NASDAQ"]
    assert "JPM" in result["NYSE"]
    assert "BAC" in result["NYSE"]
    assert "RY.TO" in result["TSX"]
    assert "TD.TO" in result["TSX"]
