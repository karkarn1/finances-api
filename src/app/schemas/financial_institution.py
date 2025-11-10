"""Financial institution schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class FinancialInstitutionBase(BaseModel):
    """Base financial institution schema."""

    name: str = Field(..., min_length=1, max_length=255)
    url: HttpUrl | str | None = None


class FinancialInstitutionCreate(FinancialInstitutionBase):
    """Schema for creating a financial institution."""

    pass


class FinancialInstitutionUpdate(BaseModel):
    """Schema for updating a financial institution."""

    name: str | None = Field(None, min_length=1, max_length=255)
    url: HttpUrl | str | None = None


class FinancialInstitutionResponse(FinancialInstitutionBase):
    """Schema for financial institution response."""

    id: UUID
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
