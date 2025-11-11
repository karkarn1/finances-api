"""Account value repository for account value database operations."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from app.models.account_value import AccountValue
from app.repositories.base import BaseRepository
from app.schemas.account_value import AccountValueCreate, AccountValueUpdate


class AccountValueRepository(BaseRepository[AccountValue]):
    """Repository for AccountValue model with account value-specific queries.

    Provides all account value-related database operations including lookups
    by account, timestamp filtering, and historical value tracking.

    Example:
        >>> repo = AccountValueRepository(AccountValue, db)
        >>> values = await repo.get_by_account_id(account_id)
    """

    async def get_by_account_id(
        self,
        account_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AccountValue]:
        """Get all account values for a specific account with pagination.

        Args:
            account_id: The account ID to filter values by
            skip: Number of records to skip (offset)
            limit: Maximum number of records to return

        Returns:
            List of account values for the account, ordered by timestamp
            descending (most recent first)

        Example:
            >>> values = await repo.get_by_account_id(
            ...     account_id=account_id,
            ...     skip=0,
            ...     limit=50
            ... )
            >>> for value in values:
            ...     print(f"{value.timestamp}: ${value.balance}")
        """
        result = await self.db.execute(
            select(AccountValue)
            .where(AccountValue.account_id == account_id)
            .order_by(AccountValue.timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_id_and_account(
        self,
        value_id: UUID,
        account_id: UUID,
    ) -> AccountValue | None:
        """Get account value by ID, ensuring it belongs to the specified account.

        Args:
            value_id: Account value ID
            account_id: Account ID (for ownership verification)

        Returns:
            AccountValue if found and belongs to account, None otherwise

        Example:
            >>> value = await repo.get_by_id_and_account(
            ...     value_id=value_id,
            ...     account_id=account_id
            ... )
            >>> if value:
            ...     print(f"Balance: ${value.balance}")
        """
        result = await self.db.execute(
            select(AccountValue).where(
                AccountValue.id == value_id,
                AccountValue.account_id == account_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_latest_by_account(
        self,
        account_id: UUID,
    ) -> AccountValue | None:
        """Get the most recent account value for an account.

        Args:
            account_id: Account ID

        Returns:
            Most recent AccountValue or None if no values exist

        Example:
            >>> latest = await repo.get_latest_by_account(account_id)
            >>> if latest:
            ...     print(f"Current balance: ${latest.balance}")
        """
        result = await self.db.execute(
            select(AccountValue)
            .where(AccountValue.account_id == account_id)
            .order_by(AccountValue.timestamp.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_values_in_range(
        self,
        account_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[AccountValue]:
        """Get account values within a date range.

        Args:
            account_id: Account ID
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)

        Returns:
            List of account values within the date range, ordered by
            timestamp ascending

        Example:
            >>> from datetime import datetime, timedelta, UTC
            >>> end = datetime.now(UTC)
            >>> start = end - timedelta(days=30)
            >>> values = await repo.get_values_in_range(
            ...     account_id=account_id,
            ...     start_date=start,
            ...     end_date=end
            ... )
            >>> print(f"Found {len(values)} values in the last 30 days")
        """
        result = await self.db.execute(
            select(AccountValue)
            .where(AccountValue.account_id == account_id)
            .where(AccountValue.timestamp >= start_date)
            .where(AccountValue.timestamp <= end_date)
            .order_by(AccountValue.timestamp.asc())
        )
        return list(result.scalars().all())

    async def exists_for_account(
        self,
        account_id: UUID,
    ) -> bool:
        """Check if any account values exist for an account.

        Args:
            account_id: Account ID to check

        Returns:
            True if at least one account value exists, False otherwise

        Example:
            >>> if not await repo.exists_for_account(account_id):
            ...     print("No balance history for this account")
        """
        value = await self.get_latest_by_account(account_id)
        return value is not None

    async def create_account_value(
        self,
        *,
        obj_in: AccountValueCreate,
    ) -> AccountValue:
        """Create a new account value with type-safe Pydantic validation.

        Args:
            obj_in: Validated account value creation data (Pydantic model)

        Returns:
            The created account value (not yet committed)

        Note:
            Caller must commit the transaction.

        Example:
            >>> from app.schemas.account_value import AccountValueCreate
            >>> from datetime import datetime, UTC
            >>> value_data = AccountValueCreate(
            ...     account_id=account_id,
            ...     timestamp=datetime.now(UTC),
            ...     balance=10000.00,
            ...     cash_balance=5000.00,
            ... )
            >>> value = await repo.create_account_value(obj_in=value_data)
            >>> await db.commit()
        """
        return await self.create(obj_in=obj_in)

    async def update_account_value(
        self,
        *,
        db_obj: AccountValue,
        obj_in: AccountValueUpdate,
    ) -> AccountValue:
        """Update an account value with type-safe Pydantic validation.

        Args:
            db_obj: The existing account value to update
            obj_in: Validated account value update data (Pydantic model)

        Returns:
            The updated account value (not yet committed)

        Note:
            Caller must commit the transaction.

        Example:
            >>> from app.schemas.account_value import AccountValueUpdate
            >>> value = await repo.get(value_id)
            >>> update_data = AccountValueUpdate(balance=12000.00)
            >>> updated = await repo.update_account_value(db_obj=value, obj_in=update_data)
            >>> await db.commit()
        """
        return await self.update(db_obj=db_obj, obj_in=obj_in)
