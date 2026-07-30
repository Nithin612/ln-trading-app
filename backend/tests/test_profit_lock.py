"""Tests for the Layered Ratchet Stop mechanism + profit-lock shadow comparator.

  - profit_lock.layered_ratchet_stop / giveback_fraction (pure, no DB)
  - atr.latest_atr (Wilder-seed ATR from stored candles)
  - profit_lock_shadow.compare_position (offline replay over a 1m tape)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.models.market_data import Ohlcv1m, OhlcvDaily
from app.models.signal import Signal
from app.models.trading import Position
from app.trading.profit_lock import (
    CLASS_PARAMS,
    DEFAULT_PARAMS,
    RatchetParams,
    giveback_fraction,
    layered_ratchet_stop,
    params_for,
)
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock

SWING = CLASS_PARAMS["swing"]  # arm 1.0R, atr_k 2.5, giveback 0.55→0.40, late 3


# ── Pure: giveback taper ───────────────────────────────────────────────────────

class TestGiveback:
    def test_flat_before_arm(self) -> None:
        assert giveback_fraction(SWING, Decimal("0.5")) == SWING.giveback_early

    def test_flat_after_late(self) -> None:
        assert giveback_fraction(SWING, Decimal("4")) == SWING.giveback_late

    def test_linear_midpoint(self) -> None:
        # r_mult 2 is halfway between arm_r(1) and late_r(3) → mid giveback
        span = SWING.giveback_late - SWING.giveback_early
        expected = SWING.giveback_early + span * Decimal("0.5")
        assert giveback_fraction(SWING, Decimal("2")) == expected

    def test_params_for_fallback(self) -> None:
        assert params_for("nonsense") is DEFAULT_PARAMS
        assert params_for(None) is DEFAULT_PARAMS
        assert params_for("intraday") is CLASS_PARAMS["intraday"]


# ── Pure: layered ratchet stop ─────────────────────────────────────────────────

class TestLayeredRatchetStop:
    def test_long_not_armed_holds_original_sl(self) -> None:
        # move 10 = 0.5R < arm 1R → nothing arms, stop stays at the risk floor
        stop = layered_ratchet_stop(
            side="LONG", entry=Decimal("500"), original_sl=Decimal("480"),
            peak_price=Decimal("510"), atr=None, params=SWING, current_stop=Decimal("480"),
        )
        assert stop == Decimal("480")

    def test_long_armed_profit_lock(self) -> None:
        # peak 525 = 1.25R; giveback tapers to 0.53125 → lock = 500 + 25*0.46875
        stop = layered_ratchet_stop(
            side="LONG", entry=Decimal("500"), original_sl=Decimal("480"),
            peak_price=Decimal("525"), atr=None, params=SWING, current_stop=Decimal("480"),
        )
        assert stop == Decimal("511.71875")

    def test_long_atr_chandelier_can_bind(self) -> None:
        # chandelier = 525 - 2.5*4 = 515 > profit-lock 511.72 → chandelier wins
        stop = layered_ratchet_stop(
            side="LONG", entry=Decimal("500"), original_sl=Decimal("480"),
            peak_price=Decimal("525"), atr=Decimal("4"), params=SWING, current_stop=Decimal("480"),
        )
        assert stop == Decimal("515")

    def test_one_way_ratchet_never_loosens(self) -> None:
        # current_stop already tighter than the computed raw → keep it
        stop = layered_ratchet_stop(
            side="LONG", entry=Decimal("500"), original_sl=Decimal("480"),
            peak_price=Decimal("525"), atr=None, params=SWING, current_stop=Decimal("515"),
        )
        assert stop == Decimal("515")

    def test_short_armed_profit_lock(self) -> None:
        # SHORT mirror: entry 100, R=6, peak(low) 91 = 1.5R
        # g at 1.5R = 0.55 + (0.40-0.55)*0.25 = 0.5125 → lock = 100 - 9*0.4875
        stop = layered_ratchet_stop(
            side="SHORT", entry=Decimal("100"), original_sl=Decimal("106"),
            peak_price=Decimal("91"), atr=None, params=SWING, current_stop=Decimal("106"),
        )
        assert stop == Decimal("95.6125")

    def test_zero_risk_never_arms(self) -> None:
        # pivot SL == entry is legal → risk 0 → stop stays put, no div-by-zero
        stop = layered_ratchet_stop(
            side="LONG", entry=Decimal("500"), original_sl=Decimal("500"),
            peak_price=Decimal("600"), atr=None,
            params=RatchetParams(Decimal("1"), Decimal("2"), Decimal("0.3"), Decimal("0.2")),
            current_stop=Decimal("500"),
        )
        assert stop == Decimal("500")


# ── ATR from stored candles ────────────────────────────────────────────────────

class TestAtr:
    async def test_wilder_seed_atr(self, db: AsyncSession) -> None:
        from app.trading.atr import latest_atr

        stock = await make_stock(db)
        base = datetime(2026, 6, 1, tzinfo=UTC)
        # 15 daily bars, each range 10, flat closes → every TR = 10 → ATR = 10
        for i in range(15):
            db.add(OhlcvDaily(
                time=base + timedelta(days=i), stock_id=stock.id,
                open=Decimal("105"), high=Decimal("110"), low=Decimal("100"),
                close=Decimal("105"), volume=1000, is_complete=True,
            ))
        await db.flush()

        atr = await latest_atr(db, stock.id, timeframe="1d", period=14)
        assert atr == Decimal("10")

    async def test_atr_none_when_insufficient_bars(self, db: AsyncSession) -> None:
        from app.trading.atr import latest_atr

        stock = await make_stock(db)
        db.add(OhlcvDaily(
            time=datetime(2026, 6, 1, tzinfo=UTC), stock_id=stock.id,
            open=Decimal("100"), high=Decimal("101"), low=Decimal("99"),
            close=Decimal("100"), volume=1, is_complete=True,
        ))
        await db.flush()
        assert await latest_atr(db, stock.id, timeframe="1d", period=14) is None


# ── Shadow replay comparator ───────────────────────────────────────────────────

class TestShadowCompare:
    async def _short_scenario(self, db: AsyncSession) -> Position:
        """SHORT that spikes to +9pts (1.5R) then reverses — the ladder locks a
        small profit (trailing_1 at 97) while the layered lock rides lower."""
        from app.core.security import hash_password
        from app.models.user import User

        user = User(
            email="pl@example.com", password_hash=hash_password("x"), full_name="PL",
            role="user", is_active=True, trading_mode="paper", capital_inr=Decimal("100000"),
        )
        db.add(user)
        await db.flush()
        stock = await make_stock(db)
        now = datetime.now(tz=UTC)
        sig = Signal(
            stock_id=stock.id, direction="SELL", classification="swing", timeframe="1d",
            entry_price="100.0000", stop_loss="106.0000", take_profit="70.0000",
            suggested_qty=100, confidence_pct=80,
            factor_scores={"X": {"weight": 20, "score": 0.8, "explanation": "e"}},
            headline="SELL", status="active",
            validity_until=now + timedelta(days=5), created_at=now,
        )
        db.add(sig)
        await db.flush()

        t0 = datetime(2026, 7, 27, 4, 0, tzinfo=UTC)  # in-session, irrelevant to replay
        # (open, high, low, close) — SHORT: favourable=low, adverse=high
        bars = [
            ("100", "100", "99", "99"),   # low 99
            ("99", "99", "96", "96"),     # low 96
            ("96", "96", "91", "91"),     # low 91  → 1.5R; ladder→trailing_1 (SL 97)
            ("91", "94", "91", "94"),     # high 94 → neither stop hit
            ("94", "97", "94", "97"),     # high 97 → ladder@97 & layered@95.6125 both hit
        ]
        for i, (o, h, low, c) in enumerate(bars):
            db.add(Ohlcv1m(
                time=t0 + timedelta(minutes=i), stock_id=stock.id,
                open=Decimal(o), high=Decimal(h), low=Decimal(low), close=Decimal(c),
                volume=1000, is_complete=True,
            ))
        pos = Position(
            user_id=user.id, stock_id=stock.id, mode="paper", side="SHORT", quantity=100,
            avg_entry_price=Decimal("100"), current_sl=Decimal("106"), current_tp=Decimal("70"),
            trail_state="none", unrealized_pnl=Decimal("0"), realized_pnl=Decimal("290"),
            exit_price=Decimal("97"), exit_reason="sl_hit",
            opened_at=t0, closed_at=t0 + timedelta(minutes=5), signal_id=sig.id,
        )
        db.add(pos)
        await db.flush()
        return pos

    async def test_layered_keeps_more_than_ladder(self, db: AsyncSession) -> None:
        from app.services.profit_lock_shadow import compare_position

        pos = await self._short_scenario(db)
        comp = await compare_position(db, pos, now=datetime.now(tz=UTC))

        assert comp.note is None
        assert comp.bars == 5
        # MFE = (100 - 91) * 100 = 900 gross
        assert comp.peak_gross == Decimal("900")

        by = {p.policy: p for p in comp.policies}
        assert set(by) == {"ladder", "layered", "giveback_33"}
        # ladder locks at 97 (trailing_1); layered rides down to 95.6125
        assert by["ladder"].exit_price == Decimal("97")
        assert by["layered"].exit_price == Decimal("95.6125")
        # → layered keeps strictly more of the move than the current ladder
        assert by["layered"].exit_net > by["ladder"].exit_net
        assert not by["layered"].still_open and not by["ladder"].still_open
        # capture ratios are populated and ordered the same way
        assert by["layered"].capture_pct > by["ladder"].capture_pct

    async def test_off_tape_exit_is_flagged_and_capture_suppressed(
        self, db: AsyncSession
    ) -> None:
        """Regression (07-27 LENSKART): a SHORT recorded a favourable exit BELOW
        anything that really traded (a stale/pre-open close). The realised P&L
        is then fictional — flag it, and compute no capture % against it — while
        peak and the policy replays stay real."""
        from app.services.profit_lock_shadow import compare_position

        pos = await self._short_scenario(db)  # real 1m low is 91
        pos.exit_price = Decimal("88.00")     # below the true low → never traded
        pos.realized_pnl = Decimal("6000")    # fictional profit
        await db.flush()

        comp = await compare_position(db, pos, now=datetime.now(tz=UTC))

        assert comp.actual_exit_off_tape is True
        assert comp.actual_capture_pct is None          # no nonsensical % vs a fake exit
        assert comp.note is not None and "off-tape" in comp.note
        assert comp.peak_gross == Decimal("900")        # peak still real
        assert any(p.policy == "layered" for p in comp.policies)  # policies still replayed

    async def test_insufficient_candles_notes_and_skips(self, db: AsyncSession) -> None:
        from app.core.security import hash_password
        from app.models.user import User
        from app.services.profit_lock_shadow import compare_position

        user = User(
            email="pl2@example.com", password_hash=hash_password("x"), full_name="PL",
            role="user", is_active=True, trading_mode="paper", capital_inr=Decimal("100000"),
        )
        db.add(user)
        await db.flush()
        stock = await make_stock(db)
        now = datetime.now(tz=UTC)
        sig = Signal(
            stock_id=stock.id, direction="BUY", classification="swing", timeframe="1d",
            entry_price="500.0000", stop_loss="480.0000", take_profit="540.0000",
            suggested_qty=100, confidence_pct=80,
            factor_scores={"X": {"weight": 20, "score": 0.8, "explanation": "e"}},
            headline="BUY", status="active", validity_until=now + timedelta(days=5), created_at=now,
        )
        db.add(sig)
        await db.flush()
        pos = Position(
            user_id=user.id, stock_id=stock.id, mode="paper", side="LONG", quantity=100,
            avg_entry_price=Decimal("500"), current_sl=Decimal("480"), current_tp=Decimal("540"),
            trail_state="none", unrealized_pnl=Decimal("0"), realized_pnl=Decimal("0"),
            opened_at=now - timedelta(hours=1), closed_at=now, signal_id=sig.id,
        )
        db.add(pos)
        await db.flush()

        comp = await compare_position(db, pos, now=now)
        assert comp.note is not None and "insufficient" in comp.note
        assert comp.policies == []
