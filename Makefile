.PHONY: help up down logs test lint build clean shell-api shell-db

# ─────────────────────────────────────────────────────────────────────────────
# Production Data Reliability Platform — Developer Makefile
# ─────────────────────────────────────────────────────────────────────────────

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Stack ─────────────────────────────────────────────────────────────────────
up: ## Start the full local stack
	docker compose up -d --build
	@echo "✅ Stack is up"
	@echo "   API:        http://localhost:8000/docs"
	@echo "   Prometheus: http://localhost:9090"
	@echo "   Grafana:    http://localhost:3000  (admin / pdrp_admin)"
	@echo "   Marquez:    http://localhost:5000"

down: ## Stop and remove containers
	docker compose down

restart: ## Restart a service: make restart svc=api
	docker compose restart $(svc)

logs: ## Tail logs for all services
	docker compose logs -f

logs-api: ## Tail API logs only
	docker compose logs -f api

# ── Testing ───────────────────────────────────────────────────────────────────
test: ## Run all tests
	cd services/api && pytest tests/ -v --tb=short

test-cov: ## Run tests with coverage
	cd services/api && pytest tests/ -v --cov=app --cov-report=term-missing

# ── Linting ───────────────────────────────────────────────────────────────────
lint: ## Run ruff linter
	ruff check services/api/app services/api/tests

lint-fix: ## Auto-fix lint errors
	ruff check --fix services/api/app services/api/tests

format: ## Format code with ruff
	ruff format services/api/app services/api/tests

# ── Database ──────────────────────────────────────────────────────────────────
db-shell: ## Open psql shell
	docker compose exec db psql -U pdrp -d pdrp

db-migrate: ## Run Alembic migrations
	cd services/api && alembic upgrade head

db-rollback: ## Rollback last Alembic migration
	cd services/api && alembic downgrade -1

# ── Dev Shells ────────────────────────────────────────────────────────────────
shell-api: ## Open shell in API container
	docker compose exec api /bin/bash

# ── Build ─────────────────────────────────────────────────────────────────────
build: ## Build Docker images
	docker compose build

# ── Clean ─────────────────────────────────────────────────────────────────────
clean: ## Remove containers and volumes (⚠️ deletes DB data)
	docker compose down -v --remove-orphans
	@echo "⚠️  All volumes removed — DB data is gone"
