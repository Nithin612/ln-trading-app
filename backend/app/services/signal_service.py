"""Signal generation service — ties together analysis engine, risk sizer, and persistence."""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.confluence import ConfluenceResult
from app.analysis.confluence import score_signal as _score_signal_python
from app.analysis.indicators.ema import _ema
from app.analysis.risk import compute_levels, compute_quantity, volatility_adjusted_qty
from app.core.config import settings
from app.models.market_data import OhlcvDaily
from app.models.signal import Signal
from app.models.stock import Stock
from app.services import market_calendar
from app.signals.classifier import classify_signal
from app.signals.expiry import compute_validity_until
from app.signals.headline import build_headline

log = logging.getLogger(__name__)


def score_signal(
    candles: pd.DataFrame,
    timeframe: str = "1d",
    min_confidence: int = 70,
    **flows: Decimal,
) -> "ConfluenceResult | None":
    """ENGINE_IMPL dispatch (Phase 1): frozen Python engine or tradecore.

    Rust path is parity-gated (tests/parity) — factor scores, confidence
    integers, and decisions are exact-equal by test. The pinned domain is
    timeframe="1d" with zero flows; outside it the reference engine answers.
    """
    if settings.engine_impl == "rust":
        if any(flows.values()):
            # tradecore.score_signal has no flow inputs yet; a weighted factor
            # (±5 pts) silently dropped could flip decisions — fail loud.
            raise NotImplementedError(
                "ENGINE_IMPL=rust cannot score FII/DII flows yet — "
                "plumb FlowInputs through tradecore before passing flows"
            )
        if timeframe != "1d":
            # Only 1d is fixture-pinned; Rust intraday classification/pivots
            # stay unpinned until the Phase-3 goldens land.
            log.warning(
                "engine_impl=rust is unpinned for timeframe=%s — answering "
                "with the python reference engine",
                timeframe,
            )
            return _score_signal_python(candles, timeframe, min_confidence, **flows)
        import tradecore

        from app.analysis.types import FactorResult

        result = tradecore.score_signal(
            [float(v) for v in candles["open"]],
            [float(v) for v in candles["high"]],
            [float(v) for v in candles["low"]],
            [float(v) for v in candles["close"]],
            [float(v) for v in candles["volume"]],
            timeframe,
            min_confidence,
        )
        if result is None:
            return None
        factors = [
            FactorResult(name, w, s, "tradecore", [])
            for name, (w, s) in result["factors"].items()
        ]
        return ConfluenceResult(
            direction=result["direction"],
            confidence_pct=result["confidence"],
            normalized_score=result["normalized"],
            factors=factors,
            triggering_patterns=[],
            triggering_indicators=[],
            is_multibagger=result["multibagger"],
        )
    return _score_signal_python(candles, timeframe, min_confidence, **flows)


async def _load_candles(
    db: AsyncSession,
    stock_id: int,
    limit: int = 300,
) -> pd.DataFrame:
    """Load the most recent `limit` completed daily candles for a stock."""
    result = await db.execute(
        select(OhlcvDaily)
        .where(OhlcvDaily.stock_id == stock_id, OhlcvDaily.is_complete.is_(True))
        .order_by(OhlcvDaily.time.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
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
            "volume": [r.volume for r in rows],
        }
    ).set_index("time")


async def _has_active_signal(
    db: AsyncSession,
    stock_id: int,
    timeframe: str,
    direction: str,
) -> bool:
    """True if an unexpired active signal already exists for this setup.

    Idempotency guard: a persistent setup would otherwise insert a
    near-identical signal on every candle close / nightly rerun while the
    previous one is still valid. Supersede-on-stronger-signal is a Phase 2
    design decision; triage only prevents duplicates.
    """
    now = datetime.now(tz=UTC)
    result = await db.execute(
        select(Signal.id)
        .where(
            Signal.stock_id == stock_id,
            Signal.timeframe == timeframe,
            Signal.direction == direction,
            Signal.status == "active",
            Signal.validity_until > now,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


def _swing_levels(candles: pd.DataFrame, n: int = 5) -> tuple[Decimal | None, Decimal | None]:
    """Delegates to the shared implementation (SL canon, 2026-07-04)."""
    from app.analysis.structure.dow import swing_levels

    return swing_levels(candles, n)


async def generate_signal_for_stock(
    db: AsyncSession,
    stock: Stock,
    capital: Decimal,
    risk_pct: Decimal,
    timeframe: str = "1d",
    fii_net_5d: Decimal = Decimal("0"),
    dii_net_5d: Decimal = Decimal("0"),
    stock_block_deal_net_cr: Decimal = Decimal("0"),
    min_confidence: int | None = None,
) -> Signal | None:
    """Run the full pipeline for one stock and return a Signal ORM object, or None.

    The returned object is NOT yet added to the session — caller decides whether to persist.
    """
    min_conf = min_confidence if min_confidence is not None else settings.min_signal_confidence
    candles = await _load_candles(db, stock.id)
    if candles.empty or len(candles) < 50:
        return None

    result = score_signal(
        candles,
        timeframe=timeframe,
        min_confidence=min_conf,
        fii_net_5d=fii_net_5d,
        dii_net_5d=dii_net_5d,
        stock_block_deal_net_cr=stock_block_deal_net_cr,
    )
    if result is None:
        return None

    if await _has_active_signal(db, stock.id, timeframe, result.direction):
        return None

    classification = classify_signal(timeframe, result.factors, result.is_multibagger)

    entry = Decimal(str(candles["close"].iloc[-1]))
    swing_low, swing_high = _swing_levels(candles)

    # EMA20 daily for positional SL
    ema20_series = _ema(candles["close"], 20)
    ema20_daily: Decimal | None = None
    if not ema20_series.dropna().empty:
        ema20_daily = Decimal(str(ema20_series.iloc[-1]))

    levels = compute_levels(
        direction=result.direction,
        classification=classification,
        entry=entry,
        swing_low=swing_low,
        swing_high=swing_high,
        ema20_daily=ema20_daily,
    )
    if levels is None:
        return None

    stop_loss, take_profit = levels
    qty = compute_quantity(capital, risk_pct, entry, stop_loss)
    # §4 volatility regime (adjudicated 2026-07-05): same reduction the
    # backtest applies — the decision window here IS the loaded candles.
    qty = volatility_adjusted_qty(qty, candles)
    if qty == 0:
        return None

    now = datetime.now(tz=UTC)
    # §5 validity in real TRADING days via the NSE calendar (Phase 2).
    offset = await market_calendar.validity_offset_days(db, classification, now)
    validity = compute_validity_until(classification, now, trading_days_offset=offset)
    headline = build_headline(stock.symbol, result, entry, stop_loss, take_profit, qty)

    factor_scores = {
        f.name: {
            "weight": f.weight,
            "score": round(f.score, 4),
            "explanation": f.explanation,
        }
        for f in result.factors
    }

    signal = Signal(
        stock_id=stock.id,
        direction=result.direction,
        classification=classification,
        timeframe=timeframe,
        entry_price=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        suggested_qty=qty,
        confidence_pct=result.confidence_pct,
        factor_scores=factor_scores,
        triggering_patterns=result.triggering_patterns or None,
        triggering_indicators=result.triggering_indicators or None,
        headline=headline,
        status="active",
        validity_until=validity,
        created_at=now,
    )
    return signal


async def run_nightly_signal_generation(
    db: AsyncSession,
    capital: Decimal,
    risk_pct: Decimal,
    timeframe: str = "1d",
) -> list[Signal]:
    """Generate signals for all active stocks and persist new ones."""
    stocks_result = await db.execute(
        select(Stock).where(Stock.is_active.is_(True))
    )
    stocks = stocks_result.scalars().all()

    generated: list[Signal] = []
    for stock in stocks:
        signal = await generate_signal_for_stock(
            db, stock, capital, risk_pct, timeframe
        )
        if signal:
            db.add(signal)
            generated.append(signal)

    if generated:
        await db.commit()
    return generated


async def run_live_signal_generation(
    db: AsyncSession,
    stock_id: int,
    timeframe: str,
    capital: Decimal,
    risk_pct: Decimal,
) -> int:
    """Re-run signal generation for one stock after a live candle closes.

    Uses intraday candles (from ohlcv_5m / ohlcv_15m / ohlcv_1h) instead of daily.
    Returns number of new signals produced (0 or 1).
    """
    from app.models.market_data import Ohlcv1h, Ohlcv1m, Ohlcv5m, Ohlcv15m

    _tf_model: dict[str, type[Any]] = {
        "1m": Ohlcv1m,
        "5m": Ohlcv5m,
        "15m": Ohlcv15m,
        "1h": Ohlcv1h,
        "1d": OhlcvDaily,
    }
    model = _tf_model.get(timeframe, OhlcvDaily)

    stock_result = await db.execute(
        select(Stock).where(Stock.id == stock_id, Stock.is_active.is_(True))
    )
    stock = stock_result.scalar_one_or_none()
    if stock is None:
        return 0

    result = await db.execute(
        select(model)
        .where(model.stock_id == stock_id, model.is_complete.is_(True))
        .order_by(model.time.desc())
        .limit(300)
    )
    rows = result.scalars().all()
    if not rows or len(rows) < 50:
        return 0

    rows = list(reversed(rows))
    candles = pd.DataFrame(
        {
            "time": [r.time for r in rows],
            "open": [float(r.open) for r in rows],
            "high": [float(r.high) for r in rows],
            "low": [float(r.low) for r in rows],
            "close": [float(r.close) for r in rows],
            "volume": [r.volume for r in rows],
        }
    ).set_index("time")

    score = score_signal(
        candles, timeframe=timeframe, min_confidence=settings.min_signal_confidence
    )
    if score is None:
        return 0

    if await _has_active_signal(db, stock_id, timeframe, score.direction):
        return 0

    classification = classify_signal(timeframe, score.factors, score.is_multibagger)
    entry = Decimal(str(candles["close"].iloc[-1]))
    swing_low, swing_high = _swing_levels(candles)
    ema20_series = _ema(candles["close"], 20)
    ema20_daily = Decimal(str(ema20_series.iloc[-1])) if not ema20_series.dropna().empty else None

    levels = compute_levels(
        direction=score.direction,
        classification=classification,
        entry=entry,
        swing_low=swing_low,
        swing_high=swing_high,
        ema20_daily=ema20_daily,
    )
    if levels is None:
        return 0

    stop_loss, take_profit = levels
    qty = compute_quantity(capital, risk_pct, entry, stop_loss)
    # §4 volatility regime (adjudicated 2026-07-05, item F)
    qty = volatility_adjusted_qty(qty, candles)
    if qty == 0:
        return 0

    now = datetime.now(tz=UTC)
    # §5 validity in real TRADING days via the NSE calendar (Phase 2).
    offset = await market_calendar.validity_offset_days(db, classification, now)
    validity = compute_validity_until(classification, now, trading_days_offset=offset)
    headline = build_headline(stock.symbol, score, entry, stop_loss, take_profit, qty)
    factor_scores = {
        f.name: {"weight": f.weight, "score": round(f.score, 4), "explanation": f.explanation}
        for f in score.factors
    }

    signal = Signal(
        stock_id=stock_id,
        direction=score.direction,
        classification=classification,
        timeframe=timeframe,
        entry_price=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        suggested_qty=qty,
        confidence_pct=score.confidence_pct,
        factor_scores=factor_scores,
        triggering_patterns=score.triggering_patterns or None,
        triggering_indicators=score.triggering_indicators or None,
        headline=headline,
        status="active",
        validity_until=validity,
        created_at=now,
    )
    db.add(signal)
    await db.commit()
    return 1
