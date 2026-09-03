"""Reward:risk floor overlay (2026-09-02).

The gate that enforces an IDENTITY rather than a hypothesis: at planned R:R < 1 the trade
needs a >50% win rate merely to break even, which no trend-following system sustains. That
is why it ships ACTIVE with no forward-evidence bar — there is nothing empirical to
falsify. Raising the floor above 1.0 WOULD be empirical (1.67 is fitted to our observed
37.5% win rate) and must go through the multiple-testing bar first.

Root cause it compensates for: `analysis/risk.py::compute_levels` (FROZEN) pairs a
STRUCTURAL stop with an ABSOLUTE-% target, so the ratio is an accident of pivot placement —
94 of 295 swing signals landed under 1.0.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.core.config import settings
from app.models.signal import Signal
from app.signals import eligibility, rr_guard
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock

_TWO_FACTORS = {
    "DOW_TREND": {"weight": 20, "score": 0.8, "explanation": "up"},
    "MACD_CROSS": {"weight": 15, "score": 0.6, "explanation": "x"},
}


class TestRrGuardPure:
    def test_target_further_than_stop_is_eligible(self) -> None:
        v = rr_guard.evaluate(
            entry=Decimal("500"), stop_loss=Decimal("480"), take_profit=Decimal("540")
        )
        assert v.blocked is False and v.assessable is True
        assert v.rr == Decimal("2")

    def test_target_closer_than_stop_is_blocked(self) -> None:
        """The real archetype: a 7% structural stop against the flat 6% swing target."""
        v = rr_guard.evaluate(
            entry=Decimal("100"), stop_loss=Decimal("93"), take_profit=Decimal("106")
        )
        assert v.blocked is True
        assert v.rr is not None and v.rr < 1
        assert v.reason is not None and "closer than the stop" in v.reason

    def test_exactly_at_the_floor_is_eligible(self) -> None:
        """`< rr_min`, not `<=` — R:R exactly 1.0 is break-even-at-50%, not below it."""
        v = rr_guard.evaluate(
            entry=Decimal("100"), stop_loss=Decimal("90"), take_profit=Decimal("110")
        )
        assert v.rr == Decimal("1") and v.blocked is False

    def test_short_side_is_symmetric(self) -> None:
        # A SELL: stop ABOVE entry, target BELOW. Distances are absolute, so the ratio
        # reads the same way round.
        v = rr_guard.evaluate(
            entry=Decimal("100"), stop_loss=Decimal("107"), take_profit=Decimal("94")
        )
        assert v.blocked is True and v.rr is not None and v.rr < 1

    def test_zero_risk_fails_open(self) -> None:
        """A gate that suppresses must never suppress on uncertainty. entry == SL is
        rejected elsewhere (risk_guards / sizing) on its own terms."""
        v = rr_guard.evaluate(
            entry=Decimal("100"), stop_loss=Decimal("100"), take_profit=Decimal("110")
        )
        assert v.assessable is False and v.blocked is False

    def test_a_tight_stop_is_not_caught_here(self) -> None:
        """Complementary to `sl_atr`, not redundant — and structurally disjoint: a
        too-tight stop mechanically produces a LARGE ratio (fixed % target ÷ tiny stop),
        so this gate passes it and sl_atr is the one that must catch it. Measured on the
        live inventory: 11 signals under R:R 1.0, 21 with stops < 2% of price, ZERO in
        both."""
        v = rr_guard.evaluate(
            entry=Decimal("238.21"), stop_loss=Decimal("237.26"), take_profit=Decimal("273.94")
        )
        assert v.blocked is False
        assert v.rr is not None and v.rr > 30  # the nonsense ratio a 0.4% stop produces

    def test_custom_floor_is_honoured(self) -> None:
        v = rr_guard.evaluate(
            entry=Decimal("100"), stop_loss=Decimal("90"), take_profit=Decimal("115"),
            rr_min=Decimal("2.0"),
        )
        assert v.rr == Decimal("1.5") and v.blocked is True

    def test_mode_gating(self) -> None:
        blocked = rr_guard.evaluate(
            entry=Decimal("100"), stop_loss=Decimal("93"), take_profit=Decimal("106")
        )
        assert rr_guard.order_block_reason(blocked, "off") is None
        assert rr_guard.order_block_reason(blocked, "shadow") is None
        assert rr_guard.order_block_reason(blocked, "active") is not None

    def test_payload_is_reconstructable(self) -> None:
        v = rr_guard.evaluate(
            entry=Decimal("100"), stop_loss=Decimal("93"), take_profit=Decimal("106")
        )
        p = v.as_payload()
        assert p["blocked"] is True and p["rr"] == "0.86" and p["rr_min"] == "1.0"


async def _signal(db: AsyncSession, stock_id: int, *, entry: str, sl: str, tp: str) -> Signal:
    now = datetime.now(tz=UTC)
    sig = Signal(
        stock_id=stock_id, direction="BUY", classification="swing", timeframe="1d",
        entry_price=entry, stop_loss=sl, take_profit=tp,
        suggested_qty=100, confidence_pct=80, factor_scores=_TWO_FACTORS,
        headline="BUY TEST", status="active", is_shadow=False,
        validity_until=now + timedelta(days=5), created_at=now,
    )
    db.add(sig)
    await db.flush()
    return sig


class TestRrGuardOrderPath:
    async def test_active_rejects_an_inverted_signal(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "rr_gate_mode", "active")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        sig = await _signal(db, stock.id, entry="100.0000", sl="93.0000", tp="106.0000")
        await db.commit()
        r = await client.post(
            "/api/v1/trading/orders",
            json={"signal_id": str(sig.id), "side": "BUY"}, headers=headers,
        )
        assert r.status_code == 409
        assert "reward:risk floor" in r.json()["detail"]

    async def test_shadow_does_not_block(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "rr_gate_mode", "shadow")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        sig = await _signal(db, stock.id, entry="100.0000", sl="93.0000", tp="106.0000")
        await db.commit()
        r = await client.post(
            "/api/v1/trading/orders",
            json={"signal_id": str(sig.id), "side": "BUY"}, headers=headers,
        )
        assert r.status_code == 201

    async def test_active_allows_a_healthy_ratio(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "rr_gate_mode", "active")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        sig = await _signal(db, stock.id, entry="500.0000", sl="480.0000", tp="540.0000")
        await db.commit()
        r = await client.post(
            "/api/v1/trading/orders",
            json={"signal_id": str(sig.id), "side": "BUY"}, headers=headers,
        )
        assert r.status_code == 201


class TestRrGuardDisplayPath:
    """The display path must agree with the order path — the whole point of
    `eligibility.preview`. R:R is decidable from the signal row, so it is a COVERED gate."""

    def test_rr_is_covered_not_unassessed(self) -> None:
        assert eligibility.GATE_RR in eligibility.COVERED_GATES
        assert eligibility.GATE_RR not in eligibility.UNCOVERED_GATES

    async def test_list_flags_an_inverted_signal_and_the_order_path_agrees(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "rr_gate_mode", "active")
        monkeypatch.setattr(settings, "regime_gate_mode", "shadow")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        sig = await _signal(db, stock.id, entry="100.0000", sl="93.0000", tp="106.0000")
        await db.commit()
        signal_id = str(sig.id)

        listed = (
            await client.get(
                "/api/v1/signals/active?include_expiring=true&include_choppy=true",
                headers=headers,
            )
        ).json()["signals"][0]
        assert listed["blocked"] is True
        assert listed["blocked_by"] == "rr_gate"

        order = await client.post(
            "/api/v1/trading/orders",
            json={"signal_id": signal_id, "side": "BUY"}, headers=headers,
        )
        assert order.status_code == 409
        assert order.json()["detail"] == listed["block_reason"]
