"""Integration tests for Phase 9 — Strategy Lab API.

Covers:
  - POST /strategy/runs — create a backtest run (no OHLCV data → 0 trades)
  - GET  /strategy/runs — list runs
  - GET  /strategy/runs/{id} — get single run
  - DELETE /strategy/runs/{id} — delete
  - POST /strategy/preset-scan — preset scan returns ranked entries
  - Auth enforcement (401 when no token)
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock


@pytest.fixture
async def auth_headers(client: AsyncClient, db: AsyncSession) -> dict[str, str]:
    await create_test_user(db, email="lab@example.com")
    # Seed a Nifty50 stock so the universe resolves (no OHLCV → 0 trades, still valid)
    await make_stock(db, symbol="RELIANCE", is_nifty50=True)
    return await get_auth_headers(client, email="lab@example.com")


_BASE_REQ = {
    "name": "Test run",
    "timeframe": "1d",
    "universe": "NIFTY50",
    "period_start": "2024-01-01T00:00:00",
    "period_end": "2024-12-31T23:59:59",
    "capital": "100000",
    "risk_pct": "2",
    "min_confidence": 70,
    "weight_multipliers": {},
}


class TestStrategyRunCreate:
    async def test_create_run_succeeds(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        resp = await client.post("/api/v1/strategy/runs", json=_BASE_REQ, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["name"] == "Test run"
        assert body["timeframe"] == "1d"
        assert body["universe"] == "NIFTY50"
        assert body["status"] == "done"
        assert body["total_trades"] == 0  # No OHLCV data in test DB

    async def test_create_run_with_weights(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        req = {**_BASE_REQ, "name": "Momentum heavy", "weight_multipliers": {"momentum": 1.5}}
        resp = await client.post("/api/v1/strategy/runs", json=req, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["factor_weights"].get("momentum") == 1.5

    async def test_create_run_invalid_period(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        req = {
            **_BASE_REQ,
            "period_start": "2024-12-31T00:00:00",
            "period_end": "2024-01-01T00:00:00",
        }
        resp = await client.post("/api/v1/strategy/runs", json=req, headers=auth_headers)
        assert resp.status_code == 422

    async def test_create_run_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/strategy/runs", json=_BASE_REQ)
        assert resp.status_code == 401

    async def test_equity_curve_present(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        resp = await client.post("/api/v1/strategy/runs", json=_BASE_REQ, headers=auth_headers)
        assert resp.status_code == 201
        body = resp.json()
        # With no data, equity_curve is a list with just [100.0]
        assert body["equity_curve"] is not None
        assert isinstance(body["equity_curve"], list)

    async def test_ranking_assigned(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        resp = await client.post("/api/v1/strategy/runs", json=_BASE_REQ, headers=auth_headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["ranking"] is not None
        assert body["ranking"] >= 1


class TestStrategyRunList:
    async def test_list_empty(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/api/v1/strategy/runs", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["runs"] == []

    async def test_list_returns_created_runs(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        # Create two runs
        for name in ["Run A", "Run B"]:
            await client.post(
                "/api/v1/strategy/runs", json={**_BASE_REQ, "name": name}, headers=auth_headers
            )
        resp = await client.get("/api/v1/strategy/runs", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        names = [r["name"] for r in body["runs"]]
        assert "Run A" in names
        assert "Run B" in names

    async def test_list_sort_by_sharpe(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        await client.post(
            "/api/v1/strategy/runs", json={**_BASE_REQ, "name": "X"}, headers=auth_headers
        )
        resp = await client.get("/api/v1/strategy/runs?sort_by=sharpe", headers=auth_headers)
        assert resp.status_code == 200

    async def test_list_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/strategy/runs")
        assert resp.status_code == 401


class TestStrategyRunGet:
    async def test_get_run_by_id(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        create = await client.post(
            "/api/v1/strategy/runs", json=_BASE_REQ, headers=auth_headers
        )
        run_id = create.json()["id"]

        resp = await client.get(f"/api/v1/strategy/runs/{run_id}", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == run_id
        assert body["name"] == "Test run"

    async def test_get_nonexistent_returns_404(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/api/v1/strategy/runs/99999", headers=auth_headers)
        assert resp.status_code == 404


class TestStrategyRunDelete:
    async def test_delete_run(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        create = await client.post(
            "/api/v1/strategy/runs", json=_BASE_REQ, headers=auth_headers
        )
        run_id = create.json()["id"]

        resp = await client.delete(f"/api/v1/strategy/runs/{run_id}", headers=auth_headers)
        assert resp.status_code == 204

        get = await client.get(f"/api/v1/strategy/runs/{run_id}", headers=auth_headers)
        assert get.status_code == 404

    async def test_delete_nonexistent_returns_404(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        resp = await client.delete("/api/v1/strategy/runs/99999", headers=auth_headers)
        assert resp.status_code == 404


class TestPresetScan:
    _SCAN_REQ = {
        "timeframe": "1d",
        "universe": "NIFTY50",
        "period_start": "2024-01-01T00:00:00",
        "period_end": "2024-12-31T23:59:59",
        "capital": "100000",
        "risk_pct": "2",
        "min_confidence": 70,
    }

    async def test_preset_scan_returns_all_presets(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/api/v1/strategy/preset-scan", json=self._SCAN_REQ, headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "entries" in body
        assert len(body["entries"]) > 0

        entry = body["entries"][0]
        assert "preset_name" in entry
        assert "win_rate_pct" in entry
        assert "sharpe" in entry
        assert "equity_curve" in entry

    async def test_preset_scan_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/strategy/preset-scan", json=self._SCAN_REQ)
        assert resp.status_code == 401

    async def test_preset_scan_invalid_period(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        req = {
            **self._SCAN_REQ,
            "period_start": "2025-01-01T00:00:00",
            "period_end": "2024-01-01T00:00:00",
        }
        resp = await client.post("/api/v1/strategy/preset-scan", json=req, headers=auth_headers)
        assert resp.status_code == 422
