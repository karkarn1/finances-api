"""Currency rate schemas for request/response validation."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CurrencyRateBase(BaseModel):
    """Base currency rate schema."""

    from_currency_code: str = Field(..., min_length=3, max_length=3, pattern="^[A-Z]{3}$")
    to_currency_code: str = Field(..., min_length=3, max_length=3, pattern="^[A-Z]{3}$")
    rate: Decimal = Field(..., gt=0, decimal_places=8)
    date: date


class CurrencyRateCreate(CurrencyRateBase):
    """Schema for creating a currency rate."""

    pass


class CurrencyRateResponse(BaseModel):
    """Schema for currency rate response."""

    id: uuid.UUID
    from_currency_code: str
    to_currency_code: str
    rate: Decimal
    date: date
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CurrencyRatesResponse(BaseModel):
    """Schema for multiple currency rates response."""

    base_currency: str
    date: date
    rates: dict[str, Decimal]
    count: int


class SyncRatesResponse(BaseModel):
    """Schema for sync rates operation response."""

    base_currency: str
    synced_count: int
    failed_count: int
    date: date
    message: str
