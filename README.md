# Finances API

A modern FastAPI application for managing personal finances with PostgreSQL, Redis, and async support.

## Features

- **FastAPI** - Modern, fast web framework for building APIs
- **PostgreSQL** - Async database operations with SQLAlchemy 2.0
- **Redis** - Caching and session management
- **Alembic** - Database migrations
- **Docker** - Containerized deployment
- **uv** - Fast Python package management

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
│       ├── core/               # Configuration
│       ├── db/                 # Database setup
│       ├── models/             # SQLAlchemy models
│       ├── schemas/            # Pydantic schemas
│       └── services/           # Business logic
├── alembic/                    # Database migrations
├── tests/                      # Test files
├── pyproject.toml              # Dependencies
├── Dockerfile                  # Container build
└── docker-compose.yml          # Local development
```

## License

MIT
