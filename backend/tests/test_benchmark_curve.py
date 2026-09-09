"""U11 — GET /analytics/benchmark-curve: NIFTY buy-and-hold aligned to a backtest equity curve.

The equity curve is per-trade (no dates; engine frozen), so the benchmark is aligned to each trade's
exit date. The endpoint FAILS CLOSED (available=False + reason) when the comparison can't be made —
which is exactly the current dev-DB state (index_ohlcv_1d empty after the 09-07 wipe).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.models.stock import Index, IndexOhlcvDaily
from app.models.strategy import StrategyRun
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers


async def _nifty(db: AsyncSession, closes: dict[date, float]) -> int:
    idx = Index(symbol="NIFTY50", name="Nifty 50", exchange="NSE", is_active=True)
    db.add(idx)
    await db.flush()
    for d, c in closes.items():
        db.add(IndexOhlcvDaily(index_id=idx.id, trade_date=d, close=Decimal(str(c))))
    await db.flush()
    return idx.id


def _trade(entry: str, exit_: str | None, pnl: float) -> dict[str, Any]:
    return {
        "stock": "X", "direction": "BUY",
        "entry_date": entry, "exit_date": exit_, "pnl_pct": pnl,
    }


async def _make_run(
    db: AsyncSession, equity_curve: list[float], trades_json: list[dict[str, Any]]
) -> StrategyRun:
    # period_start/period_end are naive DateTime() columns — asyncpg rejects tz-aware values there.
    run = StrategyRun(
        name="U11 test run", factor_weights={}, timeframe="1d", universe="nifty50",
        period_start=datetime(2024, 1, 1), period_end=datetime(2024, 1, 20),
        total_trades=len(trades_json), winning_trades=0,
        equity_curve=equity_curve, trades_json=trades_json,
    )
    db.add(run)
    await db.flush()
    return run


class TestBenchmarkCurve:
    async def test_requires_auth(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/analytics/benchmark-curve?run_id=1")
        assert r.status_code == 401

    async def test_unknown_run_404(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)
        r = await client.get("/api/v1/analytics/benchmark-curve?run_id=999999", headers=headers)
        assert r.status_code == 404

    async def test_available_series_aligned_and_returns(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)
        await _nifty(
            db, {date(2024, 1, 1): 100.0, date(2024, 1, 10): 110.0, date(2024, 1, 20): 121.0}
        )
        run = await _make_run(
            db,
            equity_curve=[100.0, 105.0, 110.25],  # start, +5%, +5%
            trades_json=[
                _trade("2024-01-01", "2024-01-10", 5.0),
                _trade("2024-01-10", "2024-01-20", 5.0),
            ],
        )
        await db.commit()

        r = await client.get(f"/api/v1/analytics/benchmark-curve?run_id={run.id}", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["available"] is True
        assert data["symbol"] == "NIFTY50"
        # benchmark indexed to 100 at 2024-01-01, aligned to each trade's exit date.
        assert data["points"] == [100.0, 110.0, 121.0]
        assert data["benchmark_return_pct"] == 21.0
        assert data["strategy_return_pct"] == 10.25  # from equity_curve, independent of the index

    async def test_non_trading_exit_date_uses_prior_close(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """An exit on a non-index date resolves to the prior session's close (as-of), not a gap."""
        await create_test_user(db)
        headers = await get_auth_headers(client)
        await _nifty(db, {date(2024, 1, 1): 100.0, date(2024, 1, 10): 110.0})
        run = await _make_run(
            db,
            equity_curve=[100.0, 105.0],
            trades_json=[_trade("2024-01-01", "2024-01-15", 5.0)],  # 01-15 has no index bar
        )
        await db.commit()

        r = await client.get(f"/api/v1/analytics/benchmark-curve?run_id={run.id}", headers=headers)
        data = r.json()
        assert data["available"] is True
        assert data["points"] == [100.0, 110.0]  # 01-15 → latest close ≤ 15 = 01-10 = 110

    async def test_fail_closed_no_index_data(self, client: AsyncClient, db: AsyncSession) -> None:
        """The current dev-DB state: no index bars → available=False; strategy return reported."""
        await create_test_user(db)
        headers = await get_auth_headers(client)
        run = await _make_run(
            db, equity_curve=[100.0, 108.0], trades_json=[_trade("2024-01-01", "2024-01-10", 8.0)]
        )
        await db.commit()

        r = await client.get(f"/api/v1/analytics/benchmark-curve?run_id={run.id}", headers=headers)
        data = r.json()
        assert data["available"] is False
        assert "NIFTY50" in (data["reason"] or "")
        assert data["points"] == []
        assert data["benchmark_return_pct"] is None
        assert data["strategy_return_pct"] == 8.0  # still computed from the equity curve

    async def test_fail_closed_window_before_first_index_bar(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """No basis close on or before the window start → fail closed, not a substituted date."""
        await create_test_user(db)
        headers = await get_auth_headers(client)
        await _nifty(db, {date(2024, 6, 1): 100.0})  # index starts AFTER the run window
        run = await _make_run(
            db, equity_curve=[100.0, 104.0], trades_json=[_trade("2024-01-01", "2024-01-10", 4.0)]
        )
        await db.commit()

        r = await client.get(f"/api/v1/analytics/benchmark-curve?run_id={run.id}", headers=headers)
        data = r.json()
        assert data["available"] is False
        assert "on or before" in (data["reason"] or "")
