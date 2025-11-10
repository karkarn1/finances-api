"""Tests for securities endpoints."""

import uuid
from datetime import UTC, datetime, timedelta

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
                datetime(2024, 1, 1, tzinfo=UTC),
                datetime(2024, 1, 2, tzinfo=UTC),
                datetime(2024, 1, 3, tzinfo=UTC),
            ]
        ),
    )
    return df


@pytest.mark.asyncio
async def test_search_securities_empty_no_yfinance_match(
    client: AsyncClient, test_user: User, auth_headers: dict[str, str], mocker
):
    """Test searching securities when database is empty and yfinance has no match."""
    from app.services.yfinance_service import InvalidSymbolError

    # Mock yfinance to return no results
    mocker.patch(
        "app.api.routes.securities.fetch_security_info",
        side_effect=InvalidSymbolError("Symbol not found"),
    )

    response = await client.get("/api/v1/securities/search?q=INVALID")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_search_securities_empty_with_yfinance_match(
    client: AsyncClient, test_user: User, auth_headers: dict[str, str], mocker
):
    """Test searching securities when database is empty but yfinance has a match."""
    # Mock yfinance to return a valid security
    mocker.patch(
        "app.api.routes.securities.fetch_security_info",
        return_value=SAMPLE_YFINANCE_INFO,
    )

    response = await client.get("/api/v1/securities/search?q=AAPL")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "AAPL"
    assert data[0]["name"] == "Apple Inc."
    assert data[0]["in_database"] is False  # Not in DB yet
    assert data[0]["last_synced_at"] is None


@pytest.mark.asyncio
async def test_search_securities_by_symbol(
    client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
    mocker,
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

    # Mock yfinance to prevent real API calls
    from app.services.yfinance_service import InvalidSymbolError
    mocker.patch(
        "app.api.routes.securities.fetch_security_info",
        side_effect=InvalidSymbolError("Symbol not found"),
    )

    response = await client.get("/api/v1/securities/search?q=AAP")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "AAPL"
    assert data[0]["name"] == "Apple Inc."
    assert data[0]["in_database"] is True  # DB result should be marked


@pytest.mark.asyncio
async def test_search_securities_db_results_have_in_database_flag(
    client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
):
    """Test that database results are marked with in_database=True."""
    # Create test security
    security = Security(
        id=uuid.uuid4(),
        symbol="MSFT",
        name="Microsoft Corporation",
        exchange="NASDAQ",
        currency="USD",
    )
    test_db.add(security)
    await test_db.commit()

    response = await client.get("/api/v1/securities/search?q=MSFT")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["in_database"] is True


@pytest.mark.asyncio
async def test_search_securities_exact_match_skips_yfinance(
    client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
    mocker,
):
    """Test that exact symbol match in DB prevents yfinance call."""
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

    # Mock yfinance - should not be called
    mock_yfinance = mocker.patch(
        "app.api.routes.securities.fetch_security_info",
        return_value=SAMPLE_YFINANCE_INFO,
    )

    response = await client.get("/api/v1/securities/search?q=AAPL")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "AAPL"
    assert data[0]["in_database"] is True

    # Verify yfinance was not called (exact match exists)
    mock_yfinance.assert_not_called()


@pytest.mark.asyncio
async def test_search_securities_partial_match_tries_yfinance(
    client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
    mocker,
):
    """Test that partial DB match still tries yfinance for exact symbol."""
    # Create test security with similar name but different symbol
    security = Security(
        id=uuid.uuid4(),
        symbol="GOOGL",
        name="Alphabet Inc.",
        exchange="NASDAQ",
        currency="USD",
    )
    test_db.add(security)
    await test_db.commit()

    # Mock yfinance to return a different security
    mocker.patch(
        "app.api.routes.securities.fetch_security_info",
        return_value={
            "name": "Apple Inc.",
            "exchange": "NASDAQ",
            "currency": "USD",
            "security_type": "EQUITY",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "market_cap": 2800000000000,
        },
    )

    # Search for "AAPL" - no exact match in DB, should query yfinance
    response = await client.get("/api/v1/securities/search?q=AAPL")
    assert response.status_code == 200
    data = response.json()

    # Should have the yfinance result (no DB matches for AAPL)
    assert len(data) == 1
    assert data[0]["symbol"] == "AAPL"
    assert data[0]["in_database"] is False


@pytest.mark.asyncio
async def test_search_securities_long_query_skips_yfinance(
    client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
    mocker,
):
    """Test that long queries (>10 chars) skip yfinance lookup."""
    # Mock yfinance - should not be called
    mock_yfinance = mocker.patch(
        "app.api.routes.securities.fetch_security_info",
        return_value=SAMPLE_YFINANCE_INFO,
    )

    response = await client.get("/api/v1/securities/search?q=ThisIsAReallyLongQuery")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0

    # Verify yfinance was not called (query too long)
    mock_yfinance.assert_not_called()


@pytest.mark.asyncio
async def test_search_securities_yfinance_api_error_doesnt_fail(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict[str, str],
    mocker,
):
    """Test that yfinance API errors don't fail the search request."""
    from app.services.yfinance_service import APIError

    # Mock yfinance to raise API error
    mocker.patch(
        "app.api.routes.securities.fetch_security_info",
        side_effect=APIError("API unavailable"),
    )

    # Request should succeed, just without yfinance results
    response = await client.get("/api/v1/securities/search?q=AAPL")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0  # No results but no error


@pytest.mark.asyncio
async def test_search_securities_yfinance_prepended_to_results(
    client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
    mocker,
):
    """Test that yfinance results are prepended (shown first)."""
    # Create test security with name containing the search term but different symbol
    security = Security(
        id=uuid.uuid4(),
        symbol="MSFT",
        name="Microsoft Corporation (Apple Partner)",  # Contains "apple"
        exchange="NASDAQ",
        currency="USD",
    )
    test_db.add(security)
    await test_db.commit()

    # Mock yfinance to return AAPL
    mocker.patch(
        "app.api.routes.securities.fetch_security_info",
        return_value=SAMPLE_YFINANCE_INFO,
    )

    # Search for "apple" - should find MSFT in DB by name, and fetch AAPL from yfinance
    response = await client.get("/api/v1/securities/search?q=apple")
    assert response.status_code == 200
    data = response.json()

    # Should have 2 results: yfinance result first, then DB result
    assert len(data) == 2
    assert data[0]["symbol"] == "APPLE"  # yfinance result first (query uppercased)
    assert data[0]["in_database"] is False
    assert data[1]["symbol"] == "MSFT"  # DB result second
    assert data[1]["in_database"] is True


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
async def test_get_security_not_found_invalid_symbol(
    client: AsyncClient, test_user: User, auth_headers: dict[str, str], mocker
):
    """Test getting a security with invalid symbol (not in DB and not in yfinance)."""
    from app.services.yfinance_service import InvalidSymbolError

    # Mock yfinance to return symbol not found
    mocker.patch(
        "app.api.routes.securities.fetch_security_info",
        side_effect=InvalidSymbolError("Symbol 'INVALID' not found in Yahoo Finance"),
    )

    response = await client.get("/api/v1/securities/INVALID")
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
async def test_get_security_auto_creates_when_not_in_db(
    client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
    mocker,
):
    """Test that endpoint auto-creates security when it doesn't exist in DB."""
    # Mock yfinance functions
    mocker.patch(
        "app.api.routes.securities.fetch_security_info",
        return_value=SAMPLE_YFINANCE_INFO,
    )
    mocker.patch(
        "app.api.routes.securities.fetch_historical_prices",
        return_value=create_sample_dataframe(),
    )

    # Security doesn't exist in DB yet
    response = await client.get("/api/v1/securities/AAPL")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["name"] == "Apple Inc."
    assert data["exchange"] == "NASDAQ"
    # Should be synced by now (sync completes within the request)
    assert data["is_syncing"] is False
    assert data["last_synced_at"] is not None

    # Verify security was created in database
    from sqlalchemy import select
    result = await test_db.execute(
        select(Security).where(Security.symbol == "AAPL")
    )
    security = result.scalar_one_or_none()
    assert security is not None
    assert security.symbol == "AAPL"


@pytest.mark.asyncio
async def test_get_security_auto_sync_yfinance_api_error(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict[str, str],
    mocker,
):
    """Test that yfinance API errors are handled properly during auto-sync."""
    from app.services.yfinance_service import APIError

    # Mock yfinance to raise API error
    mocker.patch(
        "app.api.routes.securities.fetch_security_info",
        side_effect=APIError("Yahoo Finance API unavailable"),
    )

    response = await client.get("/api/v1/securities/AAPL")
    assert response.status_code == 503
    assert "api error" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_security_auto_sync_partial_failure(
    client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
    mocker,
):
    """Test that security is still created even if price sync partially fails."""
    from app.services.yfinance_service import APIError

    # Mock security info fetch to succeed
    mocker.patch(
        "app.api.routes.securities.fetch_security_info",
        return_value=SAMPLE_YFINANCE_INFO,
    )

    # Mock price fetch to fail
    mocker.patch(
        "app.api.routes.securities.fetch_historical_prices",
        side_effect=APIError("Failed to fetch prices"),
    )

    # Should still create the security metadata even if price sync fails
    response = await client.get("/api/v1/securities/AAPL")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["name"] == "Apple Inc."
    assert data["is_syncing"] is False
    # last_synced_at should be set even if prices failed
    assert data["last_synced_at"] is not None


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
    assert data["data_completeness"] == "empty"
    assert data["actual_start"] is None
    assert data["actual_end"] is None


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
    now = datetime.now(UTC)
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
            timestamp=datetime(2024, 1, i + 1, tzinfo=UTC),
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
    now = datetime.now(UTC)
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


@pytest.mark.asyncio
async def test_get_prices_sparse_data_weekends(
    client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
):
    """Test getting prices when requested range includes weekends with no data."""
    security = Security(
        id=uuid.uuid4(),
        symbol="AAPL",
        name="Apple Inc.",
    )
    test_db.add(security)
    await test_db.commit()
    await test_db.refresh(security)

    # Add price data only for weekdays (Jan 1-5, 2024 were Mon-Fri)
    weekday_dates = [
        datetime(2024, 1, 1, tzinfo=UTC),  # Monday
        datetime(2024, 1, 2, tzinfo=UTC),  # Tuesday
        datetime(2024, 1, 3, tzinfo=UTC),  # Wednesday
        datetime(2024, 1, 4, tzinfo=UTC),  # Thursday
        datetime(2024, 1, 5, tzinfo=UTC),  # Friday
    ]

    for i, date in enumerate(weekday_dates):
        price = SecurityPrice(
            id=uuid.uuid4(),
            security_id=security.id,
            timestamp=date,
            open=150.0 + i,
            high=155.0 + i,
            low=149.0 + i,
            close=154.0 + i,
            volume=1000000 + i * 100000,
            interval_type="1d",
        )
        test_db.add(price)
    await test_db.commit()

    # Query for range including weekend (Jan 1-7, 2024)
    response = await client.get(
        "/api/v1/securities/AAPL/prices"
        "?start=2024-01-01T00:00:00Z&end=2024-01-07T23:59:59Z&interval=1d",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Should return the 5 weekday data points
    assert data["count"] == 5
    assert len(data["prices"]) == 5
    # Data completeness should be "partial" or "complete" (5 trading days in 7 calendar days)
    assert data["data_completeness"] in ["complete", "partial"]
    assert data["actual_start"] is not None
    assert data["actual_end"] is not None


@pytest.mark.asyncio
async def test_get_prices_data_outside_requested_range(
    client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
):
    """Test that endpoint returns nearby data when exact range has no data."""
    security = Security(
        id=uuid.uuid4(),
        symbol="AAPL",
        name="Apple Inc.",
    )
    test_db.add(security)
    await test_db.commit()
    await test_db.refresh(security)

    # Add price data a few days before the requested range (within 7-day buffer)
    # Data on Jan 25-29
    for i in range(5):
        price = SecurityPrice(
            id=uuid.uuid4(),
            security_id=security.id,
            timestamp=datetime(2024, 1, 25 + i, tzinfo=UTC),
            open=150.0 + i,
            high=155.0 + i,
            low=149.0 + i,
            close=154.0 + i,
            volume=1000000 + i * 100000,
            interval_type="1d",
        )
        test_db.add(price)
    await test_db.commit()

    # Request data for early February (Feb 1-5)
    # No exact data, but Jan 25-29 is within 7-day buffer
    response = await client.get(
        "/api/v1/securities/AAPL/prices"
        "?start=2024-02-01T00:00:00Z&end=2024-02-05T23:59:59Z&interval=1d",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Should return the late January data (within 7-day buffer)
    assert data["count"] == 5
    assert data["data_completeness"] == "partial"
    # Actual dates should be in late January
    assert data["actual_start"] is not None
    assert "2024-01-25" in data["actual_start"]


@pytest.mark.asyncio
async def test_get_prices_very_sparse_data(
    client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
):
    """Test getting prices when data is very sparse (low volume stock)."""
    security = Security(
        id=uuid.uuid4(),
        symbol="LOWVOL",
        name="Low Volume Stock",
    )
    test_db.add(security)
    await test_db.commit()
    await test_db.refresh(security)

    # Add only 2 data points over 30 days (very sparse)
    sparse_dates = [
        datetime(2024, 1, 1, tzinfo=UTC),
        datetime(2024, 1, 30, tzinfo=UTC),
    ]

    for i, date in enumerate(sparse_dates):
        price = SecurityPrice(
            id=uuid.uuid4(),
            security_id=security.id,
            timestamp=date,
            open=10.0 + i,
            high=11.0 + i,
            low=9.0 + i,
            close=10.5 + i,
            volume=10000,
            interval_type="1d",
        )
        test_db.add(price)
    await test_db.commit()

    # Query for the full range
    response = await client.get(
        "/api/v1/securities/LOWVOL/prices"
        "?start=2024-01-01T00:00:00Z&end=2024-01-31T23:59:59Z&interval=1d",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Should return both sparse points
    assert data["count"] == 2
    assert data["data_completeness"] == "sparse"
    assert data["actual_start"] is not None
    assert data["actual_end"] is not None


@pytest.mark.asyncio
async def test_get_prices_complete_data(
    client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
):
    """Test that complete data is properly flagged."""
    security = Security(
        id=uuid.uuid4(),
        symbol="COMPLETE",
        name="Complete Data Stock",
    )
    test_db.add(security)
    await test_db.commit()
    await test_db.refresh(security)

    # Add comprehensive data for 10 trading days
    for i in range(10):
        price = SecurityPrice(
            id=uuid.uuid4(),
            security_id=security.id,
            timestamp=datetime(2024, 1, i + 1, tzinfo=UTC),
            open=150.0 + i,
            high=155.0 + i,
            low=149.0 + i,
            close=154.0 + i,
            volume=1000000,
            interval_type="1d",
        )
        test_db.add(price)
    await test_db.commit()

    # Query for range that has complete data
    response = await client.get(
        "/api/v1/securities/COMPLETE/prices"
        "?start=2024-01-01T00:00:00Z&end=2024-01-10T23:59:59Z&interval=1d",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["count"] == 10
    # Should be "complete" since we have all 10 days
    assert data["data_completeness"] == "complete"


@pytest.mark.asyncio
async def test_get_prices_metadata_fields(
    client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
):
    """Test that all metadata fields are present in response."""
    security = Security(
        id=uuid.uuid4(),
        symbol="META",
        name="Metadata Test",
    )
    test_db.add(security)
    await test_db.commit()
    await test_db.refresh(security)

    # Add some price data
    price = SecurityPrice(
        id=uuid.uuid4(),
        security_id=security.id,
        timestamp=datetime(2024, 1, 15, tzinfo=UTC),
        open=100.0,
        high=105.0,
        low=99.0,
        close=103.0,
        volume=500000,
        interval_type="1d",
    )
    test_db.add(price)
    await test_db.commit()

    response = await client.get(
        "/api/v1/securities/META/prices"
        "?start=2024-01-01T00:00:00Z&end=2024-01-31T23:59:59Z&interval=1d",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Verify all metadata fields exist
    assert "requested_start" in data
    assert "requested_end" in data
    assert "actual_start" in data
    assert "actual_end" in data
    assert "data_completeness" in data
    assert data["requested_start"] is not None
    assert data["requested_end"] is not None
    assert data["actual_start"] is not None
    assert data["actual_end"] is not None
    assert data["data_completeness"] in ["complete", "partial", "sparse", "empty"]
