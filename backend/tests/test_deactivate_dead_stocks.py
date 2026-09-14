"""The (a)+(c) universe ruling of 2026-07-17, now enforced by the RULE.

⛔ `deactivate_dead_stocks.py` was RETIRED on 2026-09-14 (D2′b): it was the repository's
only `UPDATE stocks SET is_active`, and that job now belongs to the universe rule's
`KITE_TRADABLE` term, evaluated nightly and applied by a single writer.

⭐ **Retiring a script does not retire the behaviour it guarded.** Its dry-run and
idempotence tests died with it — they tested script mechanics — but the two BEHAVIOURAL
cases it pinned are re-asserted here against the rule that replaced it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.models.broker import KiteInstrument
from app.services.universe_materialiser import load_inputs
from app.services.universe_rule import REASON_NOT_KITE_TRADABLE, evaluate
from sqlalchemy.ext.asyncio import AsyncSession

HEADER = (
    "SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE,"
    " MARKET LOT, ISIN NUMBER, FACE VALUE\n"
)


def _csv(*symbols: str) -> str:
    return HEADER + "".join(
        f"{s},{s} Ltd,EQ,01-JAN-2000,10,1,INE000A0{i:04d},10\n"
        for i, s in enumerate(symbols)
    )


async def _instrument(
    db: AsyncSession, token: int, symbol: str, *, segment: str = "NSE"
) -> None:
    db.add(
        KiteInstrument(
            instrument_token=token,
            exchange_token=token >> 8,
            tradingsymbol=symbol,
            exchange="NSE",
            instrument_type="EQ",
            name=symbol,
            last_price=Decimal("100"),
            tick_size=Decimal("0.05"),
            lot_size=1,
            segment=segment,
            expiry="",
            strike=Decimal("0"),
            synced_at=datetime.now(tz=UTC),
        )
    )


class TestTheIndexGhost:
    """⚠ REGRESSION, and a latent defect this file caught on the day it was rewritten.

    Measured 2026-09-14: **212 `kite_instruments` rows with `segment='INDICES'` carry
    `instrument_type='EQ'`** — an index can present itself as a tradable equity. The
    retired script excluded `segment='INDICES'` explicitly; the first version of the
    universe rule did not, and was saved only by its OTHER term (an index name is not
    in `EQUITY_L`). A term that depends on a different term to be correct is how a
    latent defect waits for a coincidence.
    """

    async def test_an_index_row_does_not_make_a_symbol_tradable(
        self, db: AsyncSession
    ) -> None:
        await _instrument(db, 7001, "GHOSTIDX", segment="INDICES")
        await db.commit()

        inputs = await load_inputs(db, csv_text=_csv("GHOSTIDX"))

        assert "GHOSTIDX" not in inputs.kite_tradable
        assert evaluate("GHOSTIDX", inputs) == (False, REASON_NOT_KITE_TRADABLE)

    async def test_a_real_equity_row_still_counts(self, db: AsyncSession) -> None:
        await _instrument(db, 7002, "REALEQ", segment="NSE")
        await db.commit()

        inputs = await load_inputs(db, csv_text=_csv("REALEQ"))

        assert "REALEQ" in inputs.kite_tradable
        assert evaluate("REALEQ", inputs)[0] is True

    async def test_a_symbol_with_both_rows_is_tradable(self, db: AsyncSession) -> None:
        """The exclusion must remove the ghost, not the company behind it."""
        await _instrument(db, 7003, "BOTHROWS", segment="NSE")
        await _instrument(db, 7004, "BOTHROWS", segment="INDICES")
        await db.commit()

        inputs = await load_inputs(db, csv_text=_csv("BOTHROWS"))

        assert "BOTHROWS" in inputs.kite_tradable


class TestTheT2TRuling:
    """Ruling (a), 2026-07-17: `BE`/`BZ` names are excluded from LIVE SCANNING. Under
    D2′b that is the rule's `EQ_LISTED` term rather than a script's judgement — and it
    is why 139 of the 152 deactivated on 2026-09-14 were `BE` series."""

    async def test_a_be_series_name_is_not_in_the_universe(
        self, db: AsyncSession
    ) -> None:
        await _instrument(db, 7005, "T2TNAME", segment="NSE")
        await db.commit()

        csv_text = HEADER + "T2TNAME,T2t Ltd,BE,01-JAN-2000,10,1,INE111A01011,10\n"
        inputs = await load_inputs(db, csv_text=csv_text)

        assert "T2TNAME" not in inputs.eq_listed
        assert evaluate("T2TNAME", inputs)[0] is False

    async def test_the_same_name_in_eq_series_is(self, db: AsyncSession) -> None:
        await _instrument(db, 7006, "EQNAME", segment="NSE")
        await db.commit()

        inputs = await load_inputs(db, csv_text=_csv("EQNAME"))

        assert evaluate("EQNAME", inputs)[0] is True


class TestTheScriptIsRetired:
    def test_it_refuses_to_run_and_says_where_the_logic_went(self) -> None:
        """A tombstone that redirects beats a deleted file: someone who remembers the
        script finds it and learns what replaced it."""
        import subprocess
        import sys
        from pathlib import Path

        script = Path(__file__).resolve().parents[1] / "scripts" / "deactivate_dead_stocks.py"
        proc = subprocess.run(
            [sys.executable, str(script)], capture_output=True, text=True, timeout=60
        )

        assert proc.returncode != 0
        assert "RETIRED" in proc.stderr
        assert "universe_snapshot.py" in proc.stderr
