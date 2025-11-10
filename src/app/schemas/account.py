"""Account schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.account import AccountType


class AccountBase(BaseModel):
    """Base account schema."""

    name: str = Field(..., min_length=1, max_length=255)
    account_type: AccountType
    financial_institution_id: UUID | None = None
    is_investment_account: bool = False
    interest_rate: Decimal | None = Field(None, ge=0, le=100, decimal_places=2)

    @field_validator("interest_rate")
    @classmethod
    def validate_interest_rate(cls, v: Decimal | None, info) -> Decimal | None:
        """Validate interest rate is only for liability accounts."""
        if v is not None and v < 0:
            raise ValueError("Interest rate must be non-negative")
        return v


class AccountCreate(AccountBase):
    """Schema for creating an account."""

    pass


class AccountUpdate(BaseModel):
    """Schema for updating an account."""

    name: str | None = Field(None, min_length=1, max_length=255)
    account_type: AccountType | None = None
    financial_institution_id: UUID | None = None
    is_investment_account: bool | None = None
    interest_rate: Decimal | None = Field(None, ge=0, le=100, decimal_places=2)


class AccountResponse(AccountBase):
    """Schema for account response."""

    id: UUID
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AccountWithBalance(AccountResponse):
    """Account response with computed current balance."""

    current_balance: Decimal | None = None
    current_cash_balance: Decimal | None = None
