"""kite_instruments sync + stale sweep (2026-07-17).

Kite's instruments dump is the complete tradable universe for the kept
segments — a row missing from it is dead (delisted equity, moved
exchange, expired derivative). The upsert-only sync let those carcasses
accumulate and keep JOINing into the worker's subscription universe,
where every REST call against them failed `invalid token` (the 07-14/15
morning-repair failures: 16 stocks, 1,584 stale rows by 2026-07-17).

Real test Postgres; `build_kite` stubbed at the module seam (no Kite
calls). The sweep tests are stash-proven to FAIL on the pre-sweep code.
"""

from __future__ import annotations

from typing import Any

import app.broker.kite_client as kite_client
import pytest
from app.broker.kite_client import sync_instruments
from app.broker.tick_consumer import _build_token_stock_map
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock


def _row(token: int, symbol: str, exchange: str = "NSE", itype: str = "EQ") -> dict[str, Any]:
    """One raw dump row in the parsed-list shape kiteconnect returns."""
    return {
        "instrument_token": token,
        "exchange_token": token >> 8,
        "tradingsymbol": symbol,
        "exchange": exchange,
        "instrument_type": itype,
        "name": f"{symbol} Ltd",
        "last_price": 100.0,
        "tick_size": 0.05,
        "lot_size": 1,
        "segment": exchange,
        "expiry": "",
        "strike": 0,
    }


class _StubKC:
    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows

    def instruments(self) -> list[dict[str, Any]]:
        return self._rows


def _stub_dump(monkeypatch: pytest.MonkeyPatch, rows: list[dict[str, Any]]) -> None:
    monkeypatch.setattr(kite_client, "build_kite", lambda token: _StubKC(rows))


async def _tokens(db: AsyncSession) -> set[int]:
    rows = await db.execute(text("SELECT instrument_token FROM kite_instruments"))
    return {r[0] for r in rows}


class TestStaleSweep:
    async def test_sweep_removes_rows_absent_from_the_dump(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Token rotation: the same symbol reappears under a NEW
        instrument_token and the old row vanishes from the dump. The old
        row must be DELETED — upsert-only left it behind, and the
        symbol-join then carried both tokens (one dead) into the
        subscription universe."""
        _stub_dump(monkeypatch, [_row(101, "ROTATECO"), _row(201, "STAYCO")])
        await sync_instruments(db, "tok")
        assert await _tokens(db) == {101, 201}

        _stub_dump(monkeypatch, [_row(102, "ROTATECO"), _row(201, "STAYCO")])
        with caplog.at_level("INFO"):
            n = await sync_instruments(db, "tok")

        assert n == 2
        assert await _tokens(db) == {102, 201}  # 101 swept; old code kept it
        # the logged count comes from the DELETE's real rowcount
        assert "1 stale swept" in caplog.text

    async def test_sweep_skipped_on_partial_dump(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A truncated CSV must never mass-delete the table: below the
        _SWEEP_MIN_FRACTION tripwire the sweep is skipped loudly and the
        stale rows survive until a full dump arrives."""
        full = [_row(100 + i, f"BULKCO{i}") for i in range(10)]
        _stub_dump(monkeypatch, full)
        await sync_instruments(db, "tok")

        _stub_dump(monkeypatch, full[:2])  # 2 rows vs 10 in table → < 50%
        with caplog.at_level("WARNING"):
            n = await sync_instruments(db, "tok")

        assert n == 2
        assert len(await _tokens(db)) == 10  # nothing deleted
        assert "sweep SKIPPED" in caplog.text

    async def test_delisted_symbol_drops_out_of_the_worker_join(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Both sides of the seam: once a symbol leaves the dump, the
        worker's token_map join must stop producing it — no more doomed
        subscriptions / gap-fills / repairs for instruments Kite no
        longer lists (13 of the 16 failing stocks moved to BSE-only,
        3 delisted outright)."""
        gone = await make_stock(db, symbol="DELISTX")
        stays = await make_stock(db, symbol="ACTIVEX")

        _stub_dump(monkeypatch, [_row(11, "DELISTX"), _row(22, "ACTIVEX")])
        await sync_instruments(db, "tok")
        assert await _build_token_stock_map(db, "tok") == {11: gone.id, 22: stays.id}

        _stub_dump(monkeypatch, [_row(22, "ACTIVEX")])  # DELISTX left the dump
        await sync_instruments(db, "tok")

        assert await _build_token_stock_map(db, "tok") == {22: stays.id}

    async def test_hard_sweep_unwedges_the_fraction_guard(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """bug-hunter MEDIUM (2026-07-17): the single-tier guard counted
        the stale rows in its own denominator, so once stale ≥ live every
        future sync skipped the sweep FOREVER. Rows absent for
        ≥ _HARD_SWEEP_DAYS can't be explained by any truncated download —
        they are deleted BEFORE the guard computes its denominator, even
        on a run whose dump is too small for the young-stale sweep."""
        _stub_dump(monkeypatch, [_row(100 + i, f"WEDGE{i}") for i in range(10)])
        await sync_instruments(db, "tok")
        await db.execute(
            text(
                "UPDATE kite_instruments SET synced_at = synced_at - interval '10 days'"
                " WHERE instrument_token IN (100, 101)"
            )
        )

        _stub_dump(monkeypatch, [_row(102, "WEDGE2")])  # 1 row: young sweep must skip
        await sync_instruments(db, "tok")

        tokens = await _tokens(db)
        assert 100 not in tokens and 101 not in tokens  # hard-swept despite the skip
        assert tokens == set(range(102, 110))  # young stale survived the guard

    async def test_sweep_runs_at_exactly_half(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Boundary pin: the tripwire is a strict < — a dump exactly at
        _SWEEP_MIN_FRACTION of the table sweeps normally."""
        _stub_dump(monkeypatch, [_row(500 + i, f"HALFCO{i}") for i in range(4)])
        await sync_instruments(db, "tok")

        _stub_dump(monkeypatch, [_row(500, "HALFCO0"), _row(501, "HALFCO1")])  # 2 of 4
        await sync_instruments(db, "tok")

        assert await _tokens(db) == {500, 501}

    async def test_surviving_rows_are_refreshed_not_swept(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Rows present in consecutive dumps must survive the sweep with
        their fields refreshed (the watermark separates exactly the rows
        the dump did NOT contain)."""
        _stub_dump(monkeypatch, [_row(301, "HOLDCO")])
        await sync_instruments(db, "tok")
        first = (
            await db.execute(text("SELECT synced_at FROM kite_instruments"))
        ).scalar_one()

        rows = [_row(301, "HOLDCO")]
        rows[0]["last_price"] = 111.5
        _stub_dump(monkeypatch, rows)
        await sync_instruments(db, "tok")

        row = (
            await db.execute(
                text("SELECT synced_at, last_price FROM kite_instruments")
            )
        ).one()
        assert row[0] > first  # refreshed, not deleted
        assert float(row[1]) == 111.5
