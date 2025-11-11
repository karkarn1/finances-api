"""Repository layer for database operations.

This package provides the repository pattern implementation, centralizing
all database access logic and providing a clean separation of concerns
between data access and business logic.

Repositories:
    - BaseRepository: Generic CRUD operations for any model
    - UserRepository: User-specific queries and operations
    - AccountRepository: Account-specific queries and operations
    - AccountValueRepository: Account value-specific queries and operations
    - HoldingRepository: Holding-specific queries and operations
    - SecurityRepository: Security-specific queries and operations
    - SecurityPriceRepository: Price data queries and bulk operations

Usage:
    >>> from app.repositories import UserRepository, AccountRepository
    >>> from app.models.user import User
    >>> from app.models.account import Account
    >>>
    >>> # In a route or service
    >>> user_repo = UserRepository(User, db)
    >>> user = await user_repo.get_by_email("test@example.com")
    >>>
    >>> account_repo = AccountRepository(Account, db)
    >>> accounts = await account_repo.get_by_user_id(user.id)
"""

from app.repositories.account import AccountRepository
from app.repositories.account_value import AccountValueRepository
from app.repositories.base import BaseRepository
from app.repositories.holding import HoldingRepository
from app.repositories.security import SecurityRepository
from app.repositories.security_price import SecurityPriceRepository
from app.repositories.user import UserRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "AccountRepository",
    "AccountValueRepository",
    "HoldingRepository",
    "SecurityRepository",
    "SecurityPriceRepository",
]
