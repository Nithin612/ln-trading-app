---
name: perf-bench
description: Run the project's benchmarks and latency measurements, then record results in docs/PERFORMANCE.md with hardware context. Load after touching a hot path, closing a performance-relevant phase, or when asked "how fast is it".
---

# Performance bench

Numbers or it didn't happen. Every hot-path claim in this project traces to
a row in docs/PERFORMANCE.md.

## What to run (as available per phase)

1. **Python micro/meso:** targeted `uv run python -m timeit` or a 20-line
   bench script for the changed path (e.g. per-tick handle, candle upsert
   batch, signal eval for one stock). Warm up once, report best-of-5.
2. **Engine (Phase 1+):** `cd engine && cargo bench` (criterion) — indicator
   updates/sec, full confluence eval, backtest throughput (candles/sec),
   grid-search combos/sec at RAYON_NUM_THREADS=6.
3. **Parity-scale comparison (Phase 1+):** the standing pandas-vs-tradecore
   wall-clock table: full-universe scan · 2y/50-stock backtest · 200-combo
   grid. Same data, same machine, both engines.
4. **Live latency (Phase 3+):** replay a recorded session through the
   live-worker; report tick→Redis-publish p50/p95/p99 and candle-close→
   signal-persisted times from the built-in histograms.
5. **Frontend (Phase 5+):** replayed full-rate ticks against the style
   pages; React profiler commit times; must hold 60fps (≤16ms commits) on
   the live tables.

## Recording protocol (docs/PERFORMANCE.md)

Append, never overwrite (history shows drift):

```
## <date> — <phase/change> (commit <sha>)
Hardware: i7-1355U 12t, 15GB, balanced power · RAYON_NUM_THREADS=6
| Benchmark | Before | After | Budget | Verdict |
|-----------|--------|-------|--------|---------|
Notes: <anomalies, thermal throttling observed, data sizes>
```

## Budgets (fail loudly when exceeded)

- tick → Redis publish: p99 < 10 ms (200–500 instruments)
- candle-close → committed signal: < 100 ms (in-process engine)
- 2y/50-stock daily backtest: < 5 s (Rust target; pandas baseline recorded)
- UI live-table commit: ≤ 16 ms under full tick rate

Run benches on AC power, note `RAYON_NUM_THREADS`, close the Vite dev server
for engine benches. If a number regresses >20% with no code cause, suspect
thermals — rerun after cooldown and say so.
