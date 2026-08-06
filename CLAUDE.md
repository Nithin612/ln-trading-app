# CLAUDE.md — project context for Claude Code

Personal intelligent stock-suggestion + algo-trading platform for Indian
markets (NSE/BSE). Solo developer, personal use first, possible future
productization. Read this fully at session start; it points to everything
else.

## Current truth (updated 2026-08-06 — v2 Phase 3, in progress)

- **v1 phases 0–11 are built and tested** (auth, stock master, screener,
  categories, EOD + FII/DII ingestion, 14-factor confluence signal engine,
  dashboard, Kite WebSocket plumbing, paper trading + circuit breaker,
  strategy lab, journal, portfolio). v1 Phase 12 (live trading) was never
  started — it is now v2 Phase 7.
- **The v2 upgrade is governed by `docs/UPGRADE_PLAN.md`** (approved
  2026-07-03): Rust compute core, tick-to-tick realtime layer, four
  trading-style engines (Intraday / Swing / F&O / Investment), UI overhaul,
  outcome tracking, then live trading. `docs/PHASES.md` tracks status (its
  top block is the at-a-glance state); each finished phase reports to
  `docs/phases/`.
- **v2 Phases 0–2 done; Phase 3 (realtime) in progress — slices 3.0–3.7 all
  done and on main.** Phase-3 exit needs two LIVE-GATED items: a clean
  quiet-box **full-session soak** (p99 tick→publish ≤ 50 ms still unproven —
  the 07-10 soak was partial) and a **clean shadow week**
  (`scripts/shadow_day.sh`, zero diffs), then `/phase-gate`.
- **Paper trading runs daily** and feeds the 30-day paper clock (the *Phase-7*
  go-live gate, not the Phase-3 exit). Exit governance is per-user
  (`users.profit_lock_enabled`): ON = the **absolute-₹ profit ladder**
  (`app/trading/profit_lock.absolute_ladder_stop` — breakeven at +₹2k, seal
  peak−₹1k above ₹3k, ATR room; knobs = `settings.profit_lock_*`), OFF = the
  fixed `trail_sl` ladder. Paper entries size **risk-first from the actual
  fill** (`paper_broker.size_for_fill`), so a chased fill shrinks qty instead
  of over-risking, and repeat entries can't stack past the budget.
- **Daily analysis loop:** `make analysis [DATE=…] [WEEK_OF=…]` (or
  `/daily-analysis`) writes `docs/analysis/<date>.md` + `LEDGER.md`. Open
  fixes and priorities live in `docs/analysis/FIX_PLAN.md`. Current evidence
  (08-03→05, 15 trades): only 1/15 reached +1R — **the binding constraint is
  entry/regime selection, not the exit logic**; expectancy calibration is
  Phase 6.
- **Architecture-review backlog (2026-08-01)** is phase-mapped at the end of
  `docs/PHASES.md` (source synthesis: `~/Downloads/ARCHITECTURE_RECOMMENDATIONS.md`).
  Its now-fixes shipped — honest gap-through-stop paper fills (P0.3), 2 bps
  slippage, paper-clock reset; the rest is Phase-6 (expectancy calibration),
  the Market Context Engine phase, or Phase-7 (exchange stops, exposure caps).
  Key framing: **live trading isn't built yet** (`place_order` is paper-only,
  no Kite order/GTT path), so every "live" recommendation is a Phase-7
  constraint.
- Backend test suite **974**, frontend **257**. `make check` green is the
  baseline state — keep it that way. Tests use an isolated Redis logical DB
  (15), flushed per test — never point them at dev db 0.

## Tech stack (locked in — ask before substituting)

| Layer | Choice |
|---|---|
| Backend | Python 3.12 · FastAPI (async) · SQLAlchemy 2 async + asyncpg · Celery + Redis |
| Compute core (v2, from Phase 1) | Rust workspace `engine/` — engine-core + PyO3 wheel `tradecore` + engine-cli |
| Database | PostgreSQL 16 + TimescaleDB (port **5433** locally) · Redis 7 (volatile-lru) |
| Frontend | React 19 · TypeScript 6 · Vite 8 · Tailwind 4 tokens · Zustand + TanStack Query |
| Charts | TradingView Lightweight Charts (candles) · Recharts (dashboards) |
| Auth | JWT — access 45 min in memory · refresh 7 d httpOnly · rotation |
| Broker | Zerodha Kite Connect (token expires ~6 AM IST daily) |
| Testing | pytest (real Postgres+Redis, no mocks) · Vitest + RTL · cargo test (Phase 1+) |
| Tooling | uv · ruff · mypy (strict) · eslint · maturin (Phase 1+) |

## Hard constraints (non-negotiable — full detail in `.claude/rules/trading-domain.md`)

1. `docs/SIGNAL_ENGINE.md` is the user's edge — **protected by hook**; spec
   changes only by explicit user instruction + backtest regression (§8).
2. Signals come from the weighted confluence engine only — never a single
   indicator. ≥70% gate.
3. No look-ahead: compute on candle N, valid from N+1; committed signals
   only from `is_complete` candles; the tick-level layer is labelled
   provisional and never enters backtests.
4. Position sizing on every signal; risk_pct is a WHOLE percent (2.0 = 2%).
   Reject (never clamp) signals whose natural SL exceeds the class cap.
5. Money = Decimal / Numeric(12,4) / i64·1e-4. Storage UTC, market logic
   IST. Trading-day arithmetic needs the NSE calendar.
6. Paper trading default; live requires opt-in + 30 profitable paper days
   (clock restarted 2026-07-03 by the sizing-bug fix). The daily-loss
   circuit breaker is never disableable.
7. Every feature ships with tests (`.claude/rules/testing.md`); every
   feature follows the vertical slice (`/vertical-slice` skill).

## The Claude Code workbench (use it)

- **Hooks** (`.claude/settings.json` + `.claude/hooks/`): auto-format on
  edit; destructive-command guard; protected files (SIGNAL_ENGINE.md,
  applied migrations, .env). If a hook blocks you, it's working — don't
  fight it, tell the user.
- **Agents** (`.claude/agents/`): `quant-verifier` (any analysis/signal/
  backtest/engine change), `bug-hunter` (pipeline/async/broker changes),
  `ui-reviewer` (frontend), `perf-auditor` (hot paths), `test-guardian`
  (coverage honesty). Run the relevant ones before calling work done.
- **Rules** (`.claude/rules/`): trading-domain · python · typescript ·
  rust · testing · ui. Load the ones matching the files you touch.
- **Skills**: `/vertical-slice` (feature workflow) · `/phase-gate` (phase
  exit ritual) · `/signal-audit` (verify a signal/profile against spec) ·
  `/perf-bench` (benchmarks + PERFORMANCE.md protocol).

## Where things live

```
backend/app/      analysis/ (confluence engine, frozen at Phase 1 parity)
                  signals/ · backtest/ · broker/ (kite, tick consumer,
                  paper broker) · trading/ (circuit breaker, trail SL)
                  services/ (incl. F&O recorders) · tasks/ (Celery)
                  api/v1/ · models/ · schemas/ · core/ · db/
backend/tests/    pytest — factories in helpers.py, fixtures in conftest.py
frontend/src/     features/<area>/ pages · components/{ui,layout,charts}
                  lib/api/ (typed client) · lib/format.ts (ALL numbers)
                  store/ (zustand) · styles/tokens.css (5 themes)
engine/           Rust workspace (arrives Phase 1)
docs/             UPGRADE_PLAN (the why) · PHASES (status) · phases/
                  (per-phase reports) · SIGNAL_ENGINE (protected spec) ·
                  UI_GUIDELINES · ARCHITECTURE · PERFORMANCE · DATABASE_SCHEMA
```

## Commands

```
make up / down          postgres+redis (pg on 5433)
make backend            uvicorn dev server      make frontend   vite dev
make worker             celery worker+beat — REQUIRED for EOD ingestion +
                        nightly signals; EOD tasks self-heal ≤21d of missed
                        sessions (stop it during soaks)
make migrate            alembic upgrade head    make create-admin
make test / lint / typecheck / check            (check = the full gate)
cd backend && uv run pytest tests/<file> -q     (targeted)
```

## Communication style

Direct and concrete; no filler. Surface trade-offs on non-trivial decisions
and ask before committing to them. When you find bugs in existing code, fix
them and say what you found. Honest yes/no answers with one-line reasoning.

## Definition of done

`make check` green · tests shipped with the change · reversible migration ·
manual smoke · CHANGELOG under Unreleased · relevant agent review clean ·
phase report updated when a phase item closes. The `/phase-gate` skill runs
this list.
