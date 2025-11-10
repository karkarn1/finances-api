# Finances API

A modern FastAPI application for managing personal finances with PostgreSQL, Redis, and async support.

## Features

### Core Infrastructure
- **FastAPI** - Modern, fast web framework for building APIs
- **PostgreSQL** - Async database operations with SQLAlchemy 2.0
- **Redis** - Caching and session management (ready for use)
- **Alembic** - Database migrations
- **Docker** - Containerized deployment
- **uv** - Fast Python package management

### Authentication & Security
- **JWT Authentication** - Stateless token-based authentication
- **Argon2 Password Hashing** - Modern, secure password storage via pwdlib
- **Password Reset** - Secure token-based password reset flow
- **User Management** - Complete CRUD operations for users
- **Access & Refresh Tokens** - Dual token system for enhanced security

### Securities Tracking
- **yfinance Integration** - Real-time and historical financial data from Yahoo Finance
- **Security Search** - Search for stocks, ETFs, and other securities
- **Price History** - Store and retrieve historical price data (OHLCV)
- **Data Sync** - On-demand synchronization of security data
- **Multiple Intervals** - Support for 1m, 1h, 1d, 1wk intervals

## Getting Started

### Prerequisites

- Docker and Docker Compose

### Quick Start

Start all services (PostgreSQL, Redis, and the API):

```bash
# Using Make (recommended)
make start

# Or using docker-compose directly
docker-compose up -d
```

The API will be available at:
- **Application**: http://localhost:8000
- **API Documentation (Swagger)**: http://localhost:8000/docs
- **Alternative Documentation (ReDoc)**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

### Using Make Commands

This project includes a Makefile for common operations. View all available commands:

```bash
make help
```

Common commands:
```bash
make start          # Start all services
make stop           # Stop all services
make restart        # Restart all services
make logs           # View logs (all services)
make logs-app       # View API logs only
make migrate        # Run database migrations
make test           # Run tests
make shell          # Open shell in API container
make health         # Check API health
```

See the full list of commands by running `make help` or check the [Makefile](./Makefile).

### Database Migrations

```bash
# Apply migrations
make migrate

# Create a new migration
make migrate-create MSG="add user table"

# View migration history
make migrate-history

# Rollback last migration
make migrate-downgrade
```

Or using docker-compose directly:
```bash
docker-compose exec app alembic upgrade head
docker-compose exec app alembic revision --autogenerate -m "description"
```

### Development

View logs:
```bash
make logs           # All services
make logs-app       # API only
make logs-db        # Database only
make logs-redis     # Redis only
```

Access shells:
```bash
make shell          # API container shell
make db-shell       # PostgreSQL shell
make redis-shell    # Redis CLI
```

Restart services:
```bash
make restart        # All services
make restart-app    # API only (faster for code changes)
```

Stop all services:
```bash
make stop
```

### Local Development (Without Docker)

If you prefer to run the API locally:

1. Install dependencies:
```bash
uv sync
```

2. Start Docker services (PostgreSQL + Redis only):
```bash
docker-compose up -d db redis
```

3. Run migrations:
```bash
alembic upgrade head
```

4. Start the development server:
```bash
uv run python -m uvicorn src.main:app --reload
```

## Project Structure

```
finances-api/
├── src/
│   ├── main.py                 # FastAPI app entry
│   └── app/
│       ├── api/                # API routes
│       │   └── routes/         # Route handlers
│       │       ├── auth.py     # Authentication endpoints
│       │       ├── users.py    # User management
│       │       ├── securities.py # Securities tracking
│       │       └── health.py   # Health checks
│       ├── core/               # Configuration
│       │   ├── config.py       # Settings
│       │   ├── security.py     # Auth utilities
│       │   └── deps.py         # Dependencies
│       ├── db/                 # Database setup
│       ├── models/             # SQLAlchemy models
│       │   ├── user.py         # User model
│       │   ├── security.py     # Security model
│       │   └── security_price.py # Price data model
│       ├── schemas/            # Pydantic schemas
│       └── services/           # Business logic
│           └── yfinance_service.py # Yahoo Finance integration
├── alembic/                    # Database migrations
├── tests/                      # Test files
│   ├── api/                    # API tests
│   └── utils/                  # Utility tests
├── pyproject.toml              # Dependencies
├── Dockerfile                  # Container build
└── docker-compose.yml          # Local development
```

## API Endpoints

### Health Check
- `GET /health` - API health status

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login (access token only)
- `POST /api/v1/auth/login/tokens` - Login (access + refresh tokens)
- `GET /api/v1/auth/me` - Get current user profile
- `POST /api/v1/auth/test-token` - Validate access token
- `POST /api/v1/auth/forgot-password` - Request password reset
- `POST /api/v1/auth/reset-password` - Reset password with token

### Users
- `GET /api/v1/users/me` - Get current user (protected)
- `PATCH /api/v1/users/me` - Update current user (protected)

### Securities
- `GET /api/v1/securities/search?q={query}` - Search for securities
- `GET /api/v1/securities/{symbol}` - Get security details
- `POST /api/v1/securities/{symbol}/sync` - Sync security data from Yahoo Finance (protected)
- `GET /api/v1/securities/{symbol}/prices` - Get historical prices with filters (protected)

**Interactive API Documentation:**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Testing

Run the full test suite:
```bash
make test
```

Run with coverage:
```bash
make test-cov
```

**Test Coverage:** 89 tests passing
- Unit tests: Security utilities, password hashing
- Integration tests: API endpoints, database operations
- Authentication tests: Registration, login, password reset
- Securities tests: Search, sync, price data retrieval

Test structure:
```bash
tests/
├── conftest.py              # Shared fixtures
├── api/
│   └── routes/
│       ├── test_login.py    # Auth tests (72 total)
│       ├── test_users.py    # User tests
│       └── test_securities.py # Securities tests (17 total)
└── utils/
    └── test_security.py     # Security utils tests
```

## Technology Stack

**Backend Framework:**
- FastAPI - Async web framework
- Python 3.13+ - Modern Python features
- uvicorn - ASGI server

**Database:**
- PostgreSQL 18 - Primary database
- SQLAlchemy 2.0 - Async ORM
- Alembic - Database migrations

**Authentication:**
- PyJWT - JWT token generation
- pwdlib - Argon2 password hashing

**Financial Data:**
- yfinance - Yahoo Finance API client
- pandas - Data manipulation

**Development Tools:**
- uv - Fast package manager
- Ruff - Linter and formatter
- mypy - Static type checker
- pytest - Testing framework
- Docker - Containerization

## License

MIT
