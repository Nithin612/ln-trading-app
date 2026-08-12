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

## Decisions (settled 2026-08-12 — build started)

The three sign-offs are resolved:
1. **Framing confirmed** — Phase 6 = entry/regime selection (measure → attribute →
   select), not further exit tuning. Exit/sizing fixes already shipped (FIX_PLAN
   P0–P3).
2. **Sample-size floor = n=20** — 6.2 computes every cell but refuses to *rank* any
   cell below n=20, stated on the page (the StyleStatsHeader precedent).
3. **6.3 brought forward** — the Rust lab is sequenced right after 6.1, not last:
   6.2's statistical power lives in the 2y backtest corpus (the paper book is
   sample-starved), and only the fast lab makes corpus-scale attribution practical.

**Resulting sequence:** 6.1 (excursion data) → 6.3 (Rust-lab speed) → 6.2
(attribution at corpus scale, n≥20 floor; marginal + a few 2-D slices rather than a
fragmenting full 4-D cross-tab) → 6.4 (shadow→active promotion on forward evidence).
The external-study candidates (pair-trading / momentum / scan-catalog) enter as
**6.5** — new shadow profiles / a universe sieve measured by 6.1–6.2 and judged by
6.4, never a rewrite of this spine (see `docs/VARSITY_REVIEW_2026-08-12.md`).

**6.1 — signal-level MFE/MAE: DONE 2026-08-12.** Shared `app/services/excursion.py`
(extracted from daily_report) + `app/services/signal_excursions.compute_outcome_excursions`
+ migration `c5d6e7f8a9b0` (7 nullable columns on `signal_outcomes`) + the 5-min
expiry-sweep hook + `scripts/backfill_signal_excursions.py`. Tape-derived (1m),
direction-aware, no-look-ahead, window capped at validity, idempotent, R winsorized,
per-row commit, effective-end ordering. Pure observability; frozen engine untouched.
11 tests (all canaries mutation-verified); quant-verifier PASS, bug-hunter findings
fixed, test-guardian run by hand (spend-limited). See CHANGELOG 2026-08-12.

**6.2a — entry-quality attribution: DONE 2026-08-12.** `app/services/entry_attribution.py`
(+ `render_attribution_markdown`) + CLI `scripts/entry_attribution.py` →
`docs/analysis/attribution-<date>.md`. Per-cell expectancy by confidence · regime
(ADX) · direction · setup · time-of-day (marginals + confidence×regime 2-D),
tradeable/shadow split, n<20 no-rank floor, R winsorized ±10R, expectancy derived
from status+RR (`outcome_pnl_pct` is empty live). **First read (171 tradeable):
expectancy monotonic in regime — trending +0.20R / transitional −0.01R / choppy
−0.15R; leakiest ranked cell 70–79 × transitional −0.30R (n=63).** 7 tests,
canaries mutation-verified. See CHANGELOG 2026-08-12.

**6.3 (interactive Strategy-Lab v2) — DE-PRIORITISED.** Investigating on 2026-08-12
found the Rust backtest already exists and is parity-pinned (`run_backtest_single`,
`tests/parity/test_backtest_ext_parity.py`); only `POST /strategy/runs` still calls
the slow Python engine. So 6.3 was never the blocker for 6.2 we assumed — it's a
UI/product enhancement (switch the lab API to Rust + job-queue), not a Phase-6
critical-path item. Do it when the interactive lab matters.

**Next up: 6.2b — attribution at corpus scale.** Run the parity-clean
`run_backtest_single` over the 2y × Nifty50 corpus in a batch, feed the outcomes
through the same `entry_attribution` cells. This is where the thin live cells
(most n<20) get statistical power and the setup/regime dimensions get real teeth.
Then 6.4 (shadow→active promotion) — still time-gated by the shadow layer's forward
evidence (first fire 2026-08-10), so no rush there. 6.5 (external-study candidates:
pair-trading etc.) as new shadow profiles judged by this same attribution.
