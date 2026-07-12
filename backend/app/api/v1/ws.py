"""WebSocket endpoint for live data push — Phase 7 (+ 3.5 alerts).

Protocol (client → server):
  { "subscribe": ["RELIANCE", "TATAMOTORS"] }   subscribe to these symbols
  { "unsubscribe": ["RELIANCE"] }               stop updates for these symbols
  { "subscribe_alerts": true }                  all tick-trigger alerts
  { "subscribe_alerts": {"styles": ["intraday","swing"]} }   filtered
  { "subscribe_alerts": {"watchlist": 3} }      only that watchlist's stocks
                                                (styles combinable; stock set
                                                snapshots at subscribe — re-send
                                                to refresh after edits)
  { "subscribe_alerts": false }                 stop alerts

Protocol (server → client):
  { "type": "ltp",    "data": { "symbol": "RELIANCE", "ltp": 2850.5, "ts": "..." } }
  { "type": "candle", "data": { "symbol": "RELIANCE", "timeframe": "5m", ... } }
  { "type": "alert",  "data": { "sid", "level_id", "tag", "price", "ts",
                                "day", "source", "style", "signal_id"?,
                                "id": stream-entry-id } }
  { "type": "signal", "data": { ... signal JSON ... } }
  { "type": "error",  "data": { "detail": "..." } }

Each client connection maintains its own set of Redis subscriptions.
Redis is the fan-out bus so slow clients can't block fast ones. Alerts
come from the `alerts:live` Redis STREAM (producer: live_worker, slice
3.5): each connection tails from "$" — new alerts only; reconnect
reconciliation over REST is deliberate (plan §2: frontend reconciles
committed state on reconnect).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import jwt as pyjwt
import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import text

from app.broker.candle_aggregator import TIMEFRAME_TABLE
from app.broker.tick_consumer import CANDLE_CHANNEL, LTP_CHANNEL
from app.core.config import settings
from app.core.security import decode_token

log = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])

WS_CLOSE_UNAUTHORIZED = 4401  # app-level close code mirroring HTTP 401


def _validate_ws_token(token: str | None) -> int | None:
    """Return the user_id for a valid ACCESS token, else None.

    Signature + expiry validated; no DB round-trip — access tokens live
    45 minutes, which bounds revocation lag on the read-only stream.
    """
    if not token:
        return None
    try:
        payload = decode_token(token)
    except pyjwt.InvalidTokenError:
        return None
    if payload.get("type") != "access":
        return None
    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None


@router.websocket("/live")
async def ws_live(websocket: WebSocket) -> None:  # noqa: C901
    """Main WebSocket endpoint.

    Auth: the client passes its JWT access token as `?token=...` on the
    upgrade request. Invalid/missing tokens are rejected BEFORE accept().
    """
    user_id = _validate_ws_token(websocket.query_params.get("token"))
    if user_id is None:
        # Reject the upgrade: handshake completes then closes with 4401 so
        # the client can distinguish auth failure from a network drop.
        await websocket.accept()
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED, reason="invalid or missing token")
        return

    await websocket.accept()
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()

    # symbol → instrument_token and stock_id lookups (populated on subscribe msg)
    subscribed_tokens: dict[str, int] = {}   # symbol → instrument_token
    subscribed_sids: dict[str, int] = {}     # symbol → stock_id

    send_lock = asyncio.Lock()

    async def _send(payload: dict[str, Any]) -> None:
        async with send_lock:
            try:
                await websocket.send_text(json.dumps(payload))
            except Exception:
                pass

    async def _redis_reader() -> None:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            channel: str = message["channel"]
            data = json.loads(message["data"])

            if channel.startswith("ltp:"):
                # ltp:{instrument_token}
                itoken = int(channel.split(":")[1])
                symbol = _itoken_to_symbol(itoken, subscribed_tokens)
                await _send({"type": "ltp", "data": {**data, "symbol": symbol}})

            elif channel.startswith("candle:"):
                # candle:{table}:{stock_id}
                parts = channel.split(":")
                stock_id = int(parts[2])
                symbol = _sid_to_symbol(stock_id, subscribed_sids)
                await _send({"type": "candle", "data": {**data, "symbol": symbol}})

    alert_task: asyncio.Task[None] | None = None
    alert_styles: set[str] = set()
    # None = unscoped; a SET (possibly empty) = only these stock_ids.
    # An empty watchlist legitimately scopes to NOTHING — never conflate
    # empty with unscoped.
    alert_sids: set[int] | None = None

    async def _alert_reader() -> None:
        # Tail the alerts stream from "$" (new entries only). BLOCK keeps
        # this cheap; a transient redis error backs off instead of dying.
        last_id = "$"
        while True:
            try:
                resp = await r.xread(
                    {settings.live_alert_stream: last_id}, block=5000, count=100
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(1.0)
                continue
            for _stream, entries in resp or []:
                for entry_id, fields in entries:
                    last_id = entry_id
                    if alert_styles and fields.get("style") not in alert_styles:
                        continue
                    if alert_sids is not None:
                        try:
                            sid = int(fields.get("sid", ""))
                        except ValueError:
                            continue
                        if sid not in alert_sids:
                            continue
                    await _send({"type": "alert", "data": {**fields, "id": entry_id}})

    # redis-py's PubSub.listen() is `while self.subscribed:` — starting the
    # reader on an UNsubscribed pubsub exits immediately and the stream is
    # dead forever. A keepalive channel guarantees `subscribed` stays true
    # from before the reader starts until teardown.
    await pubsub.subscribe("__ws_keepalive__")
    reader_task = asyncio.create_task(_redis_reader())

    try:
        async for raw in _ws_iter(websocket):
            try:
                msg: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                await _send({"type": "error", "data": {"detail": "Invalid JSON"}})
                continue

            symbols: list[str] = msg.get("subscribe") or []
            unsubs: list[str] = msg.get("unsubscribe") or []

            if symbols:
                new_channels = await _subscribe_symbols(
                    symbols, pubsub, subscribed_tokens, subscribed_sids
                )
                if new_channels:
                    await pubsub.subscribe(*new_channels)

            if unsubs:
                drop_channels = _unsubscribe_symbols(
                    unsubs, pubsub, subscribed_tokens, subscribed_sids
                )
                if drop_channels:
                    await pubsub.unsubscribe(*drop_channels)

            if "subscribe_alerts" in msg:
                want = msg["subscribe_alerts"]
                if want:
                    # Validate the watchlist scope BEFORE mutating current
                    # state — a bad id must not half-apply (fail closed;
                    # ownership enforced in the service: foreign ≡ absent).
                    new_sids: set[int] | None = None
                    if isinstance(want, dict) and want.get("watchlist") is not None:
                        wl_raw = want["watchlist"]
                        # Accept only a REAL in-range integer: bool is an int
                        # subclass, int() coerces floats, and JSON ints are
                        # unbounded — anything ≥ 2^63 explodes in the driver
                        # instead of 404ing (bug-hunter MEDIUM, 2026-07-11).
                        if (
                            isinstance(wl_raw, bool)
                            or not isinstance(wl_raw, int)
                            or not (0 < wl_raw < 2**63)
                        ):
                            await _send({
                                "type": "error",
                                "data": {"detail": "watchlist must be a positive integer id"},
                            })
                            continue
                        try:
                            new_sids = await _watchlist_sids(wl_raw, user_id)
                        except Exception:
                            # A DB hiccup at subscribe time must degrade to an
                            # error frame — never tear down the whole
                            # LTP/candle/alert socket.
                            log.exception("watchlist scope lookup failed (id=%s)", wl_raw)
                            await _send({
                                "type": "error",
                                "data": {"detail": "watchlist lookup failed"},
                            })
                            continue
                        if new_sids is None:
                            await _send({
                                "type": "error",
                                "data": {"detail": f"watchlist {wl_raw} not found"},
                            })
                            continue
                    alert_styles.clear()
                    if isinstance(want, dict):
                        alert_styles.update(str(s) for s in want.get("styles") or [])
                    alert_sids = new_sids
                    if alert_task is None or alert_task.done():
                        alert_task = asyncio.create_task(_alert_reader())
                elif alert_task is not None:
                    alert_task.cancel()
                    alert_task = None
                    alert_sids = None

    except WebSocketDisconnect:
        pass
    finally:
        reader_task.cancel()
        if alert_task is not None:
            alert_task.cancel()
        await pubsub.reset()
        await r.aclose()


async def _ws_iter(ws: WebSocket) -> AsyncIterator[str]:
    """Yield raw text messages from a WebSocket until disconnect."""
    while True:
        try:
            text = await ws.receive_text()
            yield text
        except WebSocketDisconnect:
            return


async def _subscribe_symbols(
    symbols: list[str],
    pubsub: Any,
    token_map: dict[str, int],
    sid_map: dict[str, int],
) -> list[str]:
    """Look up instrument_token + stock_id for each symbol and return Redis channels."""
    from app.db.session import AsyncSessionFactory

    new_channels: list[str] = []
    async with AsyncSessionFactory() as db:
        for symbol in symbols:
            if symbol in token_map:
                continue  # already subscribed
            row = await db.execute(
                text(
                    "SELECT ki.instrument_token, s.id"
                    " FROM kite_instruments ki"
                    " JOIN stocks s ON s.symbol = ki.tradingsymbol AND s.exchange = ki.exchange"
                    " WHERE ki.tradingsymbol = :sym AND ki.instrument_type = 'EQ'"
                    " AND s.is_active = true LIMIT 1"
                ).bindparams(sym=symbol)
            )
            row_data = row.fetchone()
            if row_data is None:
                log.debug("Symbol %s not found in kite_instruments", symbol)
                continue
            itoken, sid = row_data[0], row_data[1]
            token_map[symbol] = itoken
            sid_map[symbol] = sid

            ltp_ch = LTP_CHANNEL.format(instrument_token=itoken)
            new_channels.append(ltp_ch)
            for table in TIMEFRAME_TABLE.values():
                new_channels.append(CANDLE_CHANNEL.format(table=table, stock_id=sid))

    return new_channels


async def _watchlist_sids(watchlist_id: int, user_id: int) -> set[int] | None:
    """stock_ids of the user's watchlist (None = not theirs / absent —
    the service treats foreign as absent, so existence never leaks).
    SNAPSHOT at subscribe time: re-send subscribe_alerts to refresh after
    editing the watchlist — same reconcile-on-demand model as reconnect."""
    from app.db.session import AsyncSessionFactory
    from app.services.watchlist_service import watchlist_stock_ids

    async with AsyncSessionFactory() as db:
        return await watchlist_stock_ids(db, watchlist_id, user_id)


def _unsubscribe_symbols(
    symbols: list[str],
    pubsub: Any,
    token_map: dict[str, int],
    sid_map: dict[str, int],
) -> list[str]:
    channels: list[str] = []
    for sym in symbols:
        itoken = token_map.pop(sym, None)
        sid = sid_map.pop(sym, None)
        if itoken:
            channels.append(LTP_CHANNEL.format(instrument_token=itoken))
        if sid:
            for table in TIMEFRAME_TABLE.values():
                channels.append(CANDLE_CHANNEL.format(table=table, stock_id=sid))
    return channels


def _itoken_to_symbol(itoken: int, token_map: dict[str, int]) -> str:
    for sym, tok in token_map.items():
        if tok == itoken:
            return sym
    return str(itoken)


def _sid_to_symbol(sid: int, sid_map: dict[str, int]) -> str:
    for sym, s in sid_map.items():
        if s == sid:
            return sym
    return str(sid)
