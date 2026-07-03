"""
Phase 3 — Category tests.

Covers:
- Category CRUD (create, list, get, update, delete)
- Admin-only enforcement
- Slug auto-generation
- Many-to-many: tag/untag stock, list stock categories, list category stocks
- Duplicate tagging returns 409
- Delete category cascades (stock_categories removed)
- Screener filter by category_ids
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock

# ── helpers ───────────────────────────────────────────────────────────────────

async def make_category(
    client: AsyncClient,
    admin_headers: dict[str, str],
    name: str = "EV",
    description: str | None = "Electric vehicles",
) -> dict:
    resp = await client.post(
        "/api/v1/categories",
        json={"name": name, "description": description},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── category CRUD ─────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_create_category(client: AsyncClient, db: AsyncSession) -> None:
    await create_test_user(db, email="admin@example.com", role="admin")
    headers = await get_auth_headers(client, "admin@example.com")
    cat = await make_category(client, headers)

    assert cat["name"] == "EV"
    assert cat["slug"] == "ev"
    assert cat["description"] == "Electric vehicles"
    assert cat["created_by"] is not None


@pytest.mark.anyio
async def test_create_category_slug_from_name(
    client: AsyncClient, db: AsyncSession
) -> None:
    await create_test_user(db, email="admin@example.com", role="admin")
    headers = await get_auth_headers(client, "admin@example.com")
    cat = await make_category(client, headers, name="Defence & Aerospace")

    assert cat["slug"] == "defence-aerospace"


@pytest.mark.anyio
async def test_create_category_duplicate_name_returns_409(
    client: AsyncClient, db: AsyncSession
) -> None:
    await create_test_user(db, email="admin@example.com", role="admin")
    headers = await get_auth_headers(client, "admin@example.com")
    await make_category(client, headers, name="Pharma")

    resp = await client.post(
        "/api/v1/categories",
        json={"name": "Pharma"},
        headers=headers,
    )
    assert resp.status_code == 409


@pytest.mark.anyio
async def test_create_category_non_admin_forbidden(
    client: AsyncClient, db: AsyncSession
) -> None:
    await create_test_user(db, email="user@example.com", role="user")
    headers = await get_auth_headers(client, "user@example.com")

    resp = await client.post(
        "/api/v1/categories",
        json={"name": "AI"},
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_list_categories(client: AsyncClient, db: AsyncSession) -> None:
    await create_test_user(db, email="admin@example.com", role="admin")
    await create_test_user(db, email="user@example.com", role="user")
    admin_headers = await get_auth_headers(client, "admin@example.com")
    user_headers = await get_auth_headers(client, "user@example.com")

    await make_category(client, admin_headers, name="EV")
    await make_category(client, admin_headers, name="Pharma")

    # Any authenticated user can list
    resp = await client.get("/api/v1/categories", headers=user_headers)
    assert resp.status_code == 200
    items = resp.json()
    names = [c["name"] for c in items]
    assert "EV" in names
    assert "Pharma" in names
    # stock_count present
    assert all("stock_count" in c for c in items)


@pytest.mark.anyio
async def test_get_category(client: AsyncClient, db: AsyncSession) -> None:
    await create_test_user(db, email="admin@example.com", role="admin")
    headers = await get_auth_headers(client, "admin@example.com")
    cat = await make_category(client, headers, name="Defence")

    resp = await client.get(f"/api/v1/categories/{cat['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Defence"
    assert resp.json()["stock_count"] == 0


@pytest.mark.anyio
async def test_get_category_not_found(client: AsyncClient, db: AsyncSession) -> None:
    await create_test_user(db, email="admin@example.com", role="admin")
    headers = await get_auth_headers(client, "admin@example.com")

    resp = await client.get("/api/v1/categories/9999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_update_category(client: AsyncClient, db: AsyncSession) -> None:
    await create_test_user(db, email="admin@example.com", role="admin")
    headers = await get_auth_headers(client, "admin@example.com")
    cat = await make_category(client, headers, name="Old Name")

    resp = await client.put(
        f"/api/v1/categories/{cat['id']}",
        json={"name": "New Name", "description": "Updated desc"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "New Name"
    assert data["slug"] == "new-name"
    assert data["description"] == "Updated desc"


@pytest.mark.anyio
async def test_update_category_non_admin_forbidden(
    client: AsyncClient, db: AsyncSession
) -> None:
    await create_test_user(db, email="admin@example.com", role="admin")
    await create_test_user(db, email="user@example.com", role="user")
    admin_headers = await get_auth_headers(client, "admin@example.com")
    user_headers = await get_auth_headers(client, "user@example.com")
    cat = await make_category(client, admin_headers)

    resp = await client.put(
        f"/api/v1/categories/{cat['id']}",
        json={"name": "Hacked"},
        headers=user_headers,
    )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_delete_category(client: AsyncClient, db: AsyncSession) -> None:
    await create_test_user(db, email="admin@example.com", role="admin")
    headers = await get_auth_headers(client, "admin@example.com")
    cat = await make_category(client, headers, name="Temp")

    resp = await client.delete(f"/api/v1/categories/{cat['id']}", headers=headers)
    assert resp.status_code == 204

    resp2 = await client.get(f"/api/v1/categories/{cat['id']}", headers=headers)
    assert resp2.status_code == 404


# ── stock tagging (many-to-many) ──────────────────────────────────────────────

@pytest.mark.anyio
async def test_tag_and_list_stock_categories(
    client: AsyncClient, db: AsyncSession
) -> None:
    await create_test_user(db, email="admin@example.com", role="admin")
    headers = await get_auth_headers(client, "admin@example.com")
    stock = await make_stock(db)
    cat = await make_category(client, headers, name="EV")

    # Tag the stock
    resp = await client.post(
        f"/api/v1/stocks/{stock.id}/categories",
        json={"category_id": cat["id"]},
        headers=headers,
    )
    assert resp.status_code == 201
    tag = resp.json()
    assert tag["stock_id"] == stock.id
    assert tag["category_id"] == cat["id"]

    # List categories for the stock
    resp2 = await client.get(f"/api/v1/stocks/{stock.id}/categories", headers=headers)
    assert resp2.status_code == 200
    cats = resp2.json()
    assert len(cats) == 1
    assert cats[0]["name"] == "EV"
    assert cats[0]["stock_count"] == 1


@pytest.mark.anyio
async def test_list_category_stocks(client: AsyncClient, db: AsyncSession) -> None:
    await create_test_user(db, email="admin@example.com", role="admin")
    headers = await get_auth_headers(client, "admin@example.com")
    s1 = await make_stock(db, symbol="AAA")
    s2 = await make_stock(db, symbol="BBB")
    cat = await make_category(client, headers, name="AI")

    for stock in (s1, s2):
        resp = await client.post(
            f"/api/v1/stocks/{stock.id}/categories",
            json={"category_id": cat["id"]},
            headers=headers,
        )
        assert resp.status_code == 201

    resp = await client.get(
        f"/api/v1/categories/{cat['id']}/stocks", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    symbols = [s["symbol"] for s in data["items"]]
    assert "AAA" in symbols
    assert "BBB" in symbols


@pytest.mark.anyio
async def test_duplicate_tag_returns_409(
    client: AsyncClient, db: AsyncSession
) -> None:
    await create_test_user(db, email="admin@example.com", role="admin")
    headers = await get_auth_headers(client, "admin@example.com")
    stock = await make_stock(db)
    cat = await make_category(client, headers, name="Pharma")

    await client.post(
        f"/api/v1/stocks/{stock.id}/categories",
        json={"category_id": cat["id"]},
        headers=headers,
    )
    resp = await client.post(
        f"/api/v1/stocks/{stock.id}/categories",
        json={"category_id": cat["id"]},
        headers=headers,
    )
    assert resp.status_code == 409


@pytest.mark.anyio
async def test_untag_stock(client: AsyncClient, db: AsyncSession) -> None:
    await create_test_user(db, email="admin@example.com", role="admin")
    headers = await get_auth_headers(client, "admin@example.com")
    stock = await make_stock(db)
    cat = await make_category(client, headers, name="Defence")

    await client.post(
        f"/api/v1/stocks/{stock.id}/categories",
        json={"category_id": cat["id"]},
        headers=headers,
    )

    resp = await client.delete(
        f"/api/v1/stocks/{stock.id}/categories/{cat['id']}", headers=headers
    )
    assert resp.status_code == 204

    resp2 = await client.get(f"/api/v1/stocks/{stock.id}/categories", headers=headers)
    assert resp2.json() == []


@pytest.mark.anyio
async def test_untag_nonexistent_returns_404(
    client: AsyncClient, db: AsyncSession
) -> None:
    await create_test_user(db, email="admin@example.com", role="admin")
    headers = await get_auth_headers(client, "admin@example.com")
    stock = await make_stock(db)
    cat = await make_category(client, headers)

    resp = await client.delete(
        f"/api/v1/stocks/{stock.id}/categories/{cat['id']}", headers=headers
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_delete_category_cascades(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Deleting a category must remove all stock_categories rows for it."""
    await create_test_user(db, email="admin@example.com", role="admin")
    headers = await get_auth_headers(client, "admin@example.com")
    stock = await make_stock(db)
    cat = await make_category(client, headers, name="Temp")

    await client.post(
        f"/api/v1/stocks/{stock.id}/categories",
        json={"category_id": cat["id"]},
        headers=headers,
    )

    await client.delete(f"/api/v1/categories/{cat['id']}", headers=headers)

    resp = await client.get(f"/api/v1/stocks/{stock.id}/categories", headers=headers)
    assert resp.json() == []


# ── screener integration ──────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_screener_filter_by_category(
    client: AsyncClient, db: AsyncSession
) -> None:
    await create_test_user(db, email="admin@example.com", role="admin")
    headers = await get_auth_headers(client, "admin@example.com")

    ev_stock = await make_stock(db, symbol="EVAUTO")
    await make_stock(db, symbol="PHARMA1")
    ev_cat = await make_category(client, headers, name="EV2")

    await client.post(
        f"/api/v1/stocks/{ev_stock.id}/categories",
        json={"category_id": ev_cat["id"]},
        headers=headers,
    )

    resp = await client.post(
        "/api/v1/screener/run",
        json={
            "filters": [],
            "category_ids": [ev_cat["id"]],
            "sort_by": "symbol",
            "sort_dir": "asc",
            "limit": 50,
            "offset": 0,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["symbol"] == "EVAUTO"


@pytest.mark.anyio
async def test_screener_filter_by_multiple_categories(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Stock must be in ALL listed categories to appear (AND semantics)."""
    await create_test_user(db, email="admin@example.com", role="admin")
    headers = await get_auth_headers(client, "admin@example.com")

    s1 = await make_stock(db, symbol="BOTH")
    s2 = await make_stock(db, symbol="ONLY1")
    cat_a = await make_category(client, headers, name="CatA")
    cat_b = await make_category(client, headers, name="CatB")

    # s1 is in both
    await client.post(
        f"/api/v1/stocks/{s1.id}/categories",
        json={"category_id": cat_a["id"]},
        headers=headers,
    )
    await client.post(
        f"/api/v1/stocks/{s1.id}/categories",
        json={"category_id": cat_b["id"]},
        headers=headers,
    )
    # s2 is only in cat_a
    await client.post(
        f"/api/v1/stocks/{s2.id}/categories",
        json={"category_id": cat_a["id"]},
        headers=headers,
    )

    resp = await client.post(
        "/api/v1/screener/run",
        json={
            "filters": [],
            "category_ids": [cat_a["id"], cat_b["id"]],
            "sort_by": "symbol",
            "sort_dir": "asc",
            "limit": 50,
            "offset": 0,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["symbol"] == "BOTH"


@pytest.mark.anyio
async def test_tag_stock_requires_admin(
    client: AsyncClient, db: AsyncSession
) -> None:
    await create_test_user(db, email="admin@example.com", role="admin")
    await create_test_user(db, email="user@example.com", role="user")
    admin_headers = await get_auth_headers(client, "admin@example.com")
    user_headers = await get_auth_headers(client, "user@example.com")
    stock = await make_stock(db)
    cat = await make_category(client, admin_headers, name="EV3")

    resp = await client.post(
        f"/api/v1/stocks/{stock.id}/categories",
        json={"category_id": cat["id"]},
        headers=user_headers,
    )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_stock_categories_visible_to_non_admin(
    client: AsyncClient, db: AsyncSession
) -> None:
    await create_test_user(db, email="admin@example.com", role="admin")
    await create_test_user(db, email="user@example.com", role="user")
    admin_headers = await get_auth_headers(client, "admin@example.com")
    user_headers = await get_auth_headers(client, "user@example.com")
    stock = await make_stock(db)
    cat = await make_category(client, admin_headers, name="Infra")

    await client.post(
        f"/api/v1/stocks/{stock.id}/categories",
        json={"category_id": cat["id"]},
        headers=admin_headers,
    )

    resp = await client.get(
        f"/api/v1/stocks/{stock.id}/categories", headers=user_headers
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
