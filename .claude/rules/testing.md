# Testing rules

Every feature ships with tests — no exceptions, no "in the next commit".
A bug fix ships with a regression test that fails on the old code.
453 green tests once coexisted with a dead live pipeline: test the SEAMS,
not just the units.

## Backend (pytest)

- Real Postgres test DB (`trading_platform_test`) and real Redis — no DB
  mocks. `conftest.py` truncates all tables per test; use the `db` and
  `client` fixtures, factories from `tests/helpers.py` (`make_stock`,
  `create_test_user`, `get_auth_headers`).
- asyncpg + pytest-asyncio: NullPool and function-scoped event loops (the
  configured pattern — don't fight it, a session-scoped loop deadlocks).
- EmailStr fields: use `.com` domains in fixtures (pydantic rejects some
  TLDs).
- Datetimes in tests: tz-aware always; freeze or inject time via parameters
  rather than sleeping. No `time.sleep` for synchronization — poll with
  timeout or use events.
- Deterministic: no unseeded randomness; market-data fixtures constructed
  explicitly (or golden files) so failures reproduce.

## What good coverage means here

- Each behavior branch of the change has a test; error/rejection paths
  (SL-cap rejection, circuit breaker, expired token, empty candles, None
  from Redis) are covered, not just happy paths.
- Cross-component contracts get an integration test through BOTH sides
  (e.g. consumer SETs `ltp:{stock_id}` → paper_broker reads it). Mocking
  the seam hides the seam.
- Assertions check VALUES (prices as exact Decimals, counts, payload
  fields), not just status codes / "did not raise".
- Regression tests: name them `test_<bug>_...` with a docstring saying what
  broke; include a canary assertion that would fail on the old behavior.

## Engine (from Phase 1)

- Rust: `cargo test` unit + property tests per indicator; criterion benches
  under `engine-core/benches` (numbers land in docs/PERFORMANCE.md).
- Parity: pytest suite compares Python reference vs `tradecore` on golden
  fixtures (tiered tolerances per .claude/rules/rust.md); zero
  signal-decision diffs on the 2y × Nifty50 corpus.
- Replay (from Phase 3): recorded tick sessions replayed through the live
  engine must produce byte-identical event streams; replay tests run in CI
  (`make replay`).

## Frontend (Vitest + RTL)

- Query/assert by role and visible text; mock `@/lib/api/*` modules, not
  fetch; cover loading skeleton, empty, error, and primary interaction for
  every page.

## Definition of done (per feature)

`make check` green (pytest + ruff + mypy + vitest + eslint + tsc, plus cargo
gates once engine/ exists) · reversible migration · manual smoke in browser ·
CHANGELOG entry under Unreleased · relevant subagent review (quant-verifier
for anything touching analysis/signals/backtest; bug-hunter for pipeline
changes; ui-reviewer for frontend).
