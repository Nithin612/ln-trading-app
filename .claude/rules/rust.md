# Rust rules (engine/ workspace — from Phase 1)

Workspace: `engine-core` (pure logic, no I/O) · `engine-py` (PyO3/maturin
wheel `tradecore`) · `engine-cli` (native replay/bench binary).
Gate: `cargo fmt --check`, `cargo clippy -- -D warnings`, `cargo test`.

## Library discipline (engine-core)

- **No panics in library code.** No `unwrap`/`expect`/indexing that can
  panic on malformed market data — return `Result`/`Option`. `expect` is
  allowed only in tests and engine-cli main.
- **Pure and deterministic.** engine-core does no I/O, no clocks, no
  randomness: time enters as parameters, data as slices/iterators. This is
  what makes record/replay and backtest/live parity possible.
- Numeric canon: money = i64 scaled 1e-4 (matches Numeric(12,4) — sub-paise);
  indicator math = f64; factor scores/weights = f64; confidence =
  `(normalized.abs() * 100.0).trunc() as i32` (truncation matches Python
  `int()`); "factor not applicable" = `Option::None`, never 0.0-as-sentinel
  (the Python zero-sentinel is mapped explicitly at the boundary).
- Incremental state (indicators, forming candles) in preallocated ring
  buffers; no per-tick heap allocation in hot paths; borrow, don't clone
  (clippy will not catch semantic clones in loops — reviewers must).
- Rayon: parallelism bounded via `RAYON_NUM_THREADS` ≤ 6 on the dev machine
  (thermal budget); parallel iterators only over independent instruments —
  no shared mutable state without a documented reason.

## PyO3 boundary (engine-py)

- Release the GIL (`py.allow_threads`) around any compute > ~10µs.
- One call per BATCH of ticks, not per tick — GIL churn dominates otherwise.
- Convert at the boundary once: Python Decimal ↔ i64 1e-4 via string, never
  through f64 for money. Errors map to typed Python exceptions
  (`TradecoreError` subclasses), never panics across FFI.

## Parity (the migration contract)

- Golden fixture files (committed) generated from the FROZEN Python
  implementation are the oracle — pandas-ta version recorded inside each
  fixture.
- Tolerances: 1e-9 relative (EMA family) · 1e-6 (Wilder family: RSI/ADX/ATR)
  · EXACT on factor scores, confidence integers, and signal decisions.
- Every indicator ships: unit tests (hand-computed values), property tests
  (e.g. RSI ∈ [0,100], EMA between min/max of window), and golden tests.
- Semantic choices (window canon = last 300 completed candles, pivot ties
  count as pivots, greedy S/R clustering order) are documented in
  docs/ARCHITECTURE.md and replicated exactly — "better" behavior without a
  spec change + user sign-off is a bug.
