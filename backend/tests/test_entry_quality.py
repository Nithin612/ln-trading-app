"""Entry-quality overlay — the SRTL-class leak (near-single-factor signals +
stops too tight for the stock's volatility). Two independently-moded checks:
diversity (active) + sl_atr (shadow). Pure guard logic + order-path wiring."""
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
HEALTHY = {
    "DOW_TREND": {"score": 0.7, "weight": 20, "explanation": "uptrend"},
    "MACD_CROSS": {"score": 0.6, "weight": 15, "explanation": "bull cross"},
    "RSI_LEVEL": {"score": 0.5, "weight": 10, "explanation": "rising"},
}
SINGLE = {
    "RSI_DIVERGENCE": {"score": 0.8, "weight": 10, "explanation": "bullish div"},
    "ADX": {"score": 0.0, "weight": 5, "explanation": "weak"},
    "VOLUME": {"score": 0.0, "weight": 10, "explanation": "normal"},
}
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


class TestEntryQualityGuard:
    def test_factor_diversity_counts_and_share(self) -> None:
        count, share = eq.factor_diversity(HEALTHY)
        assert count == 3 and share is not None and share < D("0.6")
        count1, share1 = eq.factor_diversity(SINGLE)
        assert count1 == 1 and share1 == D("1")

    def test_single_factor_signal_flags_diversity(self) -> None:
        v = _ev(SINGLE)
        assert v.diversity_blocked and not v.sl_blocked and v.scoring_factors == 1
        assert any("single-indicator" in r for r in v.diversity_reasons)
        assert v.blocked  # the "would-suppress" property

    def test_one_dominant_factor_flags_diversity(self) -> None:
        v = _ev(DOMINATED)
        assert v.diversity_blocked and v.scoring_factors == 2
        assert any("carries it" in r for r in v.diversity_reasons)

    def test_healthy_multifactor_passes(self) -> None:
        v = _ev(HEALTHY)  # 3 balanced factors, adequate stop (SL 3 vs ATR 1)
        assert not v.blocked and not v.diversity_reasons and not v.sl_reasons

    def test_stop_too_tight_flags_sl(self) -> None:
        v = _ev(HEALTHY, entry="100", sl="99.5", atr="1.0")  # 0.5×ATR
        assert v.sl_blocked and not v.diversity_blocked and v.sl_atr_mult == D("0.5")
        assert any("too tight" in r for r in v.sl_reasons)

    def test_adequate_stop_passes(self) -> None:
        assert not _ev(HEALTHY, entry="100", sl="97", atr="1.0").blocked  # 3×ATR

    def test_absent_atr_skips_vol_check_fail_open(self) -> None:
        v = _ev(HEALTHY, entry="100", sl="99.9", atr=None)
        assert not v.sl_blocked and v.sl_atr_mult is None

    def test_malformed_factor_scores_fail_open(self) -> None:
        assert not _ev("not-a-dict", atr=None).blocked
        assert not _ev({}, atr=None).blocked

    def test_block_reason_respects_each_mode(self) -> None:
        single = _ev(SINGLE)  # diversity_blocked, not sl_blocked
        tight = _ev(HEALTHY, entry="100", sl="99.5", atr="1.0")  # sl_blocked, not diversity
        # all-shadow / all-off → never blocks
        assert eq.order_block_reason(single, "shadow", "shadow") is None
        assert eq.order_block_reason(single, "off", "off") is None
        # diversity active blocks the single-factor signal…
        r = eq.order_block_reason(single, "active", "shadow")
        assert r is not None and "single-indicator" in r
        # …but a diversity-only flag is NOT blocked when only sl_atr is active
        assert eq.order_block_reason(single, "off", "active") is None
        # sl_atr active blocks the too-tight-stop signal
        assert eq.order_block_reason(tight, "shadow", "active") is not None
        assert eq.order_block_reason(tight, "active", "off") is None  # sl flag, diversity off

    def test_payload_json_safe(self) -> None:
        rt = json.loads(json.dumps(_ev(SINGLE).as_payload()))
        assert rt["diversity_blocked"] is True and rt["sl_blocked"] is False
        assert rt["scoring_factors"] == 1 and rt["dominant_share"] == "1.0000"


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
    async def _post(self, client, db, factor_scores):
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        sig = await _signal(db, stock.id, factor_scores)
        await db.commit()
        return await client.post(
            "/api/v1/trading/orders", json={"signal_id": sig.id, "side": "BUY"}, headers=headers
        )

    async def test_diversity_active_blocks_single_factor(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "entry_diversity_gate_mode", "active")
        monkeypatch.setattr(settings, "entry_sl_atr_gate_mode", "shadow")
        r = await self._post(client, db, SINGLE)
        assert r.status_code == 409 and "entry-quality" in r.json()["detail"].lower()

    async def test_diversity_active_allows_healthy(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "entry_diversity_gate_mode", "active")
        monkeypatch.setattr(settings, "entry_sl_atr_gate_mode", "shadow")
        assert (await self._post(client, db, HEALTHY)).status_code == 201

    async def test_all_shadow_does_not_block(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "entry_diversity_gate_mode", "shadow")
        monkeypatch.setattr(settings, "entry_sl_atr_gate_mode", "shadow")
        assert (await self._post(client, db, SINGLE)).status_code == 201  # measured, not blocked

    async def test_all_off_is_a_true_no_op(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "entry_diversity_gate_mode", "off")
        monkeypatch.setattr(settings, "entry_sl_atr_gate_mode", "off")
        assert (await self._post(client, db, SINGLE)).status_code == 201

    async def test_sl_atr_active_blocks_tight_stop_via_real_atr(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When sl_atr is flipped active, a HEALTHY (diversity-passing) signal whose
        stop is tighter than 1×ATR must 409 through the endpoint's real `latest_atr`
        fetch — the seam that proves the flip fires. ATR monkeypatched (no candles)."""
        # The ATR fetch moved with the context loader in Phase 7.1 — it was never
        # API-layer code, and the RiskEngine needs it too. Patch it where it lives.
        import app.signals.restriction_context as trading_mod

        async def fake_atr(*_a, **_k):
            return Decimal("5.0")  # |100−97| = 3 < 1.0×5.0 → too tight

        monkeypatch.setattr(trading_mod, "latest_atr", fake_atr)
        monkeypatch.setattr(settings, "entry_diversity_gate_mode", "shadow")
        monkeypatch.setattr(settings, "entry_sl_atr_gate_mode", "active")
        r = await self._post(client, db, HEALTHY)
        assert r.status_code == 409 and "too tight" in r.json()["detail"].lower()

    async def test_sl_atr_active_allows_single_factor_when_diversity_shadow(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Moding is independent: diversity shadow + sl_atr active must NOT block a
        single-factor signal on the diversity axis (only sl_atr can block)."""
        # The ATR fetch moved with the context loader in Phase 7.1 — it was never
        # API-layer code, and the RiskEngine needs it too. Patch it where it lives.
        import app.signals.restriction_context as trading_mod

        async def fake_atr(*_a, **_k):
            return Decimal("0.1")  # wide vs ATR → sl passes too

        monkeypatch.setattr(trading_mod, "latest_atr", fake_atr)
        monkeypatch.setattr(settings, "entry_diversity_gate_mode", "shadow")
        monkeypatch.setattr(settings, "entry_sl_atr_gate_mode", "active")
        assert (await self._post(client, db, SINGLE)).status_code == 201


class TestNonFiniteFactorScores:
    """REGRESSION (bug-hunter LOW, 2026-09-02): a non-finite factor score raised
    `decimal.InvalidOperation` out of `factor_diversity`.

    `Decimal('nan') != 0` is True, so a NaN smuggled in as a JSON *string* (JSONB
    accepts `"nan"`) got into `contribs` and then blew up on the `total > 0` comparison.
    On the order path that cost one order; once the same helper began running on the
    signals LIST it would have turned one malformed row into a 500 for the whole page.
    An unreadable factor is simply not a scoring factor — fail open, never raise."""

    def test_nan_score_is_ignored_not_raised(self) -> None:
        count, dominant = eq.factor_diversity(
            {"RSI_DIVERGENCE": {"weight": 20, "score": "nan", "explanation": "junk"}}
        )
        assert count == 0 and dominant is None

    def test_infinite_weight_is_ignored(self) -> None:
        count, _ = eq.factor_diversity(
            {"A": {"weight": "Infinity", "score": 0.8, "explanation": ""}}
        )
        assert count == 0

    def test_nan_alongside_good_factors_keeps_the_good_ones(self) -> None:
        """The healthy factors must still count — a poisoned row degrades to its
        readable part rather than to zero."""
        count, dominant = eq.factor_diversity(
            {
                "A": {"weight": 20, "score": 0.8, "explanation": ""},
                "B": {"weight": 15, "score": 0.6, "explanation": ""},
                "BAD": {"weight": 10, "score": "nan", "explanation": ""},
            }
        )
        assert count == 2
        assert dominant is not None and dominant < Decimal("0.9")

    def test_mixed_payload_fails_closed_under_an_active_diversity_gate(self) -> None:
        """The mixed case, spelled out (quant-verifier, 2026-09-02): {nan, 0.8} reads as
        ONE scoring factor, so an ACTIVE diversity gate BLOCKS it. That is fail-CLOSED,
        and intentional — one readable factor IS a single indicator, which SIGNAL_ENGINE
        §1/§2 forbids. Only an ALL-unreadable payload yields count 0 and fails open."""
        v = eq.evaluate(
            entry=Decimal("100"),
            stop_loss=Decimal("96"),
            factor_scores={
                "BAD": {"weight": 20, "score": "nan", "explanation": ""},
                "GOOD": {"weight": 15, "score": 0.8, "explanation": ""},
            },
            atr=None,
            min_scoring_factors=2,
            max_dominant_share=Decimal("0.9"),
            min_sl_atr_mult=Decimal("1.0"),
        )
        assert v.scoring_factors == 1
        assert v.diversity_blocked is True, "one readable factor is a single indicator"
        assert eq.order_block_reason(v, "active", "off") is not None

    def test_evaluate_survives_a_nan_payload(self) -> None:
        """End-to-end through the overlay: no raise, and the poisoned payload reads as
        ZERO scoring factors — which `evaluate` deliberately FAILS OPEN on
        (`count > 0` guard, entry_quality.py:130: "a payload we couldn't read fails open
        rather than flagging every such signal"). So the signal is not blocked on the
        diversity axis. That is the intended trade-off: a gate that suppresses must not
        suppress on uncertainty. The point of this test is that it does not RAISE."""
        v = eq.evaluate(
            entry=Decimal("100"),
            stop_loss=Decimal("96"),
            factor_scores={"A": {"weight": 20, "score": "nan", "explanation": ""}},
            atr=None,
            min_scoring_factors=2,
            max_dominant_share=Decimal("0.9"),
            min_sl_atr_mult=Decimal("1.0"),
        )
        assert v.diversity_blocked is False, "unreadable payload must fail OPEN, not block"
        assert v.scoring_factors == 0
