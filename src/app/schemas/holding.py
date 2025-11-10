"""Holding schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.security import SecurityResponse


class HoldingBase(BaseModel):
    """Base holding schema."""

    security_id: UUID | str  # Accept UUID (existing security) or symbol (auto-sync)
    shares: Decimal = Field(..., gt=0, decimal_places=6)
    average_price_per_share: Decimal = Field(..., ge=0, decimal_places=2)
    timestamp: datetime | None = None

    @field_validator("shares")
    @classmethod
    def validate_shares(cls, v: Decimal) -> Decimal:
        """Validate shares is positive."""
        if v <= 0:
            raise ValueError("Shares must be greater than 0")
        return v

    @field_validator("average_price_per_share")
    @classmethod
    def validate_price(cls, v: Decimal) -> Decimal:
        """Validate price is non-negative."""
        if v < 0:
            raise ValueError("Average price per share cannot be negative")
        return v


class HoldingCreate(HoldingBase):
    """Schema for creating a holding."""

    pass


class HoldingUpdate(BaseModel):
    """Schema for updating a holding."""

    security_id: UUID | str | None = None  # Accept UUID or symbol
    shares: Decimal | None = Field(None, gt=0, decimal_places=6)
    average_price_per_share: Decimal | None = Field(None, ge=0, decimal_places=2)
    timestamp: datetime | None = None

    @field_validator("shares")
    @classmethod
    def validate_shares(cls, v: Decimal | None) -> Decimal | None:
        """Validate shares is positive."""
        if v is not None and v <= 0:
            raise ValueError("Shares must be greater than 0")
        return v

    @field_validator("average_price_per_share")
    @classmethod
    def validate_price(cls, v: Decimal | None) -> Decimal | None:
        """Validate price is non-negative."""
        if v is not None and v < 0:
            raise ValueError("Average price per share cannot be negative")
        return v


class HoldingResponse(HoldingBase):
    """Schema for holding response."""

    id: UUID
    account_id: UUID
    security: SecurityResponse  # Nested security details
    timestamp: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HoldingWithSecurity(HoldingResponse):
    """Holding response with security details."""

    security_symbol: str | None = None
    security_name: str | None = None
    current_price: Decimal | None = None
    market_value: Decimal | None = None  # shares * current_price
    gain_loss: Decimal | None = None  # market_value - (shares * avg_price)
