"""Provisional leaderboard fanout over /ws/live (Phase 3, 3.5-deferred).

Through BOTH sides of the pub/sub seam: a producer PUBLISHes per-style
leaderboard payloads exactly as `publish_leaderboards` does, and the
WebSocket client receives `{"type": "provisional"}` frames — style
scoping (REPLACE semantics) and validation included. Pub/sub is
at-most-once, so producers pump until the subscriber sees a frame.
"""

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
import redis as redis_sync
from app.broker.provisional import LEADERBOARD_CHANNEL
from app.core.config import settings
from app.core.security import create_access_token
from app.main import app
from starlette.testclient import TestClient


def _receive_json(ws: Any, timeout: float = 10.0) -> dict[str, Any]:
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return json.loads(pool.submit(ws.receive_text).result(timeout=timeout))
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


class _Pump(threading.Thread):
    """PUBLISHes each (style, payload) every 100ms until stopped — the
    subscriber tails a fire-and-forget channel, so frames must keep
    coming after the subscription lands."""

    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        super().__init__(daemon=True)
        self.payloads = payloads
        self.stop_event = threading.Event()

    def run(self) -> None:
        r = redis_sync.from_url(settings.redis_url, decode_responses=True)
        i = 0
        while not self.stop_event.is_set():
            p = self.payloads[i % len(self.payloads)]
            r.publish(LEADERBOARD_CHANNEL.format(style=p["style"]),
                      json.dumps(p, separators=(",", ":")))
            i += 1
            time.sleep(0.1)
        r.close()


@pytest.fixture(autouse=True)
def _fresh_app_engine():
    """Dispose the app's pooled engine per test (pool-×-loop hazard —
    see test_ws_alerts.py for the full story)."""
    import asyncio

    from app.db.session import engine

    yield
    asyncio.run(engine.dispose())


def _connect(client: TestClient) -> Any:
    token = create_access_token(user_id=7, email="prov@example.com", role="user")
    return client.websocket_connect(f"/api/v1/ws/live?token={token}")


def _payload(style: str) -> dict[str, Any]:
    return {
        "provisional": True,
        "style": style,
        "as_of": "2026-07-16T06:03:00+00:00",
        "rows": [{"provisional": True, "stock_id": 1, "symbol": "TESTCO",
                  "profile_key": "rrbo", "style": style, "tf": "5m",
                  "confidence": 77, "direction": "BUY", "gate": True,
                  "sources": ["signal"]}],
    }


class TestProvisionalFanout:
    def test_subscribe_true_receives_snapshot(self) -> None:
        pump = _Pump([_payload("swing")])
        client = TestClient(app)
        with _connect(client) as ws:
            ws.send_text(json.dumps({"subscribe_provisional": True}))
            pump.start()
            try:
                msg = _receive_json(ws)
            finally:
                pump.stop_event.set()
                pump.join(timeout=5)
        assert msg["type"] == "provisional"
        data = msg["data"]
        assert data["provisional"] is True
        assert data["style"] == "swing"
        assert data["rows"][0]["confidence"] == 77
        assert data["rows"][0]["provisional"] is True

    def test_style_scoping_filters_and_replaces(self) -> None:
        pump = _Pump([_payload("swing"), _payload("intraday")])
        client = TestClient(app)
        with _connect(client) as ws:
            ws.send_text(json.dumps({"subscribe_provisional": ["intraday"]}))
            pump.start()
            try:
                first = _receive_json(ws)
                second = _receive_json(ws)
            finally:
                pump.stop_event.set()
                pump.join(timeout=5)
        for msg in (first, second):
            assert msg["type"] == "provisional"
            assert msg["data"]["style"] == "intraday", "swing must be filtered out"

    def test_unsubscribe_false_is_accepted_silently(self) -> None:
        client = TestClient(app)
        with _connect(client) as ws:
            ws.send_text(json.dumps({"subscribe_provisional": ["swing"]}))
            ws.send_text(json.dumps({"subscribe_provisional": False}))
            # a bad frame AFTER teardown still gets an error reply — proves
            # the socket survived the unsubscribe path
            ws.send_text(json.dumps({"subscribe_provisional": "bogus"}))
            msg = _receive_json(ws)
        assert msg["type"] == "error"

    def test_invalid_forms_get_error_frames(self) -> None:
        client = TestClient(app)
        with _connect(client) as ws:
            ws.send_text(json.dumps({"subscribe_provisional": "bogus"}))
            first = _receive_json(ws)
            ws.send_text(json.dumps({"subscribe_provisional": ["nonsense-style"]}))
            second = _receive_json(ws)
        assert first["type"] == "error"
        assert second["type"] == "error"
        assert "known:" in second["data"]["detail"]
