# Performance ledger

Numbers or it didn't happen: every hot-path claim traces to a dated row
here. Protocol and budgets live in the `/perf-bench` skill; append new
sections, never overwrite old ones (history shows drift).

## Budgets (hard targets, fail loudly)

| Path | Budget | Since |
|---|---|---|
| tick → Redis publish (200–500 instruments) | p99 < 10 ms | Phase 3 |
| candle close → committed signal persisted | < 100 ms | Phase 3 |
| 2y × 50-stock daily backtest (Rust) | < 5 s | Phase 1 |
| Weight-grid combo (Rust, RAYON≤6) | measured Phase 1, then regression-gated | Phase 1 |
| UI live-table commit under full tick rate | ≤ 16 ms (60 fps) | Phase 5 |

Hardware context for all local numbers: i7-1355U (2P+8E, 12 threads),
15 GB RAM, laptop thermals — bench on AC power, note RAYON_NUM_THREADS,
close the Vite dev server for engine benches.

## Baselines captured 2026-07-03 (pandas, pre-Rust) — the "before" column

Corpus: 3y NSE bhavcopy backfill (1.29M daily candles, 2,330 stocks);
benches on the 2y × 49-Nifty50 slice. Machine idle during runs.

| Benchmark | pandas baseline | Notes |
|---|---|---|
| Single confluence eval (300 candles) | **44.5 ms** | best of 5, ADANIENT |
| Full-universe scan (2,207 stocks) | **91.4 s** | one eval per stock |
| 2y × 49-stock daily backtest | **883.8 s (14.7 min)** | 863 trades; O(n²) growing-window recompute |
| 200-combo weight grid (49 stocks) | **≈ 50.5 h (extrapolated)** | 185.6 s/combo measured on 10 stocks × 3 combos |

The 50-hour grid is why the strategy lab moves to Rust (target: minutes).
Baseline trading metrics on this corpus, for regression context: win% 39.8,
Sharpe −0.07, maxDD 94.2% — the untuned engine is not profitable on real
2023–26 daily data; tuning (Phase 6) and the adjudication decisions get a
honest starting line, not a flattering one.

---

## 2026-07-03 — Phase 0 (commit 565f127)

No compute-path changes benchmarked (triage phase). Relevant structural
wins recorded for context, not as benchmarks:

- Backtest/preset endpoints moved off the event loop (`asyncio.to_thread`)
  — API + /ws/live no longer freeze for the duration of a backtest.
- Tick handling commits once per Kite batch (~1/s) instead of holding one
  transaction open all day; Celery publishes batched off-loop.
- Chain recorder budget check: NIFTY+BANKNIFTY nearest-expiry (2×10+1
  strikes × CE/PE + FUT ≈ 86 instruments) = 1 × kite.ltp + 2 × kite.quote
  per minute — comfortably inside Kite's ~1 rps quote budget.

---

## 2026-07-04 — Phase 1: Rust engine vs pandas (adjudicated canon)

Hardware: i7-1355U 12t, 15GB · RAYON_NUM_THREADS=6 · release build (thin
LTO). Identical corpus: 2y × 49 Nifty50 daily from ohlcv_1d. Parity proven
first (tests/parity: exact factor scores, confidence integers, decisions,
trade lists), THEN timed — the two engines produce identical output.

| Benchmark | pandas (frozen) | Rust engine-core | Speedup |
|---|---|---|---|
| 2y × 49-stock full backtest | 883.8 s | **0.143 s** (807 trades) | **~6,180×** |
| 200-combo weight grid (extrapolated) | ≈ 50.5 h | **≈ 29 s** (200 × 0.143) | ~6,200× |
| Single confluence eval (amortized) | 44.5 ms | ~6.5 µs (22k evals / 143 ms / 6 threads) | ~6,800× |

Notes: pandas number is the pre-adjudication measurement (same O(n²)
structure; canon changes don't affect its complexity). Rust number from
`engine-cli backtest corpus_2y_nifty50.json`. The strategy lab moves from
"overnight batch, maybe" to interactive. Budget "2y×50 backtest < 5 s"
beaten by 35×.

**2026-07-05 exit-gate re-run:** corpus regenerated with the bench-day
anchor reproduces the run exactly — 49 stocks, **807 trades, 154 ms**
(machine not fully idle; same class as 143 ms). Caveat for future benches:
the corpus recipe is date-anchored (`now() − 760 d`), so regenerating a day
later shifts the window one session and yields 791 trades — same engine,
different corpus. Pin an explicit `since` date when comparing across days.

---

## 2026-07-05 — Adjudications F/G/H applied (new standing canon)

Same pinned corpus (anchor 2024-06-04, 49 stocks × 2y, 24,878 rows).
Python engine and Rust engine-cli agree on the trade count exactly.

| Metric | A–E canon | post-F/G canon |
|---|---|---|
| Trades | 807 | **599** |
| win% | 38.9 | **40.1** |
| totPnL% | −78.7 | **+52.1** |
| sharpe | −0.27 | **+0.13** |
| maxDD% | 99.4 | 96.2 |
| Rust wall-clock (RAYON=6) | 154 ms | **172 ms** |

The +18 ms is §4's ATR(14) now computed per decision window (item F);
budget "2y×50 < 5 s" still beaten ~29×. Star detections on the corpus drop
1,778 → 394 (gap-conformant only, item G). F resizes volatile trades'
quantities without dropping any trade on this corpus; quantities enter
rupee P&L, not the pnl_pct metrics above.

**2026-07-06 metrics-ordering canon (Phase 2 slice 8b):** the equity curve
and max drawdown now compound trades sorted by (entry_date, stock) —
previously dict-insertion order (stock-grouped), which made max-DD depend
on universe ordering and physically meaningless across stocks. Win rate,
averages, Sharpe, Sortino are order-independent and unchanged; trade lists
(the parity/fixture contract) are unchanged. Equity/max-DD values in
`strategy_runs` rows and docs recorded BEFORE this date are not comparable
to new runs.

**2026-07-06 walk-forward wall-clocks (Phase 2 slice 8b, dev machine,
RAYON_NUM_THREADS=6):** one continuous `tradecore.run_universe` per profile
over [2023-07-03, 2026-06-30], setup gates as python post-filter, quarterly
folds 2024Q4→2026Q2:

| Profile | Universe (ran/excluded) | Wall-clock |
|---|---|---|
| dc1 (NIFTY50) | 47/3 | 0.5 s |
| dc2 (NIFTY50) | 47/3 | 7.4 s |
| rrbo_basic (NIFTY50) | 47/3 | 0.6 s |
| rrbo_trailing (NIFTY50) | 47/3 | 0.6 s |
| multibagger (all_active) | 1118/1230 | 15.1 s |

dc2's 7.4 s is the python `sr_zone_factor` recompute per candidate trade
(prior-window DC1 check), not the engine. multibagger is load-dominated
(~1.7 M rows). Full 5-profile regen ≈ 24 s; harness replay (5 goldens +
coverage test) 23.3 s — cheap enough to sit inside `make check`.
