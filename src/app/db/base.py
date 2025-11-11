"""Database base class and imports."""

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all database models."""

    pass


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps.

    Uses timezone-aware datetime columns (TIMESTAMP WITH TIME ZONE in PostgreSQL)
    to match the timezone-aware default values from datetime.now(UTC).
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


__all__ = ["Base", "TimestampMixin"]
