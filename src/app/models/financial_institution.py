"""Financial institution model for tracking banks, brokerages, etc."""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class FinancialInstitution(Base, TimestampMixin):
    """Financial institution (bank, brokerage, etc.)."""

    __tablename__ = "financial_institutions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    accounts: Mapped[list["Account"]] = relationship(
        "Account", back_populates="financial_institution", cascade="all, delete-orphan"
    )
