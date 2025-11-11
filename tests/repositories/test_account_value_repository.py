"""Tests for AccountValueRepository."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.account_value import AccountValue
from app.repositories.account_value import AccountValueRepository


@pytest.mark.integration
async def test_get_by_account_id(test_db: AsyncSession, test_account: Account):
    """Test getting account values by account ID."""
    repo = AccountValueRepository(AccountValue, test_db)

    # Create test account values
    now = datetime.now(UTC)
    value1 = AccountValue(
        account_id=test_account.id,
        balance=Decimal("1000.00"),
        timestamp=now - timedelta(days=2),
    )
    value2 = AccountValue(
        account_id=test_account.id,
        balance=Decimal("1100.00"),
        timestamp=now - timedelta(days=1),
    )
    value3 = AccountValue(
        account_id=test_account.id,
        balance=Decimal("1200.00"),
        timestamp=now,
    )
    test_db.add_all([value1, value2, value3])
    await test_db.commit()

    # Get all values
    values = await repo.get_by_account_id(test_account.id)

    assert len(values) == 3
    # Should be ordered by timestamp descending (most recent first)
    assert values[0].balance == Decimal("1200.00")
    assert values[1].balance == Decimal("1100.00")
    assert values[2].balance == Decimal("1000.00")


@pytest.mark.integration
async def test_get_by_account_id_with_pagination(test_db: AsyncSession, test_account: Account):
    """Test getting account values with pagination."""
    repo = AccountValueRepository(AccountValue, test_db)

    # Create 5 account values
    now = datetime.now(UTC)
    for i in range(5):
        value = AccountValue(
            account_id=test_account.id,
            balance=Decimal(f"{1000 + i * 100}.00"),
            timestamp=now - timedelta(days=4 - i),
        )
        test_db.add(value)
    await test_db.commit()

    # Get first 2 values
    values = await repo.get_by_account_id(test_account.id, skip=0, limit=2)
    assert len(values) == 2
    assert values[0].balance == Decimal("1400.00")  # Most recent
    assert values[1].balance == Decimal("1300.00")

    # Get next 2 values
    values = await repo.get_by_account_id(test_account.id, skip=2, limit=2)
    assert len(values) == 2
    assert values[0].balance == Decimal("1200.00")
    assert values[1].balance == Decimal("1100.00")


@pytest.mark.integration
async def test_get_by_id_and_account(test_db: AsyncSession, test_account: Account):
    """Test getting account value by ID with account verification."""
    repo = AccountValueRepository(AccountValue, test_db)

    # Create test account value
    value = AccountValue(
        account_id=test_account.id,
        balance=Decimal("1000.00"),
        timestamp=datetime.now(UTC),
    )
    test_db.add(value)
    await test_db.commit()
    await test_db.refresh(value)

    # Get value by ID and account
    result = await repo.get_by_id_and_account(value.id, test_account.id)
    assert result is not None
    assert result.id == value.id
    assert result.balance == Decimal("1000.00")


@pytest.mark.integration
async def test_get_by_id_and_account_wrong_account(
    test_db: AsyncSession, test_account: Account, other_user_account: Account
):
    """Test that wrong account cannot access account value."""
    repo = AccountValueRepository(AccountValue, test_db)

    # Create account value for test_account
    value = AccountValue(
        account_id=test_account.id,
        balance=Decimal("1000.00"),
        timestamp=datetime.now(UTC),
    )
    test_db.add(value)
    await test_db.commit()
    await test_db.refresh(value)

    # Try to get with other_user_account ID
    result = await repo.get_by_id_and_account(value.id, other_user_account.id)
    assert result is None


@pytest.mark.integration
async def test_get_latest_by_account(test_db: AsyncSession, test_account: Account):
    """Test getting the most recent account value."""
    repo = AccountValueRepository(AccountValue, test_db)

    # Create multiple account values
    now = datetime.now(UTC)
    value1 = AccountValue(
        account_id=test_account.id,
        balance=Decimal("1000.00"),
        timestamp=now - timedelta(days=2),
    )
    value2 = AccountValue(
        account_id=test_account.id,
        balance=Decimal("1100.00"),
        timestamp=now - timedelta(days=1),
    )
    value3 = AccountValue(
        account_id=test_account.id,
        balance=Decimal("1200.00"),
        timestamp=now,
    )
    test_db.add_all([value1, value2, value3])
    await test_db.commit()

    # Get latest
    latest = await repo.get_latest_by_account(test_account.id)
    assert latest is not None
    assert latest.balance == Decimal("1200.00")
    assert latest.timestamp == now


@pytest.mark.integration
async def test_get_latest_by_account_no_values(test_db: AsyncSession, test_account: Account):
    """Test getting latest when no values exist."""
    repo = AccountValueRepository(AccountValue, test_db)

    latest = await repo.get_latest_by_account(test_account.id)
    assert latest is None


@pytest.mark.integration
async def test_get_values_in_range(test_db: AsyncSession, test_account: Account):
    """Test getting account values within a date range."""
    repo = AccountValueRepository(AccountValue, test_db)

    # Create account values spanning 30 days
    now = datetime.now(UTC)
    for i in range(30):
        value = AccountValue(
            account_id=test_account.id,
            balance=Decimal(f"{1000 + i * 10}.00"),
            timestamp=now - timedelta(days=29 - i),
        )
        test_db.add(value)
    await test_db.commit()

    # Get values from last 7 days
    start_date = now - timedelta(days=7)
    end_date = now
    values = await repo.get_values_in_range(test_account.id, start_date, end_date)

    # Should have 8 values (days 0-7 inclusive)
    assert len(values) == 8
    # Should be ordered by timestamp ascending
    assert values[0].balance == Decimal("1220.00")  # Oldest in range
    assert values[-1].balance == Decimal("1290.00")  # Most recent


@pytest.mark.integration
async def test_exists_for_account(test_db: AsyncSession, test_account: Account):
    """Test checking if account values exist."""
    repo = AccountValueRepository(AccountValue, test_db)

    # No values yet
    assert await repo.exists_for_account(test_account.id) is False

    # Add a value
    value = AccountValue(
        account_id=test_account.id,
        balance=Decimal("1000.00"),
        timestamp=datetime.now(UTC),
    )
    test_db.add(value)
    await test_db.commit()

    # Now should exist
    assert await repo.exists_for_account(test_account.id) is True


@pytest.mark.integration
async def test_create_account_value(test_db: AsyncSession, test_account: Account):
    """Test creating a new account value."""
    repo = AccountValueRepository(AccountValue, test_db)

    now = datetime.now(UTC)
    value = await repo.create(
        obj_in={
            "account_id": test_account.id,
            "balance": Decimal("5000.00"),
            "cash_balance": Decimal("500.00"),
            "timestamp": now,
        }
    )

    assert value.id is not None
    assert value.balance == Decimal("5000.00")
    assert value.cash_balance == Decimal("500.00")
    # Compare without timezone info since SQLite doesn't store timezone
    assert value.timestamp.replace(tzinfo=UTC) == now


@pytest.mark.integration
async def test_update_account_value(test_db: AsyncSession, test_account: Account):
    """Test updating an account value."""
    repo = AccountValueRepository(AccountValue, test_db)

    # Create value
    value = AccountValue(
        account_id=test_account.id,
        balance=Decimal("1000.00"),
        timestamp=datetime.now(UTC),
    )
    test_db.add(value)
    await test_db.commit()
    await test_db.refresh(value)

    # Update it
    updated = await repo.update(
        db_obj=value,
        obj_in={"balance": Decimal("2000.00")},
    )

    assert updated.balance == Decimal("2000.00")


@pytest.mark.integration
async def test_delete_account_value(test_db: AsyncSession, test_account: Account):
    """Test deleting an account value."""
    repo = AccountValueRepository(AccountValue, test_db)

    # Create value
    value = AccountValue(
        account_id=test_account.id,
        balance=Decimal("1000.00"),
        timestamp=datetime.now(UTC),
    )
    test_db.add(value)
    await test_db.commit()
    await test_db.refresh(value)

    # Delete it
    await repo.delete(id=value.id)
    await test_db.commit()

    # Verify it's gone
    result = await repo.get(value.id)
    assert result is None
