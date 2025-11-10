"""Tests for securities endpoints."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pandas as pd
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security import Security
from app.models.security_price import SecurityPrice
from app.models.user import User


pytestmark = pytest.mark.integration


# Sample yfinance data for mocking
SAMPLE_YFINANCE_INFO = {
    "name": "Apple Inc.",
    "exchange": "NASDAQ",
    "currency": "USD",
    "security_type": "EQUITY",
    "sector": "Technology",
    "industry": "Consumer Electronics",
    "market_cap": 2800000000000,
}

SAMPLE_PRICE_DATA = {
    "Open": [150.0, 151.0, 152.0],
    "High": [155.0, 156.0, 157.0],
    "Low": [149.0, 150.0, 151.0],
    "Close": [154.0, 155.0, 156.0],
    "Volume": [1000000, 1100000, 1200000],
}


def create_sample_dataframe():
    """Create a sample price DataFrame for testing."""
    df = pd.DataFrame(
        SAMPLE_PRICE_DATA,
        index=pd.DatetimeIndex(
            [
                datetime(2024, 1, 1, tzinfo=timezone.utc),
                datetime(2024, 1, 2, tzinfo=timezone.utc),
                datetime(2024, 1, 3, tzinfo=timezone.utc),
            ]
        ),
    )
    return df


@pytest.mark.asyncio
async def test_search_securities_empty(
    client: AsyncClient, test_user: User, auth_headers: dict[str, str]
):
    """Test searching securities when database is empty."""
    response = await client.get("/api/v1/securities/search?q=AAPL")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_search_securities_by_symbol(
    client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
):
    """Test searching securities by symbol."""
    # Create test security
    security = Security(
        id=uuid.uuid4(),
        symbol="AAPL",
        name="Apple Inc.",
        exchange="NASDAQ",
        currency="USD",
    )
    test_db.add(security)
    await test_db.commit()

    response = await client.get("/api/v1/securities/search?q=AAP")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "AAPL"
    assert data[0]["name"] == "Apple Inc."


@pytest.mark.asyncio
async def test_search_securities_by_name(
    client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
):
    """Test searching securities by name."""
    # Create test security
    security = Security(
        id=uuid.uuid4(),
        symbol="AAPL",
        name="Apple Inc.",
        exchange="NASDAQ",
        currency="USD",
    )
    test_db.add(security)
    await test_db.commit()

    response = await client.get("/api/v1/securities/search?q=apple")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "AAPL"


@pytest.mark.asyncio
async def test_search_securities_limit(
    client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
):
    """Test searching securities with limit."""
    # Create multiple test securities
    for i in range(25):
        security = Security(
            id=uuid.uuid4(),
            symbol=f"TEST{i}",
            name=f"Test Company {i}",
        )
        test_db.add(security)
    await test_db.commit()

    response = await client.get("/api/v1/securities/search?q=test&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 10


@pytest.mark.asyncio
async def test_get_security_not_found(
    client: AsyncClient, test_user: User, auth_headers: dict[str, str]
):
    """Test getting a security that doesn't exist."""
    response = await client.get("/api/v1/securities/AAPL")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_security_success(
    client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
):
    """Test getting an existing security."""
    security = Security(
        id=uuid.uuid4(),
        symbol="AAPL",
        name="Apple Inc.",
        exchange="NASDAQ",
        currency="USD",
        is_syncing=False,
    )
    test_db.add(security)
    await test_db.commit()

    response = await client.get("/api/v1/securities/AAPL")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["name"] == "Apple Inc."
    assert data["is_syncing"] is False


@pytest.mark.asyncio
async def test_sync_security_unauthorized(client: AsyncClient):
    """Test syncing without authentication."""
    response = await client.post("/api/v1/securities/AAPL/sync")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_sync_security_new(
    client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
    mocker,
):
    """Test syncing a new security."""
    # Mock yfinance functions
    mocker.patch(
        "app.api.routes.securities.fetch_security_info",
        return_value=SAMPLE_YFINANCE_INFO,
    )
    mocker.patch(
        "app.api.routes.securities.fetch_historical_prices",
        return_value=create_sample_dataframe(),
    )

    response = await client.post(
        "/api/v1/securities/AAPL/sync", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["security"]["symbol"] == "AAPL"
    assert data["security"]["name"] == "Apple Inc."
    assert data["prices_synced"] >= 3  # At least the mocked data
    assert "successfully synced" in data["message"].lower()


@pytest.mark.asyncio
async def test_sync_security_already_syncing(
    client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
):
    """Test syncing when sync is already in progress."""
    # Create security with is_syncing=True
    security = Security(
        id=uuid.uuid4(),
        symbol="AAPL",
        name="Apple Inc.",
        is_syncing=True,
    )
    test_db.add(security)
    await test_db.commit()

    response = await client.post(
        "/api/v1/securities/AAPL/sync", headers=auth_headers
    )
    assert response.status_code == 409
    assert "already in progress" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_sync_security_invalid_symbol(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict[str, str],
    mocker,
):
    """Test syncing with an invalid symbol."""
    from app.services.yfinance_service import InvalidSymbolError

    mocker.patch(
        "app.api.routes.securities.fetch_security_info",
        side_effect=InvalidSymbolError("Symbol not found"),
    )

    response = await client.post(
        "/api/v1/securities/INVALID/sync", headers=auth_headers
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_sync_security_api_error(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict[str, str],
    mocker,
):
    """Test syncing when yfinance API fails."""
    from app.services.yfinance_service import APIError

    mocker.patch(
        "app.api.routes.securities.fetch_security_info",
        side_effect=APIError("API unavailable"),
    )

    response = await client.post(
        "/api/v1/securities/AAPL/sync", headers=auth_headers
    )
    assert response.status_code == 503
    assert "api error" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_prices_no_security(
    client: AsyncClient, test_user: User, auth_headers: dict[str, str]
):
    """Test getting prices for non-existent security."""
    response = await client.get(
        "/api/v1/securities/AAPL/prices", headers=auth_headers
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_prices_no_data(
    client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
):
    """Test getting prices when no price data exists."""
    security = Security(
        id=uuid.uuid4(),
        symbol="AAPL",
        name="Apple Inc.",
    )
    test_db.add(security)
    await test_db.commit()

    response = await client.get(
        "/api/v1/securities/AAPL/prices", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["security"]["symbol"] == "AAPL"
    assert data["prices"] == []
    assert data["count"] == 0


@pytest.mark.asyncio
async def test_get_prices_with_data(
    client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
):
    """Test getting prices with existing price data."""
    security = Security(
        id=uuid.uuid4(),
        symbol="AAPL",
        name="Apple Inc.",
    )
    test_db.add(security)
    await test_db.commit()
    await test_db.refresh(security)

    # Add price data - use recent dates within last 30 days
    now = datetime.now(timezone.utc)
    for i in range(5):
        price = SecurityPrice(
            id=uuid.uuid4(),
            security_id=security.id,
            timestamp=now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=4-i),
            open=150.0 + i,
            high=155.0 + i,
            low=149.0 + i,
            close=154.0 + i,
            volume=1000000 + i * 100000,
            interval_type="1d",
        )
        test_db.add(price)
    await test_db.commit()

    response = await client.get(
        "/api/v1/securities/AAPL/prices?interval=1d", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["security"]["symbol"] == "AAPL"
    assert len(data["prices"]) == 5
    assert data["count"] == 5
    assert data["interval_type"] == "1d"


@pytest.mark.asyncio
async def test_get_prices_with_date_range(
    client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
):
    """Test getting prices with date range filter."""
    security = Security(
        id=uuid.uuid4(),
        symbol="AAPL",
        name="Apple Inc.",
    )
    test_db.add(security)
    await test_db.commit()
    await test_db.refresh(security)

    # Add price data for 10 days
    for i in range(10):
        price = SecurityPrice(
            id=uuid.uuid4(),
            security_id=security.id,
            timestamp=datetime(2024, 1, i + 1, tzinfo=timezone.utc),
            open=150.0 + i,
            high=155.0 + i,
            low=149.0 + i,
            close=154.0 + i,
            volume=1000000 + i * 100000,
            interval_type="1d",
        )
        test_db.add(price)
    await test_db.commit()

    # Query for specific range (days 3-7)
    response = await client.get(
        "/api/v1/securities/AAPL/prices"
        "?start=2024-01-03T00:00:00Z&end=2024-01-07T23:59:59Z&interval=1d",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 5  # Days 3, 4, 5, 6, 7
    assert len(data["prices"]) == 5


@pytest.mark.asyncio
async def test_get_prices_different_intervals(
    client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
):
    """Test getting prices filters by interval type."""
    security = Security(
        id=uuid.uuid4(),
        symbol="AAPL",
        name="Apple Inc.",
    )
    test_db.add(security)
    await test_db.commit()
    await test_db.refresh(security)

    # Add both daily and minute prices - use recent dates
    now = datetime.now(timezone.utc)
    for i in range(3):
        # Daily - within last 30 days
        price_daily = SecurityPrice(
            id=uuid.uuid4(),
            security_id=security.id,
            timestamp=now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=2-i),
            open=150.0,
            high=155.0,
            low=149.0,
            close=154.0,
            volume=1000000,
            interval_type="1d",
        )
        test_db.add(price_daily)

        # Minute - within last 24 hours
        price_minute = SecurityPrice(
            id=uuid.uuid4(),
            security_id=security.id,
            timestamp=now - timedelta(hours=2-i),
            open=150.0,
            high=155.0,
            low=149.0,
            close=154.0,
            volume=100000,
            interval_type="1m",
        )
        test_db.add(price_minute)
    await test_db.commit()

    # Query daily only
    response = await client.get(
        "/api/v1/securities/AAPL/prices?interval=1d", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 3
    assert data["interval_type"] == "1d"

    # Query minute only
    response = await client.get(
        "/api/v1/securities/AAPL/prices?interval=1m", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 3
    assert data["interval_type"] == "1m"


@pytest.mark.asyncio
async def test_get_prices_invalid_interval(
    client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
):
    """Test getting prices with invalid interval."""
    security = Security(
        id=uuid.uuid4(),
        symbol="AAPL",
        name="Apple Inc.",
    )
    test_db.add(security)
    await test_db.commit()

    response = await client.get(
        "/api/v1/securities/AAPL/prices?interval=5m", headers=auth_headers
    )
    assert response.status_code == 422  # Validation error
