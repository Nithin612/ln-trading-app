# Phase 1 — Rust engine core, adjudication, parity, benchmarks

**Completed:** 2026-07-04 · **Exit gate passed:** 2026-07-05 ·
**Plan:** `docs/UPGRADE_PLAN.md` (Phase 1)
**Commits:** `3c87028` (scaffold) → `e29cc75` (parity+bench), 11 commits,
plus the gate commit (fmt fix + dispatch guards + docs).

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
| Rust tests | 30 (unit+property+4 oracle fixtures) — parity exact on first run for patterns/structure, confluence, and backtest |
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

## Exit gate (2026-07-05, `/phase-gate`)

- **Static:** ruff · mypy (112 files) · eslint · tsc · cargo fmt · clippy —
  green after fixing a missed rustfmt pass on `engine-py/lib.rs` +
  `engine-cli/main.rs` (3 cosmetic diffs the "final lint sweep" had skipped;
  the stale usage hint gained `backtest` while there).
- **Suites:** Rust **30** · backend **453** · frontend **131** · parity **6**
  — all green.
- **Smoke:** ENGINE_IMPL seam on all 49 Nifty50 windows — 2 fire at the
  70-gate (EICHERMOT BUY conf 82, POWERGRID BUY conf 76), EXACT across
  engines factor-for-factor; at gate 0, 39/49 fire, all exact. Native
  `engine-cli backtest` on the corpus regenerated with the bench-day anchor
  reproduces the recorded run **to the trade** (49 stocks, 807 trades,
  154 ms).
- **Regression:** metric deltas vs v1 goldens are the five adjudicated
  decisions, user-approved 2026-07-04; the committed fixtures are the new
  goldens and cargo test + `make parity` pin them exactly.
- **Review:** quant-verifier — adjudicated canon (A–E) implemented
  consistently in both engines, look-ahead hygiene, i64/Decimal money
  discipline, and exact 96-window/125-trade parity all verified sound.
  Initial BLOCKED was solely the uncommitted fmt fix (finding 1), resolved
  in the gate commit.

### Gate fixes applied

- `score_signal` rust branch fails loud (`NotImplementedError`) on non-zero
  FII/DII flows — tradecore has no flow inputs yet; silently dropping a
  weight-5 factor could flip decisions (+ regression test).
- `score_signal` rust branch answers timeframes ≠ 1d with the python
  reference engine (warning logged) — only 1d is fixture-pinned; Rust
  intraday classification/pivots are unpinned until Phase 3
  (+ regression test). Parity suite 4 → 6 tests.
- `parity` pytest mark registered; ARCHITECTURE.md fixture path corrected.

### Carried forward from review

- **Phase 3, before shadow week:** expose factor `is_pattern`/`is_indicator`
  through the FFI so rust-path signals persist real
  `triggering_patterns`/`triggering_indicators` + explanations (today:
  empty lists and `"tradecore"` placeholder strings — decision/levels/qty
  are identical, the stored envelope is not). Add intraday parity goldens,
  then remove the off-1d fallback.
- **User adjudication needed (§8 process, same ritual as A–E) — none of
  these block Phase 1 (pre-existing v1 behavior, identical in both engines,
  fixture-pinned):**
  - **F)** Spec §4 "ATR(14) > 3% of price → reduce position size 25%" is
    implemented in NEITHER engine (`atr_pct_of_price` in bbands.py is dead
    code). Implement in both + regenerate fixtures, or amend the spec.
  - **G)** Spec §2.2 Morning/Evening Star: the gap condition is omitted in
    both engines (star patterns fire more often than spec).
  - **H)** Weight semantics: every sub-factor carries its full group weight
    (EMA_CROSS 15 + PRICE_VS_EMA 15, RSI 10+10, MACD 10+10, BBANDS 10 has
    no §3 row) → max fired weight 150+10, not §3's 105; §7's worked example
    is internally inconsistent (70+0.75+2 ≠ 73.75). Needs a one-line ruling
    recorded in ARCHITECTURE.md §Adjudicated canon.

### F/G/H evidence (measured 2026-07-05, `scripts/adjudication_experiments_fgh.py`)

Pinned corpus (anchor 2024-06-04T12:00Z, 49 stocks × 2y, 24,878 rows);
BASELINE reproduces the 807-trade parity oracle exactly. Variants are
runtime monkeypatches; frozen code untouched. Awaiting user rulings.

| variant | trades | win% | avgPnL% | totPnL% | sharpe | maxDD% |
|---|---|---|---|---|---|---|
| BASELINE (adjudicated engine) | 807 | 38.9 | −0.10 | −78.7 | −0.27 | 99.4 |
| G — star real-body gap required | 599 | 40.1 | +0.09 | **+52.1** | +0.13 | 96.2 |
| H1 — pairs share group weight | 1,212 | 37.0 | −0.61 | −744.4 | −1.10 | 100.0 |
| H2 — H1 + BBANDS excluded | 1,241 | 36.8 | −0.60 | −740.4 | −1.07 | 100.0 |
| G+H1 combined | 892 | 38.3 | −0.52 | −464.7 | −0.87 | 100.0 |

- **G:** 1,384 of 1,778 star detections (78%) fail the §2.2 gap — the
  gap-less ±0.95 stars out-score every other pattern and mint bad trades.
  Adding the gap flips the corpus positive. Strong case to implement.
- **H:** sharing group weights LOOSENS the gate (moderate-scoring pair
  members stop diluting the normalized score) → ~400 extra, worse trades.
  Current per-sub-factor weights act as a conservative filter. Strong case
  to keep code semantics and amend §3/§7 instead. BBANDS in/out immaterial.
- **F** (post-processed from the baseline trade list — sizing never enters
  pnl_pct metrics): 46/807 trades (5.7%) were in the ATR>3% regime, 0
  dropped by the reduction; those trades were net **winners** (+₹1.49L), so
  the −25% cut costs ₹37,195 realized P&L while removing ₹1,15,481
  capital-at-risk. A pure risk-preference call, not an accuracy one.
- Caveats: one corpus (2y × Nifty50 daily), untuned weights. G/H effects
  are structural and far beyond the §8 5% bar; F's delta is thin evidence
  either way (46 trades).

**Rulings (user, 2026-07-05): G implement · H keep-code-amend-spec ·
F implement — applied the same day** in both engines in lockstep with
regenerated oracles (backtest fixture 125→101 trades; generator now
committed as `scripts/generate_engine_fixtures.py`). SIGNAL_ENGINE.md
§3/§7 amended under explicit user authorization (guard lifted for exactly
two edits, then restored — verified byte-identical). New standing
baseline: **599 trades · win% 40.1 · totPnL +52.1 · sharpe +0.13 ·
maxDD 96.2**; Rust engine-cli reproduces 599 exactly (172 ms). +8
regression tests (backend 461 · Rust 33 · parity 6). Full ruling table:
docs/ARCHITECTURE.md §Adjudicated canon, second round.

Quant-verifier on the applied diff (commit f14552f): **SIGNOFF,
pass-with-notes** — operators/boundaries/integer arithmetic/decision
windows verified identical cross-language, zero look-ahead, oracle delta
fully decomposed into F/G, guard restoration byte-verified. Two INFO
follow-ups carried to Phase 2: persist a `volatility_reduced` flag (or
pre-reduction qty) on Signal rows so journal review can attribute §4
sizing cuts; make the §7 example window mechanically checkable via the
fixture generator.
- **Benign, noted:** ADX>40 gate is `max(65, min_conf−5)` — equals spec at
  the configured 70, diverges for other minimums; swing/positional expiry
  approximates trading days as 7/42 calendar days (expires EARLY — safe
  direction) until the NSE calendar lands in Phase 2.
