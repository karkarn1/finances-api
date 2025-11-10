"""Tests for AccountRepository."""

from decimal import Decimal

import pytest

from app.models.account import Account, AccountType
from app.repositories.account import AccountRepository


@pytest.mark.asyncio
async def test_get_by_user_id(test_db, test_user):
    """Test getting accounts by user ID."""
    repo = AccountRepository(Account, test_db)

    # Create test accounts
    account1 = Account(
        user_id=test_user.id,
        name="My TFSA",
        account_type=AccountType.TFSA,
        is_investment_account=True,
    )
    account2 = Account(
        user_id=test_user.id,
        name="Checking Account",
        account_type=AccountType.CHECKING,
        is_investment_account=False,
    )
    test_db.add_all([account1, account2])
    await test_db.commit()

    # Get accounts
    accounts = await repo.get_by_user_id(test_user.id)

    assert len(accounts) == 2
    # Should be ordered by name
    assert accounts[0].name == "Checking Account"
    assert accounts[1].name == "My TFSA"


@pytest.mark.asyncio
async def test_get_by_user_id_empty(test_db, test_user):
    """Test getting accounts when user has none."""
    repo = AccountRepository(Account, test_db)
    accounts = await repo.get_by_user_id(test_user.id)

    assert len(accounts) == 0


@pytest.mark.asyncio
async def test_get_by_user_id_pagination(test_db, test_user):
    """Test pagination of user accounts."""
    repo = AccountRepository(Account, test_db)

    # Create 5 test accounts
    for i in range(5):
        account = Account(
            user_id=test_user.id,
            name=f"Account {i}",
            account_type=AccountType.CHECKING,
            is_investment_account=False,
        )
        test_db.add(account)
    await test_db.commit()

    # Test pagination
    page1 = await repo.get_by_user_id(test_user.id, skip=0, limit=2)
    page2 = await repo.get_by_user_id(test_user.id, skip=2, limit=2)

    assert len(page1) == 2
    assert len(page2) == 2
    assert page1[0].id != page2[0].id


@pytest.mark.asyncio
async def test_get_by_user_and_name(test_db, test_user):
    """Test getting account by user ID and name."""
    repo = AccountRepository(Account, test_db)

    account = Account(
        user_id=test_user.id,
        name="My TFSA",
        account_type=AccountType.TFSA,
        is_investment_account=True,
    )
    test_db.add(account)
    await test_db.commit()
    await test_db.refresh(account)

    # Test exact match
    found = await repo.get_by_user_and_name(test_user.id, "My TFSA")
    assert found is not None
    assert found.id == account.id

    # Test case-insensitive match
    found_lowercase = await repo.get_by_user_and_name(test_user.id, "my tfsa")
    assert found_lowercase is not None
    assert found_lowercase.id == account.id


@pytest.mark.asyncio
async def test_get_by_user_and_name_not_found(test_db, test_user):
    """Test getting account by name when it doesn't exist."""
    repo = AccountRepository(Account, test_db)

    found = await repo.get_by_user_and_name(test_user.id, "Nonexistent")
    assert found is None


@pytest.mark.asyncio
async def test_exists_by_name(test_db, test_user):
    """Test checking if account name exists for user."""
    repo = AccountRepository(Account, test_db)

    account = Account(
        user_id=test_user.id,
        name="My TFSA",
        account_type=AccountType.TFSA,
        is_investment_account=True,
    )
    test_db.add(account)
    await test_db.commit()

    # Should exist
    assert await repo.exists_by_name(test_user.id, "My TFSA") is True
    assert await repo.exists_by_name(test_user.id, "my tfsa") is True  # Case-insensitive

    # Should not exist
    assert await repo.exists_by_name(test_user.id, "Nonexistent") is False


@pytest.mark.asyncio
async def test_get_by_type(test_db, test_user):
    """Test getting accounts by type."""
    repo = AccountRepository(Account, test_db)

    # Create accounts of different types
    tfsa = Account(
        user_id=test_user.id,
        name="My TFSA",
        account_type=AccountType.TFSA,
        is_investment_account=True,
    )
    rrsp = Account(
        user_id=test_user.id,
        name="My RRSP",
        account_type=AccountType.RRSP,
        is_investment_account=True,
    )
    checking = Account(
        user_id=test_user.id,
        name="Checking",
        account_type=AccountType.CHECKING,
        is_investment_account=False,
    )
    test_db.add_all([tfsa, rrsp, checking])
    await test_db.commit()

    # Get TFSAs only
    tfsas = await repo.get_by_type(test_user.id, AccountType.TFSA.value)
    assert len(tfsas) == 1
    assert tfsas[0].account_type == AccountType.TFSA

    # Get RRSPs only
    rrsps = await repo.get_by_type(test_user.id, AccountType.RRSP.value)
    assert len(rrsps) == 1
    assert rrsps[0].account_type == AccountType.RRSP


@pytest.mark.asyncio
async def test_get_investment_accounts(test_db, test_user):
    """Test getting investment accounts only."""
    repo = AccountRepository(Account, test_db)

    # Create investment and non-investment accounts
    tfsa = Account(
        user_id=test_user.id,
        name="My TFSA",
        account_type=AccountType.TFSA,
        is_investment_account=True,
    )
    checking = Account(
        user_id=test_user.id,
        name="Checking",
        account_type=AccountType.CHECKING,
        is_investment_account=False,
    )
    rrsp = Account(
        user_id=test_user.id,
        name="My RRSP",
        account_type=AccountType.RRSP,
        is_investment_account=True,
    )
    test_db.add_all([tfsa, checking, rrsp])
    await test_db.commit()

    # Get investment accounts
    investment_accounts = await repo.get_investment_accounts(test_user.id)

    assert len(investment_accounts) == 2
    assert all(acc.is_investment_account for acc in investment_accounts)
    # Should be ordered by name
    assert investment_accounts[0].name == "My RRSP"
    assert investment_accounts[1].name == "My TFSA"


@pytest.mark.asyncio
async def test_get_asset_accounts(test_db, test_user):
    """Test getting asset accounts (vs liability accounts)."""
    repo = AccountRepository(Account, test_db)

    # Create asset accounts
    tfsa = Account(
        user_id=test_user.id,
        name="My TFSA",
        account_type=AccountType.TFSA,
        is_investment_account=True,
    )
    checking = Account(
        user_id=test_user.id,
        name="Checking",
        account_type=AccountType.CHECKING,
        is_investment_account=False,
    )

    # Create liability accounts
    credit_card = Account(
        user_id=test_user.id,
        name="Credit Card",
        account_type=AccountType.CREDIT_CARD,
        is_investment_account=False,
    )
    mortgage = Account(
        user_id=test_user.id,
        name="Mortgage",
        account_type=AccountType.MORTGAGE,
        is_investment_account=False,
        interest_rate=Decimal("3.5"),
    )

    test_db.add_all([tfsa, checking, credit_card, mortgage])
    await test_db.commit()

    # Get asset accounts only
    asset_accounts = await repo.get_asset_accounts(test_user.id)

    assert len(asset_accounts) == 2
    assert all(acc.is_asset for acc in asset_accounts)
    assert asset_accounts[0].name == "Checking"
    assert asset_accounts[1].name == "My TFSA"


@pytest.mark.asyncio
async def test_account_isolation_between_users(test_db, test_user, test_superuser):
    """Test that accounts are properly isolated between users."""
    repo = AccountRepository(Account, test_db)

    # Create account for test_user
    user_account = Account(
        user_id=test_user.id,
        name="User TFSA",
        account_type=AccountType.TFSA,
        is_investment_account=True,
    )

    # Create account for test_superuser
    admin_account = Account(
        user_id=test_superuser.id,
        name="Admin TFSA",
        account_type=AccountType.TFSA,
        is_investment_account=True,
    )

    test_db.add_all([user_account, admin_account])
    await test_db.commit()

    # Each user should only see their own accounts
    user_accounts = await repo.get_by_user_id(test_user.id)
    admin_accounts = await repo.get_by_user_id(test_superuser.id)

    assert len(user_accounts) == 1
    assert len(admin_accounts) == 1
    assert user_accounts[0].id == user_account.id
    assert admin_accounts[0].id == admin_account.id
