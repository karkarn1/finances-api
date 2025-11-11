# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Last Updated:** November 11, 2025

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
- Cache Statistics: http://localhost:8000/health/cache

## Architecture

### Recent Architectural Changes (November 2025)

**Major Refactor - Repository Pattern + Service Layer (November 10-11, 2025):**

The codebase underwent a significant architectural refactor to implement clean architecture principles:

1. **Repository Pattern**: All data access goes through `BaseRepository[ModelType]` generic class
   - Location: `src/app/repositories/base.py`
   - Type-safe CRUD operations with async/await
   - Centralized query building and pagination
   - 7 model-specific repositories extending BaseRepository

2. **Service Layer**: Business logic separated from API routes
   - Location: `src/app/services/`
   - 6 service modules: user, security, yfinance, price_data, currency, exchange_rate
   - Services use repositories for data access
   - Encapsulate complex business workflows

3. **Transaction Management**: Explicit transaction control
   - `transactional()` context manager for read-write transactions
   - `read_only_transaction()` for read-only queries
   - `with_savepoint()` for nested transactions
   - Automatic rollback on exceptions

4. **Exception Hierarchy**: Centralized error handling
   - Location: `src/app/core/exceptions.py`
   - `AppException` base class with auto HTTP status mapping
   - Specific exceptions: `ValidationError`, `AuthenticationError`, `NotFoundError`, `ConflictError`, `ExternalAPIError`
   - Automatic conversion to HTTP responses

5. **Logging Middleware**: Request/response logging
   - Location: `src/app/middleware/logging.py`
   - Logs all requests with method, path, status, timing
   - Adds `X-Process-Time` header with request duration
   - Structured logging for production monitoring

**Benefits:**
- Better separation of concerns
- Easier testing (mock repositories, not database)
- Type safety throughout the stack
- Consistent error handling
- Centralized transaction management

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

**Models (9 total)** - Located in `src/app/models/`:

1. **User** (`user.py`): Authentication and user management
   - Email (unique, indexed), hashed_password, is_active, is_superuser
   - Password reset tokens with expiration
   - Relationships: accounts, financial institutions

2. **Security** (`security.py`): Stock/ETF tracking
   - Symbol (unique), name, asset_class, exchange, currency, sector, industry
   - Data synced from Yahoo Finance via yfinance
   - Relationships: security_prices, holdings

3. **SecurityPrice** (`security_price.py`): OHLCV historical data
   - Security foreign key, date, interval (1m, 1h, 1d, 1wk, 1mo)
   - Open, high, low, close, volume
   - Composite unique constraint (security_id, date, interval)
   - Indexes for efficient date-range queries

4. **Currency** (`currency.py`): ISO 4217 currency codes
   - **Breaking Change (Nov 11)**: `code` is now PRIMARY KEY (was UUID `id`)
   - Code (3-letter ISO, PRIMARY KEY), name, symbol
   - Relationships: exchange rates, accounts, securities

5. **CurrencyRate** (`currency_rate.py`): Exchange rates
   - Base currency, target currency, rate, date
   - Synced from exchangerate-api.com
   - Historical tracking for date-based conversions

6. **FinancialInstitution** (`financial_institution.py`): Banks, brokerages
   - User foreign key, name, institution_type, website
   - Relationships: accounts

7. **Account** (`account.py`): User financial accounts
   - User foreign key, institution foreign key (nullable)
   - Name, account_type (enum: 10 types), currency_code, description
   - Account types: CHECKING, SAVINGS, TFSA, RRSP, FHSA, MARGIN, CREDIT_CARD, LINE_OF_CREDIT, PAYMENT_PLAN, MORTGAGE
   - Relationships: account_values, holdings

8. **AccountValue** (`account_value.py`): Balance history
   - Account foreign key, date, value
   - Tracks account balances over time for historical analysis

9. **Holding** (`holding.py`): Investment positions
   - Account foreign key, security foreign key
   - Quantity (Decimal for fractional shares), average_cost
   - Composite unique constraint (account_id, security_id)

**Base Infrastructure:**
- **Base Model**: All models inherit from `Base` (AsyncAttrs + DeclarativeBase) in `src/app/db/base.py`
- **TimestampMixin**: Provides automatic `created_at` and `updated_at` fields using `datetime.utcnow`
- **Session Factory**: `AsyncSessionLocal` created with `expire_on_commit=False` and `autoflush=False`
- **Dependency Injection**: `get_db()` generator provides sessions with automatic commit/rollback/close

**Repositories** - Located in `src/app/repositories/`:
- `BaseRepository[ModelType]`: Generic CRUD operations
- `UserRepository`: User-specific queries
- `SecurityRepository`: Security search and filtering
- `CurrencyRepository`: Currency management
- `FinancialInstitutionRepository`: Institution queries by user
- `AccountRepository`: Account queries by user
- `HoldingRepository`: Holdings queries by account/user

### Service Layer

**Services** - Located in `src/app/services/`:

1. **UserService** (`user_service.py`): User management
   - User CRUD operations
   - Authentication (login, password reset)
   - User profile updates

2. **SecurityService** (`security_service.py`): Securities management
   - Database search with fallback to yfinance
   - Security CRUD operations
   - Integration with YFinanceService

3. **YFinanceService** (`yfinance_service.py`): Yahoo Finance integration
   - Search securities on Yahoo Finance
   - Fetch security details (name, sector, industry, etc.)
   - Sync historical prices with multiple intervals
   - Uses requests-cache with Redis backend

4. **PriceDataService** (`price_data_service.py`): Price data management
   - Store and retrieve historical prices
   - Filter by date range and interval
   - Price data aggregation

5. **CurrencyService** (`currency_service.py`): Currency management
   - Currency CRUD operations
   - Integration with ExchangeRateService

6. **ExchangeRateService** (`exchange_rate_service.py`): Exchange rate syncing
   - Fetch rates from exchangerate-api.com
   - Store historical exchange rates
   - Date-based rate lookups

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

**Route Modules** - Located in `src/app/api/routes/`:

1. **auth.py** - Authentication endpoints (8 endpoints):
   - POST `/register` - User registration
   - POST `/login` - Login with access + refresh tokens
   - POST `/refresh` - Refresh access token
   - POST `/forgot-password` - Request password reset
   - POST `/reset-password` - Reset password with token
   - GET `/me` - Get current user profile
   - PATCH `/me` - Update user profile
   - POST `/logout` - Logout (client-side token removal)

2. **users.py** - User management (5 endpoints):
   - GET `/` - List users (paginated, superuser only)
   - POST `/` - Create user (superuser only)
   - GET `/{user_id}` - Get user by ID
   - PATCH `/{user_id}` - Update user
   - DELETE `/{user_id}` - Delete user

3. **securities.py** - Securities tracking (4 endpoints):
   - GET `/search?q={query}` - Search securities (DB + yfinance fallback)
   - GET `/{symbol}` - Get security details
   - POST `/{symbol}/sync` - Sync security data from Yahoo Finance
   - GET `/{symbol}/prices` - Get historical prices (with interval filtering)

4. **currencies.py** - Currency management (4 endpoints):
   - GET `/` - List currencies
   - POST `/` - Create currency
   - GET `/{code}` - Get currency by code
   - POST `/{code}/rates` - Sync exchange rates from API

5. **financial_institutions.py** - Institution management (5 endpoints):
   - GET `/` - List user's institutions
   - POST `/` - Create institution
   - GET `/{id}` - Get institution by ID
   - PATCH `/{id}` - Update institution
   - DELETE `/{id}` - Delete institution

6. **accounts.py** - Account management (5 endpoints):
   - GET `/` - List user's accounts
   - POST `/` - Create account
   - GET `/{id}` - Get account by ID
   - PATCH `/{id}` - Update account
   - DELETE `/{id}` - Delete account
   - GET `/{id}/values` - Get account balance history

7. **holdings.py** - Investment holdings (5 endpoints):
   - GET `/` - List holdings (by user or account)
   - POST `/` - Create holding (auto-syncs security if not exists)
   - GET `/{id}` - Get holding by ID
   - PATCH `/{id}` - Update holding
   - DELETE `/{id}` - Delete holding

8. **health.py** - Health checks (3 endpoints):
   - GET `/health` - Basic health check
   - GET `/health/database` - Database connectivity check
   - GET `/health/cache` - Redis cache statistics

**Total: 40+ API endpoints**

- **Versioning**: API routes prefixed with `/api/v1`
- **Dependency injection**: Database sessions injected via FastAPI's `Depends(get_db)`
- **Response models**: Pydantic schemas in `src/app/schemas/` for request/response validation
- **Authorization**: Routes use dependency injection to enforce authentication and permission checks

### Redis Caching (Fully Implemented)

**Status**: ✅ Operational (not "planned" or "infrastructure ready")

**Implementation**:
- **requests-cache** library with Redis backend for yfinance HTTP caching
- Configuration in `src/app/services/yfinance_service.py`
- Automatic caching of all Yahoo Finance API requests

**Cache Expiration Policies**:
- **Daily data** (1d, 1wk, 1mo intervals): 24 hours
- **Intraday data** (1m, 1h intervals): 15 minutes
- **Security info** (name, sector, industry): 6 hours

**Health Monitoring**:
- Endpoint: `GET /health/cache`
- Returns: Hit count, miss count, total requests, hit rate

**Benefits**:
- Reduces API calls to Yahoo Finance
- Improves response times
- Handles rate limiting gracefully
- Respects data freshness requirements

### Test Structure

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
├── repositories/            # Repository layer tests
├── services/                # Service layer tests
└── utils/
    └── test_security.py     # Security utility tests (password, JWT)
```

**Test Coverage:** 32 test files with comprehensive coverage
- Authentication tests: 72 tests (register, login, tokens, password reset, /me)
- Securities tests: 17 tests (search, details, sync, prices)
- Repository tests: Data access layer testing
- Service tests: Business logic testing
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
- `@pytest.mark.unit` - Unit tests (security, utilities, repositories, services)
- `@pytest.mark.integration` - Integration tests (API endpoints)

### Development vs Production
- In development mode (`ENVIRONMENT=development`), tables are auto-created via `Base.metadata.create_all()` in lifespan startup
- In production, rely exclusively on Alembic migrations
- CORS settings configured via environment variables in `Settings` class

## Key Patterns

### Adding a New Model

1. Create model file in `src/app/models/` inheriting from `Base` and `TimestampMixin`
2. Import model in `src/app/db/base.py` (required for Alembic autogenerate)
3. Create repository in `src/app/repositories/` extending `BaseRepository[ModelType]`
4. Create service in `src/app/services/` using the repository
5. Create Pydantic schemas in `src/app/schemas/`
6. Generate migration: `make migrate-create MSG="add_model_name"`
7. Review and apply: `make migrate`

### Creating an API Endpoint

1. Create router in `src/app/api/routes/`
2. Inject services via `Depends()` (services handle data access via repositories)
3. Import and include router in `src/main.py` with appropriate prefix and tags
4. Use async/await for all operations
5. Return Pydantic response models for proper serialization
6. Add tests in `tests/api/routes/test_<endpoint>.py`
7. For protected endpoints, use `CurrentActiveUser` dependency

**Example:**
```python
# src/app/api/routes/my_endpoint.py
from fastapi import APIRouter, Depends
from app.core.deps import get_db, CurrentActiveUser
from app.services.my_service import MyService

router = APIRouter()

@router.get("/items")
async def get_items(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentActiveUser = None,  # Protected route
):
    service = MyService(db)
    items = await service.get_items(user_id=current_user.id)
    return items
```

### Using Repository Pattern

```python
# In service layer (src/app/services/my_service.py)
from app.repositories.my_repository import MyRepository
from app.core.transaction import transactional, read_only_transaction

class MyService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = MyRepository(db)

    async def get_item(self, item_id: UUID) -> Item:
        # Read-only operation
        async with read_only_transaction(self.db):
            return await self.repo.get_by_id(item_id)

    async def create_item(self, data: ItemCreate) -> Item:
        # Write operation with auto-commit
        async with transactional(self.db):
            return await self.repo.create(data)

    async def complex_operation(self, data: ComplexData) -> Result:
        # Multiple operations in single transaction
        async with transactional(self.db):
            item1 = await self.repo.create(data.part1)

            # Nested savepoint for partial rollback
            async with with_savepoint(self.db):
                item2 = await self.repo.create(data.part2)

            return Result(item1=item1, item2=item2)
```

### Database Queries

```python
# In repository (src/app/repositories/my_repository.py)
from app.repositories.base import BaseRepository

class MyRepository(BaseRepository[MyModel]):
    async def get_by_custom_field(self, field_value: str) -> MyModel | None:
        result = await self.db.execute(
            select(MyModel).where(MyModel.custom_field == field_value)
        )
        return result.scalar_one_or_none()

    async def get_paginated(self, skip: int, limit: int) -> list[MyModel]:
        result = await self.db.execute(
            select(MyModel).offset(skip).limit(limit)
        )
        return result.scalars().all()
```

### Exception Handling

```python
# In service layer
from app.core.exceptions import NotFoundError, ValidationError, ConflictError

class MyService:
    async def get_item(self, item_id: UUID) -> Item:
        item = await self.repo.get_by_id(item_id)
        if not item:
            # Auto-converts to 404 HTTP response
            raise NotFoundError(f"Item {item_id} not found")
        return item

    async def create_item(self, data: ItemCreate) -> Item:
        # Check for duplicates
        existing = await self.repo.get_by_field("name", data.name)
        if existing:
            # Auto-converts to 409 HTTP response
            raise ConflictError(f"Item with name {data.name} already exists")

        # Validate business rules
        if data.value < 0:
            # Auto-converts to 400 HTTP response
            raise ValidationError("Value cannot be negative")

        return await self.repo.create(data)
```

## Docker Services

- **app**: FastAPI application on port 8000
- **db**: PostgreSQL 18 on port 5432
- **redis**: Redis 8 on port 6379

All services connected via `app_network` bridge network with health checks configured.

## Environment Variables

Required in `.env` file (located in project root):

```env
# Required for JWT authentication
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/finances_db
REDIS_URL=redis://redis:6379/0
ENVIRONMENT=development

# Optional: Currency exchange rate API
EXCHANGE_RATE_API_KEY=your-api-key-here
```

**Critical**: `.env` must be listed in `docker-compose.yml` under `env_file` for the app service.

## Dependencies

**Core** (pyproject.toml):
- **FastAPI** >=0.115.0 - Web framework
- **SQLAlchemy** >=2.0.35 - Async ORM
- **Alembic** >=1.13.3 - Database migrations
- **asyncpg** >=0.29.0 - PostgreSQL async driver
- **redis** >=5.2.0 - Redis client
- **requests-cache** >=1.2.0 - HTTP caching with Redis backend
- **PyJWT** >=2.9.0 - JWT token handling
- **pwdlib[argon2]** >=0.2.1 - Password hashing
- **yfinance** >=0.2.40 - Yahoo Finance data
- **pandas** >=2.2.0 - Data manipulation
- **slowapi** >=0.1.9 - Rate limiting
- **pydantic** >=2.9.2 - Data validation
- **pydantic-settings** >=2.6.0 - Settings management

**Development**:
- **pytest** >=8.3.3 - Testing framework
- **pytest-asyncio** - Async test support
- **ruff** >=0.7.4 - Linter and formatter
- **mypy** >=1.13.0 - Type checker
- **httpx** - Async HTTP client for tests

## Integration Points

### Frontend Integration

The API is fully integrated with the React frontend (`finances-app/`):

**Authentication Flow**:
1. Frontend sends credentials to `/api/v1/auth/login`
2. Backend validates and returns JWT tokens
3. Frontend stores tokens and includes in `Authorization: Bearer <token>` header
4. Backend validates JWT via `get_current_user()` dependency

**Integrated Features**:
- ✅ Authentication (login, register, password reset)
- ✅ User profile management
- ✅ Securities search and tracking
- ✅ Currency management
- ✅ Financial institutions
- ✅ Accounts with balance history
- ✅ Holdings management

**Not Yet Integrated**:
- ❌ Dashboard metrics (needs endpoints)
- ❌ Transactions (needs model + endpoints)
- ❌ Budget tracking (needs model + endpoints)
- ❌ Goals tracking (needs model + endpoints)

### External APIs

**Yahoo Finance (yfinance)**:
- Security search and details
- Historical price data (OHLCV)
- Multiple intervals: 1m, 1h, 1d, 1wk, 1mo
- Cached via Redis (15min-24h depending on data type)

**exchangerate-api.com**:
- Currency exchange rates
- Historical rates for date-based conversions
- API key required (optional, has fallback)

## Breaking Changes

### November 11, 2025: Currency Model Refactor

**Change**: Currency `code` is now PRIMARY KEY (was UUID `id`)

**Migration**:
```bash
# Already applied in alembic/versions/
# Migration: make currency code primary key
make migrate
```

**Impact**:
- All currency references updated to use `code` instead of `id`
- Foreign keys in Account and Security models updated
- API endpoints now accept currency code (e.g., "USD") instead of UUID
- Frontend updated to match new schema

**Rationale**:
- Currency codes are natural primary keys (ISO 4217 standard)
- Eliminates unnecessary UUID column
- Simpler API interface
- More intuitive for users

## Known Issues & Future Work

### Planned Features

**Backend**:
- Transactions model and endpoints (for account transactions)
- Budget tracking (budget categories, allocations, tracking)
- Expense/income categories (user-defined categories)
- Goals tracking API (financial goals with progress)
- Email verification system
- Rate limiting configuration (slowapi already included)
- WebSocket support for real-time updates
- Additional financial data providers (beyond yfinance)

**Infrastructure**:
- Rate limiting per-endpoint configuration
- Request validation improvements
- More comprehensive error messages
- API versioning strategy (currently v1)

### Performance Optimizations

**Already Implemented**:
- ✅ Redis HTTP caching for yfinance (15min-24h TTL)
- ✅ Database connection pooling
- ✅ Async I/O throughout
- ✅ Efficient indexes on models

**Future**:
- Query result caching for expensive operations
- Background tasks for data syncing
- Batch operations for bulk imports

## Troubleshooting

### Common Issues

**1. Authentication not working**
- Verify `.env` file exists and contains `SECRET_KEY`
- Ensure `.env` is listed in `docker-compose.yml` under `env_file`
- Check logs: `make logs-app`

**2. Database migrations fail**
- Ensure models are imported in `src/app/db/base.py`
- Check migration files in `alembic/versions/`
- View migration history: `make migrate-history`

**3. Redis caching not working**
- Check Redis is running: `make status`
- Verify `REDIS_URL` in `.env`
- Check cache statistics: `curl http://localhost:8000/health/cache`

**4. Tests failing**
- Tests use SQLite in-memory (no Docker required for pytest)
- Check fixtures in `conftest.py`
- Run with verbose: `docker-compose exec app pytest -v`

### Debugging

**View logs**:
```bash
make logs-app    # API logs
make logs-db     # PostgreSQL logs
make logs-redis  # Redis logs
```

**Access shells**:
```bash
make shell       # API container shell
make db-shell    # PostgreSQL psql
make redis-shell # Redis CLI
```

**Check health**:
```bash
make health      # Basic health check
curl http://localhost:8000/health/database  # Database check
curl http://localhost:8000/health/cache     # Cache statistics
```

---

**Last Updated:** November 11, 2025
**Application Status:** Production-ready with repository pattern, service layer, and comprehensive API coverage
**Test Coverage:** 32 test files with unit and integration tests
