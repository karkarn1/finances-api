"""Tests for currency API endpoints."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.currency import Currency
from app.models.currency_rate import CurrencyRate


@pytest.fixture
async def test_currencies(test_db: AsyncSession) -> dict[str, Currency]:
    """Create test currencies for testing."""
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


@pytest.mark.integration
async def test_list_currencies(
    client: AsyncClient, test_db: AsyncSession, test_currencies: dict[str, Currency]
) -> None:
    """Test listing all currencies."""
    response = await client.get("/api/v1/currencies/")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 4

    # Check structure
    assert "id" in data[0]
    assert "code" in data[0]
    assert "name" in data[0]
    assert "symbol" in data[0]
    assert "is_active" in data[0]


@pytest.mark.integration
async def test_list_currencies_active_only(
    client: AsyncClient, test_db: AsyncSession, test_currencies: dict[str, Currency]
) -> None:
    """Test listing only active currencies."""
    # Create inactive currency
    inactive_currency = Currency(code="XXX", name="Test Inactive", symbol="X", is_active=False)
    test_db.add(inactive_currency)
    await test_db.commit()

    # Get active only
    response = await client.get("/api/v1/currencies/?active_only=true")
    assert response.status_code == 200
    data = response.json()
    codes = [c["code"] for c in data]
    assert "XXX" not in codes

    # Get all
    response = await client.get("/api/v1/currencies/?active_only=false")
    assert response.status_code == 200
    data = response.json()
    codes = [c["code"] for c in data]
    assert "XXX" in codes


@pytest.mark.integration
async def test_get_currency_success(
    client: AsyncClient, test_currencies: dict[str, Currency]
) -> None:
    """Test getting a specific currency by code."""
    response = await client.get("/api/v1/currencies/USD")
    assert response.status_code == 200

    data = response.json()
    assert data["code"] == "USD"
    assert data["name"] == "US Dollar"
    assert data["symbol"] == "$"
    assert data["is_active"] is True


@pytest.mark.integration
async def test_get_currency_not_found(client: AsyncClient) -> None:
    """Test getting a non-existent currency."""
    response = await client.get("/api/v1/currencies/ZZZ")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.integration
async def test_create_currency_success(
    client: AsyncClient, test_currencies: dict[str, Currency]
) -> None:
    """Test creating a new currency."""
    currency_data = {
        "code": "NZD",
        "name": "New Zealand Dollar",
        "symbol": "NZ$",
        "is_active": True,
    }

    response = await client.post("/api/v1/currencies/", json=currency_data)
    assert response.status_code == 201

    data = response.json()
    assert data["code"] == "NZD"
    assert data["name"] == "New Zealand Dollar"
    assert data["symbol"] == "NZ$"
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.integration
async def test_create_currency_duplicate(
    client: AsyncClient, test_currencies: dict[str, Currency]
) -> None:
    """Test creating a currency that already exists."""
    currency_data = {
        "code": "USD",
        "name": "US Dollar",
        "symbol": "$",
        "is_active": True,
    }

    response = await client.post("/api/v1/currencies/", json=currency_data)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.integration
async def test_create_currency_invalid_code(client: AsyncClient) -> None:
    """Test creating a currency with invalid code."""
    # Code too short
    response = await client.post(
        "/api/v1/currencies/",
        json={"code": "US", "name": "Test", "symbol": "$", "is_active": True},
    )
    assert response.status_code == 422

    # Code too long
    response = await client.post(
        "/api/v1/currencies/",
        json={"code": "USDD", "name": "Test", "symbol": "$", "is_active": True},
    )
    assert response.status_code == 422


@pytest.mark.integration
async def test_update_currency_success(client: AsyncClient, test_db: AsyncSession) -> None:
    """Test updating a currency."""
    # Create test currency
    currency = Currency(code="TST", name="Test Currency", symbol="T", is_active=True)
    test_db.add(currency)
    await test_db.commit()

    # Update it
    update_data = {
        "name": "Updated Test Currency",
        "symbol": "T$",
        "is_active": False,
    }

    response = await client.put("/api/v1/currencies/TST", json=update_data)
    assert response.status_code == 200

    data = response.json()
    assert data["code"] == "TST"
    assert data["name"] == "Updated Test Currency"
    assert data["symbol"] == "T$"
    assert data["is_active"] is False


@pytest.mark.integration
async def test_update_currency_not_found(client: AsyncClient) -> None:
    """Test updating a non-existent currency."""
    response = await client.put("/api/v1/currencies/ZZZ", json={"name": "Test", "symbol": "$"})
    assert response.status_code == 404


@pytest.mark.integration
async def test_update_currency_partial(client: AsyncClient, test_db: AsyncSession) -> None:
    """Test partial update of currency."""
    # Create test currency
    currency = Currency(code="PAR", name="Partial Test", symbol="P", is_active=True)
    test_db.add(currency)
    await test_db.commit()

    # Update only name
    response = await client.put("/api/v1/currencies/PAR", json={"name": "New Name"})
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == "New Name"
    assert data["symbol"] == "P"  # Unchanged
    assert data["is_active"] is True  # Unchanged


@pytest.mark.integration
async def test_get_currency_rates_success(
    client: AsyncClient, test_db: AsyncSession, test_currencies: dict[str, Currency]
) -> None:
    """Test getting exchange rates for a currency."""
    usd = test_currencies["USD"]
    eur = test_currencies["EUR"]
    cad = test_currencies["CAD"]

    # Create rates
    today = date.today()
    rate1 = CurrencyRate(
        from_currency_id=usd.id,
        to_currency_id=eur.id,
        rate=Decimal("0.92"),
        date=today,
    )
    rate2 = CurrencyRate(
        from_currency_id=usd.id,
        to_currency_id=cad.id,
        rate=Decimal("1.35"),
        date=today,
    )
    test_db.add_all([rate1, rate2])
    await test_db.commit()

    # Get rates
    response = await client.get(f"/api/v1/currencies/USD/rates?rate_date={today}")
    assert response.status_code == 200

    data = response.json()
    assert data["base_currency"] == "USD"
    assert data["date"] == str(today)
    assert data["count"] == 2
    assert "EUR" in data["rates"]
    assert "CAD" in data["rates"]
    assert float(data["rates"]["EUR"]) == 0.92
    assert float(data["rates"]["CAD"]) == 1.35


@pytest.mark.integration
async def test_get_currency_rates_not_found(client: AsyncClient) -> None:
    """Test getting rates for non-existent currency."""
    response = await client.get("/api/v1/currencies/ZZZ/rates")
    assert response.status_code == 404


@pytest.mark.integration
async def test_get_currency_rates_no_rates(
    client: AsyncClient, test_currencies: dict[str, Currency]
) -> None:
    """Test getting rates when none exist for date."""
    future_date = date.today() + timedelta(days=365)
    response = await client.get(f"/api/v1/currencies/USD/rates?rate_date={future_date}")
    assert response.status_code == 404
    assert "no rates found" in response.json()["detail"].lower()


@pytest.mark.integration
@pytest.mark.skip(reason="Requires external API - use for manual testing only")
async def test_sync_rates_success(
    client: AsyncClient, test_db: AsyncSession, test_currencies: dict[str, Currency]
) -> None:
    """Test syncing exchange rates from external API.

    Note: This test is skipped by default as it requires external API access.
    Enable manually for integration testing with real API.
    """
    response = await client.post("/api/v1/currencies/sync-rates?base_currency=USD")
    assert response.status_code == 200

    data = response.json()
    assert data["base_currency"] == "USD"
    assert data["synced_count"] > 0
    assert "message" in data

    # Verify rates were stored
    result = await test_db.execute(select(CurrencyRate))
    rates = result.scalars().all()
    assert len(rates) > 0


@pytest.mark.integration
async def test_sync_rates_invalid_base_currency(client: AsyncClient, test_db: AsyncSession) -> None:
    """Test syncing with invalid base currency."""
    # Create a test currency that won't be found by the API
    response = await client.post("/api/v1/currencies/sync-rates?base_currency=ZZZ")
    # Should still return 200 but with 0 synced
    assert response.status_code == 200
    data = response.json()
    assert data["synced_count"] == 0
