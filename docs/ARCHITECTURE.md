# Backend Architecture

This document provides a comprehensive overview of the Finances API architecture, design patterns, and architectural decisions.

## Table of Contents

- [System Overview](#system-overview)
- [Architectural Patterns](#architectural-patterns)
- [Layer Architecture](#layer-architecture)
- [Data Flow](#data-flow)
- [Core Components](#core-components)
- [Design Patterns](#design-patterns)
- [External Integrations](#external-integrations)
- [Security Architecture](#security-architecture)
- [Performance & Scalability](#performance--scalability)
- [Error Handling](#error-handling)
- [Testing Strategy](#testing-strategy)

## System Overview

The Finances API is built using a **layered architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)                  │
│         Routes, Endpoints, Request/Response             │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                   Service Layer                         │
│         Business Logic, Orchestration                   │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                 Repository Layer                        │
│         Data Access, Query Building                     │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                  Database Layer                         │
│         PostgreSQL, SQLAlchemy Models                   │
└─────────────────────────────────────────────────────────┘
```

**Key Technologies:**
- **FastAPI** - Async web framework with automatic OpenAPI generation
- **PostgreSQL 18** - Primary data store with async operations
- **SQLAlchemy 2.0** - Async ORM with type hints
- **Redis 8** - Caching layer for external API responses
- **Pydantic 2.x** - Data validation and serialization

## Architectural Patterns

### 1. Repository Pattern

The Repository pattern abstracts data access logic, providing a clean interface between the service layer and the database.

**Benefits:**
- Separation of concerns
- Easier testing (mock repositories)
- Centralized query logic
- Database-agnostic business logic

**Implementation:**

```python
# Base repository with common operations
class BaseRepository(Generic[ModelT]):
    def __init__(self, model: Type[ModelT]):
        self.model = model

    async def get(self, db: AsyncSession, id: UUID) -> ModelT | None:
        result = await db.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, obj_in: BaseModel) -> ModelT:
        obj = self.model(**obj_in.model_dump())
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

# Specialized repository
class UserRepository(BaseRepository[User]):
    async def get_by_email(self, db: AsyncSession, email: str) -> User | None:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()
```

**Repository Examples:**
- `UserRepository` - User data access
- `SecurityRepository` - Securities and financial instruments
- `SecurityPriceRepository` - Historical price data
- `AccountRepository` - User accounts
- `HoldingRepository` - Investment holdings

### 2. Service Layer Pattern

The Service layer contains business logic and orchestrates operations across multiple repositories.

**Benefits:**
- Business logic isolation
- Reusability across endpoints
- Transaction management
- Complex operation orchestration

**Implementation:**

```python
class SecurityService:
    def __init__(
        self,
        security_repo: SecurityRepository,
        price_repo: SecurityPriceRepository,
        yfinance_service: YFinanceService
    ):
        self.security_repo = security_repo
        self.price_repo = price_repo
        self.yfinance_service = yfinance_service

    async def sync_security_data(
        self,
        db: AsyncSession,
        symbol: str
    ) -> Security:
        # 1. Fetch from yfinance (cached via Redis)
        ticker_data = await self.yfinance_service.get_ticker_info(symbol)

        # 2. Update or create security
        security = await self.security_repo.get_by_symbol(db, symbol)
        if security:
            security = await self.security_repo.update(db, security, ticker_data)
        else:
            security = await self.security_repo.create(db, ticker_data)

        # 3. Fetch and store price history
        prices = await self.yfinance_service.get_historical_prices(symbol)
        await self.price_repo.bulk_create(db, prices)

        return security
```

**Service Examples:**
- `UserService` - User management and authentication
- `SecurityService` - Security data synchronization
- `YFinanceService` - Yahoo Finance API integration
- `PriceDataService` - Price data aggregation
- `CurrencyService` - Currency and exchange rates
- `ExchangeService` - Currency conversion logic

### 3. Dependency Injection Pattern

FastAPI's dependency injection system is used extensively for:
- Database session management
- User authentication
- Repository and service instantiation

**Implementation:**

```python
# Database session dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Current user dependency (with authentication)
async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    payload = decode_jwt(token)
    user = await user_repo.get(db, payload["sub"])
    if not user or not user.is_active:
        raise UnauthorizedError()
    return user

# Type alias for cleaner route signatures
CurrentActiveUser = Annotated[User, Depends(get_current_user)]

# Usage in routes
@router.get("/users/me")
async def get_me(current_user: CurrentActiveUser):
    return current_user
```

### 4. Transaction Management Pattern

Automatic transaction management with rollback on exceptions.

**Implementation:**

```python
# Automatic commit on success, rollback on exception
@router.post("/accounts")
async def create_account(
    account_in: AccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentActiveUser
):
    # Transaction starts automatically
    account = await account_repo.create(db, account_in)

    # If exception occurs, transaction is rolled back
    # If success, transaction is committed

    return account
```

**Explicit transaction control when needed:**

```python
async def complex_operation(db: AsyncSession):
    async with db.begin():
        # Multiple operations in single transaction
        account = await account_repo.create(db, account_data)
        holding = await holding_repo.create(db, holding_data)
        value = await value_repo.create(db, value_data)

        # All succeed or all rollback
```

### 5. Exception Hierarchy Pattern

Custom exception hierarchy for precise error handling and appropriate HTTP status codes.

**Implementation:**

```python
# Base exception
class AppException(Exception):
    """Base application exception"""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

# Domain-specific exceptions
class ResourceNotFoundError(AppException):
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            f"{resource} with identifier '{identifier}' not found",
            status_code=404
        )

class UnauthorizedError(AppException):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, status_code=401)

class ValidationError(AppException):
    def __init__(self, message: str):
        super().__init__(message, status_code=400)

# Exception handler
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message}
    )
```

## Layer Architecture

### API Layer (Routes)

**Location:** `src/app/api/routes/`

**Responsibilities:**
- HTTP request handling
- Request validation (via Pydantic)
- Response serialization
- Authentication/authorization checks
- Endpoint documentation (docstrings)

**Example:**

```python
@router.get("/securities/{symbol}", response_model=SecurityResponse)
async def get_security(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentActiveUser
) -> Security:
    """
    Get security details by symbol.

    - **symbol**: Security ticker symbol (e.g., AAPL, GOOGL)
    - Returns: Security details including current price, metadata
    """
    security = await security_repo.get_by_symbol(db, symbol)
    if not security:
        raise ResourceNotFoundError("Security", symbol)
    return security
```

**Route Modules:**
- `auth.py` - Authentication (login, register, password reset)
- `users.py` - User management
- `securities.py` - Securities and price data
- `currencies.py` - Currency management
- `financial_institutions.py` - Institution management
- `accounts.py` - Account CRUD operations
- `account_values.py` - Account valuation history
- `holdings.py` - Investment holdings

### Service Layer

**Location:** `src/app/services/`

**Responsibilities:**
- Business logic implementation
- Multi-repository orchestration
- External API integration
- Data transformation
- Complex calculations

**Example:**

```python
class UserService:
    async def authenticate_user(
        self,
        db: AsyncSession,
        email: str,
        password: str
    ) -> User | None:
        # 1. Fetch user
        user = await self.user_repo.get_by_email(db, email)
        if not user:
            return None

        # 2. Verify password
        if not verify_password(password, user.hashed_password):
            return None

        # 3. Check if active
        if not user.is_active:
            raise ValidationError("Account is disabled")

        return user
```

### Repository Layer

**Location:** `src/app/repositories/`

**Responsibilities:**
- Database query construction
- CRUD operations
- Complex queries
- Data access abstraction

**Example:**

```python
class SecurityRepository(BaseRepository[Security]):
    async def search(
        self,
        db: AsyncSession,
        query: str,
        limit: int = 10
    ) -> list[Security]:
        stmt = (
            select(Security)
            .where(
                or_(
                    Security.symbol.ilike(f"%{query}%"),
                    Security.name.ilike(f"%{query}%")
                )
            )
            .limit(limit)
        )
        result = await db.execute(stmt)
        return result.scalars().all()
```

### Database Layer

**Location:** `src/app/models/`, `src/app/db/`

**Responsibilities:**
- SQLAlchemy model definitions
- Database relationships
- Constraints and indexes
- Connection management

**Example:**

```python
class Security(Base, TimestampMixin):
    __tablename__ = "securities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    security_type: Mapped[SecurityType] = mapped_column(Enum(SecurityType))
    exchange: Mapped[str | None] = mapped_column(String(50))
    currency_code: Mapped[str] = mapped_column(String(3), default="USD")

    # Relationships
    prices: Mapped[list["SecurityPrice"]] = relationship(back_populates="security")
    holdings: Mapped[list["Holding"]] = relationship(back_populates="security")
```

## Data Flow

### Request Flow Example: Search Securities

```
1. Client Request
   └─> GET /api/v1/securities/search?query=AAPL

2. API Layer (routes/securities.py)
   ├─> Extract query parameter
   ├─> Validate input (Pydantic)
   └─> Authenticate user (JWT)

3. Service Layer (services/security_service.py)
   ├─> Call repository.search()
   └─> Transform results if needed

4. Repository Layer (repositories/security.py)
   ├─> Build SQL query
   └─> Execute via SQLAlchemy

5. Database Layer
   ├─> Execute SQL on PostgreSQL
   └─> Return results

6. Response Flow (reverse)
   ├─> Repository returns models
   ├─> Service returns models
   ├─> API serializes to Pydantic schema
   └─> FastAPI returns JSON
```

### Complex Flow Example: Sync Security Data

```
1. Client Request
   └─> POST /api/v1/securities/{symbol}/sync

2. API Layer
   ├─> Authenticate user
   └─> Call service.sync_security_data()

3. Service Layer (SecurityService)
   ├─> Call YFinanceService.get_ticker_info() → Redis cache check
   │   ├─> Cache hit: return cached data
   │   └─> Cache miss: fetch from yfinance → cache → return
   │
   ├─> Update or create Security via repository
   │
   ├─> Call YFinanceService.get_historical_prices() → Redis cache
   │
   └─> Bulk insert prices via PriceRepository

4. Multiple Database Operations
   ├─> Update security metadata
   ├─> Insert/update price records
   └─> Commit transaction

5. Response
   └─> Return updated Security object
```

## Core Components

### Authentication System

**JWT-based authentication with access and refresh tokens.**

**Flow:**

```python
# 1. User Login
POST /api/v1/auth/login
{
    "email": "user@example.com",
    "password": "password123"
}

# 2. Server Response
{
    "access_token": "eyJ...",  # 30 min expiry
    "refresh_token": "eyJ...", # 7 days expiry
    "token_type": "bearer"
}

# 3. Authenticated Request
GET /api/v1/users/me
Headers: {
    "Authorization": "Bearer eyJ..."
}

# 4. Token Refresh (when access token expires)
POST /api/v1/auth/refresh
Headers: {
    "Authorization": "Bearer <refresh_token>"
}
```

**Security Features:**
- Argon2 password hashing (via pwdlib)
- JWT token signing with HS256
- Token expiration validation
- Refresh token rotation
- Password reset via secure tokens

### Caching Layer (Redis)

**Purpose:** Reduce external API calls and improve response times.

**Implementation:**

```python
class YFinanceService:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.cache_ttl = 3600  # 1 hour

    async def get_ticker_info(self, symbol: str) -> dict:
        # Check cache
        cache_key = f"ticker:{symbol}"
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

        # Fetch from yfinance
        ticker = yf.Ticker(symbol)
        data = ticker.info

        # Cache result
        await self.redis.setex(
            cache_key,
            self.cache_ttl,
            json.dumps(data)
        )

        return data
```

**Cached Data:**
- yfinance HTTP requests (1 hour TTL)
- Security information (1 hour TTL)
- Exchange rates (1 hour TTL)

### Logging System

**Structured logging with correlation IDs for request tracing.**

**Implementation:**

```python
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        # Log request
        logger.info(
            "Request started",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "url": str(request.url),
                "client_ip": request.client.host
            }
        )

        # Process request
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time

        # Log response
        logger.info(
            "Request completed",
            extra={
                "correlation_id": correlation_id,
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2)
            }
        )

        return response
```

## Design Patterns

### 1. Async/Await Pattern

All I/O operations are async for maximum performance.

```python
# Database queries
user = await user_repo.get(db, user_id)

# External API calls
ticker_data = await yfinance_service.get_ticker_info(symbol)

# Cache operations
cached_data = await redis_client.get(cache_key)
```

### 2. Type Hints Pattern

Comprehensive type hints for IDE support and type checking.

```python
from typing import Annotated

async def get_user(
    db: AsyncSession,
    user_id: UUID
) -> User | None:
    return await user_repo.get(db, user_id)

# Type aliases for clarity
CurrentActiveUser = Annotated[User, Depends(get_current_user)]
```

### 3. Mixin Pattern

Reusable model mixins for common fields.

```python
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

# Usage
class User(Base, TimestampMixin):
    # Automatically has created_at and updated_at
    pass
```

### 4. Factory Pattern

Fixtures and factory functions for testing.

```python
@pytest.fixture
async def test_user(db: AsyncSession) -> User:
    user = User(
        email="test@example.com",
        hashed_password=hash_password("password123"),
        is_active=True
    )
    db.add(user)
    await db.commit()
    return user
```

## External Integrations

### Yahoo Finance (yfinance)

**Purpose:** Real-time and historical financial data.

**Integration:**

```python
class YFinanceService:
    async def get_ticker_info(self, symbol: str) -> dict:
        """Get ticker information (cached via Redis)"""
        pass

    async def get_historical_prices(
        self,
        symbol: str,
        interval: str = "1d",
        period: str = "1mo"
    ) -> list[SecurityPrice]:
        """Get historical OHLCV data"""
        pass

    async def search_securities(self, query: str) -> list[dict]:
        """Search for securities by symbol or name"""
        pass
```

**Features:**
- Automatic Redis caching
- Multiple interval support (1m, 1h, 1d, 1wk)
- Retry logic for failed requests
- Error handling for invalid symbols

## Security Architecture

### Authentication Flow

```
1. User submits credentials
2. Server validates credentials
3. Server generates JWT access + refresh tokens
4. Client stores tokens securely
5. Client includes access token in Authorization header
6. Server validates token on each request
7. On expiry, client uses refresh token to get new tokens
```

### Authorization

**Role-based access control (RBAC):**

```python
# Check if user is admin
async def get_current_admin_user(
    current_user: CurrentActiveUser
) -> User:
    if not current_user.is_superuser:
        raise ForbiddenError("Admin access required")
    return current_user

# Usage
@router.get("/admin/users")
async def list_all_users(
    admin_user: Annotated[User, Depends(get_current_admin_user)]
):
    # Only accessible by admins
    pass
```

### Data Protection

- **Password hashing:** Argon2 algorithm
- **Token encryption:** HS256 JWT signing
- **Database:** PostgreSQL with SSL in production
- **Secrets management:** Environment variables
- **CORS:** Configured allowed origins

## Performance & Scalability

### Database Optimization

**Indexes:**
```python
class Security(Base):
    symbol: Mapped[str] = mapped_column(String(20), index=True, unique=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
```

**Connection Pooling:**
```python
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20
)
```

**Async Operations:**
- All database queries use async/await
- Non-blocking I/O for external APIs
- Concurrent request handling

### Caching Strategy

**Redis caching for:**
- yfinance API responses (1 hour TTL)
- Security metadata (1 hour TTL)
- Exchange rates (1 hour TTL)

**Cache invalidation:**
- TTL-based expiration
- Manual invalidation on data updates

### Pagination

```python
@router.get("/securities")
async def list_securities(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    securities = await security_repo.get_multi(db, skip=skip, limit=limit)
    return securities
```

## Error Handling

### Exception Hierarchy

```
AppException (base)
├── ResourceNotFoundError (404)
├── UnauthorizedError (401)
├── ForbiddenError (403)
├── ValidationError (400)
├── ConflictError (409)
└── ServiceUnavailableError (503)
```

### Global Exception Handler

```python
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception",
        exc_info=exc,
        extra={"correlation_id": request.state.correlation_id}
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )
```

### Validation Errors

Pydantic automatically validates request bodies and returns 422 with details:

```json
{
    "detail": [
        {
            "loc": ["body", "email"],
            "msg": "value is not a valid email address",
            "type": "value_error.email"
        }
    ]
}
```

## Testing Strategy

### Test Pyramid

```
         /\
        /  \   E2E Tests (via frontend)
       /____\
      /      \  Integration Tests
     /________\
    /          \ Unit Tests
   /____________\
```

### Unit Tests

Test individual functions in isolation:

```python
@pytest.mark.unit
async def test_hash_password():
    password = "mypassword123"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)
```

### Integration Tests

Test multiple layers together:

```python
@pytest.mark.integration
async def test_create_account(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/v1/accounts",
        json={"name": "Test Account", "account_type": "INVESTMENT"},
        headers=auth_headers
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Account"
```

### Test Database

Uses SQLite in-memory for fast, isolated tests:

```python
@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    # Create in-memory SQLite database
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Yield session
    async with AsyncSessionLocal() as session:
        yield session
```

## Deployment Architecture

### Docker Compose Services

```yaml
services:
  app:        # FastAPI application
  db:         # PostgreSQL 18
  redis:      # Redis 8
```

### Health Checks

```python
@router.get("/health")
async def health_check():
    return {"status": "healthy"}

@router.get("/health/db")
async def health_check_db(db: AsyncSession = Depends(get_db)):
    # Test database connection
    await db.execute(text("SELECT 1"))
    return {"status": "healthy", "database": "connected"}

@router.get("/health/redis")
async def health_check_redis(redis: Redis = Depends(get_redis)):
    # Test Redis connection
    await redis.ping()
    return {"status": "healthy", "redis": "connected"}
```

### Environment Configuration

All configuration via environment variables (12-factor app):

```python
class Settings(BaseSettings):
    SECRET_KEY: str
    DATABASE_URL: str
    REDIS_URL: str
    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"
```

## Best Practices

### Code Organization

1. **One model per file** in `models/`
2. **One repository per model** in `repositories/`
3. **Group related routes** in route files
4. **Keep services focused** on single responsibility

### Type Safety

```python
# Always use type hints
async def get_user(db: AsyncSession, user_id: UUID) -> User | None:
    return await user_repo.get(db, user_id)

# Use Pydantic for validation
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
```

### Async Best Practices

```python
# Good: Await all async calls
user = await user_repo.get(db, user_id)

# Bad: Missing await
user = user_repo.get(db, user_id)  # Returns coroutine, not User!

# Good: Concurrent operations when possible
results = await asyncio.gather(
    security_repo.get(db, id1),
    security_repo.get(db, id2)
)
```

### Database Best Practices

```python
# Good: Use relationship loading
stmt = select(Account).options(selectinload(Account.holdings))

# Good: Use indexes for frequent queries
class Security(Base):
    symbol: Mapped[str] = mapped_column(index=True)

# Good: Use transactions for multiple operations
async with db.begin():
    account = await account_repo.create(db, account_data)
    holding = await holding_repo.create(db, holding_data)
```

---

**Last Updated:** November 11, 2025
