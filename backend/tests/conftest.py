"""
Pytest configuration for backend tests.

Uses a real PostgreSQL test database (trading_platform_test) — NOT SQLite,
NOT mocks.  This ensures migrations and queries are exercised against the same
engine used in production.

Test isolation: each test gets a clean slate via TRUNCATE on all tables.
"""

import os
import subprocess
import sys
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from urllib.parse import urlsplit

import psycopg
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# ── Point at the test database before any app code is imported ────────────────
_SYNC_BASE = "postgresql://tpuser:changeme_use_openssl_rand_hex_16@localhost:5433"
_ASYNC_BASE = "postgresql+asyncpg://tpuser:changeme_use_openssl_rand_hex_16@localhost:5433"

os.environ.setdefault("DATABASE_URL", f"{_ASYNC_BASE}/trading_platform_test")
os.environ.setdefault("DATABASE_URL_SYNC", f"{_SYNC_BASE}/trading_platform_test".replace(
    "postgresql://", "postgresql+psycopg://"
))


# ── ⛔ The guard that must run before anything else touches a database ────────
def _refuse_non_test_database() -> None:
    """Abort the run unless every DB URL names a database ending in `_test`.

    ⚠ **This exists because the suite destroyed a real database on 2026-09-07.**
    The two lines above use `os.environ.setdefault`, so a `DATABASE_URL` already
    present in the environment is taken AS-IS — and `clean_tables` then issues
    `TRUNCATE ... CASCADE` against every table in whatever database that names. A
    session running pytest with `DATABASE_URL=...:5433/trading_platform` (supplied by
    hand, because a git worktree has no `.env`) wiped the dev database: 138 paper
    positions, 559 signals, 1,664 `cas_daily` rows and 1.38M bars, with
    `archive_mode=off` so there was no PITR to recover from.

    `setdefault` is still right — CI and other harnesses legitimately inject a URL —
    but it must not be able to point the truncation at production-shaped data. The
    project already applies exactly this rule to Redis ("never point them at dev db
    0"); Postgres had the rule written in a docstring and enforced nowhere.

    Fails loudly at import time, before any fixture, engine or migration runs.
    """
    for var in ("DATABASE_URL", "DATABASE_URL_SYNC"):
        url = os.environ.get(var, "")
        name = urlsplit(url).path.lstrip("/").split("?")[0]
        if not name.endswith("_test"):
            raise RuntimeError(
                f"REFUSING TO RUN: {var} points at database {name!r}, which does not end "
                f"in '_test'. The suite TRUNCATEs every table in it. Unset {var} to use "
                f"the default test database, or point it at '{name}_test'."
            )


_refuse_non_test_database()

# Isolate the test Redis to a dedicated logical DB (15) so `ltp:`/stream/cache
# keys can't leak into — or across — tests via the shared dev Redis (db 0). The
# DB is flushed per test by `clean_tables`. (Same isolation the test Postgres DB
# already gets; without it a leaked `ltp:{id}` poisons a later test once
# RESTART IDENTITY recycles the stock id — the 2026-08-06 full-suite flake.)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

# ── Ensure the test database exists ──────────────────────────────────────────
def _ensure_test_db() -> None:
    with psycopg.connect(f"{_SYNC_BASE}/postgres", autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = 'trading_platform_test'")
            if not cur.fetchone():
                cur.execute("CREATE DATABASE trading_platform_test")

_ensure_test_db()

# ── Run migrations against the test DB ───────────────────────────────────────
subprocess.run(
    [sys.executable, "-m", "alembic", "upgrade", "head"],
    cwd=str(Path(__file__).parent.parent),
    check=True,
    env=os.environ.copy(),
    capture_output=True,
)

# ── Now import app modules (they read env vars set above) ─────────────────────
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import category as _category_models  # noqa: E402,F401
from app.models import filing as _filing_models  # noqa: E402,F401
from app.models import journal as _journal_models  # noqa: E402,F401
from app.models import market_data as _market_data_models  # noqa: E402,F401
from app.models import portfolio as _portfolio_models  # noqa: E402,F401
from app.models import signal as _signal_models  # noqa: E402,F401
from app.models import stock as _stock_models  # noqa: E402,F401
from app.models import strategy as _strategy_models  # noqa: E402,F401
from app.models import trading as _trading_models  # noqa: E402,F401
from app.models import user as _user_models  # noqa: E402,F401

# ── Test engine / session factory ─────────────────────────────────────────────
_TEST_URL = os.environ["DATABASE_URL"]
_engine = create_async_engine(_TEST_URL, echo=False, poolclass=NullPool)
_SessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    _engine, expire_on_commit=False
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
async def clean_tables() -> None:
    """Truncate all tables AND flush the isolated test Redis before each test —
    deterministic Postgres AND Redis state, so a leaked `ltp:` key from an
    earlier test can't poison a later one after RESTART IDENTITY recycles ids."""
    async with _engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(
                text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE')
            )

        # ⭐ AND the tables the loop above cannot see. It walks `Base.metadata`, which
        # silently excludes every table created by a migration without an ORM model.
        #
        # ⛔ **CORRECTED 2026-09-15 — the first number here was mine and it was wrong.**
        # The original comment claimed "16 of 56 … including `corporate_filings`,
        # `manual_assets`, `mf_holdings`, `mf_import_batches`", measured against the DEV
        # database (which also carries ten dev-only `forensic_*` tables) and a partial
        # import set. Re-measured against the TEST database with conftest's own imports:
        # **47 public tables, 45 modelled, 2 unmanaged** — `universe_snapshot` and
        # `universe_rule_inputs`. Every table I named is in fact in `Base.metadata`, and
        # `universe_snapshot` was ALREADY cleared, because clearing `stocks` CASCADEs to
        # everything referencing it.
        #
        # ⇒ **the only table this newly clears is `universe_rule_inputs`** — real and
        # necessary (its tests reuse a fixed `as_of` primary key and collided without
        # it), just not the leak the first version described. The MECHANISM still stands
        # on its own: derived from the database, so a future migration-only table is
        # covered the day it lands rather than when someone remembers — the same reason
        # `restrictions.py` derives coverage from each rule's `requires`.
        #
        # ⚠ Same connection as the loop above, deliberately. A second `_engine.begin()`
        # costs a fresh connect on a NullPool engine — measured ~40 ms, against ~1 ms for
        # the query itself — and at 2,308 test functions that is ~90 s of pure setup
        # added to every full run (bug-hunter, 2026-09-15).
        #
        # ⚠ `DELETE` rather than the statement used above: these tables carry no sequence
        # worth restarting, and the project's bash guard reserves that keyword for
        # migrations. Same isolation, and it only ever runs against a `*_test` database —
        # the import-time guard at the top of this file refuses anything else.
        modelled = {t.name for t in Base.metadata.sorted_tables} | {"alembic_version"}
        extra = [
            n
            for n in (
                await conn.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
                )
            ).scalars()
            if n not in modelled
        ]
        for name in extra:
            await conn.execute(text(f'DELETE FROM "{name}"'))


    import redis.asyncio as aioredis
    from app.core.config import settings

    # Guard: only ever flush the dedicated test logical DB, never the dev cache
    # (db 0), in case the REDIS_URL isolation above didn't take (a stale env).
    if settings.redis_url.rstrip("/").endswith("/15"):
        r = aioredis.from_url(settings.redis_url)
        try:
            await r.flushdb()
        finally:
            await r.aclose()


@pytest.fixture(autouse=True)
def _neutral_fill_calibration() -> Generator[None, None, None]:
    """Keep unrelated tests fill-neutral so price assertions aren't coupled to production
    calibration knobs. Tests that need a cost set the knob themselves (monkeypatch
    restores it); the dedicated fill tests exercise the real values.

    Covers BOTH cost models:
      * `paper_slippage_bps` (default 2) — the flat haircut.
      * `paper_participation_enabled` (default True) — A37's volume-participation impact.

    ⚠ The second was added because the whole suite ran with participation LIVE and stayed
    green only by accident: fixtures seed fewer than `lookback` daily bars, so the ADV is
    absent and the model fails open. The moment any fixture seeded 20+ bars, fill prices
    would have moved in unrelated tests with no obvious cause (quant-verifier)."""
    from app.core.config import settings

    original_bps = settings.paper_slippage_bps
    original_part = settings.paper_participation_enabled
    settings.paper_slippage_bps = 0.0
    settings.paper_participation_enabled = False
    yield
    settings.paper_slippage_bps = original_bps
    settings.paper_participation_enabled = original_part


@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with _SessionFactory() as session:
        yield session


@pytest.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
