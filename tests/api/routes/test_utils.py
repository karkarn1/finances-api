"""Tests for utility endpoints (health checks)."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def test_health_check(client: AsyncClient) -> None:
    """Test basic health check endpoint returns healthy status."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "healthy"


async def test_database_health_check(client: AsyncClient, test_db: AsyncSession) -> None:
    """Test database health check returns connected status."""
    response = await client.get("/health/db")

    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


async def test_health_endpoint_no_auth_required(client: AsyncClient) -> None:
    """Test health check endpoint does not require authentication."""
    # This test verifies that health check works without any auth headers
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


async def test_health_check_response_structure(client: AsyncClient) -> None:
    """Test health check returns expected JSON structure."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "status" in data
    assert isinstance(data["status"], str)


async def test_database_health_response_structure(client: AsyncClient) -> None:
    """Test database health check returns expected JSON structure."""
    response = await client.get("/health/db")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "status" in data
    assert "database" in data
    assert isinstance(data["status"], str)
    assert isinstance(data["database"], str)


@pytest.mark.asyncio
async def test_health_check_performance(client: AsyncClient) -> None:
    """Test health check responds quickly (performance test)."""
    import time

    start = time.time()
    response = await client.get("/health")
    duration = time.time() - start

    assert response.status_code == 200
    # Health check should respond in less than 100ms
    assert duration < 0.1


async def test_health_endpoints_consistent_format(client: AsyncClient) -> None:
    """Test both health endpoints return consistent format."""
    health_response = await client.get("/health")
    db_health_response = await client.get("/health/db")

    assert health_response.status_code == 200
    assert db_health_response.status_code == 200

    # Both should have 'status' key
    assert "status" in health_response.json()
    assert "status" in db_health_response.json()

    # Both should return dict
    assert isinstance(health_response.json(), dict)
    assert isinstance(db_health_response.json(), dict)
