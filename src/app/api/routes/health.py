"""Health check endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_cache_stats
from app.db.session import get_db

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@router.get("/health/db")
async def database_health(db: AsyncSession = Depends(get_db)):
    """Database health check."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": str(e)}


@router.get("/health/cache")
async def cache_health():
    """
    Cache health check and statistics.

    Returns cache status, backend type, and size (if available).
    Useful for monitoring Redis cache performance.
    """
    stats = get_cache_stats()
    if stats.get("enabled"):
        return {"status": "healthy", "cache": stats}
    return {"status": "disabled", "cache": stats}
