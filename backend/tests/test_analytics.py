"""Outcome analytics API — per-style aggregate over signal_outcomes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.models.profile import StrategyProfile
from app.models.signal import Signal, SignalOutcome
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_profile, make_stock


async def _signal_with_outcome(
    db: AsyncSession,
    stock_id: int,
    profile: StrategyProfile,
    status: str,
    pnl_pct: float | None,
    *,
    direction: str = "BUY",
    classification: str = "swing",
    entered: bool = True,
) -> Signal:
    now = datetime.now(tz=UTC)  # >= OUTCOME_EPOCH (2026-07-19)
    sig = Signal(
        stock_id=stock_id,
        direction=direction,
        classification=classification,
        timeframe="1d",
        entry_price="500.0000",
        stop_loss="480.0000",
        take_profit="540.0000",
        suggested_qty=100,
        confidence_pct=80,
        factor_scores={},
        headline="x",
        status="expired",  # resolved — avoids the active-signal dedup index
        validity_until=now + timedelta(days=5),
        created_at=now,
        profile_id=profile.id,
        profile_key=profile.key,
        outcome_pnl_pct=Decimal(str(pnl_pct)) if pnl_pct is not None else None,
    )
    db.add(sig)
    await db.flush()
    db.add(SignalOutcome(
        signal_id=sig.id,
        stock_id=stock_id,
        direction=direction,
        classification=classification,
        timeframe="1d",
        validity_until=now + timedelta(days=5),
        status=status,
        entry_touched_at=now if entered else None,
    ))
    await db.flush()
    return sig


class TestOutcomeAnalytics:
    async def test_requires_auth(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/analytics/outcomes")
        assert r.status_code == 401

    async def test_empty_returns_all_four_styles(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)
        r = await client.get("/api/v1/analytics/outcomes", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total_outcomes"] == 0
        assert {s["style"] for s in data["styles"]} == {"intraday", "swing", "fno", "investment"}
        assert all(s["hit_rate"] is None and s["total"] == 0 for s in data["styles"])

    async def test_aggregates_per_style(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        swing = await make_profile(db, key="rrbo", style="swing")

        # swing: 2 wins (+6, +5), 1 loss (-2), 1 no-entry (null pnl, not entered)
        await _signal_with_outcome(db, stock.id, swing, "tp_first", 6.0)
        await _signal_with_outcome(db, stock.id, swing, "tp_first", 5.0)
        await _signal_with_outcome(db, stock.id, swing, "sl_first", -2.0)
        await _signal_with_outcome(db, stock.id, swing, "expired_untouched", None, entered=False)
        await db.commit()

        r = await client.get("/api/v1/analytics/outcomes", headers=headers)
        assert r.status_code == 200
        data = r.json()
        styles = {s["style"]: s for s in data["styles"]}
        assert data["total_outcomes"] == 4

        sw = styles["swing"]
        assert sw["total"] == 4
        assert sw["wins"] == 2 and sw["losses"] == 1 and sw["no_entry"] == 1
        assert sw["entered"] == 3
        assert sw["sample"] == 4
        assert abs(sw["hit_rate"] - 2 / 3) < 1e-9         # wins / (wins+losses)
        assert abs(sw["entry_rate"] - 3 / 4) < 1e-9
        assert abs(sw["avg_return_pct"] - (6.0 + 5.0 - 2.0) / 3) < 1e-6  # avg of non-null pnl = 3.0

        # untouched styles stay zeroed
        assert styles["intraday"]["total"] == 0
        assert styles["intraday"]["hit_rate"] is None

    async def test_cohort_excludes_pre_epoch_signals(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """Signals created before OUTCOME_EPOCH must not count (straddler bias)."""
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        swing = await make_profile(db, key="rrbo", style="swing")
        sig = await _signal_with_outcome(db, stock.id, swing, "tp_first", 6.0)
        sig.created_at = datetime(2026, 7, 1, tzinfo=UTC)  # before the 07-19 epoch
        await db.commit()

        r = await client.get("/api/v1/analytics/outcomes", headers=headers)
        styles = {s["style"]: s for s in r.json()["styles"]}
        assert styles["swing"]["total"] == 0  # excluded by the cohort filter
