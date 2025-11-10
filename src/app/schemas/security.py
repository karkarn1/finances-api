"""Security schemas for request/response validation."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SecurityBase(BaseModel):
    """Base security schema."""

    symbol: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=255)
    exchange: str | None = Field(None, max_length=50)
    currency: str | None = Field(None, max_length=10)
    security_type: str | None = Field(None, max_length=50)
    sector: str | None = Field(None, max_length=100)
    industry: str | None = Field(None, max_length=100)
    market_cap: float | None = None


class SecurityCreate(SecurityBase):
    """Schema for creating a security."""

    pass


class SecurityResponse(SecurityBase):
    """Schema for security response."""

    id: uuid.UUID
    last_synced_at: datetime | None
    is_syncing: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PriceData(BaseModel):
    """Schema for a single price data point."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class SecurityPricesResponse(BaseModel):
    """Schema for security prices response."""

    security: SecurityResponse
    prices: list[PriceData]
    interval_type: str
    count: int


class SyncResponse(BaseModel):
    """Schema for sync operation response."""

    security: SecurityResponse
    prices_synced: int
    message: str
