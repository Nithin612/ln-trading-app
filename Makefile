# Trading Platform — convenience commands
# Run `make help` to see everything available.

.DEFAULT_GOAL := help
SHELL := /bin/bash

# Rust toolchain lives in ~/.cargo (rustup); make targets must find it even
# when the invoking shell hasn't sourced cargo env.
export PATH := $(HOME)/.cargo/bin:$(PATH)

# Auto-detect docker compose v2 (`docker compose`) vs v1 (`docker-compose`)
DC := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")

# Colors for help text
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m

.PHONY: help
help:  ## Show this help
	@echo ""
	@echo "$(BLUE)Trading Platform — available commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-18s$(NC) %s\n", $$1, $$2}'
	@echo ""

# ════════════════════════ Infrastructure ════════════════════════

.PHONY: up
up:  ## Start postgres + redis in background
	@$(DC) up -d postgres redis
	@echo ""
	@echo "$(GREEN)✓ Services running$(NC)"
	@echo "  Postgres: localhost:5433  (user: tpuser, db: trading_platform)"
	@echo "  Redis:    localhost:6379"
	@echo ""
	@echo "  Verify with: $(YELLOW)make db-shell$(NC) or $(YELLOW)make redis-shell$(NC)"

.PHONY: up-tools
up-tools:  ## Start everything including pgAdmin (web UI at :5050)
	@$(DC) --profile tools up -d
	@echo ""
	@echo "$(GREEN)✓ All services running$(NC)"
	@echo "  pgAdmin:  http://localhost:5050  ([email protected] / admin)"

.PHONY: down
down:  ## Stop all services (data preserved)
	@$(DC) down

.PHONY: restart
restart: down up  ## Stop and restart

.PHONY: logs
logs:  ## Tail logs from all services
	@$(DC) logs -f --tail=100

.PHONY: logs-pg
logs-pg:  ## Tail postgres logs only
	@$(DC) logs -f --tail=100 postgres

.PHONY: ps
ps:  ## Show running services
	@$(DC) ps

# ════════════════════════ Database ════════════════════════════

.PHONY: db-shell
db-shell:  ## Open psql shell inside postgres container
	@$(DC) exec postgres psql -U $${POSTGRES_USER:-tpuser} -d $${POSTGRES_DB:-trading_platform}

.PHONY: db-extensions
db-extensions:  ## Verify TimescaleDB and helper extensions are loaded
	@$(DC) exec postgres psql -U $${POSTGRES_USER:-tpuser} -d $${POSTGRES_DB:-trading_platform} -c "\dx"

.PHONY: redis-shell
redis-shell:  ## Open redis-cli inside redis container
	@$(DC) exec redis redis-cli

# ════════════════════════ Destructive ═════════════════════════

.PHONY: clean
clean:  ## Stop services AND DELETE ALL DATA (asks confirmation)
	@echo "$(YELLOW)WARNING: this deletes all postgres data and redis data.$(NC)"
	@read -p "Type 'yes' to continue: " confirm && [ "$$confirm" = "yes" ] || (echo "Aborted." && exit 1)
	@$(DC) down -v
	@echo "$(GREEN)All data wiped.$(NC)"

# ════════════════════════ Status ═══════════════════════════════

.PHONY: status
status:  ## Quick health check of all services
	@echo "$(BLUE)Service status:$(NC)"
	@$(DC) ps --format "table {{.Service}}\t{{.Status}}\t{{.Ports}}"
	@echo ""
	@echo "$(BLUE)Postgres ping:$(NC)"
	@$(DC) exec -T postgres pg_isready -U $${POSTGRES_USER:-tpuser} || echo "$(YELLOW)not ready$(NC)"
	@echo "$(BLUE)Redis ping:$(NC)"
	@$(DC) exec -T redis redis-cli ping || echo "$(YELLOW)not ready$(NC)"

# ════════════════════════ Development ═════════════════════════

.PHONY: backend
backend:  ## Run FastAPI dev server (hot-reload)
	@cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: live-worker
live-worker:  ## Run the live worker under a restart supervisor (soak ritual)
	@cd backend && while true; do \
		uv run python -m app.broker.live_worker $(WORKER_ARGS); code=$$?; \
		if [ $$code -eq 0 ]; then echo "live-worker: clean exit (session over)"; break; fi; \
		if [ $$code -eq 4 ]; then \
			echo "live-worker: NO TOKEN — run 'uv run python scripts/kite_login.py' (retrying in 60s)"; sleep 60; \
		else \
			echo "live-worker: exit $$code — restarting in 5s"; sleep 5; \
		fi; \
	done

.PHONY: frontend
frontend:  ## Run Vite dev server
	@cd frontend && pnpm dev

.PHONY: migrate
migrate:  ## Apply pending Alembic migrations
	@cd backend && uv run alembic upgrade head

.PHONY: create-admin
create-admin:  ## Interactively create the first admin user
	@cd backend && uv run python scripts/create_admin.py

# ════════════════════════ Engine (Rust) ════════════════════════

.PHONY: engine-build
engine-build:  ## Build tradecore wheel into the backend venv (maturin develop --release)
	@cd backend && uv run maturin develop --release -m ../engine/crates/engine-py/Cargo.toml

.PHONY: engine-test
engine-test:  ## Run Rust unit + golden tests
	@cd engine && cargo test --workspace

.PHONY: engine-lint
engine-lint:  ## cargo fmt --check + clippy -D warnings
	@echo "$(BLUE)▶ cargo fmt$(NC)"
	@cd engine && cargo fmt --all --check
	@echo "$(BLUE)▶ cargo clippy$(NC)"
	@cd engine && cargo clippy --workspace --all-targets -- -D warnings

.PHONY: engine-bench
engine-bench:  ## Run criterion benches (record results in docs/PERFORMANCE.md)
	@cd engine && RAYON_NUM_THREADS=6 cargo bench

.PHONY: parity
parity:  ## Python-vs-Rust parity suite (golden fixtures; arrives with P1 task 22)
	@if [ -d backend/tests/parity ]; then \
		cd backend && uv run pytest tests/parity -q; \
	else \
		echo "$(YELLOW)Parity suite not generated yet (P1: after adjudication + goldens).$(NC)"; \
	fi

# ════════════════════════ Quality ══════════════════════════════

.PHONY: test
test:  ## Run all tests (backend + frontend)
	@echo "$(BLUE)▶ Backend tests$(NC)"
	@cd backend && uv run pytest tests/ -v
	@echo ""
	@echo "$(BLUE)▶ Frontend tests$(NC)"
	@cd frontend && pnpm test

.PHONY: lint
lint:  ## Lint backend (ruff) + frontend (eslint)
	@echo "$(BLUE)▶ Ruff$(NC)"
	@cd backend && uv run ruff check app/ tests/
	@echo "$(BLUE)▶ ESLint$(NC)"
	@cd frontend && pnpm lint

.PHONY: typecheck
typecheck:  ## Type-check backend (mypy) + frontend (tsc)
	@echo "$(BLUE)▶ Mypy$(NC)"
	@cd backend && uv run mypy app/
	@echo "$(BLUE)▶ TypeScript$(NC)"
	@cd frontend && pnpm typecheck

.PHONY: replay
replay:  ## Live-engine record/replay goldens (byte-identical event streams)
	@cd backend && uv run pytest -m replay -q

.PHONY: walkforward
walkforward:  ## Walk-forward golden harness (§8 drift gate; skips cleanly without goldens/DB)
	@cd backend && uv run pytest tests/goldens -q

.PHONY: check
check: lint typecheck engine-lint engine-test test parity walkforward replay  ## Full CI gate (python + rust + frontend)
