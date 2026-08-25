"""CAS (Closing Auction Session) capture — Stage 1 (parse + upsert idempotency + window guard).

Covers: parsing the non-documented Kite /quote auction fields; the upsert that FREEZES the
pre-auction price on the first capture while converging the rest to the final auction print; and the
task's CAS-window self-guard."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from app.models.stock import CasDaily
from app.services import cas_capture as cc
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock

D = Decimal
TD = date(2026, 8, 25)


class TestParse:
    def test_full_auction_quote(self) -> None:
        p = cc.parse_cas({
            "last_price": 1317, "indicative_close_price": 1317.5,
            "total_imbalance_qty": -72596, "reference_limit_price": 1310.2,
        })
        assert p is not None
        assert p.last_price == D("1317") and p.indicative_close == D("1317.5")
        assert p.reference_price == D("1310.2") and p.total_imbalance_qty == -72596

    def test_pre_auction_zeros_preserved(self) -> None:
        # Before the auction populates (~15:21) the fields are 0 — kept, not dropped.
        p = cc.parse_cas({"last_price": 1312.7, "indicative_close_price": 0, "total_imbalance_qty": 0})  # noqa: E501
        assert p is not None
        assert p.indicative_close == D("0") and p.total_imbalance_qty == 0
        assert p.reference_price is None  # absent → None

    def test_no_last_price_is_unusable(self) -> None:
        assert cc.parse_cas({"indicative_close_price": 100}) is None
        assert cc.parse_cas(None) is None
        assert cc.parse_cas("nope") is None  # type: ignore[arg-type]

    def test_malformed_imbalance_falls_to_none(self) -> None:
        p = cc.parse_cas({"last_price": 100, "total_imbalance_qty": "x"})
        assert p is not None and p.total_imbalance_qty is None


class _FakeKite:
    def __init__(self, quotes: dict[str, Any]) -> None:
        self._quotes = quotes

    async def quote(self, batch: list[Any]) -> dict[str, Any]:
        return {k: self._quotes[k] for k in batch if k in self._quotes}


class TestCapture:
    async def test_upsert_freezes_pre_auction_and_converges(self, db: AsyncSession) -> None:
        stock = await make_stock(db, symbol="RELIANCE")
        await db.commit()
        smap = {"NSE:RELIANCE": stock.id}

        # 1) pre-auction poll (~15:15): indicative 0, imbalance 0.
        pre = _FakeKite({"NSE:RELIANCE": {
            "last_price": 1312.7, "indicative_close_price": 0,
            "total_imbalance_qty": 0, "reference_limit_price": 1310,
        }})
        assert await cc.capture_cas(db, pre, smap, trade_date=TD) == 1
        row = (await db.execute(select(CasDaily).where(CasDaily.stock_id == stock.id))).scalar_one()
        assert row.pre_auction_price == D("1312.7") and row.official_close == D("1312.7")
        assert row.indicative_close == D("0") and row.polls == 1

        # 2) post-execution poll (~15:31): auction cleared at 1317.
        post = _FakeKite({"NSE:RELIANCE": {
            "last_price": 1317, "indicative_close_price": 1317,
            "total_imbalance_qty": 0, "reference_limit_price": 1310,
        }})
        assert await cc.capture_cas(db, post, smap, trade_date=TD) == 1
        await db.refresh(row)
        assert row.pre_auction_price == D("1312.7")  # FROZEN — the 3:15 price, not the clear price
        assert row.official_close == D("1317") and row.indicative_close == D("1317")
        assert row.polls == 2  # incremented, one row (idempotent per (stock, date))

    async def test_imbalance_keeps_last_nonzero_not_post_match_zero(self, db: AsyncSession) -> None:
        # Regression (bug-hunter HIGH): a matched auction's final poll reports imbalance 0; that
        # post-execution 0 must NOT clobber the meaningful mid-auction imbalance (the Stage-2
        # predictor). Replays the real HDFCBANK shape: pre-auction 0 → mid −68132 → post-match 0.
        stock = await make_stock(db, symbol="HDFCBANK")
        await db.commit()
        smap = {"NSE:HDFCBANK": stock.id}
        q = lambda last, ind, imb: _FakeKite({  # noqa: E731
            "NSE:HDFCBANK": {"last_price": last, "indicative_close_price": ind,
                             "total_imbalance_qty": imb}})
        await cc.capture_cas(db, q(724, 0, 0), smap, trade_date=TD)          # pre-auction
        await cc.capture_cas(db, q(724, 727, -68132), smap, trade_date=TD)   # mid-auction
        await cc.capture_cas(db, q(727.5, 727.5, 0), smap, trade_date=TD)    # post-match (cleared)
        row = (await db.execute(select(CasDaily).where(CasDaily.stock_id == stock.id))).scalar_one()
        assert row.total_imbalance_qty == -68132  # last NON-ZERO, not the post-match 0
        assert row.official_close == D("727.5") and row.polls == 3

    async def test_skips_symbols_without_a_usable_quote(self, db: AsyncSession) -> None:
        s1 = await make_stock(db, symbol="AAA")
        s2 = await make_stock(db, symbol="BBB")
        await db.commit()
        smap = {"NSE:AAA": s1.id, "NSE:BBB": s2.id}
        kite = _FakeKite({"NSE:AAA": {"last_price": 100, "indicative_close_price": 101,
                                      "total_imbalance_qty": 5}})  # BBB missing from the response
        assert await cc.capture_cas(db, kite, smap, trade_date=TD) == 1
        rows = (await db.execute(select(CasDaily))).scalars().all()
        assert {r.stock_id for r in rows} == {s1.id}


class TestWindowGuard:
    def test_cas_window_bounds(self) -> None:
        from datetime import time

        from app.tasks import cas_tasks
        assert cas_tasks._CAS_START == time(15, 15) and cas_tasks._CAS_END == time(15, 33)
        # _within_cas_window reads the wall clock; just assert it returns a bool without raising.
        assert isinstance(cas_tasks._within_cas_window(), bool)
