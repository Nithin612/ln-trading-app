"""Phase 6.8.5 — CA-adjust of OPEN paper positions.

The correctness core: a split/bonus scales price levels ÷factor and qty ×factor
so R (`|entry−SL|×qty`) and notional are preserved EXACTLY; the adjustment is
idempotent per (position, action). Plus the admin API that records the verified
event.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from app.models.corporate_action import PositionCorporateAction
from app.models.trading import Position
from app.services.ca_adjust import (
    apply_ca_to_position,
    apply_ex_date_corporate_actions,
    record_corporate_action,
)
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock

EX = date(2026, 8, 18)


async def _position(
    db: AsyncSession,
    user_id: int,
    stock_id: int,
    *,
    qty: int = 10,
    entry: str = "100.0000",
    sl: str = "95.0000",
    tp: str = "120.0000",
    peak: str = "110.0000",
    peak_pnl: str = "100.00",
    side: str = "LONG",
    closed: bool = False,
) -> Position:
    pos = Position(
        user_id=user_id, stock_id=stock_id, mode="paper", side=side, quantity=qty,
        avg_entry_price=Decimal(entry), current_sl=Decimal(sl), current_tp=Decimal(tp),
        peak_price=Decimal(peak), peak_pnl=Decimal(peak_pnl), trail_state="none",
        realized_pnl=Decimal("0"), opened_at=datetime(2026, 8, 10, 4, 0, tzinfo=UTC),
        closed_at=datetime(2026, 8, 12, 4, 0, tzinfo=UTC) if closed else None,
    )
    db.add(pos)
    await db.flush()
    return pos


# ── the R-preserving adjustment ───────────────────────────────────────────────
class TestAdjustmentMath:
    async def test_split_5to1_preserves_r_and_notional_to_the_paisa(
        self, db: AsyncSession
    ) -> None:
        user = await create_test_user(db)
        stock = await make_stock(db)
        pos = await _position(db, user.id, stock.id)  # qty 10 @ 100, SL 95, TP 120, peak 110
        ca = await record_corporate_action(
            db, stock_id=stock.id, action_type="split", ex_date=EX, ratio_from=1, ratio_to=5
        )
        r_before = abs(Decimal("100") - Decimal("95")) * 10  # 50
        notional_before = Decimal("100") * 10  # 1000

        led = await apply_ca_to_position(db, pos, ca)

        assert pos.quantity == 50
        assert pos.avg_entry_price == Decimal("20.0000")
        assert pos.current_sl == Decimal("19.0000")
        assert pos.current_tp == Decimal("24.0000")
        assert pos.peak_price == Decimal("22.0000")
        assert pos.peak_pnl == Decimal("100.00")  # ₹ P&L — invariant, untouched
        # R and notional preserved EXACTLY
        assert abs(pos.avg_entry_price - pos.current_sl) * pos.quantity == r_before
        assert pos.avg_entry_price * pos.quantity == notional_before
        assert led is not None
        assert (led.old_quantity, led.new_quantity) == (10, 50)
        assert led.factor == Decimal("5.000000")

    async def test_bonus_1to1_doubles_qty_halves_price(self, db: AsyncSession) -> None:
        user = await create_test_user(db)
        stock = await make_stock(db)
        pos = await _position(db, user.id, stock.id, qty=20, entry="200.0000", sl="190.0000",
                              tp="240.0000", peak="220.0000")
        # a 1:1 bonus → holder ends with 2 shares per 1 held → ratio 1:2
        ca = await record_corporate_action(
            db, stock_id=stock.id, action_type="bonus", ex_date=EX, ratio_from=1, ratio_to=2
        )
        await apply_ca_to_position(db, pos, ca)
        assert pos.quantity == 40
        assert pos.avg_entry_price == Decimal("100.0000")
        assert pos.current_sl == Decimal("95.0000")
        assert pos.current_tp == Decimal("120.0000")
        # R preserved: 10×20 = 5×40 = 200
        assert abs(pos.avg_entry_price - pos.current_sl) * pos.quantity == Decimal("200")

    async def test_short_position_r_preserved(self, db: AsyncSession) -> None:
        user = await create_test_user(db)
        stock = await make_stock(db)
        pos = await _position(db, user.id, stock.id, side="SHORT", qty=10, entry="100.0000",
                              sl="105.0000", tp="90.0000", peak="96.0000")
        ca = await record_corporate_action(
            db, stock_id=stock.id, action_type="split", ex_date=EX, ratio_from=1, ratio_to=5
        )
        await apply_ca_to_position(db, pos, ca)
        assert pos.quantity == 50
        assert pos.avg_entry_price == Decimal("20.0000")
        assert pos.current_sl == Decimal("21.0000")
        assert abs(pos.avg_entry_price - pos.current_sl) * pos.quantity == Decimal("50")

    async def test_non_divisible_bonus_preserves_r_within_a_paisa_and_warns(
        self, db: AsyncSession, caplog: pytest.LogCaptureFixture
    ) -> None:
        """quant-verifier HIGH regression: a fractional-entitlement bonus (qty not
        divisible by ratio_from) must NOT silently drop R. Entry follows the nominal
        ex-date scale; SL scales by distance × the floored qty so R is preserved to
        quantization (not the old ~1.5% structural drift), and it is LOGGED."""
        user = await create_test_user(db)
        stock = await make_stock(db)
        # 3-for-5 bonus (5:8) on qty 33 → 33×8//5 = 52 (52.8 floored)
        pos = await _position(db, user.id, stock.id, qty=33, entry="100.0000",
                              sl="95.0000", tp="130.0000", peak="110.0000")
        ca = await record_corporate_action(
            db, stock_id=stock.id, action_type="bonus", ex_date=EX, ratio_from=5, ratio_to=8
        )
        r_before = abs(Decimal("100") - Decimal("95")) * 33  # 165

        with caplog.at_level(logging.WARNING):
            await apply_ca_to_position(db, pos, ca)

        assert pos.quantity == 52
        assert pos.avg_entry_price == Decimal("62.5000")  # nominal 100 × 5/8, matches market
        r_after = abs(pos.avg_entry_price - pos.current_sl) * pos.quantity
        # R preserved to the paisa — quantization only, NOT the old structural −2.50 drop
        assert abs(r_after - r_before) < Decimal("0.01")
        assert "fractional entitlement" in caplog.text

    async def test_idempotent_rerun_is_noop(self, db: AsyncSession) -> None:
        user = await create_test_user(db)
        stock = await make_stock(db)
        pos = await _position(db, user.id, stock.id)
        ca = await record_corporate_action(
            db, stock_id=stock.id, action_type="split", ex_date=EX, ratio_from=1, ratio_to=5
        )
        first = await apply_ca_to_position(db, pos, ca)
        qty_after, entry_after = pos.quantity, pos.avg_entry_price

        second = await apply_ca_to_position(db, pos, ca)  # the idempotency canary

        assert first is not None and second is None
        assert pos.quantity == qty_after and pos.avg_entry_price == entry_after  # NOT re-halved
        n_ledger = (
            await db.execute(
                select(func.count())
                .select_from(PositionCorporateAction)
                .where(PositionCorporateAction.position_id == pos.id)
            )
        ).scalar()
        assert n_ledger == 1  # applied exactly once


# ── the ex-date worker ────────────────────────────────────────────────────────
class TestExDateWorker:
    async def test_adjusts_only_open_matching_positions(self, db: AsyncSession) -> None:
        user = await create_test_user(db)
        stock_a = await make_stock(db, symbol="SPLITCO")
        stock_b = await make_stock(db, symbol="OTHERCO")
        open_a = await _position(db, user.id, stock_a.id)  # adjusted
        closed_a = await _position(db, user.id, stock_a.id, closed=True)  # NOT (closed)
        open_b = await _position(db, user.id, stock_b.id)  # NOT (no CA)
        await record_corporate_action(
            db, stock_id=stock_a.id, action_type="split", ex_date=EX, ratio_from=1, ratio_to=5
        )
        await db.commit()

        applied = await apply_ex_date_corporate_actions(db, EX)
        await db.commit()

        assert len(applied) == 1
        assert open_a.quantity == 50  # adjusted
        assert closed_a.quantity == 10  # untouched — closed
        assert open_b.quantity == 10  # untouched — no CA

        # a second run is a no-op (idempotent at the ex-date level)
        assert await apply_ex_date_corporate_actions(db, EX) == []
        assert open_a.quantity == 50  # not re-adjusted

    async def test_catches_up_a_missed_past_ex_date(self, db: AsyncSession) -> None:
        """bug-hunter MED regression: `ex_date <= as_of`, so a CA whose ex-date was
        MISSED (worker down, or entered late) is still applied on a later run — a
        position left un-adjusted through a split would otherwise false-stop-out."""
        user = await create_test_user(db)
        stock = await make_stock(db)
        pos = await _position(db, user.id, stock.id)  # opened before, still open
        await record_corporate_action(
            db, stock_id=stock.id, action_type="split", ex_date=EX, ratio_from=1, ratio_to=5
        )
        await db.commit()

        # run FIVE days after the ex-date (the morning run was missed)
        applied = await apply_ex_date_corporate_actions(db, EX + timedelta(days=5))

        assert len(applied) == 1
        assert pos.quantity == 50  # caught up, not silently skipped

    async def test_future_ex_date_not_applied_early(self, db: AsyncSession) -> None:
        """A CA whose ex-date is in the FUTURE must NOT be applied before it."""
        user = await create_test_user(db)
        stock = await make_stock(db)
        pos = await _position(db, user.id, stock.id)
        await record_corporate_action(
            db, stock_id=stock.id, action_type="split", ex_date=EX, ratio_from=1, ratio_to=5
        )
        await db.commit()
        assert await apply_ex_date_corporate_actions(db, EX - timedelta(days=1)) == []
        assert pos.quantity == 10  # untouched — ex-date hasn't arrived

    async def test_no_action_on_a_day_with_no_ex_date(self, db: AsyncSession) -> None:
        assert await apply_ex_date_corporate_actions(db, date(2026, 1, 1)) == []


# ── the admin API ─────────────────────────────────────────────────────────────
async def _admin_headers(client: AsyncClient, db: AsyncSession) -> dict:
    await create_test_user(db, email="ca-admin@example.com", password="adminpass123", role="admin")
    return await get_auth_headers(client, email="ca-admin@example.com", password="adminpass123")


class TestCorporateActionApi:
    async def test_create_requires_admin(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)  # a regular user
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        await db.commit()
        r = await client.post(
            "/api/v1/corporate-actions",
            json={"stock_id": stock.id, "action_type": "split", "ex_date": "2026-08-18",
                  "ratio_from": 1, "ratio_to": 5},
            headers=headers,
        )
        assert r.status_code == 403

    async def test_create_happy_path(self, client: AsyncClient, db: AsyncSession) -> None:
        headers = await _admin_headers(client, db)
        stock = await make_stock(db)
        await db.commit()
        r = await client.post(
            "/api/v1/corporate-actions",
            json={"stock_id": stock.id, "action_type": "split", "ex_date": "2026-08-18",
                  "ratio_from": 1, "ratio_to": 5, "note": "5:1 split"},
            headers=headers,
        )
        assert r.status_code == 201
        body = r.json()
        assert body["ratio_from"] == 1 and body["ratio_to"] == 5
        assert body["action_type"] == "split" and body["source"] == "manual"

    async def test_create_bad_ratio_422(self, client: AsyncClient, db: AsyncSession) -> None:
        headers = await _admin_headers(client, db)
        stock = await make_stock(db)
        await db.commit()
        r = await client.post(
            "/api/v1/corporate-actions",
            json={"stock_id": stock.id, "action_type": "split", "ex_date": "2026-08-18",
                  "ratio_from": 0, "ratio_to": 5},
            headers=headers,
        )
        assert r.status_code == 422

    async def test_create_unknown_stock_404(self, client: AsyncClient, db: AsyncSession) -> None:
        headers = await _admin_headers(client, db)
        r = await client.post(
            "/api/v1/corporate-actions",
            json={"stock_id": 999999, "action_type": "bonus", "ex_date": "2026-08-18",
                  "ratio_from": 1, "ratio_to": 2},
            headers=headers,
        )
        assert r.status_code == 404

    async def test_create_duplicate_409(self, client: AsyncClient, db: AsyncSession) -> None:
        headers = await _admin_headers(client, db)
        stock = await make_stock(db)
        await db.commit()
        payload = {"stock_id": stock.id, "action_type": "split", "ex_date": "2026-08-18",
                   "ratio_from": 1, "ratio_to": 5}
        first = await client.post("/api/v1/corporate-actions", json=payload, headers=headers)
        assert first.status_code == 201
        dup = await client.post("/api/v1/corporate-actions", json=payload, headers=headers)
        assert dup.status_code == 409
