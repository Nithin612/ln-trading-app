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
def _neutral_paper_slippage() -> Generator[None, None, None]:
    """Keep unrelated tests slippage-neutral so fill-price assertions aren't
    coupled to the production `paper_slippage_bps` calibration knob (default
    2 bps). Tests that need the haircut set `settings.paper_slippage_bps`
    themselves (monkeypatch restores it); the dedicated slippage tests exercise
    the real 2-bps path."""
    from app.core.config import settings

    original = settings.paper_slippage_bps
    settings.paper_slippage_bps = 0.0
    yield
    settings.paper_slippage_bps = original


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
