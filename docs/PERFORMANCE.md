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

## Baselines to capture in Phase 1 (pandas, pre-Rust)

- [ ] Full-universe nightly scan (all active stocks, 1d)
- [ ] 2y × 50-stock daily backtest wall-clock
- [ ] 200-combo preset scan wall-clock
- [ ] Single-stock confluence eval (300 candles)

These become the "before" column of the Phase-1 comparison table.

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
