"""Integration tests for broker API endpoints — Phase 7.

Tests use the real DB (same pattern as other integration tests).
Kite API calls are mocked since we can't hit real Zerodha in CI.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.core.security import create_access_token, hash_password
from app.models.user import User
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# ── Helpers ───────────────────────────────────────────────────────────────────

async def _make_user(
    db: AsyncSession,
    email: str = "kiteuser@example.com",
    role: str = "user",
) -> tuple[User, str]:
    user = User(
        email=email,
        password_hash=hash_password("Secret123"),
        full_name="Kite Test",
        role=role,
        is_active=True,
        trading_mode="paper",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token(user.id, email, role)
    return user, token


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── /broker/kite/login ───────────────────────────────────────────────────────

async def test_kite_login_returns_url(client: AsyncClient, db: AsyncSession) -> None:
    _, tok = await _make_user(db)
    with patch(
        "app.api.v1.broker.get_login_url",
        return_value="https://kite.zerodha.com/connect/login?api_key=test",
    ):
        resp = await client.get("/api/v1/broker/kite/login", headers=_bearer(tok))
    assert resp.status_code == 200
    data = resp.json()
    assert "login_url" in data
    assert "kite.zerodha.com" in data["login_url"]


async def test_kite_login_requires_auth(client: AsyncClient, db: AsyncSession) -> None:
    resp = await client.get("/api/v1/broker/kite/login")
    assert resp.status_code in (401, 403)


# ── /broker/kite/status ──────────────────────────────────────────────────────

async def test_kite_status_not_connected(client: AsyncClient, db: AsyncSession) -> None:
    _, tok = await _make_user(db, email="status@example.com")
    resp = await client.get("/api/v1/broker/kite/status", headers=_bearer(tok))
    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is False
    assert data["expires_at"] is None
    assert data["consumer_running"] is False


# ── /broker/kite/callback ────────────────────────────────────────────────────

async def test_kite_callback_redirects_to_frontend(client: AsyncClient, db: AsyncSession) -> None:
    """Public callback endpoint redirects browser to frontend with request_token."""
    resp = await client.get(
        "/api/v1/broker/kite/callback",
        params={"request_token": "tok123", "action": "login", "status": "success"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert "tok123" in location
    assert "/broker/kite" in location


async def test_kite_exchange_success(client: AsyncClient, db: AsyncSession) -> None:
    _, tok = await _make_user(db, email="exchange@example.com")

    fake_session_data = {"access_token": "fake_access_abc", "user_id": "TEST"}
    with patch("app.broker.kite_client.KiteConnect") as mock_cls:
        mock_kc = MagicMock()
        mock_cls.return_value = mock_kc
        mock_kc.generate_session.return_value = fake_session_data

        resp = await client.get(
            "/api/v1/broker/kite/exchange",
            params={"request_token": "fake_req_token_xyz"},
            headers=_bearer(tok),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "Connected" in data["detail"]
    assert "expires_at" in data


async def test_kite_exchange_bad_token(client: AsyncClient, db: AsyncSession) -> None:
    _, tok = await _make_user(db, email="badexchange@example.com")
    with patch("app.broker.kite_client.KiteConnect") as mock_cls:
        mock_kc = MagicMock()
        mock_cls.return_value = mock_kc
        mock_kc.generate_session.side_effect = Exception("Invalid request token")

        resp = await client.get(
            "/api/v1/broker/kite/exchange",
            params={"request_token": "bad_token"},
            headers=_bearer(tok),
        )
    assert resp.status_code == 400
    assert "failed" in resp.json()["detail"].lower()


# ── /broker/kite/instruments/sync — admin only ────────────────────────────────

async def test_instruments_sync_requires_admin(client: AsyncClient, db: AsyncSession) -> None:
    """Regular user cannot sync instruments."""
    _, tok = await _make_user(db, email="normaluser@example.com", role="user")
    resp = await client.post("/api/v1/broker/kite/instruments/sync", headers=_bearer(tok))
    assert resp.status_code == 403


async def test_instruments_sync_no_kite_token(client: AsyncClient, db: AsyncSession) -> None:
    """Admin with no Kite access_token gets 400."""
    _, tok = await _make_user(db, email="admin2@example.com", role="admin")
    resp = await client.post("/api/v1/broker/kite/instruments/sync", headers=_bearer(tok))
    assert resp.status_code == 400
    assert "authenticate" in resp.json()["detail"].lower()
