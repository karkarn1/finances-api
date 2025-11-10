"""Account model for tracking financial accounts (assets and liabilities)."""

import enum
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class AccountType(str, enum.Enum):
    """Account types - assets and liabilities."""

    # Asset accounts
    CHECKING = "checking"
    SAVINGS = "savings"
    TFSA = "tfsa"
    RRSP = "rrsp"
    FHSA = "fhsa"
    MARGIN = "margin"

    # Liability accounts
    CREDIT_CARD = "credit_card"
    LINE_OF_CREDIT = "line_of_credit"
    PAYMENT_PLAN = "payment_plan"
    MORTGAGE = "mortgage"


# Asset types for helper property
ASSET_TYPES = {
    AccountType.CHECKING,
    AccountType.SAVINGS,
    AccountType.TFSA,
    AccountType.RRSP,
    AccountType.FHSA,
    AccountType.MARGIN,
}


class Account(Base, TimestampMixin):
    """Financial account (checking, savings, investment, credit card, etc.)."""

    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    financial_institution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("financial_institutions.id", ondelete="SET NULL"), nullable=True
    )
    currency_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("currencies.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255))
    account_type: Mapped[AccountType] = mapped_column(Enum(AccountType))
    is_investment_account: Mapped[bool] = mapped_column(Boolean, default=False)
    interest_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )  # For liabilities

    # Relationships
    financial_institution: Mapped["FinancialInstitution"] = relationship(
        "FinancialInstitution", back_populates="accounts"
    )
    currency: Mapped["Currency"] = relationship("Currency")
    account_values: Mapped[list["AccountValue"]] = relationship(
        "AccountValue", back_populates="account", cascade="all, delete-orphan"
    )
    holdings: Mapped[list["Holding"]] = relationship(
        "Holding", back_populates="account", cascade="all, delete-orphan"
    )

    @property
    def is_asset(self) -> bool:
        """Check if this is an asset account (vs liability)."""
        return self.account_type in ASSET_TYPES
