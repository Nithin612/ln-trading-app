# Python rules (backend/)

Python 3.12 · FastAPI async · SQLAlchemy 2 async + asyncpg · Celery · uv.
`make check` must stay green: pytest + ruff (line length 100) + mypy strict.

## Async discipline

- Handlers and services are `async def`; anything CPU-bound (pandas,
  backtests) goes to `asyncio.to_thread`, Celery, or the Rust engine — never
  on the event loop.
- Foreign threads (KiteTicker, Celery callbacks) never touch asyncio state
  directly: capture the running loop once (`asyncio.get_running_loop()` in
  the async context) and marshal with `loop.call_soon_threadsafe(...)`.
  `asyncio.get_event_loop()` raises on non-main threads in 3.12.
- Every `asyncio.create_task` result is owned: kept, awaited, or cancelled
  in a `finally`. No orphan tasks.
- Long-lived workers use bounded queues with an explicit overflow policy
  (drop-oldest for LTP-class data; never drop candle-closing events).

## Database

- `flush()` makes rows visible to THIS session; `commit()` makes them real.
  Side effects that depend on data visibility (Celery dispatch, Redis
  publish) fire AFTER the commit.
- Raw-SQL table names only from a whitelist (e.g. `TIMEFRAME_TABLE`), with a
  guard raise; values always bind-parameters. Bind Decimals as Decimal —
  never `float(price)`.
- Migrations: reversible (`alembic downgrade -1` works), one revision per
  change, never edit an existing revision (hook enforces). Hypertable
  gotchas: unique constraints must include `time`; DDL on compressed chunks
  needs decompress-first.
- Session lifetime: request-scoped via DI, task-scoped in Celery/workers.
  No module-level sessions.

## Style that matters here

- Full type annotations on public functions; mypy runs strict — fix the
  type, don't sprinkle `type: ignore` (each surviving ignore needs a code
  and a reason).
- Pydantic v2 models at the API edge (`XCreate` / `XUpdate` / `XOut`);
  domain code receives validated values, not raw dicts.
- Custom exceptions per domain; never bare `except:`; log with context
  (`log.exception` in handlers, structured key=value).
- Money is `Decimal`; construct from `str` (`Decimal(str(x))` when x is
  float-tainted), quantize to `Decimal("0.0001")` at persistence boundaries.
- Datetimes: always tz-aware (`datetime.now(tz=UTC)`); IST conversions via
  `zoneinfo.ZoneInfo("Asia/Kolkata")`, never manual +5:30 arithmetic.
- Imports at module top except to break cycles or defer heavy deps in Celery
  tasks (existing pattern) — comment why when deferring.
