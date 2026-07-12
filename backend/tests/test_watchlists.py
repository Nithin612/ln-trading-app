"""Watchlist CRUD + ownership isolation (Phase 3.5 follow-up slice).

Ownership is the load-bearing behavior: every route scopes on the
authenticated user, and a foreign watchlist id must be indistinguishable
from an absent one (404 — existence never leaks).
"""

import pytest
from app.models.watchlist import WatchlistItem
from app.services.watchlist_service import watchlist_stock_ids
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock

pytestmark = pytest.mark.asyncio


async def _owner(db: AsyncSession, client: AsyncClient) -> dict[str, str]:
    await create_test_user(db, email="wl-owner@example.com")
    return await get_auth_headers(client, email="wl-owner@example.com")


async def _other(db: AsyncSession, client: AsyncClient) -> dict[str, str]:
    await create_test_user(db, email="wl-other@example.com")
    return await get_auth_headers(client, email="wl-other@example.com")


class TestWatchlistCrud:
    async def test_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/watchlists")
        assert resp.status_code == 401

    async def test_create_list_roundtrip(self, db, client) -> None:
        headers = await _owner(db, client)
        resp = await client.post(
            "/api/v1/watchlists", json={"name": "Breakouts"}, headers=headers
        )
        assert resp.status_code == 201
        created = resp.json()
        assert created["name"] == "Breakouts"
        assert created["items"] == []

        resp = await client.get("/api/v1/watchlists", headers=headers)
        assert resp.status_code == 200
        lists = resp.json()
        assert [w["name"] for w in lists] == ["Breakouts"]

    async def test_duplicate_name_409_and_empty_name_422(self, db, client) -> None:
        headers = await _owner(db, client)
        await client.post(
            "/api/v1/watchlists", json={"name": "Dup"}, headers=headers
        )
        dup = await client.post(
            "/api/v1/watchlists", json={"name": "Dup"}, headers=headers
        )
        assert dup.status_code == 409

        empty = await client.post(
            "/api/v1/watchlists", json={"name": "   "}, headers=headers
        )
        assert empty.status_code == 422

    async def test_rename_and_rename_collision(self, db, client) -> None:
        headers = await _owner(db, client)
        a = (
            await client.post(
                "/api/v1/watchlists", json={"name": "A"}, headers=headers
            )
        ).json()
        await client.post("/api/v1/watchlists", json={"name": "B"}, headers=headers)

        ok = await client.patch(
            f"/api/v1/watchlists/{a['id']}", json={"name": "A2"}, headers=headers
        )
        assert ok.status_code == 200
        assert ok.json()["name"] == "A2"

        clash = await client.patch(
            f"/api/v1/watchlists/{a['id']}", json={"name": "B"}, headers=headers
        )
        assert clash.status_code == 409

    async def test_delete_cascades_items(self, db, client) -> None:
        headers = await _owner(db, client)
        stock = await make_stock(db, symbol="WLDEL")
        wl = (
            await client.post(
                "/api/v1/watchlists", json={"name": "Doomed"}, headers=headers
            )
        ).json()
        await client.post(
            f"/api/v1/watchlists/{wl['id']}/stocks",
            json={"stock_id": stock.id},
            headers=headers,
        )

        resp = await client.delete(
            f"/api/v1/watchlists/{wl['id']}", headers=headers
        )
        assert resp.status_code == 204

        rows = await db.execute(
            select(WatchlistItem).where(WatchlistItem.watchlist_id == wl["id"])
        )
        assert rows.scalars().all() == []  # ON DELETE CASCADE, not orphaned


class TestWatchlistItems:
    async def test_add_remove_stock_with_symbols(self, db, client) -> None:
        headers = await _owner(db, client)
        s2 = await make_stock(db, symbol="ZWL2", company_name="Zed Ltd")
        s1 = await make_stock(db, symbol="AWL1", company_name="Ay Ltd")
        wl = (
            await client.post(
                "/api/v1/watchlists", json={"name": "Core"}, headers=headers
            )
        ).json()

        for sid in (s2.id, s1.id):
            resp = await client.post(
                f"/api/v1/watchlists/{wl['id']}/stocks",
                json={"stock_id": sid},
                headers=headers,
            )
            assert resp.status_code == 200
        items = resp.json()["items"]
        # joined symbol/company, sorted by symbol
        assert [(i["symbol"], i["company_name"]) for i in items] == [
            ("AWL1", "Ay Ltd"),
            ("ZWL2", "Zed Ltd"),
        ]

        # idempotent re-add
        again = await client.post(
            f"/api/v1/watchlists/{wl['id']}/stocks",
            json={"stock_id": s1.id},
            headers=headers,
        )
        assert again.status_code == 200
        assert len(again.json()["items"]) == 2

        removed = await client.delete(
            f"/api/v1/watchlists/{wl['id']}/stocks/{s1.id}", headers=headers
        )
        assert removed.status_code == 200
        assert [i["symbol"] for i in removed.json()["items"]] == ["ZWL2"]

        # idempotent re-remove
        again = await client.delete(
            f"/api/v1/watchlists/{wl['id']}/stocks/{s1.id}", headers=headers
        )
        assert again.status_code == 200

    async def test_unknown_stock_404(self, db, client) -> None:
        headers = await _owner(db, client)
        wl = (
            await client.post(
                "/api/v1/watchlists", json={"name": "X"}, headers=headers
            )
        ).json()
        resp = await client.post(
            f"/api/v1/watchlists/{wl['id']}/stocks",
            json={"stock_id": 99999999},
            headers=headers,
        )
        assert resp.status_code == 404


class TestOwnershipIsolation:
    async def test_foreign_watchlist_is_indistinguishable_from_absent(
        self, db, client
    ) -> None:
        owner_headers = await _owner(db, client)
        other_headers = await _other(db, client)
        stock = await make_stock(db, symbol="WLISO")
        wl = (
            await client.post(
                "/api/v1/watchlists", json={"name": "Private"}, headers=owner_headers
            )
        ).json()

        assert (await client.get("/api/v1/watchlists", headers=other_headers)).json() == []
        for resp in (
            await client.patch(
                f"/api/v1/watchlists/{wl['id']}", json={"name": "Stolen"},
                headers=other_headers,
            ),
            await client.delete(
                f"/api/v1/watchlists/{wl['id']}", headers=other_headers
            ),
            await client.post(
                f"/api/v1/watchlists/{wl['id']}/stocks",
                json={"stock_id": stock.id}, headers=other_headers,
            ),
        ):
            assert resp.status_code == 404

        # owner unaffected by the attempts
        mine = (await client.get("/api/v1/watchlists", headers=owner_headers)).json()
        assert [w["name"] for w in mine] == ["Private"]


class TestStockIdsService:
    async def test_none_vs_empty_distinction(self, db, client) -> None:
        """None = not yours/absent (caller must reject); set() = a real
        but empty watchlist (legitimately scopes to nothing)."""
        owner = await create_test_user(db, email="wl-svc@example.com")
        other = await create_test_user(db, email="wl-svc2@example.com")
        stock = await make_stock(db, symbol="WLSVC")

        from app.models.watchlist import Watchlist

        full = Watchlist(user_id=owner.id, name="full")
        empty = Watchlist(user_id=owner.id, name="empty")
        db.add_all([full, empty])
        await db.flush()
        db.add(WatchlistItem(watchlist_id=full.id, stock_id=stock.id))
        await db.commit()

        assert await watchlist_stock_ids(db, full.id, owner.id) == {stock.id}
        assert await watchlist_stock_ids(db, empty.id, owner.id) == set()
        assert await watchlist_stock_ids(db, full.id, other.id) is None
        assert await watchlist_stock_ids(db, 424242, owner.id) is None


class TestIdBounds:
    async def test_out_of_int64_ids_are_422_not_500(self, db, client) -> None:
        """bug-hunter LOW 2026-07-11: unbounded JSON ints reached asyncpg
        as DataError (500). Bounded at the edge now."""
        headers = await _owner(db, client)
        huge = 10**25
        resp = await client.patch(
            f"/api/v1/watchlists/{huge}", json={"name": "X"}, headers=headers
        )
        assert resp.status_code == 422
        wl = (
            await client.post(
                "/api/v1/watchlists", json={"name": "Bounds"}, headers=headers
            )
        ).json()
        resp = await client.post(
            f"/api/v1/watchlists/{wl['id']}/stocks",
            json={"stock_id": huge},
            headers=headers,
        )
        assert resp.status_code == 422
        resp = await client.delete(
            f"/api/v1/watchlists/{wl['id']}/stocks/{huge}", headers=headers
        )
        assert resp.status_code == 422
