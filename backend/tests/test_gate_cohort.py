"""U20 — GET /analytics/cohort/{gate_key}: the trades a gate would block, as chartable data.

The would-block set is the order path's own verdict (eligibility.preview, one gate active), not a
parallel predicate. Supported for the signal-only gates (regime · diversity · R:R). Empty when no
signals exist (the current dev-DB state after the 09-07 wipe).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.models.market_data import OhlcvDaily
from app.models.signal import Signal, SignalOutcome
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock

_NOW = datetime(2026, 3, 2, 6, 0, tzinfo=UTC)


async def _sig(
    db: AsyncSession,
    stock_id: int,
    *,
    entry: str,
    sl: str,
    tp: str,
    factors: dict[str, Any],
    pnl: float | None = None,
    outcome_status: str | None = None,
    bars: bool = True,
) -> Signal:
    sig = Signal(
        stock_id=stock_id, direction="BUY", classification="swing", timeframe="1d",
        entry_price=entry, stop_loss=sl, take_profit=tp, suggested_qty=100,
        confidence_pct=80, factor_scores=factors, headline="x", status="expired",
        validity_until=_NOW + timedelta(days=5), created_at=_NOW,
        outcome_pnl_pct=Decimal(str(pnl)) if pnl is not None else None,
    )
    db.add(sig)
    await db.flush()
    if outcome_status is not None:
        db.add(SignalOutcome(
            signal_id=sig.id, stock_id=stock_id, direction="BUY", classification="swing",
            timeframe="1d", validity_until=_NOW + timedelta(days=5), status=outcome_status,
        ))
    if bars:
        for k in range(-6, 4):
            t = _NOW + timedelta(days=k)
            db.add(OhlcvDaily(
                stock_id=stock_id, time=t, open=Decimal("100"), high=Decimal("102"),
                low=Decimal("99"), close=Decimal("101"), volume=100000, is_complete=True,
            ))
    await db.flush()
    return sig


class TestGateCohort:
    async def test_requires_auth(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/analytics/cohort/rr_min")
        assert r.status_code == 401

    async def test_rr_cohort_blocks_low_reward_risk(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db, symbol="RRLOW")
        # R:R = (105-100)/(100-90) = 0.5 < 1.0 → the R:R gate would block it.
        await _sig(
            db, stock.id, entry="100.0000", sl="90.0000", tp="105.0000",
            factors={
                "DOW_TREND": {"weight": 20, "score": 0.8, "explanation": "up"},
                "MACD_CROSS": {"weight": 10, "score": 0.7, "explanation": "x"},
            },
            pnl=3.0, outcome_status="sl_first",
        )
        await db.commit()

        r = await client.get("/api/v1/analytics/cohort/rr_min", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["supported"] is True
        assert data["gate"] == "rr_gate"
        assert data["cohort_count"] == 1
        t = data["trades"][0]
        assert t["symbol"] == "RRLOW"
        assert "R:R" in t["reason"] or "reward" in t["reason"].lower()
        # risk% = |100-90|/100 = 10% ; realized_r = pnl 3% / 10% = 0.3
        assert t["realized_r"] == 0.3
        assert t["outcome_status"] == "sl_first"
        assert len(t["bars"]) > 0  # OHLC window attached

    async def test_diversity_cohort_blocks_single_factor(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """The SRTL archetype — one scoring factor clears ≥70% but the diversity gate blocks it."""
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db, symbol="SOLO")
        # R:R = 2 (won't trip R:R); ONE scoring factor (< 2) → diversity gate blocks.
        await _sig(
            db, stock.id, entry="100.0000", sl="95.0000", tp="110.0000",
            factors={
                "RSI_DIVERGENCE": {"weight": 15, "score": 0.8, "explanation": "div"},
                "ADX": {"weight": 15, "score": 0.0, "explanation": "flat"},
            },
        )
        await db.commit()

        r = await client.get("/api/v1/analytics/cohort/entry_diversity", headers=headers)
        data = r.json()
        assert data["supported"] is True
        assert data["gate"] == "entry_diversity_gate"
        assert data["cohort_count"] == 1
        assert data["trades"][0]["symbol"] == "SOLO"

    async def test_rr_cohort_excludes_healthy_rr(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """A signal with R:R ≥ 1 is NOT in the R:R would-block cohort."""
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db, symbol="RROK")
        await _sig(
            db, stock.id, entry="100.0000", sl="95.0000", tp="115.0000",  # R:R = 3
            factors={
                "DOW_TREND": {"weight": 20, "score": 0.8, "explanation": "up"},
                "MACD_CROSS": {"weight": 10, "score": 0.7, "explanation": "x"},
            },
        )
        await db.commit()

        r = await client.get("/api/v1/analytics/cohort/rr_min", headers=headers)
        data = r.json()
        assert data["supported"] is True
        assert data["cohort_count"] == 0
        assert data["scanned"] == 1

    async def test_unsupported_gate_returns_supported_false(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """A live-state gate (chase) has no signal-only cohort — supported=False, not fabricated."""
        await create_test_user(db)
        headers = await get_auth_headers(client)
        r = await client.get("/api/v1/analytics/cohort/chase", headers=headers)
        data = r.json()
        assert data["supported"] is False
        assert data["cohort_count"] == 0
        assert data["reason"]
        assert data["gate_status"] == "shadow"  # 'chase' is a known register key (shadow)

    async def test_count_is_honest_and_payload_is_bounded(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """cohort_count reflects ALL blocked among scanned; only the returned trades are capped."""
        await create_test_user(db)
        headers = await get_auth_headers(client)
        for i in range(3):
            stock = await make_stock(db, symbol=f"LOWRR{i}")
            await _sig(  # R:R 0.5 → each is blocked by the R:R gate
                db, stock.id, entry="100.0000", sl="90.0000", tp="105.0000",
                factors={
                    "DOW_TREND": {"weight": 20, "score": 0.8, "explanation": "up"},
                    "MACD_CROSS": {"weight": 10, "score": 0.7, "explanation": "x"},
                },
                bars=False,
            )
        await db.commit()

        r = await client.get("/api/v1/analytics/cohort/rr_min?limit=2", headers=headers)
        data = r.json()
        assert data["scanned"] == 3
        assert data["cohort_count"] == 3      # honest — every blocked signal counted
        assert len(data["trades"]) == 2       # payload bounded by limit

    async def test_empty_when_no_signals(self, client: AsyncClient, db: AsyncSession) -> None:
        """The current dev-DB state: supported gate, no signals → empty cohort (not an error)."""
        await create_test_user(db)
        headers = await get_auth_headers(client)
        r = await client.get("/api/v1/analytics/cohort/regime_adx", headers=headers)
        data = r.json()
        assert data["supported"] is True
        assert data["cohort_count"] == 0
        assert data["scanned"] == 0
