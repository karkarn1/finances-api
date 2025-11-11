# Finances API

A modern, production-ready FastAPI application for managing personal finances with async PostgreSQL, Redis caching, JWT authentication, and comprehensive financial data integration.

## Features

### Core Infrastructure
- **FastAPI** - High-performance async web framework with automatic OpenAPI documentation
- **PostgreSQL 18** - Async database operations with SQLAlchemy 2.0
- **Redis 8** - Operational caching layer for API responses and rate limiting
- **Alembic** - Database migration management with version control
- **Docker** - Containerized deployment with docker-compose orchestration
- **uv** - Fast, modern Python package management

### Architecture Patterns
- **Repository Pattern** - Clean separation of data access logic
- **Service Layer** - Business logic isolation and reusability
- **Dependency Injection** - FastAPI-native dependency management
- **Transaction Management** - Automatic rollback on exceptions
- **Exception Hierarchy** - Custom exceptions for precise error handling
- **Logging Middleware** - Request/response logging with correlation IDs

### Authentication & Security
- **JWT Authentication** - Stateless token-based authentication
- **Argon2 Password Hashing** - Modern, secure password storage via pwdlib
- **Password Reset** - Secure token-based password reset flow with email
- **Access & Refresh Tokens** - Dual token system for enhanced security
- **User Management** - Complete CRUD operations with role-based access

### Financial Data Features
- **Securities Tracking** - Real-time and historical data for stocks, ETFs, mutual funds
- **yfinance Integration** - Yahoo Finance API integration with Redis caching
- **Multi-Currency Support** - Currency management with real-time exchange rates
- **Financial Institutions** - Institution tracking and categorization
- **Account Management** - Multi-account tracking across institutions
- **Holdings Management** - Investment position tracking with valuations
- **Account Valuation** - Historical account value tracking over time
- **Price History** - OHLCV data storage with multiple interval support (1m, 1h, 1d, 1wk)

## Quick Start

### Prerequisites

- **Docker** and **Docker Compose** installed
- That's it! All other dependencies are containerized.

### Start the Application

```bash
# Start all services (PostgreSQL, Redis, API)
make start

# Run database migrations
make migrate

# View application logs
make logs-app
```

The API will be available at:
- **Application:** http://localhost:8000
- **API Documentation (Swagger):** http://localhost:8000/docs
- **Alternative Documentation (ReDoc):** http://localhost:8000/redoc
- **Health Check:** http://localhost:8000/health

### Stop the Application

```bash
make stop
```

## Table of Contents

- [Makefile Commands](#makefile-commands)
- [Project Structure](#project-structure)
- [Technology Stack](#technology-stack)
- [Database Models](#database-models)
- [API Endpoints](#api-endpoints)
- [Development](#development)
- [Testing](#testing)
- [Configuration](#configuration)
- [Documentation](#documentation)

## Makefile Commands

View all available commands:
```bash
make help
```

### Service Management
```bash
make start          # Start all services (PostgreSQL, Redis, API)
make stop           # Stop all services
make restart        # Restart all services
make down           # Stop and remove containers
make logs           # View logs from all services
make logs-app       # View application logs only
make logs-db        # View PostgreSQL logs
make logs-redis     # View Redis logs
```

### Database Operations
```bash
make migrate              # Run database migrations
make migrate-create MSG="description"  # Create new migration
make migrate-history      # View migration history
make migrate-downgrade    # Rollback one migration
make db-shell            # Open PostgreSQL shell
```

### Development Tools
```bash
make shell          # Open bash shell in app container
make test           # Run pytest test suite
make test-cov       # Run tests with coverage report
make lint           # Check code with Ruff
make lint-fix       # Auto-fix Ruff issues
make format         # Format code with Ruff
make type-check     # Run mypy type checking
```

### Container Management
```bash
make build          # Build Docker images
make rebuild        # Rebuild images without cache
make ps             # List running containers
make clean          # Remove containers and volumes
```

## Project Structure

```
finances-api/
├── src/app/                    # Application source code
│   ├── api/                    # API layer
│   │   └── routes/            # API route modules
│   │       ├── auth.py        # Authentication endpoints
│   │       ├── users.py       # User management
│   │       ├── securities.py  # Securities endpoints
│   │       ├── currencies.py  # Currency endpoints
│   │       ├── financial_institutions.py
│   │       ├── accounts.py    # Account endpoints
│   │       ├── account_values.py
│   │       └── holdings.py    # Holdings endpoints
│   ├── core/                  # Core configuration
│   │   ├── config.py         # Settings and configuration
│   │   ├── deps.py           # FastAPI dependencies
│   │   ├── exceptions.py     # Custom exception hierarchy
│   │   └── logging.py        # Logging configuration
│   ├── db/                    # Database layer
│   │   ├── base.py           # SQLAlchemy base and imports
│   │   └── session.py        # Database session management
│   ├── models/                # SQLAlchemy models
│   │   ├── user.py
│   │   ├── security.py
│   │   ├── security_price.py
│   │   ├── currency.py
│   │   ├── currency_rate.py
│   │   ├── financial_institution.py
│   │   ├── account.py
│   │   ├── account_value.py
│   │   └── holding.py
│   ├── repositories/          # Repository pattern (data access)
│   │   ├── base.py
│   │   ├── user.py
│   │   ├── security.py
│   │   ├── security_price.py
│   │   ├── account.py
│   │   ├── account_value.py
│   │   └── holding.py
│   ├── schemas/               # Pydantic schemas (validation)
│   │   ├── user.py
│   │   ├── auth.py
│   │   ├── security.py
│   │   ├── currency.py
│   │   ├── financial_institution.py
│   │   ├── account.py
│   │   ├── account_value.py
│   │   └── holding.py
│   ├── services/              # Business logic layer
│   │   ├── user_service.py
│   │   ├── security_service.py
│   │   ├── yfinance_service.py
│   │   ├── price_data_service.py
│   │   ├── currency_service.py
│   │   └── exchange_service.py
│   └── main.py               # FastAPI application entry point
├── tests/                     # Test suite
│   ├── conftest.py           # Shared fixtures
│   ├── api/routes/           # API endpoint tests
│   ├── repositories/         # Repository tests
│   └── services/             # Service tests
├── alembic/                   # Database migrations
│   ├── versions/             # Migration files
│   └── env.py                # Alembic configuration
├── docs/                      # Documentation
│   ├── ARCHITECTURE.md       # System architecture
│   ├── API.md                # API reference
│   ├── DATABASE.md           # Database schema
│   ├── TESTING.md            # Testing guide
│   ├── DEPLOYMENT.md         # Deployment instructions
│   └── CONTRIBUTING.md       # Development guidelines
├── docker-compose.yml         # Service orchestration
├── Dockerfile                 # Multi-stage Docker build
├── Makefile                   # Development commands
├── pyproject.toml            # Python dependencies (uv)
├── alembic.ini               # Alembic configuration
└── README.md                 # This file
```

## Technology Stack

### Framework & Runtime
- **Python 3.13+** - Modern Python with latest features
- **FastAPI** - High-performance async web framework
- **uvicorn** - Lightning-fast ASGI server
- **Pydantic 2.x** - Data validation and settings management

### Database & ORM
- **PostgreSQL 18** - Robust relational database
- **SQLAlchemy 2.0** - Async ORM with type hints
- **asyncpg** - High-performance PostgreSQL driver
- **Alembic** - Database migration tool

### Caching & Storage
- **Redis 8** - In-memory caching and session storage
- **redis-py** - Async Redis client

### Authentication & Security
- **PyJWT** - JSON Web Token implementation
- **pwdlib** - Password hashing with Argon2
- **python-multipart** - Form data parsing

### External APIs
- **yfinance** - Yahoo Finance data integration
- **httpx** - Modern async HTTP client

### Development Tools
- **uv** - Fast Python package manager
- **Ruff** - Fast Python linter and formatter
- **mypy** - Static type checking
- **pytest** - Testing framework
- **pytest-asyncio** - Async test support

### DevOps
- **Docker** - Containerization
- **docker-compose** - Multi-container orchestration

## Database Models

The application uses 9 SQLAlchemy models representing the core domain:

### User Management
- **User** - User accounts with authentication

### Financial Securities
- **Security** - Stocks, ETFs, mutual funds (linked to yfinance)
- **SecurityPrice** - Historical OHLCV price data

### Currency Management
- **Currency** - Currency definitions (USD, EUR, etc.)
- **CurrencyRate** - Historical exchange rates

### Financial Institutions & Accounts
- **FinancialInstitution** - Banks, brokerages, etc.
- **Account** - User accounts at institutions
- **AccountValue** - Historical account valuations

### Holdings
- **Holding** - Investment positions in securities

See [docs/DATABASE.md](docs/DATABASE.md) for complete schema documentation.

## API Endpoints

The API provides 40+ endpoints organized into logical groups:

### Authentication (8 endpoints)
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/login` - User login (returns JWT tokens)
- `POST /api/v1/auth/refresh` - Refresh access token
- `POST /api/v1/auth/logout` - User logout
- `POST /api/v1/auth/forgot-password` - Initiate password reset
- `POST /api/v1/auth/reset-password` - Complete password reset
- `POST /api/v1/auth/verify-email` - Email verification
- `POST /api/v1/auth/change-password` - Change password (authenticated)

### Users (5 endpoints)
- `GET /api/v1/users/me` - Get current user
- `PATCH /api/v1/users/me` - Update current user
- `DELETE /api/v1/users/me` - Delete current user
- `GET /api/v1/users` - List users (admin)
- `GET /api/v1/users/{id}` - Get user by ID (admin)

### Securities (4 endpoints)
- `GET /api/v1/securities/search` - Search securities
- `GET /api/v1/securities/{symbol}` - Get security details
- `POST /api/v1/securities/{symbol}/sync` - Sync security data
- `GET /api/v1/securities/{symbol}/prices` - Get price history

### Currencies (6 endpoints)
- `GET /api/v1/currencies` - List currencies
- `POST /api/v1/currencies` - Create currency
- `GET /api/v1/currencies/{code}` - Get currency
- `PATCH /api/v1/currencies/{code}` - Update currency
- `DELETE /api/v1/currencies/{code}` - Delete currency
- `GET /api/v1/currencies/{code}/rates` - Get exchange rates

### Financial Institutions (5 endpoints)
- `GET /api/v1/financial-institutions` - List institutions
- `POST /api/v1/financial-institutions` - Create institution
- `GET /api/v1/financial-institutions/{id}` - Get institution
- `PATCH /api/v1/financial-institutions/{id}` - Update institution
- `DELETE /api/v1/financial-institutions/{id}` - Delete institution

### Accounts (5 endpoints)
- `GET /api/v1/accounts` - List user accounts
- `POST /api/v1/accounts` - Create account
- `GET /api/v1/accounts/{id}` - Get account
- `PATCH /api/v1/accounts/{id}` - Update account
- `DELETE /api/v1/accounts/{id}` - Delete account

### Account Values (3 endpoints)
- `GET /api/v1/accounts/{id}/values` - Get account value history
- `POST /api/v1/accounts/{id}/values` - Record account value
- `GET /api/v1/account-values/latest` - Get latest values for all accounts

### Holdings (5 endpoints)
- `GET /api/v1/holdings` - List holdings
- `POST /api/v1/holdings` - Create holding
- `GET /api/v1/holdings/{id}` - Get holding
- `PATCH /api/v1/holdings/{id}` - Update holding
- `DELETE /api/v1/holdings/{id}` - Delete holding

### Health Checks (3 endpoints)
- `GET /health` - Application health
- `GET /health/db` - Database connectivity
- `GET /health/redis` - Redis connectivity

See [docs/API.md](docs/API.md) for complete API documentation with request/response examples.

## Development

### Local Development Setup

All development is Docker-based. No local Python installation required.

```bash
# Start services
make start

# Run migrations
make migrate

# View logs
make logs-app

# Open shell in container
make shell

# Inside container, you can run:
python  # Python REPL
pytest  # Run tests
alembic # Alembic commands
```

### Creating a New Migration

```bash
# After modifying models in src/app/models/
make migrate-create MSG="add new table"

# Review the generated migration in alembic/versions/
# Then apply it
make migrate
```

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test file
docker-compose exec app pytest tests/api/routes/test_auth.py

# Run tests matching pattern
docker-compose exec app pytest -k "test_login"
```

### Code Quality

```bash
# Lint code
make lint

# Auto-fix issues
make lint-fix

# Format code
make format

# Type check
make type-check

# Run all checks
make lint && make type-check && make test
```

### Adding a New Endpoint

1. **Create/update model** in `src/app/models/`
2. **Create migration** with `make migrate-create MSG="description"`
3. **Run migration** with `make migrate`
4. **Create schema** in `src/app/schemas/`
5. **Create repository** in `src/app/repositories/` (optional, for complex queries)
6. **Create service** in `src/app/services/` (optional, for business logic)
7. **Create route** in `src/app/api/routes/`
8. **Write tests** in `tests/api/routes/`
9. **Test locally** with `make test`

## Testing

### Test Organization

```
tests/
├── conftest.py              # Shared fixtures
├── api/routes/              # API endpoint tests
│   ├── test_auth.py        # 72 auth tests
│   ├── test_users.py
│   ├── test_securities.py  # 17 securities tests
│   ├── test_currencies.py
│   └── ...
├── repositories/            # Repository layer tests
│   ├── test_user_repository.py
│   └── ...
└── services/                # Service layer tests
    ├── test_user_service.py
    └── ...
```

### Test Coverage

- **Total Tests:** 89+
- **Auth Tests:** 72 (registration, login, token refresh, password reset, etc.)
- **Securities Tests:** 17 (search, details, sync, price history)
- **Repository Tests:** Data access layer verification
- **Service Tests:** Business logic validation

### Running Tests

```bash
# All tests
make test

# With coverage
make test-cov

# Specific test file
docker-compose exec app pytest tests/api/routes/test_auth.py -v

# Specific test
docker-compose exec app pytest tests/api/routes/test_auth.py::test_register_success -v

# Tests matching pattern
docker-compose exec app pytest -k "auth" -v
```

### Test Markers

Tests are marked for categorization:

```python
@pytest.mark.unit          # Unit tests
@pytest.mark.integration   # Integration tests
```

Run specific markers:
```bash
docker-compose exec app pytest -m unit
docker-compose exec app pytest -m integration
```

See [docs/TESTING.md](docs/TESTING.md) for complete testing guide.

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Application
SECRET_KEY=your-secret-key-here-change-in-production
ENVIRONMENT=development

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/finances_db

# Redis
REDIS_URL=redis://redis:6379/0

# JWT
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Email (optional, for password reset)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=noreply@finances.com

# CORS
BACKEND_CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]
```

### Critical Configuration

**IMPORTANT:** Ensure `.env` is listed in `docker-compose.yml` under the `app` service:

```yaml
services:
  app:
    env_file:
      - .env
```

### Configuration Class

Settings are managed via Pydantic in `src/app/core/config.py`:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SECRET_KEY: str
    ENVIRONMENT: str = "development"
    DATABASE_URL: str
    REDIS_URL: str
    # ... more settings
```

## Documentation

### Available Documentation

- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Detailed system architecture, patterns, and design decisions
- **[API.md](docs/API.md)** - Complete API reference with all 40+ endpoints
- **[DATABASE.md](docs/DATABASE.md)** - Database schema, models, and relationships
- **[TESTING.md](docs/TESTING.md)** - Testing strategy, fixtures, and guidelines
- **[DEPLOYMENT.md](docs/DEPLOYMENT.md)** - Docker deployment and production setup
- **[CONTRIBUTING.md](docs/CONTRIBUTING.md)** - Development guidelines and code standards

### Interactive API Documentation

When the application is running, access interactive docs:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## Architecture Highlights

### Repository Pattern

Data access is abstracted through repositories:

```python
# Repository handles data access
class UserRepository:
    async def get_by_email(self, email: str) -> User | None:
        # Database query logic
        pass

# Service uses repository
class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def authenticate(self, email: str, password: str):
        user = await self.repo.get_by_email(email)
        # Business logic
```

### Service Layer

Business logic is isolated in services:

```python
# Service handles business logic
class SecurityService:
    async def sync_security_data(self, symbol: str):
        # 1. Fetch from yfinance
        # 2. Update database
        # 3. Cache results
        # 4. Return updated security
```

### Transaction Management

Automatic transaction management with rollback on errors:

```python
@router.post("/accounts")
async def create_account(
    account_in: AccountCreate,
    db: AsyncSession = Depends(get_db)
):
    # Transaction automatically committed on success
    # Automatically rolled back on exception
    return await account_repo.create(db, account_in)
```

### Exception Hierarchy

Custom exceptions for precise error handling:

```python
# Base exception
class AppException(Exception):
    pass

# Specific exceptions
class ResourceNotFoundError(AppException):
    pass

class UnauthorizedError(AppException):
    pass

# Usage in routes
@router.get("/users/{id}")
async def get_user(id: UUID):
    user = await user_repo.get(id)
    if not user:
        raise ResourceNotFoundError(f"User {id} not found")
    return user
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for complete architecture documentation.

## Troubleshooting

### Database Connection Issues

```bash
# Check if PostgreSQL is running
make logs-db

# Test database connection
make db-shell

# Reset database (WARNING: deletes all data)
make down
make start
make migrate
```

### Redis Connection Issues

```bash
# Check if Redis is running
make logs-redis

# Test Redis connection
docker-compose exec redis redis-cli ping
# Should return: PONG
```

### Migration Issues

```bash
# Check migration status
make migrate-history

# Rollback last migration
make migrate-downgrade

# Reset migrations (WARNING: deletes all data)
make down
make start
# Delete alembic/versions/*.py files
make migrate
```

### Container Issues

```bash
# View container status
make ps

# Rebuild containers
make rebuild

# Clean everything and start fresh
make clean
make start
make migrate
```

## Performance Considerations

### Redis Caching

Redis is actively used for:
- **yfinance HTTP requests** - Reduces API calls to Yahoo Finance
- **Security data** - Caches frequently accessed security information

### Database Optimization

- **Async operations** - All database queries are async
- **Connection pooling** - SQLAlchemy manages connection pools
- **Indexes** - Strategic indexes on frequently queried columns

### API Performance

- **Async endpoints** - Non-blocking I/O operations
- **Pagination** - Large result sets are paginated
- **Field selection** - Return only requested fields

## Security Considerations

### Authentication

- **JWT tokens** - Stateless authentication
- **Refresh tokens** - Stored securely, rotated on use
- **Token expiration** - Short-lived access tokens (30 min)

### Password Security

- **Argon2** - Modern password hashing algorithm
- **Password complexity** - Enforced via validation
- **Password reset** - Secure token-based flow

### API Security

- **CORS** - Configured allowed origins
- **Rate limiting** - Ready for implementation with Redis
- **Input validation** - Pydantic schemas validate all inputs
- **SQL injection** - Protected via SQLAlchemy ORM

## Contributing

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for development guidelines, code style, and PR process.

## License

MIT License - see LICENSE file for details.

---

**Last Updated:** November 11, 2025
