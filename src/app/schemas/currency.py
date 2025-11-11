"""Currency schemas for request/response validation."""

from pydantic import BaseModel, Field


class CurrencyBase(BaseModel):
    """Base currency schema."""

    code: str = Field(..., min_length=3, max_length=3, pattern="^[A-Z]{3}$")
    name: str = Field(..., min_length=1, max_length=100)
    symbol: str = Field(..., min_length=1, max_length=10)


class CurrencyCreate(CurrencyBase):
    """Schema for creating a currency."""

    pass


class CurrencyUpdate(BaseModel):
    """Schema for updating a currency."""

    name: str | None = Field(None, min_length=1, max_length=100)
    symbol: str | None = Field(None, min_length=1, max_length=10)


class CurrencyResponse(CurrencyBase):
    """Schema for currency response."""

    model_config = {"from_attributes": True}
