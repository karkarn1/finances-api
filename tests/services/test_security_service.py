"""Tests for security service functions."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security import Security
from app.services import security_service
from app.services.yfinance_service import APIError, InvalidSymbolError


@pytest.mark.integration
async def test_get_or_create_security_creates_new(test_db: AsyncSession, mocker) -> None:
    """Test creating a new security with price sync."""
    # Mock yfinance calls
    mock_info = {
        "longName": "Apple Inc.",
        "currency": "USD",
        "exchange": "NASDAQ",
        "quoteType": "EQUITY",
    }
    mocker.patch(
        "app.services.security_service.fetch_security_info",
        return_value=mock_info,
    )
    mocker.patch(
        "app.services.security_service.fetch_historical_prices",
        return_value=None,  # Empty dataframe means no prices
    )
    mocker.patch(
        "app.services.security_service.parse_yfinance_data",
        return_value=[],  # No price data
    )

    security = await security_service.get_or_create_security(
        test_db,
        "AAPL",
        sync_prices=True,
        sync_daily=True,
        sync_intraday=False,
    )

    assert security.symbol == "AAPL"
    assert security.name == "Apple Inc."
    assert security.currency == "USD"
    assert security.exchange == "NASDAQ"
    assert security.security_type == "EQUITY"


@pytest.mark.integration
async def test_get_or_create_security_returns_existing(
    test_db: AsyncSession, test_security: Security
) -> None:
    """Test returning existing security without recreation."""
    # test_security should already exist in db
    security = await security_service.get_or_create_security(
        test_db,
        test_security.symbol,
        sync_prices=False,
    )

    assert security.id == test_security.id
    assert security.symbol == test_security.symbol


@pytest.mark.integration
async def test_get_or_create_security_no_sync(test_db: AsyncSession, mocker) -> None:
    """Test creating security without price sync."""
    mock_info = {
        "longName": "Test Corp",
        "currency": "USD",
        "quoteType": "EQUITY",
    }
    mocker.patch(
        "app.services.security_service.fetch_security_info",
        return_value=mock_info,
    )
    mock_fetch_prices = mocker.patch("app.services.security_service.fetch_historical_prices")

    security = await security_service.get_or_create_security(
        test_db,
        "TEST",
        sync_prices=False,
    )

    assert security.symbol == "TEST"
    # Verify fetch_historical_prices was NOT called
    mock_fetch_prices.assert_not_called()


@pytest.mark.integration
async def test_get_or_create_security_handles_sync_failure(test_db: AsyncSession, mocker) -> None:
    """Test that sync failures don't prevent security creation."""
    mock_info = {
        "longName": "Test Corp",
        "currency": "USD",
        "quoteType": "EQUITY",
    }
    mocker.patch(
        "app.services.security_service.fetch_security_info",
        return_value=mock_info,
    )
    # Mock price fetching to raise an error
    mocker.patch(
        "app.services.security_service.fetch_historical_prices",
        side_effect=APIError("API failed"),
    )

    # Should not raise, just log warning
    security = await security_service.get_or_create_security(
        test_db,
        "TEST",
        sync_prices=True,
        sync_daily=True,
    )

    assert security.symbol == "TEST"
    assert security.name == "Test Corp"


@pytest.mark.integration
async def test_get_or_create_security_invalid_symbol(test_db: AsyncSession, mocker) -> None:
    """Test handling of invalid symbol."""
    mocker.patch(
        "app.services.security_service.fetch_security_info",
        side_effect=InvalidSymbolError("Symbol not found"),
    )

    with pytest.raises(InvalidSymbolError) as exc_info:
        await security_service.get_or_create_security(
            test_db,
            "INVALID",
            sync_prices=False,
        )

    assert "Symbol not found" in str(exc_info.value)


@pytest.mark.integration
async def test_get_or_create_security_api_error(test_db: AsyncSession, mocker) -> None:
    """Test handling of API errors."""
    mocker.patch(
        "app.services.security_service.fetch_security_info",
        side_effect=APIError("API error occurred"),
    )

    with pytest.raises(APIError) as exc_info:
        await security_service.get_or_create_security(
            test_db,
            "AAPL",
            sync_prices=False,
        )

    assert "API error occurred" in str(exc_info.value)


@pytest.mark.integration
async def test_get_or_create_security_with_only_daily_sync(test_db: AsyncSession, mocker) -> None:
    """Test creating security with only daily price sync."""
    mock_info = {
        "longName": "Microsoft Corporation",
        "shortName": "Microsoft",
        "currency": "USD",
        "exchange": "NASDAQ",
        "quoteType": "EQUITY",
    }
    mocker.patch(
        "app.services.security_service.fetch_security_info",
        return_value=mock_info,
    )
    mock_fetch_daily = mocker.patch(
        "app.services.security_service.fetch_historical_prices",
        return_value=None,
    )
    mocker.patch(
        "app.services.security_service.parse_yfinance_data",
        return_value=[],
    )

    security = await security_service.get_or_create_security(
        test_db,
        "MSFT",
        sync_prices=True,
        sync_daily=True,
        sync_intraday=False,
    )

    assert security.symbol == "MSFT"
    assert security.name == "Microsoft Corporation"
    # Verify daily fetch was called once (not twice for intraday)
    assert mock_fetch_daily.call_count == 1


@pytest.mark.integration
async def test_get_or_create_security_with_both_sync_types(test_db: AsyncSession, mocker) -> None:
    """Test creating security with both daily and intraday price sync."""
    mock_info = {
        "longName": "Google LLC",
        "currency": "USD",
        "exchange": "NASDAQ",
        "quoteType": "EQUITY",
    }
    mocker.patch(
        "app.services.security_service.fetch_security_info",
        return_value=mock_info,
    )
    mock_fetch_prices = mocker.patch(
        "app.services.security_service.fetch_historical_prices",
        return_value=None,
    )
    mocker.patch(
        "app.services.security_service.parse_yfinance_data",
        return_value=[],
    )

    security = await security_service.get_or_create_security(
        test_db,
        "GOOGL",
        sync_prices=True,
        sync_daily=True,
        sync_intraday=True,
    )

    assert security.symbol == "GOOGL"
    # Verify both daily and intraday fetches were called
    assert mock_fetch_prices.call_count == 2


@pytest.mark.integration
async def test_get_or_create_security_uses_short_name_fallback(
    test_db: AsyncSession, mocker
) -> None:
    """Test that shortName is used when longName is not available."""
    mock_info = {
        "shortName": "Tesla",  # Only shortName, no longName
        "currency": "USD",
        "exchange": "NASDAQ",
        "quoteType": "EQUITY",
    }
    mocker.patch(
        "app.services.security_service.fetch_security_info",
        return_value=mock_info,
    )
    mocker.patch(
        "app.services.security_service.fetch_historical_prices",
        return_value=None,
    )
    mocker.patch(
        "app.services.security_service.parse_yfinance_data",
        return_value=[],
    )

    security = await security_service.get_or_create_security(
        test_db,
        "TSLA",
        sync_prices=False,
    )

    assert security.symbol == "TSLA"
    assert security.name == "Tesla"


@pytest.mark.integration
async def test_get_or_create_security_uses_symbol_fallback(test_db: AsyncSession, mocker) -> None:
    """Test that symbol is used when neither longName nor shortName is available."""
    mock_info = {
        # No longName or shortName
        "currency": "USD",
        "exchange": "NYSE",
        "quoteType": "ETF",
    }
    mocker.patch(
        "app.services.security_service.fetch_security_info",
        return_value=mock_info,
    )
    mocker.patch(
        "app.services.security_service.fetch_historical_prices",
        return_value=None,
    )
    mocker.patch(
        "app.services.security_service.parse_yfinance_data",
        return_value=[],
    )

    security = await security_service.get_or_create_security(
        test_db,
        "SPY",
        sync_prices=False,
    )

    assert security.symbol == "SPY"
    assert security.name == "SPY"  # Falls back to symbol
