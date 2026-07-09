"""Per-profile suggestion pipeline (Phase 2 slice 7; Phase-3 pre-work).

For each ACTIVE profile: resolve universe → load candles → score through
the confluence engine (real FII/DII flows, profile weight_multipliers via
the exact BacktestEngine sequence) → gate on the profile's setup conditions
with full session context (prev-day OHLC + 9:25 cross-section on intraday
timeframes, built by the SAME session_context code the walk-forward runs) →
risk-template TP override (SL stays classification canon;
reject-don't-clamp preserved) → persist Signal rows tagged
(profile_id, profile_key, setup_trigger, volatility_reduced).

Idempotency/supersede policy (design-reviewed):
  - same (stock, profile_key) active + same direction  → skip
  - same pair active + OPPOSITE direction              → supersede old, insert new
  - races resolve at the DB partial-unique index (IntegrityError → skip)
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.risk import compute_quantity, volatility_adjusted_qty
from app.analysis.structure.dow import swing_levels
from app.backtest.tp_rules import tp_from_template as _tp_from_template
from app.models.profile import StrategyProfile
from app.models.signal import Signal
from app.profiles import session_context as sctx
from app.profiles.setups import SetupContext, evaluate_conditions
from app.services import market_calendar
from app.services.fii_dii_service import get_market_flow_5d, get_stock_block_deal_net_cr
from app.services.signal_service import score_signal
from app.services.universe_service import resolve_universe
from app.signals.classifier import classify_signal
from app.signals.expiry import compute_validity_until
from app.signals.headline import build_headline
from app.signals.risk_guards import safe_levels

log = logging.getLogger(__name__)

_IST = ZoneInfo("Asia/Kolkata")

# Same whitelist discipline as the strategy-lab loader — table names only
# ever come from here.
_TIMEFRAME_TABLE: dict[str, str] = {
    "1d": "ohlcv_1d",
    "1h": "ohlcv_1h",
    "15m": "ohlcv_15m",
    "5m": "ohlcv_5m",
    "1m": "ohlcv_1m",
}

# Cross-section fetch bounds: symbols per query caps asyncpg row buffering
# (walk-forward OOM lesson, 8c); the calendar lookback only bounds the
# fetch — session pairing itself is data-driven, so any holiday cluster
# shorter than this window is handled by construction.
_XSEC_CHUNK = 50
_XSEC_LOOKBACK_DAYS = 8


def _intraday_setup_context(
    window: pd.DataFrame,
    cross_section_by_session: dict[date, dict[str, float]] | None,
) -> tuple[dict[str, float] | None, dict[str, float] | None]:
    """(prev_day, cross_section) for the window's DECISION bar (its last
    row) — the live twin of walkforward.apply_setup_filter's context.

    prev_day is the previous PRESENT session's OHLC aggregated from the
    window's own bars (shared session_context math; None fails the
    evaluators closed). The cross-section is consulted only when the
    decision bar starts at/after 09:20 IST — before that the 9:25 screen
    does not exist yet and reading it would be look-ahead (quant-verifier
    HIGH, 2026-07-07).
    """
    index_ist = [ts.astimezone(_IST) for ts in window.index]
    dates_ist = [ts.date() for ts in index_ist]
    prev_day = sctx.prev_session_ohlc_for_window(
        dates_ist,
        [float(v) for v in window["open"]],
        [float(v) for v in window["high"]],
        [float(v) for v in window["low"]],
        [float(v) for v in window["close"]],
    )
    cross_section: dict[str, float] | None = None
    decision = index_ist[-1]
    screen_born = decision.timetz().replace(tzinfo=None) >= sctx.SCREEN_925_READY
    if cross_section_by_session is not None and screen_born:
        cross_section = cross_section_by_session.get(decision.date())
    return prev_day, cross_section


async def _cross_section_925_live(
    db: AsyncSession,
    timeframe: str,
    stock_ids: list[int],
    sym_map: dict[int, str],
) -> dict[date, dict[str, float]]:
    """9:25 cross-section from the profile's OWN intraday bars — the same
    per-symbol reconstruction the walk-forward uses (session_context), so
    live gate outcomes replay exactly.

    The ranking pool spans the resolved universe (8c-5b parity lesson: the
    pool must match the processed set); symbols without a prior close or an
    early bar are simply absent and the evaluator fails closed for them.
    """
    table = _TIMEFRAME_TABLE.get(timeframe)
    if table is None:
        raise ValueError(f"unknown timeframe {timeframe!r}")
    symbols = [sym_map[sid] for sid in stock_ids if sid in sym_map]
    if len(set(symbols)) != len(symbols):
        # Bars series are keyed by symbol; a dual-exchange listing would
        # interleave two stocks' bars into one series and corrupt its
        # screen pct (bug-hunter latent LOW — unreachable while ingestion
        # is NSE-only, loud if that ever changes).
        dupes = sorted({s for s in symbols if symbols.count(s) > 1})
        log.warning(
            "cross-section: symbols listed under multiple stock ids %s — "
            "their 9:25 screen values are unreliable",
            dupes,
        )
    t0 = datetime.now(tz=UTC) - timedelta(days=_XSEC_LOOKBACK_DAYS)
    series: dict[str, tuple[list[date], list[datetime], list[float]]] = {}
    for i in range(0, len(stock_ids), _XSEC_CHUNK):
        rows = (
            await db.execute(
                text(
                    f"SELECT stock_id, time, close FROM {table}"  # noqa: S608
                    " WHERE stock_id = ANY(:sids) AND time >= :t0"
                    " AND is_complete IS TRUE"
                    " ORDER BY stock_id, time"
                ),
                {"sids": stock_ids[i : i + _XSEC_CHUNK], "t0": t0},
            )
        ).fetchall()
        for r in rows:
            symbol = sym_map.get(r.stock_id)
            if symbol is None:
                continue
            dates_, times_, closes_ = series.setdefault(symbol, ([], [], []))
            ist = r.time.astimezone(_IST)
            dates_.append(ist.date())
            times_.append(ist)
            closes_.append(float(r.close))
    out: dict[date, dict[str, float]] = {}
    for symbol, (dates_, times_, closes_) in series.items():
        for d, pct in sctx.pct_change_at_925(dates_, times_, closes_).items():
            out.setdefault(d, {})[symbol] = pct
    return out


async def _load_window(
    db: AsyncSession, stock_id: int, timeframe: str, limit: int = 300
) -> pd.DataFrame:
    """Last ≤`limit` COMPLETED candles for one stock — the decision window."""
    table = _TIMEFRAME_TABLE.get(timeframe)
    if table is None:
        raise ValueError(f"unknown timeframe {timeframe!r}")
    rows = (
        await db.execute(
            text(
                f"SELECT time, open, high, low, close, volume FROM {table}"  # noqa: S608
                " WHERE stock_id = :sid AND is_complete IS TRUE"
                " ORDER BY time DESC LIMIT :lim"
            ),
            {"sid": stock_id, "lim": limit},
        )
    ).fetchall()
    if not rows:
        return pd.DataFrame()
    rows = list(reversed(rows))
    return pd.DataFrame(
        {
            "time": [r.time for r in rows],
            "open": [float(r.open) for r in rows],
            "high": [float(r.high) for r in rows],
            "low": [float(r.low) for r in rows],
            "close": [float(r.close) for r in rows],
            "volume": [int(r.volume) for r in rows],
        }
    ).set_index("time")


async def _validity_for(
    db: AsyncSession,
    profile: StrategyProfile,
    classification: str,
    now: datetime,
) -> datetime:
    """Profile validity_spec override, else classification default (§5)."""
    spec = profile.validity_spec
    if spec and spec.get("kind") == "trading_days":
        target = await market_calendar.add_trading_days(db, now, int(spec["n"]))
        offset = (target.date() - now.date()).days
        return compute_validity_until("swing", now, trading_days_offset=offset)
    if spec and spec.get("kind") == "same_day":
        return compute_validity_until("intraday", now)
    offset = await market_calendar.validity_offset_days(db, classification, now)
    return compute_validity_until(classification, now, trading_days_offset=offset)


async def _resolve_existing(
    db: AsyncSession, stock_id: int, profile_key: str, direction: str
) -> str:
    """Apply the supersede policy. Returns 'skip' | 'insert'."""
    existing = (
        await db.execute(
            select(Signal).where(
                Signal.stock_id == stock_id,
                Signal.profile_key == profile_key,
                Signal.status == "active",
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        return "insert"
    if existing.direction == direction:
        return "skip"
    existing.status = "superseded"
    existing.expired_at = datetime.now(tz=UTC)
    await db.flush()
    return "insert"


async def _process_stock(
    db: AsyncSession,
    profile: StrategyProfile,
    stock_id: int,
    symbol: str,
    flows: tuple[Decimal, Decimal],
    as_of: date,
    capital: Decimal,
    risk_pct: Decimal,
    cross_section_by_session: dict[date, dict[str, float]] | None = None,
) -> Signal | None:
    """One stock through the full profile pipeline. Returns the flushed
    Signal, or None (no signal / gated / rejected / deduped)."""
    window = await _load_window(db, stock_id, profile.timeframe)
    if window.empty or len(window) < 50:
        return None

    fii_net_5d, dii_net_5d = flows
    block_net = await get_stock_block_deal_net_cr(db, stock_id, as_of)
    result = score_signal(
        window,
        timeframe=profile.timeframe,
        min_confidence=profile.min_confidence,
        weight_multipliers={
            str(k): float(v) for k, v in (profile.weight_multipliers or {}).items()
        },
        fii_net_5d=fii_net_5d,
        dii_net_5d=dii_net_5d,
        stock_block_deal_net_cr=block_net,
    )
    if result is None:
        return None

    prev_day: dict[str, float] | None = None
    cross_section: dict[str, float] | None = None
    if profile.timeframe != "1d":
        prev_day, cross_section = _intraday_setup_context(window, cross_section_by_session)
    ctx = SetupContext(
        direction=result.direction,
        factors={f.name: (float(f.weight), float(f.score)) for f in result.factors},
        prev_day=prev_day,
        cross_section=cross_section,
        symbol=symbol,
    )
    passed, evidence = evaluate_conditions(profile.setup_conditions, window, ctx)
    if not passed:
        return None

    classification = classify_signal(profile.timeframe, result.factors, result.is_multibagger)
    entry = Decimal(str(window["close"].iloc[-1]))
    swing_low, swing_high = swing_levels(window)
    levels = safe_levels(
        direction=result.direction,
        classification=classification,
        entry=entry,
        swing_low=swing_low,
        swing_high=swing_high,
    )
    if levels is None:
        # Natural SL beyond the class cap OR degenerate/wrong-side pivot
        # (SL == entry crashes compute_quantity) — rejected, never clamped.
        return None
    stop_loss, _canon_tp = levels
    take_profit = _tp_from_template(profile.risk_template, result.direction, entry, stop_loss)

    qty_raw = compute_quantity(capital, risk_pct, entry, stop_loss)
    qty = volatility_adjusted_qty(qty_raw, window)
    if qty == 0:
        return None

    now = datetime.now(tz=UTC)
    validity = await _validity_for(db, profile, classification, now)
    signal = Signal(
        stock_id=stock_id,
        direction=result.direction,
        classification=classification,
        timeframe=profile.timeframe,
        entry_price=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        suggested_qty=qty,
        confidence_pct=result.confidence_pct,
        factor_scores={
            f.name: {
                "weight": f.weight,
                "score": round(f.score, 4),
                "explanation": f.explanation,
            }
            for f in result.factors
        },
        triggering_patterns=result.triggering_patterns or None,
        triggering_indicators=result.triggering_indicators or None,
        headline=build_headline(symbol, result, entry, stop_loss, take_profit, qty),
        status="active",
        validity_until=validity,
        profile_id=profile.id,
        profile_key=profile.key,
        setup_trigger=evidence,
        volatility_reduced=qty != qty_raw,
    )
    # SAVEPOINT per stock: an IntegrityError (concurrent run won the
    # partial-unique race) must not roll back earlier suggestions.
    try:
        async with db.begin_nested():
            action = await _resolve_existing(db, stock_id, profile.key, result.direction)
            if action == "skip":
                return None
            db.add(signal)
            await db.flush()
    except IntegrityError:
        log.info("profile %s: %s raced an existing active suggestion", profile.key, symbol)
        return None
    return signal


async def run_profile(
    db: AsyncSession,
    profile: StrategyProfile,
    capital: Decimal,
    risk_pct: Decimal,
) -> list[Signal]:
    """Run one profile over its universe; persists and returns new Signals."""
    stock_ids, sym_map = await resolve_universe(db, profile.universe_spec)
    if not stock_ids:
        log.warning("profile %s: universe resolved empty", profile.key)
        return []

    as_of = datetime.now(tz=UTC).astimezone(_IST).date()
    flows = await get_market_flow_5d(db, as_of)

    if profile.timeframe == "1m" and any(
        str(c.get("type")) in {"pdh_breakout", "pdl_breakdown", "opening_gap"}
        for c in profile.setup_conditions
    ):
        # A 1m session is 375 bars > the 300-bar window cap, so prev-day
        # context can never assemble — every condition fails closed. Safe
        # direction, but it must be loud, not a silently dead profile
        # (bug-hunter latent LOW, 2026-07-09).
        log.warning(
            "profile %s: prev-day setups cannot evaluate on 1m windows "
            "(300-bar cap < one session) — all conditions will fail closed",
            profile.key,
        )

    # 9:25 cross-section: one universe-wide build per run, only when an
    # intraday profile actually gates on it. Per-stock consultation stays
    # decision-bar-relative inside _process_stock.
    cross_section_by_session: dict[date, dict[str, float]] | None = None
    if profile.timeframe != "1d" and any(
        str(c.get("type")) == "top_gainer_925" for c in profile.setup_conditions
    ):
        cross_section_by_session = await _cross_section_925_live(
            db, profile.timeframe, list(stock_ids), sym_map
        )

    created: list[Signal] = []
    for stock_id in stock_ids:
        symbol = sym_map.get(stock_id, str(stock_id))
        try:
            signal = await _process_stock(
                db,
                profile,
                stock_id,
                symbol,
                flows,
                as_of,
                capital,
                risk_pct,
                cross_section_by_session=cross_section_by_session,
            )
        except Exception:
            # One pathological stock must never kill the remaining universe
            # or the profiles after this one (a ValueError here used to take
            # down the whole nightly run — Phase-2 gate finding).
            log.exception("profile %s: %s failed — skipping stock", profile.key, symbol)
            continue
        if signal is not None:
            created.append(signal)

    if created:
        await db.commit()
    return created


async def run_scheduled_profiles(
    db: AsyncSession,
    schedule: str,
    capital: Decimal,
    risk_pct: Decimal,
) -> dict[str, int]:
    """Run every ACTIVE profile on the given schedule key."""
    profiles = (
        (
            await db.execute(
                select(StrategyProfile).where(
                    StrategyProfile.status == "active",
                    StrategyProfile.schedule == schedule,
                )
            )
        )
        .scalars()
        .all()
    )
    counts: dict[str, int] = {}
    for profile in profiles:
        created = await run_profile(db, profile, capital, risk_pct)
        counts[profile.key] = len(created)
    log.info("profile run (%s): %s", schedule, counts)
    return counts
