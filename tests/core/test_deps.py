"""Tests for core dependencies."""

from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.deps import verify_account_access
from app.models.account import Account


@pytest.mark.integration
async def test_verify_account_access_success(test_db, test_user, test_account):
    """Test successful account access verification."""
    account = await verify_account_access(
        account_id=test_account.id,
        current_user=test_user,
        db=test_db,
    )
    assert account.id == test_account.id
    assert account.user_id == test_user.id
    assert isinstance(account, Account)


@pytest.mark.integration
async def test_verify_account_access_not_found(test_db, test_user):
    """Test account not found raises 404."""
    non_existent_id = uuid4()

    with pytest.raises(HTTPException) as exc_info:
        await verify_account_access(
            account_id=non_existent_id,
            current_user=test_user,
            db=test_db,
        )

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


@pytest.mark.integration
async def test_verify_account_access_forbidden(test_db, test_user, other_user, other_user_account):
    """Test accessing another user's account raises 403."""
    with pytest.raises(HTTPException) as exc_info:
        await verify_account_access(
            account_id=other_user_account.id,
            current_user=test_user,  # Wrong user trying to access other_user's account
            db=test_db,
        )

    assert exc_info.value.status_code == 403
    assert "not authorized" in exc_info.value.detail.lower()


@pytest.mark.integration
async def test_verify_account_access_returns_account_model(test_db, test_user, test_account):
    """Test that verify_account_access returns a full Account model."""
    from app.models.account import AccountType

    account = await verify_account_access(
        account_id=test_account.id,
        current_user=test_user,
        db=test_db,
    )

    # Verify it has all expected attributes
    assert hasattr(account, "id")
    assert hasattr(account, "user_id")
    assert hasattr(account, "name")
    assert hasattr(account, "account_type")
    assert hasattr(account, "is_investment_account")
    assert account.name == "Test Checking Account"
    assert account.account_type == AccountType.CHECKING
    assert account.is_investment_account is False


@pytest.mark.integration
async def test_verify_account_access_with_different_users(
    test_db, test_user, other_user, test_account, other_user_account
):
    """Test that different users can only access their own accounts."""
    # test_user can access their account
    account1 = await verify_account_access(
        account_id=test_account.id,
        current_user=test_user,
        db=test_db,
    )
    assert account1.id == test_account.id

    # other_user can access their account
    account2 = await verify_account_access(
        account_id=other_user_account.id,
        current_user=other_user,
        db=test_db,
    )
    assert account2.id == other_user_account.id

    # test_user cannot access other_user's account
    with pytest.raises(HTTPException) as exc_info:
        await verify_account_access(
            account_id=other_user_account.id,
            current_user=test_user,
            db=test_db,
        )
    assert exc_info.value.status_code == 403

    # other_user cannot access test_user's account
    with pytest.raises(HTTPException) as exc_info:
        await verify_account_access(
            account_id=test_account.id,
            current_user=other_user,
            db=test_db,
        )
    assert exc_info.value.status_code == 403
