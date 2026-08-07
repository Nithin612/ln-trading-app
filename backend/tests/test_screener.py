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


class TestFieldCoverage:
    """`GET /screener/fields` — every filterable field with how much of the
    universe it actually covers.

    A filter on a mostly-null column returns almost nothing, which reads as "no
    stocks match your criteria" rather than "this data isn't loaded". Sector sat
    at 59 of 2,333 stocks for months behind exactly that ambiguity.
    """

    async def test_requires_auth(self, client: AsyncClient) -> None:
        assert (await client.get("/api/v1/screener/fields")).status_code == 401

    async def test_counts_are_measured_not_hardcoded(
        self, client: AsyncClient, db: AsyncSession, auth_headers: dict[str, str]
    ) -> None:
        await make_stock(db, symbol="WITHSEC", sector="Energy")
        await make_stock(db, symbol="NOSEC1", sector=None)
        await make_stock(db, symbol="NOSEC2", sector=None)
        await db.commit()

        body = (await client.get("/api/v1/screener/fields", headers=auth_headers)).json()
        by_field = {f["field"]: f for f in body["fields"]}

        assert body["total_active_stocks"] == 3
        assert by_field["sector"]["populated"] == 1
        # symbol is NOT NULL, so it covers the whole universe and must not warn.
        assert by_field["symbol"]["populated"] == 3

    async def test_unavailable_fields_report_no_coverage(
        self, client: AsyncClient, db: AsyncSession, auth_headers: dict[str, str]
    ) -> None:
        """An `available=False` field has no real column — coverage is None, not 0.

        Reporting 0 would render as "0 of N stocks have this", implying the data
        merely hasn't loaded when the feature does not exist yet.
        """
        await make_stock(db, symbol="ANY")
        await db.commit()

        body = (await client.get("/api/v1/screener/fields", headers=auth_headers)).json()
        by_field = {f["field"]: f for f in body["fields"]}

        rsi = by_field["indicator.rsi_14"]
        assert rsi["available"] is False
        assert rsi["populated"] is None
        assert rsi["note"]

    async def test_market_cap_is_reported_empty_rather_than_hidden(
        self, client: AsyncClient, db: AsyncSession, auth_headers: dict[str, str]
    ) -> None:
        """Nothing populates market_cap_cr — say so instead of matching nothing."""
        await make_stock(db, symbol="ANY")
        await db.commit()

        body = (await client.get("/api/v1/screener/fields", headers=auth_headers)).json()
        by_field = {f["field"]: f for f in body["fields"]}
        assert by_field["market_cap_cr"]["populated"] == 0

    async def test_inactive_stocks_are_excluded_from_both_counts(
        self, client: AsyncClient, db: AsyncSession, auth_headers: dict[str, str]
    ) -> None:
        """Coverage is a ratio; counting deactivated rows in one side skews it.

        The 15 T2T rows deactivated on 2026-07-17 must not appear as a coverage
        hole in a universe the screener never returns them from.
        """
        await make_stock(db, symbol="LIVE", sector="Energy")
        await make_stock(db, symbol="DEAD", sector=None, is_active=False)
        await db.commit()

        body = (await client.get("/api/v1/screener/fields", headers=auth_headers)).json()
        by_field = {f["field"]: f for f in body["fields"]}
        assert body["total_active_stocks"] == 1
        assert by_field["sector"]["populated"] == 1
