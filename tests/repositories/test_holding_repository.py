"""Tests for HoldingRepository."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.models.account import Account, AccountType
from app.models.holding import Holding
from app.models.security import Security
from app.repositories.holding import HoldingRepository


@pytest.mark.asyncio
async def test_get_by_account_id(test_db, test_user):
    """Test getting holdings by account ID."""
    repo = HoldingRepository(Holding, test_db)

    # Create account
    account = Account(
        user_id=test_user.id,
        name="My TFSA",
        account_type=AccountType.TFSA,
        is_investment_account=True,
    )
    test_db.add(account)
    await test_db.commit()
    await test_db.refresh(account)

    # Create securities
    security1 = Security(symbol="AAPL", name="Apple Inc.", currency="USD")
    security2 = Security(symbol="GOOGL", name="Alphabet Inc.", currency="USD")
    test_db.add_all([security1, security2])
    await test_db.commit()
    await test_db.refresh(security1)
    await test_db.refresh(security2)

    # Create holdings at different timestamps to ensure ordering
    now = datetime.now(UTC)
    holding1 = Holding(
        account_id=account.id,
        security_id=security1.id,
        timestamp=now - timedelta(seconds=10),  # Older
        shares=Decimal("10.5"),
        average_price_per_share=Decimal("150.00"),
    )
    holding2 = Holding(
        account_id=account.id,
        security_id=security2.id,
        timestamp=now,  # Newer
        shares=Decimal("5.0"),
        average_price_per_share=Decimal("2500.00"),
    )
    test_db.add_all([holding1, holding2])
    await test_db.commit()

    # Get holdings
    holdings = await repo.get_by_account_id(account.id)

    assert len(holdings) == 2
    # Should be ordered by timestamp descending (most recent first)
    assert holdings[0].shares == Decimal("5.0")  # Newer holding
    assert holdings[1].shares == Decimal("10.5")  # Older holding


@pytest.mark.asyncio
async def test_get_by_account_id_empty(test_db, test_user):
    """Test getting holdings when account has none."""
    repo = HoldingRepository(Holding, test_db)

    # Create empty account
    account = Account(
        user_id=test_user.id,
        name="Empty Account",
        account_type=AccountType.TFSA,
        is_investment_account=True,
    )
    test_db.add(account)
    await test_db.commit()
    await test_db.refresh(account)

    holdings = await repo.get_by_account_id(account.id)
    assert len(holdings) == 0


@pytest.mark.asyncio
async def test_get_by_account_id_pagination(test_db, test_user):
    """Test pagination of holdings."""
    repo = HoldingRepository(Holding, test_db)

    # Create account and security
    account = Account(
        user_id=test_user.id,
        name="My TFSA",
        account_type=AccountType.TFSA,
        is_investment_account=True,
    )
    security = Security(symbol="AAPL", name="Apple Inc.", currency="USD")
    test_db.add_all([account, security])
    await test_db.commit()
    await test_db.refresh(account)
    await test_db.refresh(security)

    # Create 5 holdings at different timestamps
    now = datetime.now(UTC)
    for i in range(5):
        holding = Holding(
            account_id=account.id,
            security_id=security.id,
            timestamp=now - timedelta(days=i),
            shares=Decimal(f"{i + 1}.0"),
            average_price_per_share=Decimal("150.00"),
        )
        test_db.add(holding)
    await test_db.commit()

    # Test pagination
    page1 = await repo.get_by_account_id(account.id, skip=0, limit=2)
    page2 = await repo.get_by_account_id(account.id, skip=2, limit=2)

    assert len(page1) == 2
    assert len(page2) == 2
    assert page1[0].id != page2[0].id


@pytest.mark.asyncio
async def test_get_by_account_and_security(test_db, test_user):
    """Test getting most recent holding by account and security."""
    repo = HoldingRepository(Holding, test_db)

    # Create account and security
    account = Account(
        user_id=test_user.id,
        name="My TFSA",
        account_type=AccountType.TFSA,
        is_investment_account=True,
    )
    security = Security(symbol="AAPL", name="Apple Inc.", currency="USD")
    test_db.add_all([account, security])
    await test_db.commit()
    await test_db.refresh(account)
    await test_db.refresh(security)

    # Create holdings at different timestamps
    now = datetime.now(UTC)
    older_holding = Holding(
        account_id=account.id,
        security_id=security.id,
        timestamp=now - timedelta(days=7),
        shares=Decimal("5.0"),
        average_price_per_share=Decimal("140.00"),
    )
    newer_holding = Holding(
        account_id=account.id,
        security_id=security.id,
        timestamp=now,
        shares=Decimal("10.0"),
        average_price_per_share=Decimal("150.00"),
    )
    test_db.add_all([older_holding, newer_holding])
    await test_db.commit()
    await test_db.refresh(newer_holding)

    # Should return the most recent holding
    holding = await repo.get_by_account_and_security(account.id, "AAPL")

    assert holding is not None
    assert holding.id == newer_holding.id
    assert holding.shares == Decimal("10.0")
    # Should have security loaded
    assert holding.security.symbol == "AAPL"


@pytest.mark.asyncio
async def test_get_by_account_and_security_case_insensitive(test_db, test_user):
    """Test that security symbol lookup is case-insensitive."""
    repo = HoldingRepository(Holding, test_db)

    # Create account and security
    account = Account(
        user_id=test_user.id,
        name="My TFSA",
        account_type=AccountType.TFSA,
        is_investment_account=True,
    )
    security = Security(symbol="AAPL", name="Apple Inc.", currency="USD")
    test_db.add_all([account, security])
    await test_db.commit()
    await test_db.refresh(account)
    await test_db.refresh(security)

    holding = Holding(
        account_id=account.id,
        security_id=security.id,
        timestamp=datetime.now(UTC),
        shares=Decimal("10.0"),
        average_price_per_share=Decimal("150.00"),
    )
    test_db.add(holding)
    await test_db.commit()

    # Test lowercase
    found = await repo.get_by_account_and_security(account.id, "aapl")
    assert found is not None

    # Test mixed case
    found_mixed = await repo.get_by_account_and_security(account.id, "AaPl")
    assert found_mixed is not None


@pytest.mark.asyncio
async def test_get_by_account_and_security_not_found(test_db, test_user):
    """Test getting holding when it doesn't exist."""
    repo = HoldingRepository(Holding, test_db)

    account = Account(
        user_id=test_user.id,
        name="My TFSA",
        account_type=AccountType.TFSA,
        is_investment_account=True,
    )
    test_db.add(account)
    await test_db.commit()
    await test_db.refresh(account)

    holding = await repo.get_by_account_and_security(account.id, "NONEXISTENT")
    assert holding is None


@pytest.mark.asyncio
async def test_exists_for_security(test_db, test_user):
    """Test checking if holding exists for security."""
    repo = HoldingRepository(Holding, test_db)

    # Create account and security
    account = Account(
        user_id=test_user.id,
        name="My TFSA",
        account_type=AccountType.TFSA,
        is_investment_account=True,
    )
    security = Security(symbol="AAPL", name="Apple Inc.", currency="USD")
    test_db.add_all([account, security])
    await test_db.commit()
    await test_db.refresh(account)
    await test_db.refresh(security)

    holding = Holding(
        account_id=account.id,
        security_id=security.id,
        timestamp=datetime.now(UTC),
        shares=Decimal("10.0"),
        average_price_per_share=Decimal("150.00"),
    )
    test_db.add(holding)
    await test_db.commit()

    # Should exist
    assert await repo.exists_for_security(account.id, "AAPL") is True

    # Should not exist
    assert await repo.exists_for_security(account.id, "GOOGL") is False


@pytest.mark.asyncio
async def test_get_holdings_with_security(test_db, test_user):
    """Test getting holdings with eagerly loaded security data."""
    repo = HoldingRepository(Holding, test_db)

    # Create account and security
    account = Account(
        user_id=test_user.id,
        name="My TFSA",
        account_type=AccountType.TFSA,
        is_investment_account=True,
    )
    security = Security(symbol="AAPL", name="Apple Inc.", currency="USD")
    test_db.add_all([account, security])
    await test_db.commit()
    await test_db.refresh(account)
    await test_db.refresh(security)

    holding = Holding(
        account_id=account.id,
        security_id=security.id,
        timestamp=datetime.now(UTC),
        shares=Decimal("10.0"),
        average_price_per_share=Decimal("150.00"),
    )
    test_db.add(holding)
    await test_db.commit()

    # Get holdings with security loaded
    holdings = await repo.get_holdings_with_security(account.id)

    assert len(holdings) == 1
    # Security should be loaded (no additional query needed)
    assert holdings[0].security.symbol == "AAPL"
    assert holdings[0].security.name == "Apple Inc."


@pytest.mark.asyncio
async def test_get_holdings_at_timestamp(test_db, test_user):
    """Test getting holdings at a specific timestamp."""
    repo = HoldingRepository(Holding, test_db)

    # Create account and security
    account = Account(
        user_id=test_user.id,
        name="My TFSA",
        account_type=AccountType.TFSA,
        is_investment_account=True,
    )
    security = Security(symbol="AAPL", name="Apple Inc.", currency="USD")
    test_db.add_all([account, security])
    await test_db.commit()
    await test_db.refresh(account)
    await test_db.refresh(security)

    # Create holdings at different timestamps
    now = datetime.now(UTC)
    old_holding = Holding(
        account_id=account.id,
        security_id=security.id,
        timestamp=now - timedelta(days=30),
        shares=Decimal("5.0"),
        average_price_per_share=Decimal("140.00"),
    )
    mid_holding = Holding(
        account_id=account.id,
        security_id=security.id,
        timestamp=now - timedelta(days=15),
        shares=Decimal("8.0"),
        average_price_per_share=Decimal("145.00"),
    )
    new_holding = Holding(
        account_id=account.id,
        security_id=security.id,
        timestamp=now,
        shares=Decimal("10.0"),
        average_price_per_share=Decimal("150.00"),
    )
    test_db.add_all([old_holding, mid_holding, new_holding])
    await test_db.commit()
    await test_db.refresh(mid_holding)

    # Get holdings as of 15 days ago
    holdings = await repo.get_holdings_at_timestamp(account.id, now - timedelta(days=15))

    # Should return the mid holding (most recent as of that timestamp)
    assert len(holdings) == 1
    assert holdings[0].shares == Decimal("8.0")


@pytest.mark.asyncio
async def test_holding_isolation_between_accounts(test_db, test_user):
    """Test that holdings are properly isolated between accounts."""
    repo = HoldingRepository(Holding, test_db)

    # Create two accounts
    account1 = Account(
        user_id=test_user.id,
        name="Account 1",
        account_type=AccountType.TFSA,
        is_investment_account=True,
    )
    account2 = Account(
        user_id=test_user.id,
        name="Account 2",
        account_type=AccountType.RRSP,
        is_investment_account=True,
    )
    security = Security(symbol="AAPL", name="Apple Inc.", currency="USD")
    test_db.add_all([account1, account2, security])
    await test_db.commit()
    await test_db.refresh(account1)
    await test_db.refresh(account2)
    await test_db.refresh(security)

    # Create holdings in different accounts
    now = datetime.now(UTC)
    holding1 = Holding(
        account_id=account1.id,
        security_id=security.id,
        timestamp=now,
        shares=Decimal("10.0"),
        average_price_per_share=Decimal("150.00"),
    )
    holding2 = Holding(
        account_id=account2.id,
        security_id=security.id,
        timestamp=now,
        shares=Decimal("20.0"),
        average_price_per_share=Decimal("155.00"),
    )
    test_db.add_all([holding1, holding2])
    await test_db.commit()

    # Each account should only see its own holdings
    holdings1 = await repo.get_by_account_id(account1.id)
    holdings2 = await repo.get_by_account_id(account2.id)

    assert len(holdings1) == 1
    assert len(holdings2) == 1
    assert holdings1[0].shares == Decimal("10.0")
    assert holdings2[0].shares == Decimal("20.0")
