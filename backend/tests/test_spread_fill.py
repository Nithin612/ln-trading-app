"""Phase 6.8.2 — spread-aware slippage & impact model.

Flat 2 bps is an adequate model for a Nifty large-cap whose book is a tick wide,
and a lie for a small-cap whose spread is 50–100 bps. Every paper fill on an
illiquid name was overstating our edge — and that record is the Phase-7 go-live
gate, so the honesty of these numbers matters more than their convenience.

Covers: the bps model (half-spread + size impact, floor, caps, side-correct
liquidity), `simulate_fill`'s fail-open branches, the entry path's size↔impact
refinement pass, the exit path, the persisted telemetry, and the daily report's
§9 surface.

The load-bearing test in this file is
`TestFailOpen::test_absent_depth_is_byte_identical_to_flat` — 6.8.2 must be a
strict superset of the old behaviour, so a missing book can never move a fill.
"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from app.broker.depth import DEPTH_KEY, Depth, write_depth
from app.broker.paper_broker import (
    FillModel,
    _simulated_fill,
    close_position,
    place_paper_order,
    simulate_fill,
    spread_aware_bps,
)
from app.core.config import Settings, settings
from app.models.signal import Signal
from app.models.trading import Order, Position
from app.models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock

# A book 100 bps wide on a ₹500 name: mid 500, spread ₹5 → half-spread 50 bps.
WIDE = Depth(bid=Decimal("497.50"), ask=Decimal("502.50"), bid_qty=400, ask_qty=300)
# A tick-wide large-cap book: 2 bps total → 1 bps half-spread, UNDER the flat floor.
TIGHT = Depth(bid=Decimal("499.95"), ask=Decimal("500.05"), bid_qty=5000, ask_qty=5000)


@asynccontextmanager
async def depth_in_redis(stock_id: int, depth: Depth) -> AsyncIterator[None]:
    """Publish a live book on the real 6.8.1 Redis contract for the duration of
    a test — the seam paper_broker actually reads, not a mock of it."""
    import redis.asyncio as aioredis

    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await write_depth(
            r,
            stock_id=stock_id,
            instrument_token=1,
            depth=depth,
            ts=datetime.now(tz=UTC).isoformat(),
        )
        yield
    finally:
        await r.delete(DEPTH_KEY.format(stock_id=stock_id))
        await r.aclose()


async def _make_user(
    db: AsyncSession,
    email: str = "spread@example.com",
    capital: Decimal = Decimal("100000"),
) -> User:
    """`capital` is overridable because the per-position notional cap (added 2026-09-02,
    `paper_max_notional_leverage`) makes an order larger than the account impossible — as
    it should be. A test that needs a genuinely large order to exercise the impact term has
    to fund it."""
    from app.core.security import hash_password

    user = User(
        email=email,
        password_hash=hash_password("pass123"),
        full_name="Trader",
        role="user",
        is_active=True,
        trading_mode="paper",
        capital_inr=capital,
        risk_per_trade_pct=Decimal("2.00"),
        daily_loss_limit_pct=Decimal("3.00"),
        max_trades_per_day=5,
        allow_offmarket_entry=True,  # fill off the signal price, no live tick needed
    )
    db.add(user)
    await db.flush()
    return user


async def _make_signal(db: AsyncSession, stock_id: int) -> Signal:
    sig = Signal(
        stock_id=stock_id,
        direction="BUY",
        classification="swing",
        timeframe="1d",
        entry_price="500.0000",
        stop_loss="480.0000",
        take_profit="540.0000",
        suggested_qty=100,
        confidence_pct=80,
        factor_scores={"DOW_TREND": {"weight": 20, "score": 0.8, "explanation": "up"}},
        headline="BUY TEST@500",
        status="active",
        validity_until=datetime.now(tz=UTC) + timedelta(days=5),
        created_at=datetime.now(tz=UTC),
    )
    db.add(sig)
    await db.flush()
    return sig


# ── The bps model ─────────────────────────────────────────────────────────────


class TestSpreadAwareBps:
    def test_wide_book_charges_the_real_half_spread(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A 100-bps book costs 50 bps a side — 25× the flat 2 bps it replaces."""
        monkeypatch.setattr(settings, "paper_slippage_bps", 2.0)
        total, half, impact = spread_aware_bps(WIDE, "BUY", None)
        assert half == Decimal("50")
        assert impact == Decimal(0)  # no size given → spread only
        assert total == Decimal("50")

    def test_flat_bps_is_a_floor_so_a_tight_book_is_never_cheaper(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The point of 6.8.2 is honesty, not a discount: a 1-bps half-spread
        must NOT undercut the 2-bps flat model and flatter the paper record."""
        monkeypatch.setattr(settings, "paper_slippage_bps", 2.0)
        total, half, _ = spread_aware_bps(TIGHT, "BUY", None)
        assert half == Decimal("1")
        assert total == Decimal("2")  # floored at the flat baseline

    def test_impact_is_k_bps_when_the_order_equals_top_of_book(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "paper_slippage_bps", 0.0)
        monkeypatch.setattr(settings, "paper_impact_k_bps", 5.0)
        _, _, impact = spread_aware_bps(WIDE, "BUY", 300)  # ask_qty == 300
        assert impact == Decimal("5")

    def test_impact_scales_with_size_past_the_touch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "paper_slippage_bps", 0.0)
        monkeypatch.setattr(settings, "paper_impact_k_bps", 5.0)
        total_small, _, impact_small = spread_aware_bps(WIDE, "BUY", 150)
        total_big, _, impact_big = spread_aware_bps(WIDE, "BUY", 600)
        assert impact_small == Decimal("2.5")  # 5 × 150/300
        assert impact_big == Decimal("10")  # 5 × 600/300
        assert total_big > total_small  # eating deeper costs more

    def test_impact_is_capped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A 1-share book must not price an unbounded haircut."""
        monkeypatch.setattr(settings, "paper_slippage_bps", 0.0)
        monkeypatch.setattr(settings, "paper_impact_k_bps", 5.0)
        monkeypatch.setattr(settings, "paper_impact_cap_bps", 50.0)
        thin = Depth(bid=Decimal("497.50"), ask=Decimal("502.50"), bid_qty=1, ask_qty=1)
        total, half, impact = spread_aware_bps(thin, "BUY", 10_000)
        assert impact == Decimal("50")  # capped, not 5 × 10000
        assert total == half + Decimal("50")

    def test_total_has_a_hard_ceiling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A feed glitch that survives the crossed-book filter can't price a
        fill absurdly."""
        monkeypatch.setattr(settings, "paper_slippage_bps", 0.0)
        monkeypatch.setattr(settings, "paper_slippage_max_bps", 60.0)
        monkeypatch.setattr(settings, "paper_impact_k_bps", 5.0)
        total, half, impact = spread_aware_bps(WIDE, "BUY", 300)
        assert half + impact == Decimal("55")
        assert total == Decimal("55")  # under the ceiling, untouched
        total2, _, _ = spread_aware_bps(WIDE, "BUY", 3000)  # half 50 + impact 50
        assert total2 == Decimal("60")  # clamped to the ceiling

    def test_side_takes_the_correct_side_of_the_book(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A BUY eats the ASK's resting size, a SELL the BID's. An asymmetric
        book must therefore price the two sides differently."""
        monkeypatch.setattr(settings, "paper_slippage_bps", 0.0)
        monkeypatch.setattr(settings, "paper_impact_k_bps", 5.0)
        lopsided = Depth(
            bid=Decimal("497.50"), ask=Decimal("502.50"), bid_qty=1000, ask_qty=100
        )
        _, _, buy_impact = spread_aware_bps(lopsided, "BUY", 100)
        _, _, sell_impact = spread_aware_bps(lopsided, "SELL", 100)
        assert buy_impact == Decimal("5")  # 5 × 100/100 — takes the thin ask
        assert sell_impact == Decimal("0.5")  # 5 × 100/1000 — the deep bid

    def test_no_visible_size_charges_the_cap(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Zero resting size at the touch is the worst case, not the free case."""
        monkeypatch.setattr(settings, "paper_slippage_bps", 0.0)
        monkeypatch.setattr(settings, "paper_impact_cap_bps", 50.0)
        empty = Depth(bid=Decimal("497.50"), ask=Decimal("502.50"), bid_qty=0, ask_qty=0)
        _, _, impact = spread_aware_bps(empty, "BUY", 10)
        assert impact == Decimal("50")


# ── simulate_fill: the fail-open contract ─────────────────────────────────────


class TestFailOpen:
    def test_absent_depth_is_byte_identical_to_flat(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """THE canary for this slice. No book (pre-open, thin name, cache miss,
        capture off) must reproduce the pre-6.8.2 fill exactly — 6.8.2 adds a
        path, it never perturbs the existing one."""
        monkeypatch.setattr(settings, "paper_slippage_bps", 2.0)
        for side, ref in (("BUY", Decimal("500")), ("SELL", Decimal("480"))):
            fm = simulate_fill(ref, side, depth=None, quantity=100)
            assert fm.model == "flat"
            assert fm.fill == _simulated_fill(ref, side)
            assert fm.slippage_bps == fm.baseline_bps == Decimal("2.0")
            assert fm.excess_bps == Decimal(0)

    def test_disabled_flag_ignores_a_live_book(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The kill switch is a real kill switch — depth present, model off."""
        monkeypatch.setattr(settings, "paper_slippage_bps", 2.0)
        monkeypatch.setattr(settings, "paper_spread_fill_enabled", False)
        fm = simulate_fill(Decimal("500"), "BUY", depth=WIDE, quantity=100)
        assert fm.model == "flat"
        assert fm.fill == _simulated_fill(Decimal("500"), "BUY")

    def test_shipped_defaults_are_conservative(self) -> None:
        """Canary on the SHIPPED defaults (the suite pins the live singleton, so
        a silent revert would otherwise pass unnoticed)."""
        assert Settings.model_fields["paper_spread_fill_enabled"].default is True
        assert Settings.model_fields["paper_impact_k_bps"].default == 5.0
        assert Settings.model_fields["paper_impact_cap_bps"].default == 50.0
        assert Settings.model_fields["paper_slippage_max_bps"].default == 500.0


class TestSimulateFill:
    def test_spread_fill_is_adverse_on_both_sides(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "paper_slippage_bps", 0.0)
        buy = simulate_fill(Decimal("500"), "BUY", depth=WIDE, quantity=None)
        sell = simulate_fill(Decimal("500"), "SELL", depth=WIDE, quantity=None)
        assert buy.fill == Decimal("502.5000")  # 500 × (1 + 50bps)
        assert sell.fill == Decimal("497.5000")  # 500 × (1 − 50bps)
        assert buy.model == sell.model == "spread"

    def test_wide_book_fills_worse_than_the_flat_model(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The whole point: an illiquid name must cost more than flat 2 bps."""
        monkeypatch.setattr(settings, "paper_slippage_bps", 2.0)
        wide = simulate_fill(Decimal("500"), "BUY", depth=WIDE, quantity=None)
        assert wide.fill > _simulated_fill(Decimal("500"), "BUY")
        assert wide.excess_bps == Decimal("48")  # 50 charged vs 2 baseline

    def test_money_stays_decimal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "paper_slippage_bps", 2.0)
        fm = simulate_fill(Decimal("500"), "BUY", depth=WIDE, quantity=100)
        for value in (fm.fill, fm.reference, fm.slippage_bps, fm.bid, fm.ask):
            assert isinstance(value, Decimal)

    def test_payload_round_trips_through_json_exactly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The telemetry lands in a JSONB column — prices must survive as
        strings, never as floats that lose the last paisa."""
        monkeypatch.setattr(settings, "paper_slippage_bps", 2.0)
        fm = simulate_fill(Decimal("500"), "BUY", depth=WIDE, quantity=300)
        payload = json.loads(json.dumps(fm.as_payload()))
        assert Decimal(payload["fill"]) == fm.fill
        assert Decimal(payload["bid"]) == WIDE.bid
        assert payload["model"] == "spread"
        assert payload["top_qty"] == 300  # ask side, the one a BUY takes
        assert Decimal(payload["excess_bps"]) > 0

    def test_excess_is_never_negative(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "paper_slippage_bps", 2.0)
        fm = simulate_fill(Decimal("500"), "BUY", depth=TIGHT, quantity=1)
        assert fm.excess_bps == Decimal(0)
        assert isinstance(fm, FillModel)


# ── Entry path ────────────────────────────────────────────────────────────────


class TestEntryFill:
    async def test_entry_without_depth_matches_the_old_path(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fail-open canary through the real order path (no depth key set)."""
        monkeypatch.setattr(settings, "paper_slippage_bps", 2.0)
        user = await _make_user(db)
        stock = await make_stock(db, symbol="NODEPTH")
        signal = await _make_signal(db, stock.id)

        _, pos = await place_paper_order(db, user, signal, side="BUY", quantity=100)
        await db.commit()

        assert pos.avg_entry_price == _simulated_fill(Decimal("500"), "BUY")

    async def test_wide_spread_entry_fills_worse_than_flat(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "paper_slippage_bps", 2.0)
        monkeypatch.setattr(settings, "paper_impact_k_bps", 0.0)  # isolate the spread
        user = await _make_user(db)
        stock = await make_stock(db, symbol="WIDECO")
        signal = await _make_signal(db, stock.id)
        await db.commit()

        async with depth_in_redis(stock.id, WIDE):
            _, pos = await place_paper_order(db, user, signal, side="BUY", quantity=100)
            await db.commit()

        assert pos.avg_entry_price == Decimal("502.5000")  # 50 bps, not 2
        assert pos.avg_entry_price > _simulated_fill(Decimal("500"), "BUY")

    async def test_large_order_pays_impact_past_top_of_book(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Size beyond the resting ask costs more than size that fits at it."""
        monkeypatch.setattr(settings, "paper_slippage_bps", 0.0)
        monkeypatch.setattr(settings, "paper_impact_k_bps", 5.0)
        user_small = await _make_user(db, email="small@example.com")
        # Funded so the 3000-share order is a trade this account could actually place:
        # 3000 × ~₹505 ≈ ₹15.2L, which needs more than ₹1L of capital now that the
        # per-position notional cap is enforced. The fill economics under test are
        # unchanged — what changed is that the scenario is no longer physically impossible.
        user_big = await _make_user(
            db, email="big@example.com", capital=Decimal("2000000")
        )
        stock = await make_stock(db, symbol="IMPACTCO")
        signal = await _make_signal(db, stock.id)
        await db.commit()

        async with depth_in_redis(stock.id, WIDE):  # ask_qty 300
            _, small = await place_paper_order(
                db, user_small, signal, side="BUY", quantity=30
            )
            _, big = await place_paper_order(
                db, user_big, signal, side="BUY", quantity=3000
            )
            await db.commit()

        # 30/300 → 0.5 bps impact, so 50.5 bps total: 500 × 1.00505 = 502.525,
        # which lands mid-tick and rounds up the 0.05 grid to 502.55.
        assert small.avg_entry_price == Decimal("502.5500")
        # 3000/300 = 10× the touch → impact hits its 50-bps cap → 100 bps total.
        assert big.avg_entry_price == Decimal("505.0000")
        assert big.avg_entry_price > small.avg_entry_price

    async def test_sizing_is_risk_first_from_the_spread_aware_fill(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A wider spread means a worse fill, a wider |fill − SL|, and therefore
        a SMALLER position — the risk budget is held, not the share count. This
        is the size↔impact refinement pass doing its job.
        """
        monkeypatch.setattr(settings, "paper_slippage_bps", 0.0)
        monkeypatch.setattr(settings, "paper_impact_k_bps", 5.0)
        user = await _make_user(db)
        stock = await make_stock(db, symbol="SIZECO")
        signal = await _make_signal(db, stock.id)  # entry 500, SL 480
        await db.commit()

        async with depth_in_redis(stock.id, WIDE):
            _, pos = await place_paper_order(db, user, signal, side="BUY")
            await db.commit()

        # Budget = 100000 × 2% = ₹2000. Flat would fill 500 → 20/share → 100 sh.
        # Spread-aware charges 51.47 bps → a raw adverse price of 502.5733, which ceils
        # to 502.60 → 22.60/share → 88 sh.
        #
        # ⚠ This asserted 502.5500 until 2026-09-05, and that value was the BUG: with
        # `ROUND_HALF_UP` to the NEAREST tick a BUY filled at 502.55 — **below** the
        # 502.5733 the model had just computed — so we underpaid by ₹0.023/share while the
        # module's contract says it "can only make a fill worse". `_round_tick` is now
        # directional (BUY ceils, SELL floors). Canary: 502.60 ≥ the raw adverse price and
        # 502.55 is not.
        assert pos.avg_entry_price == Decimal("502.6000")
        assert pos.quantity == 88
        risk = Decimal(pos.quantity) * (pos.avg_entry_price - Decimal("480"))
        assert risk <= Decimal("2000")  # budget held despite the worse fill

    async def test_entry_records_fill_telemetry(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "paper_slippage_bps", 2.0)
        user = await _make_user(db)
        stock = await make_stock(db, symbol="TELECO")
        signal = await _make_signal(db, stock.id)
        await db.commit()

        async with depth_in_redis(stock.id, WIDE):
            order, _ = await place_paper_order(
                db, user, signal, side="BUY", quantity=100
            )
            await db.commit()

        fill = order.broker_payload["fill"]
        assert fill["model"] == "spread"
        assert Decimal(fill["reference"]) == Decimal("500")
        assert Decimal(fill["half_spread_bps"]) == Decimal("50")
        assert Decimal(fill["baseline_bps"]) == Decimal("2")
        assert Decimal(fill["excess_bps"]) > 0
        assert "chase" in order.broker_payload  # existing telemetry untouched


# ── Exit path ─────────────────────────────────────────────────────────────────


class TestExitFill:
    async def test_exit_crosses_the_real_spread(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The exit is where illiquidity bites — the whole position crosses at
        once, so realised P&L must be worse than the flat-bps baseline."""
        monkeypatch.setattr(settings, "paper_slippage_bps", 2.0)
        monkeypatch.setattr(settings, "paper_impact_k_bps", 0.0)
        user = await _make_user(db)
        stock = await make_stock(db, symbol="EXITCO")
        signal = await _make_signal(db, stock.id)
        pos = Position(
            user_id=user.id,
            stock_id=stock.id,
            mode="paper",
            side="LONG",
            quantity=100,
            avg_entry_price=Decimal("500"),
            current_sl=Decimal("480"),
            current_tp=Decimal("540"),
            trail_state="none",
            unrealized_pnl=Decimal("0"),
            realized_pnl=Decimal("0"),
            opened_at=datetime.now(tz=UTC),
            signal_id=signal.id,
        )
        db.add(pos)
        await db.commit()

        async with depth_in_redis(stock.id, WIDE):
            order, closed = await close_position(
                db, pos, exit_price=Decimal("540"), reason="test"
            )
            await db.commit()

        assert closed.exit_price == Decimal("537.3000")  # 540 × (1 − 50 bps)
        assert closed.exit_price < _simulated_fill(Decimal("540"), "SELL")
        assert order.broker_payload["fill"]["model"] == "spread"
        assert order.broker_payload["reason"] == "test"  # existing payload kept

    async def test_exit_without_depth_is_unchanged(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "paper_slippage_bps", 2.0)
        user = await _make_user(db)
        stock = await make_stock(db, symbol="EXITFLAT")
        signal = await _make_signal(db, stock.id)
        pos = Position(
            user_id=user.id,
            stock_id=stock.id,
            mode="paper",
            side="LONG",
            quantity=100,
            avg_entry_price=Decimal("500"),
            current_sl=Decimal("480"),
            current_tp=Decimal("540"),
            trail_state="none",
            unrealized_pnl=Decimal("0"),
            realized_pnl=Decimal("0"),
            opened_at=datetime.now(tz=UTC),
            signal_id=signal.id,
        )
        db.add(pos)
        await db.commit()

        _, closed = await close_position(
            db, pos, exit_price=Decimal("540"), reason="test"
        )
        await db.commit()

        assert closed.exit_price == _simulated_fill(Decimal("540"), "SELL")  # 539.90


# ── Daily report §9 ───────────────────────────────────────────────────────────


class TestFillRealismReport:
    async def test_builds_rows_and_computes_the_honesty_delta(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services.daily_report import build_fill_realism, ist_day_bounds

        monkeypatch.setattr(settings, "paper_slippage_bps", 2.0)
        monkeypatch.setattr(settings, "paper_impact_k_bps", 0.0)
        user = await _make_user(db)
        stock = await make_stock(db, symbol="REPORTCO")
        signal = await _make_signal(db, stock.id)
        await db.commit()

        async with depth_in_redis(stock.id, WIDE):
            await place_paper_order(db, user, signal, side="BUY", quantity=100)
            await db.commit()

        order = (await db.execute(select(Order))).scalars().one()
        assert order.filled_at is not None
        start, end = ist_day_bounds(
            order.filled_at.astimezone(ZoneInfo("Asia/Kolkata")).date()
        )

        rows = await build_fill_realism(db, user_id=user.id, start=start, end=end)
        assert len(rows) == 1
        row = rows[0]
        assert row.symbol == "REPORTCO"
        assert row.kind == "entry" and row.side == "BUY"
        assert row.model == "spread"
        assert row.excess_bps == Decimal("48")  # 50 charged − 2 flat baseline
        # 100 shares × ₹500 reference × 48 bps = ₹240 of overstated edge.
        assert row.excess_inr == Decimal("240.00")

    async def test_pre_6_8_2_orders_are_skipped_not_crashed(
        self, db: AsyncSession
    ) -> None:
        """Historical orders carry no `fill` block — the report must ignore them
        rather than raise on a KeyError."""
        from app.services.daily_report import build_fill_realism, ist_day_bounds

        user = await _make_user(db)
        stock = await make_stock(db, symbol="OLDCO")
        now = datetime.now(tz=UTC)
        db.add(
            Order(
                user_id=user.id,
                stock_id=stock.id,
                mode="paper",
                side="BUY",
                order_type="MARKET",
                quantity=10,
                status="filled",
                placed_at=now,
                filled_at=now,
                filled_price=Decimal("100"),
                filled_qty=10,
                broker_payload={"chase": {"fill": "100"}},  # legacy shape
            )
        )
        await db.commit()

        start, end = ist_day_bounds(now.astimezone(ZoneInfo("Asia/Kolkata")).date())
        assert await build_fill_realism(db, user_id=user.id, start=start, end=end) == []

    def test_section_renders_the_totals(self) -> None:
        from app.services.daily_report import (
            FillRealismRow,
            _render_fill_realism_section,
        )

        rows = [
            FillRealismRow(
                symbol="WIDECO",
                kind="entry",
                side="BUY",
                quantity=100,
                model="spread",
                reference=Decimal("500"),
                fill=Decimal("502.50"),
                slippage_bps=Decimal("50"),
                baseline_bps=Decimal("2"),
                excess_bps=Decimal("48"),
                half_spread_bps=Decimal("50"),
                impact_bps=Decimal("0"),
                excess_inr=Decimal("240.00"),
                filled_at=datetime.now(tz=UTC),
            )
        ]
        text = "\n".join(_render_fill_realism_section(rows))
        assert "9. Fill realism" in text
        assert "WIDECO" in text
        assert "1 of 1" in text
        assert "240" in text  # the honesty delta is stated in rupees

    def test_empty_section_explains_the_silence(self) -> None:
        """A dark section must say WHY it is dark — the §7/§8 discipline."""
        from app.services.daily_report import _render_fill_realism_section

        text = "\n".join(_render_fill_realism_section([]))
        assert "No paper fills" in text
        assert "before 6.8.2" in text
