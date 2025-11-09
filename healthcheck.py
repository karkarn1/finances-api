#!/usr/bin/env python3
"""
Health check script for Docker containers and deployment.

Tests database and Redis connectivity and reports health status.
"""

import sys
import asyncio
from typing import Dict, Any

try:
    import asyncpg
    import redis.asyncio as redis
except ImportError:
    print("Missing dependencies. Install with: uv pip install asyncpg redis")
    sys.exit(1)


async def check_postgres(db_url: str) -> Dict[str, Any]:
    """Check PostgreSQL connectivity."""
    try:
        conn = await asyncpg.connect(db_url)
        await conn.execute("SELECT 1")
        await conn.close()
        return {"status": "healthy", "message": "PostgreSQL connection successful"}
    except Exception as e:
        return {"status": "unhealthy", "message": f"PostgreSQL error: {str(e)}"}


async def check_redis(redis_url: str) -> Dict[str, Any]:
    """Check Redis connectivity."""
    try:
        client = redis.from_url(redis_url, decode_responses=True)
        await client.ping()
        await client.aclose()
        return {"status": "healthy", "message": "Redis connection successful"}
    except Exception as e:
        return {"status": "unhealthy", "message": f"Redis error: {str(e)}"}


async def main():
    """Run health checks."""
    import os

    # Get connection strings from environment
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/app_db"
    )
    redis_url = os.getenv(
        "REDIS_URL",
        "redis://localhost:6379/0"
    )

    # Convert asyncpg URL format
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    print("🏥 Running health checks...\n")

    # Run checks
    postgres_result = await check_postgres(db_url)
    redis_result = await check_redis(redis_url)

    # Print results
    print(f"PostgreSQL: {postgres_result['status'].upper()}")
    print(f"  {postgres_result['message']}\n")

    print(f"Redis: {redis_result['status'].upper()}")
    print(f"  {redis_result['message']}\n")

    # Overall status
    if (
        postgres_result["status"] == "healthy"
        and redis_result["status"] == "healthy"
    ):
        print("✅ All systems healthy")
        sys.exit(0)
    else:
        print("❌ Some systems unhealthy")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
