"""FastAPI application entry point."""

import logging
import logging.config
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes import (
    account_values,
    accounts,
    auth,
    currencies,
    financial_institutions,
    health,
    holdings,
    securities,
    users,
)
from app.core.cache import configure_yfinance_cache
from app.core.config import settings
from app.core.exceptions import AppException, app_exception_handler
from app.core.middleware import RequestLoggingMiddleware
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.db.base import Base
from app.db.session import engine

# Configure logging
logging.config.dictConfig(settings.LOGGING_CONFIG)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan events."""
    # Startup
    print("🚀 Starting application...")

    # Initialize database
    async with engine.begin() as conn:
        # Create tables (use Alembic in production)
        if settings.ENVIRONMENT == "development":
            await conn.run_sync(Base.metadata.create_all)

    # Configure yfinance HTTP cache with Redis
    configure_yfinance_cache()

    yield

    # Shutdown
    print("👋 Shutting down application...")
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
)

# Add rate limiter to app state
app.state.limiter = limiter

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=settings.CORS_CREDENTIALS,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
)

# Add request/response logging middleware
# Note: Middleware is applied in reverse order, so this will be the outermost layer
app.add_middleware(RequestLoggingMiddleware)

# Note: SlowAPIMiddleware is not used due to compatibility issues with FastAPI response models
# X-RateLimit-* headers are only added to 429 responses via rate_limit_exceeded_handler

# Register exception handlers
app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(securities.router, prefix="/api/v1/securities", tags=["securities"])
app.include_router(currencies.router, prefix="/api/v1/currencies", tags=["currencies"])
app.include_router(
    financial_institutions.router,
    prefix="/api/v1/financial-institutions",
    tags=["financial-institutions"],
)
app.include_router(accounts.router, prefix="/api/v1/accounts", tags=["accounts"])
app.include_router(
    account_values.router,
    prefix="/api/v1/accounts/{account_id}/values",
    tags=["account-values"],
)
app.include_router(
    holdings.router,
    prefix="/api/v1/accounts/{account_id}/holdings",
    tags=["holdings"],
)
