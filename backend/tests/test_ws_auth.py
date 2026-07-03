"""WebSocket auth tests (Phase 0 triage).

/api/v1/ws/live used to accept ANY connection — the JWT validation was a
TODO. The endpoint now rejects missing/invalid/non-access tokens with app
close code 4401 before serving any data.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt as pyjwt
import pytest
from app.api.v1.ws import WS_CLOSE_UNAUTHORIZED, _validate_ws_token
from app.core.config import settings
from app.core.security import create_access_token
from app.main import app
from starlette.testclient import TestClient


class TestValidateWsToken:
    def test_valid_access_token(self) -> None:
        token = create_access_token(user_id=42, email="t@example.com", role="user")
        assert _validate_ws_token(token) == 42

    def test_missing_token(self) -> None:
        assert _validate_ws_token(None) is None
        assert _validate_ws_token("") is None

    def test_garbage_token(self) -> None:
        assert _validate_ws_token("not-a-jwt") is None

    def test_wrong_secret_rejected(self) -> None:
        forged = pyjwt.encode(
            {
                "sub": "1",
                "type": "access",
                "exp": datetime.now(UTC) + timedelta(minutes=5),
            },
            "wrong-secret",
            algorithm=settings.jwt_algorithm,
        )
        assert _validate_ws_token(forged) is None

    def test_expired_token_rejected(self) -> None:
        expired = pyjwt.encode(
            {
                "sub": "1",
                "type": "access",
                "exp": datetime.now(UTC) - timedelta(minutes=1),
            },
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        assert _validate_ws_token(expired) is None

    def test_refresh_token_rejected(self) -> None:
        """A refresh token is NOT an access credential for the stream."""
        refresh_like = pyjwt.encode(
            {
                "sub": "1",
                "type": "refresh",
                "exp": datetime.now(UTC) + timedelta(days=1),
            },
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        assert _validate_ws_token(refresh_like) is None


def _ws_close_code(url: str) -> tuple[bool, int | None]:
    """Connect and return (closed_immediately, close_code)."""
    client = TestClient(app)
    with client.websocket_connect(url) as ws:
        try:
            msg: dict[str, Any] = ws.receive()
        except Exception:
            return True, None
        if msg.get("type") == "websocket.close":
            return True, msg.get("code")
        return False, None


class TestWsUpgradeGate:
    def test_no_token_closed_4401(self) -> None:
        closed, code = _ws_close_code("/api/v1/ws/live")
        assert closed is True
        assert code == WS_CLOSE_UNAUTHORIZED

    def test_bad_token_closed_4401(self) -> None:
        closed, code = _ws_close_code("/api/v1/ws/live?token=bogus")
        assert closed is True
        assert code == WS_CLOSE_UNAUTHORIZED

    @pytest.mark.filterwarnings("ignore::DeprecationWarning")
    def test_valid_token_stays_open(self) -> None:
        token = create_access_token(user_id=7, email="ws@example.com", role="user")
        client = TestClient(app)
        with client.websocket_connect(f"/api/v1/ws/live?token={token}") as ws:
            # Connection is accepted and serving: send a subscribe for an
            # unknown symbol; the server must not close on us.
            ws.send_text('{"subscribe": ["NOSUCHSYM"]}')
            # No close frame expected; closing from our side must succeed.
            ws.close()
