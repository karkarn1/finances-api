"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print("🚀 Starting application...")
    async with engine.begin() as conn:
        # Create tables (use Alembic in production)
        if settings.ENVIRONMENT == "development":
            await conn.run_sync(Base.metadata.create_all)

    yield

    # Shutdown
    print("👋 Shutting down application...")
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_CREDENTIALS,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
)

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
