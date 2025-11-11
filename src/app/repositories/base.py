"""Base repository with common CRUD operations.

Provides generic database operations that can be inherited by model-specific
repositories. Uses SQLAlchemy 2.0's async API with proper type hints.

Supports both Pydantic models and dictionaries for create/update operations,
with automatic validation for Pydantic models.
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel
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

    async def create(self, *, obj_in: BaseModel | dict[str, Any]) -> ModelType:
        """Create a new record with Pydantic validation support.

        Args:
            obj_in: Pydantic model or dictionary of field names and values.
                Pydantic models are recommended for automatic validation.

        Returns:
            Created model instance (not yet committed)

        Note:
            Caller must commit the transaction.

        Raises:
            ValidationError: If Pydantic model validation fails
            TypeError: If dictionary contains invalid field names

        Example:
            Using Pydantic model (recommended for type safety and validation):

            >>> from app.schemas.user import UserCreate
            >>> user_data = UserCreate(email="test@example.com", password="secure123", username="test")
            >>> user = await repo.create(obj_in=user_data)
            >>> await db.commit()

            Using dictionary (for dynamic data):

            >>> user_data = {"email": "test@example.com", "username": "test"}
            >>> user = await repo.create(obj_in=user_data)
            >>> await db.commit()
        """
        # Convert Pydantic model to dictionary if needed
        if isinstance(obj_in, BaseModel):
            create_data = obj_in.model_dump(exclude_unset=True)
        else:
            create_data = obj_in

        db_obj = self.model(**create_data)
        self.db.add(db_obj)
        await self.db.flush()
        await self.db.refresh(db_obj)
        return db_obj

    async def update(
        self,
        *,
        db_obj: ModelType,
        obj_in: BaseModel | dict[str, Any],
    ) -> ModelType:
        """Update an existing record with Pydantic validation support.

        Args:
            db_obj: Existing model instance to update
            obj_in: Pydantic model or dictionary of fields to update (can be partial).
                Pydantic models are recommended for automatic validation.

        Returns:
            Updated model instance (not yet committed)

        Note:
            Caller must commit the transaction.

        Raises:
            ValidationError: If Pydantic model validation fails
            AttributeError: If dictionary contains invalid field names

        Example:
            Using Pydantic model (recommended for type safety and validation):

            >>> from app.schemas.user import UserUpdate
            >>> user = await repo.get(123)
            >>> update_data = UserUpdate(email="new@example.com")
            >>> updated = await repo.update(db_obj=user, obj_in=update_data)
            >>> await db.commit()

            Using dictionary (for dynamic data):

            >>> user = await repo.get(123)
            >>> updated = await repo.update(
            ...     db_obj=user,
            ...     obj_in={"email": "new@example.com"}
            ... )
            >>> await db.commit()
        """
        # Convert Pydantic model to dictionary if needed
        if isinstance(obj_in, BaseModel):
            update_data = obj_in.model_dump(exclude_unset=True)
        else:
            update_data = obj_in

        for field, value in update_data.items():
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
