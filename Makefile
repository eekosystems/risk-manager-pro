.DEFAULT_GOAL := help
.PHONY: help install dev test lint format type-check migrate seed clean docker-up docker-down docker-reset

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------

install: install-backend install-frontend ## Install all dependencies

install-backend:
	cd backend && pip install -e ".[dev]"

install-frontend:
	cd frontend && npm ci

# ---------------------------------------------------------------------------
# Development
# ---------------------------------------------------------------------------

dev: ## Run backend + frontend dev servers in parallel
	@echo "Starting backend and frontend..."
	$(MAKE) dev-backend & $(MAKE) dev-frontend & wait

dev-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

test: ## Run all tests
	cd backend && python -m pytest -v --tb=short

test-cov: ## Run tests with coverage report
	cd backend && python -m pytest -v --cov=app --cov-report=term-missing --tb=short

# ---------------------------------------------------------------------------
# Linting & Formatting
# ---------------------------------------------------------------------------

lint: ## Run linters (backend + frontend)
	cd backend && ruff check .
	cd frontend && npm run lint

format: ## Auto-format code (backend)
	cd backend && ruff format .
	cd backend && ruff check --fix .

type-check: ## Run type checkers (backend + frontend)
	cd backend && mypy app
	cd frontend && npm run type-check

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

migrate: ## Run Alembic migrations
	cd backend && alembic upgrade head

migrate-new: ## Create a new migration (usage: make migrate-new msg="add users table")
	cd backend && alembic revision --autogenerate -m "$(msg)"

seed: ## Seed database with dev data
	cd backend && python -m scripts.seed

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

docker-up: ## Start PostgreSQL + Azurite containers
	docker compose up -d

docker-down: ## Stop containers
	docker compose down

docker-reset: ## Stop containers and remove volumes
	docker compose down -v

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

clean: ## Remove build artifacts and caches
	find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find backend -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find backend -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find backend -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/.coverage backend/htmlcov
	rm -rf frontend/node_modules/.cache frontend/dist
