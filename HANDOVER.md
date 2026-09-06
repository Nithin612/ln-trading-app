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
| **7.3** order FSM + event bus + cutover | ✅ **DONE** — migration, model, FSM, bus, event store, and the order path cut over. 42 tests. |
| **7.4** kill switch + recovery + reconciliation | ✅ **DONE** — 19 tests |
| **CAS Stage 2** (#12) | ✅ **DONE** — ρ −0.272, CI [−0.478, −0.088] excludes zero. Sign robust, magnitude not. NOT promotable at 7 days |
| **A27** config dry-run (#18) | ✅ **DONE** — `make config-check`, 21 tests |

**Full backend suite after 7.1+7.2: 2028 passed, 1 skipped, 0 failed.** (7.3's 32 tests
came after that run — re-run the suite before calling 7.3 done.)

### ✅ Full suite GREEN through ALL of Phase 7

**2137 passed, 1 skipped, 44 deselected, 0 failed** (34:49). Exactly
**1995 baseline + 33 (7.1) + 27 (7.2) + 42 (7.3) + 19 (7.4) + 21 (A27)** — every new test
accounted for, no regression anywhere. `ruff` + `mypy app/ scripts/` clean.
Log: `/home/nithin/.claude/jobs/74d5bb2c/tmp/pytest_a27.log`.

⚠ **One real failure was caught on the way and is worth remembering:** A13 asserted
`PRE_TRADE_RULES[0] == RULE_BREAKER`, and 7.4 legitimately broke it by putting the kill
switch first. Index 0 was a stricter proxy than the invariant A13 actually defends — its
own message already said the right thing ("before every PER-SIGNAL rule"). Now pinned as
two assertions so a future reordering cannot hoist a per-signal rule above the account
rails.

### ▶▶ RESUME HERE — next unblocked work, ranked

**Phase 7.1–7.4 is COMPLETE.** CAS-2 and A27 are done. Remaining unblocked:

| # | task | note |
|---|---|---|
| **#19** | A3 broker-token status | small; protects cycle-2 data quality (token dies ~06:00 IST daily, and a silent lapse makes fills quietly cheaper than reality) |
| **#14** | Minervini trend template | an explicit, recorded DROP is a legitimate resolution |
| **#8** | momentum ×1.5 backtest path | forward accrual is stalled at 3 minted / 0 resolved |
| **#11** | MCE 6 news veto | Google News RSS + FinBERT, shadow-first |
| **#20** | pre-COVID backtest sourcing spike | does NOT block cycle 2 |
| **#6** | F1 market_cap spike | feeds decision D3 |

⛔ **Blocked on the user: #7 #9 #10 #13 #15** (D1–D5), plus **D6** (Kite has no
client-order-id field — reconciliation's matching key).

⚠ **A limit from 7.2 that still stands:** the paper gateway's `fetch_open_orders()` is
structurally empty, so **paper cannot exercise reconciliation's main path**. 7.4 already
reports this as a caveat on every run — never read a green paper reconciliation as evidence.

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
