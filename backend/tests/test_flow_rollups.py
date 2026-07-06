"""FII/DII flow rollups + generation wiring (Phase 2 slice 3).

Regression context: the §2.7 factor (weight 5) scored zero on every signal
ever generated — both generation paths passed the Decimal("0") defaults and
nothing aggregated fii_dii_daily / bulk_block_deals. These tests pin the
5-TRADING-day rollup (calendar-aware) and that the nightly path passes real
values through.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

from app.models.market_calendar import NseHoliday
from app.models.market_data import BulkBlockDeal, FiiDiiDaily
from app.services.fii_dii_service import (
    get_market_flow_5d,
    get_stock_block_deal_net_cr,
)
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock

GANDHI_2025 = date(2025, 10, 2)  # Thursday holiday
AS_OF = date(2025, 10, 6)  # Monday
# 5 trading days ending Mon Oct 6, skipping Gandhi (Oct 2) + weekend:
WINDOW = [date(2025, 9, 29), date(2025, 9, 30), date(2025, 10, 1), date(2025, 10, 3), AS_OF]
BEFORE_WINDOW = date(2025, 9, 26)  # Friday — must be excluded


def _flow(d: date, itype: str, seg: str, buy: str, sell: str) -> FiiDiiDaily:
    return FiiDiiDaily(
        trade_date=d,
        investor_type=itype,
        segment=seg,
        buy_value_cr=Decimal(buy),
        sell_value_cr=Decimal(sell),
    )


class TestMarketFlow5d:
    async def test_sums_cash_segment_over_trading_window(self, db: AsyncSession) -> None:
        db.add(NseHoliday(holiday_date=GANDHI_2025, name="Gandhi Jayanti", source="published"))
        # +500 net FII on each of the 5 window days
        for d in WINDOW:
            db.add(_flow(d, "FII", "cash", "1500", "1000"))
            db.add(_flow(d, "DII", "cash", "900", "1100"))  # −200/day
        # noise that must be EXCLUDED: outside window; futures segment
        db.add(_flow(BEFORE_WINDOW, "FII", "cash", "99999", "0"))
        db.add(_flow(AS_OF, "FII", "futures", "88888", "0"))
        await db.commit()

        fii, dii = await get_market_flow_5d(db, AS_OF)
        assert fii == Decimal("2500")
        assert dii == Decimal("-1000")

    async def test_empty_tables_give_zeros(self, db: AsyncSession) -> None:
        fii, dii = await get_market_flow_5d(db, AS_OF)
        assert fii == Decimal("0")
        assert dii == Decimal("0")


class TestStockBlockDealNet:
    async def test_nets_buys_minus_sells_in_crore(self, db: AsyncSession) -> None:
        stock = await make_stock(db, symbol="FLOWS1")
        other = await make_stock(db, symbol="FLOWS2")
        db.add(NseHoliday(holiday_date=GANDHI_2025, name="Gandhi Jayanti", source="published"))
        db.add(
            BulkBlockDeal(
                trade_date=WINDOW[0], stock_id=stock.id, deal_type="bulk",
                client_name="A", transaction="BUY", quantity=1_000_000,
                price=Decimal("150"), source="NSE",
            )
        )  # +₹15.00 Cr
        db.add(
            BulkBlockDeal(
                trade_date=WINDOW[3], stock_id=stock.id, deal_type="block",
                client_name="B", transaction="SELL", quantity=200_000,
                price=Decimal("145"), source="NSE",
            )
        )  # −₹2.90 Cr
        # excluded: other stock, and a huge deal before the window
        db.add(
            BulkBlockDeal(
                trade_date=WINDOW[0], stock_id=other.id, deal_type="bulk",
                client_name="C", transaction="BUY", quantity=9_999_999,
                price=Decimal("999"), source="NSE",
            )
        )
        db.add(
            BulkBlockDeal(
                trade_date=BEFORE_WINDOW, stock_id=stock.id, deal_type="bulk",
                client_name="D", transaction="BUY", quantity=9_999_999,
                price=Decimal("999"), source="NSE",
            )
        )
        await db.commit()

        net = await get_stock_block_deal_net_cr(db, stock.id, AS_OF)
        assert net == Decimal("12.10")  # 15.00 − 2.90, exact Decimal

    async def test_no_deals_is_zero(self, db: AsyncSession) -> None:
        stock = await make_stock(db, symbol="FLOWS3")
        assert await get_stock_block_deal_net_cr(db, stock.id, AS_OF) == Decimal("0.00")


class TestNightlyWiring:
    async def test_nightly_passes_real_flows_to_generation(
        self, db: AsyncSession, monkeypatch
    ) -> None:
        """The nightly loop must fetch the rollups and pass them through —
        the old code omitted the kwargs entirely (permanent zeros)."""
        import app.services.signal_service as svc

        await make_stock(db, symbol="FLOWS4")
        db.add(NseHoliday(holiday_date=GANDHI_2025, name="Gandhi Jayanti", source="published"))
        for d in WINDOW:
            db.add(_flow(d, "FII", "cash", "1000", "400"))  # +600/day → 3000
        await db.commit()

        seen: dict[str, Decimal] = {}

        async def spy(db_, stock, capital, risk_pct, timeframe="1d", **kwargs):
            seen.update(kwargs)
            return None

        monkeypatch.setattr(svc, "generate_signal_for_stock", spy)

        class _FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):  # noqa: ANN001, ANN206
                return datetime(2025, 10, 6, 13, 0, tzinfo=UTC if tz else None)

        monkeypatch.setattr(svc, "datetime", _FrozenDatetime)

        await svc.run_nightly_signal_generation(
            db, Decimal("500000"), Decimal("2"), "1d"
        )
        assert seen["fii_net_5d"] == Decimal("3000")
        assert seen["dii_net_5d"] == Decimal("0")
        assert "stock_block_deal_net_cr" in seen
