"""Holding model for tracking investment positions."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Holding(Base, TimestampMixin):
    """Investment holding (stock, ETF, etc.) in an account at a point in time."""

    __tablename__ = "holdings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("securities.id", ondelete="RESTRICT"), index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )
    shares: Mapped[Decimal] = mapped_column(Numeric(15, 6))  # Supports fractional shares
    average_price_per_share: Mapped[Decimal] = mapped_column(Numeric(15, 2))

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="holdings")
    security: Mapped["Security"] = relationship("Security")

    # Ensure unique holdings per account per security per timestamp
    __table_args__ = (
        UniqueConstraint(
            "account_id", "security_id", "timestamp", name="uq_account_security_timestamp"
        ),
    )
