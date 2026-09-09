"""U19 — GET /analytics/cohort/{gate_key}/horizon: mean R + %-reaching-+1R by holding day.

Flagged (would-block) vs passed (would-allow), split by the order path's own verdict. Traces each
signal's realized R forward from entry over daily bars. Empty when signals are absent (dev DB).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.models.market_data import OhlcvDaily
from app.models.signal import Signal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock

_NOW = datetime(2026, 3, 2, 6, 0, tzinfo=UTC)


async def _sig_with_path(
    db: AsyncSession, symbol: str, *, entry: str, sl: str, tp: str,
    path: list[tuple[float, float, float, float]],  # per day: (open, high, low, close)
) -> Signal:
    stock = await make_stock(db, symbol=symbol)
    sig = Signal(
        stock_id=stock.id, direction="BUY", classification="swing", timeframe="1d",
        entry_price=entry, stop_loss=sl, take_profit=tp, suggested_qty=100,
        confidence_pct=80, headline="x", status="expired",
        factor_scores={
            "DOW_TREND": {"weight": 20, "score": 0.8, "explanation": "up"},
            "MACD_CROSS": {"weight": 10, "score": 0.7, "explanation": "x"},
        },
        validity_until=_NOW + timedelta(days=10), created_at=_NOW,
    )
    db.add(sig)
    await db.flush()
    for k, (o, h, low, c) in enumerate(path):
        db.add(OhlcvDaily(
            stock_id=stock.id, time=datetime(2026, 3, 2, tzinfo=UTC) + timedelta(days=k),
            open=Decimal(str(o)), high=Decimal(str(h)), low=Decimal(str(low)),
            close=Decimal(str(c)), volume=100000, is_complete=True,
        ))
    await db.flush()
    return sig


def _pt(data: dict[str, Any], day: int) -> dict[str, Any]:
    return next(p for p in data["points"] if p["day"] == day)


class TestGateHorizon:
    async def test_requires_auth(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/analytics/cohort/rr_min/horizon")
        assert r.status_code == 401

    async def test_flagged_vs_passed_r_by_day(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)
        # The entry candle (bar 0, the created_at date) is EXCLUDED — entry == its close, so its own
        # R is a same-bar artifact. Holding day 1 = the FIRST session after entry (bar 1).
        # FLAGGED (R:R 0.5 < 1 → blocked by the R:R gate). risk = 10.
        # day1 close 110 → R +1.0, high 111 → +1R by day 1 ; day2 close 105 → R 0.5
        await _sig_with_path(
            db, "FLAG", entry="100.0000", sl="90.0000", tp="105.0000",
            path=[(100, 100, 100, 100), (100, 111, 100, 110), (110, 110, 104, 105)],
        )
        # PASSED (R:R 3 ≥ 1 → not blocked). risk = 5.
        # day1 close 90 → R -2.0, high 101 → no +1R ; day2 close 92 → R -1.6
        await _sig_with_path(
            db, "PASS", entry="100.0000", sl="95.0000", tp="115.0000",
            path=[(100, 100, 100, 100), (100, 101, 89, 90), (92, 92, 90, 92)],
        )
        await db.commit()

        r = await client.get("/api/v1/analytics/cohort/rr_min/horizon", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["supported"] is True
        assert data["flagged_total"] == 1
        assert data["passed_total"] == 1
        # No day-0 point — the horizon starts at the first tradeable session (N+1).
        assert min(p["day"] for p in data["points"]) == 1

        d1 = _pt(data, 1)
        assert d1["flagged_mean_r"] == 1.0
        assert d1["passed_mean_r"] == -2.0
        assert d1["flagged_n"] == 1 and d1["passed_n"] == 1
        assert d1["flagged_hit_ge_1r"] == 1.0   # flagged reached +1R by the first session
        assert d1["passed_hit_ge_1r"] == 0.0     # passed did not

        d2 = _pt(data, 2)
        assert d2["flagged_mean_r"] == 0.5
        assert d2["passed_mean_r"] == -1.6

    async def test_unsupported_gate(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)
        r = await client.get("/api/v1/analytics/cohort/chase/horizon", headers=headers)
        data = r.json()
        assert data["supported"] is False
        assert data["reason"]
        assert data["gate_status"] == "shadow"

    async def test_empty_when_no_signals(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)
        r = await client.get("/api/v1/analytics/cohort/rr_min/horizon", headers=headers)
        data = r.json()
        assert data["supported"] is True
        assert data["flagged_total"] == 0 and data["passed_total"] == 0
        assert all(p["flagged_mean_r"] is None for p in data["points"])
