"""Entry-quality overlay — the SRTL-class leak (near-single-factor signals + stops
too tight for the stock's volatility). Pure guard logic + order-path wiring."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.core.config import settings
from app.models.signal import Signal
from app.signals import entry_quality as eq
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock

D = Decimal
# A balanced, genuine multi-factor confluence (3 factors, no single dominant one).
HEALTHY = {
    "DOW_TREND": {"score": 0.7, "weight": 20, "explanation": "uptrend"},
    "MACD_CROSS": {"score": 0.6, "weight": 15, "explanation": "bull cross"},
    "RSI_LEVEL": {"score": 0.5, "weight": 10, "explanation": "rising"},
}
# SRTL: one factor carries the whole 80% (every other factor 0.0).
SINGLE = {
    "RSI_DIVERGENCE": {"score": 0.8, "weight": 10, "explanation": "bullish div"},
    "ADX": {"score": 0.0, "weight": 5, "explanation": "weak"},
    "VOLUME": {"score": 0.0, "weight": 10, "explanation": "normal"},
}
# Two scoring factors but one is 99.8% of the confluence (a noise second factor).
DOMINATED = {
    "RSI_DIVERGENCE": {"score": 0.8, "weight": 30, "explanation": "div"},
    "VOLUME": {"score": 0.01, "weight": 5, "explanation": "trace"},
}


def _ev(factor_scores, *, entry="100", sl="97", atr="1.0"):
    return eq.evaluate(
        entry=D(entry), stop_loss=D(sl), factor_scores=factor_scores,
        atr=D(atr) if atr is not None else None,
        min_scoring_factors=2, max_dominant_share=D("0.90"), min_sl_atr_mult=D("1.0"),
    )


# ── pure guard ────────────────────────────────────────────────────────────────
class TestEntryQualityGuard:
    def test_factor_diversity_counts_and_share(self) -> None:
        count, share = eq.factor_diversity(HEALTHY)
        assert count == 3 and share is not None and share < D("0.6")
        count1, share1 = eq.factor_diversity(SINGLE)
        assert count1 == 1 and share1 == D("1")  # only one factor scored

    def test_single_factor_signal_blocks(self) -> None:
        v = _ev(SINGLE)
        assert v.blocked and v.scoring_factors == 1
        assert any("single-indicator" in r for r in v.reasons)

    def test_one_dominant_factor_blocks(self) -> None:
        v = _ev(DOMINATED)
        assert v.blocked and v.scoring_factors == 2
        assert any("carries it" in r for r in v.reasons)

    def test_healthy_multifactor_passes(self) -> None:
        v = _ev(HEALTHY)  # 3 balanced factors, adequate stop (SL 3 vs ATR 1)
        assert not v.blocked and v.reasons == []

    def test_stop_too_tight_for_volatility_blocks(self) -> None:
        # healthy factors, but SL 0.5 vs ATR 1.0 → 0.5×ATR < 1×
        v = _ev(HEALTHY, entry="100", sl="99.5", atr="1.0")
        assert v.blocked and v.sl_atr_mult == D("0.5")
        assert any("too tight" in r for r in v.reasons)

    def test_adequate_stop_passes(self) -> None:
        v = _ev(HEALTHY, entry="100", sl="97", atr="1.0")  # 3×ATR
        assert not v.blocked

    def test_absent_atr_skips_vol_check_fail_open(self) -> None:
        # a very tight stop but no ATR → the vol dimension can't judge → not blocked
        v = _ev(HEALTHY, entry="100", sl="99.9", atr=None)
        assert not v.blocked and v.sl_atr_mult is None

    def test_malformed_factor_scores_fail_open(self) -> None:
        assert not _ev("not-a-dict", atr=None).blocked
        assert not _ev({}, atr=None).blocked  # nothing parsed → not judged

    def test_block_reason_only_active(self) -> None:
        v = _ev(SINGLE)
        assert eq.order_block_reason(v, "off") is None
        assert eq.order_block_reason(v, "shadow") is None
        r = eq.order_block_reason(v, "active")
        assert r is not None and "entry-quality" in r.lower()

    def test_payload_json_safe(self) -> None:
        payload = _ev(SINGLE).as_payload()
        rt = json.loads(json.dumps(payload))
        assert rt["blocked"] is True and rt["scoring_factors"] == 1
        assert rt["dominant_share"] == "1.0000"


# ── order-path wiring ─────────────────────────────────────────────────────────
async def _signal(db, stock_id, factor_scores, *, entry="100.0000", sl="97.0000"):
    now = datetime.now(tz=UTC)
    sig = Signal(
        stock_id=stock_id, direction="BUY", classification="swing", timeframe="1d",
        entry_price=entry, stop_loss=sl, take_profit="115.0000", suggested_qty=100,
        confidence_pct=80, factor_scores=factor_scores, headline="BUY TEST", status="active",
        validity_until=now + timedelta(days=5), created_at=now,
    )
    db.add(sig)
    await db.flush()
    return sig


class TestEntryQualityWiring:
    async def test_shadow_does_not_block_single_factor(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "entry_quality_gate_mode", "shadow")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        sig = await _signal(db, stock.id, SINGLE)
        await db.commit()
        r = await client.post(
            "/api/v1/trading/orders", json={"signal_id": sig.id, "side": "BUY"}, headers=headers
        )
        assert r.status_code == 201  # shadow: measured, not blocked

    async def test_active_blocks_single_factor(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "entry_quality_gate_mode", "active")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        sig = await _signal(db, stock.id, SINGLE)  # no ATR data → only diversity fires
        await db.commit()
        r = await client.post(
            "/api/v1/trading/orders", json={"signal_id": sig.id, "side": "BUY"}, headers=headers
        )
        assert r.status_code == 409
        assert "entry-quality" in r.json()["detail"].lower()

    async def test_active_allows_healthy(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "entry_quality_gate_mode", "active")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        sig = await _signal(db, stock.id, HEALTHY)  # 3 factors, no ATR → vol skipped
        await db.commit()
        r = await client.post(
            "/api/v1/trading/orders", json={"signal_id": sig.id, "side": "BUY"}, headers=headers
        )
        assert r.status_code == 201

    async def test_off_is_a_true_no_op(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "entry_quality_gate_mode", "off")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        sig = await _signal(db, stock.id, SINGLE)
        await db.commit()
        r = await client.post(
            "/api/v1/trading/orders", json={"signal_id": sig.id, "side": "BUY"}, headers=headers
        )
        assert r.status_code == 201
