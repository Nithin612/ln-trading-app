"""Trigger-level construction for the live worker (Phase 3, slice 3.5).

Builds the `tradecore.LiveBook.set_levels` payloads — the host side of the
tick-trigger layer. Levels are alert thresholds, never signal inputs:
nothing here feeds scoring, sizing, or backtests.

Sources, per stock:
  static (built once at session start)
    - PDH cross-up / PDL cross-down from the previous 1d candle. High/low
      are derivation-identical between the 1d table and session-aggregated
      bars (only CLOSE differs — the 3.0 parity concern), so the 1d table
      is safe here.
    - 5m volume-burst baseline = avg completed-5m volume over the last
      ~20 sessions. The forming candle's PARTIAL volume is compared
      against `live_vburst_mult ×` that full-bucket average — firing early
      means genuinely bursty, never merely "on pace".
  signal-derived (refreshed every `live_level_refresh_s`)
    - active signals: entry zone (± live_entry_zone_pct, mirroring the
      §2.5 proximity), SL proximity, TP proximity.
    - S/R zone crosses for stocks with active signals, from the frozen
      detector (`app.analysis.structure.levels.detect_sr_levels`) over the
      signal-timeframe window canon (last 300 completed candles).

Level ids (unique per instrument, stable across refreshes so the engine
preserves armed-state; kept < 2^53 so JSON consumers never lose bits):
    1 = PDH · 2 = PDL · 3 = vburst
    S/R: SR_BASE_ID + sha256(timeframe:zone_type:price)[:6] % 2^20 —
    identity-derived, NOT rank-derived: a strength reshuffle between
    refreshes must not reassign ids (that would reset armed-state, bypass
    the re-arm band, and break consumer (id, day) dedupe — bug-hunter LOW
    2026-07-10). Same-stock hash collisions (~1e-4) skip the weaker zone.
    signal levels: SIGNAL_BASE_ID + (sha256(signal uuid) & 48 bits)·4 +
    slot (0=entry zone, 1=SL near, 2=TP near) — signals.id is a UUID, so
    the id is a stable truncated hash, not arithmetic on the key. The
    S/R range [100, 100+2^20) overlaps signal ids only for hash values
    < 2^20/4 (P ≈ 5e-9 per signal — accepted, documented).
"""

from __future__ import annotations

import hashlib
import logging
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.broker.candle_aggregator import TIMEFRAME_TABLE
from app.core.config import settings

log = logging.getLogger(__name__)

_IST = ZoneInfo("Asia/Kolkata")

PDH_ID = 1
PDL_ID = 2
VBURST_ID = 3
SR_BASE_ID = 100
SR_ID_SPAN = 1 << 20
SIGNAL_BASE_ID = 1000
_SR_MAX_ZONES = 8
_SR_WINDOW = 300  # the window canon: last 300 completed candles

# A level dict as tradecore.set_levels expects it (also the recording
# "lv" payload). Money fields are Decimal-parseable strings.
LevelDict = dict[str, Any]
# Host-side meta per (stock_id, level_id): style/source/signal for alert
# enrichment — the engine round-trips only the id.
LevelMeta = dict[int, dict[str, Any]]


def _pct_to_bp(pct: float) -> int:
    return int(round(pct * 100))


def _q4(value: Decimal | float) -> str:
    """Decimal-parseable money string, quantized to the 1e-4 canon."""
    return str(Decimal(str(value)).quantize(Decimal("0.0001")))


def signal_level_ids(signal_id: str) -> tuple[int, int, int]:
    """Stable per-signal level ids from the signal UUID (48-bit hash ×4 +
    slot, offset past the static/S&R ranges; < 2^53 for JSON safety)."""
    h = int.from_bytes(hashlib.sha256(signal_id.encode()).digest()[:6], "big")
    base = SIGNAL_BASE_ID + h * 4
    return base, base + 1, base + 2


async def load_static_levels(
    db: Any, today: datetime, stock_ids: list[int]
) -> tuple[dict[int, list[LevelDict]], dict[int, LevelMeta]]:
    """PDH/PDL + volume-burst baselines for the SUBSCRIBED stocks — one
    pass, two aggregate queries, built once at worker startup. Restricting
    to the subscription set keeps the engine from allocating per-tf state
    for stocks that will never tick (quant-verifier LOW, 2026-07-10)."""
    levels: dict[int, list[LevelDict]] = {}
    meta: dict[int, LevelMeta] = {}
    if not stock_ids:
        return levels, meta
    rearm = settings.live_cross_rearm_bp

    # Previous session's 1d high/low: newest 1d candle strictly before
    # today's IST date (timestamp conventions can't leak today's row in).
    ist_midnight = datetime.combine(today.astimezone(_IST).date(), time(0), tzinfo=_IST)
    rows = await db.execute(
        text(
            "SELECT DISTINCT ON (stock_id) stock_id, high, low"
            " FROM ohlcv_1d WHERE time < :cutoff AND is_complete"
            " AND stock_id = ANY(:sids)"
            " ORDER BY stock_id, time DESC"
        ).bindparams(cutoff=ist_midnight.astimezone(UTC), sids=stock_ids)
    )
    for sid, high, low in rows.fetchall():
        stock_levels = [
            {"id": PDH_ID, "kind": "cross_up", "price": _q4(high), "rearm_bp": rearm},
            {"id": PDL_ID, "kind": "cross_down", "price": _q4(low), "rearm_bp": rearm},
        ]
        levels[sid] = stock_levels
        meta[sid] = {
            PDH_ID: {"source": "pdh", "style": "market"},
            PDL_ID: {"source": "pdl", "style": "market"},
        }

    # 5m volume baseline over ~20 sessions (30 calendar days).
    rows = await db.execute(
        text(
            "SELECT stock_id, AVG(volume)::bigint FROM ohlcv_5m"
            " WHERE time >= :since AND is_complete AND stock_id = ANY(:sids)"
            " GROUP BY stock_id"
        ).bindparams(since=today - timedelta(days=30), sids=stock_ids)
    )
    mult_bp = int(round(settings.live_vburst_mult * 10_000))
    for sid, baseline in rows.fetchall():
        if not baseline or baseline <= 0:
            continue
        levels.setdefault(sid, []).append(
            {
                "id": VBURST_ID,
                "kind": "vburst",
                "tf_minutes": 5,
                "baseline": int(baseline),
                "mult_bp": mult_bp,
            }
        )
        meta.setdefault(sid, {})[VBURST_ID] = {"source": "vburst", "style": "market"}
    return levels, meta


async def _active_signals(db: Any) -> list[dict[str, Any]]:
    # ORDER BY id: merged level-list order must be deterministic, or an
    # unchanged stock reports as changed on every Postgres row-order flip
    # (spurious set_levels + recording churn — quant-verifier MEDIUM).
    rows = await db.execute(
        text(
            "SELECT id, stock_id, entry_price, stop_loss, take_profit,"
            " classification, timeframe FROM signals"
            " WHERE status = 'active'"
            " AND (validity_until IS NULL OR validity_until > now())"
            " ORDER BY id"
        )
    )
    return [
        {
            # asyncpg returns a UUID object for the uuid column — normalize
            # to the canonical string form Signal.id uses (str(uuid4())).
            "id": str(r[0]),
            "stock_id": r[1],
            "entry": r[2],
            "sl": r[3],
            "tp": r[4],
            "classification": r[5],
            "timeframe": r[6],
        }
        for r in rows.fetchall()
    ]


def _signal_levels(sig: dict[str, Any]) -> tuple[list[LevelDict], LevelMeta]:
    """Entry zone + SL/TP proximity for one active signal."""
    entry: Decimal = sig["entry"]
    zone_id, sl_id, tp_id = signal_level_ids(sig["id"])
    half = Decimal(str(settings.live_entry_zone_pct)) / 100
    within = settings.live_sltp_within_bp
    meta_common = {
        "source": "signal",
        "style": str(sig["classification"]),
        "signal_id": sig["id"],
    }
    levels: list[LevelDict] = [
        {
            "id": zone_id,
            "kind": "zone",
            "low": _q4(entry * (1 - half)),
            "high": _q4(entry * (1 + half)),
        }
    ]
    meta: LevelMeta = {zone_id: {**meta_common, "source": "entry_zone"}}
    if sig["sl"] and sig["sl"] > 0:
        levels.append(
            {"id": sl_id, "kind": "near", "price": _q4(sig["sl"]), "within_bp": within}
        )
        meta[sl_id] = {**meta_common, "source": "sl_near"}
    if sig["tp"] and sig["tp"] > 0:
        levels.append(
            {"id": tp_id, "kind": "near", "price": _q4(sig["tp"]), "within_bp": within}
        )
        meta[tp_id] = {**meta_common, "source": "tp_near"}
    return levels, meta


async def _sr_levels_for(
    db: Any, stock_id: int, timeframe: str
) -> tuple[list[LevelDict], LevelMeta]:
    """S/R cross levels from the frozen detector over the window canon.
    Import deferred: pandas + the analysis stack load only when a signal
    stock actually needs S/R (worker startup stays lean)."""
    import pandas as pd

    from app.analysis.structure.levels import detect_sr_levels

    table = TIMEFRAME_TABLE.get(timeframe)
    if table is None:
        return [], {}
    rows = await db.execute(
        text(
            f"SELECT high, low FROM {table}"  # noqa: S608 — whitelisted table
            " WHERE stock_id = :sid AND is_complete"
            " ORDER BY time DESC LIMIT :lim"
        ).bindparams(sid=stock_id, lim=_SR_WINDOW)
    )
    data = rows.fetchall()[::-1]  # chronological
    if len(data) < 20:
        return [], {}
    frame = pd.DataFrame(data, columns=["high", "low"])
    zones = detect_sr_levels(frame)
    zones.sort(key=lambda z: (-z.strength, z.price_lower))
    levels: list[LevelDict] = []
    meta: LevelMeta = {}
    rearm = settings.live_cross_rearm_bp
    for zone in zones[:_SR_MAX_ZONES]:
        if zone.zone_type == "resistance":
            kind, price = "cross_up", _q4(zone.price_upper)
        elif zone.zone_type == "support":
            kind, price = "cross_down", _q4(zone.price_lower)
        else:
            continue
        # Identity-derived id: stable as long as the zone itself is —
        # rank reshuffles between refreshes must not reassign ids.
        digest = hashlib.sha256(
            f"{timeframe}:{zone.zone_type}:{price}".encode()
        ).digest()
        level_id = SR_BASE_ID + int.from_bytes(digest[:6], "big") % SR_ID_SPAN
        if level_id in meta:
            log.debug("S/R id collision on stock %s; skipping weaker zone", stock_id)
            continue
        levels.append({"id": level_id, "kind": kind, "price": price, "rearm_bp": rearm})
        meta[level_id] = {
            "source": f"sr_{zone.zone_type}",
            "style": "market",
            "strength": zone.strength,
        }
    return levels, meta


@dataclass
class LevelDirectory:
    """Merged static + signal-derived levels with change tracking.

    `refresh` (refresher thread) returns only stocks whose merged list
    CHANGED vs the last CONSUMER-ACKNOWLEDGED state; `mark_sent` is the
    ack, called by the CONSUMER thread only after the engine ACCEPTED a
    set_levels (via `WorkerState.on_levels_applied`). An item that gets
    evicted by drop-oldest, or rejected by engine validation, is simply
    never acked and re-sends every cycle — loud on repeat rejection, never
    silently divergent (quant-verifier + bug-hunter MEDIUM, 2026-07-10).
    `_lock` covers `last_sent` (two threads touch it).
    """

    static_levels: dict[int, list[LevelDict]] = field(default_factory=dict)
    static_meta: dict[int, LevelMeta] = field(default_factory=dict)
    last_sent: dict[int, list[LevelDict]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    async def refresh(
        self, db: Any
    ) -> list[tuple[int, list[LevelDict], LevelMeta]]:
        """(stock_id, merged levels, merged meta) for every changed stock."""
        merged: dict[int, list[LevelDict]] = {
            sid: list(levels) for sid, levels in self.static_levels.items()
        }
        meta: dict[int, LevelMeta] = {
            sid: dict(m) for sid, m in self.static_meta.items()
        }
        # S/R computes ONCE per (stock, timeframe) — a second signal on the
        # same pair must reuse, not re-append duplicate ids (which would
        # reject the stock's whole set_levels — quant-verifier HIGH).
        sr_done: set[tuple[int, str]] = set()
        for sig in await _active_signals(db):
            sid = sig["stock_id"]
            sig_levels, sig_meta = _signal_levels(sig)
            merged.setdefault(sid, []).extend(sig_levels)
            meta.setdefault(sid, {}).update(sig_meta)
            key = (sid, str(sig["timeframe"]))
            if key in sr_done:
                continue
            sr_done.add(key)
            try:
                sr_levels, sr_meta = await _sr_levels_for(db, sid, sig["timeframe"])
            except Exception:
                log.exception("S/R levels failed for stock_id=%s; continuing", sid)
                continue
            merged[sid].extend(sr_levels)
            meta[sid].update(sr_meta)
        with self._lock:
            acked = {sid: list(levels) for sid, levels in self.last_sent.items()}
        changed = [
            (sid, levels, meta.get(sid, {}))
            for sid, levels in merged.items()
            if acked.get(sid) != levels
        ]
        # A stock whose last signal expired must fall back to statics.
        for sid in acked:
            if sid not in merged:
                changed.append((sid, [], {}))
        return changed

    def mark_sent(self, sid: int, levels: list[LevelDict]) -> None:
        """Consumer-thread ack: the engine accepted this exact list."""
        with self._lock:
            if levels:
                self.last_sent[sid] = levels
            else:
                self.last_sent.pop(sid, None)


async def build_directory(
    db: Any, today: datetime, stock_ids: list[int]
) -> LevelDirectory:
    """Startup construction: statics once (subscription set only), then
    one refresh pass so the initial payload carries active-signal levels."""
    static_levels, static_meta = await load_static_levels(db, today, stock_ids)
    return LevelDirectory(static_levels=static_levels, static_meta=static_meta)
