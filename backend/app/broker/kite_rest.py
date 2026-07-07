"""Shared throttled Kite REST client (Phase 2 track T).

trading-domain.md: Kite REST is rate-limited (historical ~3 req/s) and ALL
REST calls go through this shared throttled client — never raw
requests/httpx/bare KiteConnect. The throttle is process-wide per client
instance; callers share one instance per token.

Async-first: kiteconnect is sync, so every call runs in a worker thread
(asyncio.to_thread) behind a monotonic-clock spacing gate. Transient
network failures retry with backoff; rate-limit responses back off harder.
"""

from __future__ import annotations

import asyncio
import logging
import time as _time
from datetime import datetime
from typing import Any

import requests.exceptions as _rex
from kiteconnect import KiteConnect
from kiteconnect.exceptions import KiteException, NetworkException, TokenException

from app.core.config import settings

log = logging.getLogger(__name__)

# ~3 req/s ceiling for historical endpoints, with headroom for jitter.
_DEFAULT_MIN_INTERVAL_S = 0.34
_RETRIES = 3
_BACKOFF_S = (1.0, 3.0, 9.0)

# What actually flies out of kiteconnect on transport failure: it re-raises
# raw `requests` exceptions, which subclass OSError/RequestException — NOT
# the builtins and NOT NetworkException (bug-hunter, Phase-2 gate; confirmed
# in production when the first backfill run died on an uncaught ReadTimeout).
_TRANSIENT = (
    NetworkException,  # Kite's own 429/5xx wrapper
    _rex.ConnectionError,
    _rex.Timeout,  # covers ConnectTimeout + ReadTimeout
    ConnectionError,
    TimeoutError,
)


class ThrottledKite:
    """One KiteConnect wrapped behind an async rate gate.

    Not a connection pool — Kite limits are per app+token, so a single
    serialized gate is exactly the right shape.
    """

    def __init__(self, access_token: str, min_interval_s: float = _DEFAULT_MIN_INTERVAL_S):
        self._kc = KiteConnect(api_key=settings.kite_api_key)
        self._kc.set_access_token(access_token)
        self._min_interval_s = min_interval_s
        self._gate = asyncio.Lock()
        self._last_call = 0.0

    async def _call(self, fn: Any, /, *args: Any, **kwargs: Any) -> Any:
        """Serialize + space + retry one sync kiteconnect call.

        Backoff sleeps INSIDE the gate on purpose: when Kite pushes back,
        every caller sharing this client must pause, not just this one.
        """
        for attempt in range(_RETRIES + 1):
            async with self._gate:
                wait = self._min_interval_s - (_time.monotonic() - self._last_call)
                if wait > 0:
                    await asyncio.sleep(wait)
                try:
                    return await asyncio.to_thread(fn, *args, **kwargs)
                except _TRANSIENT as exc:
                    if attempt >= _RETRIES:
                        raise
                    delay = _BACKOFF_S[attempt]
                    log.warning(
                        "kite REST retry %d/%d in %.0fs: %s", attempt + 1, _RETRIES, delay, exc
                    )
                    await asyncio.sleep(delay)
                finally:
                    # EVERY attempt consumed rate budget — non-transient
                    # failures (TokenException, InputException…) must not
                    # let the next caller fire unspaced.
                    self._last_call = _time.monotonic()
        raise RuntimeError("unreachable")  # pragma: no cover

    async def historical_data(
        self,
        instrument_token: int,
        from_dt: datetime,
        to_dt: datetime,
        interval: str,
    ) -> list[dict[str, Any]]:
        """OHLCV candles. interval: minute|5minute|15minute|60minute|day.

        Raises kiteconnect exceptions unchanged — callers decide whether a
        PermissionException (no historical add-on) is fatal.
        """
        data = await self._call(
            self._kc.historical_data,
            instrument_token=instrument_token,
            from_date=from_dt,
            to_date=to_dt,
            interval=interval,
            continuous=False,
        )
        return list(data)


__all__ = ["KiteException", "NetworkException", "ThrottledKite", "TokenException"]
