"""Phase 6.8.3 — circuit-band eligibility overlay.

Covers the four layers of the slice: the pure guard logic (direction + proximity
+ fail-open), the Redis band cache (parse/serialize/refresh/read), the order-path
wiring (shadow no-op vs active reject, verdict stamped), and the shadow report.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from app.broker.circuit_bands import (
    CIRCUIT_KEY,
    CircuitBand,
    get_circuit_band,
    parse_band,
    parse_quote_band,
    refresh_bands,
    serialize_band,
    write_band,
)
from app.core.config import settings
from app.models.signal import Signal
from app.models.trading import Order, Position
from app.services import circuit_gate_shadow as cgs
from app.signals import circuit_guard
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock

PROX = Decimal("1.5")


def _ev(
    entry: str, side: str, lower: str | None, upper: str | None
) -> circuit_guard.CircuitVerdict:
    band = (
        CircuitBand(Decimal(lower), Decimal(upper))
        if lower is not None and upper is not None
        else None
    )
    return circuit_guard.evaluate(Decimal(entry), side, band, PROX)


# ── Layer 1: the pure guard ──────────────────────────────────────────────────
class TestCircuitGuard:
    def test_long_near_lower_band_blocks(self) -> None:
        # entry 500, lower 497 → 0.6% away ≤ 1.5% → blocked
        v = _ev("500", "BUY", "497", "560")
        assert v.blocked and v.adverse == "lower" and v.side == "LONG"
        assert v.distance_pct is not None and v.distance_pct < PROX

    def test_long_far_from_lower_passes(self) -> None:
        v = _ev("500", "BUY", "400", "560")
        assert not v.blocked and v.distance_pct == Decimal("20")

    def test_short_near_upper_band_blocks(self) -> None:
        # SELL entry 500, upper 503 → 0.6% away → blocked
        v = _ev("500", "SELL", "440", "503")
        assert v.blocked and v.adverse == "upper" and v.side == "SHORT"

    def test_short_far_from_upper_passes(self) -> None:
        assert not _ev("500", "SELL", "440", "600").blocked

    def test_direction_matters_long_ignores_near_upper(self) -> None:
        """A LONG keys off the LOWER band only — a near UPPER band must NOT block it
        (a sign-flip that gated the wrong side would be a silent, expensive bug)."""
        # upper 0.4% away, lower 20% away → LONG passes
        assert not _ev("500", "BUY", "400", "502").blocked
        # the mirror: a SHORT near the LOWER band is not blocked either
        assert not _ev("500", "SELL", "502", "600").blocked

    def test_no_band_fails_open(self) -> None:
        """The fail-open canary: no cached band ⇒ eligible, has_band False."""
        v = _ev("500", "BUY", None, None)
        assert not v.blocked and not v.has_band and v.distance_pct is None

    def test_nonpositive_entry_fails_open(self) -> None:
        assert not _ev("0", "BUY", "1", "2").blocked

    def test_at_the_band_blocks(self) -> None:
        v = _ev("500", "BUY", "500", "560")
        assert v.blocked and v.distance_pct == Decimal("0")

    def test_block_reason_only_in_active_mode(self) -> None:
        blocked = _ev("500", "BUY", "497", "560")
        assert circuit_guard.order_block_reason(blocked, "off") is None
        assert circuit_guard.order_block_reason(blocked, "shadow") is None
        reason = circuit_guard.order_block_reason(blocked, "active")
        assert reason is not None and "circuit" in reason.lower()

    def test_block_reason_none_when_eligible_even_active(self) -> None:
        assert circuit_guard.order_block_reason(_ev("500", "BUY", "400", "560"), "active") is None

    def test_payload_is_json_safe_and_decimal_strings(self) -> None:
        payload = _ev("500", "BUY", "497", "560").as_payload()
        round_tripped = json.loads(json.dumps(payload))
        assert round_tripped["blocked"] is True
        assert round_tripped["entry"] == "500" and isinstance(round_tripped["entry"], str)
        assert round_tripped["lower"] == "497" and round_tripped["adverse"] == "lower"


# ── Layer 2: the Redis band cache ────────────────────────────────────────────
class TestCircuitBands:
    def test_parse_quote_band_valid(self) -> None:
        band = parse_quote_band({"lower_circuit_limit": 90.0, "upper_circuit_limit": 110.0})
        assert band == CircuitBand(Decimal("90.0"), Decimal("110.0"))

    @pytest.mark.parametrize(
        "row",
        [
            {},  # missing
            {"lower_circuit_limit": 0, "upper_circuit_limit": 110},  # zero band (index/derivative)
            {"lower_circuit_limit": 110, "upper_circuit_limit": 90},  # crossed
            {"lower_circuit_limit": None, "upper_circuit_limit": 110},
            "not-a-dict",
        ],
    )
    def test_parse_quote_band_bad_inputs_none(self, row: Any) -> None:
        assert parse_quote_band(row) is None

    def test_serialize_parse_round_trip_decimal_exact(self) -> None:
        band = CircuitBand(Decimal("123.4500"), Decimal("150.9900"))
        raw = serialize_band(7, band, ts=datetime.now(UTC).isoformat())
        assert parse_band(raw) == band

    def test_parse_band_bad_cache_entry_none(self) -> None:
        assert parse_band(None) is None
        assert parse_band("{not json") is None
        assert parse_band(json.dumps({"lower": "0", "upper": "10"})) is None  # invalid band

    async def test_refresh_and_read_round_trip(self) -> None:
        stock_a, stock_b = 90001, 90002
        token_map = {111: stock_a, 222: stock_b}

        class _FakeKite:
            def __init__(self) -> None:
                self.calls: list[list[int]] = []

            async def quote(self, instruments: list[int]) -> dict[str, Any]:
                self.calls.append(list(instruments))
                data = {
                    111: {"lower_circuit_limit": 90, "upper_circuit_limit": 110},
                    222: {"lower_circuit_limit": 45, "upper_circuit_limit": 55},
                }
                return {str(t): data[t] for t in instruments if t in data}

        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        kite = _FakeKite()
        try:
            written = await refresh_bands(r, kite, token_map, ts=datetime.now(UTC).isoformat())
            assert written == 2
            assert len(kite.calls) == 1  # ONE batched call, not per-instrument
            assert await get_circuit_band(stock_a) == CircuitBand(Decimal("90"), Decimal("110"))
            assert await get_circuit_band(stock_b) == CircuitBand(Decimal("45"), Decimal("55"))
        finally:
            await r.delete(CIRCUIT_KEY.format(stock_id=stock_a))
            await r.delete(CIRCUIT_KEY.format(stock_id=stock_b))
            await r.aclose()

    async def test_get_circuit_band_absent_is_none(self) -> None:
        assert await get_circuit_band(99999) is None


@asynccontextmanager
async def band_in_redis(stock_id: int, band: CircuitBand) -> AsyncIterator[None]:
    """Seed a live band on the real 6.8.3 Redis contract for a test's duration."""
    import redis.asyncio as aioredis

    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await write_band(r, stock_id, band, ts=datetime.now(UTC).isoformat())
        yield
    finally:
        await r.delete(CIRCUIT_KEY.format(stock_id=stock_id))
        await r.aclose()


async def _make_signal(db: AsyncSession, stock_id: int, direction: str = "BUY") -> Signal:
    now = datetime.now(tz=UTC)
    sig = Signal(
        stock_id=stock_id,
        direction=direction,
        classification="swing",
        timeframe="1d",
        entry_price="500.0000",
        stop_loss="480.0000",
        take_profit="540.0000",
        suggested_qty=100,
        confidence_pct=80,
        factor_scores={"DOW_TREND": {"weight": 20, "score": 0.8, "explanation": "uptrend"}},
        headline="BUY TEST",
        status="active",
        validity_until=now + timedelta(days=5),
        created_at=now,
    )
    db.add(sig)
    await db.flush()
    return sig


# ── Layer 3: order-path wiring (mirrors the regime-gate wiring tests) ─────────
class TestCircuitGateWiring:
    async def test_shadow_mode_does_not_block(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Default (shadow): a near-band entry still trades — the overlay is inert
        until flipped active. (The verdict stamped on the order is covered by
        TestCircuitGateShadow, which reads it back through the report; a direct DB
        re-read here would trip the shared-session greenlet context.)"""
        monkeypatch.setattr(settings, "circuit_gate_mode", "shadow")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await db.commit()

        async with band_in_redis(stock.id, CircuitBand(Decimal("497"), Decimal("560"))):
            r = await client.post(
                "/api/v1/trading/orders",
                json={"signal_id": signal.id, "side": "BUY"},
                headers=headers,
            )
        assert r.status_code == 201

    async def test_active_mode_blocks_near_band(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "circuit_gate_mode", "active")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await db.commit()

        async with band_in_redis(stock.id, CircuitBand(Decimal("497"), Decimal("560"))):
            r = await client.post(
                "/api/v1/trading/orders",
                json={"signal_id": signal.id, "side": "BUY"},
                headers=headers,
            )
        assert r.status_code == 409
        assert "circuit" in r.json()["detail"].lower()

    async def test_active_mode_allows_far_band(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "circuit_gate_mode", "active")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await db.commit()

        async with band_in_redis(stock.id, CircuitBand(Decimal("400"), Decimal("560"))):
            r = await client.post(
                "/api/v1/trading/orders",
                json={"signal_id": signal.id, "side": "BUY"},
                headers=headers,
            )
        assert r.status_code == 201

    async def test_off_mode_is_a_true_no_op(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """off mode: even a near-band entry trades — the gate is fully disabled
        (no read, no stamp, no block)."""
        monkeypatch.setattr(settings, "circuit_gate_mode", "off")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await db.commit()

        async with band_in_redis(stock.id, CircuitBand(Decimal("497"), Decimal("560"))):
            r = await client.post(
                "/api/v1/trading/orders",
                json={"signal_id": signal.id, "side": "BUY"},
                headers=headers,
            )
        assert r.status_code == 201

    async def test_active_mode_fails_open_with_no_band(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No cached band ⇒ active mode still admits the order (fail-open)."""
        monkeypatch.setattr(settings, "circuit_gate_mode", "active")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await db.commit()

        r = await client.post(
            "/api/v1/trading/orders",
            json={"signal_id": signal.id, "side": "BUY"},
            headers=headers,
        )
        assert r.status_code == 201


# ── Layer 4: the shadow report ───────────────────────────────────────────────
class TestCircuitGateShadow:
    async def test_aggregates_blocked_entries_and_outcome(self, db: AsyncSession) -> None:
        user = await create_test_user(db)
        stock = await make_stock(db)
        sig = await _make_signal(db, stock.id)
        now = datetime.now(tz=UTC)

        def _stamp(blocked: bool, has_band: bool) -> dict[str, Any]:
            return {
                "reason": "entry",
                "circuit_gate": {
                    "blocked": blocked, "has_band": has_band, "side": "LONG",
                    "adverse": "lower", "entry": "500", "lower": "497", "upper": "560",
                    "distance_pct": "0.6000", "proximity_pct": "1.5",
                },
            }

        # one blocked (resolved, net-losing), one allowed, one no-band
        for payload in (_stamp(True, True), _stamp(False, True), _stamp(False, False)):
            db.add(Order(
                user_id=user.id, signal_id=sig.id, stock_id=stock.id, mode="paper",
                side="BUY", order_type="MARKET", quantity=100, status="filled",
                placed_at=now, filled_at=now, filled_price=Decimal("500"),
                filled_qty=100, broker_payload=payload,
            ))
        # a closing order (no circuit_gate) must be ignored
        db.add(Order(
            user_id=user.id, signal_id=sig.id, stock_id=stock.id, mode="paper",
            side="SELL", order_type="MARKET", quantity=100, status="filled",
            placed_at=now, filled_at=now, filled_price=Decimal("490"),
            filled_qty=100, broker_payload={"reason": "manual"},
        ))
        # the position the blocked entry opened, closed at a loss
        db.add(Position(
            user_id=user.id, stock_id=stock.id, signal_id=sig.id, mode="paper",
            side="LONG", quantity=100, avg_entry_price=Decimal("500"),
            realized_pnl=Decimal("-1500"), opened_at=now, closed_at=now,
        ))
        await db.commit()

        r = await cgs.compute_circuit_gate_shadow(db, since=now - timedelta(days=1))
        assert r.n_evaluated == 3  # closing order excluded
        assert r.n_with_band == 2 and r.n_no_band == 1
        assert r.n_blocked == 1
        assert r.blocked_resolved == 1
        assert r.blocked_realized_total == Decimal("-1500")
        assert r.blocked[0].symbol == stock.symbol

        # readiness: only 1 resolved < target → NOT ready, but net-losing note
        ready, reason = cgs.forward_evidence_ready(r)
        assert not ready and "keep accruing" in reason
        assert "circuit-gate" in cgs.readiness_line(r)
        assert "Circuit-gate shadow" in cgs.render_markdown(r, day=now.date())

    async def test_repeat_entries_on_one_signal_not_double_counted(
        self, db: AsyncSession
    ) -> None:
        """bug-hunter MED regression: two blocked entries that average into ONE
        signal's position must count as ONE resolved trade, not two — else the
        readiness bar and the net-loss figure inflate toward a premature flip."""
        user = await create_test_user(db)
        stock = await make_stock(db)
        sig = await _make_signal(db, stock.id)
        now = datetime.now(tz=UTC)
        blocked_payload = {
            "reason": "entry",
            "circuit_gate": {
                "blocked": True, "has_band": True, "side": "LONG", "adverse": "lower",
                "entry": "500", "lower": "497", "upper": "560",
                "distance_pct": "0.6000", "proximity_pct": "1.5",
            },
        }
        for _ in range(2):  # two blocked entry orders on the SAME signal
            db.add(Order(
                user_id=user.id, signal_id=sig.id, stock_id=stock.id, mode="paper",
                side="BUY", order_type="MARKET", quantity=100, status="filled",
                placed_at=now, filled_at=now, filled_price=Decimal("500"),
                filled_qty=100, broker_payload=dict(blocked_payload),
            ))
        # ONE position (the averaged-in trade), closed at a single -1500 loss
        db.add(Position(
            user_id=user.id, stock_id=stock.id, signal_id=sig.id, mode="paper",
            side="LONG", quantity=200, avg_entry_price=Decimal("500"),
            realized_pnl=Decimal("-1500"), opened_at=now, closed_at=now,
        ))
        await db.commit()

        r = await cgs.compute_circuit_gate_shadow(db, since=now - timedelta(days=1))
        assert r.n_blocked == 2  # two blocked ENTRY orders
        assert len(r.blocked) == 1  # …but one distinct blocked name/trade
        assert r.blocked_resolved == 1  # counted ONCE, not twice
        assert r.blocked_realized_total == Decimal("-1500")  # not -3000

    async def test_reopened_positions_summed_once_per_signal(self, db: AsyncSession) -> None:
        """A signal with two closed positions (reopen) sums both, counted once."""
        user = await create_test_user(db)
        stock = await make_stock(db)
        sig = await _make_signal(db, stock.id)
        now = datetime.now(tz=UTC)
        db.add(Order(
            user_id=user.id, signal_id=sig.id, stock_id=stock.id, mode="paper",
            side="BUY", order_type="MARKET", quantity=100, status="filled",
            placed_at=now, filled_at=now, filled_price=Decimal("500"), filled_qty=100,
            broker_payload={"reason": "entry", "circuit_gate": {
                "blocked": True, "has_band": True, "side": "LONG", "adverse": "lower",
                "entry": "500", "lower": "497", "upper": "560",
                "distance_pct": "0.6", "proximity_pct": "1.5"}},
        ))
        for pnl in (Decimal("-1000"), Decimal("-500")):  # two closed positions, one signal
            db.add(Position(
                user_id=user.id, stock_id=stock.id, signal_id=sig.id, mode="paper",
                side="LONG", quantity=100, avg_entry_price=Decimal("500"),
                realized_pnl=pnl, opened_at=now, closed_at=now,
            ))
        await db.commit()

        r = await cgs.compute_circuit_gate_shadow(db, since=now - timedelta(days=1))
        assert r.blocked_resolved == 1
        assert r.blocked_realized_total == Decimal("-1500")  # -1000 + -500, summed

    async def test_empty_cohort(self, db: AsyncSession) -> None:
        r = await cgs.compute_circuit_gate_shadow(db, since=datetime.now(tz=UTC))
        assert r.n_evaluated == 0 and r.n_blocked == 0
        assert r.blocked_realized_total is None
        assert "Circuit-gate shadow" in cgs.render_markdown(r, day=datetime.now(tz=UTC).date())
