"""Historical `ohlcv_1d` backfill — the survivorship-safety contract.

The assertions that matter are the ones stopping a multi-year backfill from quietly
reconstructing a **survivor-only** universe:

- an unknown symbol in `historical` mode becomes a stock, so a company that has since
  delisted still gets its bars — this is the whole point of the mode;
- it is created **inactive**, so it can never reach live scanning or sizing;
- an existing ACTIVE stock is never touched, in either direction;
- the DEFAULT (daily-ingestion) path is unchanged and still skips unknown and inactive
  names, because the T2T ruling says deactivated names get no EOD bars.
"""

from __future__ import annotations

import importlib.util as _ilu
import sys as _sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path as _Path

from app.models.stock import Stock
from app.services import bhavcopy_service as bs
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock


def _load_backfill_module():  # noqa: D103 — scripts/ is not an importable package
    path = _Path(__file__).resolve().parents[1] / "scripts" / "backfill_ohlcv_history.py"
    spec = _ilu.spec_from_file_location("backfill_ohlcv_history", path)
    assert spec and spec.loader
    mod = _ilu.module_from_spec(spec)
    _sys.modules["backfill_ohlcv_history"] = mod
    spec.loader.exec_module(mod)
    return mod


bhf = _load_backfill_module()


_DAY = date(2020, 3, 23)  # the COVID low — a date only the backfill can reach


def _row(symbol: str, *, close: str = "100.00", d: date = _DAY) -> bs.BhavRow:
    return bs.BhavRow(
        symbol=symbol,
        trade_date=d,
        open=Decimal("99.00"),
        high=Decimal("101.00"),
        low=Decimal("98.00"),
        close=Decimal(close),
        volume=12345,
    )


async def _bars_for(db: AsyncSession, stock_id: int) -> int:
    return int(
        (
            await db.execute(
                text("SELECT count(*) FROM ohlcv_1d WHERE stock_id = :sid"),
                {"sid": stock_id},
            )
        ).scalar_one()
    )


class TestSurvivorshipSafety:
    async def test_unknown_symbol_gets_a_stock_and_its_bars(self, db: AsyncSession) -> None:
        """⭐ The point of the mode. A name that traded in 2020 and has since delisted is
        absent from our Kite-derived `stocks` snapshot; without this it would vanish from
        history and the reconstructed universe would contain only survivors."""
        inserted, _ = await bs.upsert_bhavcopy_rows(db, [_row("DELISTEDCO")], historical=True)
        assert inserted == 1

        stock = (
            await db.execute(select(Stock).where(Stock.symbol == "DELISTEDCO"))
        ).scalar_one()
        assert await _bars_for(db, stock.id) == 1

    async def test_created_stock_is_inactive(self, db: AsyncSession) -> None:
        """It is not tradeable today. An active row would leak a dead company into live
        scanning, sizing and signal generation."""
        await bs.upsert_bhavcopy_rows(db, [_row("GONECO")], historical=True)
        stock = (
            await db.execute(select(Stock).where(Stock.symbol == "GONECO"))
        ).scalar_one()
        assert stock.is_active is False

    async def test_existing_active_stock_is_never_deactivated(
        self, db: AsyncSession
    ) -> None:
        """⭐ The backfill can only ADD names. If it could flip an existing row it would
        silently disable a live stock halfway through a 7-year run."""
        live = await make_stock(db, symbol="LIVECO", is_active=True)
        await bs.upsert_bhavcopy_rows(db, [_row("LIVECO")], historical=True)

        await db.refresh(live)
        assert live.is_active is True
        assert live.company_name == "Test Company Ltd", "name must not be overwritten"

    async def test_inactive_stock_receives_bars_in_historical_mode(
        self, db: AsyncSession
    ) -> None:
        dead = await make_stock(db, symbol="DEADCO", is_active=False)
        inserted, _ = await bs.upsert_bhavcopy_rows(db, [_row("DEADCO")], historical=True)
        assert inserted == 1
        assert await _bars_for(db, dead.id) == 1


class TestDailyPathIsTradeabilityBlind:
    """D3 (2026-09-14) — the price archive never consults a trading decision.

    ⛔ REVERSED DELIBERATELY. This class previously asserted
    `test_inactive_stock_gets_no_bars` with the docstring *"The T2T ruling: a
    deactivated name gets no EOD bars on the live path."* That coupling is what
    let a SELECTION mistake destroy PRICE HISTORY: between 2026-09-07 and 09-12
    the real universe was wrongly `is_active = false` and 1,481 names lost five
    sessions of bars, silently.

    It also made the repair non-durable. U3 refilled the hole in `historical`
    mode on 09-13, but `eod_catchup.py:102` calls the DEFAULT path — so the next
    EOD run would have written ~1,170 names instead of ~2,640 and reopened the
    hole the following day.

    ⚠ The T2T ruling is not overturned: it is a TRADING policy and the scanner
    still enforces it (`resolve_universe` filters `is_active` itself). It was
    never implementable here anyway — `parse_bhavcopy_csv` keeps `EQ` series
    only, so a name that MOVES to `BE` stops appearing in what we ingest
    regardless of any flag. See PART XIII of the universe plan.
    """

    async def test_unknown_symbol_is_still_skipped_not_created(
        self, db: AsyncSession
    ) -> None:
        """Unchanged, and the line D3 does NOT cross: recording a bar is
        bookkeeping, but MINTING an instrument is a universe decision. Creating
        rows stays a `historical=True` behaviour."""
        inserted, skipped = await bs.upsert_bhavcopy_rows(db, [_row("NEVERHEARDOF")])
        assert (inserted, skipped) == (0, 1)
        assert (
            await db.execute(select(Stock).where(Stock.symbol == "NEVERHEARDOF"))
        ).scalar_one_or_none() is None

    async def test_an_inactive_stock_now_receives_bars(self, db: AsyncSession) -> None:
        """The regression canary: on the old code this was (0, 1) and 0 bars."""
        dead = await make_stock(db, symbol="T2TCO", is_active=False)
        inserted, skipped = await bs.upsert_bhavcopy_rows(db, [_row("T2TCO")])
        assert (inserted, skipped) == (1, 0)
        assert await _bars_for(db, dead.id) == 1

    async def test_active_stock_still_ingests(self, db: AsyncSession) -> None:
        live = await make_stock(db, symbol="ACTIVECO", is_active=True)
        inserted, _ = await bs.upsert_bhavcopy_rows(db, [_row("ACTIVECO")])
        assert inserted == 1
        assert await _bars_for(db, live.id) == 1

    async def test_a_mixed_bhavcopy_ingests_both(self, db: AsyncSession) -> None:
        """The shape of a real session: the archive records what TRADED, and the
        active flag no longer partitions it."""
        live = await make_stock(db, symbol="MIXLIVE", is_active=True)
        dead = await make_stock(db, symbol="MIXDEAD", is_active=False)
        inserted, skipped = await bs.upsert_bhavcopy_rows(
            db, [_row("MIXLIVE"), _row("MIXDEAD")]
        )
        assert (inserted, skipped) == (2, 0)  # old code: (1, 1)
        assert await _bars_for(db, live.id) == 1
        assert await _bars_for(db, dead.id) == 1

    async def test_the_daily_and_historical_paths_now_agree_on_a_known_symbol(
        self, db: AsyncSession
    ) -> None:
        """Both modes attach bars to a known name; they differ only on UNKNOWN
        ones. Pinning that keeps the two from drifting apart again."""
        a = await make_stock(db, symbol="AGREEA", is_active=False)
        b = await make_stock(db, symbol="AGREEB", is_active=False)
        daily, _ = await bs.upsert_bhavcopy_rows(db, [_row("AGREEA")])
        hist, _ = await bs.upsert_bhavcopy_rows(db, [_row("AGREEB")], historical=True)
        assert daily == hist == 1
        assert await _bars_for(db, a.id) == await _bars_for(db, b.id) == 1


class TestIdempotence:
    async def test_rerunning_the_same_day_inserts_nothing(self, db: AsyncSession) -> None:
        """A 950-day run gets interrupted. Re-running must be free, not duplicated."""
        rows = [_row("REPEATCO")]
        first, _ = await bs.upsert_bhavcopy_rows(db, rows, historical=True)
        second, skipped = await bs.upsert_bhavcopy_rows(db, rows, historical=True)

        assert first == 1
        assert second == 0, "ON CONFLICT DO NOTHING"
        assert skipped == 1

        stock = (
            await db.execute(select(Stock).where(Stock.symbol == "REPEATCO"))
        ).scalar_one()
        assert await _bars_for(db, stock.id) == 1

    async def test_existing_bar_is_not_overwritten(self, db: AsyncSession) -> None:
        """Today's ingested data must survive a backfill that overlaps it — the run is
        bounded by date, but a mis-typed --end must not rewrite live bars."""
        live = await make_stock(db, symbol="KEEPCO")
        await db.execute(
            text(
                "INSERT INTO ohlcv_1d (time, stock_id, open, high, low, close, volume,"
                " is_complete) VALUES (:t, :sid, 1, 1, 1, :c, 1, true)"
            ),
            {
                "t": datetime(_DAY.year, _DAY.month, _DAY.day, tzinfo=UTC),
                "sid": live.id,
                "c": Decimal("777.00"),
            },
        )
        await db.commit()

        await bs.upsert_bhavcopy_rows(db, [_row("KEEPCO", close="100.00")], historical=True)

        close = (
            await db.execute(
                text("SELECT close FROM ohlcv_1d WHERE stock_id = :sid"), {"sid": live.id}
            )
        ).scalar_one()
        assert Decimal(str(close)) == Decimal("777.0000"), "the pre-existing bar wins"


class TestBatching:
    async def test_more_rows_than_one_chunk(self, db: AsyncSession) -> None:
        """The insert is chunked; a run spanning a chunk boundary must not lose or
        duplicate rows. A real bhavcopy day is ~2,300 rows against a 500 chunk."""
        n = bs._CHUNK + 7
        rows = [_row(f"BULK{i:04d}") for i in range(n)]
        inserted, skipped = await bs.upsert_bhavcopy_rows(db, rows, historical=True)

        assert inserted == n
        assert skipped == 0
        total = int(
            (
                await db.execute(
                    text(
                        "SELECT count(*) FROM ohlcv_1d o JOIN stocks s ON s.id = o.stock_id"
                        " WHERE s.symbol LIKE 'BULK%'"
                    )
                )
            ).scalar_one()
        )
        assert total == n

    async def test_mixed_known_and_unknown_counts_correctly(
        self, db: AsyncSession
    ) -> None:
        await make_stock(db, symbol="KNOWNCO")
        inserted, skipped = await bs.upsert_bhavcopy_rows(
            db, [_row("KNOWNCO"), _row("UNKNOWNCO")], historical=False
        )
        assert (inserted, skipped) == (1, 1)


class TestSaturdaySessionsAreReachable:
    """⛔ REGRESSION (2026-09-17). `_weekdays` enumerated Mon-Fri, so NSE's Saturday
    special sessions — budget days and DR-site tests, on which the market genuinely
    trades — were structurally unreachable: the request was never made.

    Measured when this was found: `ohlcv_1d` was missing **3 of 6** special sessions
    (2024-03-02, 2025-02-01, 2026-02-01) while `ohlcv_5m` held 4,242-15,600 rows on the
    same dates. All three serve from the archive today.

    ⚠ The canary is the SATURDAY, not the count: enumerating Mon-Sat is only correct
    because a non-session 404s, which is the same path a weekday holiday takes.
    """

    def test_a_known_saturday_session_is_enumerated(self) -> None:
        """2025-02-01 was a real NSE session (Union Budget). On the old code this
        returned an empty list and the date could never be fetched."""
        sat = date(2025, 2, 1)
        assert sat.weekday() == 5, "fixture date must be a Saturday"
        assert bhf._candidate_days(sat, sat) == [sat]

    def test_sunday_is_enumerated_because_nse_has_traded_on_one(self) -> None:
        """⛔⛔ The first version of this fix excluded Sunday on the stated ground that
        'NSE has never held one'. **2026-02-01 is a Sunday on which NSE traded** (Budget
        day) — `ohlcv_5m` holds 15,675 rows for it and the archive serves the bhavcopy.
        Excluding Sunday reproduced the defect being fixed, one weekday over."""
        sun = date(2026, 2, 1)
        assert sun.weekday() == 6, "fixture date must be a Sunday"
        assert bhf._candidate_days(sun, sun) == [sun]

    def test_the_enumerator_asserts_nothing_about_which_days_are_sessions(self) -> None:
        """⭐ THE CONTRACT: offer every calendar day and let the archive's 404 decide.
        Any weekday filter is a claim about a calendar this code does not own, and both
        such claims made here have been wrong."""
        mon = date(2025, 1, 27)
        assert mon.weekday() == 0
        got = bhf._candidate_days(mon, mon + timedelta(days=6))
        assert len(got) == 7
        assert {d.weekday() for d in got} == set(range(7))
