# Trading-domain rules (non-negotiable)

These encode the platform's safety and correctness invariants. They override
convenience, deadlines, and "just this once". CLAUDE.md points here; the
full spec lives in docs/SIGNAL_ENGINE.md (protected — edits require explicit
user instruction + backtest regression per §8).

## Signal integrity

- **Confluence only.** No signal from a single indicator, ever. Everything
  flows through the weighted confluence scorer (≥70% gate; ADX regime
  adjustments per spec §4). New factors join the framework — they never
  bypass it.
- **No look-ahead.** Compute on candle N, valid from N+1. Backtest fills at
  N+1 open. Never evaluate indicators on `is_complete = false` candles for
  committed signals. The tick-level "forming/provisional" layer must be
  labelled as such end-to-end and never enters backtests or P&L.
- **No repainting.** A committed signal's factors were computed from data
  available at commit time; regeneration must not rewrite history
  (idempotency guard: `_has_active_signal`).
- **Position sizing mandatory.** Every signal carries
  `qty = floor(capital × risk% / |entry − SL|)`. risk_pct is a WHOLE
  percentage (2.0 = 2%) — `compute_quantity` divides by 100 itself; never
  pre-divide (that was the 100× undersizing bug).
- **Reject, don't clamp.** If the natural SL exceeds the classification cap
  (scalp/intraday 0.5%, swing 8%), reject the signal. Never tighten an SL to
  fit.
- **Validity per classification.** Scalp 30 min · intraday until 3:15 PM IST
  · swing 5 TRADING days · positional 30 TRADING days. Trading days need the
  NSE holiday calendar — calendar-day arithmetic is a bug.

## Python engine freeze (Phase 1, since 2026-07-04)

`backend/app/analysis/`, `app/backtest/engine.py`, and the swing/window
canon are FROZEN at the adjudicated state (commit ea4b06d): bugfix-only,
and any fix must regenerate the Rust oracle fixtures in the same commit.
The committed fixtures under `engine/crates/engine-core/tests/fixtures/`
are the parity oracle — the Python code becomes deletable after the
Phase-3 shadow week.

## Money and time

- Prices/P&L/capital: `Decimal` in Python, `Numeric(12,4)` in Postgres,
  i64 scaled 1e-4 in Rust. Floats allowed ONLY inside indicator math (f64)
  and display payloads.
- Storage UTC, market logic IST (UTC+5:30 — half-hour offset: date-boundary
  bugs are easy). All datetimes tz-aware. Candle periods session-aligned
  (9:15 IST open), never naive UTC-hour floors.
- Session guard: ticks outside 9:15–15:30 IST (pre-open, post-close) must
  not mint candles.

## Trading safety

- Paper mode is the default. Live mode requires explicit user opt-in AND a
  30-day profitable paper record (enforced in code, not by promise).
- The daily-loss circuit breaker is never disabled, weakened, or made
  configurable-off in live mode. Not for tests, not on request.
- Kite access tokens die ~6:00 AM IST daily: any long-running consumer must
  treat token expiry as a normal lifecycle event (restart + warmup +
  gap-fill), not an error loop.
- Kite REST is rate-limited (historical ~3 req/s): all REST calls go through
  the shared throttled client — never raw `requests`/`httpx` to Kite.

## Redis contracts

- Latest price: KEY `ltp:{stock_id}` (plain Decimal-parseable string,
  TTL 600s) — import `LTP_KEY` from `app.broker.tick_consumer`, never retype.
- Fan-out: pub/sub channels `ltp:{instrument_token}`,
  `candle:{table}:{stock_id}` (at-most-once, OK to drop).
- Anything that must not be lost (alerts, queued work) uses Redis Streams or
  the DB — never bare pub/sub.
- Every cache key gets a TTL (eviction policy is volatile-lru: TTL-less keys
  are treated as broker-critical and never evicted).
