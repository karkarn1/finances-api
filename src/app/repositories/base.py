"""Base repository with common CRUD operations.

Provides generic database operations that can be inherited by model-specific
repositories. Uses SQLAlchemy 2.0's async API with proper type hints.
"""

from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

# Generic type for SQLAlchemy models
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base repository with common CRUD operations.

    Provides generic create, read, update, delete operations for any
    SQLAlchemy model. Repositories do NOT manage transactions - the
    caller is responsible for commit/rollback.

    Type Parameters:
        ModelType: The SQLAlchemy model class

    Example:
        >>> class UserRepository(BaseRepository[User]):
        ...     pass
        >>>
        >>> repo = UserRepository(User, db)
        >>> user = await repo.get(user_id)
    """

    def __init__(self, model: type[ModelType], db: AsyncSession):
        """Initialize repository.

        Args:
            model: The SQLAlchemy model class
            db: Async database session
        """
        self.model = model
        self.db = db

    async def get(self, id: Any) -> ModelType | None:
        """Get a single record by primary key.

        Args:
            id: Primary key value

        Returns:
            Model instance if found, None otherwise

        Example:
            >>> user = await repo.get(123)
            >>> if user:
            ...     print(user.email)
        """
        result = await self.db.execute(
            select(self.model).where(self.model.id == id)  # type: ignore[attr-defined]
        )
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ModelType]:
        """Get multiple records with pagination.

        Args:
            skip: Number of records to skip (offset)
            limit: Maximum number of records to return

        Returns:
            List of model instances

        Example:
            >>> users = await repo.get_multi(skip=0, limit=20)
            >>> print(f"Found {len(users)} users")
        """
        result = await self.db.execute(select(self.model).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def create(self, *, obj_in: dict[str, Any]) -> ModelType:
        """Create a new record.

        Args:
            obj_in: Dictionary of field names and values

        Returns:
            Created model instance (not yet committed)

        Note:
            Caller must commit the transaction.

        Example:
            >>> user_data = {"email": "test@example.com", "username": "test"}
            >>> user = await repo.create(obj_in=user_data)
            >>> await db.commit()
        """
        db_obj = self.model(**obj_in)
        self.db.add(db_obj)
        await self.db.flush()
        await self.db.refresh(db_obj)
        return db_obj

    async def update(
        self,
        *,
        db_obj: ModelType,
        obj_in: dict[str, Any],
    ) -> ModelType:
        """Update an existing record.

        Args:
            db_obj: Existing model instance to update
            obj_in: Dictionary of fields to update (can be partial)

        Returns:
            Updated model instance (not yet committed)

        Note:
            Caller must commit the transaction.

        Example:
            >>> user = await repo.get(123)
            >>> updated = await repo.update(
            ...     db_obj=user,
            ...     obj_in={"email": "new@example.com"}
            ... )
            >>> await db.commit()
        """
        for field, value in obj_in.items():
            setattr(db_obj, field, value)

        await self.db.flush()
        await self.db.refresh(db_obj)
        return db_obj

    async def delete(self, *, id: Any) -> ModelType:
        """Delete a record by primary key.

        Args:
            id: Primary key value

        Returns:
            Deleted model instance (not yet committed)

        Raises:
            ValueError: If record not found

        Note:
            Caller must commit the transaction.

        Example:
            >>> user = await repo.delete(id=123)
            >>> await db.commit()
        """
        db_obj = await self.get(id)
        if not db_obj:
            raise ValueError(f"{self.model.__name__} with id {id} not found")

        await self.db.delete(db_obj)
        await self.db.flush()
        return db_obj

    async def exists(self, id: Any) -> bool:
        """Check if a record exists by primary key.

        Args:
            id: Primary key value

        Returns:
            True if record exists, False otherwise

        Example:
            >>> if await repo.exists(123):
            ...     print("User exists")
        """
        result = await self.get(id)
        return result is not None
