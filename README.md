# Trading Platform

Personal stock-suggestion and algo-trading platform for Indian markets
(NSE/BSE). Confluence-based signals (never single-indicator), four trading
styles (Intraday · Swing · F&O · Investment), paper-first discipline with a
non-disableable daily-loss circuit breaker, and — in progress — a Rust
compute core with a tick-to-tick realtime layer on Zerodha Kite.

**Status:** v1 phases 0–11 complete (439 backend + 131 frontend tests).
v2 upgrade underway — Phase 0 (workbench + triage + F&O recorders) done.
Roadmap: [`docs/PHASES.md`](docs/PHASES.md) · rationale:
[`docs/UPGRADE_PLAN.md`](docs/UPGRADE_PLAN.md) · per-phase results:
[`docs/phases/`](docs/phases/).

## Quickstart (local dev)

```bash
# 1. Infrastructure (Postgres+TimescaleDB on 5433, Redis on 6379)
make up

# 2. Backend (Python 3.12 via uv)
cd backend && uv sync && cd ..
make migrate                # alembic upgrade head
make create-admin           # first admin user (interactive)
make backend                # FastAPI on :8000

# 3. Frontend (React 19 + Vite 8)
cd frontend && npm install && cd ..
make frontend               # Vite dev server on :5173

# 4. Background jobs (optional in dev; required for recorders/signals)
cd backend && uv run celery -A app.celery_app worker -l info   # worker
cd backend && uv run celery -A app.celery_app beat -l info     # scheduler
```

Environment: copy `.env.example` → `.env` and fill it in. Never commit
`.env`. Zerodha credentials are optional until v2 Phase 3 (live data);
the F&O EOD recorders run off free NSE archives without them.

## The full gate

```bash
make check    # pytest + ruff + mypy + vitest + eslint + tsc
make test     # both test suites only
```

Definition of done, phase workflow, and review agents: see
[`CLAUDE.md`](CLAUDE.md) and `.claude/` (this repo is built with Claude
Code; hooks auto-format, guard destructive commands, and protect
`docs/SIGNAL_ENGINE.md` — the strategy spec).

## Layout

```
backend/    FastAPI app, analysis engine, Celery tasks, pytest suite
frontend/   React SPA (token-driven 5-theme UI)
engine/     Rust compute core (arrives v2 Phase 1)
docs/       specs & plans (SIGNAL_ENGINE is protected), phase reports
docker/     postgres init scripts
```

## Safety rails that are not up for debate

- Paper trading is the default; live mode needs explicit opt-in **plus** 30
  profitable paper-trading days, enforced in code.
- The daily-loss circuit breaker cannot be disabled in live mode.
- Position sizing (`floor(capital × risk% / |entry − SL|)`) attaches to
  every signal; signals whose natural stop exceeds the classification cap
  are rejected, not tightened.
- No look-ahead anywhere: signals compute on candle N, act from N+1.

⚠️ This platform assists trading decisions; it does not guarantee profits.
Its job is disciplined risk, measured signal quality, and honest tracking.
