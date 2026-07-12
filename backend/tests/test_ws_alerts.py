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


@pytest.fixture(autouse=True)
def _fresh_app_engine():
    """Each TestClient runs the app in a NEW portal event loop, but the
    app's module-level engine POOLS asyncpg connections bound to the
    PREVIOUS test's loop — any ws path that touches the DB through
    AsyncSessionFactory (watchlist scoping, symbol subscribe) then dies
    with 'Task attached to a different loop' (the Celery pool-×-loop
    lesson, test-harness edition). Prod is unaffected (one loop per
    process); tests dispose the pool per test."""
    import asyncio

    from app.db.session import engine

    yield
    asyncio.run(engine.dispose())


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


def _seed_watchlist() -> tuple[int, int, int, int, int]:
    """(user_id, full_watchlist_id, empty_watchlist_id, in_sid, out_sid).

    The WS handler resolves watchlists through the app's own session
    factory, so rows must be REAL and committed. Seeding runs on an
    isolated NullPool engine inside its own loop (the pooled-engine ×
    fresh-loop hazard); conftest truncation cleans up per test.
    """
    import asyncio

    from app.models.watchlist import Watchlist, WatchlistItem
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from tests.helpers import create_test_user, make_stock

    async def seed() -> tuple[int, int, int, int, int]:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as db:
                user = await create_test_user(db, email="ws-wl@example.com")
                s_in = await make_stock(db, symbol="WLIN")
                s_out = await make_stock(db, symbol="WLOUT")
                full = Watchlist(user_id=user.id, name="ws-full")
                empty = Watchlist(user_id=user.id, name="ws-empty")
                db.add_all([full, empty])
                await db.flush()
                db.add(WatchlistItem(watchlist_id=full.id, stock_id=s_in.id))
                await db.commit()
                return user.id, full.id, empty.id, s_in.id, s_out.id
        finally:
            await engine.dispose()

    return asyncio.run(seed())


def _connect_as(client: TestClient, user_id: int) -> Any:
    token = create_access_token(
        user_id=user_id, email="ws-wl@example.com", role="user"
    )
    return client.websocket_connect(f"/api/v1/ws/live?token={token}")


class TestWatchlistScope:
    def test_watchlist_scope_filters_foreign_sids(self, alert_stream) -> None:
        user_id, full_id, _empty_id, in_sid, out_sid = _seed_watchlist()
        inside = {**ALERT, "sid": in_sid, "tag": "cross_up"}
        outside = {**ALERT, "sid": out_sid, "tag": "near"}
        pump = _Pump(alert_stream, [inside, outside])
        client = TestClient(app)
        with _connect_as(client, user_id) as ws:
            ws.send_text(json.dumps({"subscribe_alerts": {"watchlist": full_id}}))
            pump.start()
            try:
                first = _receive_json(ws)
                second = _receive_json(ws)
            finally:
                pump.stop_event.set()
                pump.join(timeout=5)
        for msg in (first, second):
            assert msg["type"] == "alert"
            assert msg["data"]["sid"] == str(in_sid), "out-of-watchlist sid leaked"

    def test_watchlist_combines_with_style_filter(self, alert_stream) -> None:
        user_id, full_id, _empty_id, in_sid, _out_sid = _seed_watchlist()
        wrong_style = {**ALERT, "sid": in_sid, "style": "intraday"}
        right_style = {**ALERT, "sid": in_sid, "style": "swing"}
        pump = _Pump(alert_stream, [wrong_style, right_style])
        client = TestClient(app)
        with _connect_as(client, user_id) as ws:
            ws.send_text(
                json.dumps(
                    {"subscribe_alerts": {"watchlist": full_id, "styles": ["swing"]}}
                )
            )
            pump.start()
            try:
                msg = _receive_json(ws)
            finally:
                pump.stop_event.set()
                pump.join(timeout=5)
        assert msg["data"]["style"] == "swing"
        assert msg["data"]["sid"] == str(in_sid)

    def test_foreign_watchlist_rejected_fail_closed(self, alert_stream) -> None:
        """A watchlist you don't own is an ERROR frame and NO subscription —
        never a silent fall-back to unscoped fan-out."""
        user_id, full_id, _empty_id, in_sid, _out_sid = _seed_watchlist()
        pump = _Pump(alert_stream, [{**ALERT, "sid": in_sid}])
        client = TestClient(app)
        with _connect_as(client, user_id + 999_999) as ws:
            ws.send_text(json.dumps({"subscribe_alerts": {"watchlist": full_id}}))
            err = _receive_json(ws)
            assert err["type"] == "error"
            assert "not found" in err["data"]["detail"]
            pump.start()
            try:
                with pytest.raises(Exception):  # noqa: B017 — timeout = nothing arrived
                    _receive_json(ws, timeout=2.0)
            finally:
                pump.stop_event.set()
                pump.join(timeout=5)

    def test_empty_watchlist_delivers_nothing(self, alert_stream) -> None:
        """Empty set ≠ unscoped: an empty watchlist scopes to NOTHING."""
        user_id, _full_id, empty_id, in_sid, out_sid = _seed_watchlist()
        pump = _Pump(alert_stream, [{**ALERT, "sid": in_sid}, {**ALERT, "sid": out_sid}])
        client = TestClient(app)
        with _connect_as(client, user_id) as ws:
            ws.send_text(json.dumps({"subscribe_alerts": {"watchlist": empty_id}}))
            pump.start()
            try:
                with pytest.raises(Exception):  # noqa: B017 — timeout = nothing arrived
                    _receive_json(ws, timeout=2.0)
            finally:
                pump.stop_event.set()
                pump.join(timeout=5)

    def test_out_of_range_or_non_int_watchlist_id_is_error_frame_not_dead_socket(
        self, alert_stream
    ) -> None:
        """bug-hunter MEDIUM 2026-07-11: JSON ints are unbounded — an id
        ≥ 2^63 used to reach asyncpg as a DataError and tear down the
        WHOLE socket (LTP+candles+alerts). bool/float coercion (LOW) is
        rejected by the same guard. Canary: on the old code the first
        send kills the connection and the follow-up subscribe never
        yields an alert."""
        user_id, full_id, _empty_id, in_sid, _out_sid = _seed_watchlist()
        pump = _Pump(alert_stream, [{**ALERT, "sid": in_sid}])
        client = TestClient(app)
        with _connect_as(client, user_id) as ws:
            for bad in (10**25, True, 3.7, -5 * 10**24):
                ws.send_text(json.dumps({"subscribe_alerts": {"watchlist": bad}}))
                err = _receive_json(ws)
                assert err["type"] == "error"
                assert "positive integer" in err["data"]["detail"]
            # the socket survived all four — a real subscribe still works
            ws.send_text(json.dumps({"subscribe_alerts": {"watchlist": full_id}}))
            pump.start()
            try:
                msg = _receive_json(ws)
            finally:
                pump.stop_event.set()
                pump.join(timeout=5)
        assert msg["type"] == "alert"
        assert msg["data"]["sid"] == str(in_sid)
