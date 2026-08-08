# Phase 6 — outcome tracking + strategy lab v2 · PLAN FOR REVIEW

**Status: NOT STARTED. This document is a proposal, not a commitment.**
Written 2026-08-08 while the user was away, deliberately as a plan rather than
code: Phase 6 touches expectancy calibration and the FROZEN analysis engine,
which are the user's calls, not an agent's.

---

## The one-paragraph case

Your own evidence says the binding constraint is **entry/regime selection, not
exits**: over 08-03→05, 15 trades, only **1 reached +1R**. The profit-lock work
proved the exit machinery is correct when it arms — it just had almost nothing
to protect. So Phase 6 is not "tune the ladder further"; it is "find out which
setups actually have an edge, and stop taking the ones that don't." Everything
below serves that question.

## What Phase 6 must NOT become

- **Not a re-litigation of the frozen engine.** `app/analysis/`,
  `app/backtest/engine.py` and the swing/window canon are frozen bugfix-only
  (trading-domain rules). Phase 6 measures and selects; it does not re-derive
  factor math. Any fix there regenerates the Rust oracle fixtures in the same
  commit.
- **Not tuning on the live book.** The paper record gates Phase 7. Calibrating
  against the same trades you are counting toward go-live contaminates both.
- **Not a dashboard project.** A prettier hit-rate page does not answer the
  entry question. Measurement that changes a decision, or it does not ship.

## Proposed slices

### 6.1 — Signal-level MFE/MAE (prerequisite, low risk)

Today `signal_outcomes` records first-touch ordering (`tp_first` / `sl_first`),
which answers "did it win" but not "how much was on the table" or "how close did
it come to stopping first". Without excursion data you cannot tell a bad *setup*
from a bad *stop placement*, and those need opposite fixes.

- Extend the outcome recorder to track max favourable / adverse excursion per
  signal, from the same tick stream that already drives the touch levels.
- Backfill from the 1m tape for the existing cohort (the daily report already
  loads those tapes — `tape_excursion` exists).
- Deliverable: every signal carries MFE/MAE in R multiples.
- **Known open item this closes:** "signal-level MFE/MAE missing (Phase 6)".

### 6.2 — Entry-quality attribution

The actual question. For each closed signal, decompose the outcome into:
regime at entry (ADX/VIX bucket), setup type, confidence bucket, entry-vs-fill
slippage, and time-of-day. Report which cells have positive expectancy and
which are systematically negative.

- Read-only over existing data. No engine change.
- Deliverable: a per-cell expectancy table with sample sizes, and — critically —
  **an explicit refusal to report cells below a sample threshold** (the
  StyleStatsHeader precedent: never dress up n<20).
- This is what turns "1/15 reached +1R" into "these three cells are the leak".

### 6.3 — Strategy Lab v2 on the Rust engine

Currently `POST /strategy/runs` executes the frozen **Python** `BacktestEngine`
inside the HTTP request via `to_thread`. The Rust core is ~6,180× faster and
already parity-pinned. Moving the lab onto it turns a coffee-break backtest into
an interactive one, which is what makes 6.4 practical at all.

- Keep the Python engine as the parity oracle; do not delete it.
- Add job-queue offload so a long sweep does not hold a request open.

### 6.4 — Weight tuning + promotion workflow

Only after 6.1–6.3. Rayon-parallel parameter sweeps, walk-forward validated,
with a **promotion gate**: a profile moves `shadow → active` only on forward
evidence, never on in-sample fit. The shadow layer built on 2026-08-08 is
already the mechanism — see `intraday-shadow-layer` in memory.

- This is where the flagged profiles (dc1, dc2, multibagger, and the intraday
  trio) get a real verdict instead of a stale one.

## Sequencing note

6.1 and 6.2 are read-only and independently useful — they can ship without
touching the engine or the lab. 6.3 is infrastructure. 6.4 is the payoff and
should not start until the first three are done, because tuning against
un-attributed outcomes is how you overfit.

## What I need from you before starting

1. **Confirm the framing** — that Phase 6's job is entry/regime selection, not
   further exit tuning. If you disagree, the slice order changes completely.
2. **Sample-size policy.** 6.2 will produce cells with n=3. My default is to
   compute but refuse to *rank* below n=20, and say so on the page. Tell me if
   you want a different floor.
3. **Whether 6.3 is in scope now** or deferred — it is the largest piece and the
   only one that touches the lab's execution path.

Nothing here is started. The shadow layer landing on 2026-08-10 will produce the
first forward evidence 6.4 would eventually consume, so there is no rush to
begin 6.4 specifically.
