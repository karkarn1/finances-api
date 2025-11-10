"""SecurityPrice model for storing OHLCV price data."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class SecurityPrice(Base, TimestampMixin):
    """OHLCV price data for securities at different time intervals."""

    __tablename__ = "security_prices"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, index=True
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("securities.id", ondelete="CASCADE"), index=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(BigInteger)
    interval_type: Mapped[str] = mapped_column(
        String(10)
    )  # "1m", "1h", "1d", "1wk"

    # Relationship back to security
    security: Mapped["Security"] = relationship("Security", back_populates="prices")

    # Composite indexes for efficient querying
    __table_args__ = (
        Index("idx_security_time", "security_id", "timestamp"),
        Index("idx_security_interval_time", "security_id", "interval_type", "timestamp"),
    )
