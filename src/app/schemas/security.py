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
    in_database: bool = True  # Indicates if security exists in DB or fetched from yfinance

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
    requested_start: datetime | None = None
    requested_end: datetime | None = None
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    data_completeness: str = "complete"  # "complete", "partial", "sparse", "empty"


class SyncResponse(BaseModel):
    """Schema for sync operation response."""

    security: SecurityResponse
    prices_synced: int
    message: str


class BulkSyncResult(BaseModel):
    """Result for a single security in bulk sync operation."""

    symbol: str
    status: str  # "success", "failed", "skipped"
    message: str
    prices_synced: int = 0
    error: str | None = None


class BulkSyncResponse(BaseModel):
    """Schema for bulk sync operation response."""

    total_requested: int
    successfully_added: int
    failed_additions: int
    successfully_synced: int
    failed_syncs: int
    skipped: int
    results: list[BulkSyncResult]
    message: str


class BulkSyncStartResponse(BaseModel):
    """Schema for bulk sync start response (immediate return)."""

    message: str = "Bulk sync job started"
    total_securities: int
    status: str = "running"
