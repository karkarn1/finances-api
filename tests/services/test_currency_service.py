"""Tests for currency service functions."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.currency import Currency
from app.models.currency_rate import CurrencyRate
from app.services.currency_service import (
    fetch_exchange_rates,
    get_exchange_rate,
    sync_currency_rates,
)


@pytest.fixture
async def test_currencies(test_db: AsyncSession) -> dict[str, Currency]:
    """Create test currencies for service testing."""
    currencies = [
        Currency(code="USD", name="US Dollar", symbol="$", is_active=True),
        Currency(code="EUR", name="Euro", symbol="€", is_active=True),
        Currency(code="GBP", name="British Pound", symbol="£", is_active=True),
        Currency(code="CAD", name="Canadian Dollar", symbol="C$", is_active=True),
    ]
    test_db.add_all(currencies)
    await test_db.commit()

    # Refresh to get IDs
    for curr in currencies:
        await test_db.refresh(curr)

    return {curr.code: curr for curr in currencies}


@pytest.mark.unit
@pytest.mark.skip(reason="Requires external API - use for manual testing only")
async def test_fetch_exchange_rates_success() -> None:
    """Test fetching exchange rates from external API.

    Note: Skipped by default to avoid external API calls in CI.
    """
    rates = await fetch_exchange_rates("USD")
    assert rates is not None
    assert isinstance(rates, dict)
    assert "EUR" in rates
    assert "GBP" in rates
    assert "CAD" in rates
    assert isinstance(rates["EUR"], (int, float))


@pytest.mark.unit
async def test_fetch_exchange_rates_mocked() -> None:
    """Test fetching exchange rates with mocked API response."""
    from unittest.mock import MagicMock, Mock

    # Mock response object
    mock_response = Mock()
    mock_response.json = MagicMock(
        return_value={
            "rates": {
                "EUR": 0.92,
                "GBP": 0.79,
                "CAD": 1.35,
            }
        }
    )
    # raise_for_status is a regular method
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client:
        # Set up the async context manager and get method
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value = mock_instance

        # Test current rates (no date)
        rates = await fetch_exchange_rates("USD")
        assert rates is not None
        assert rates["USD"] == 1.0  # Base currency added by function
        assert rates["EUR"] == 0.92
        assert rates["GBP"] == 0.79
        assert rates["CAD"] == 1.35

        # Test historical rates (with date)
        historical_date = date(2024, 1, 15)
        rates = await fetch_exchange_rates("USD", historical_date)
        assert rates is not None
        assert rates["USD"] == 1.0
        assert rates["EUR"] == 0.92


@pytest.mark.unit
async def test_fetch_exchange_rates_api_error() -> None:
    """Test handling API errors gracefully."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get.side_effect = Exception(
            "API Error"
        )

        rates = await fetch_exchange_rates("USD")

        assert rates is None


@pytest.mark.integration
async def test_sync_currency_rates_success(
    test_db: AsyncSession, test_currencies: dict[str, Currency]
) -> None:
    """Test syncing currency rates to database."""
    mock_rates = {
        "USD": 1.0,
        "EUR": 0.92,
        "GBP": 0.79,
        "CAD": 1.35,
    }

    with patch(
        "app.services.currency_service.fetch_exchange_rates",
        new=AsyncMock(return_value=mock_rates),
    ):
        synced, failed = await sync_currency_rates(test_db, "USD")

        # Should create bidirectional rates for 3 currencies (excludes USD->USD)
        # EUR, GBP, CAD: 3 currencies * 2 directions = 6 rates
        assert synced == 6
        assert failed == 0

        # Verify rates were stored
        result = await test_db.execute(select(CurrencyRate))
        stored_rates = result.scalars().all()
        assert len(stored_rates) == 6


@pytest.mark.integration
async def test_sync_currency_rates_skips_missing_currencies(
    test_db: AsyncSession, test_currencies: dict[str, Currency]
) -> None:
    """Test that sync skips currencies not in database."""
    mock_rates = {
        "USD": 1.0,
        "EUR": 0.92,
        "ZZZ": 999.99,  # Currency not in database
    }

    with patch(
        "app.services.currency_service.fetch_exchange_rates",
        new=AsyncMock(return_value=mock_rates),
    ):
        synced, failed = await sync_currency_rates(test_db, "USD")

        # Should only sync EUR (excludes USD->USD, and ZZZ is not in database)
        # 1 currency * 2 directions = 2 rates
        assert synced == 2
        assert failed == 0


@pytest.mark.integration
async def test_sync_currency_rates_api_failure(test_db: AsyncSession) -> None:
    """Test handling API failure during sync."""
    with patch(
        "app.services.currency_service.fetch_exchange_rates",
        new=AsyncMock(return_value=None),
    ):
        synced, failed = await sync_currency_rates(test_db, "USD")

        assert synced == 0
        assert failed == 0


@pytest.mark.integration
async def test_sync_currency_rates_custom_date(
    test_db: AsyncSession, test_currencies: dict[str, Currency]
) -> None:
    """Test syncing rates for a specific date."""
    custom_date = date(2024, 1, 15)
    mock_rates = {"USD": 1.0, "EUR": 0.92}

    with patch(
        "app.services.currency_service.fetch_exchange_rates",
        new=AsyncMock(return_value=mock_rates),
    ):
        synced, failed = await sync_currency_rates(test_db, "USD", custom_date)

        # Should sync EUR only (excludes USD->USD)
        # 1 currency * 2 directions = 2 rates
        assert synced == 2

        # Verify date was set correctly
        result = await test_db.execute(select(CurrencyRate))
        rates = result.scalars().all()
        for rate in rates:
            assert rate.date == custom_date


@pytest.mark.integration
async def test_sync_currency_rates_prevents_duplicates(
    test_db: AsyncSession, test_currencies: dict[str, Currency]
) -> None:
    """Test that syncing same rates twice doesn't create duplicates."""
    mock_rates = {"USD": 1.0, "EUR": 0.92}

    with patch(
        "app.services.currency_service.fetch_exchange_rates",
        new=AsyncMock(return_value=mock_rates),
    ):
        # First sync
        synced1, failed1 = await sync_currency_rates(test_db, "USD")
        # Should sync EUR only (excludes USD->USD)
        # 1 currency * 2 directions = 2 rates
        assert synced1 == 2

        # Second sync should rollback due to unique constraint
        synced2, failed2 = await sync_currency_rates(test_db, "USD")
        # Will fail to commit due to unique constraint
        assert synced2 == 0


@pytest.mark.integration
async def test_get_exchange_rate_success(
    test_db: AsyncSession, test_currencies: dict[str, Currency]
) -> None:
    """Test getting exchange rate between two currencies."""
    # Get currencies from fixture
    usd = test_currencies["USD"]
    eur = test_currencies["EUR"]

    # Create rate
    today = date.today()
    rate = CurrencyRate(
        from_currency_id=usd.id,
        to_currency_id=eur.id,
        rate=Decimal("0.92"),
        date=today,
    )
    test_db.add(rate)
    await test_db.commit()

    # Get rate
    result_rate = await get_exchange_rate(test_db, "USD", "EUR", today)

    assert result_rate is not None
    assert result_rate == Decimal("0.92")


@pytest.mark.integration
async def test_get_exchange_rate_not_found(test_db: AsyncSession) -> None:
    """Test getting rate that doesn't exist."""
    result = await get_exchange_rate(test_db, "USD", "EUR")
    assert result is None


@pytest.mark.integration
async def test_get_exchange_rate_currency_not_found(test_db: AsyncSession) -> None:
    """Test getting rate for non-existent currency."""
    result = await get_exchange_rate(test_db, "ZZZ", "EUR")
    assert result is None


@pytest.mark.integration
async def test_sync_creates_bidirectional_rates(
    test_db: AsyncSession, test_currencies: dict[str, Currency]
) -> None:
    """Test that sync creates both forward and reverse rates."""
    mock_rates = {"USD": 1.0, "EUR": 0.92}

    with patch(
        "app.services.currency_service.fetch_exchange_rates",
        new=AsyncMock(return_value=mock_rates),
    ):
        await sync_currency_rates(test_db, "USD")

        # Get currencies from fixture
        usd = test_currencies["USD"]
        eur = test_currencies["EUR"]

        # Check USD -> EUR rate
        result = await test_db.execute(
            select(CurrencyRate).where(
                CurrencyRate.from_currency_id == usd.id,
                CurrencyRate.to_currency_id == eur.id,
            )
        )
        usd_to_eur = result.scalar_one()
        assert usd_to_eur.rate == Decimal("0.92")

        # Check EUR -> USD rate (reverse)
        result = await test_db.execute(
            select(CurrencyRate).where(
                CurrencyRate.from_currency_id == eur.id,
                CurrencyRate.to_currency_id == usd.id,
            )
        )
        eur_to_usd = result.scalar_one()
        # Reverse rate should be 1 / 0.92
        expected_reverse = Decimal("1") / Decimal("0.92")
        assert abs(eur_to_usd.rate - expected_reverse) < Decimal("0.00000001")
