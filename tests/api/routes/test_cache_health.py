"""Tests for cache health endpoint."""

import pytest
from unittest.mock import patch

from app.core.cache import get_cache_stats


@pytest.mark.integration
async def test_cache_health_enabled(client):
    """Test cache health endpoint when cache is enabled."""
    with patch("app.api.routes.health.get_cache_stats") as mock_stats:
        mock_stats.return_value = {
            "enabled": True,
            "backend": "RedisCache",
            "size": 42,
        }

        response = await client.get("/health/cache")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["cache"]["enabled"] is True
        assert data["cache"]["backend"] == "RedisCache"
        assert data["cache"]["size"] == 42


@pytest.mark.integration
async def test_cache_health_disabled(client):
    """Test cache health endpoint when cache is disabled."""
    with patch("app.api.routes.health.get_cache_stats") as mock_stats:
        mock_stats.return_value = {"enabled": False}

        response = await client.get("/health/cache")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "disabled"
        assert data["cache"]["enabled"] is False


@pytest.mark.integration
async def test_cache_health_error(client):
    """Test cache health endpoint when there's an error getting stats."""
    with patch("app.api.routes.health.get_cache_stats") as mock_stats:
        mock_stats.return_value = {"enabled": False, "error": "Connection failed"}

        response = await client.get("/health/cache")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "disabled"
        assert data["cache"]["enabled"] is False
        assert data["cache"]["error"] == "Connection failed"
