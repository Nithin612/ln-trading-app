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
from collections.abc import AsyncGenerator
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
    """Truncate all tables before each test for deterministic state."""
    async with _engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(
                text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE')
            )


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
