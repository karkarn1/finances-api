"""HTTP caching configuration for yfinance requests using requests-cache and Redis."""

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import requests_cache
from redis import Redis
from redis.exceptions import RedisError
from requests_cache.backends.redis import RedisCache

from app.core.config import settings

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Cache expiration times based on data type
CACHE_EXPIRATION = {
    # Historical daily/weekly/monthly data - stable, cache for 24 hours
    "daily_data": timedelta(hours=24),
    # Intraday data (1m, 1h intervals) - fresher data needed, cache for 15 minutes
    "intraday_data": timedelta(minutes=15),
    # Security metadata (company info) - changes infrequently, cache for 6 hours
    "security_info": timedelta(hours=6),
    # Default fallback
    "default": timedelta(hours=1),
}


def get_redis_connection() -> "Redis[Any] | None":
    """
    Get Redis connection for caching.

    Returns:
        Redis client instance or None if connection fails

    Note:
        This function handles connection errors gracefully and returns None
        if Redis is unavailable, allowing the app to continue without caching.
    """
    try:
        # Parse Redis URL from settings
        redis_client: Redis[Any] = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=False,  # Keep binary responses for requests-cache
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        # Test connection
        redis_client.ping()
        logger.info(f"Successfully connected to Redis at {settings.REDIS_URL}")
        return redis_client
    except RedisError as e:
        logger.warning(f"Failed to connect to Redis: {e}. Caching will be disabled.")
        return None
    except Exception as e:
        logger.error(f"Unexpected error connecting to Redis: {e}. Caching will be disabled.")
        return None


def configure_yfinance_cache() -> None:
    """
    Configure requests-cache for yfinance HTTP requests with Redis backend.

    Sets up URL pattern-based expiration:
    - Historical daily/weekly/monthly data: 24 hours
    - Intraday data (minute/hour intervals): 15 minutes
    - Security metadata: 6 hours
    - Default: 1 hour

    The cache uses Redis for storage with automatic TTL-based cleanup.
    If Redis is unavailable, caching is gracefully disabled.

    Note:
        This should be called during app startup (in lifespan context).
        requests-cache will patch yfinance's underlying requests library.
    """
    # Check if Redis is available
    redis_conn = get_redis_connection()

    if redis_conn is None:
        logger.warning("Skipping cache configuration - Redis unavailable")
        return

    try:
        # Create Redis backend with custom connection
        backend = RedisCache(
            namespace="yfinance",  # Prefix for all cache keys
            connection=redis_conn,
        )

        # Configure URL-based expiration patterns
        # Yahoo Finance API endpoints and their expiration times
        urls_expire_after = {
            # Daily, weekly, monthly historical data - stable, cache longer
            "*/v8/finance/chart/*interval=1d*": CACHE_EXPIRATION["daily_data"],
            "*/v8/finance/chart/*interval=1wk*": CACHE_EXPIRATION["daily_data"],
            "*/v8/finance/chart/*interval=1mo*": CACHE_EXPIRATION["daily_data"],
            # Intraday data - more dynamic, cache shorter
            "*/v8/finance/chart/*interval=1m*": CACHE_EXPIRATION["intraday_data"],
            "*/v8/finance/chart/*interval=1h*": CACHE_EXPIRATION["intraday_data"],
            # Security info/metadata
            "*/v10/finance/quoteSummary/*": CACHE_EXPIRATION["security_info"],
            "*/v7/finance/quote/*": CACHE_EXPIRATION["security_info"],
            # Default for other endpoints
            "*query.yahooapis.com*": CACHE_EXPIRATION["default"],
        }

        # Install the cache globally (patches requests library)
        requests_cache.install_cache(
            backend=backend,
            urls_expire_after=urls_expire_after,
            allowable_methods=("GET", "POST"),  # Cache GET and POST requests
            stale_if_error=True,  # Return stale cache on network errors
        )

        logger.info("✓ Configured yfinance cache with Redis backend and pattern-based expiration")
        logger.info(f"  - Daily/weekly/monthly data: {CACHE_EXPIRATION['daily_data']}")
        logger.info(f"  - Intraday data: {CACHE_EXPIRATION['intraday_data']}")
        logger.info(f"  - Security metadata: {CACHE_EXPIRATION['security_info']}")
        logger.info(f"  - Default: {CACHE_EXPIRATION['default']}")

    except Exception as e:
        logger.error(f"Failed to configure yfinance cache: {e}")
        logger.warning("Continuing without caching")


def clear_yfinance_cache() -> None:
    """
    Clear all cached yfinance responses.

    This removes all entries from the Redis cache namespace.
    Useful for testing or when data needs to be refreshed.
    """
    try:
        cache = requests_cache.get_cache()
        if cache is not None:
            cache.clear()
            logger.info("Cleared all yfinance cache entries")
        else:
            logger.warning("No active cache to clear")
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")


def get_cache_stats() -> dict[str, Any]:
    """
    Get cache statistics including hits, misses, and size.

    Returns:
        Dictionary with cache statistics:
        - enabled: Whether caching is active
        - backend: Backend type (e.g., 'redis')
        - size: Number of cached responses (if available)
    """
    try:
        cache = requests_cache.get_cache()
        if cache is None:
            return {"enabled": False}

        stats: dict[str, Any] = {
            "enabled": True,
            "backend": type(cache).__name__,
        }

        # Try to get cache size (may not be supported by all backends)
        try:
            stats["size"] = len(cache.responses)
        except Exception:
            stats["size"] = "unavailable"

        return stats
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        return {"enabled": False, "error": str(e)}
