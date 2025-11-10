"""Tests for holding endpoints with auto-sync functionality."""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account, AccountType
from app.models.holding import Holding
from app.models.security import Security


@pytest.mark.integration
async def test_create_holding_with_existing_security(
    client: AsyncClient,
    test_user,
    auth_headers: dict,
    test_db: AsyncSession,
) -> None:
    """Test creating a holding with an existing security (UUID)."""
    # Create a test account
    account = Account(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Test Investment Account",
        account_type=AccountType.TFSA,
        is_investment_account=True,
    )
    test_db.add(account)
    await test_db.commit()
    await test_db.refresh(account)

    # Create a test security
    security = Security(
        id=uuid.uuid4(),
        symbol="TEST",
        name="Test Corporation",
        exchange="NASDAQ",
        currency="USD",
        security_type="EQUITY",
    )
    test_db.add(security)
    await test_db.commit()
    await test_db.refresh(security)

    # Create holding with UUID
    response = await client.post(
        f"/api/v1/accounts/{account.id}/holdings/",
        json={
            "security_id": str(security.id),
            "shares": 10.5,
            "average_price_per_share": 150.25,
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["security_id"] == str(security.id)
    assert Decimal(str(data["shares"])) == Decimal("10.5")
    assert Decimal(str(data["average_price_per_share"])) == Decimal("150.25")


@pytest.mark.integration
async def test_create_holding_with_symbol_auto_sync(
    client: AsyncClient,
    test_user,
    auth_headers: dict,
    test_db: AsyncSession,
) -> None:
    """Test creating a holding with a symbol that triggers auto-sync from Yahoo Finance."""
    # Create a test account
    account = Account(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Test Investment Account",
        account_type=AccountType.TFSA,
        is_investment_account=True,
    )
    test_db.add(account)
    await test_db.commit()
    await test_db.refresh(account)

    # Ensure AAPL doesn't exist in database
    result = await test_db.execute(select(Security).where(Security.symbol == "AAPL"))
    existing_security = result.scalar_one_or_none()
    if existing_security:
        await test_db.delete(existing_security)
        await test_db.commit()

    # Create holding with symbol (should auto-sync from Yahoo Finance)
    response = await client.post(
        f"/api/v1/accounts/{account.id}/holdings/",
        json={
            "security_id": "AAPL",  # Symbol, not UUID
            "shares": 5.0,
            "average_price_per_share": 180.00,
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()

    # Verify holding was created
    assert Decimal(str(data["shares"])) == Decimal("5.0")
    assert Decimal(str(data["average_price_per_share"])) == Decimal("180.00")

    # Verify security was auto-synced from Yahoo Finance
    security_id = data["security_id"]
    result = await test_db.execute(
        select(Security).where(Security.id == uuid.UUID(security_id))
    )
    security = result.scalar_one_or_none()

    assert security is not None
    assert security.symbol == "AAPL"
    assert security.name is not None  # Should have fetched from Yahoo Finance
    assert security.exchange is not None
    assert security.currency == "USD"
    assert security.security_type == "EQUITY"


@pytest.mark.integration
async def test_create_holding_with_invalid_symbol(
    client: AsyncClient,
    test_user,
    auth_headers: dict,
    test_db: AsyncSession,
) -> None:
    """Test creating a holding with an invalid symbol returns 404."""
    # Create a test account
    account = Account(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Test Investment Account",
        account_type=AccountType.TFSA,
        is_investment_account=True,
    )
    test_db.add(account)
    await test_db.commit()
    await test_db.refresh(account)

    # Try to create holding with invalid symbol
    response = await client.post(
        f"/api/v1/accounts/{account.id}/holdings/",
        json={
            "security_id": "INVALIDXYZ123",
            "shares": 5.0,
            "average_price_per_share": 100.00,
        },
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert "not found in Yahoo Finance" in response.json()["detail"]


@pytest.mark.integration
async def test_create_holding_non_investment_account(
    client: AsyncClient,
    test_user,
    auth_headers: dict,
    test_db: AsyncSession,
) -> None:
    """Test creating a holding in a non-investment account fails."""
    # Create a non-investment account
    account = Account(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Test Checking Account",
        account_type=AccountType.CHECKING,
        is_investment_account=False,
    )
    test_db.add(account)
    await test_db.commit()
    await test_db.refresh(account)

    # Try to create holding
    response = await client.post(
        f"/api/v1/accounts/{account.id}/holdings/",
        json={
            "security_id": "AAPL",
            "shares": 5.0,
            "average_price_per_share": 180.00,
        },
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "investment accounts" in response.json()["detail"]


@pytest.mark.integration
async def test_update_holding_with_symbol(
    client: AsyncClient,
    test_user,
    auth_headers: dict,
    test_db: AsyncSession,
) -> None:
    """Test updating a holding's security using a symbol."""
    # Create a test account
    account = Account(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Test Investment Account",
        account_type=AccountType.TFSA,
        is_investment_account=True,
    )
    test_db.add(account)
    await test_db.commit()
    await test_db.refresh(account)

    # Create initial security
    security1 = Security(
        id=uuid.uuid4(),
        symbol="TEST1",
        name="Test Corporation 1",
        exchange="NASDAQ",
        currency="USD",
        security_type="EQUITY",
    )
    test_db.add(security1)
    await test_db.commit()
    await test_db.refresh(security1)

    # Create holding
    holding = Holding(
        id=uuid.uuid4(),
        account_id=account.id,
        security_id=security1.id,
        shares=Decimal("10.0"),
        average_price_per_share=Decimal("100.00"),
    )
    test_db.add(holding)
    await test_db.commit()
    await test_db.refresh(holding)

    # Ensure MSFT doesn't exist in database
    result = await test_db.execute(select(Security).where(Security.symbol == "MSFT"))
    existing_security = result.scalar_one_or_none()
    if existing_security:
        await test_db.delete(existing_security)
        await test_db.commit()

    # Update holding with new symbol
    response = await client.put(
        f"/api/v1/accounts/{account.id}/holdings/{holding.id}",
        json={
            "security_id": "MSFT",  # Symbol, not UUID
            "shares": 15.0,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Verify holding was updated
    assert Decimal(str(data["shares"])) == Decimal("15.0")
    assert data["security_id"] != str(security1.id)  # Should be different security

    # Verify MSFT was auto-synced
    new_security_id = data["security_id"]
    result = await test_db.execute(
        select(Security).where(Security.id == uuid.UUID(new_security_id))
    )
    new_security = result.scalar_one_or_none()

    assert new_security is not None
    assert new_security.symbol == "MSFT"
    assert new_security.name is not None


@pytest.mark.integration
async def test_get_holdings(
    client: AsyncClient,
    test_user,
    auth_headers: dict,
    test_db: AsyncSession,
) -> None:
    """Test getting all holdings for an account with security details."""
    # Create a test account
    account = Account(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Test Investment Account",
        account_type=AccountType.TFSA,
        is_investment_account=True,
    )
    test_db.add(account)
    await test_db.commit()
    await test_db.refresh(account)

    # Create test securities
    security1 = Security(
        id=uuid.uuid4(),
        symbol="TEST1",
        name="Test Corporation 1",
        exchange="NASDAQ",
        currency="USD",
        security_type="EQUITY",
    )
    security2 = Security(
        id=uuid.uuid4(),
        symbol="TEST2",
        name="Test Corporation 2",
        exchange="NYSE",
        currency="USD",
        security_type="EQUITY",
    )
    test_db.add_all([security1, security2])
    await test_db.commit()

    # Create holdings
    holding1 = Holding(
        id=uuid.uuid4(),
        account_id=account.id,
        security_id=security1.id,
        shares=Decimal("10.0"),
        average_price_per_share=Decimal("100.00"),
    )
    holding2 = Holding(
        id=uuid.uuid4(),
        account_id=account.id,
        security_id=security2.id,
        shares=Decimal("5.0"),
        average_price_per_share=Decimal("200.00"),
    )
    test_db.add_all([holding1, holding2])
    await test_db.commit()

    # Get holdings
    response = await client.get(
        f"/api/v1/accounts/{account.id}/holdings/",
        params={"account_id": str(account.id)},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Verify security details are included in the response
    for holding in data:
        assert "security" in holding
        assert "id" in holding["security"]
        assert "symbol" in holding["security"]
        assert "name" in holding["security"]
        assert "exchange" in holding["security"]
        assert "currency" in holding["security"]
        assert "security_type" in holding["security"]

    # Verify specific security details match
    holding1_data = next(h for h in data if h["security"]["symbol"] == "TEST1")
    assert holding1_data["security"]["name"] == "Test Corporation 1"
    assert holding1_data["security"]["exchange"] == "NASDAQ"
    assert holding1_data["security"]["security_type"] == "EQUITY"

    holding2_data = next(h for h in data if h["security"]["symbol"] == "TEST2")
    assert holding2_data["security"]["name"] == "Test Corporation 2"
    assert holding2_data["security"]["exchange"] == "NYSE"
    assert holding2_data["security"]["security_type"] == "EQUITY"


@pytest.mark.integration
async def test_get_single_holding_with_security_details(
    client: AsyncClient,
    test_user,
    auth_headers: dict,
    test_db: AsyncSession,
) -> None:
    """Test getting a single holding returns complete security details."""
    # Create a test account
    account = Account(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Test Investment Account",
        account_type=AccountType.TFSA,
        is_investment_account=True,
    )
    test_db.add(account)
    await test_db.commit()
    await test_db.refresh(account)

    # Create test security
    security = Security(
        id=uuid.uuid4(),
        symbol="AAPL",
        name="Apple Inc.",
        exchange="NASDAQ",
        currency="USD",
        security_type="EQUITY",
        sector="Technology",
        industry="Consumer Electronics",
    )
    test_db.add(security)
    await test_db.commit()

    # Create holding
    holding = Holding(
        id=uuid.uuid4(),
        account_id=account.id,
        security_id=security.id,
        shares=Decimal("10.0"),
        average_price_per_share=Decimal("150.25"),
    )
    test_db.add(holding)
    await test_db.commit()
    await test_db.refresh(holding)

    # Get single holding
    response = await client.get(
        f"/api/v1/accounts/{account.id}/holdings/{holding.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Verify holding details
    assert data["id"] == str(holding.id)
    assert Decimal(str(data["shares"])) == Decimal("10.0")
    assert Decimal(str(data["average_price_per_share"])) == Decimal("150.25")

    # Verify security details are properly nested
    assert "security" in data
    security_data = data["security"]
    assert security_data["id"] == str(security.id)
    assert security_data["symbol"] == "AAPL"
    assert security_data["name"] == "Apple Inc."
    assert security_data["exchange"] == "NASDAQ"
    assert security_data["currency"] == "USD"
    assert security_data["security_type"] == "EQUITY"
    assert security_data["sector"] == "Technology"
    assert security_data["industry"] == "Consumer Electronics"


@pytest.mark.integration
async def test_delete_holding(
    client: AsyncClient,
    test_user,
    auth_headers: dict,
    test_db: AsyncSession,
) -> None:
    """Test deleting a holding."""
    # Create a test account
    account = Account(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Test Investment Account",
        account_type=AccountType.TFSA,
        is_investment_account=True,
    )
    test_db.add(account)
    await test_db.commit()
    await test_db.refresh(account)

    # Create test security
    security = Security(
        id=uuid.uuid4(),
        symbol="TEST",
        name="Test Corporation",
        exchange="NASDAQ",
        currency="USD",
        security_type="EQUITY",
    )
    test_db.add(security)
    await test_db.commit()

    # Create holding
    holding = Holding(
        id=uuid.uuid4(),
        account_id=account.id,
        security_id=security.id,
        shares=Decimal("10.0"),
        average_price_per_share=Decimal("100.00"),
    )
    test_db.add(holding)
    await test_db.commit()
    await test_db.refresh(holding)

    # Delete holding
    response = await client.delete(
        f"/api/v1/accounts/{account.id}/holdings/{holding.id}",
        headers=auth_headers,
    )

    assert response.status_code == 204

    # Verify holding was deleted
    result = await test_db.execute(select(Holding).where(Holding.id == holding.id))
    deleted_holding = result.scalar_one_or_none()
    assert deleted_holding is None
