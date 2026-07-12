# Trading Platform

Personal stock-suggestion and algo-trading platform for Indian markets
(NSE/BSE). Confluence-based signals (never single-indicator), four trading
styles (Intraday · Swing · F&O · Investment), paper-first discipline with a
non-disableable daily-loss circuit breaker, a **Rust compute core**
(`tradecore`) with proven Python parity, and a tick-to-tick realtime layer
on Zerodha Kite: dedicated live worker, record/replay determinism, tick
triggers, live alerts, and watchlists.

**Status:** v1 phases 0–11 complete. v2 upgrade in **Phase 3 (realtime)**,
nearly done — the live worker, Rust tick→candle engine, record/replay
harness, trigger/alert stream, alert UI, and watchlist-scoped fanout are
all shipped; remaining: the latency-verdict soak, provisional confidence,
outcome ticks (3.6), and the shadow week (3.7). Suites: ~745 backend ·
161 frontend · 55+ Rust tests. **Start any work session by reading the
"CONTINUE HERE" block in [`docs/PHASES.md`](docs/PHASES.md).** Rationale
lives in [`docs/UPGRADE_PLAN.md`](docs/UPGRADE_PLAN.md), per-phase records
in [`docs/phases/`](docs/phases/).

## Prerequisites

| Tool | Why |
|---|---|
| Docker + Compose | Postgres 16 + TimescaleDB (host port **5433**) and Redis 7 |
| [uv](https://docs.astral.sh/uv/) | Python 3.12 env + deps for `backend/` |
| Node 20+ with [pnpm](https://pnpm.io/) | `frontend/` (React 19 · Vite · Tailwind v4) |
| Rust stable toolchain (`rustup`) | `engine/` workspace; builds the `tradecore` wheel the backend imports |

## Quickstart (local dev)

```bash
# 0. Environment (project ROOT .env — backend AND docker-compose read it)
cp .env.example .env        # set JWT_SECRET_KEY + one postgres password
                            # (compose and the DATABASE_URLs share it)

# 1. Infrastructure (Postgres+TimescaleDB on 5433, Redis on 6379)
make up                     # make up-tools adds pgAdmin on :5050

# 2. Backend (Python 3.12 via uv)
cd backend && uv sync && cd ..
make engine-build           # Rust tradecore wheel into backend/.venv (required)
make migrate                # alembic upgrade head
make create-admin           # first admin (defaults: admin@trading.com / Admin123! — change it)
make backend                # FastAPI dev server on :8000

# 3. Frontend
cd frontend && pnpm install && cd ..
make frontend               # Vite on :5173 (proxies /api + the /ws/live WebSocket to :8000)

# 4. Background jobs (optional in dev; required for recorders/nightly signals)
cd backend && uv run celery -A app.celery_app worker -l info   # worker
cd backend && uv run celery -A app.celery_app beat -l info     # scheduler
```

Rebuild the wheel with `make engine-build` whenever `engine/` changes.

## Live market data (Zerodha Kite)

EOD ingestion and the F&O recorders run off free NSE archives — no broker
account needed. Live ticks need a Kite Connect app (see `.env.example`)
plus the **daily token ritual** (the access token dies ~6:00 AM IST; this
is a normal lifecycle event, not an error):

```bash
cd backend && uv run python scripts/kite_login.py   # paste the redirect URL back
```

The realtime layer runs as a **dedicated process**, never inside the API:

```bash
make live-worker                          # supervisor loop (the soak ritual)
LIVE_RECORD_PATH=./rec.jsonl make live-worker      # + record ticks for replay
WORKER_ARGS=--gap-fill make live-worker            # REST-backfill gaps first
```

Supervisor contract: exit 0 = session over (stops) · exit 4 = no usable
token (waits for the login ritual) · anything else restarts after 5 s.
The worker owns the candle tables; don't also start the legacy v1 consumer
(`POST /broker/kite/consumer/start`) while it runs. During a measured soak,
keep the box quiet: no pytest/cargo builds, backend API down.

## Tests & the gate

```bash
make check         # the full CI gate — green is the baseline state
```

`make check` = ruff + eslint → mypy + tsc → cargo fmt/clippy → cargo test
→ backend pytest (real Postgres+Redis test DB, no mocks) → frontend vitest
→ Python↔Rust parity goldens → walk-forward §8 drift gate → record/replay
byte-identity. Targeted runs:

```bash
cd backend && uv run pytest tests/<file> -q      # one file
make walkforward                                 # §8 golden harness (~7 min)
make replay                                      # replay determinism (~5 s)
make engine-test                                 # Rust only
RAYON_NUM_THREADS=6 make engine-bench            # criterion → docs/PERFORMANCE.md
```

Two hard-won rules: **never run two pytest sessions at once** (they share
the test DB and truncate it per test), and on a loaded desktop run the
backend suite as three sequential legs instead of one
(`pytest -m "not parity and not walkforward"` · `-m parity` ·
`-m walkforward`) — the single-process run has been OOM-killed under
desktop load.

## Layout

```
backend/app/      analysis/ (confluence engine — FROZEN, parity oracle)
                  signals/ · backtest/ · broker/ (kite REST/WS, live_worker,
                  replay, live_levels) · trading/ (circuit breaker, trail SL)
                  services/ · tasks/ (Celery) · api/v1/ · models/ · schemas/
backend/tests/    pytest — factories in helpers.py; goldens under tests/goldens
frontend/src/     features/<area>/ · components/{ui,layout,charts} ·
                  lib/api/ (typed client) · lib/format.ts (ALL numbers) ·
                  styles/tokens.css (5 themes; Tailwind v4 `(--var)` classes)
engine/           Rust workspace: engine-core (pure logic) · engine-py
                  (PyO3 wheel `tradecore`) · engine-cli
docs/             UPGRADE_PLAN (the why) · PHASES (status + CONTINUE HERE) ·
                  phases/ (per-phase ledgers) · SIGNAL_ENGINE (protected
                  strategy spec) · UI_GUIDELINES · ARCHITECTURE ·
                  PERFORMANCE · DATABASE_SCHEMA
docker/           postgres init scripts (TimescaleDB extensions)
```

Definition of done, phase workflow, and the review agents: see
[`CLAUDE.md`](CLAUDE.md) and `.claude/` (this repo is built with Claude
Code; hooks auto-format, guard destructive commands, and protect
`docs/SIGNAL_ENGINE.md` — the strategy spec changes only by explicit
owner instruction + backtest regression).

## Safety rails that are not up for debate

- Paper trading is the default; live mode needs explicit opt-in **plus** 30
  profitable paper-trading days, enforced in code.
- The daily-loss circuit breaker cannot be disabled in live mode.
- Position sizing (`floor(capital × risk% / |entry − SL|)`) attaches to
  every signal; signals whose natural stop exceeds the classification cap
  are rejected, not tightened.
- No look-ahead anywhere: signals compute on candle N, act from N+1; the
  tick-level "forming" layer is labelled provisional end-to-end and never
  enters backtests or P&L.

⚠️ This platform assists trading decisions; it does not guarantee profits.
Its job is disciplined risk, measured signal quality, and honest tracking.
