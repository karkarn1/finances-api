"""Tests for request/response logging middleware."""

import pytest
from httpx import AsyncClient


@pytest.mark.integration
async def test_logging_middleware_adds_timing_header(client: AsyncClient) -> None:
    """Test that middleware adds X-Process-Time header to responses."""
    response = await client.get("/health")

    # Verify timing header is present
    assert "X-Process-Time" in response.headers

    # Verify timing header is a valid float string
    timing = float(response.headers["X-Process-Time"])
    assert timing >= 0


@pytest.mark.integration
async def test_logging_middleware_skips_health_endpoint(client: AsyncClient, caplog) -> None:
    """Test that middleware doesn't log health check endpoint."""
    with caplog.at_level("INFO"):
        response = await client.get("/health")

    # Verify response is successful
    assert response.status_code == 200

    # Verify health endpoint was not logged (quiet path)
    assert "/health" not in caplog.text


@pytest.mark.integration
async def test_logging_middleware_logs_api_request(client: AsyncClient, caplog, test_user) -> None:
    """Test that middleware logs API requests with timing."""
    with caplog.at_level("INFO"):
        response = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {test_user['token']}"},
        )

    # Verify response is successful
    assert response.status_code == 200

    # Verify request was logged with directional arrow and method/path
    assert "→ GET /api/v1/users/me" in caplog.text

    # Verify response was logged with arrow, status, and timing
    assert "← GET /api/v1/users/me - 200" in caplog.text


@pytest.mark.integration
async def test_logging_middleware_logs_failures_at_warning_level(
    client: AsyncClient, caplog
) -> None:
    """Test that middleware logs error responses at WARNING level."""
    with caplog.at_level("WARNING"):
        response = await client.get("/api/v1/invalid-endpoint")

    # Verify 404 response
    assert response.status_code == 404

    # Verify error was logged
    assert "← GET" in caplog.text
    assert "404" in caplog.text


@pytest.mark.integration
async def test_logging_middleware_skips_docs_endpoints(client: AsyncClient, caplog) -> None:
    """Test that middleware doesn't log API documentation endpoints."""
    quiet_paths = ["/docs", "/openapi.json", "/redoc"]

    for path in quiet_paths:
        caplog.clear()
        with caplog.at_level("INFO"):
            response = await client.get(path)

        # Verify path was not logged (quiet path)
        assert path not in caplog.text
