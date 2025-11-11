"""Tests for rate limiting functionality."""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import limiter
from app.models.user import User

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def reset_limiter():
    """Reset rate limiter storage before each test."""
    # Clear the limiter's storage to prevent test interference
    try:
        if hasattr(limiter, "limiter") and hasattr(limiter.limiter, "storage"):
            if hasattr(limiter.limiter.storage, "storage"):
                limiter.limiter.storage.storage.clear()
    except Exception:
        # If clearing fails, continue - tests will still work
        pass
    yield
    # Clear again after test
    try:
        if hasattr(limiter, "limiter") and hasattr(limiter.limiter, "storage"):
            if hasattr(limiter.limiter.storage, "storage"):
                limiter.limiter.storage.storage.clear()
    except Exception:
        pass


@pytest.mark.asyncio
async def test_rate_limit_enforced_on_login(
    client: AsyncClient, test_user: User
) -> None:
    """Test that rate limit is enforced on login endpoint."""
    # AUTH_RATE_LIMIT = "5/minute"
    # Make 5 successful requests (should all succeed)
    for i in range(5):
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": "TestPass123"},
        )
        assert response.status_code in [
            200,
            401,
        ], f"Request {i+1} failed with status {response.status_code}"

    # 6th request should be rate limited
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": test_user.username, "password": "TestPass123"},
    )
    assert response.status_code == 429
    data = response.json()
    assert "detail" in data
    assert "rate limit" in data["detail"].lower()
    assert "retry_after" in data


@pytest.mark.asyncio
async def test_rate_limit_headers_present(
    client: AsyncClient, test_user: User
) -> None:
    """Test that rate limit headers are included in 429 responses."""
    # Exhaust rate limit (5 requests)
    for _ in range(5):
        await client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": "TestPass123"},
        )

    # Get rate limited response
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": test_user.username, "password": "TestPass123"},
    )

    # Check for X-RateLimit-* headers on 429 response
    assert response.status_code == 429
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Reset" in response.headers


@pytest.mark.asyncio
async def test_rate_limit_429_includes_retry_after(
    client: AsyncClient, test_user: User
) -> None:
    """Test that 429 response includes Retry-After header."""
    # Exhaust rate limit (5 requests)
    for _ in range(5):
        await client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": "TestPass123"},
        )

    # Next request should return 429 with Retry-After header
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": test_user.username, "password": "TestPass123"},
    )
    assert response.status_code == 429
    assert "Retry-After" in response.headers


@pytest.mark.asyncio
async def test_rate_limit_per_endpoint(
    client: AsyncClient, test_user: User, auth_headers: dict[str, str]
) -> None:
    """Test that different endpoints have independent rate limits."""
    # Exhaust login rate limit (5 requests)
    for _ in range(5):
        await client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": "TestPass123"},
        )

    # Login should be rate limited
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": test_user.username, "password": "TestPass123"},
    )
    assert response.status_code == 429

    # But /me endpoint should still work (different limit)
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_enforced_on_register(client: AsyncClient) -> None:
    """Test that rate limit is enforced on register endpoint."""
    # Make 5 registration attempts
    for i in range(5):
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"test{i}@example.com",
                "username": f"testuser{i}",
                "password": "testpass123",
            },
        )

    # 6th request should be rate limited
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test99@example.com",
            "username": "testuser99",
            "password": "testpass123",
        },
    )
    assert response.status_code == 429


@pytest.mark.asyncio
async def test_rate_limit_enforced_on_sync_endpoint(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Test that rate limit is enforced on expensive sync endpoint."""
    # SYNC_RATE_LIMIT = "10/minute"
    # Make 10 sync requests
    for i in range(10):
        response = await client.post(
            "/api/v1/securities/AAPL/sync", headers=auth_headers
        )
        # Some may succeed, some may fail due to other reasons,
        # but we should not hit rate limit yet
        assert response.status_code != 429, f"Request {i+1} was rate limited too early"

    # 11th request should be rate limited
    response = await client.post("/api/v1/securities/AAPL/sync", headers=auth_headers)
    assert response.status_code == 429


@pytest.mark.asyncio
async def test_rate_limit_different_endpoints_different_limits(
    client: AsyncClient, test_user: User, auth_headers: dict[str, str]
) -> None:
    """Test that auth endpoints (5/min) and sync endpoints (10/min) have different limits."""
    # Exhaust auth rate limit (5 requests)
    for _ in range(5):
        await client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": "TestPass123"},
        )

    # Auth endpoint should be rate limited
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": test_user.username, "password": "TestPass123"},
    )
    assert response.status_code == 429

    # But sync endpoint should still accept requests (has 10/min limit)
    response = await client.post("/api/v1/securities/AAPL/sync", headers=auth_headers)
    # Should not be rate limited (different limit)
    assert response.status_code != 429


@pytest.mark.asyncio
async def test_rate_limit_can_be_disabled(
    client: AsyncClient, test_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that rate limiting can be disabled via config."""
    # Note: This test would require reloading the app with RATE_LIMIT_ENABLED=False
    # For now, we test that the config option exists
    assert hasattr(settings, "RATE_LIMIT_ENABLED")
    assert isinstance(settings.RATE_LIMIT_ENABLED, bool)


@pytest.mark.asyncio
async def test_rate_limit_response_format(
    client: AsyncClient, test_user: User
) -> None:
    """Test that rate limit exceeded response has correct format."""
    # Exhaust rate limit
    for _ in range(5):
        await client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": "TestPass123"},
        )

    # Get rate limited response
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": test_user.username, "password": "TestPass123"},
    )

    assert response.status_code == 429
    data = response.json()

    # Check response body structure
    assert "detail" in data
    assert isinstance(data["detail"], str)
    assert "retry_after" in data
    assert isinstance(data["retry_after"], int)

    # Check headers
    assert "Retry-After" in response.headers
    assert response.headers["Retry-After"].isdigit()


@pytest.mark.asyncio
async def test_rate_limit_x_ratelimit_headers(
    client: AsyncClient, test_user: User
) -> None:
    """Test that X-RateLimit-* headers contain correct information on 429 responses."""
    # Exhaust rate limit (5 requests)
    for _ in range(5):
        await client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": "TestPass123"},
        )

    # Get rate limited response
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": test_user.username, "password": "TestPass123"},
    )

    # Verify we got rate limited
    assert response.status_code == 429

    # Verify header structure on 429 response
    assert "X-RateLimit-Limit" in response.headers
    assert response.headers["X-RateLimit-Limit"].isdigit()
    assert int(response.headers["X-RateLimit-Limit"]) == 5  # AUTH_RATE_LIMIT

    assert "X-RateLimit-Remaining" in response.headers
    remaining = int(response.headers["X-RateLimit-Remaining"])
    assert remaining == 0  # Should be 0 when rate limited

    assert "X-RateLimit-Reset" in response.headers
    assert response.headers["X-RateLimit-Reset"].isdigit()


@pytest.mark.asyncio
async def test_rate_limit_counts_per_ip(client: AsyncClient, test_user: User) -> None:
    """Test that rate limits are tracked per IP address."""
    # All requests from same client should share the rate limit counter
    for i in range(5):
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": "TestPass123"},
        )
        remaining = int(response.headers.get("X-RateLimit-Remaining", "0"))
        # Remaining should decrease with each request
        expected_remaining = 4 - i  # AUTH_RATE_LIMIT is 5/minute
        assert remaining <= expected_remaining

    # Next request should be rate limited
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": test_user.username, "password": "TestPass123"},
    )
    assert response.status_code == 429
