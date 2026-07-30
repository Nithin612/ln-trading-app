"""
Tests for the stock list and detail endpoints.

All tests use a real Postgres test database (see conftest.py).
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
    stocks = [
        await make_stock(db, symbol="RELIANCE", company_name="Reliance Industries Ltd",
                         sector="Energy", is_nifty50=True, is_fno=True, lot_size=250),
        await make_stock(db, symbol="INFY", company_name="Infosys Ltd",
                         sector="IT", is_nifty50=True, is_fno=True, lot_size=300),
        await make_stock(db, symbol="AXISBANK", company_name="Axis Bank Ltd",
                         sector="Financial Services", is_banknifty=True,
                         is_fno=True, lot_size=1200),
        await make_stock(db, symbol="TATAPOWER", company_name="Tata Power Company Ltd",
                         sector="Energy", is_fno=True, lot_size=1375),
        await make_stock(db, symbol="IRFC", company_name="Indian Railway Finance Corp",
                         sector="Financial Services", is_fno=False, is_nifty50=False),
    ]
    return stocks


class TestStockList:
    async def test_list_returns_all_active(
        self, client: AsyncClient, auth_headers: dict, sample_stocks: list[Stock]
    ) -> None:
        resp = await client.get("/api/v1/stocks", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 5

    async def test_pagination(
        self, client: AsyncClient, auth_headers: dict, sample_stocks: list[Stock]
    ) -> None:
        resp = await client.get(
            "/api/v1/stocks", params={"page": 1, "page_size": 2}, headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["pages"] == 3

    async def test_sort_by_symbol_asc(
        self, client: AsyncClient, auth_headers: dict, sample_stocks: list[Stock]
    ) -> None:
        resp = await client.get(
            "/api/v1/stocks", params={"sort_by": "symbol", "sort_dir": "asc"},
            headers=auth_headers,
        )
        symbols = [s["symbol"] for s in resp.json()["items"]]
        assert symbols == sorted(symbols)

    async def test_filter_is_nifty50(
        self, client: AsyncClient, auth_headers: dict, sample_stocks: list[Stock]
    ) -> None:
        resp = await client.get(
            "/api/v1/stocks", params={"is_nifty50": True}, headers=auth_headers
        )
        data = resp.json()
        assert data["total"] == 2
        assert all(s["is_nifty50"] for s in data["items"])

    async def test_filter_is_fno(
        self, client: AsyncClient, auth_headers: dict, sample_stocks: list[Stock]
    ) -> None:
        resp = await client.get(
            "/api/v1/stocks", params={"is_fno": True}, headers=auth_headers
        )
        assert resp.json()["total"] == 4

    async def test_filter_sector(
        self, client: AsyncClient, auth_headers: dict, sample_stocks: list[Stock]
    ) -> None:
        resp = await client.get(
            "/api/v1/stocks", params={"sector": "Energy"}, headers=auth_headers
        )
        assert resp.json()["total"] == 2

    async def test_fuzzy_search_by_symbol(
        self, client: AsyncClient, auth_headers: dict, sample_stocks: list[Stock]
    ) -> None:
        resp = await client.get(
            "/api/v1/stocks", params={"q": "RELI"}, headers=auth_headers
        )
        assert resp.status_code == 200
        symbols = [s["symbol"] for s in resp.json()["items"]]
        assert "RELIANCE" in symbols

    async def test_search_ranks_prefix_over_bigger_cap_substring(
        self, client: AsyncClient, auth_headers: dict, db: AsyncSession
    ) -> None:
        """Regression: search used to order by market cap, burying the intended
        match. A prefix match must beat a bigger-cap non-prefix match."""
        from decimal import Decimal

        ts = await make_stock(db, symbol="TATASTEEL", company_name="Tata Steel Ltd")
        ts.market_cap_cr = Decimal("50000")
        # XTATAY contains "TATA" (substring) but is not a prefix match
        xy = await make_stock(db, symbol="XTATAY", company_name="X Tata Y Ltd")
        xy.market_cap_cr = Decimal("999999")  # far larger cap
        await db.commit()

        resp = await client.get(
            "/api/v1/stocks",
            params={"q": "TATA", "sort_by": "market_cap_cr", "sort_dir": "desc"},
            headers=auth_headers,
        )
        symbols = [s["symbol"] for s in resp.json()["items"]]
        assert symbols[0] == "TATASTEEL"  # prefix wins despite ~20× smaller cap
        assert symbols.index("TATASTEEL") < symbols.index("XTATAY")

    async def test_search_drops_low_similarity_noise(
        self, client: AsyncClient, auth_headers: dict, db: AsyncSession
    ) -> None:
        """Regression: the 0.1 trigram threshold dredged up near-unrelated
        symbols (e.g. ATAM for 'TATA'). ATAM must no longer be a match."""
        await make_stock(db, symbol="TATASTEEL", company_name="Tata Steel Ltd")
        await make_stock(db, symbol="ATAM", company_name="Atam Valves Ltd")
        await db.commit()

        resp = await client.get(
            "/api/v1/stocks", params={"q": "TATA"}, headers=auth_headers
        )
        symbols = [s["symbol"] for s in resp.json()["items"]]
        assert "TATASTEEL" in symbols
        assert "ATAM" not in symbols  # canary: matched on the old 0.1 threshold

    async def test_search_matches_substring_in_symbol(
        self, client: AsyncClient, auth_headers: dict, db: AsyncSession
    ) -> None:
        await make_stock(db, symbol="HDFCBANK", company_name="HDFC Bank Ltd")
        await make_stock(db, symbol="ICICIBANK", company_name="ICICI Bank Ltd")
        await db.commit()

        resp = await client.get(
            "/api/v1/stocks", params={"q": "BANK"}, headers=auth_headers
        )
        symbols = [s["symbol"] for s in resp.json()["items"]]
        assert "HDFCBANK" in symbols and "ICICIBANK" in symbols

    async def test_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/stocks")
        assert resp.status_code == 401


class TestStockDetail:
    async def test_get_existing_stock(
        self, client: AsyncClient, auth_headers: dict, sample_stocks: list[Stock]
    ) -> None:
        stock_id = sample_stocks[0].id
        resp = await client.get(f"/api/v1/stocks/{stock_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "RELIANCE"
        assert data["is_nifty50"] is True

    async def test_get_nonexistent_stock(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        resp = await client.get("/api/v1/stocks/99999", headers=auth_headers)
        assert resp.status_code == 404
