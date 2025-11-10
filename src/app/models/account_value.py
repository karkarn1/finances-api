"""Account value model for tracking account balance history."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class AccountValue(Base, TimestampMixin):
    """Account balance snapshot at a point in time."""

    __tablename__ = "account_values"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )
    balance: Mapped[Decimal] = mapped_column(Numeric(15, 2))  # Total balance
    cash_balance: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2), nullable=True
    )  # For investment accounts

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="account_values")

    # Ensure unique balance entries per account per timestamp
    __table_args__ = (
        UniqueConstraint("account_id", "timestamp", name="uq_account_timestamp"),
    )
