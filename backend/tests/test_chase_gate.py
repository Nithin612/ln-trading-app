"""Anti-chase eligibility gate — overlay + order-path wiring + shadow sidecar.

Blocks an order when the LIVE price has run more than `chase_max_r` × the trade's risk PAST the
signal's entry (the server-side backstop to the AlertBell guardrail). Covers: pure chase_r logic
(both sides, negative chase, fail-open on no-price / zero-risk, boundary); order-path
off/shadow/active + fail-open; the shadow sidecar partition (chased / near-entry / no-data)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import redis.asyncio as aioredis
from app.broker.tick_consumer import LTP_KEY
from app.core.config import settings
from app.models.signal import Signal
from app.models.trading import Order, Position
from app.services import chase_shadow as cs
from app.signals import chase_guard as cg
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock

D = Decimal
# BUY entry ₹500, SL ₹480 → 1R = ₹20; default ceiling 0.33R → ₹506.60.
ENTRY, SL = D("500"), D("480")


# ── Pure overlay ──────────────────────────────────────────────────────────────
class TestOverlay:
    def test_buy_chase_blocks(self) -> None:
        v = cg.evaluate(entry=ENTRY, stop_loss=SL, market_price=D("520"), side="BUY")
        assert v.assessable is True and v.blocked is True
        assert v.chase_r == D("1")  # (520-500)/20
        assert v.side == "LONG"

    def test_buy_near_entry_allowed(self) -> None:
        v = cg.evaluate(entry=ENTRY, stop_loss=SL, market_price=D("503"), side="BUY")
        assert v.assessable is True and v.blocked is False
        assert v.chase_r == D("0.15")  # (503-500)/20

    def test_boundary_at_ceiling_not_blocked(self) -> None:
        # chase_r exactly == max_chase_r → not strictly greater → eligible.
        v = cg.evaluate(
            entry=ENTRY, stop_loss=SL, market_price=D("506.6"), side="BUY", max_chase_r=D("0.33")
        )
        assert v.chase_r == D("0.33") and v.blocked is False

    def test_sell_is_mirrored(self) -> None:
        # SELL entry 500, SL 520 (risk 20); price 480 → chase_r (500-480)/20 = 1.0 → block.
        v = cg.evaluate(entry=D("500"), stop_loss=D("520"), market_price=D("480"), side="SELL")
        assert v.side == "SHORT" and v.blocked is True and v.chase_r == D("1")

    def test_negative_chase_never_blocks(self) -> None:
        # BUY filling BELOW entry (better than planned) → negative chase_r, never blocked.
        v = cg.evaluate(entry=ENTRY, stop_loss=SL, market_price=D("495"), side="BUY")
        assert v.chase_r < 0 and v.blocked is False

    def test_no_price_fails_open(self) -> None:
        v = cg.evaluate(entry=ENTRY, stop_loss=SL, market_price=None, side="BUY")
        assert v.assessable is False and v.blocked is False and v.chase_r is None

    def test_zero_risk_fails_open(self) -> None:
        v = cg.evaluate(entry=D("500"), stop_loss=D("500"), market_price=D("520"), side="BUY")
        assert v.assessable is False and v.blocked is False and v.chase_r is None

    def test_as_payload_strings(self) -> None:
        p = cg.evaluate(entry=ENTRY, stop_loss=SL, market_price=D("520"), side="BUY").as_payload()
        assert p["blocked"] is True and p["assessable"] is True
        assert p["chase_r"] == "1.0000" and p["max_chase_r"] == "0.33"
        assert p["entry"] == "500.0000" and p["market_price"] == "520.0000"
        assert p["side"] == "LONG"

    def test_order_block_reason_modes(self) -> None:
        blocked = cg.evaluate(entry=ENTRY, stop_loss=SL, market_price=D("520"), side="BUY")
        assert cg.order_block_reason(blocked, "off") is None
        assert cg.order_block_reason(blocked, "shadow") is None
        assert "anti-chase" in (cg.order_block_reason(blocked, "active") or "")
        ok = cg.evaluate(entry=ENTRY, stop_loss=SL, market_price=D("503"), side="BUY")
        assert cg.order_block_reason(ok, "active") is None


# ── Order-path wiring ─────────────────────────────────────────────────────────
async def _make_signal(db: AsyncSession, stock_id: int) -> Signal:
    now = datetime.now(tz=UTC)
    sig = Signal(
        stock_id=stock_id, direction="BUY", classification="swing", timeframe="1d",
        entry_price="500.0000", stop_loss="480.0000", take_profit="540.0000",
        suggested_qty=100, confidence_pct=80,
        factor_scores={
            "DOW_TREND": {"weight": 20, "score": 0.8, "explanation": "up"},
            "MACD_CROSS": {"weight": 15, "score": 0.6, "explanation": "x"},
        },
        headline="t", status="active", is_shadow=False,
        validity_until=now + timedelta(days=5), created_at=now,
    )
    db.add(sig)
    await db.flush()
    return sig


async def _order(client: AsyncClient, headers: dict[str, str], signal_id: str) -> int:
    r = await client.post(
        "/api/v1/trading/orders", json={"signal_id": signal_id, "side": "BUY"}, headers=headers
    )
    return r.status_code


async def _set_ltp(stock_id: int, price: str) -> aioredis.Redis:
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    await r.set(LTP_KEY.format(stock_id=stock_id), price, ex=600)
    return r


class TestOrderPath:
    async def test_off_is_true_no_op(self, client, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(settings, "chase_gate_mode", "off")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db, symbol="CHOFF")
        sig = await _make_signal(db, stock.id)
        await db.commit()
        r = await _set_ltp(stock.id, "520")  # chased, but gate is off
        try:
            assert await _order(client, headers, sig.id) == 201
        finally:
            await r.delete(LTP_KEY.format(stock_id=stock.id))
            await r.aclose()

    async def test_active_blocks_chase(self, client, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(settings, "chase_gate_mode", "active")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db, symbol="CHACT")
        sig = await _make_signal(db, stock.id)
        await db.commit()
        r = await _set_ltp(stock.id, "520")  # 1.0R past entry → chasing
        try:
            assert await _order(client, headers, sig.id) == 409
        finally:
            await r.delete(LTP_KEY.format(stock_id=stock.id))
            await r.aclose()

    async def test_active_allows_near_entry(self, client, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(settings, "chase_gate_mode", "active")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db, symbol="CHNEAR")
        sig = await _make_signal(db, stock.id)
        await db.commit()
        r = await _set_ltp(stock.id, "503")  # 0.15R past entry → within ceiling
        try:
            assert await _order(client, headers, sig.id) == 201
        finally:
            await r.delete(LTP_KEY.format(stock_id=stock.id))
            await r.aclose()

    async def test_shadow_never_blocks_but_stamps(self, client, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(settings, "chase_gate_mode", "shadow")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db, symbol="CHSHAD")
        sig = await _make_signal(db, stock.id)
        await db.commit()
        r = await _set_ltp(stock.id, "520")  # chased, but shadow → allowed
        try:
            assert await _order(client, headers, sig.id) == 201
        finally:
            await r.delete(LTP_KEY.format(stock_id=stock.id))
            await r.aclose()
        # The shadow verdict is stamped for the report even though it didn't block.
        order = (
            await db.execute(select(Order).where(Order.signal_id == sig.id))
        ).scalars().first()
        assert order is not None and order.broker_payload is not None
        stamp = order.broker_payload["chase_gate"]
        assert stamp["blocked"] is True and stamp["assessable"] is True

    async def test_active_fails_open_without_live_price(self, client, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(settings, "chase_gate_mode", "active")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db, symbol="CHNOLTP")
        sig = await _make_signal(db, stock.id)
        await db.commit()
        # No LTP set → get_live_ltp None → not assessable → eligible (fail open).
        assert await _order(client, headers, sig.id) == 201


# ── Shadow sidecar ──────────────────────────────────────────────────────────
async def _closed_position(
    db: AsyncSession, user_id: int, stock_id: int, signal_id: str, realized: str
) -> None:
    db.add(
        Position(
            user_id=user_id, stock_id=stock_id, signal_id=signal_id, mode="paper", side="LONG",
            quantity=10, avg_entry_price=D("500"), realized_pnl=D(realized),
            opened_at=datetime.now(tz=UTC), closed_at=datetime.now(tz=UTC),
        )
    )


async def _order_row(
    db: AsyncSession, user_id: int, stock_id: int, signal_id: str, payload: dict
) -> None:
    db.add(
        Order(
            user_id=user_id, stock_id=stock_id, signal_id=signal_id, mode="paper", side="BUY",
            order_type="MARKET", quantity=10, status="filled", broker_payload=payload,
        )
    )


class TestShadow:
    def test_chase_r_prefers_gate_stamp_over_broker_telemetry(self) -> None:
        # gate stamp present → used; broker telemetry only as fallback.
        both = {"chase_gate": {"chase_r": "0.9"}, "chase": {"chase_r": "0.1"}}
        gate_none = {"chase_gate": {"chase_r": None}, "chase": {"chase_r": "0.2"}}
        assert cs._chase_r_from_payload(both) == D("0.9")
        assert cs._chase_r_from_payload({"chase": {"chase_r": "0.1"}}) == D("0.1")
        assert cs._chase_r_from_payload(gate_none) == D("0.2")  # gate None → broker fallback
        assert cs._chase_r_from_payload({}) is None
        assert cs._chase_r_from_payload(None) is None

    async def test_partitions_chased_near_no_data(self, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(settings, "chase_max_r", 0.33)
        user = await create_test_user(db)
        chased = await make_stock(db, symbol="CHSD")
        near = await make_stock(db, symbol="NEAR")
        blank = await make_stock(db, symbol="BLANK")
        s_chased = await _make_signal(db, chased.id)
        s_near = await _make_signal(db, near.id)
        s_blank = await _make_signal(db, blank.id)
        # chased: chase_r 1.0 > 0.33, lost ₹2,000
        await _order_row(db, user.id, chased.id, s_chased.id, {"chase_gate": {"chase_r": "1.0"}})
        await _closed_position(db, user.id, chased.id, s_chased.id, "-2000")
        # near entry: chase_r 0.1, won ₹800
        await _order_row(db, user.id, near.id, s_near.id, {"chase": {"chase_r": "0.10"}})
        await _closed_position(db, user.id, near.id, s_near.id, "800")
        # no chase stamp
        await _order_row(db, user.id, blank.id, s_blank.id, {})
        await db.commit()

        r = await cs.compute_chase_shadow(db)
        assert r.chased.n == 1 and r.chased.resolved == 1 and r.chased.net == D("-2000")
        assert r.near_entry.n == 1 and r.near_entry.net == D("800") and r.near_entry.win_pct == 100
        assert r.no_data.n == 1
        assert cs.chase_flip_ready(r)[0] is False  # only 1 resolved chased — keep accruing

    async def test_render_smoke(self, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        user = await create_test_user(db)
        stock = await make_stock(db, symbol="RND")
        sig = await _make_signal(db, stock.id)
        await _order_row(db, user.id, stock.id, sig.id, {"chase_gate": {"chase_r": "0.9"}})
        await _closed_position(db, user.id, stock.id, sig.id, "-1500")
        await db.commit()
        md = cs.render_markdown(await cs.compute_chase_shadow(db), day=datetime.now(tz=UTC).date())
        assert "Anti-chase shadow" in md and "flip readiness" in md and "chased" in md.lower()
