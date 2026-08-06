# Performance ledger

Numbers or it didn't happen: every hot-path claim traces to a dated row
here. Protocol and budgets live in the `/perf-bench` skill; append new
sections, never overwrite old ones (history shows drift).

## Budgets (hard targets, fail loudly)

| Path | Budget | Since |
|---|---|---|
| tick → Redis publish (full universe, ~2,055 instruments) | p99 ≤ 50 ms (hard) — **MET, measured on the optimized worker across two full sessions 2026-07-15/16**; the (10,20] tightening target was NOT reached (total p99 still (20,50] every segment), so the gate stays 50 ms. The 8eac05a slate moved processing p50 7.5→5.0 ms and (07-15 main segment) processing p99 into (10,20]; further reading is histogram-limited (bucket ladder jumps 20→50) — ledger §Fourth soak | Phase 3 · restated 2026-07-14 by user ruling (was p99 < 10 ms, authored for 200–500 instruments; three independent full-scale soak measurements pinned steady-state p50 7.5 / p99 (20,50] — ledger §Third soak) · verdict recorded 2026-07-16 |
| candle close → committed signal persisted | < 100 ms | Phase 3 |
| 2y × 50-stock daily backtest (Rust) | < 5 s | Phase 1 |
| Weight-grid combo (Rust, RAYON≤6) | measured Phase 1, then regression-gated | Phase 1 |
| UI live-table commit under full tick rate | ≤ 16 ms (60 fps) — **MET 2026-08-06**: React commit p99 **7.6–8.8 ms** across 50/300/1,000-row profiles at 500–5,000 ticks/s in real Chrome 151; frame cadence flat 60 Hz, zero jank frames in the realistic profile (§Phase 5 browser measurement) | Phase 5 |

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

**2026-07-07 intraday walk-forward wall-clocks (slice 8c-3, dev machine):**
F&O universe (205 ran / 5 excluded), eval 2024Q4→2026Q2, one
tradecore.run_universe per profile, 15-symbol load chunks (a 400-symbol
5m fetch buffers >10M rows and OOMs the 16GB machine — do not raise):

| Profile | TF | Bars loaded | Wall-clock |
|---|---|---|---|
| pdh_pdl | 15m | ~3.8M | 82 s |
| orb_15m | 15m | ~3.8M | 75 s |
| gainer_925 | 5m | ~10.7M | 244 s |

Harness replay of all 8 goldens ≈ 7 min (inside make check via
`make walkforward`). Loading dominates; the engine itself is seconds.

---

## 2026-08-06 — Phase 5: live-layer render cost (UI)

Source: `frontend/src/test/livePerf.test.ts` (runs in `make check`, so these
are regression-gated, not one-off readings). Measures `useLiveQuotes` v2 with a
500-symbol subscription and a stubbed rAF driven off the fake-timer clock.

**What the Phase-5 UI budget actually rests on** — render count is a function of
FRAMES, not of tick count:

| Measurement | Result |
|---|---|
| 12,000 ticks delivered over 60 frames | **60 renders** (exactly one per frame) |
| 10 ticks vs 10,000 ticks inside ONE frame | **1 render either way** |
| A frame with no ticks | **0 renders** — no rAF is scheduled, so an idle tape is free |
| Coalescing correctness | newest price per symbol survives the frame (latest-wins) |

The "before" for context: v1 did one `setState` per tick, each cloning the whole
quote map — i.e. 12,000 renders and 12,000 O(n) copies for the same input, plus
a socket teardown on every symbol-list change and a `subscribe` re-sent every
render. Those are fixed (Phase 5 slice 5.1); the numbers above are the after.

### Browser measurement — the 60 fps budget row is MET

Measured 2026-08-06 in **real Chrome 151 (headless=new)** via
`frontend/perf/run-bench.mjs`, which drives `frontend/perf/live-table-bench.html`
(source `src/perf/LiveTableBench.tsx`) over the DevTools Protocol. The harness
mounts the REAL `useLiveQuotes` + `useVirtualRows` + `PriceCell` + themed table,
feeds them from a stubbed socket at a chosen tick rate with a price that moves
every tick (so `PriceCell` actually flashes and the DOM genuinely changes), and
reports React `<Profiler>` `actualDuration` per commit — literally the quantity
the budget names — plus rAF frame intervals and PerformanceObserver long tasks.

Reproduce (needs a dev server; use the isolated bench config so it cannot
clobber a running one's optimize cache):

```
cd frontend
./node_modules/.bin/vite --config perf/vite.bench.config.ts     # port 5199
node perf/run-bench.mjs --url http://localhost:5199 --rows 300 --tps 2000 --ms 10000
```

| Profile | Rows | Ticks/s | Ticks | Commits | Commit p50 / p95 / **p99** / max (ms) | Frame p50 / p99 (ms) | Frames > 20 ms | Long tasks |
|---|---|---|---|---|---|---|---|---|
| Realistic (suggestions cap at 50 rows) | 50 | 500 | 4,910 | 951 | 1.0 / 4.4 / **8.8** / 28.1 | 16.7 / 16.8 | **0** of 595 | 0 |
| Stress | 300 | 2,000 | 19,920 | 534 | 2.4 / 6.0 / **7.8** / 56.4 | 16.7 / 16.8 | 2 of 598 | 1 |
| Headroom | 1,000 | 5,000 | 49,900 | 529 | 2.2 / 5.3 / **7.6** / 91.7 | 16.7 / 16.8 | 2 of 598 | 1 |

| Path | Budget | Status |
|---|---|---|
| UI live-table commit under full tick rate | ≤ 16 ms (60 fps) | **MET — worst p99 8.8 ms across all three profiles** |

Reading the numbers honestly:

- **Frame cadence is a flat 60 Hz** (p50 16.7 ms, p99 16.8 ms). "Frames > 16.7"
  is a useless metric at 60 Hz — vsync lands at 16.67–16.8 — so jank is counted
  at **> 20 ms** (missed slot) and **> 33 ms** (visible stutter).
- The 2 slow frames and the single long task in the heavier profiles are the
  **mount/first-paint hitch**, not steady state; the realistic profile has zero
  of both. The `max` commit values (28–92 ms) are that same first commit.
- **Row count barely moves the cost** — 50 → 1,000 rows changes p99 by ~1 ms —
  because windowing renders ~26 rows regardless. That is the virtualization
  earning its place.
- **Ticks per second barely move it either**, which is the rAF batching: 4,910
  vs 49,900 ticks land within ~1 ms of the same p99.

Caveats, stated rather than buried:

- **Headless Chrome**, so the compositor/GPU path differs from a windowed
  browser. Treat this as the main-thread cost, which is what the budget targets.
- **The socket is stubbed.** This measures the CLIENT's cost to apply and paint
  a full-rate tape. The backend tick→publish path is a separate budget, already
  measured over four soaks (see §Budgets).
- Run on a contended box (a `make check` was running), so if anything these are
  pessimistic.
