.PHONY: help start stop restart rebuild logs logs-app logs-db logs-redis status ps clean shell db-shell redis-shell migrate migrate-create migrate-history migrate-downgrade test test-cov lint format type-check health install dev-install

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)Finances API - Available Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

# Docker Commands
start: ## Start all services (PostgreSQL, Redis, API)
	@echo "$(BLUE)Starting all services...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo "API: http://localhost:8000"
	@echo "Docs: http://localhost:8000/docs"

stop: ## Stop all services
	@echo "$(YELLOW)Stopping all services...$(NC)"
	docker-compose down
	@echo "$(GREEN)✓ Services stopped$(NC)"

restart: ## Restart all services
	@echo "$(YELLOW)Restarting all services...$(NC)"
	docker-compose restart
	@echo "$(GREEN)✓ Services restarted$(NC)"

restart-app: ## Restart only the API service
	@echo "$(YELLOW)Restarting API service...$(NC)"
	docker-compose restart app
	@echo "$(GREEN)✓ API service restarted$(NC)"

rebuild: ## Rebuild and start all services
	@echo "$(BLUE)Rebuilding all services...$(NC)"
	docker-compose up -d --build
	@echo "$(GREEN)✓ Services rebuilt and started$(NC)"

# Logs
logs: ## View logs from all services
	docker-compose logs -f

logs-app: ## View logs from API service only
	docker-compose logs -f app

logs-db: ## View logs from PostgreSQL service only
	docker-compose logs -f db

logs-redis: ## View logs from Redis service only
	docker-compose logs -f redis

# Status
status: ## Show status of all services
	@docker-compose ps

ps: status ## Alias for status

# Clean
clean: ## Stop and remove all containers, networks, and volumes
	@echo "$(YELLOW)Cleaning up all containers, networks, and volumes...$(NC)"
	docker-compose down -v
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

clean-all: clean ## Stop and remove everything including images
	@echo "$(YELLOW)Removing Docker images...$(NC)"
	docker-compose down -v --rmi all
	@echo "$(GREEN)✓ Complete cleanup done$(NC)"

# Shell Access
shell: ## Open a shell in the API container
	docker-compose exec app /bin/sh

db-shell: ## Open a PostgreSQL shell
	docker-compose exec db psql -U postgres -d finances_db

redis-shell: ## Open a Redis CLI
	docker-compose exec redis redis-cli

# Database Migrations
migrate: ## Run all pending migrations
	@echo "$(BLUE)Running migrations...$(NC)"
	docker-compose exec app alembic upgrade head
	@echo "$(GREEN)✓ Migrations applied$(NC)"

migrate-create: ## Create a new migration (use: make migrate-create MSG="description")
	@if [ -z "$(MSG)" ]; then \
		echo "$(YELLOW)Usage: make migrate-create MSG=\"your migration description\"$(NC)"; \
		exit 1; \
	fi
	@echo "$(BLUE)Creating migration: $(MSG)$(NC)"
	docker-compose exec app alembic revision --autogenerate -m "$(MSG)"
	@echo "$(GREEN)✓ Migration created$(NC)"

migrate-history: ## Show migration history
	docker-compose exec app alembic history

migrate-downgrade: ## Rollback last migration
	@echo "$(YELLOW)Rolling back last migration...$(NC)"
	docker-compose exec app alembic downgrade -1
	@echo "$(GREEN)✓ Migration rolled back$(NC)"

# Testing
test: ## Run tests inside Docker
	docker-compose exec app pytest

test-cov: ## Run tests with coverage report
	docker-compose exec app pytest --cov=src --cov-report=term-missing

test-local: ## Run tests locally (requires local setup)
	uv run pytest

test-cov-local: ## Run tests with coverage locally
	uv run pytest --cov=src --cov-report=term-missing --cov-report=html

# Code Quality
lint: ## Run linter (ruff check)
	docker-compose exec app ruff check .

lint-fix: ## Run linter with auto-fix
	docker-compose exec app ruff check . --fix

format: ## Format code with ruff
	docker-compose exec app ruff format .

format-check: ## Check code formatting without changes
	docker-compose exec app ruff format . --check

type-check: ## Run type checker (mypy)
	docker-compose exec app mypy src/

lint-local: ## Run linter locally
	uv run ruff check .

format-local: ## Format code locally
	uv run ruff format .

type-check-local: ## Run type checker locally
	uv run mypy src/

# Health & Info
health: ## Check API health
	@curl -s http://localhost:8000/health | python3 -m json.tool || echo "API is not responding"

api-info: ## Show API info
	@echo "$(BLUE)API Information:$(NC)"
	@echo "  Base URL:     http://localhost:8000"
	@echo "  Health:       http://localhost:8000/health"
	@echo "  Swagger Docs: http://localhost:8000/docs"
	@echo "  ReDoc:        http://localhost:8000/redoc"
	@echo "  Users API:    http://localhost:8000/api/v1/users"

# Installation
install: ## Install dependencies locally with uv
	uv sync

dev-install: ## Install dependencies including dev tools
	uv sync --all-groups

# Database Operations
db-backup: ## Backup database to backup.sql
	@echo "$(BLUE)Creating database backup...$(NC)"
	docker-compose exec -T db pg_dump -U postgres finances_db > backup.sql
	@echo "$(GREEN)✓ Database backed up to backup.sql$(NC)"

db-restore: ## Restore database from backup.sql
	@echo "$(YELLOW)Restoring database from backup.sql...$(NC)"
	docker-compose exec -T db psql -U postgres finances_db < backup.sql
	@echo "$(GREEN)✓ Database restored$(NC)"

db-reset: ## Drop and recreate database (WARNING: destroys all data!)
	@echo "$(YELLOW)⚠️  WARNING: This will destroy all data!$(NC)"
	@read -p "Are you sure? (y/N) " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose exec db psql -U postgres -c "DROP DATABASE IF EXISTS finances_db;"; \
		docker-compose exec db psql -U postgres -c "CREATE DATABASE finances_db;"; \
		echo "$(GREEN)✓ Database reset complete$(NC)"; \
	fi

# Development Workflow
dev: start migrate ## Start services and run migrations (full dev setup)
	@echo "$(GREEN)✓ Development environment ready!$(NC)"
	@make api-info

dev-reset: clean start migrate ## Clean reset of dev environment
	@echo "$(GREEN)✓ Development environment reset complete!$(NC)"
	@make api-info
