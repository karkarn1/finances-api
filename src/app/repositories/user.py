"""User repository for user-specific database operations."""

from sqlalchemy import select

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model with user-specific queries.

    Provides all user-related database operations including lookups
    by email, username, and various user filters.

    Example:
        >>> repo = UserRepository(User, db)
        >>> user = await repo.get_by_email("test@example.com")
    """

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email address.

        Args:
            email: The email address to search for

        Returns:
            User object if found, None otherwise

        Example:
            >>> user = await repo.get_by_email("test@example.com")
            >>> if user:
            ...     print(user.username)
        """
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """Get user by username.

        Args:
            username: The username to search for

        Returns:
            User object if found, None otherwise

        Example:
            >>> user = await repo.get_by_username("johndoe")
            >>> if user:
            ...     print(user.email)
        """
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_username_or_email(self, identifier: str) -> User | None:
        """Get user by username or email address.

        Tries username first, then falls back to email lookup if not found.
        Useful for login flows where users can authenticate with either.

        Args:
            identifier: Username or email address

        Returns:
            User object if found, None otherwise

        Example:
            >>> # Can use username
            >>> user = await repo.get_by_username_or_email("johndoe")
            >>> # Or email
            >>> user = await repo.get_by_username_or_email("john@example.com")
        """
        # Try username first
        user = await self.get_by_username(identifier)

        # If not found, try email
        if not user:
            user = await self.get_by_email(identifier)

        return user

    async def exists_by_email(self, email: str) -> bool:
        """Check if email address is already registered.

        Args:
            email: Email address to check

        Returns:
            True if email exists, False otherwise

        Example:
            >>> if await repo.exists_by_email("test@example.com"):
            ...     raise ValueError("Email already registered")
        """
        user = await self.get_by_email(email)
        return user is not None

    async def exists_by_username(self, username: str) -> bool:
        """Check if username is already registered.

        Args:
            username: Username to check

        Returns:
            True if username exists, False otherwise

        Example:
            >>> if await repo.exists_by_username("johndoe"):
            ...     raise ValueError("Username already taken")
        """
        user = await self.get_by_username(username)
        return user is not None

    async def get_active_users(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> list[User]:
        """Get all active users with pagination.

        Args:
            skip: Number of records to skip (offset)
            limit: Maximum number of records to return

        Returns:
            List of active users

        Example:
            >>> active_users = await repo.get_active_users(skip=0, limit=50)
            >>> print(f"Found {len(active_users)} active users")
        """
        result = await self.db.execute(
            select(User)
            .where(User.is_active == True)  # noqa: E712
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_users_with_reset_tokens(self) -> list[User]:
        """Get all users with non-null reset tokens.

        Used for password reset token validation where we need to
        find the user by verifying the token against hashed values.

        Returns:
            List of users with reset tokens

        Example:
            >>> users = await repo.get_users_with_reset_tokens()
            >>> for user in users:
            ...     if verify_password(plaintext_token, user.reset_token):
            ...         # Found the user
            ...         break
        """
        result = await self.db.execute(select(User).where(User.reset_token.isnot(None)))
        return list(result.scalars().all())
