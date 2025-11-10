"""Holding repository for holding-specific database operations."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.holding import Holding
from app.repositories.base import BaseRepository


class HoldingRepository(BaseRepository[Holding]):
    """Repository for Holding model with holding-specific queries.

    Provides all holding-related database operations including lookups
    by account, security, and timestamp filtering.

    Example:
        >>> repo = HoldingRepository(Holding, db)
        >>> holdings = await repo.get_by_account_id(account_id)
    """

    async def get_by_account_id(
        self,
        account_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Holding]:
        """Get all holdings for a specific account with pagination.

        Args:
            account_id: The account ID to filter holdings by
            skip: Number of records to skip (offset)
            limit: Maximum number of records to return

        Returns:
            List of holdings in the account, ordered by timestamp descending
            (most recent first)

        Example:
            >>> holdings = await repo.get_by_account_id(
            ...     account_id=account_id,
            ...     skip=0,
            ...     limit=50
            ... )
            >>> for holding in holdings:
            ...     print(f"{holding.security.symbol}: {holding.shares} shares")
        """
        result = await self.db.execute(
            select(Holding)
            .where(Holding.account_id == account_id)
            .order_by(Holding.timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_account_and_security(
        self,
        account_id: UUID,
        security_symbol: str,
    ) -> Holding | None:
        """Get the most recent holding by account and security symbol.

        Since holdings are snapshots at different timestamps, this returns
        the most recent holding for the given account and security.

        Args:
            account_id: The account ID
            security_symbol: The security symbol (e.g., "AAPL")

        Returns:
            Most recent Holding object if found, None otherwise

        Note:
            Eagerly loads the security relationship for immediate access
            to security details.

        Example:
            >>> holding = await repo.get_by_account_and_security(
            ...     account_id=account_id,
            ...     security_symbol="AAPL"
            ... )
            >>> if holding:
            ...     print(f"Shares: {holding.shares}")
            ...     print(f"Avg Price: ${holding.average_price_per_share}")
        """
        result = await self.db.execute(
            select(Holding)
            .options(joinedload(Holding.security))
            .join(Holding.security)
            .where(Holding.account_id == account_id)
            .where(Holding.security.has(symbol=security_symbol.upper()))
            .order_by(Holding.timestamp.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def exists_for_security(
        self,
        account_id: UUID,
        security_symbol: str,
    ) -> bool:
        """Check if holding exists for account and security.

        Args:
            account_id: The account ID to check
            security_symbol: The security symbol to check

        Returns:
            True if any holding exists for this account and security,
            False otherwise

        Example:
            >>> if not await repo.exists_for_security(
            ...     account_id=account_id,
            ...     security_symbol="AAPL"
            ... ):
            ...     print("No holdings for AAPL in this account")
        """
        holding = await self.get_by_account_and_security(account_id, security_symbol)
        return holding is not None

    async def get_latest_holdings_by_account(
        self,
        account_id: UUID,
    ) -> list[Holding]:
        """Get the latest holdings for each security in an account.

        For each unique security in the account, returns the most recent
        holding snapshot. This is useful for getting the current portfolio
        composition.

        Args:
            account_id: The account ID to get holdings for

        Returns:
            List of latest holdings, one per unique security, ordered by
            security symbol

        Note:
            This performs a subquery to find the max timestamp for each
            security, then fetches those specific holdings.

        Example:
            >>> latest = await repo.get_latest_holdings_by_account(account_id)
            >>> for holding in latest:
            ...     symbol = holding.security.symbol
            ...     shares = holding.shares
            ...     print(f"{symbol}: {shares} shares")
        """
        # Subquery to find the latest timestamp for each security in this account
        latest_timestamps = (
            select(
                Holding.security_id,
                select(Holding.timestamp)
                .where(Holding.account_id == account_id)
                .where(Holding.security_id == Holding.security_id)
                .order_by(Holding.timestamp.desc())
                .limit(1)
                .scalar_subquery()
                .label("max_timestamp"),
            )
            .where(Holding.account_id == account_id)
            .distinct()
            .subquery()
        )

        # Get holdings matching those timestamps
        result = await self.db.execute(
            select(Holding)
            .options(joinedload(Holding.security))
            .join(
                latest_timestamps,
                (Holding.security_id == latest_timestamps.c.security_id)
                & (Holding.timestamp == latest_timestamps.c.max_timestamp),
            )
            .where(Holding.account_id == account_id)
            .order_by(Holding.security_id)
        )
        return list(result.scalars().all())

    async def get_holdings_at_timestamp(
        self,
        account_id: UUID,
        timestamp: datetime,
    ) -> list[Holding]:
        """Get holdings for an account at or before a specific timestamp.

        For each security, returns the most recent holding as of the given
        timestamp. Useful for historical portfolio snapshots.

        Args:
            account_id: The account ID
            timestamp: The timestamp to query holdings at

        Returns:
            List of holdings as of the timestamp, ordered by security symbol

        Example:
            >>> from datetime import datetime, UTC
            >>> last_month = datetime.now(UTC).replace(day=1)
            >>> holdings = await repo.get_holdings_at_timestamp(
            ...     account_id=account_id,
            ...     timestamp=last_month
            ... )
            >>> print(f"Had {len(holdings)} positions last month")
        """
        result = await self.db.execute(
            select(Holding)
            .options(joinedload(Holding.security))
            .where(Holding.account_id == account_id)
            .where(Holding.timestamp <= timestamp)
            .order_by(Holding.security_id, Holding.timestamp.desc())
        )

        # Group by security and take the first (most recent) for each
        holdings_by_security: dict[UUID, Holding] = {}
        for holding in result.scalars().all():
            if holding.security_id not in holdings_by_security:
                holdings_by_security[holding.security_id] = holding

        return list(holdings_by_security.values())

    async def get_holdings_with_security(
        self,
        account_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Holding]:
        """Get holdings with eagerly loaded security data.

        This method is optimized to avoid N+1 queries by eager loading
        the security relationship using joinedload.

        Args:
            account_id: The account ID to filter by
            skip: Number of records to skip (offset)
            limit: Maximum number of records to return

        Returns:
            List of holdings with security data loaded, ordered by timestamp
            descending

        Example:
            >>> holdings = await repo.get_holdings_with_security(account_id)
            >>> for holding in holdings:
            ...     # No additional query needed for security
            ...     print(f"{holding.security.symbol}: {holding.shares} shares")
        """
        result = await self.db.execute(
            select(Holding)
            .options(joinedload(Holding.security))
            .where(Holding.account_id == account_id)
            .order_by(Holding.timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
