"""Database session management with transaction utilities.

This module provides:
- AsyncSession factory for dependency injection
- Transaction context managers for explicit transaction control
- Utility functions for read-only and nested transactions
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

logger = logging.getLogger(__name__)

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency for route handlers.

    This is the standard dependency injection method for FastAPI routes.
    It automatically manages commit/rollback/close lifecycle.

    Yields:
        AsyncSession: Database session for the request

    Example:
        ```python
        @router.get("/users")
        async def list_users(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(User))
            return result.scalars().all()
        ```
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def transactional(
    db: AsyncSession,
    *,
    commit: bool = True,
) -> AsyncGenerator[AsyncSession, None]:
    """Explicit transaction context manager with automatic commit/rollback.

    Use this when you need explicit transaction control within a service
    or route handler. Automatically commits on success or rolls back on
    exception.

    Args:
        db: The database session
        commit: Whether to commit on success (default: True)

    Yields:
        AsyncSession: The database session

    Raises:
        Exception: Re-raises any exception after rollback

    Example:
        ```python
        # In a service function
        async with transactional(db):
            user = User(email="user@example.com", username="johndoe")
            db.add(user)
            # Auto-commits on success, auto-rollbacks on exception

        # Or with multiple operations
        async with transactional(db):
            for item in items:
                db.add(item)
            # All operations commit together or rollback together
        ```

    Note:
        If commit=False, the session is rolled back instead:
        ```python
        async with transactional(db, commit=False):
            # Read-only operations, no commit at end
            result = await db.execute(select(User))
        ```
    """
    try:
        yield db
        if commit:
            await db.commit()
            logger.debug("Transaction committed successfully")
    except Exception as e:
        await db.rollback()
        logger.error(f"Transaction rolled back due to error: {type(e).__name__}: {e}")
        raise


@asynccontextmanager
async def read_only_transaction(
    db: AsyncSession,
) -> AsyncGenerator[AsyncSession, None]:
    """Read-only transaction context manager (never commits).

    Use this for queries that should never modify the database.
    Ensures no accidental commits and properly cleans up resources.

    Args:
        db: The database session

    Yields:
        AsyncSession: The database session

    Example:
        ```python
        async with read_only_transaction(db):
            result = await db.execute(select(User).limit(10))
            users = result.scalars().all()
            # No commit, just reads
        ```

    Note:
        Never commits changes, even on success. Safe for read-only operations
        and prevents accidental modifications.
    """
    try:
        yield db
        # Never commit read-only transactions
    except Exception as e:
        logger.error(f"Read-only transaction error: {type(e).__name__}: {e}")
        raise


@asynccontextmanager
async def with_savepoint(
    db: AsyncSession,
    name: str = "sp1",
) -> AsyncGenerator[object, None]:
    """Create a nested transaction savepoint.

    Use this for nested transaction control within an outer transaction.
    Allows rolling back to a specific point without rolling back the
    entire transaction.

    Args:
        db: The database session
        name: Name of the savepoint (default: "sp1")

    Yields:
        Savepoint object from SQLAlchemy

    Raises:
        Exception: Re-raises any exception after savepoint rollback

    Example:
        ```python
        async with transactional(db):
            user = User(email="user@example.com")
            db.add(user)
            await db.flush()

            try:
                async with with_savepoint(db, "user_profile"):
                    profile = Profile(user_id=user.id)
                    db.add(profile)
                    # If profile creation fails, this savepoint rolls back
            except Exception:
                # User creation succeeds, profile creation failed
                await db.commit()
        ```

    Note:
        Savepoints only work within an outer transaction context.
        Always use this within a transactional() or get_db() context.
    """
    async with db.begin_nested() as savepoint:
        try:
            yield savepoint
        except Exception as e:
            logger.warning(f"Savepoint '{name}' rolled back due to error: {type(e).__name__}: {e}")
            raise
