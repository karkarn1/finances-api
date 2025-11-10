"""Account value schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AccountValueBase(BaseModel):
    """Base account value schema."""

    balance: Decimal = Field(..., decimal_places=2)
    cash_balance: Decimal | None = Field(None, decimal_places=2)
    timestamp: datetime | None = None

    @field_validator("balance", "cash_balance")
    @classmethod
    def validate_balances(cls, v: Decimal | None) -> Decimal | None:
        """Validate balance values."""
        if v is not None and v < 0:
            raise ValueError("Balance cannot be negative")
        return v


class AccountValueCreate(AccountValueBase):
    """Schema for creating an account value entry."""

    @field_validator("cash_balance")
    @classmethod
    def validate_cash_balance_for_investment(cls, v: Decimal | None, info) -> Decimal | None:
        """Validate that cash_balance is provided for investment accounts."""
        # Note: This validation will be enhanced in the route handler
        # where we have access to the account information
        return v


class AccountValueUpdate(BaseModel):
    """Schema for updating an account value entry."""

    balance: Decimal | None = Field(None, decimal_places=2)
    cash_balance: Decimal | None = Field(None, decimal_places=2)
    timestamp: datetime | None = None

    @field_validator("balance", "cash_balance")
    @classmethod
    def validate_balances(cls, v: Decimal | None) -> Decimal | None:
        """Validate balance values."""
        if v is not None and v < 0:
            raise ValueError("Balance cannot be negative")
        return v


class AccountValueResponse(AccountValueBase):
    """Schema for account value response."""

    id: UUID
    account_id: UUID
    timestamp: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
