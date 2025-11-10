"""SecurityPrice repository for price data operations."""

import uuid
from datetime import datetime

from sqlalchemy import delete, select

from app.models.security_price import SecurityPrice
from app.repositories.base import BaseRepository


class SecurityPriceRepository(BaseRepository[SecurityPrice]):
    """Repository for SecurityPrice model with price-specific queries.

    Provides all price-related database operations including date range
    queries, interval filtering, bulk operations, and data management.

    Example:
        >>> repo = SecurityPriceRepository(SecurityPrice, db)
        >>> prices = await repo.get_by_security_and_date_range(
        ...     security_id,
        ...     start_date,
        ...     end_date
        ... )
    """

    async def get_by_security_and_date_range(
        self,
        security_id: uuid.UUID,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d",
    ) -> list[SecurityPrice]:
        """Get prices for security within date range.

        Args:
            security_id: UUID of the security
            start_date: Start datetime (inclusive)
            end_date: End datetime (inclusive)
            interval: Price interval ("1m", "1h", "1d", "1wk")

        Returns:
            List of price records ordered by timestamp ascending

        Example:
            >>> from datetime import datetime, timedelta, UTC
            >>> end = datetime.now(UTC)
            >>> start = end - timedelta(days=30)
            >>> prices = await repo.get_by_security_and_date_range(
            ...     security.id,
            ...     start,
            ...     end,
            ...     interval="1d"
            ... )
            >>> for price in prices:
            ...     print(f"{price.timestamp}: ${price.close}")
        """
        result = await self.db.execute(
            select(SecurityPrice)
            .where(
                (SecurityPrice.security_id == security_id)
                & (SecurityPrice.interval_type == interval)
                & (SecurityPrice.timestamp >= start_date)
                & (SecurityPrice.timestamp <= end_date)
            )
            .order_by(SecurityPrice.timestamp.asc())
        )
        return list(result.scalars().all())

    async def get_latest(
        self,
        security_id: uuid.UUID,
        interval: str = "1d",
    ) -> SecurityPrice | None:
        """Get latest price for security at specified interval.

        Args:
            security_id: UUID of the security
            interval: Price interval ("1m", "1h", "1d", "1wk")

        Returns:
            Latest price record if found, None otherwise

        Example:
            >>> latest = await repo.get_latest(security.id, interval="1d")
            >>> if latest:
            ...     print(f"Latest close: ${latest.close}")
        """
        result = await self.db.execute(
            select(SecurityPrice)
            .where(
                (SecurityPrice.security_id == security_id)
                & (SecurityPrice.interval_type == interval)
            )
            .order_by(SecurityPrice.timestamp.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def bulk_create(
        self,
        prices: list[SecurityPrice],
    ) -> list[SecurityPrice]:
        """Bulk insert price records.

        More efficient than individual inserts when adding many prices.
        Uses add_all for batch insertion.

        Args:
            prices: List of SecurityPrice instances to insert

        Returns:
            List of inserted price instances (not yet committed)

        Note:
            Caller must commit the transaction.

        Example:
            >>> prices = [
            ...     SecurityPrice(
            ...         security_id=security.id,
            ...         timestamp=datetime.now(UTC),
            ...         open=100.0,
            ...         high=101.0,
            ...         low=99.0,
            ...         close=100.5,
            ...         volume=1000000,
            ...         interval_type="1d"
            ...     ),
            ...     # ... more prices
            ... ]
            >>> inserted = await repo.bulk_create(prices)
            >>> await db.commit()
            >>> print(f"Inserted {len(inserted)} price records")
        """
        self.db.add_all(prices)
        await self.db.flush()
        return prices

    async def delete_by_security(self, security_id: uuid.UUID) -> int:
        """Delete all prices for a security.

        Useful when re-syncing a security and want to clear old data.

        Args:
            security_id: UUID of the security

        Returns:
            Number of price records deleted

        Note:
            Caller must commit the transaction.

        Example:
            >>> deleted_count = await repo.delete_by_security(security.id)
            >>> await db.commit()
            >>> print(f"Deleted {deleted_count} price records")
        """
        result = await self.db.execute(
            delete(SecurityPrice).where(SecurityPrice.security_id == security_id)
        )
        await self.db.flush()
        return result.rowcount  # type: ignore

    async def delete_by_security_and_interval(
        self,
        security_id: uuid.UUID,
        interval: str,
    ) -> int:
        """Delete all prices for a security at specific interval.

        More targeted deletion than delete_by_security when you only
        want to clear a specific interval type.

        Args:
            security_id: UUID of the security
            interval: Price interval to delete ("1m", "1h", "1d", "1wk")

        Returns:
            Number of price records deleted

        Note:
            Caller must commit the transaction.

        Example:
            >>> # Delete only minute-level data
            >>> deleted = await repo.delete_by_security_and_interval(
            ...     security.id,
            ...     "1m"
            ... )
            >>> await db.commit()
        """
        result = await self.db.execute(
            delete(SecurityPrice).where(
                (SecurityPrice.security_id == security_id)
                & (SecurityPrice.interval_type == interval)
            )
        )
        await self.db.flush()
        return result.rowcount  # type: ignore

    async def get_count_by_security(
        self,
        security_id: uuid.UUID,
        interval: str | None = None,
    ) -> int:
        """Get count of price records for a security.

        Useful for verifying sync completeness and data availability.

        Args:
            security_id: UUID of the security
            interval: Optional interval filter

        Returns:
            Count of price records

        Example:
            >>> # Get total price count
            >>> total = await repo.get_count_by_security(security.id)
            >>> print(f"Total prices: {total}")
            >>>
            >>> # Get count for specific interval
            >>> daily_count = await repo.get_count_by_security(
            ...     security.id,
            ...     interval="1d"
            ... )
            >>> print(f"Daily prices: {daily_count}")
        """
        query = select(SecurityPrice).where(SecurityPrice.security_id == security_id)

        if interval:
            query = query.where(SecurityPrice.interval_type == interval)

        result = await self.db.execute(query)
        prices = result.scalars().all()
        return len(prices)
