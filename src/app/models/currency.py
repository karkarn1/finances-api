"""Currency model for tracking different currencies (USD, EUR, CAD, etc.)."""

import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Currency(Base, TimestampMixin):
    """Currency model for different currencies used in the application.

    Currencies are used to track exchange rates and support multi-currency
    accounts and transactions.

    Attributes:
        id: Unique identifier for the currency
        code: ISO 4217 currency code (e.g., "USD", "EUR", "CAD")
        name: Full name of the currency (e.g., "US Dollar")
        symbol: Currency symbol (e.g., "$", "€", "£")
        is_active: Whether the currency is currently active
        created_at: Timestamp when the currency was created
        updated_at: Timestamp when the currency was last updated
    """

    __tablename__ = "currencies"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, index=True
    )
    code: Mapped[str] = mapped_column(String(3), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    symbol: Mapped[str] = mapped_column(String(10))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    rates_from: Mapped[list["CurrencyRate"]] = relationship(
        "CurrencyRate",
        foreign_keys="CurrencyRate.from_currency_id",
        back_populates="from_currency",
        cascade="all, delete-orphan",
    )
    rates_to: Mapped[list["CurrencyRate"]] = relationship(
        "CurrencyRate",
        foreign_keys="CurrencyRate.to_currency_id",
        back_populates="to_currency",
        cascade="all, delete-orphan",
    )
