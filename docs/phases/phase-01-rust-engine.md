# Phase 1 — Rust engine core, adjudication, parity, benchmarks

**Completed:** 2026-07-04 · **Plan:** `docs/UPGRADE_PLAN.md` (Phase 1)
**Commits:** `3c87028` (scaffold) → `e29cc75` (parity+bench), 11 commits.

## Goal

Move all signal math to a compiled core with *proven* equivalence to the
Python engine, adjudicate five places where code and spec disagreed, and
measure the speedup that makes the strategy lab (Phase 6) and tick-level
realtime (Phase 3) feasible.

## Why (what future-you needs to remember)

- **The data had to be backfilled first**: `ohlcv_1d` was EMPTY — v1
  Phase 4's "5 years backfilled" described code, not data. 3 years of NSE
  bhavcopy (1.29M candles, 2,330 stocks, 773 sessions) now loaded, and
  `scripts/backfill_eod.py` exists for re-runs.
- **pandas-ta 0.4.71b0 has undocumented seeding semantics** that were
  decoded numerically and from source: EMA seeds with SMA; RSI seeds
  Wilder with the FIRST diff (output from bar 1); ADX's internal ATR uses
  `prenan=True` (length−1 seed samples — differs from standalone ATR!)
  and seeds the ADX smoothing with the first DX. All documented in the
  Rust modules and locked by the committed reference fixture.
- **The adjudication mattered more than expected**: honest fills (item E)
  revealed the old backtest's +1.8% totPnL was fill-model flattery — the
  truthful number on 2023–26 daily data is ≈ −108%. This was accepted
  knowingly: Phases 2/6 optimize against reality now.

## Adjudicated decisions (user, 2026-07-04, evidence-based)

A) volume direction-match · B) RSI ±0.4 bands removed · C) pivot swing-SL
(N=5) shared by live+backtest with degenerate-SL rejection · D) last-300
window canon everywhere · E) honest fills (gap exits at open, fill candle
checked). Full evidence table: `docs/ARCHITECTURE.md` §Adjudicated canon.
Applied to BOTH engines in one commit (`ea4b06d`) with 8 Python regression
tests + regenerated Rust oracles.

## What was built

1. **engine/ workspace** (rustc 1.96.1 pinned): engine-core (pure logic,
   panics denied by lint), engine-py → `tradecore` wheel (PyO3 abi3-py312,
   GIL released per batch), engine-cli (bench/replay).
2. **engine-core modules**: indicators (EMA/RSI/SMA/MACD/ATR/ADX/BBands —
   incremental `*State` structs with batch fns built on top so live and
   backtest can't diverge), pivots (THE swing implementation, == ties),
   patterns (10 detectors), structure (Dow/S&R clustering/fib), factors
   (all 14), confluence (scorer with zero-sentinel, int-truncation,
   ADX-regime gate, volume direction-match), risk (i64·1e-4 money with
   Decimal-parity string conversion, half-even), backtest (adjudicated
   canon + Rayon `run_universe`).
3. **Four committed oracle fixtures** (generated from the frozen Python on
   real DB data): pandas-ta reference, 49-window patterns/structure,
   84-window confluence pipeline, 6-stock/125-trade backtest.
4. **Cross-language parity suite** (`make parity`, tests/parity/): frozen
   Python vs tradecore on the dev-DB corpus — exact factor scores,
   confidence integers, decisions, trade lists; ENGINE_IMPL dispatch tests.
5. **ENGINE_IMPL flag** (`settings.engine_impl`, default python):
   signal_service routes scoring through tradecore when "rust" — the
   Phase-3 shadow-week switch.
6. **Python engine frozen** (bugfix-only; rule in trading-domain.md);
   sunset after the Phase-3 shadow week.

## Results / metrics

| Gate | Result |
|---|---|
| Rust tests | 29 (unit+property+4 oracle fixtures) — parity exact on first run for patterns/structure, confluence, and backtest |
| Cross-language parity | 96 confluence windows + 125-trade lists: EXACT |
| Backend suite | 447 passed (post-adjudication) · +8 canon regression tests |
| **2y × 49-stock backtest** | pandas **883.8 s** → Rust **0.143 s** (**~6,180×**, RAYON=6) |
| 200-combo weight grid | ≈50.5 h extrapolated → **≈29 s** |
| Budgets | "2y×50 < 5 s" beaten 35× |

Baseline trading metrics (honest fills, untuned): 807 trades, negative
expectancy — the truthful starting line for Phase 2/6 tuning.

## Decisions taken

- Money scale i64·1e-4 with `money_from_str` replicating Python
  `Decimal(str(x))` (shortest-repr parse + half-even) — cap checks by
  exact cross-multiplication.
- Factor groups precomputed (tags-beat-names resolution: DOW_TREND→
  structure, BBANDS→volume, MULTIBAGGER→institutional).
- Explanation strings stay Python-side; the parity contract is scores +
  codes + decisions.
- FII/DII flows enter backtests as zeros (no historical flow data) —
  identical in both engines; live flows wire in at Phase 2.

## Deferred / carried forward

- Rust-side metrics (Sharpe/Sortino/DD) — trades are the parity contract;
  metric computation stays Python-side until the Phase-6 lab needs it hot.
- Criterion micro-benches — headline wall-clock recorded; per-indicator
  microbenches when tuning hot loops (Phase 3).
- Python factor-code deletion + ENGINE_IMPL removal — after the Phase-3
  shadow week (one live week, zero decision diffs required).
- Backtest weight-multiplier parity test (Rust groups implemented and
  unit-consistent; cross-language grid comparison lands with the Phase-6
  lab rewrite).

## How to see it working

```bash
make engine-test && make parity          # all oracles + cross-language
cd engine && PATH=$HOME/.cargo/bin:$PATH cargo build --release -p engine-cli
RAYON_NUM_THREADS=6 ./target/release/engine-cli backtest <corpus.json>
# ENGINE_IMPL=rust make backend  → live scoring through tradecore
```
