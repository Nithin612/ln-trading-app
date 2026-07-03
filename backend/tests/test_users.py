"""
Phase 1 — User CRUD endpoint tests.

Covers: admin-only list/create, profile access control, update restrictions,
role-change enforcement, and deactivation guard.
"""

from app.core.security import create_access_token, hash_password
from app.models.user import User
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# ── Helpers ───────────────────────────────────────────────────────────────────

async def _make_user(
    db: AsyncSession,
    email: str,
    role: str = "user",
    is_active: bool = True,
) -> User:
    user = User(
        email=email,
        password_hash=hash_password("Secret123"),
        full_name="Test Person",
        role=role,
        is_active=is_active,
        trading_mode="paper",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _bearer(user: User) -> dict:
    token = create_access_token(user.id, user.email, user.role)
    return {"Authorization": f"Bearer {token}"}


# ── List users ────────────────────────────────────────────────────────────────

async def test_admin_can_list_users(client: AsyncClient, db: AsyncSession) -> None:
    admin = await _make_user(db, "admin@test.com", role="admin")
    await _make_user(db, "user1@test.com")
    await _make_user(db, "user2@test.com")

    resp = await client.get("/api/v1/users", headers=_bearer(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3


async def test_regular_user_cannot_list_users(client: AsyncClient, db: AsyncSession) -> None:
    user = await _make_user(db, "plain@test.com")

    resp = await client.get("/api/v1/users", headers=_bearer(user))
    assert resp.status_code == 403


async def test_list_users_unauthenticated(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/users")
    assert resp.status_code == 401


# ── Create user ───────────────────────────────────────────────────────────────

async def test_admin_create_user(client: AsyncClient, db: AsyncSession) -> None:
    admin = await _make_user(db, "admin@test.com", role="admin")

    resp = await client.post(
        "/api/v1/users",
        json={
            "email": "new@test.com",
            "password": "NewPass1",
            "full_name": "New User",
        },
        headers=_bearer(admin),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new@test.com"
    assert body["role"] == "user"
    assert "password_hash" not in body


async def test_create_duplicate_email(client: AsyncClient, db: AsyncSession) -> None:
    admin = await _make_user(db, "admin@test.com", role="admin")
    await _make_user(db, "existing@test.com")

    resp = await client.post(
        "/api/v1/users",
        json={"email": "existing@test.com", "password": "NewPass1", "full_name": "Dup"},
        headers=_bearer(admin),
    )
    assert resp.status_code == 409


async def test_non_admin_cannot_create_user(client: AsyncClient, db: AsyncSession) -> None:
    user = await _make_user(db, "plain@test.com")

    resp = await client.post(
        "/api/v1/users",
        json={"email": "new2@test.com", "password": "NewPass1", "full_name": "New"},
        headers=_bearer(user),
    )
    assert resp.status_code == 403


async def test_create_user_weak_password(client: AsyncClient, db: AsyncSession) -> None:
    admin = await _make_user(db, "admin@test.com", role="admin")

    resp = await client.post(
        "/api/v1/users",
        json={"email": "weak@test.com", "password": "short", "full_name": "Weak"},
        headers=_bearer(admin),
    )
    assert resp.status_code == 422


# ── Get single user ───────────────────────────────────────────────────────────

async def test_user_gets_own_profile(client: AsyncClient, db: AsyncSession) -> None:
    user = await _make_user(db, "own@test.com")

    resp = await client.get(f"/api/v1/users/{user.id}", headers=_bearer(user))
    assert resp.status_code == 200
    assert resp.json()["email"] == "own@test.com"


async def test_admin_gets_any_profile(client: AsyncClient, db: AsyncSession) -> None:
    admin = await _make_user(db, "admin@test.com", role="admin")
    other = await _make_user(db, "other@test.com")

    resp = await client.get(f"/api/v1/users/{other.id}", headers=_bearer(admin))
    assert resp.status_code == 200


async def test_user_cannot_get_other_profile(client: AsyncClient, db: AsyncSession) -> None:
    user1 = await _make_user(db, "u1@test.com")
    user2 = await _make_user(db, "u2@test.com")

    resp = await client.get(f"/api/v1/users/{user2.id}", headers=_bearer(user1))
    assert resp.status_code == 403


async def test_get_nonexistent_user(client: AsyncClient, db: AsyncSession) -> None:
    admin = await _make_user(db, "admin@test.com", role="admin")

    resp = await client.get("/api/v1/users/99999", headers=_bearer(admin))
    assert resp.status_code == 404


# ── Update user ───────────────────────────────────────────────────────────────

async def test_user_updates_own_name(client: AsyncClient, db: AsyncSession) -> None:
    user = await _make_user(db, "update@test.com")

    resp = await client.patch(
        f"/api/v1/users/{user.id}",
        json={"full_name": "Updated Name"},
        headers=_bearer(user),
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Updated Name"


async def test_user_cannot_change_own_role(client: AsyncClient, db: AsyncSession) -> None:
    user = await _make_user(db, "escalate@test.com")

    resp = await client.patch(
        f"/api/v1/users/{user.id}",
        json={"role": "admin"},
        headers=_bearer(user),
    )
    assert resp.status_code == 403


async def test_admin_can_change_role(client: AsyncClient, db: AsyncSession) -> None:
    admin = await _make_user(db, "admin@test.com", role="admin")
    user = await _make_user(db, "promote@test.com")

    resp = await client.patch(
        f"/api/v1/users/{user.id}",
        json={"role": "readonly"},
        headers=_bearer(admin),
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "readonly"


# ── Deactivate user ───────────────────────────────────────────────────────────

async def test_admin_deactivates_user(client: AsyncClient, db: AsyncSession) -> None:
    admin = await _make_user(db, "admin@test.com", role="admin")
    user = await _make_user(db, "deactivate@test.com")

    resp = await client.delete(f"/api/v1/users/{user.id}", headers=_bearer(admin))
    assert resp.status_code == 200

    # Verify user is now inactive
    check = await client.get(f"/api/v1/users/{user.id}", headers=_bearer(admin))
    assert check.json()["is_active"] is False


async def test_admin_cannot_deactivate_self(client: AsyncClient, db: AsyncSession) -> None:
    admin = await _make_user(db, "admin@test.com", role="admin")

    resp = await client.delete(f"/api/v1/users/{admin.id}", headers=_bearer(admin))
    assert resp.status_code == 400


async def test_non_admin_cannot_deactivate(client: AsyncClient, db: AsyncSession) -> None:
    user1 = await _make_user(db, "u1@test.com")
    user2 = await _make_user(db, "u2@test.com")

    resp = await client.delete(f"/api/v1/users/{user2.id}", headers=_bearer(user1))
    assert resp.status_code == 403
