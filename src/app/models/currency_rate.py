"""Currency rate model for tracking exchange rates between currencies."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class CurrencyRate(Base, TimestampMixin):
    """Exchange rate between two currencies for a specific date.

    Stores historical exchange rates to support accurate multi-currency
    calculations and reporting.

    Attributes:
        id: Unique identifier for the rate
        from_currency_id: Source currency UUID
        to_currency_id: Target currency UUID
        rate: Exchange rate (e.g., 1 USD = 1.35 CAD means rate=1.35)
        date: Date for which this rate is valid
        created_at: Timestamp when the rate was created
        updated_at: Timestamp when the rate was last updated
    """

    __tablename__ = "currency_rates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, index=True)
    from_currency_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("currencies.id", ondelete="CASCADE"), index=True
    )
    to_currency_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("currencies.id", ondelete="CASCADE"), index=True
    )
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    date: Mapped[date] = mapped_column(Date, index=True)

    # Relationships
    from_currency: Mapped["Currency"] = relationship(
        "Currency",
        foreign_keys=[from_currency_id],
        back_populates="rates_from",
    )
    to_currency: Mapped["Currency"] = relationship(
        "Currency",
        foreign_keys=[to_currency_id],
        back_populates="rates_to",
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "from_currency_id",
            "to_currency_id",
            "date",
            name="uq_currency_rate_from_to_date",
        ),
        Index("ix_currency_rates_from_to_date", "from_currency_id", "to_currency_id", "date"),
    )
