# CLAUDE.md — project context for Claude Code

Personal intelligent stock-suggestion + algo-trading platform for Indian
markets (NSE/BSE). Solo developer, personal use first, possible future
productization. Read this fully at session start; it points to everything
else.

## Current truth

> **Status lives in ONE place: the top block of `docs/PHASES.md`.** Read it
> first, every session. This section used to duplicate it and drifted badly —
> on 2026-08-08 it still claimed 974 tests (actual: 1120), Phase 3 "in
> progress", and Phase 5 "NOT merged" weeks after it was gated. A status block
> that disagrees with reality is worse than no status block, so what remains
> here is only what is NOT derivable from PHASES.md or the code.

- **v1 phases 0–11 are built and tested.** v1 Phase 12 (live trading) was never
  started — it is now v2 Phase 7. **Live trading genuinely does not exist**:
  `place_order` is paper-only, with no Kite order/GTT path. Every "live"
  recommendation you read anywhere in these docs is a Phase-7 constraint, not a
  description of something running.
- **The v2 upgrade is governed by `docs/UPGRADE_PLAN.md`** (approved
  2026-07-03): Rust compute core, tick-to-tick realtime, four style engines,
  UI overhaul, outcome tracking, then live trading. `docs/PHASES.md` tracks
  status; each finished phase reports to `docs/phases/`.
- **Paper trading runs daily** and feeds the 30-day paper clock (the *Phase-7*
  go-live gate — **not** the Phase-3 exit; this pair is confused often). Exit
  governance is per-user (`users.profit_lock_enabled`): ON = the absolute-₹
  profit ladder (`app/trading/profit_lock.absolute_ladder_stop` — breakeven at
  +₹2k, seal peak−₹1k above ₹3k, ATR room; knobs = `settings.profit_lock_*`),
  OFF = the fixed `trail_sl` ladder. Paper entries size **risk-first from the
  actual fill** (`paper_broker.size_for_fill`), so a chased fill shrinks qty
  instead of over-risking, and repeat entries can't stack past the budget.
- **Daily analysis loop:** `make analysis [DATE=…] [WEEK_OF=…]` (or
  `/daily-analysis`) writes `docs/analysis/<date>.md` + `LEDGER.md`; open fixes
  live in `docs/analysis/FIX_PLAN.md`. **The binding constraint on profit is
  entry/regime selection, not exit logic** — only 1 of 15 trades reached +1R
  over 08-03→05, so the exit machinery was correct but had nothing to protect.
  That is what Phase 6 exists to attack (`docs/phases/phase-06-plan.md`).
  **Phase 6 (6.1+6.2) has since QUANTIFIED that leak** at corpus scale: the
  70–79 confidence band and the transitional ADX regime are net-negative, and a
  **regime gate** (skip ADX 20–25) beats a higher confidence gate — the gate
  experiment nearly doubles captured R. Verdict + numbers live in the PHASES top
  block; `docs/analysis/attribution-*.md` + `gate-experiment-*.md` are the reports.
  **Phase 6 has since run through 6.4:** the §8 walk-forward validated the regime
  gate out-of-sample, and both the regime gate and the `momentum ×1.5` retune are
  now BUILT and running SHADOW-first (measure-only — nothing on the money path
  yet). **The regime gate is now FLIPPED to active (2026-08-14, user
  decision, reversible)** — `REGIME_GATE_MODE=active` in `.env` + backend/worker
  restart; the paper order path now rejects transitional (ADX 20–25) entries,
  monitored live via the daily Flip readiness banner (revert = `shadow` + restart).
  6.5 pair-trading is BUILT shadow-first; promoting the momentum ×1.5 retune still
  waits on forward evidence. **The active build is now Phase 6.8 (Execution Realism
  & Exchange-Safety)** — 6.8.1 depth capture, 6.8.2 spread-aware slippage, and
  6.8.3 circuit-band eligibility overlay, 6.8.4 continuous open-book MTM (rolling
  MFE/MAE for carried holds + weekly per-day open-MTM series), and 6.8.5 CA-adjust
  OPEN paper positions (R-preserving split/bonus; admin-verified ratio; ex-date
  worker, idempotent+catch-up; migration `a7b8c9d0e1f2`) are DONE (through
  2026-08-18, all reviewed), next is 6.8.6 silent-feed-outage alarm
  (`docs/phases/phase-06.8-execution-realism-plan.md`). All
  6.8 slices build on the Phase-6 branch; **paper day-1 is DEFERRED until the phase
  is done + user "proceed"; merge to main only after.** Nothing auto-advances —
  the NEXT menu lives in the PHASES top block.
- **Circuit-band overlay since 6.8.3** (`app/signals/circuit_guard.py`, shadow-first,
  `circuit_gate_mode`): skips entering a name within `circuit_proximity_pct` (1.5%)
  of its ADVERSE band (long→lower, short→upper) — an un-exitable trade. Bands from a
  market-hours task's batched Kite `quote()` → Redis `circuit:{stock_id}`; the order
  path only READS the cache, fail-open. Frozen engine untouched; `off` = true no-op.
- **Paper fills are spread-aware since 6.8.2**: when the live `depth:{stock_id}`
  book is fresh, the haircut is the real half-spread + a size-vs-top-of-book
  impact term, floored at `paper_slippage_bps` so a fill is never *cheaper* than
  the old flat model and fails open to it when depth is absent. This was not
  cosmetic — **82% of live NSE books have a half-spread wider than the flat 2 bps**.
  Paper P&L before and after 2026-08-17 is therefore **not comparable**; the
  30-day clock needs a reset. Backtests are untouched (they never read depth).
- **Two report sections exist because "the engine produced nothing" was once
  indistinguishable from "the engine is broken":** §7 F&O engine health and §8
  intraday shadow layer. Both attribute a zero to a *reason*. When either shows
  a dark day, read the reason before concluding anything about a strategy.
- **The intraday profiles run in SHADOW** — real schedule, measured to outcome,
  never tradeable (the order path admits `status == 'active'` only). They are
  not activated because walk-forward returned negative risk-adjusted returns for
  all three. See `docs/PHASES.md` and `docs/phases/phase-06-plan.md` §6.4 for
  the promotion path. **Any tradeable statistic must filter `is_shadow IS
  FALSE`** — `signals.status` is a lifecycle field the sweeper overwrites, so it
  cannot carry provenance.
- **Machine quirk that has bitten three times:** a snap refresh prunes anything
  living under `~/snap/`. It has already destroyed the uv venvs and the pnpm
  store (`pnpm add` still fails with `ERR_PNPM_UNEXPECTED_STORE` — repoint
  `store-dir` outside `~/snap/` and run one full `pnpm install` before adding
  any package). Check where `claude` itself resolves to as well.
- `make check` green is the baseline state — keep it that way. Tests use an
  isolated Redis logical DB (15), flushed per test — never point them at dev
  db 0. Options math + F&O suggestions run behind the `tradecore` wheel: run
  `make engine-build` after pulling engine changes.

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

## Doc-sync ritual (run at the END of every task — not just phase gates)

A doc that disagrees with reality is worse than no doc: on 2026-08-08 a stale
status block cost real time (it claimed 974 tests and Phase 3 "in progress"
weeks after the truth had moved). So the moment a task, sub-slice, or phase
closes — or status/behaviour changes — sync the record BEFORE calling it done:

1. **`docs/PHASES.md` top block (STATE AT A GLANCE)** — the single source of
   truth. Update its content AND its `(updated <date>)` stamp.
2. **`docs/PHASES.md` "CONTINUE HERE"** — the next-session pointer; stale here
   sends the next session down a dead path.
3. **The active phase plan** (`docs/phases/phase-0X-*.md`) — status line + a
   DONE marker on the slice you closed.
4. **`CHANGELOG.md`** under Unreleased.
5. **CLAUDE.md** — the "Current truth" bullets and any "next build" pointer, if
   they moved.
6. **Memory** — the relevant fact file under the memory dir AND its one-line
   entry in `MEMORY.md`.
7. **Any other `.md` the change touched** (analysis report, README, per-phase doc).

If you changed what is true, you are not done until every place that states it
agrees. When a checkbox disagrees with the artifact or the code, trust the
artifact and fix the checkbox.

## Definition of done

`make check` green · tests shipped with the change · reversible migration ·
manual smoke · CHANGELOG under Unreleased · relevant agent review clean ·
phase report updated when a phase item closes · **the doc-sync ritual above run**
(every task, not just at a gate). The `/phase-gate` skill runs this list.
