"""Pytest fixtures for testing."""

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, get_password_hash
from app.db.base import Base
from app.db.session import get_db
from app.models.user import User
from main import app

# Test database URL (SQLite in-memory for fast tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_db(test_engine) -> AsyncGenerator[AsyncSession]:
    """Create a test database session."""
    async_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async with async_session_maker() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(test_db: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """Create a test client with database override."""

    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def test_user(test_db: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("TestPass123"),
        is_active=True,
        is_superuser=False,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def test_superuser(test_db: AsyncSession) -> User:
    """Create a test superuser."""
    user = User(
        email="admin@example.com",
        username="adminuser",
        hashed_password=get_password_hash("AdminPass123"),
        is_active=True,
        is_superuser=True,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def test_inactive_user(test_db: AsyncSession) -> User:
    """Create an inactive test user."""
    user = User(
        email="inactive@example.com",
        username="inactiveuser",
        hashed_password=get_password_hash("InactivePass123"),
        is_active=False,
        is_superuser=False,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest.fixture(scope="function")
def user_token(test_user: User) -> str:
    """Generate a valid access token for test user."""
    return create_access_token(data={"sub": test_user.username})


@pytest.fixture(scope="function")
def superuser_token(test_superuser: User) -> str:
    """Generate a valid access token for test superuser."""
    return create_access_token(data={"sub": test_superuser.username})


@pytest.fixture(scope="function")
def inactive_user_token(test_inactive_user: User) -> str:
    """Generate a valid access token for inactive user."""
    return create_access_token(data={"sub": test_inactive_user.username})


@pytest.fixture(scope="function")
def auth_headers(user_token: str) -> dict[str, str]:
    """Generate authorization headers with user token."""
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture(scope="function")
def superuser_auth_headers(superuser_token: str) -> dict[str, str]:
    """Generate authorization headers with superuser token."""
    return {"Authorization": f"Bearer {superuser_token}"}


@pytest.fixture(scope="function")
def inactive_user_auth_headers(inactive_user_token: str) -> dict[str, str]:
    """Generate authorization headers with inactive user token."""
    return {"Authorization": f"Bearer {inactive_user_token}"}
