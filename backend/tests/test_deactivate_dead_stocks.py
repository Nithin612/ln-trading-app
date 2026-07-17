"""deactivate_dead_stocks.py — the (a)+(c) universe ruling (2026-07-17).

Real test Postgres. The load-bearing assertion is the T2T canary: a
stock whose ONLY listing is a series-suffixed NSE row (SYMBOL-BE) must
NOT be deactivated — ruling (a) keeps surveillance-series stocks active
in the master (EOD flows) while the live join excludes them naturally.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from deactivate_dead_stocks import deactivate_dead_stocks  # noqa: E402


async def _instrument(
    db: AsyncSession,
    token: int,
    symbol: str,
    exchange: str = "NSE",
    segment: str = "NSE",
    itype: str = "EQ",
) -> None:
    await db.execute(
        text(
            "INSERT INTO kite_instruments (instrument_token, exchange_token,"
            " tradingsymbol, exchange, instrument_type, name, last_price,"
            " tick_size, lot_size, segment, expiry, strike, synced_at)"
            " VALUES (:t, :et, :sym, :ex, :it, :nm, 100, 0.05, 1, :seg, '', 0, :ts)"
        ),
        {
            "t": token, "et": token >> 8, "sym": symbol, "ex": exchange,
            "it": itype, "nm": f"{symbol} Ltd", "seg": segment,
            "ts": datetime.now(UTC),
        },
    )


async def _is_active(db: AsyncSession, stock_id: int) -> bool:
    return bool(
        (
            await db.execute(
                text("SELECT is_active FROM stocks WHERE id = :sid"), {"sid": stock_id}
            )
        ).scalar_one()
    )


async def _forensic_reasons(db: AsyncSession) -> dict[str, str]:
    rows = await db.execute(text("SELECT symbol, reason FROM forensic_stocks_deactivated"))
    return dict(rows.all())


class TestDeactivateDeadStocks:
    async def test_classification_and_t2t_canary(
        self, db: AsyncSession, monkeypatch: Any
    ) -> None:
        """Four stocks, four fates: dead → deactivated; BSE-mover →
        deactivated (separate reason); healthy EQ → untouched; T2T
        (suffixed-only listing) → UNTOUCHED (ruling (a))."""
        await db.execute(text("DROP TABLE IF EXISTS forensic_stocks_deactivated"))
        dead = await make_stock(db, symbol="DEADCO")
        moved = await make_stock(db, symbol="MOVEDCO")
        healthy = await make_stock(db, symbol="HEALTHCO")
        t2t = await make_stock(db, symbol="WATCHCO")
        await _instrument(db, 11, "MOVEDCO", exchange="BSE", segment="BSE")
        await _instrument(db, 22, "HEALTHCO")
        await _instrument(db, 33, "WATCHCO-BE")  # T2T series listing only

        counts = await deactivate_dead_stocks(db, dry_run=False)

        assert counts == {"dead_no_listing": 1, "moved_bse_only": 1}
        assert not await _is_active(db, dead.id)
        assert not await _is_active(db, moved.id)
        assert await _is_active(db, healthy.id)
        assert await _is_active(db, t2t.id)  # THE canary: T2T stays active
        assert await _forensic_reasons(db) == {
            "DEADCO": "dead_no_listing",
            "MOVEDCO": "moved_bse_only",
        }

    async def test_index_row_is_not_a_listing(self, db: AsyncSession) -> None:
        """A segment='INDICES' row sharing the symbol must not keep a
        master row alive (the NIFTYNXT50-style ghost)."""
        await db.execute(text("DROP TABLE IF EXISTS forensic_stocks_deactivated"))
        ghost = await make_stock(db, symbol="IDXGHOST")
        await _instrument(db, 44, "IDXGHOST", segment="INDICES")

        counts = await deactivate_dead_stocks(db, dry_run=False)

        assert counts == {"dead_no_listing": 1}
        assert not await _is_active(db, ghost.id)

    async def test_bse_index_row_does_not_flip_the_reason(self, db: AsyncSession) -> None:
        """The reason drives group-wise REVERSAL, so mislabels matter: a
        BSE row with segment='INDICES' sharing a dead stock's symbol must
        not flip dead_no_listing → moved_bse_only (bug-hunter mutant C —
        the reason-CASE's INDICES exclusion was unpinned)."""
        await db.execute(text("DROP TABLE IF EXISTS forensic_stocks_deactivated"))
        dead = await make_stock(db, symbol="IDXREASON")
        await _instrument(db, 55, "IDXREASON", exchange="BSE", segment="INDICES")

        counts = await deactivate_dead_stocks(db, dry_run=False)

        assert counts == {"dead_no_listing": 1}
        assert not await _is_active(db, dead.id)
        assert await _forensic_reasons(db) == {"IDXREASON": "dead_no_listing"}

    async def test_dry_run_writes_nothing(self, db: AsyncSession) -> None:
        await db.execute(text("DROP TABLE IF EXISTS forensic_stocks_deactivated"))
        dead = await make_stock(db, symbol="DRYCO")

        counts = await deactivate_dead_stocks(db, dry_run=True)

        assert counts == {"dead_no_listing": 1}
        assert await _is_active(db, dead.id)  # untouched
        exists = (
            await db.execute(
                text(
                    "SELECT count(*) FROM information_schema.tables"
                    " WHERE table_name = 'forensic_stocks_deactivated'"
                )
            )
        ).scalar_one()
        assert exists == 0  # no forensic table minted on dry-run

    async def test_second_run_is_idempotent(self, db: AsyncSession) -> None:
        await db.execute(text("DROP TABLE IF EXISTS forensic_stocks_deactivated"))
        await make_stock(db, symbol="ONCECO")

        first = await deactivate_dead_stocks(db, dry_run=False)
        second = await deactivate_dead_stocks(db, dry_run=False)

        assert first == {"dead_no_listing": 1}
        assert second == {}  # nothing active left to match
        n = (
            await db.execute(text("SELECT count(*) FROM forensic_stocks_deactivated"))
        ).scalar_one()
        assert n == 1  # no duplicate forensic rows
