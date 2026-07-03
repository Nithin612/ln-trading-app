"""
Tests for the screener compiler and saved-screens API.
"""
from __future__ import annotations

import pytest
from app.models.stock import Stock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock


@pytest.fixture
async def auth_headers(client: AsyncClient, db: AsyncSession) -> dict[str, str]:
    await create_test_user(db)
    return await get_auth_headers(client)


@pytest.fixture
async def sample_stocks(db: AsyncSession) -> list[Stock]:
    return [
        await make_stock(db, symbol="RELIANCE", company_name="Reliance Industries",
                         sector="Energy", is_nifty50=True, is_fno=True, lot_size=250),
        await make_stock(db, symbol="INFY", company_name="Infosys Ltd",
                         sector="IT", is_nifty50=True, is_fno=True, lot_size=300),
        await make_stock(db, symbol="AXISBANK", company_name="Axis Bank Ltd",
                         sector="Financial Services", is_banknifty=True,
                         is_fno=True, lot_size=1200),
    ]


class TestScreenerRun:
    async def test_empty_filters_returns_all_active(
        self, client: AsyncClient, auth_headers: dict, sample_stocks: list[Stock]
    ) -> None:
        resp = await client.post(
            "/api/v1/screener/run",
            json={"filters": [], "logic": "AND"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 3

    async def test_filter_is_nifty50_eq_true(
        self, client: AsyncClient, auth_headers: dict, sample_stocks: list[Stock]
    ) -> None:
        resp = await client.post(
            "/api/v1/screener/run",
            json={"filters": [{"field": "is_nifty50", "op": "eq", "value": True}]},
            headers=auth_headers,
        )
        data = resp.json()
        assert data["total"] == 2
        assert all(s["is_nifty50"] for s in data["items"])

    async def test_filter_sector_eq(
        self, client: AsyncClient, auth_headers: dict, sample_stocks: list[Stock]
    ) -> None:
        resp = await client.post(
            "/api/v1/screener/run",
            json={"filters": [{"field": "sector", "op": "eq", "value": "IT"}]},
            headers=auth_headers,
        )
        assert resp.json()["total"] == 1

    async def test_filter_lot_size_gte(
        self, client: AsyncClient, auth_headers: dict, sample_stocks: list[Stock]
    ) -> None:
        resp = await client.post(
            "/api/v1/screener/run",
            json={"filters": [{"field": "lot_size", "op": "gte", "value": 300}]},
            headers=auth_headers,
        )
        assert resp.json()["total"] == 2

    async def test_filter_lot_size_between(
        self, client: AsyncClient, auth_headers: dict, sample_stocks: list[Stock]
    ) -> None:
        resp = await client.post(
            "/api/v1/screener/run",
            json={"filters": [{"field": "lot_size", "op": "between", "value": [200, 400]}]},
            headers=auth_headers,
        )
        assert resp.json()["total"] == 2

    async def test_filter_symbol_in(
        self, client: AsyncClient, auth_headers: dict, sample_stocks: list[Stock]
    ) -> None:
        resp = await client.post(
            "/api/v1/screener/run",
            json={"filters": [{"field": "symbol", "op": "in", "value": ["RELIANCE", "INFY"]}]},
            headers=auth_headers,
        )
        assert resp.json()["total"] == 2

    async def test_or_logic(
        self, client: AsyncClient, auth_headers: dict, sample_stocks: list[Stock]
    ) -> None:
        resp = await client.post(
            "/api/v1/screener/run",
            json={
                "filters": [
                    {"field": "sector", "op": "eq", "value": "Energy"},
                    {"field": "sector", "op": "eq", "value": "IT"},
                ],
                "logic": "OR",
            },
            headers=auth_headers,
        )
        assert resp.json()["total"] == 2

    async def test_unknown_field_rejected(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        resp = await client.post(
            "/api/v1/screener/run",
            json={"filters": [{"field": "malicious_field", "op": "eq", "value": True}]},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_unavailable_phase4_field_rejected(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        resp = await client.post(
            "/api/v1/screener/run",
            json={"filters": [{"field": "indicator.rsi_14", "op": "gte", "value": 40}]},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_invalid_op_for_bool_field_rejected(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        resp = await client.post(
            "/api/v1/screener/run",
            json={"filters": [{"field": "is_nifty50", "op": "gt", "value": True}]},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_between_requires_two_values(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        resp = await client.post(
            "/api/v1/screener/run",
            json={"filters": [{"field": "lot_size", "op": "between", "value": [100]}]},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_pagination_via_limit_offset(
        self, client: AsyncClient, auth_headers: dict, sample_stocks: list[Stock]
    ) -> None:
        resp = await client.post(
            "/api/v1/screener/run",
            json={"filters": [], "limit": 2, "offset": 0},
            headers=auth_headers,
        )
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 3

    async def test_invalid_logic_rejected(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        resp = await client.post(
            "/api/v1/screener/run",
            json={"filters": [], "logic": "XOR"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/screener/run", json={"filters": []})
        assert resp.status_code == 401


class TestSavedScreens:
    async def test_create_and_list(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        payload = {
            "name": "Nifty50 F&O",
            "filter_spec": {
                "filters": [
                    {"field": "is_nifty50", "op": "eq", "value": True},
                    {"field": "is_fno", "op": "eq", "value": True},
                ],
                "logic": "AND",
                "sort_by": "symbol",
                "sort_dir": "asc",
                "limit": 50,
                "offset": 0,
            },
        }
        create_resp = await client.post(
            "/api/v1/screener/saved", json=payload, headers=auth_headers
        )
        assert create_resp.status_code == 201
        assert create_resp.json()["name"] == "Nifty50 F&O"

        list_resp = await client.get("/api/v1/screener/saved", headers=auth_headers)
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

    async def test_duplicate_name_rejected(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        payload = {
            "name": "My Screen",
            "filter_spec": {"filters": [], "logic": "AND", "sort_by": "symbol",
                            "sort_dir": "asc", "limit": 50, "offset": 0},
        }
        await client.post("/api/v1/screener/saved", json=payload, headers=auth_headers)
        resp = await client.post(
            "/api/v1/screener/saved", json=payload, headers=auth_headers
        )
        assert resp.status_code == 409

    async def test_delete(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        payload = {
            "name": "To Delete",
            "filter_spec": {"filters": [], "logic": "AND", "sort_by": "symbol",
                            "sort_dir": "asc", "limit": 50, "offset": 0},
        }
        created = await client.post(
            "/api/v1/screener/saved", json=payload, headers=auth_headers
        )
        screen_id = created.json()["id"]

        del_resp = await client.delete(
            f"/api/v1/screener/saved/{screen_id}", headers=auth_headers
        )
        assert del_resp.status_code == 204

        list_resp = await client.get("/api/v1/screener/saved", headers=auth_headers)
        assert list_resp.json() == []

    async def test_cannot_delete_another_users_screen(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        # user A creates a screen
        await create_test_user(db, email="user_a@example.com")
        headers_a = await get_auth_headers(client, email="user_a@example.com")
        payload = {
            "name": "User A Screen",
            "filter_spec": {"filters": [], "logic": "AND", "sort_by": "symbol",
                            "sort_dir": "asc", "limit": 50, "offset": 0},
        }
        created = await client.post(
            "/api/v1/screener/saved", json=payload, headers=headers_a
        )
        screen_id = created.json()["id"]

        # user B tries to delete it
        await create_test_user(db, email="user_b@example.com")
        headers_b = await get_auth_headers(client, email="user_b@example.com")
        resp = await client.delete(
            f"/api/v1/screener/saved/{screen_id}", headers=headers_b
        )
        assert resp.status_code == 404
