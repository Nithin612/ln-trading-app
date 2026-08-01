---
name: phase-gate
description: Run the full quality gate for a phase or feature — all checks, suites, regression comparisons — and produce the go/no-go summary plus doc updates. Load when closing out a phase, or before declaring any substantial work "done".
---

# Phase gate

The exit ritual. A phase is closed only when every gate below passes and the
results are written down where future-you will find them.

> **Phases 4–7 — architecture cross-check:** before starting and again at this
> gate, consult `docs/NAUTILUS_TRADER_ANALYSIS.md` for the adopt/adapt/avoid
> items relevant to the phase (§6 gap-analysis · §9 India adaptations · §8
> don't-copy). **Phase 7 opens with slice 1 = the RiskEngine single-gate
> consolidation** (test-first, equivalence-pinned) — before any live-order path.

## Gates (run in order, stop on first hard failure)

1. **Static:** `cd backend && uv run ruff check app/ tests/ && uv run mypy app/`
   and `cd frontend && npm run lint && npm run typecheck`.
   From Phase 1 add: `cd engine && cargo fmt --check && cargo clippy --all-targets -- -D warnings`.
2. **Suites:** `cd backend && uv run pytest tests/ -q` ·
   `cd frontend && npm test`. From Phase 1 add `cargo test` + `make parity`.
   From Phase 3 add `make replay`. Record exact pass counts.
3. **Regression (trading logic changed?):** run the standing backtest
   (`make backtest STOCKS=NIFTY50 PERIOD=2Y` or the strategy-lab preset) and
   diff win rate / Sharpe / max drawdown against the recorded goldens in
   docs/phases/. **>5% movement on any metric = STOP; user approval
   required before merge** (SIGNAL_ENGINE.md §8).
4. **Manual smoke:** the phase's demo scenario end-to-end in the browser
   (`make backend` + `make frontend`). List what you clicked and saw.
5. **Reviews:** quant-verifier on analysis/signal diffs, bug-hunter on
   pipeline diffs, ui-reviewer on frontend diffs, test-guardian if coverage
   is in doubt. CRITICAL/HIGH findings block the gate.

## Then write it down

- **CHANGELOG.md** — under Unreleased, grouped Backend/Frontend/Tests, with
  the new totals.
- **docs/phases/phase-NN-<slug>.md** — goal → why → what was built (with
  file paths) → results/metrics (test counts, bench numbers, backtest
  metrics) → decisions taken → what's deferred where.
- **docs/PHASES.md** — flip the status cell.
- **docs/PERFORMANCE.md** — new bench/latency numbers if this phase touched
  a hot path.

## Output

Report a single verdict block to the user:

```
PHASE GATE: PASS | FAIL
  static:      ...
  tests:       backend N passed · frontend M passed · (engine ...)
  regression:  win% Δx.x · sharpe Δx.xx · maxDD Δx.x  (vs golden <file>)
  smoke:       <one line per scenario>
  reviews:     <agent: verdict>
  docs:        CHANGELOG ✓ · phase report ✓ · PHASES.md ✓
Blockers (if FAIL): ...
```
