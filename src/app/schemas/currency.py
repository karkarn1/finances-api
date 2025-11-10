"""Currency schemas for request/response validation."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CurrencyBase(BaseModel):
    """Base currency schema."""

    code: str = Field(..., min_length=3, max_length=3, pattern="^[A-Z]{3}$")
    name: str = Field(..., min_length=1, max_length=100)
    symbol: str = Field(..., min_length=1, max_length=10)


class CurrencyCreate(CurrencyBase):
    """Schema for creating a currency."""

    is_active: bool = True


class CurrencyUpdate(BaseModel):
    """Schema for updating a currency."""

    name: str | None = Field(None, min_length=1, max_length=100)
    symbol: str | None = Field(None, min_length=1, max_length=10)
    is_active: bool | None = None


class CurrencyResponse(CurrencyBase):
    """Schema for currency response."""

    id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
