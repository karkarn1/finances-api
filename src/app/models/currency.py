"""Currency model for tracking different currencies (USD, EUR, CAD, etc.)."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Currency(Base):
    """Currency model for different currencies used in the application.

    Currencies are reference data representing ISO 4217 currency codes.
    They are used to track exchange rates and support multi-currency
    accounts and transactions.

    Attributes:
        code: ISO 4217 currency code (e.g., "USD", "EUR", "CAD") - primary key
        name: Full name of the currency (e.g., "US Dollar")
        symbol: Currency symbol (e.g., "$", "€", "£")
    """

    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    symbol: Mapped[str] = mapped_column(String(10))

    # Relationships
    rates_from: Mapped[list["CurrencyRate"]] = relationship(
        "CurrencyRate",
        foreign_keys="CurrencyRate.from_currency_code",
        back_populates="from_currency",
        cascade="all, delete-orphan",
    )
    rates_to: Mapped[list["CurrencyRate"]] = relationship(
        "CurrencyRate",
        foreign_keys="CurrencyRate.to_currency_code",
        back_populates="to_currency",
        cascade="all, delete-orphan",
    )
