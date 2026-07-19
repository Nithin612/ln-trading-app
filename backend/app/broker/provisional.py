"""Provisional confidence + per-style leaderboards (Phase 3, 3.5-deferred).

Pinned design (phase-03 ledger §Decisions, 2026-07-11, user-approved):
throttled batch rescore of a BOUNDED HOT SET on a refresher-style thread —
the SAME frozen scorer sequence (`run_all_factors → apply_weight_multipliers
→ score_from_factors`, entered through `score_signal`) on the same
300-completed-bar window canon with the forming bar appended, so the
provisional score CONVERGES to the committed score at candle close. The
O(1)-incremental sketch stays rejected; the WS/UI surface is
compute-agnostic.

Semantics (provisional-labelled END TO END):
  - DERIVED OBSERVABILITY VIEW. Never an engine event, never recorded,
    never replayed, never in backtests or P&L. `"provisional": true` is
    stamped on every payload; the worker's recorder is untouched (this
    thread only READS the book via `forming_snapshot`).
  - Gate-faithful: each (stock, profile) pair is scored through
    `score_signal` with the profile's REAL min_confidence (the ADX regime
    adjustment lives inside the frozen scorer). A leaderboard row exists
    only where the frozen engine would speak — except active-signal pairs,
    which always publish (confidence=None when below gate: "your signal's
    setup no longer passes" is the actionable preview).
  - Hot set = active-signal stocks + near-trigger stocks (alert stream,
    recent window) + watchlist stocks — bounded by
    `live_provisional_hotset_max` with priority signal > trigger >
    watchlist; clipping is LOGGED, never silent.

Window canon per pair:
  - intraday timeframes: last ≤300 completed bars from the profile's table;
    if 300, the OLDEST is dropped before the forming bar (from
    `LiveBook.forming_snapshot`) is appended — the committed run at close
    scores exactly that window.
  - 1d: the book mints no daily bar; today's forming 1d bar is
    session-aggregated from today's committed 5m bars + the forming 5m
    snapshot (the 3.0 own-bars principle). NOTE: tonight's committed 1d
    bar comes from the NSE bhavcopy (close = last-30-min VWAP), so the 1d
    preview converges to the session-aggregate score — a data-source
    delta, not an algorithm drift (ledger §Provisional confidence).

Cadence: `live_provisional_refresh_s` between cycle STARTS is the target;
a cycle that overruns logs loudly and simply starts the next one later —
the throttle is the wait, never a queue.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time as time_mod
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select, text

from app.core.config import settings

log = logging.getLogger(__name__)

_IST = ZoneInfo("Asia/Kolkata")

# Session window for provisional cycles (worker-local canon; +5 min drain
# grace past close so the last forming bars still converge on screen).
_RUN_FROM = time(9, 15)
_RUN_UNTIL = time(15, 35)

# Redis surface (every key gets a TTL — rules/trading-domain.md).
LEADERBOARD_KEY = "provisional:leaderboard:{style}"
LEADERBOARD_CHANNEL = "provisional:{style}"

# Every style a leaderboard can publish under: the four profile styles +
# the legacy signal classifications (an active signal with no bound
# profile rescores under its classification). WS + REST import this —
# never retype (the LTP_KEY rule).
ALL_PROVISIONAL_STYLES: tuple[str, ...] = (
    "intraday",
    "swing",
    "fno",
    "investment",
    "scalp",
    "positional",
)

# Profile timeframe label → LiveBook tf_minutes (1d has no book timeframe —
# it goes through the session-aggregate path).
_TF_MINUTES: dict[str, int] = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}

_WINDOW_CAP = 300  # the window canon: last 300 completed candles

# resolve_universe is index/config work, not tick work — cache per profile.
_UNIVERSE_TTL_S = 600.0
# bulk/block deals change via manual admin ingestion only (Phase 4 automates)
# — a short cache keeps the per-pair DB chatter off the cycle budget.
_FLOWS_TTL_S = 60.0


def _in_session(now_utc: datetime) -> bool:
    now_ist = now_utc.astimezone(_IST)
    if now_ist.weekday() > 4:
        return False
    return _RUN_FROM <= now_ist.timetz().replace(tzinfo=None) <= _RUN_UNTIL


def _money_f(raw: int) -> float:
    """i64·1e-4 → float, through Decimal exactly like every other outbound
    money conversion (float(Decimal) — never raw/10000 float division)."""
    return float(Decimal(raw) / Decimal(10_000))


@dataclass
class HotStock:
    symbol: str
    sources: set[str] = field(default_factory=set)  # signal | trigger | watchlist


@dataclass
class SignalPair:
    """An active signal binds (stock, profile-params) — always scored."""

    stock_id: int
    signal_id: str
    profile_key: str | None  # None = legacy engine (defaults, no multipliers)
    timeframe: str
    style: str  # signal classification stands in for style on legacy rows
    symbol: str  # carried so a clipped-from-hot-set pair still names itself


def _recent_trigger_sids(redis: Any, now_utc: datetime) -> set[int]:
    """Stock ids with a tick-trigger alert inside the recency window. The
    stream is at-least-once and capped (maxlen) — page newest-first until
    entries age past the cutoff: one capped call silently shrinks the
    window during an open-auction alert burst (bug-hunter LOW 2026-07-19).
    Bounded by maxlen (10k) ≤ 20 pages worst case."""
    cutoff = int(now_utc.timestamp()) - settings.live_provisional_trigger_window_s
    entries: list[Any] = []
    try:
        last_id = "+"
        while True:
            page = redis.xrevrange(settings.live_alert_stream, max=last_id, count=500)
            entries.extend(page)
            if len(page) < 500:
                break
            try:
                oldest_ts = int(page[-1][1].get("ts", 0))
            except (TypeError, ValueError):
                oldest_ts = 0
            if oldest_ts < cutoff:
                break
            last_id = "(" + page[-1][0]  # exclusive continuation
    except Exception:
        log.exception("provisional: alert-stream read failed; skipping triggers")
        return set()
    sids: set[int] = set()
    for _entry_id, fields in entries:
        try:
            if int(fields.get("ts", 0)) >= cutoff:
                sids.add(int(fields["sid"]))
        except (KeyError, TypeError, ValueError):
            # one malformed stream entry skips ITSELF, never the cycle
            continue
    return sids


async def load_hot_set(
    db: Any, redis: Any, now_utc: datetime
) -> tuple[dict[int, HotStock], list[SignalPair]]:
    """Assemble the bounded hot set. Priority when clipping:
    signal > trigger > watchlist (clipping is logged, never silent)."""
    hot: dict[int, HotStock] = {}
    pairs: list[SignalPair] = []

    rows = (
        await db.execute(
            text(
                "SELECT s.id, s.stock_id, s.profile_key, s.timeframe,"
                " s.classification, st.symbol"
                " FROM signals s JOIN stocks st ON st.id = s.stock_id"
                " WHERE s.status = 'active'"
                " AND (s.validity_until IS NULL OR s.validity_until > now())"
                " ORDER BY s.id"
            )
        )
    ).fetchall()
    for r in rows:
        hot.setdefault(r.stock_id, HotStock(symbol=r.symbol)).sources.add("signal")
        pairs.append(
            SignalPair(
                stock_id=r.stock_id,
                signal_id=str(r.id),
                profile_key=r.profile_key,
                timeframe=str(r.timeframe),
                style=str(r.classification),
                symbol=str(r.symbol),
            )
        )

    trigger_sids = _recent_trigger_sids(redis, now_utc)
    if trigger_sids:
        rows = (
            await db.execute(
                text("SELECT id, symbol FROM stocks WHERE id = ANY(:sids) AND is_active"),
                {"sids": sorted(trigger_sids)},
            )
        ).fetchall()
        for r in rows:
            hot.setdefault(r.id, HotStock(symbol=r.symbol)).sources.add("trigger")

    rows = (
        await db.execute(
            text(
                "SELECT DISTINCT wi.stock_id, st.symbol"
                " FROM watchlist_items wi JOIN stocks st ON st.id = wi.stock_id"
                " WHERE st.is_active"
            )
        )
    ).fetchall()
    for r in rows:
        hot.setdefault(r.stock_id, HotStock(symbol=r.symbol)).sources.add("watchlist")

    cap = settings.live_provisional_hotset_max
    if len(hot) > cap:
        rank = {"signal": 0, "trigger": 1, "watchlist": 2}
        ordered = sorted(
            hot.items(), key=lambda kv: (min(rank[s] for s in kv[1].sources), kv[0])
        )
        dropped = ordered[cap:]
        hot = dict(ordered[:cap])
        log.warning(
            "provisional: hot set clipped %d → %d (dropped %d: %s…)",
            len(ordered),
            cap,
            len(dropped),
            [sid for sid, _ in dropped[:10]],
        )
    return hot, pairs


def forming_bars_by_tf(
    snapshot: list[dict[str, Any]],
) -> dict[tuple[int, int], dict[str, Any]]:
    """LiveBook.forming_snapshot events → {(stock_id, tf_minutes): event}."""
    return {(e["stock_id"], e["tf_minutes"]): e for e in snapshot}


async def _todays_5m_aggregate(
    db: Any, stock_ids: list[int], session_day: date
) -> dict[int, dict[str, Any]]:
    """Per stock: today's committed-5m session aggregate (one grouped query)."""
    if not stock_ids:
        return {}
    day_start = datetime.combine(session_day, time(0), tzinfo=UTC)
    rows = (
        await db.execute(
            text(
                "SELECT stock_id,"
                " (array_agg(open ORDER BY time ASC))[1] AS open,"
                " max(high) AS high, min(low) AS low,"
                " (array_agg(close ORDER BY time DESC))[1] AS close,"
                " sum(volume)::bigint AS volume, max(time) AS last_time"
                " FROM ohlcv_5m"
                " WHERE stock_id = ANY(:sids) AND time >= :t0 AND is_complete"
                " GROUP BY stock_id"
            ),
            {"sids": stock_ids, "t0": day_start},
        )
    ).fetchall()
    return {
        r.stock_id: {
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": int(r.volume),
            "last_time": r.last_time,
        }
        for r in rows
    }


def forming_daily_bar(
    committed_today: dict[str, Any] | None,
    forming_5m: dict[str, Any] | None,
    session_day: date,
) -> tuple[datetime, dict[str, float | int]] | None:
    """Today's forming 1d bar from own bars (3.0 principle): committed-5m
    session aggregate merged with the forming 5m snapshot. The bar sits at
    UTC midnight of the session day — the ohlcv_1d storage canon."""
    bar_time = datetime.combine(session_day, time(0), tzinfo=UTC)
    if committed_today is None and forming_5m is None:
        return None
    if forming_5m is not None and committed_today is not None:
        # Merge only a bucket the committed set doesn't already cover
        # (restart re-mints can briefly leave both describing one bucket).
        forming_start = datetime.fromtimestamp(forming_5m["time"], tz=UTC)
        if forming_start <= committed_today["last_time"]:
            forming_5m = None
    if forming_5m is None and committed_today is not None:
        c = committed_today
        return bar_time, {
            "open": c["open"],
            "high": c["high"],
            "low": c["low"],
            "close": c["close"],
            "volume": int(c["volume"]),
        }
    f = forming_5m if forming_5m is not None else {}
    f_bar = {
        "open": _money_f(f["open"]),
        "high": _money_f(f["high"]),
        "low": _money_f(f["low"]),
        "close": _money_f(f["close"]),
        "volume": int(f["volume"]),
    }
    if committed_today is None:
        return bar_time, f_bar
    c = committed_today
    return bar_time, {
        "open": c["open"],
        "high": max(c["high"], f_bar["high"]),
        "low": min(c["low"], f_bar["low"]),
        "close": f_bar["close"],
        "volume": int(c["volume"]) + int(f_bar["volume"]),
    }


def append_forming(window: Any, bar_time: datetime, bar: dict[str, float | int]) -> Any:
    """Window canon: drop rows the forming bar supersedes, keep ≤299
    completed, append the forming bar — the exact frame the committed run
    scores at close."""
    import pandas as pd

    completed = window[window.index < bar_time]
    if len(completed) >= _WINDOW_CAP:
        completed = completed.iloc[-(_WINDOW_CAP - 1) :]
    forming_row = pd.DataFrame(
        {
            "open": [float(bar["open"])],
            "high": [float(bar["high"])],
            "low": [float(bar["low"])],
            "close": [float(bar["close"])],
            "volume": [int(bar["volume"])],
        },
        index=pd.DatetimeIndex([bar_time]),
    )
    return pd.concat([completed, forming_row])


@dataclass
class _Cache:
    universes: dict[int, tuple[float, set[int]]] = field(default_factory=dict)
    flows: tuple[float, tuple[Decimal, Decimal]] | None = None
    block_net: dict[int, tuple[float, Decimal]] = field(default_factory=dict)


async def _universe_for(db: Any, profile: Any, cache: _Cache, now_mono: float) -> set[int]:
    from app.services.universe_service import resolve_universe

    hit = cache.universes.get(profile.id)
    if hit is not None and now_mono - hit[0] < _UNIVERSE_TTL_S:
        return hit[1]
    stock_ids, _sym = await resolve_universe(db, profile.universe_spec)
    ids = set(stock_ids)
    cache.universes[profile.id] = (now_mono, ids)
    return ids


async def _flows_for(
    db: Any, as_of: date, cache: _Cache, now_mono: float
) -> tuple[Decimal, Decimal]:
    from app.services.fii_dii_service import get_market_flow_5d

    if cache.flows is not None and now_mono - cache.flows[0] < _FLOWS_TTL_S:
        return cache.flows[1]
    flows = await get_market_flow_5d(db, as_of)
    cache.flows = (now_mono, flows)
    return flows


async def _block_net_for(
    db: Any, stock_id: int, as_of: date, cache: _Cache, now_mono: float
) -> Decimal:
    from app.services.fii_dii_service import get_stock_block_deal_net_cr

    hit = cache.block_net.get(stock_id)
    if hit is not None and now_mono - hit[0] < _FLOWS_TTL_S:
        return hit[1]
    value = await get_stock_block_deal_net_cr(db, stock_id, as_of)
    cache.block_net[stock_id] = (now_mono, value)
    return value


async def score_pair(
    db: Any,
    *,
    stock_id: int,
    timeframe: str,
    min_confidence: int,
    weight_multipliers: dict[str, float] | None,
    forming_by_tf: dict[tuple[int, int], dict[str, Any]],
    agg_5m: dict[int, dict[str, Any]],
    session_day: date,
    flows: tuple[Decimal, Decimal],
    block_net: Decimal,
) -> tuple[Any | None, bool]:
    """One (stock, profile-params) pair through the frozen sequence on the
    forming-appended window. Returns (result, had_data): result None with
    had_data=True means below the ADX-adjusted gate — a real statement
    about the setup; had_data=False means the window was unusable
    (empty/<50 bars/unknown timeframe) and the score says NOTHING."""
    from app.profiles.pipeline import _load_window
    from app.services.signal_service import score_signal

    window = await _load_window(db, stock_id, timeframe)
    if window.empty or len(window) < 50:
        return None, False

    if timeframe == "1d":
        forming = forming_daily_bar(
            agg_5m.get(stock_id), forming_by_tf.get((stock_id, 5)), session_day
        )
    else:
        minutes = _TF_MINUTES.get(timeframe)
        event = forming_by_tf.get((stock_id, minutes)) if minutes is not None else None
        forming = None
        if event is not None:
            forming = (
                datetime.fromtimestamp(event["time"], tz=UTC),
                {
                    "open": _money_f(event["open"]),
                    "high": _money_f(event["high"]),
                    "low": _money_f(event["low"]),
                    "close": _money_f(event["close"]),
                    "volume": int(event["volume"]),
                },
            )
    if forming is not None:
        window = append_forming(window, forming[0], forming[1])

    fii_net_5d, dii_net_5d = flows
    result = score_signal(
        window,
        timeframe=timeframe,
        min_confidence=min_confidence,
        weight_multipliers=weight_multipliers,
        fii_net_5d=fii_net_5d,
        dii_net_5d=dii_net_5d,
        stock_block_deal_net_cr=block_net,
    )
    return result, True


async def run_cycle(
    db: Any, redis: Any, book: Any, now_utc: datetime
) -> dict[str, Any]:
    """One provisional pass: hot set → snapshot → rescore → per-style
    leaderboards. Returns cycle stats (logged by the thread loop)."""
    from app.models.profile import StrategyProfile

    cache: _Cache = run_cycle.__dict__.setdefault("_cache", _Cache())
    now_mono = time_mod.monotonic()
    session_day = now_utc.astimezone(_IST).date()

    hot, signal_pairs = await load_hot_set(db, redis, now_utc)
    profiles = (
        (
            await db.execute(
                select(StrategyProfile).where(StrategyProfile.status == "active")
            )
        )
        .scalars()
        .all()
    )
    profile_by_key = {p.key: p for p in profiles}

    # Signal pairs score with THEIR profile's params even when that
    # profile is no longer active (the preview follows the signal —
    # quant-verifier HIGH 2026-07-18): fetch the non-superseded row for
    # any pair key the active set didn't cover. Superseded rows stay out
    # deliberately: the signal's key now denotes the newest version.
    missing_keys = {
        sp.profile_key
        for sp in signal_pairs
        if sp.profile_key and sp.profile_key not in profile_by_key
    }
    if missing_keys:
        extra = (
            (
                await db.execute(
                    select(StrategyProfile).where(
                        StrategyProfile.key.in_(sorted(missing_keys)),
                        StrategyProfile.status != "superseded",
                    )
                )
            )
            .scalars()
            .all()
        )
        profile_by_key.update({p.key: p for p in extra})

    # Effective timeframe per pair (bound profile wins) — needed before
    # the snapshot so 1d signal pairs get their 5m aggregates.
    pair_tf = {
        sp.signal_id: (
            profile_by_key[sp.profile_key].timeframe
            if sp.profile_key and sp.profile_key in profile_by_key
            else sp.timeframe
        )
        for sp in signal_pairs
    }

    hot_ids = sorted(hot)
    # Snapshot hot stocks PLUS clipped-from-hot signal stocks: signal
    # pairs always publish, so they always deserve a forming bar.
    snapshot_ids = sorted(set(hot) | {sp.stock_id for sp in signal_pairs})
    snapshot = book.forming_snapshot(snapshot_ids) if snapshot_ids else []
    forming_by_tf = forming_bars_by_tf(snapshot)

    # 1d pairs need today's committed-5m aggregates (one grouped query).
    has_daily_profile = any(p.timeframe == "1d" for p in profiles)
    needs_daily = {sid for sid in hot_ids if has_daily_profile} | {
        sp.stock_id for sp in signal_pairs if pair_tf[sp.signal_id] == "1d"
    }
    agg_5m = await _todays_5m_aggregate(db, sorted(needs_daily), session_day)

    flows = await _flows_for(db, session_day, cache, now_mono)

    # Candidate pairs: hot × active profiles (universe-scoped), plus every
    # active-signal pair (scored with ITS profile's params even when the
    # profile is inactive — the preview follows the signal, and below-gate
    # results still publish for these).
    rows: list[dict[str, Any]] = []
    scored = 0
    signal_keys = {(sp.stock_id, sp.profile_key) for sp in signal_pairs}
    for profile in profiles:
        universe = await _universe_for(db, profile, cache, now_mono)
        for sid in hot_ids:
            if sid not in universe or (sid, profile.key) in signal_keys:
                continue
            block = await _block_net_for(db, sid, session_day, cache, now_mono)
            try:
                result, _had_data = await score_pair(
                    db,
                    stock_id=sid,
                    timeframe=profile.timeframe,
                    min_confidence=profile.min_confidence,
                    weight_multipliers={
                        str(k): float(v)
                        for k, v in (profile.weight_multipliers or {}).items()
                    },
                    forming_by_tf=forming_by_tf,
                    agg_5m=agg_5m,
                    session_day=session_day,
                    flows=flows,
                    block_net=block,
                )
            except Exception:
                log.exception(
                    "provisional: scoring failed stock_id=%s profile=%s", sid, profile.key
                )
                continue
            scored += 1
            if result is None:
                continue
            rows.append(
                {
                    "provisional": True,
                    "stock_id": sid,
                    "symbol": hot[sid].symbol,
                    "profile_key": profile.key,
                    "style": profile.style,
                    "tf": profile.timeframe,
                    "confidence": result.confidence_pct,
                    "direction": result.direction,
                    "gate": True,
                    "sources": sorted(hot[sid].sources),
                }
            )

    for sp in signal_pairs:
        profile = profile_by_key.get(sp.profile_key) if sp.profile_key else None
        min_conf = profile.min_confidence if profile is not None else 70
        multipliers = (
            {str(k): float(v) for k, v in (profile.weight_multipliers or {}).items()}
            if profile is not None
            else None
        )
        timeframe = pair_tf[sp.signal_id]
        style = profile.style if profile is not None else sp.style
        block = await _block_net_for(db, sp.stock_id, session_day, cache, now_mono)
        try:
            result, had_data = await score_pair(
                db,
                stock_id=sp.stock_id,
                timeframe=timeframe,
                min_confidence=min_conf,
                weight_multipliers=multipliers,
                forming_by_tf=forming_by_tf,
                agg_5m=agg_5m,
                session_day=session_day,
                flows=flows,
                block_net=block,
            )
        except Exception:
            log.exception(
                "provisional: signal rescore failed stock_id=%s signal=%s",
                sp.stock_id,
                sp.signal_id,
            )
            continue
        scored += 1
        symbol = hot[sp.stock_id].symbol if sp.stock_id in hot else sp.symbol
        rows.append(
            {
                "provisional": True,
                "stock_id": sp.stock_id,
                "symbol": symbol,
                "profile_key": sp.profile_key,
                "style": style,
                "tf": timeframe,
                "confidence": result.confidence_pct if result is not None else None,
                "direction": result.direction if result is not None else None,
                # gate False = a REAL below-gate verdict; None = the window
                # was unusable and the score says nothing (never conflate —
                # "your setup no longer passes" must not mean "DB hiccup").
                "gate": (result is not None) if had_data else None,
                "sources": sorted(hot[sp.stock_id].sources) if sp.stock_id in hot else ["signal"],
                "signal_id": sp.signal_id,
            }
        )

    published = publish_leaderboards(redis, rows, now_utc)
    return {"hot": len(hot), "pairs_scored": scored, "rows": len(rows), "styles": published}


def publish_leaderboards(redis: Any, rows: list[dict[str, Any]], now_utc: datetime) -> int:
    """Per-style leaderboard: SET (TTL) + PUBLISH. At-most-once fan-out;
    the key is the REST/late-subscriber reconciliation path.

    EVERY known style publishes EVERY cycle, empty boards included — a
    style whose last row dropped below gate must overwrite its key and
    tell subscribers, or the stale board outlives the setup (bug-hunter
    MEDIUM 2026-07-19, executed repro). Semantics: empty rows with a
    fresh as_of = genuinely nothing to show; MISSING key = worker
    down / outside session."""
    by_style: dict[str, list[dict[str, Any]]] = {s: [] for s in ALL_PROVISIONAL_STYLES}
    for row in rows:
        by_style.setdefault(str(row["style"]), []).append(row)
    published = 0
    pipe = redis.pipeline(transaction=False)
    for style, style_rows in sorted(by_style.items()):
        # stock_id tiebreak: equal-confidence rows must not swap across
        # cycles at the top-N boundary (profile load order is unordered)
        style_rows.sort(
            key=lambda r: (r["confidence"] is None, -(r["confidence"] or 0), r["stock_id"])
        )
        # Top-N is the leaderboard surface — but active-signal rows ALWAYS
        # publish (the pinned "your signal's setup" preview): clipping only
        # ever drops non-signal rows.
        top_n = settings.live_provisional_top_n
        kept = style_rows[:top_n] + [
            r for r in style_rows[top_n:] if r.get("signal_id") is not None
        ]
        payload = json.dumps(
            {
                "provisional": True,
                "style": style,
                "as_of": now_utc.isoformat(),
                "rows": kept,
            },
            separators=(",", ":"),
        )
        pipe.set(
            LEADERBOARD_KEY.format(style=style),
            payload,
            ex=settings.live_provisional_key_ttl_s,
        )
        pipe.publish(LEADERBOARD_CHANNEL.format(style=style), payload)
        published += 1
    if published:
        pipe.execute()
    return published


def run_provisional(book: Any, stop: threading.Event) -> None:
    """Provisional refresher thread: own event loop + own engine + own
    redis client (the run_refresher pattern — pooled connections never
    cross loops). Reads the book ONLY via forming_snapshot (thread-safe
    frozen/Mutex FFI); zero work lands on the consumer thread."""
    import redis as redis_sync
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    loop_holder = asyncio.new_event_loop()
    engine = create_async_engine(settings.database_url, pool_size=1, max_overflow=0)
    redis = redis_sync.from_url(settings.redis_url, decode_responses=True)

    async def _one_cycle() -> dict[str, Any]:
        async with AsyncSession(engine) as db:
            return await run_cycle(db, redis, book, datetime.now(tz=UTC))

    cadence = float(settings.live_provisional_refresh_s)
    cycles = 0
    delay = cadence
    try:
        # `delay` = cadence minus the last cycle's duration, so the target
        # is between cycle STARTS (the documented contract); an overrun
        # clamps to 0 and the next cycle simply starts late — never queued.
        while not stop.wait(delay):
            if not _in_session(datetime.now(tz=UTC)):
                delay = cadence
                continue
            started = time_mod.monotonic()
            try:
                stats = loop_holder.run_until_complete(_one_cycle())
            except Exception:
                log.exception("provisional: cycle failed; retrying next tick")
                delay = cadence
                continue
            elapsed_s = time_mod.monotonic() - started
            delay = max(0.0, cadence - elapsed_s)
            cycles += 1
            if elapsed_s > cadence:
                log.warning(
                    "provisional: cycle overran the cadence: %.0f ms > %.0f ms (%s)",
                    elapsed_s * 1000.0,
                    cadence * 1000.0,
                    stats,
                )
            elif cycles % 30 == 1:
                log.info("provisional: cycle %.0f ms %s", elapsed_s * 1000.0, stats)
    finally:
        loop_holder.run_until_complete(engine.dispose())
        loop_holder.close()
        try:
            redis.close()
        except Exception:
            log.debug("provisional: redis close raised; ignoring")
