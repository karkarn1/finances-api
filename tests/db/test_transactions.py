"""Tests for database transaction context managers.

Tests verify that transaction context managers properly handle:
- Automatic commit on success
- Automatic rollback on exception
- Savepoint management
- Read-only transaction behavior
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import read_only_transaction, transactional, with_savepoint
from app.models.user import User


@pytest.mark.asyncio
class TestTransactionalContextManager:
    """Tests for the transactional context manager."""

    async def test_transactional_commits_on_success(self, test_db: AsyncSession) -> None:
        """Test that transactional context commits changes on successful exit."""
        test_user = User(
            email="transactional@example.com",
            username="transactional_user",
            hashed_password="hashed_password_value",
            is_active=True,
        )

        # Create user within transactional context
        async with transactional(test_db):
            test_db.add(test_user)

        # Verify user was committed by querying database
        result = await test_db.execute(
            select(User).where(User.email == "transactional@example.com")
        )
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.email == "transactional@example.com"
        assert user.username == "transactional_user"

    async def test_transactional_rolls_back_on_exception(self, test_db: AsyncSession) -> None:
        """Test that transactional context rolls back on exception."""
        test_user = User(
            email="rollback@example.com",
            username="rollback_user",
            hashed_password="hashed_password_value",
            is_active=True,
        )

        # Try to create user but raise exception
        with pytest.raises(ValueError):
            async with transactional(test_db):
                test_db.add(test_user)
                raise ValueError("Intentional error for testing")

        # Verify user was rolled back and not in database
        result = await test_db.execute(select(User).where(User.email == "rollback@example.com"))
        user = result.scalar_one_or_none()
        assert user is None

    async def test_transactional_commit_false_does_not_commit(self, test_db: AsyncSession) -> None:
        """Test that commit=False prevents commits."""
        test_user = User(
            email="no_commit@example.com",
            username="no_commit_user",
            hashed_password="hashed_password_value",
            is_active=True,
        )

        # Create user with commit=False
        async with transactional(test_db, commit=False):
            test_db.add(test_user)

        # Verify user was NOT committed
        result = await test_db.execute(select(User).where(User.email == "no_commit@example.com"))
        user = result.scalar_one_or_none()
        assert user is None

    async def test_transactional_multiple_operations_atomic(self, test_db: AsyncSession) -> None:
        """Test that multiple operations within transaction are atomic."""
        user1 = User(
            email="atomic1@example.com",
            username="atomic_user_1",
            hashed_password="hashed_password_1",
            is_active=True,
        )
        user2 = User(
            email="atomic2@example.com",
            username="atomic_user_2",
            hashed_password="hashed_password_2",
            is_active=True,
        )

        # Add multiple users in single transaction
        async with transactional(test_db):
            test_db.add(user1)
            test_db.add(user2)

        # Verify both users were committed
        result = await test_db.execute(
            select(User).where(User.email.in_(["atomic1@example.com", "atomic2@example.com"]))
        )
        users = result.scalars().all()
        assert len(users) == 2

    async def test_transactional_re_raises_exception(self, test_db: AsyncSession) -> None:
        """Test that transactional context re-raises exceptions after rollback."""
        with pytest.raises(RuntimeError) as exc_info:
            async with transactional(test_db):
                test_db.add(
                    User(
                        email="error@example.com",
                        username="error_user",
                        hashed_password="hashed",
                        is_active=True,
                    )
                )
                raise RuntimeError("Test error message")

        # Verify exception was re-raised
        assert "Test error message" in str(exc_info.value)


@pytest.mark.asyncio
class TestReadOnlyTransactionContextManager:
    """Tests for the read_only_transaction context manager."""

    async def test_read_only_transaction_allows_reads(self, test_db: AsyncSession) -> None:
        """Test that read_only_transaction allows query operations."""
        # Add a user to database
        test_user = User(
            email="readonly@example.com",
            username="readonly_user",
            hashed_password="hashed_password_value",
            is_active=True,
        )
        test_db.add(test_user)
        await test_db.commit()

        # Read within read_only_transaction
        async with read_only_transaction(test_db):
            result = await test_db.execute(select(User).where(User.email == "readonly@example.com"))
            user = result.scalar_one_or_none()

        # Verify read was successful
        assert user is not None
        assert user.email == "readonly@example.com"

    async def test_read_only_transaction_prevents_commits(self, test_db: AsyncSession) -> None:
        """Test that read_only_transaction context doesn't commit added objects."""
        test_user = User(
            email="prevent_commit@example.com",
            username="prevent_commit_user",
            hashed_password="hashed_password_value",
            is_active=True,
        )

        # Try to add user in read_only_transaction
        async with read_only_transaction(test_db):
            test_db.add(test_user)
            # Session will have the user in identity map but not committed
            # Verify it's in the session but would need explicit commit
            assert test_user in test_db.new or test_user in test_db.identity_map.values()

        # Rollback to clear the session state
        await test_db.rollback()

        # Verify user was NOT committed to the database
        result = await test_db.execute(
            select(User).where(User.email == "prevent_commit@example.com")
        )
        user = result.scalar_one_or_none()
        assert user is None

    async def test_read_only_transaction_handles_exceptions(self, test_db: AsyncSession) -> None:
        """Test that read_only_transaction handles exceptions gracefully."""
        with pytest.raises(ValueError):
            async with read_only_transaction(test_db):
                # Read a user
                result = await test_db.execute(select(User).limit(1))
                result.scalar_one_or_none()
                # Raise an exception
                raise ValueError("Read operation failed")

    async def test_read_only_transaction_multiple_queries(self, test_db: AsyncSession) -> None:
        """Test that multiple reads work in read_only_transaction."""
        # Add test users
        users_data = [
            ("user1@example.com", "user1", True),
            ("user2@example.com", "user2", True),
            ("user3@example.com", "user3", False),
        ]

        for email, username, is_active in users_data:
            user = User(
                email=email,
                username=username,
                hashed_password="hashed",
                is_active=is_active,
            )
            test_db.add(user)

        await test_db.commit()

        # Execute multiple reads in read_only_transaction
        async with read_only_transaction(test_db):
            # Query 1: Active users
            result1 = await test_db.execute(select(User).where(User.is_active))
            active_users = result1.scalars().all()

            # Query 2: User count
            result2 = await test_db.execute(select(User))
            all_users = result2.scalars().all()

        # Verify queries were successful
        assert len(active_users) >= 2
        assert len(all_users) >= 3


@pytest.mark.asyncio
class TestSavepointContextManager:
    """Tests for the with_savepoint context manager."""

    async def test_savepoint_commits_on_success(self, test_db: AsyncSession) -> None:
        """Test that savepoint commits when context exits successfully."""
        async with transactional(test_db):
            # Create outer transaction user
            user1 = User(
                email="outer@example.com",
                username="outer_user",
                hashed_password="hashed",
                is_active=True,
            )
            test_db.add(user1)

            # Create savepoint user
            user2 = User(
                email="savepoint@example.com",
                username="savepoint_user",
                hashed_password="hashed",
                is_active=True,
            )

            async with with_savepoint(test_db, "user_creation"):
                test_db.add(user2)

        # Verify both users were committed
        result = await test_db.execute(
            select(User).where(User.email.in_(["outer@example.com", "savepoint@example.com"]))
        )
        users = result.scalars().all()
        assert len(users) == 2

    async def test_savepoint_rolls_back_on_exception(self, test_db: AsyncSession) -> None:
        """Test that savepoint rolls back on exception without affecting outer transaction."""
        async with transactional(test_db):
            # Create outer transaction user
            user1 = User(
                email="outer_success@example.com",
                username="outer_success_user",
                hashed_password="hashed",
                is_active=True,
            )
            test_db.add(user1)

            # Try to create savepoint user but raise exception
            user2 = User(
                email="savepoint_fail@example.com",
                username="savepoint_fail_user",
                hashed_password="hashed",
                is_active=True,
            )

            try:
                async with with_savepoint(test_db, "failed_user"):
                    test_db.add(user2)
                    raise ValueError("Savepoint error")
            except ValueError:
                pass  # Expected error

        # Verify outer user was committed but savepoint user was not
        result = await test_db.execute(
            select(User).where(User.email == "outer_success@example.com")
        )
        outer_user = result.scalar_one_or_none()
        assert outer_user is not None

        result = await test_db.execute(
            select(User).where(User.email == "savepoint_fail@example.com")
        )
        savepoint_user = result.scalar_one_or_none()
        assert savepoint_user is None

    async def test_savepoint_nested_success(self, test_db: AsyncSession) -> None:
        """Test that nested savepoints work correctly."""
        async with transactional(test_db):
            user1 = User(
                email="nested1@example.com",
                username="nested_user_1",
                hashed_password="hashed",
                is_active=True,
            )
            test_db.add(user1)

            async with with_savepoint(test_db, "sp1"):
                user2 = User(
                    email="nested2@example.com",
                    username="nested_user_2",
                    hashed_password="hashed",
                    is_active=True,
                )
                test_db.add(user2)

                # Nested savepoint within savepoint
                async with with_savepoint(test_db, "sp2"):
                    user3 = User(
                        email="nested3@example.com",
                        username="nested_user_3",
                        hashed_password="hashed",
                        is_active=True,
                    )
                    test_db.add(user3)

        # Verify all users were committed
        result = await test_db.execute(
            select(User).where(
                User.email.in_(
                    ["nested1@example.com", "nested2@example.com", "nested3@example.com"]
                )
            )
        )
        users = result.scalars().all()
        assert len(users) == 3

    async def test_savepoint_re_raises_exception(self, test_db: AsyncSession) -> None:
        """Test that savepoint context re-raises exceptions after rollback."""
        async with transactional(test_db):
            test_db.add(
                User(
                    email="pre_savepoint@example.com",
                    username="pre_savepoint_user",
                    hashed_password="hashed",
                    is_active=True,
                )
            )

            with pytest.raises(RuntimeError) as exc_info:
                async with with_savepoint(test_db, "failing_sp"):
                    raise RuntimeError("Savepoint error message")

            assert "Savepoint error message" in str(exc_info.value)
