# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A modern FastAPI application for managing personal finances with async PostgreSQL, Redis caching, and containerized deployment using Docker. Built with Python 3.13+ and managed with `uv` for fast dependency management.

**All development is Docker-based.** The application runs entirely in containers, with hot reload enabled for development.

## Quick Reference - Makefile Commands

The project uses a Makefile for common operations. Run `make help` to see all available commands.

### Most Common Commands
```bash
make start          # Start all services
make stop           # Stop all services
make restart        # Restart all services
make logs           # View all logs (follow mode)
make logs-app       # View API logs only
make migrate        # Run database migrations
make test           # Run tests
make shell          # Open shell in API container
make health         # Check API health
```

### Development Commands

#### Service Management
```bash
# Start all services (PostgreSQL, Redis, API)
make start
# Equivalent to: docker-compose up -d

# Stop all services
make stop
# Equivalent to: docker-compose down

# Restart all services
make restart
# Equivalent to: docker-compose restart

# Restart only the API (faster for code changes)
make restart-app
# Equivalent to: docker-compose restart app

# Rebuild and start (after Dockerfile changes)
make rebuild
# Equivalent to: docker-compose up -d --build

# View service status
make status
# Equivalent to: docker-compose ps
```

#### Logs and Debugging
```bash
# View all logs (follow mode)
make logs

# View specific service logs
make logs-app    # API logs
make logs-db     # PostgreSQL logs
make logs-redis  # Redis logs
```

#### Shell Access
```bash
# Open shell in API container
make shell
# Equivalent to: docker-compose exec app /bin/sh

# Open PostgreSQL shell
make db-shell
# Equivalent to: docker-compose exec db psql -U postgres -d finances_db

# Open Redis CLI
make redis-shell
# Equivalent to: docker-compose exec redis redis-cli
```

### Database Migrations
```bash
# Run all pending migrations
make migrate
# Equivalent to: docker-compose exec app alembic upgrade head

# Create a new migration
make migrate-create MSG="add user table"
# Equivalent to: docker-compose exec app alembic revision --autogenerate -m "add user table"

# View migration history
make migrate-history
# Equivalent to: docker-compose exec app alembic history

# Rollback last migration
make migrate-downgrade
# Equivalent to: docker-compose exec app alembic downgrade -1
```

### Testing
```bash
# Run all tests inside Docker
make test
# Equivalent to: docker-compose exec app pytest

# Run tests with coverage report
make test-cov
# Equivalent to: docker-compose exec app pytest --cov=src --cov-report=term-missing

# Run specific test file
docker-compose exec app pytest tests/api/routes/test_login.py -v

# Run specific test function
docker-compose exec app pytest tests/api/routes/test_login.py::test_register_with_valid_data -v

# Run tests by marker
docker-compose exec app pytest -m unit          # Unit tests only
docker-compose exec app pytest -m integration   # Integration tests only

# Run tests locally (requires local uv setup)
make test-local
# Equivalent to: uv run pytest
```

### Code Quality
```bash
# Run linter (check only)
make lint
# Equivalent to: docker-compose exec app ruff check .

# Run linter with auto-fix
make lint-fix
# Equivalent to: docker-compose exec app ruff check . --fix

# Format code
make format
# Equivalent to: docker-compose exec app ruff format .

# Type checking
make type-check
# Equivalent to: docker-compose exec app mypy src/
```

### Database Operations
```bash
# Backup database
make db-backup
# Creates backup.sql

# Restore database from backup
make db-restore
# Restores from backup.sql

# Reset database (WARNING: destroys all data)
make db-reset
# Drops and recreates the database
```

### Development Workflow Shortcuts
```bash
# Start services and run migrations (full setup)
make dev
# Equivalent to: make start && make migrate

# Clean reset of dev environment
make dev-reset
# Equivalent to: make clean && make start && make migrate

# Complete cleanup (removes volumes and data)
make clean
# Equivalent to: docker-compose down -v
```

The API will be available at:
- Application: http://localhost:8000
- API Docs (Swagger): http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health Check: http://localhost:8000/health

## Architecture

### Async-First Design
- All database operations use `async/await` with SQLAlchemy 2.0's async API
- Database session management via `AsyncSession` with proper connection pooling
- FastAPI's lifespan events handle engine initialization and disposal

### Authentication System
- **JWT Tokens**: Stateless authentication using PyJWT (HS256 algorithm)
- **Password Hashing**: Argon2 via pwdlib (modern, recommended over bcrypt)
- **Token Types**:
  - Access tokens (30 min expiration)
  - Refresh tokens (7 day expiration)
- **Security Utilities**: Located in `src/app/core/security.py`
  - `get_password_hash()` - Hash passwords with Argon2
  - `verify_password()` - Verify password against hash
  - `create_access_token()` - Generate JWT access tokens
  - `create_refresh_token()` - Generate JWT refresh tokens
  - `decode_token()` - Validate and decode JWT tokens
- **Authentication Dependencies**: Located in `src/app/core/deps.py`
  - `get_current_user()` - Extract and validate user from JWT
  - `get_current_active_user()` - Ensure user is active
  - `get_current_superuser()` - Ensure user has superuser privileges
- **Type Aliases**: Use `CurrentUser`, `CurrentActiveUser`, `CurrentSuperUser` for cleaner dependency injection

### Database Layer
- **Base Model**: All models inherit from `Base` (AsyncAttrs + DeclarativeBase) in `src/app/db/base.py`
- **TimestampMixin**: Provides automatic `created_at` and `updated_at` fields using `datetime.utcnow`
- **Session Factory**: `AsyncSessionLocal` created with `expire_on_commit=False` and `autoflush=False`
- **Dependency Injection**: `get_db()` generator provides sessions with automatic commit/rollback/close

### Configuration Management
- Centralized in `src/app/core/config.py` using Pydantic Settings
- Environment variables loaded from `.env` file (must be mounted in Docker via `env_file`)
- Settings accessed via singleton `settings` instance
- **Critical**: `.env` file must be listed in `docker-compose.yml` under `env_file` for JWT tokens to work correctly
- Database URL dynamically set in Alembic's `env.py` from settings

### Alembic Migration Strategy
- **Async migrations**: `alembic/env.py` configured for async engine
- **Auto-detection**: Configured with `compare_type=True` and `compare_server_default=True`
- **Model imports**: All models must be imported in `src/app/db/base.py` for autogenerate to work
- **Database URL**: Automatically pulled from `settings.DATABASE_URL`

### API Structure
- **Versioning**: API routes prefixed with `/api/v1`
- **Route modules**: Separate router files in `src/app/api/routes/`
  - `auth.py` - Authentication endpoints (register, login, tokens, /me, password reset)
  - `users.py` - User CRUD operations (protected)
  - `securities.py` - Securities tracking (search, details, sync, prices) with yfinance integration
  - `health.py` - Health check endpoints
- **Dependency injection**: Database sessions injected via FastAPI's `Depends(get_db)`
- **Response models**: Pydantic schemas in `src/app/schemas/` for request/response validation
- **Authorization**: Routes use dependency injection to enforce authentication and permission checks

### Test Structure (FastAPI Template Pattern)
Tests are organized following the official FastAPI full-stack template:
```
tests/
├── conftest.py              # Shared fixtures (SQLite in-memory DB, test client, auth)
├── api/
│   └── routes/
│       ├── test_login.py    # Authentication endpoint tests (72 tests)
│       ├── test_users.py    # User endpoint tests
│       ├── test_securities.py # Securities endpoint tests (17 tests)
│       └── test_utils.py    # Health check tests
└── utils/
    └── test_security.py     # Security utility tests (password, JWT)
```

**Test Coverage:** 89 tests passing
- Authentication tests: 72 tests (register, login, tokens, password reset, /me)
- Securities tests: 17 tests (search, details, sync, prices)
- Security utility tests: Password hashing, JWT token generation/validation

**Test Fixtures** (in `conftest.py`):
- `test_engine` - SQLite in-memory database engine
- `test_db` - Database session for tests
- `client` - AsyncClient with dependency overrides
- `test_user` - Regular user fixture
- `test_superuser` - Superuser fixture
- `test_inactive_user` - Inactive user fixture
- `auth_headers`, `superuser_auth_headers` - Pre-authenticated request headers

**Test Markers**:
- `@pytest.mark.unit` - Unit tests (security, utilities)
- `@pytest.mark.integration` - Integration tests (API endpoints)

### Securities Tracking Architecture
- **Models**: `Security` and `SecurityPrice` in `src/app/models/`
  - `Security`: Symbol, name, asset class, currency (from yfinance)
  - `SecurityPrice`: OHLCV data with interval support (1m, 1h, 1d, 1wk, 1mo)
- **Service Layer**: `YFinanceService` in `src/app/services/yfinance_service.py`
  - `search_securities()` - Search for securities
  - `get_security_info()` - Fetch security details from Yahoo Finance
  - `sync_security_data()` - Sync security and historical prices
  - `get_historical_prices()` - Retrieve stored price data with filtering
- **Schemas**: Request/response models in `src/app/schemas/security.py`
  - Search requests/responses
  - Security detail models
  - Price data models with timeframe support
- **Database Indexes**: Optimized for symbol lookup and date-range queries

### Development vs Production
- In development mode (`ENVIRONMENT=development`), tables are auto-created via `Base.metadata.create_all()` in lifespan startup
- In production, rely exclusively on Alembic migrations
- CORS settings configured via environment variables in `Settings` class

## Key Patterns

### Adding a New Model
1. Create model file in `src/app/models/` inheriting from `Base` and `TimestampMixin`
2. Import model in `src/app/db/base.py` (required for Alembic autogenerate)
3. Create Pydantic schemas in `src/app/schemas/`
4. Generate migration: `alembic revision --autogenerate -m "add_model_name"`
5. Review and apply: `alembic upgrade head`

### Creating an API Endpoint
1. Create router in `src/app/api/routes/`
2. Use `AsyncSession = Depends(get_db)` for database access
3. Import and include router in `src/main.py` with appropriate prefix and tags
4. Use async/await for all database operations
5. Return Pydantic response models for proper serialization
6. Add tests in `tests/api/routes/test_<endpoint>.py`
7. For protected endpoints, use `CurrentActiveUser` dependency

**Example:**
```python
# src/app/api/routes/my_endpoint.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, CurrentActiveUser

router = APIRouter()

@router.get("/items")
async def get_items(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentActiveUser = None,  # Protected route
):
    # Implementation
    pass
```

### Database Queries
```python
# Select query
result = await db.execute(select(User).where(User.id == user_id))
user = result.scalar_one_or_none()

# Pagination
result = await db.execute(select(User).offset(skip).limit(limit))
users = result.scalars().all()
```

## Docker Services

- **app**: FastAPI application on port 8000
- **db**: PostgreSQL 18 on port 5432
- **redis**: Redis 8 on port 6379

All services connected via `app_network` bridge network with health checks configured.
