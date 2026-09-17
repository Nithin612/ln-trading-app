"""U8 — the index registry, and the honest limit of what registering it bought.

⭐ `indices` held **3 rows** (NIFTY50, BANKNIFTY, FINNIFTY) against **166 indices** in the
free NSE daily file the VIX recorder already downloads. So `benchmark.py` could only ever
return NIFTY50, every "sector" comparison was against the broad market, and the overlay was
unevaluable rather than untested.

⛔ **But registering them did NOT make sector-RS sector-relative** — see
`TestTheSectorIndicesAreNotYetUSED`, which is the most important thing in this file.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from app.models.stock import Index
from app.services.benchmark import benchmark_symbol_for
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock


#: ⚠ The registry is seeded by migration `c3d4e5f6a7b8`, and `conftest.clean_tables`
#: TRUNCATEs every table before each test — so migration-seeded rows are NOT present here.
#: That is the same phenomenon V6's starvation alarm found in `strategy_profiles`: a data
#: seed is invisible to anything that empties the table afterwards. So the DECLARED list is
#: asserted against the migration module directly, and behaviour is tested on fixtures.
def _load_migration() -> ModuleType:
    """⚠ `alembic/versions/` is not an importable package (no `__init__.py`, and the
    filenames start with a hex revision id), so it is loaded by PATH. Reading the
    migration's own constants is the point: this asserts what the seed DECLARES, which is
    the only thing that survives `clean_tables` truncating the table."""
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "c3d4e5f6a7b8_u8_index_registry.py"
    )
    spec = importlib.util.spec_from_file_location("u8_index_registry", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MIGRATION = _load_migration()
REGISTERED: tuple[tuple[str, str], ...] = _MIGRATION._SECTOR + _MIGRATION._SIZE


class TestTheDeclaredRegistry:
    def test_it_registers_the_sector_and_size_sets(self) -> None:
        symbols = {s for s, _ in REGISTERED}
        assert {"NIFTYAUTO", "NIFTYIT", "NIFTYPHARMA", "NIFTYREALTY"} <= symbols
        assert {"NIFTYNEXT50", "NIFTY500", "NIFTYMIDCAP150"} <= symbols
        assert len(REGISTERED) == 24  # 16 sector + 8 size; the 3 originals already exist

    def test_the_healthcare_name_carries_its_trailing_word(self) -> None:
        """⚠ The one that would have failed SILENTLY. `Index.name` is the join key the
        ingester matches against the CSV's "Index Name", and the real name is
        **"Nifty Healthcare Index"** — the plan's prose says "Healthcare". A near-miss
        registers an index that never ingests, with no error anywhere. Verified against
        the live file on 2026-09-16."""
        names = dict(REGISTERED)
        assert names["NIFTYHEALTH"] == "Nifty Healthcare Index"

    def test_no_bond_or_futures_index_is_registered(self) -> None:
        """⛔ ~139 of the 166 indices in that file are G-Sec, bond, futures and strategy
        indices. Comparing an equity against `Nifty 10 yr Benchmark G-Sec` is a category
        error, and registering them would multiply the daily ingest for data nothing
        reads."""
        for _sym, name in REGISTERED:
            for bad in ("G-Sec", "G-sec", "Futures", "BHARAT Bond", "Arbitrage", "1D Rate"):
                assert bad not in name, f"{name} should not be registered"

    def test_every_symbol_is_unique(self) -> None:
        """The insert is `ON CONFLICT (symbol) DO NOTHING`, so a duplicate in this list
        would silently drop one of the two names rather than fail."""
        symbols = [s for s, _ in REGISTERED]
        assert len(symbols) == len(set(symbols))

    async def test_the_insert_is_idempotent_against_a_live_table(
        self, db: AsyncSession
    ) -> None:
        """The migration re-runs on every fresh database, and the 3 original indices are
        already present; `ON CONFLICT (symbol)` is what stops a second application
        duplicating them."""
        await db.execute(
            text(
                "INSERT INTO indices (symbol, name, exchange, is_active)"
                " VALUES ('NIFTYIT', 'Nifty IT', 'NSE', true)"
            )
        )
        await db.commit()
        before = (await db.execute(text("SELECT count(*) FROM indices"))).scalar()
        await db.execute(
            text(
                "INSERT INTO indices (symbol, name, exchange, is_active)"
                " VALUES ('NIFTYIT', 'Nifty IT', 'NSE', true)"
                " ON CONFLICT (symbol) DO NOTHING"
            )
        )
        await db.commit()
        assert (await db.execute(text("SELECT count(*) FROM indices"))).scalar() == before


class TestTheSectorIndicesAreNotYetUSED:
    """⛔⛔ THE HONEST LIMIT, and the reason this file exists.

    Registering 16 sector indices did **not** make sector-RS sector-relative.
    `benchmark_symbol_for` picks on two MEMBERSHIP FLAGS (`is_banknifty`, `is_finnifty`)
    and otherwise returns NIFTY50 — so for all but bank and financial names, "relative
    strength" is still measured against the broad market, exactly as before. The bars for
    the other 14 sector indices are ingested daily and read by nothing.

    Closing that gap is U8 step 4, which needs **U7's sector map** — and only **500 of
    3,395** stocks currently carry a sector. This test exists so nobody reads "sector
    indices registered" as "sector-RS works".
    """

    async def test_an_ordinary_stock_still_benchmarks_against_the_broad_market(
        self, db: AsyncSession
    ) -> None:
        pharma = await make_stock(db, symbol="SUNPHARMA", sector="Pharmaceuticals")
        db.add(Index(symbol="NIFTYPHARMA", name="Nifty Pharma", exchange="NSE", is_active=True))
        await db.commit()
        # A pharma name, with `Nifty Pharma` registered and ingested daily…
        assert (
            await db.execute(select(Index.symbol).where(Index.symbol == "NIFTYPHARMA"))
        ).scalar_one() == "NIFTYPHARMA"
        # …is STILL compared against the broad market.
        assert benchmark_symbol_for(pharma) == "NIFTY50"

    async def test_only_the_two_flagged_families_get_a_narrower_benchmark(
        self, db: AsyncSession
    ) -> None:
        bank = await make_stock(db, symbol="HDFCBANK", is_banknifty=True)
        fin = await make_stock(db, symbol="BAJFINANCE", is_finnifty=True)
        await db.commit()
        assert benchmark_symbol_for(bank) == "BANKNIFTY"
        assert benchmark_symbol_for(fin) == "FINNIFTY"
