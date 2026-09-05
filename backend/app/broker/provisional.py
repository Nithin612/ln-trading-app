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
    watchlist; clipping is LOGGED, never silent, and counted onto the
    cycle stats. "Near-trigger" means SIGNAL-BOUND alerts only: breadth
    levels (vburst / PDH / PDL / S&R, stamped style="market") carried 1271
    distinct stocks in one 15-min window on 2026-08-18 and flooded the cap
    out from under the watchlist, so they are excluded unless
    `live_provisional_trigger_market_max` dials them back in — as a
    bounded, recency-ordered discovery tier ranked BELOW the watchlist,
    deduped against everything already hot, so the dial can never starve
    the watchlist the way unfiltered breadth did.

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

Cost: the frozen engine, not the DB — measured 2026-08-14 on the live hot
set, `run_all_factors` was 45.7 ms/window and 92.6% of a 15 s cycle (window
loads: 4.4 ms). Pairs sharing (timeframe, gate, multipliers) therefore share
a memo slot keyed on the exact scorer inputs, and window loads are deduped
within a cycle: 328 pairs → 159 engine calls, and 0 when nothing moved. The
memo is an identity check, never a staleness window — see `_Cache.scores`.
A cycle where every hot stock ticks still costs ~8 s on the Python engine
(`tradecore` is 266× faster but cannot take FII/DII flows yet), so the
cadence remains a target the engine cannot always meet. Re-measured
2026-08-19: 35.6 ms/window steady on a 300-bar 5m window, so the ~50
engine calls of a live cycle are 1.8-2.4 s against a 3 s cadence — live
cycles ran 3.1-4.2 s. Overruns are therefore EXPECTED, not a fault; they
self-throttle (`delay = max(0, cadence - elapsed)`) and never queue. Watch
the RATE in `provisional:health:{day}` before touching the cadence.

Cost the docstring cannot show: this thread runs the PYTHON engine inside
the consumer's process, so it holds the GIL for most of every cycle. A
consumer-like 1 ms wake loop measured p50 1.08 ms / max 2.14 ms idle vs
p50 6.16 ms / max 33.3 ms with one scorer thread running (2026-08-19).
Moving the refresher to its own PROCESS is the durable fix if the tick
path ever needs that headroom back.
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
# Cycle-health surface, one key per IST session day (monitoring only —
# nothing reads it on the hot path).
HEALTH_KEY = "provisional:health:{day}"

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
    # signal | trigger | watchlist | market  (see the rank map in load_hot_set)
    sources: set[str] = field(default_factory=set)


@dataclass
class HotSetStats:
    """Per-cycle hot-set accounting. The clip used to exist ONLY as a log
    line, so "did the cap stop biting?" could not be answered from a run
    started without a log file — these ride the cycle stats instead.
    Source counts describe the KEPT set (what actually got scored)."""

    raw: int = 0
    kept: int = 0
    clipped: int = 0
    signal: int = 0
    trigger: int = 0
    watchlist: int = 0
    market: int = 0
    #: A26 — how far the PROTECTED tiers (signal + trigger) overflowed the cap. Non-zero
    #: means the cap was deliberately exceeded to avoid dropping committed work, and it is
    #: a configuration problem that must be seen, not a steady state.
    protected_overflow: int = 0


@dataclass
class SignalPair:
    """An active signal binds (stock, profile-params) — always scored."""

    stock_id: int
    signal_id: str
    profile_key: str | None  # None = legacy engine (defaults, no multipliers)
    timeframe: str
    style: str  # signal classification stands in for style on legacy rows
    symbol: str  # carried so a clipped-from-hot-set pair still names itself


def _alert_entries_since(redis: Any, cutoff: int) -> list[Any]:
    """Alert-stream entries newest-first, paged until they age past the
    cutoff. The stream is capped (maxlen), and ONE capped call silently
    shrank the recency window during an open-auction burst (bug-hunter LOW
    2026-07-19) — hence paging. Bounded by maxlen (10k) ≤ 20 pages."""
    entries: list[Any] = []
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
    return entries


def _recent_alert_sids(redis: Any, now_utc: datetime) -> tuple[set[int], list[int]]:
    """`(signal-bound sids, market-level sids newest-first)` inside the
    stream is at-least-once and capped (maxlen) — page newest-first until
    entries age past the cutoff: one capped call silently shrinks the
    window during an open-auction alert burst (bug-hunter LOW 2026-07-19).
    Bounded by maxlen (10k) ≤ 20 pages worst case.

    "Near-trigger" is SIGNAL-BOUND only. The producer stamps style="market"
    on breadth levels (vburst / PDH / PDL / S&R) and the signal's
    classification on signal-bound ones (`live_levels` meta), and breadth is
    not a near-trigger: measured 2026-08-18, market-level alerts carried
    1271 distinct stocks inside one 15-min window against a 150 hot-set cap,
    so the cap went to the lowest stock_ids and watchlist stocks never
    scored.

    The two tiers are returned SEPARATELY because they are admitted
    differently: signal-bound sids are near-triggers, while market-level
    sids are a bounded, recency-ordered discovery tier that `load_hot_set`
    admits below the watchlist (`live_provisional_trigger_market_max`).
    Recency here is stream-ID (XADD arrival) order, not the `ts` field —
    `_publish_alerts` XADDs one pipeline per tick batch, so the two agree
    in practice."""
    cutoff = int(now_utc.timestamp()) - settings.live_provisional_trigger_window_s
    try:
        entries = _alert_entries_since(redis, cutoff)
    except Exception:
        log.exception("provisional: alert-stream read failed; skipping triggers")
        return set(), []  # fail open: no triggers, no breadth — never a crash
    # `entries` is newest-first (xrevrange pages, extended in order), so
    # market-level encounter order IS recency order.
    sids: set[int] = set()
    market: list[int] = []
    seen_market: set[int] = set()
    for _entry_id, fields in entries:
        try:
            if int(fields.get("ts", 0)) < cutoff:
                continue
            sid = int(fields["sid"])
        except (KeyError, TypeError, ValueError):
            # one malformed stream entry skips ITSELF, never the cycle
            continue
        # A style-less entry predates the stamp, so it reads as market:
        # fail CLOSED, because failing open lets the flood back silently.
        if str(fields.get("style", "market")) == "market":
            if sid not in seen_market:
                seen_market.add(sid)
                market.append(sid)
            continue
        sids.add(sid)
    return sids, market


def admit_market_tier(
    hot: dict[int, HotStock],
    market_ordered: list[int],
    active_symbols: dict[int, str],
    market_max: int,
) -> int:
    """Admit up to `market_max` market-level (breadth) stocks, newest-first,
    returning how many were admitted. Mutates `hot`.

    Runs LAST, after every other source, and two rules make it safe:
      - a slot must buy coverage nothing else already has (`sid in hot` skips,
        and inactive stocks skip) — otherwise the dial silently delivers less
        than it claims (quant-verifier MEDIUM 2026-08-19);
      - the "market" source ranks BELOW "watchlist" in the clip, because
        admitting breadth at trigger priority is exactly what starved the
        watchlist before the filter existed.
    """
    if market_max <= 0:
        return 0
    admitted = 0
    for sid in market_ordered:  # newest-first
        if admitted >= market_max:
            break
        if sid in hot or sid not in active_symbols:
            continue
        hot[sid] = HotStock(symbol=active_symbols[sid])
        hot[sid].sources.add("market")
        admitted += 1
    return admitted


#: Tiers whose stocks are NEVER dropped to fit the cap. A stock carrying an active signal
#: or a live trigger represents committed work: not scoring it does not shed load, it
#: deletes a signal from the record.
_TIER_RANK = {"signal": 0, "trigger": 1, "watchlist": 2, "market": 3}
_PROTECTED_MAX_RANK = _TIER_RANK["trigger"]


def apply_hotset_cap(hot: dict[int, HotStock], cap: int) -> tuple[dict[int, HotStock], int]:
    """A26 — enforce the hot-set cap, HARD for discovery tiers and SOFT for protected ones.

    Returns `(kept, protected_overflow)`. `protected_overflow` is how far the protected
    tiers alone exceeded `cap`; non-zero means the cap was knowingly broken rather than
    committed work dropped, and it is a configuration problem to be seen, not a steady
    state.

    **Why the cap is not simply enforced.** It is a CPU budget. Dropping a discovery stock
    costs an opportunity; dropping a signal-bound stock removes a signal from the trading
    record — the cap would then be determining what we traded. Refusing to run at all (the
    contrasting library's answer to its broker token ceiling) is worse again: it scores
    NOTHING. So protected tiers overflow the budget and shout.

    Pure and dependency-free so the boundary is testable without a database — the previous
    version lived inline and could only be exercised through a full cycle, which is part of
    why a real clip went unnoticed for weeks.
    """
    if cap <= 0 or len(hot) <= cap:
        return hot, 0

    def rank(entry: HotStock) -> int:
        return min(_TIER_RANK[s] for s in entry.sources)

    ordered = sorted(hot.items(), key=lambda kv: (rank(kv[1]), kv[0]))
    protected = [kv for kv in ordered if rank(kv[1]) <= _PROTECTED_MAX_RANK]
    discovery = [kv for kv in ordered if rank(kv[1]) > _PROTECTED_MAX_RANK]

    if len(protected) > cap:
        overflow = len(protected) - cap
        log.error(
            "provisional: hot-set cap EXCEEDED — %d protected stocks (%d signal-bound, "
            "%d trigger-bound) against a cap of %d. Admitting all %d and running over "
            "budget, because dropping them would silently remove %d stocks carrying "
            "committed work from the record. REMEDY: raise `live_provisional_hotset_max` "
            "above %d, or reduce concurrent active signals. All %d discovery stocks are "
            "dropped this cycle.",
            len(protected),
            sum(1 for _, e in protected if "signal" in e.sources),
            sum(1 for _, e in protected if "trigger" in e.sources),
            cap,
            len(protected),
            overflow,
            len(protected),
            len(discovery),
        )
        return dict(protected), overflow

    room = cap - len(protected)
    kept = protected + discovery[:room]
    dropped = discovery[room:]
    log.warning(
        "provisional: hot set clipped %d → %d — %d discovery stocks dropped (%s…). All %d "
        "protected (signal/trigger) stocks kept. REMEDY: raise "
        "`live_provisional_hotset_max`, trim watchlists, or lower "
        "`live_provisional_market_max`.",
        len(ordered),
        len(kept),
        len(dropped),
        [sid for sid, _ in dropped[:10]],
        len(protected),
    )
    return dict(kept), 0


async def load_hot_set(
    db: Any, redis: Any, now_utc: datetime
) -> tuple[dict[int, HotStock], list[SignalPair], HotSetStats]:
    """Assemble the bounded hot set.

    **A26 — the cap is HARD for discovery tiers and SOFT for protected ones.**

    `signal` and `trigger` stocks are PROTECTED: a stock carrying an active signal that is
    not scored is a signal that silently does not exist, which makes the cap a determinant
    of the trading record rather than a CPU budget. So if the protected tiers alone exceed
    the cap they are ALL admitted, the cap is knowingly exceeded, and the overflow is
    escalated with the numbers and a remedy.

    `watchlist` and `market` are discovery tiers and still clip to fill whatever budget
    remains, by priority — but the warning now names what to do about it.

    The failure this exists to prevent already happened: breadth alerts flooded the hot
    set, watchlist stocks silently stopped being scored, and it was found weeks later. The
    contrast (repo 8) is a library that refuses at its token ceiling with an error naming
    the actual numbers and two concrete remedies. Degrading quietly is the defect.
    """
    hot: dict[int, HotStock] = {}
    pairs: list[SignalPair] = []

    rows = (
        await db.execute(
            text(
                "SELECT s.id, s.stock_id, s.profile_key, s.timeframe,"
                " s.classification, st.symbol"
                " FROM signals s JOIN stocks st ON st.id = s.stock_id"
                # status='active' only: is_shadow signals carry
                # status='shadow', so no shadow row can reach a leaderboard.
                # If that ever changes, stamp `shadow` on the row the way
                # live_worker._publish_alerts stamps it on alerts.
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

    signal_bound, market_ordered = _recent_alert_sids(redis, now_utc)
    market_max = settings.live_provisional_trigger_market_max
    # ONE query for both tiers. The is_active filter has to run BEFORE the
    # market trim, or an inactive row silently eats a slot (quant-verifier
    # MEDIUM 2026-08-19).
    lookup = set(signal_bound)
    if market_max > 0:
        lookup |= set(market_ordered)
    active_symbols: dict[int, str] = {}
    if lookup:
        rows = (
            await db.execute(
                text("SELECT id, symbol FROM stocks WHERE id = ANY(:sids) AND is_active"),
                {"sids": sorted(lookup)},
            )
        ).fetchall()
        active_symbols = {r.id: str(r.symbol) for r in rows}
    for sid in sorted(signal_bound):
        if sid in active_symbols:
            hot.setdefault(sid, HotStock(symbol=active_symbols[sid])).sources.add("trigger")

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

    # Market-level discovery tier LAST — see `admit_market_tier`.
    admit_market_tier(hot, market_ordered, active_symbols, market_max)

    cap = settings.live_provisional_hotset_max
    raw = len(hot)
    hot, overflow = apply_hotset_cap(hot, cap)
    stats = HotSetStats(
        raw=raw, kept=len(hot), clipped=max(0, raw - len(hot)), protected_overflow=overflow
    )
    for entry in hot.values():
        stats.signal += "signal" in entry.sources
        stats.trigger += "trigger" in entry.sources
        stats.watchlist += "watchlist" in entry.sources
        stats.market += "market" in entry.sources
    return hot, pairs, stats


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


# Scoring memo identity.
#   slot   = (stock_id, timeframe, min_confidence, multipliers) — WHAT is
#            being scored. Every profile sharing these params shares a slot,
#            which is why the five 1d profiles collapse to one engine call
#            per stock instead of five.
#   inputs = the exact values the frozen scorer would receive. Committed
#            history is immutable during a session, so the window is pinned
#            by (length, last bar time, last close) rather than hashed.
_ScoreSlot = tuple[int, str, int, tuple[tuple[str, float], ...]]
_ScoreInputs = tuple[Any, ...]


def _multiplier_key(multipliers: dict[str, float] | None) -> tuple[tuple[str, float], ...]:
    """Order-independent identity for a profile's weight multipliers —
    `{}` and None are the same (frozen, unscaled) scorer."""
    if not multipliers:
        return ()
    return tuple(sorted((str(k), float(v)) for k, v in multipliers.items()))


def _window_fingerprint(window: Any) -> tuple[int, Any, float]:
    """Identity of a committed window without hashing 300 rows. Committed
    bars never change mid-session (the worker runs 9:15–15:35), so length +
    the last bar's time and close pin the frame."""
    return (len(window), window.index[-1], float(window["close"].iloc[-1]))


@dataclass
class _Cache:
    universes: dict[int, tuple[float, set[int]]] = field(default_factory=dict)
    flows: tuple[float, tuple[Decimal, Decimal]] | None = None
    block_net: dict[int, tuple[float, Decimal]] = field(default_factory=dict)
    # One slot per (stock, scoring-params), holding the input fingerprint its
    # answer came from. A hit means the frozen scorer would be handed
    # byte-identical inputs — and it is pure (no clock, no randomness, no
    # I/O), so the memoized answer IS the current answer, not a stale one.
    # Keyed per SLOT, never per input: a per-input key would mint a new entry
    # every time a forming bar ticks and grow without bound all session.
    scores: dict[_ScoreSlot, tuple[_ScoreInputs, Any | None, bool]] = field(
        default_factory=dict
    )
    # Reset each cycle: a slow cycle must be able to say whether it did real
    # work or repeated itself.
    hits: int = 0
    misses: int = 0


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
    cache: _Cache | None = None,
    windows: dict[tuple[int, str], Any] | None = None,
) -> tuple[Any | None, bool]:
    """One (stock, profile-params) pair through the frozen sequence on the
    forming-appended window. Returns (result, had_data): result None with
    had_data=True means below the ADX-adjusted gate — a real statement
    about the setup; had_data=False means the window was unusable
    (empty/<50 bars/unknown timeframe) and the score says NOTHING.

    `windows` (per-cycle) dedups the window LOAD across the profiles that
    score the same stock; `cache` memoizes the SCORE itself on exact input
    identity. Both are optional — omitted, this is the original uncached
    path, which is what the parity/unit tests exercise."""
    from app.profiles.pipeline import _load_window
    from app.services.signal_service import score_signal

    window_key = (stock_id, timeframe)
    if windows is not None and window_key in windows:
        window = windows[window_key]
    else:
        window = await _load_window(db, stock_id, timeframe)
        if windows is not None:
            windows[window_key] = window
    if window.empty or len(window) < 50:
        return None, False
    committed_fp = _window_fingerprint(window)

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
    slot: _ScoreSlot = (
        stock_id,
        timeframe,
        min_confidence,
        _multiplier_key(weight_multipliers),
    )
    inputs: _ScoreInputs = (committed_fp, forming, fii_net_5d, dii_net_5d, block_net)
    if cache is not None:
        memo = cache.scores.get(slot)
        if memo is not None and memo[0] == inputs:
            cache.hits += 1
            return memo[1], memo[2]
        cache.misses += 1

    result = score_signal(
        window,
        timeframe=timeframe,
        min_confidence=min_confidence,
        weight_multipliers=weight_multipliers,
        fii_net_5d=fii_net_5d,
        dii_net_5d=dii_net_5d,
        stock_block_deal_net_cr=block_net,
    )
    if cache is not None:
        cache.scores[slot] = (inputs, result, True)
    return result, True


async def run_cycle(
    db: Any, redis: Any, book: Any, now_utc: datetime
) -> dict[str, Any]:
    """One provisional pass: hot set → snapshot → rescore → per-style
    leaderboards. Returns cycle stats (logged by the thread loop)."""
    from app.models.profile import StrategyProfile

    cache: _Cache = run_cycle.__dict__.setdefault("_cache", _Cache())
    cache.hits = 0
    cache.misses = 0
    # Window loads are deduped WITHIN a cycle only: across cycles a committed
    # bar can close, and serving that from a TTL cache would publish a score
    # built on a window the engine has already moved past.
    windows: dict[tuple[int, str], Any] = {}
    now_mono = time_mod.monotonic()
    session_day = now_utc.astimezone(_IST).date()

    hot, signal_pairs, hot_stats = await load_hot_set(db, redis, now_utc)
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

    # Drop memo slots for stocks that have left the cycle's scope, so the map
    # tracks the hot set instead of accumulating every stock seen all session.
    in_scope = set(snapshot_ids)
    if cache.scores:
        cache.scores = {k: v for k, v in cache.scores.items() if k[0] in in_scope}

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
                    cache=cache,
                    windows=windows,
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
                cache=cache,
                windows=windows,
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
    return {
        "hot": len(hot),
        "hot_raw": hot_stats.raw,
        "clipped": hot_stats.clipped,
        # A26: durable, so "did the cap bite, and did it drop committed work?" is
        # answerable from a run started without a log file. The original incident was
        # found weeks late precisely because the clip existed only as a log line.
        "protected_overflow": hot_stats.protected_overflow,
        "src_signal": hot_stats.signal,
        "src_trigger": hot_stats.trigger,
        "src_watchlist": hot_stats.watchlist,
        "src_market": hot_stats.market,
        "pairs_scored": scored,
        "rows": len(rows),
        "styles": published,
        # engine_calls is the cycle's REAL cost driver; pairs_scored counts
        # published pairs, which the memo decoupled from work done.
        "engine_calls": cache.misses,
        "memo_hits": cache.hits,
        "windows": len(windows),
    }


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


# Sentinel: Redis itself failed, as opposed to "no key for that day". A
# restart cannot otherwise tell a WIPED day from a first run (bug-hunter LOW
# 2026-08-19) — and the whole point of this key is that there is no log to
# cross-check against.
_READ_FAILED = object()


def _health_raw(redis: Any, day: str) -> Any:
    """Raw payload · None if absent · `_READ_FAILED` if the read raised.
    WARNING, not DEBUG: `live_worker.main` configures the root logger at
    INFO, so a DEBUG line here is invisible exactly when it matters."""
    try:
        return redis.get(HEALTH_KEY.format(day=day))
    except Exception:
        log.warning(
            "provisional: cycle-stats read failed — the day's counters restart "
            "from zero",
            exc_info=True,
        )
        return _READ_FAILED


def read_cycle_stats(redis: Any, day: str) -> dict[str, Any] | None:
    """The day's counters as already recorded, or None. The supervisor
    restarts the worker mid-session (token expiry is a normal lifecycle
    event), and a restart must not zero the day's record — the thread seeds
    from this."""
    raw = _health_raw(redis, day)
    if raw is _READ_FAILED or not raw:
        return None
    try:
        doc = json.loads(raw)
    except ValueError:
        log.warning("provisional: cycle-stats key unparseable; starting fresh")
        return None
    return doc if isinstance(doc, dict) else None


def _seed_counters(redis: Any, day: str) -> tuple[int, int, int, float, float, int, bool]:
    """Resume the day's counters: (cycles, overruns, clip_cycles, sum_ms,
    max_ms, restarts, seed_failed).

    Monitoring must NEVER stop the thread from starting. The key is a plain
    JSON doc a debugging script can overwrite, so a non-numeric counter
    would otherwise raise straight out of `run_provisional` — and it is a
    non-joined daemon thread with no restart path, so the provisional layer
    would go dark for the whole session with only a `threading.excepthook`
    traceback on a terminal `make live-worker` does not tee (bug-hunter LOW
    2026-08-19, reproduced)."""
    raw = _health_raw(redis, day)
    read_failed = raw is _READ_FAILED
    prior: dict[str, Any] = {}
    if not read_failed and raw:
        try:
            doc = json.loads(raw)
        except ValueError:
            log.warning("provisional: cycle-stats key unparseable; starting fresh")
            doc = None
        if isinstance(doc, dict):
            prior = doc
    try:
        cycles = int(prior.get("cycles", 0))
        overruns = int(prior.get("overruns", 0))
        clip_cycles = int(prior.get("clip_cycles", 0))
        # mean × n reconstructs the sum the previous run never stored
        elapsed_sum_ms = float(prior.get("elapsed_mean_ms", 0.0)) * cycles
        elapsed_max_ms = float(prior.get("elapsed_max_ms", 0.0))
        restarts = int(prior.get("restarts", 0)) + (1 if prior else 0)
    except (TypeError, ValueError):
        log.warning(
            "provisional: cycle-stats counters are non-numeric; starting fresh"
        )
        return 0, 0, 0, 0.0, 0.0, 0, True
    return cycles, overruns, clip_cycles, elapsed_sum_ms, elapsed_max_ms, restarts, read_failed


def publish_cycle_stats(
    redis: Any,
    *,
    day: str,
    now_utc: datetime,
    cadence_s: float,
    cycles: int,
    overruns: int,
    clip_cycles: int,
    elapsed_ms: float,
    elapsed_sum_ms: float,
    elapsed_max_ms: float,
    restarts: int,
    seed_failed: bool,
    stats: dict[str, Any],
) -> None:
    """Publish cycle health to `provisional:health:{day}` (TTL'd SET, never
    a pub/sub — a monitor that misses the message must still be able to read
    it). CUMULATIVE counters, because the question a log line cannot answer
    is a RATE: what fraction of the day's cycles overran or clipped. A
    MISSING key = the thread never cycled that day; a stale `as_of` = it
    stopped. Failure here can never disturb a cycle."""
    try:
        payload = json.dumps(
            {
                "day": day,
                "as_of": now_utc.isoformat(),
                "restarts": restarts,
                # true = this run could not seed the day's prior counters
                # (Redis read failed OR the key held non-numeric counters),
                # so everything below undercounts the day
                "seed_failed": seed_failed,
                "cadence_ms": round(cadence_s * 1000.0, 1),
                "cycles": cycles,
                "overruns": overruns,
                "overrun_pct": round(100.0 * overruns / cycles, 1) if cycles else 0.0,
                "clip_cycles": clip_cycles,
                "clip_pct": round(100.0 * clip_cycles / cycles, 1) if cycles else 0.0,
                "elapsed_ms": round(elapsed_ms, 1),
                "elapsed_mean_ms": round(elapsed_sum_ms / cycles, 1) if cycles else 0.0,
                "elapsed_max_ms": round(elapsed_max_ms, 1),
                "last": stats,
            },
            separators=(",", ":"),
        )
        redis.set(
            HEALTH_KEY.format(day=day),
            payload,
            ex=settings.live_provisional_health_ttl_s,
        )
    except Exception:
        # WARNING, not DEBUG: a persistent SET failure makes the health
        # report read "the worker did not run", which is a false conclusion.
        log.warning("provisional: cycle-stats publish failed", exc_info=True)


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
    # One process = one session day (`_run_until_done` bounds it), so the day
    # is resolved once; a restart resumes the SAME key's counters.
    day = datetime.now(tz=UTC).astimezone(_IST).date().isoformat()
    (
        cycles,
        overruns,
        clip_cycles,
        elapsed_sum_ms,
        elapsed_max_ms,
        restarts,
        seed_failed,
    ) = _seed_counters(redis, day)
    # `cycles` is CUMULATIVE across restarts, so it cannot throttle this
    # process's own log line — after a restart seeded at 4000 the first
    # liveness line would wait up to 30 cycles (bug-hunter LOW 2026-08-19).
    ran = 0
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
            ran += 1
            elapsed_ms = elapsed_s * 1000.0
            elapsed_sum_ms += elapsed_ms
            elapsed_max_ms = max(elapsed_max_ms, elapsed_ms)
            if elapsed_s > cadence:
                overruns += 1
            if stats.get("clipped"):
                clip_cycles += 1
            publish_cycle_stats(
                redis,
                day=day,
                now_utc=datetime.now(tz=UTC),
                cadence_s=cadence,
                cycles=cycles,
                overruns=overruns,
                clip_cycles=clip_cycles,
                elapsed_ms=elapsed_ms,
                elapsed_sum_ms=elapsed_sum_ms,
                elapsed_max_ms=elapsed_max_ms,
                restarts=restarts,
                seed_failed=seed_failed,
                stats=stats,
            )
            if elapsed_s > cadence:
                log.warning(
                    "provisional: cycle overran the cadence: %.0f ms > %.0f ms (%s)",
                    elapsed_s * 1000.0,
                    cadence * 1000.0,
                    stats,
                )
            elif ran % 30 == 1:
                log.info("provisional: cycle %.0f ms %s", elapsed_s * 1000.0, stats)
    finally:
        loop_holder.run_until_complete(engine.dispose())
        loop_holder.close()
        try:
            redis.close()
        except Exception:
            log.debug("provisional: redis close raised; ignoring")
