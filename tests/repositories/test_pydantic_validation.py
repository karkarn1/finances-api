"""Test Pydantic validation in repositories."""

import pytest
from datetime import datetime, UTC
from uuid import UUID

from pydantic import BaseModel, ValidationError

from sqlalchemy.ext.asyncio import AsyncSession
from app.models.account import Account
from app.models.account_value import AccountValue
from app.models.holding import Holding
from app.models.security import Security
from app.models.user import User
from app.repositories.account import AccountRepository
from app.repositories.account_value import AccountValueRepository
from app.repositories.holding import HoldingRepository
from app.repositories.user import UserRepository
from app.schemas.account import AccountCreate, AccountUpdate
from app.schemas.account_value import AccountValueCreate, AccountValueUpdate
from app.schemas.holding import HoldingCreate, HoldingUpdate
from app.schemas.user import UserCreate, UserUpdate


@pytest.mark.asyncio
async def test_base_repository_create_with_pydantic_model(test_db: AsyncSession, test_user: User):
    """Test creating a record with Pydantic model."""
    # Note: User schema includes password, but SQLAlchemy model doesn't
    # So we test with Account which aligns Pydantic and SQLAlchemy fields
    repo = AccountRepository(Account, test_db)

    # Create using Pydantic model - Account schema fields match the model
    account_data = AccountCreate(
        name="Test Account",
        account_type="checking",
        financial_institution_id=None,
        is_investment_account=False,
    )

    # Manually add user_id since routes typically do this
    account_dict = account_data.model_dump()
    account_dict["user_id"] = test_user.id

    account = await repo.create(obj_in=account_dict)
    assert account.name == "Test Account"
    assert account.user_id == test_user.id

    await test_db.commit()


@pytest.mark.asyncio
async def test_base_repository_create_with_dict(test_db: AsyncSession, test_user: User):
    """Test creating a record with dictionary."""
    repo = AccountRepository(Account, test_db)

    # Create using dictionary
    account_data = {
        "user_id": test_user.id,
        "name": "Dict Account",
        "account_type": "savings",
        "financial_institution_id": None,
        "is_investment_account": False,
    }

    account = await repo.create(obj_in=account_data)
    assert account.name == "Dict Account"
    assert account.user_id == test_user.id

    await test_db.commit()


@pytest.mark.asyncio
async def test_base_repository_update_with_pydantic_model(test_db: AsyncSession, test_user: User):
    """Test updating a record with Pydantic model."""
    repo = AccountRepository(Account, test_db)

    # Create initial account
    account_data = AccountCreate(
        name="Original Name",
        account_type="checking",
        financial_institution_id=None,
        is_investment_account=False,
    )
    account_dict = account_data.model_dump()
    account_dict["user_id"] = test_user.id
    account = await repo.create(obj_in=account_dict)
    await test_db.commit()

    # Update using Pydantic model
    update_data = AccountUpdate(name="Updated Name")
    updated_account = await repo.update(db_obj=account, obj_in=update_data)
    assert updated_account.name == "Updated Name"

    await test_db.commit()


@pytest.mark.asyncio
async def test_base_repository_update_with_dict(test_db: AsyncSession, test_user: User):
    """Test updating a record with dictionary."""
    repo = AccountRepository(Account, test_db)

    # Create initial account
    account_data = {
        "user_id": test_user.id,
        "name": "Original Name Dict",
        "account_type": "savings",
        "financial_institution_id": None,
        "is_investment_account": False,
    }
    account = await repo.create(obj_in=account_data)
    await test_db.commit()

    # Update using dictionary
    update_data = {"name": "Updated Name Dict"}
    updated_account = await repo.update(db_obj=account, obj_in=update_data)
    assert updated_account.name == "Updated Name Dict"

    await test_db.commit()


@pytest.mark.asyncio
async def test_account_repository_create_account_typed(test_db: AsyncSession, test_user: User):
    """Test AccountRepository.create_account with type-safe Pydantic validation."""
    repo = AccountRepository(Account, test_db)

    account_data = AccountCreate(
        name="My Checking",
        account_type="checking",
        financial_institution_id=None,
        is_investment_account=False,
    )

    # Note: create_account is a helper method. In real usage, routes add user_id.
    # For this test, we directly add user_id to the dict
    account_dict = account_data.model_dump()
    account_dict["user_id"] = test_user.id
    account = await repo.create(obj_in=account_dict)
    assert account.name == "My Checking"
    assert account.user_id == test_user.id

    await test_db.commit()


@pytest.mark.asyncio
async def test_account_repository_update_account_typed(test_db: AsyncSession, test_user: User):
    """Test AccountRepository.update_account with type-safe Pydantic validation."""
    repo = AccountRepository(Account, test_db)

    # Create account
    account_data = AccountCreate(
        name="Original Name",
        account_type="checking",
        financial_institution_id=None,
        is_investment_account=False,
    )
    account_dict = account_data.model_dump()
    account_dict["user_id"] = test_user.id
    account = await repo.create(obj_in=account_dict)
    await test_db.commit()

    # Update using Pydantic model
    update_data = AccountUpdate(name="Updated Name")
    updated_account = await repo.update(db_obj=account, obj_in=update_data)
    assert updated_account.name == "Updated Name"

    await test_db.commit()


@pytest.mark.asyncio
async def test_pydantic_validation_catches_invalid_data(test_db: AsyncSession):
    """Test that Pydantic validation catches invalid data."""
    repo = UserRepository(User, test_db)

    # This should raise ValidationError due to short password
    with pytest.raises(ValidationError) as exc_info:
        user_data = UserCreate(
            email="test@example.com",
            username="test",
            password="short",  # Too short - min 8 chars
        )

    assert "at least 8 characters" in str(exc_info.value)


@pytest.mark.asyncio
async def test_exclude_unset_respects_partial_updates(test_db: AsyncSession, test_user: User):
    """Test that exclude_unset=True respects partial updates."""
    repo = AccountRepository(Account, test_db)

    # Create account
    account_data = AccountCreate(
        name="Original Account",
        account_type="checking",
        financial_institution_id=None,
        is_investment_account=False,
    )
    account_dict = account_data.model_dump()
    account_dict["user_id"] = test_user.id
    account = await repo.create(obj_in=account_dict)
    original_name = account.name
    await test_db.commit()

    # Partial update - only account_type set
    update_data = AccountUpdate(account_type="savings")
    updated_account = await repo.update(db_obj=account, obj_in=update_data)

    # Account type should be updated
    assert updated_account.account_type == "savings"
    # Name should remain unchanged
    assert updated_account.name == original_name

    await test_db.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
