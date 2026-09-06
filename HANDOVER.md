# HANDOVER — autonomous overnight run, 2026-09-06 → 09-07

**Branch:** `feature/pre-cycle2-hardening`
**Worktree:** `/home/nithin/code/agent/Claude/trading-platform/.claude/worktrees/pre-cycle2-hardening`

## Standing instruction (user, 2026-09-06 ~23:55 IST)

> *"start from 7.0 and proceed whatever in queue which you do not need my assistance… I am
> going to sleep now and we will meet in the morning… do not waste time"*

**Work autonomously through the queue in ID order. Commit each completed slice. DO NOT push.**

## Do NOT touch — blocked on user decisions D1–D5

| task | decision needed |
|---|---|
| #7 R1 VWAP/RVOL | **D1** frozen-engine sign-off |
| #9 R2 spread-width gate | **D2** build-or-drop (*recommend drop*) |
| #10 MCE 5b | **D3** market-cap vendor |
| #13 `compute_levels` | **D5** fix vs tourniquet |
| #15 concentration/sizing | **D4** cap enough? |

## What to read first

1. `docs/phases/pre-cycle2-queue.md` — the queue, entry check, and the five decisions
2. `docs/phases/phase-07-live-trading-plan.md` — §2 cycle-2 criteria, §3 slice split, §4 heat cap
3. `TaskList` — live status

## Ground rules that bite here

- **`make check` green is the baseline.** Last verified 2026-09-06: **1995 passed, 1 skipped,
  44 deselected, 0 failed** (`-m "not walkforward and not parity and not replay"`, 31:49).
- **Run ONE long task at a time** (pytest / agents / make check) — concurrent runs collide on
  the shared test DB's per-test truncation and surface as a phantom failure elsewhere.
- **The frozen engine is off-limits**: `app/analysis/`, `app/backtest/engine.py`, the swing/window
  canon. Bugfix-only, and any fix regenerates the Rust oracle fixtures in the same commit.
- **Doc-sync ritual runs at the END of every task**, not just at gates (CLAUDE.md).
- **Push, merge and branch creation are the user's** (W4).

## ▶ PROGRESS — overnight run 2026-09-06 → 09-07

| slice | state |
|---|---|
| **7.0** design pass (A33+A42+A35) | ✅ DONE — `docs/phases/phase-07.0-oms-design.md` |
| **7.1** RiskEngine + heat cap | ✅ DONE — `app/trading/risk_engine.py`, 33 tests |
| **A13** breaker un-suppressibility | ✅ DONE (rode with 7.1) |
| **7.2** BrokerAdapter port + Kite spike | ✅ DONE — `app/broker/adapter.py`, `paper_adapter.py`, `scripts/kite_readonly_spike.py`, 27 tests |
| **7.3** order FSM + event bus | 🔶 **PARTIAL** — migration + model + FSM + bus done (32 tests). **REMAINING: the durable event WRITER and the live-path cutover.** |
| **7.4** reconciliation | ⬜ not started |

**Full backend suite after 7.1+7.2: 2028 passed, 1 skipped, 0 failed.** (7.3's 32 tests
came after that run — re-run the suite before calling 7.3 done.)

### ▶▶ RESUME HERE — what 7.3 still needs

1. **A durable event writer**: persist `adapter.OrderEvent` → `OrderEventRow`, allocating
   `seq` per order. The `UNIQUE(client_order_id, seq)` constraint is the integrity rule;
   let it raise rather than working around it.
2. **The live-path cutover**: `place_order` writes `submitted` **before** the RiskEngine
   runs, then `denied` on refusal. That is the whole point — a decision cannot fail to be
   recorded if the row exists before the decision is made.
3. ⚠ **When the cutover lands, `orders` stops being a list of trades and becomes a list of
   INTENTS.** Two readers were already checked and are safe (`max_trades_per_day` counts
   `Position.id`; `daily_report.py:605` filters `status == "filled"`), but **every new
   `orders` reader must filter on terminal state** — the `signals.status` lesson in a new
   table.

### ⚠ Dev-environment notes for the resumed session

- **The worktree venv needed `tradecore`** (the wheel lives in the main checkout's venv).
  It was copied in; if `uv sync` prunes it again, re-copy from
  `../../../backend/.venv/lib/python3.12/site-packages/tradecore` or run `make engine-build`.
- **There is no `.env` in the worktree**, so tests need `JWT_SECRET_KEY=...` on the command
  line; conftest `setdefault`s the DB/Redis URLs itself.
- **Alembic sync URL uses psycopg 3**: `postgresql+psycopg://tpuser:...@localhost:5433/...`
  (bare `postgresql://` picks psycopg2, which is not installed).
- **`order_events` is APPLIED to the dev DB** and verified reversible (upgrade → downgrade
  → upgrade).

## State at handover

Buckets A (8 items) and B (11 items) COMPLETE and artifact-verified; Bucket C 7 of ~60.
Queue committed at `7b1a2e1`. Nothing on the money path has changed.
