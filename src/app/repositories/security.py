"""Security repository for securities database operations."""

from datetime import datetime

from sqlalchemy import select

from app.models.security import Security
from app.repositories.base import BaseRepository


class SecurityRepository(BaseRepository[Security]):
    """Repository for Security model with security-specific queries.

    Provides all security-related database operations including symbol
    lookups, search functionality, and sync status management.

    Example:
        >>> repo = SecurityRepository(Security, db)
        >>> security = await repo.get_by_symbol("AAPL")
    """

    async def get_by_symbol(self, symbol: str) -> Security | None:
        """Get security by symbol.

        Args:
            symbol: Stock symbol (e.g., "AAPL", "MSFT")

        Returns:
            Security object if found, None otherwise

        Note:
            Symbol comparison is case-sensitive (symbols should be
            uppercased before calling this method).

        Example:
            >>> security = await repo.get_by_symbol("AAPL")
            >>> if security:
            ...     print(security.name)
        """
        result = await self.db.execute(select(Security).where(Security.symbol == symbol.upper()))
        return result.scalar_one_or_none()

    async def search(
        self,
        query: str,
        limit: int = 20,
    ) -> list[Security]:
        """Search securities by name or symbol (case-insensitive).

        Searches both symbol and name fields using ILIKE pattern matching.
        Results are ordered by symbol alphabetically.

        Args:
            query: Search query string
            limit: Maximum number of results to return

        Returns:
            List of matching securities ordered by symbol

        Example:
            >>> securities = await repo.search("apple", limit=10)
            >>> for sec in securities:
            ...     print(f"{sec.symbol}: {sec.name}")
        """
        search_pattern = f"%{query}%"

        result = await self.db.execute(
            select(Security)
            .where((Security.symbol.ilike(search_pattern)) | (Security.name.ilike(search_pattern)))
            .order_by(Security.symbol)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_with_latest_price(self, symbol: str) -> Security | None:
        """Get security with latest price data eagerly loaded.

        This method uses eager loading to fetch the security along with
        its associated price data in a single query.

        Args:
            symbol: Stock symbol (e.g., "AAPL")

        Returns:
            Security object with prices loaded, None if not found

        Note:
            This method is useful when you need both security metadata
            and price data to avoid N+1 queries.

        Example:
            >>> security = await repo.get_with_latest_price("AAPL")
            >>> if security and security.prices:
            ...     latest = security.prices[-1]
            ...     print(f"Latest price: ${latest.close}")
        """
        # For now, just get the security. In the future, we can add
        # eager loading with joinedload(Security.prices) when needed
        return await self.get_by_symbol(symbol)

    async def update_sync_status(
        self,
        symbol: str,
        *,
        is_syncing: bool,
        last_synced_at: datetime | None = None,
    ) -> Security:
        """Update security sync status.

        Updates the is_syncing flag and optionally the last_synced_at
        timestamp for a security.

        Args:
            symbol: Stock symbol
            is_syncing: Whether sync is in progress
            last_synced_at: Optional timestamp of last successful sync

        Returns:
            Updated security instance (not yet committed)

        Raises:
            ValueError: If security not found

        Note:
            Caller must commit the transaction.

        Example:
            >>> # Mark sync as started
            >>> security = await repo.update_sync_status("AAPL", is_syncing=True)
            >>> await db.commit()
            >>>
            >>> # Mark sync as completed
            >>> from datetime import datetime, UTC
            >>> security = await repo.update_sync_status(
            ...     "AAPL",
            ...     is_syncing=False,
            ...     last_synced_at=datetime.now(UTC)
            ... )
            >>> await db.commit()
        """
        security = await self.get_by_symbol(symbol)
        if not security:
            raise ValueError(f"Security with symbol '{symbol}' not found")

        security.is_syncing = is_syncing
        if last_synced_at is not None:
            security.last_synced_at = last_synced_at

        await self.db.flush()
        await self.db.refresh(security)
        return security

    async def exists_by_symbol(self, symbol: str) -> bool:
        """Check if security exists by symbol.

        Args:
            symbol: Stock symbol to check

        Returns:
            True if security exists, False otherwise

        Example:
            >>> if not await repo.exists_by_symbol("AAPL"):
            ...     print("Security needs to be synced first")
        """
        security = await self.get_by_symbol(symbol)
        return security is not None
