"""
Phase 1 — Auth endpoint tests.

Covers: login success/failure, inactive user, refresh rotation,
revoked session rejection, logout, and protected route access.
"""

from app.core.security import create_access_token, hash_password
from app.models.user import User
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# ── Helpers ───────────────────────────────────────────────────────────────────

async def _make_user(
    db: AsyncSession,
    email: str = "user@test.com",
    password: str = "Secret123",
    role: str = "user",
    is_active: bool = True,
) -> User:
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name="Test User",
        role=role,
        is_active=is_active,
        trading_mode="paper",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Login ─────────────────────────────────────────────────────────────────────

async def test_login_success(client: AsyncClient, db: AsyncSession) -> None:
    await _make_user(db, email="login@test.com", password="Secret123")

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@test.com", "password": "Secret123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "login@test.com"
    # Refresh cookie must be set
    assert "refresh_token" in resp.cookies


async def test_login_wrong_password(client: AsyncClient, db: AsyncSession) -> None:
    await _make_user(db, email="wp@test.com", password="Secret123")

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "wp@test.com", "password": "WrongPass1"},
    )
    assert resp.status_code == 401


async def test_login_unknown_email(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@test.com", "password": "Secret123"},
    )
    assert resp.status_code == 401


async def test_login_inactive_user(client: AsyncClient, db: AsyncSession) -> None:
    await _make_user(db, email="inactive@test.com", password="Secret123", is_active=False)

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@test.com", "password": "Secret123"},
    )
    assert resp.status_code == 403


# ── Token refresh ─────────────────────────────────────────────────────────────

async def test_refresh_issues_new_tokens(client: AsyncClient, db: AsyncSession) -> None:
    await _make_user(db, email="refresh@test.com", password="Secret123")

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "refresh@test.com", "password": "Secret123"},
    )
    assert login.status_code == 200
    old_access = login.json()["access_token"]
    old_refresh = login.cookies["refresh_token"]

    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200
    new_access = resp.json()["access_token"]
    new_refresh = resp.cookies.get("refresh_token")

    assert new_access != old_access
    assert new_refresh is not None
    assert new_refresh != old_refresh


async def test_refresh_old_token_is_revoked(client: AsyncClient, db: AsyncSession) -> None:
    """After rotation the original refresh token must be rejected."""
    await _make_user(db, email="rot@test.com", password="Secret123")

    await client.post(
        "/api/v1/auth/login",
        json={"email": "rot@test.com", "password": "Secret123"},
    )
    old_refresh = client.cookies.get("refresh_token")
    await client.post("/api/v1/auth/refresh")

    # Manually set old cookie and try to refresh again
    client.cookies.set("refresh_token", old_refresh)
    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


async def test_refresh_missing_cookie(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


async def test_refresh_invalid_token(client: AsyncClient) -> None:
    client.cookies.set("refresh_token", "this.is.garbage")
    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


# ── Logout ────────────────────────────────────────────────────────────────────

async def test_logout_clears_cookie(client: AsyncClient, db: AsyncSession) -> None:
    user = await _make_user(db, email="logout@test.com", password="Secret123")
    token = create_access_token(user.id, user.email, user.role)

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "logout@test.com", "password": "Secret123"},
    )
    assert login.status_code == 200

    resp = await client.post("/api/v1/auth/logout", headers=_auth_header(token))
    assert resp.status_code == 200
    # Cookie should be cleared (empty or deleted)
    cookie_val = resp.cookies.get("refresh_token", "")
    assert cookie_val == ""


# ── Protected routes ──────────────────────────────────────────────────────────

async def test_me_with_valid_token(client: AsyncClient, db: AsyncSession) -> None:
    user = await _make_user(db, email="me@test.com", password="Secret123")
    token = create_access_token(user.id, user.email, user.role)

    resp = await client.get("/api/v1/auth/me", headers=_auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@test.com"


async def test_me_no_token(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_invalid_token(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me", headers=_auth_header("bad.token.here"))
    assert resp.status_code == 401


async def test_me_deactivated_user(client: AsyncClient, db: AsyncSession) -> None:
    user = await _make_user(
        db, email="disabled@test.com", password="Secret123", is_active=False
    )
    token = create_access_token(user.id, user.email, user.role)

    resp = await client.get("/api/v1/auth/me", headers=_auth_header(token))
    assert resp.status_code == 403
