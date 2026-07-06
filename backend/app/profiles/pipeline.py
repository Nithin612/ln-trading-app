"""Per-profile suggestion pipeline (Phase 2 slice 7).

For each ACTIVE profile: resolve universe → load candles → score through
the FROZEN python confluence engine (real FII/DII flows) → gate on the
profile's setup conditions → risk-template TP override (SL stays
classification canon; reject-don't-clamp preserved) → persist Signal rows
tagged (profile_id, profile_key, setup_trigger, volatility_reduced).

Idempotency/supersede policy (design-reviewed):
  - same (stock, profile_key) active + same direction  → skip
  - same pair active + OPPOSITE direction              → supersede old, insert new
  - races resolve at the DB partial-unique index (IntegrityError → skip)
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.risk import compute_levels, compute_quantity, volatility_adjusted_qty
from app.analysis.structure.dow import swing_levels
from app.models.profile import StrategyProfile
from app.models.signal import Signal
from app.profiles.setups import SetupContext, evaluate_conditions
from app.services import market_calendar
from app.services.fii_dii_service import get_market_flow_5d, get_stock_block_deal_net_cr
from app.services.signal_service import score_signal
from app.services.universe_service import resolve_universe
from app.signals.classifier import classify_signal
from app.signals.expiry import compute_validity_until
from app.signals.headline import build_headline

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


def _tp_from_template(
    template: dict[str, object], direction: str, entry: Decimal, stop_loss: Decimal
) -> Decimal:
    """§6 take-profit per the profile's risk template. SL is never touched
    (classification canon, reject-don't-clamp happened upstream)."""
    kind = str(template.get("kind"))
    sign = 1 if direction == "BUY" else -1
    if kind == "rr":
        ratio = Decimal(str(template["ratio"]))
        risk = abs(entry - stop_loss)
        tp = entry + sign * risk * ratio
    elif kind in ("flat_pct", "flat_pct_trailing"):
        pct = Decimal(str(template["target_pct"]))
        tp = entry * (Decimal("1") + sign * pct / Decimal("100"))
    elif kind == "ema_trail":
        pct = Decimal(str(template["min_target_pct"]))
        tp = entry * (Decimal("1") + sign * pct / Decimal("100"))
    else:  # unreachable — schema rejects unknown kinds at load
        raise ValueError(f"unknown risk template kind {kind!r}")
    return tp.quantize(Decimal("0.0001"))


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
        fii_net_5d=fii_net_5d,
        dii_net_5d=dii_net_5d,
        stock_block_deal_net_cr=block_net,
    )
    if result is None:
        return None

    ctx = SetupContext(
        direction=result.direction,
        factors={f.name: (float(f.weight), float(f.score)) for f in result.factors},
        symbol=symbol,
    )
    passed, evidence = evaluate_conditions(profile.setup_conditions, window, ctx)
    if not passed:
        return None

    classification = classify_signal(profile.timeframe, result.factors, result.is_multibagger)
    entry = Decimal(str(window["close"].iloc[-1]))
    swing_low, swing_high = swing_levels(window)
    levels = compute_levels(
        direction=result.direction,
        classification=classification,
        entry=entry,
        swing_low=swing_low,
        swing_high=swing_high,
    )
    if levels is None:
        return None  # natural SL beyond the class cap — rejected, never clamped
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

    created: list[Signal] = []
    for stock_id in stock_ids:
        signal = await _process_stock(
            db,
            profile,
            stock_id,
            sym_map.get(stock_id, str(stock_id)),
            flows,
            as_of,
            capital,
            risk_pct,
        )
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
