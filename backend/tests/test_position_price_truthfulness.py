"""V2 — a position's mark carries its provenance (2026-09-14).

⛔ THE DEFECT. `PositionsPage` renders `current_price`, and PART XVIII claimed an
unpriced position shows a bare `—`. Measured in round 4, the truth is worse:
`get_current_price` falls through **live tick → last COMPLETE 1m bar → DAILY CLOSE**, so
`current_price` almost never goes null. A position whose feed died rendered a plausible
number from a previous session **with nothing marking it**. An em-dash at least signals
absence; a stale close signals nothing and looks live.

⚠ `stranded` is a DIFFERENT condition, not a worse staleness: no tradable EQ instrument
exists, so the position cannot be priced or exited through the live path at all and needs
a human. It gets its own flag because it needs its own copy.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.broker import paper_broker as pb
from app.models.market_data import Ohlcv1m, OhlcvDaily
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock

NOW = datetime(2026, 9, 14, 6, 0, tzinfo=UTC)


async def _minute_bar(db: AsyncSession, stock_id: int, close: str) -> None:
    db.add(
        Ohlcv1m(
            time=NOW - timedelta(minutes=5), stock_id=stock_id,
            open=Decimal(close), high=Decimal(close), low=Decimal(close),
            close=Decimal(close), volume=100, is_complete=True,
        )
    )


async def _daily_bar(db: AsyncSession, stock_id: int, close: str) -> None:
    db.add(
        OhlcvDaily(
            time=NOW - timedelta(days=1), stock_id=stock_id,
            open=Decimal(close), high=Decimal(close), low=Decimal(close),
            close=Decimal(close), volume=1000, is_complete=True,
        )
    )


class TestProvenanceIsReported:
    async def test_a_minute_bar_is_reported_as_minute(self, db: AsyncSession) -> None:
        s = await make_stock(db, symbol="MINCO")
        await _minute_bar(db, s.id, "101.50")
        await _daily_bar(db, s.id, "99.00")
        await db.commit()

        price, source = await pb.stored_price_with_source(db, s.id)

        assert price == Decimal("101.50")
        assert source == pb.PRICE_MINUTE, "the 1m bar is fresher and must win"

    async def test_a_daily_close_is_reported_as_daily(self, db: AsyncSession) -> None:
        """⭐ THE CANARY. This is the case that used to render a day-old close as
        though it were a live quote."""
        s = await make_stock(db, symbol="DAYCO")
        await _daily_bar(db, s.id, "99.00")
        await db.commit()

        price, source = await pb.stored_price_with_source(db, s.id)

        assert price == Decimal("99.00")
        assert source == pb.PRICE_DAILY

    async def test_no_data_at_all_is_reported_as_none(self, db: AsyncSession) -> None:
        s = await make_stock(db, symbol="NODATA")
        await db.commit()

        assert await pb.stored_price_with_source(db, s.id) == (None, pb.PRICE_NONE)

    async def test_the_four_states_are_distinct(self) -> None:
        """Four rungs, four names — collapsing any two is how the defect happened."""
        states = {pb.PRICE_LIVE, pb.PRICE_MINUTE, pb.PRICE_DAILY, pb.PRICE_NONE}
        assert len(states) == 4


class TestTheOldChainIsUnchanged:
    """`get_current_price` now DELEGATES to the sourced variant, so there is exactly one
    fallback chain. Its behaviour must be byte-identical or every money-path caller
    silently changed."""

    async def test_it_still_prefers_the_minute_bar(self, db: AsyncSession) -> None:
        s = await make_stock(db, symbol="SAMEMIN")
        await _minute_bar(db, s.id, "101.50")
        await _daily_bar(db, s.id, "99.00")
        await db.commit()

        assert await pb.get_current_price(db, s.id) == Decimal("101.50")

    async def test_it_still_falls_back_to_daily(self, db: AsyncSession) -> None:
        s = await make_stock(db, symbol="SAMEDAY")
        await _daily_bar(db, s.id, "99.00")
        await db.commit()

        assert await pb.get_current_price(db, s.id) == Decimal("99.00")

    async def test_it_still_returns_none_with_nothing_stored(
        self, db: AsyncSession
    ) -> None:
        s = await make_stock(db, symbol="SAMENONE")
        await db.commit()
        assert await pb.get_current_price(db, s.id) is None

    async def test_it_agrees_with_the_sourced_variant_on_the_price(
        self, db: AsyncSession
    ) -> None:
        """The two must not drift: same chain, same answer."""
        s = await make_stock(db, symbol="AGREE")
        await _minute_bar(db, s.id, "77.25")
        await db.commit()

        plain = await pb.get_current_price(db, s.id)
        sourced, _ = await pb.stored_price_with_source(db, s.id)
        assert plain == sourced


class TestTheEnricherStamps:
    def test_a_price_from_a_daily_close_is_marked_daily(self) -> None:
        from app.api.v1.trading import _enrich_position
        from app.models.trading import Position

        pos = Position(
            id="x", user_id=1, stock_id=1, mode="paper", side="LONG", quantity=1,
            avg_entry_price=Decimal("100"), trail_state="none", realized_pnl=Decimal("0"),
            opened_at=NOW,
        )
        out = _enrich_position(
            pos, "DAYCO", Decimal("99"), None, price_state=pb.PRICE_DAILY
        )
        assert out.price_state == pb.PRICE_DAILY
        assert out.stranded is False

    def test_a_missing_price_is_none_regardless_of_what_was_passed(self) -> None:
        """Defensive: a caller that forgets the state must UNDERSTATE freshness, never
        overstate it."""
        from app.api.v1.trading import _enrich_position
        from app.models.trading import Position

        pos = Position(
            id="y", user_id=1, stock_id=1, mode="paper", side="LONG", quantity=1,
            avg_entry_price=Decimal("100"), trail_state="none", realized_pnl=Decimal("0"),
            opened_at=NOW,
        )
        out = _enrich_position(pos, "NOCO", None, None, price_state=pb.PRICE_LIVE)
        assert out.price_state == pb.PRICE_NONE

    def test_stranded_is_carried_through(self) -> None:
        from app.api.v1.trading import _enrich_position
        from app.models.trading import Position

        pos = Position(
            id="z", user_id=1, stock_id=1, mode="paper", side="LONG", quantity=1,
            avg_entry_price=Decimal("100"), trail_state="none", realized_pnl=Decimal("0"),
            opened_at=NOW,
        )
        out = _enrich_position(pos, "GHOST", Decimal("50"), None, stranded=True)
        assert out.stranded is True

    def test_the_default_is_the_safe_one(self) -> None:
        """An un-stamped position reads `none`, not `live`."""
        from app.schemas.trading import PositionOut

        assert PositionOut.model_fields["price_state"].default == pb.PRICE_NONE
        assert PositionOut.model_fields["stranded"].default is False


class TestTheWireVocabularyMatchesTheBroker:
    """W5 — there is now exactly ONE declaration: `PriceSource` in `app.schemas.trading`,
    with the broker's `PRICE_*` constants ANNOTATED by it, so mypy refuses a value the API
    cannot serialise. This test is the cheaper second line: it asserts the constant SET and
    the Literal's members are the same, which catches a constant added without widening the
    type (or removed and left behind) in a plain `pytest` run, without waiting for mypy.

    It derives both sides from the declarations rather than restating either — the
    `test_enum_exhaustiveness` idiom — so it breaks when the vocabulary grows, which is the
    only way this class of test earns its keep."""

    def test_every_broker_constant_is_serialisable(self) -> None:
        from typing import get_args

        from app.broker import paper_broker as pb
        from app.schemas.trading import PriceSource

        declared = {
            v for k, v in vars(pb).items() if k.startswith("PRICE_") and isinstance(v, str)
        }
        assert declared, "no PRICE_* constants found — has the naming convention changed?"
        assert declared == set(get_args(PriceSource)), (
            f"broker declares {sorted(declared)} but the wire accepts "
            f"{sorted(get_args(PriceSource))} — widen both together, or the API serves a "
            "value no client can render"
        )

    def test_the_default_is_the_absence_case(self) -> None:
        """A row that never had its price resolved must not claim a live tick."""
        from app.broker.paper_broker import PRICE_NONE
        from app.schemas.trading import PositionOut

        assert PositionOut.model_fields["price_state"].default == PRICE_NONE
