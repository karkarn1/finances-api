"""Account repository for account-specific database operations."""

from sqlalchemy import select

from app.models.account import Account
from app.repositories.base import BaseRepository
from app.schemas.account import AccountCreate, AccountUpdate


class AccountRepository(BaseRepository[Account]):
    """Repository for Account model with account-specific queries.

    Provides all account-related database operations including lookups
    by user, account name, and filtering by account status.

    Example:
        >>> repo = AccountRepository(Account, db)
        >>> accounts = await repo.get_by_user_id(user_id)
    """

    async def get_by_user_id(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Account]:
        """Get all accounts for a specific user with pagination.

        Args:
            user_id: The user ID to filter accounts by
            skip: Number of records to skip (offset)
            limit: Maximum number of records to return

        Returns:
            List of accounts owned by the user, ordered by name

        Example:
            >>> accounts = await repo.get_by_user_id(user_id=1, skip=0, limit=20)
            >>> for account in accounts:
            ...     print(f"{account.name}: {account.account_type}")
        """
        result = await self.db.execute(
            select(Account)
            .where(Account.user_id == user_id)
            .order_by(Account.name)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_user_and_name(
        self,
        user_id: int,
        name: str,
    ) -> Account | None:
        """Get account by user ID and account name.

        Args:
            user_id: The user ID that owns the account
            name: The account name to search for

        Returns:
            Account object if found, None otherwise

        Note:
            Account names should be unique per user but case-insensitive
            matching is used for flexibility.

        Example:
            >>> account = await repo.get_by_user_and_name(
            ...     user_id=1,
            ...     name="My TFSA"
            ... )
            >>> if account:
            ...     print(f"Found account: {account.id}")
        """
        result = await self.db.execute(
            select(Account)
            .where(Account.user_id == user_id)
            .where(Account.name.ilike(name))  # Case-insensitive
        )
        return result.scalar_one_or_none()

    async def exists_by_name(
        self,
        user_id: int,
        name: str,
    ) -> bool:
        """Check if account name exists for user (for uniqueness validation).

        Args:
            user_id: The user ID to check within
            name: The account name to check

        Returns:
            True if account name exists for this user, False otherwise

        Note:
            Uses case-insensitive comparison to prevent users from creating
            "TFSA" and "tfsa" as separate accounts.

        Example:
            >>> if await repo.exists_by_name(user_id=1, name="My TFSA"):
            ...     raise ValueError("Account name already exists")
        """
        account = await self.get_by_user_and_name(user_id, name)
        return account is not None

    async def get_by_type(
        self,
        user_id: int,
        account_type: str,
    ) -> list[Account]:
        """Get all accounts of a specific type for a user.

        Args:
            user_id: The user ID to filter by
            account_type: The account type to filter by (e.g., "tfsa", "rrsp")

        Returns:
            List of accounts matching the type, ordered by name

        Example:
            >>> tfsas = await repo.get_by_type(user_id=1, account_type="tfsa")
            >>> for account in tfsas:
            ...     print(f"TFSA: {account.name}")
        """
        result = await self.db.execute(
            select(Account)
            .where(Account.user_id == user_id)
            .where(Account.account_type == account_type)
            .order_by(Account.name)
        )
        return list(result.scalars().all())

    async def get_investment_accounts(
        self,
        user_id: int,
    ) -> list[Account]:
        """Get all investment accounts for a user.

        Investment accounts are accounts that can hold securities (stocks,
        ETFs, bonds, etc.) such as TFSA, RRSP, FHSA, and margin accounts.

        Args:
            user_id: The user ID to filter by

        Returns:
            List of investment accounts, ordered by name

        Example:
            >>> investment_accounts = await repo.get_investment_accounts(user_id=1)
            >>> for account in investment_accounts:
            ...     print(f"{account.name} has {len(account.holdings)} holdings")
        """
        result = await self.db.execute(
            select(Account)
            .where(Account.user_id == user_id)
            .where(Account.is_investment_account == True)  # noqa: E712
            .order_by(Account.name)
        )
        return list(result.scalars().all())

    async def get_asset_accounts(
        self,
        user_id: int,
    ) -> list[Account]:
        """Get all asset accounts for a user (vs liability accounts).

        Asset accounts include checking, savings, TFSA, RRSP, FHSA, margin.
        Liability accounts include credit cards, mortgages, loans, etc.

        Args:
            user_id: The user ID to filter by

        Returns:
            List of asset accounts, ordered by name

        Note:
            Uses the Account.is_asset property which checks the account_type
            against the ASSET_TYPES set.

        Example:
            >>> assets = await repo.get_asset_accounts(user_id=1)
            >>> total_value = sum(a.balance for a in assets)
        """
        result = await self.db.execute(
            select(Account).where(Account.user_id == user_id).order_by(Account.name)
        )
        accounts = list(result.scalars().all())

        # Filter using the model property
        return [account for account in accounts if account.is_asset]

    async def create_account(
        self,
        *,
        obj_in: AccountCreate,
    ) -> Account:
        """Create a new account with type-safe Pydantic validation.

        Args:
            obj_in: Validated account creation data (Pydantic model)

        Returns:
            The created account (not yet committed)

        Note:
            Caller must commit the transaction.

        Example:
            >>> from app.schemas.account import AccountCreate
            >>> account_data = AccountCreate(
            ...     user_id=1,
            ...     name="My Checking",
            ...     account_type="checking",
            ...     is_investment_account=False,
            ... )
            >>> account = await repo.create_account(obj_in=account_data)
            >>> await db.commit()
        """
        return await self.create(obj_in=obj_in)

    async def update_account(
        self,
        *,
        db_obj: Account,
        obj_in: AccountUpdate,
    ) -> Account:
        """Update an account with type-safe Pydantic validation.

        Args:
            db_obj: The existing account to update
            obj_in: Validated account update data (Pydantic model)

        Returns:
            The updated account (not yet committed)

        Note:
            Caller must commit the transaction.

        Example:
            >>> from app.schemas.account import AccountUpdate
            >>> account = await repo.get(account_id)
            >>> update_data = AccountUpdate(name="Updated Checking")
            >>> updated = await repo.update_account(db_obj=account, obj_in=update_data)
            >>> await db.commit()
        """
        return await self.update(db_obj=db_obj, obj_in=obj_in)
