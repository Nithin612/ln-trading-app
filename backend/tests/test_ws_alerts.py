"""Alert fanout over /ws/live (Phase 3 slice 3.5).

End-to-end through BOTH sides of the stream seam: a producer XADDs to the
alerts stream (as live_worker does) and the WebSocket client receives
`{"type": "alert"}` frames — style filtering included. The stream name is
monkeypatched per test so nothing touches the real `alerts:live` key.
"""

import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
import redis as redis_sync
from app.core.config import settings
from app.core.security import create_access_token
from app.main import app
from starlette.testclient import TestClient


def _receive_json(ws: Any, timeout: float = 10.0) -> dict[str, Any]:
    """ws.receive_text with a real timeout — a broken feature must fail
    the test, never hang the suite."""
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return json.loads(pool.submit(ws.receive_text).result(timeout=timeout))
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


class _Pump(threading.Thread):
    """XADDs alert entries every 100ms until stopped (the reader tails
    from "$", so entries must keep coming after subscription)."""

    def __init__(self, stream: str, payloads: list[dict[str, Any]]) -> None:
        super().__init__(daemon=True)
        self.stream = stream
        self.payloads = payloads
        self.stop_event = threading.Event()

    def run(self) -> None:
        r = redis_sync.from_url(settings.redis_url, decode_responses=True)
        i = 0
        while not self.stop_event.is_set():
            r.xadd(self.stream, self.payloads[i % len(self.payloads)],
                   maxlen=100, approximate=True)
            i += 1
            time.sleep(0.1)
        r.delete(self.stream)
        r.close()


@pytest.fixture
def alert_stream(monkeypatch) -> str:
    stream = f"alerts:test:{uuid.uuid4().hex}"
    monkeypatch.setattr(settings, "live_alert_stream", stream)
    return stream


def _connect(client: TestClient) -> Any:
    token = create_access_token(user_id=7, email="alerts@example.com", role="user")
    return client.websocket_connect(f"/api/v1/ws/live?token={token}")


ALERT = {
    "sid": 42, "level_id": 1001, "tag": "zone_enter", "price": "101.55",
    "ts": 1700000000, "day": "2026-07-09", "source": "entry_zone",
    "style": "swing", "signal_id": "abc-123",
}


class TestAlertFanout:
    def test_subscribed_client_receives_alert_fields(self, alert_stream) -> None:
        pump = _Pump(alert_stream, [ALERT])
        client = TestClient(app)
        with _connect(client) as ws:
            ws.send_text(json.dumps({"subscribe_alerts": True}))
            pump.start()
            try:
                msg = _receive_json(ws)
            finally:
                pump.stop_event.set()
                pump.join(timeout=5)
        assert msg["type"] == "alert"
        data = msg["data"]
        # redis streams round-trip values as strings; the entry id is added
        assert data["tag"] == "zone_enter"
        assert data["price"] == "101.55"
        assert data["style"] == "swing"
        assert data["signal_id"] == "abc-123"
        assert data["sid"] == "42"
        assert "id" in data

    def test_style_filter_drops_other_styles(self, alert_stream) -> None:
        swing = {**ALERT, "style": "swing", "tag": "cross_up"}
        intraday = {**ALERT, "style": "intraday", "tag": "near"}
        pump = _Pump(alert_stream, [swing, intraday])
        client = TestClient(app)
        with _connect(client) as ws:
            ws.send_text(json.dumps({"subscribe_alerts": {"styles": ["intraday"]}}))
            pump.start()
            try:
                first = _receive_json(ws)
                second = _receive_json(ws)
            finally:
                pump.stop_event.set()
                pump.join(timeout=5)
        for msg in (first, second):
            assert msg["type"] == "alert"
            assert msg["data"]["style"] == "intraday", "swing alerts must be filtered"
