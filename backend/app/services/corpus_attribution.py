"""Corpus-scale entry attribution (Phase 6 slice 6.2b).

Runs the parity-clean Rust backtest (`tradecore.run_universe`) over the Nifty50
daily corpus and feeds each trade through the SAME `entry_attribution` aggregator
(`attribute_rows`). Where the live loader reads recorded outcomes, this
reconstructs the two dimensions the trade dict doesn't carry — regime from the
raw ADX level (`tradecore.adx`, length 14, matching the frozen `adx_factor`) and
MFE/MAE from the shared `tape_excursion` over the trade's fill→exit window.

The FROZEN engine is untouched: the backtest already exists and is parity-pinned
(`tests/parity/test_backtest_ext_parity.py`). Read-only — measurement only,
never feeds scoring/sizing/gating.
"""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.entry_attribution import AttributionReport, Row, attribute_rows
from app.services.excursion import tape_excursion

log = logging.getLogger(__name__)

_ADX_LEN = 14  # matches app/analysis/indicators/adx.py adx_factor(length=14)
_SIDE = {"BUY": "LONG", "SELL": "SHORT"}
_CORPUS_CAPITAL = "100000"  # capital/risk only set qty; they don't change which signals fire
_CORPUS_RISK = "2"

# (symbol, times, open, high, low, close, volume)
_StockBars = tuple[
    str, list[datetime], list[float], list[float], list[float], list[float], list[float]
]


async def load_nifty50_daily(db: AsyncSession, *, min_rows: int = 300) -> list[_StockBars]:
    """Per Nifty50 stock: (symbol, times, o, h, l, c, v), ascending. Skips stocks
    with < min_rows completed bars (the confluence window needs warmup)."""
    rows = (
        await db.execute(
            text(
                "SELECT s.symbol, o.time, o.open, o.high, o.low, o.close, o.volume"
                " FROM ohlcv_1d o JOIN stocks s ON s.id = o.stock_id"
                " WHERE s.is_nifty50 IS TRUE AND o.is_complete IS TRUE"
                " ORDER BY s.symbol, o.time"
            )
        )
    ).all()
    by_sym: dict[str, list[Any]] = {}
    for r in rows:
        by_sym.setdefault(r.symbol, []).append(r)
    out: list[_StockBars] = []
    for sym, rs in by_sym.items():
        if len(rs) < min_rows:
            continue
        out.append(
            (
                sym,
                [r.time for r in rs],
                [float(r.open) for r in rs],
                [float(r.high) for r in rs],
                [float(r.low) for r in rs],
                [float(r.close) for r in rs],
                [float(r.volume) for r in rs],
            )
        )
    return out


def _status(trade: dict[str, Any]) -> str:
    if trade.get("hit_target"):
        return "tp_first"
    if trade.get("hit_sl"):
        return "sl_first"
    return "expired_open"  # force-exited at the last bar, entered but neither TP nor SL


def trade_to_row(
    trade: dict[str, Any],
    times: list[datetime],
    high: list[float],
    low: list[float],
    close: list[float],
    adx_levels: list[float],
) -> Row | None:
    """Reconstruct an attribution Row from one backtest trade + its bars. Regime
    from the ADX level at fill; MFE/MAE via tape_excursion over [fill_idx, exit_idx].
    Returns None on an unmappable direction or out-of-range indices."""
    side = _SIDE.get(str(trade["direction"]))
    if side is None:
        return None
    fill = int(trade["fill_idx"])
    exit_i = int(trade["exit_idx"])
    if not (0 <= fill <= exit_i < len(close)):
        return None

    entry = Decimal(str(trade["entry"]))
    risk = abs(entry - Decimal(str(trade["sl"])))
    rr = float(abs(Decimal(str(trade["tp"])) - entry) / risk) if risk > 0 else None

    bars = [
        (times[i], Decimal(str(high[i])), Decimal(str(low[i])), Decimal(str(close[i])))
        for i in range(fill, exit_i + 1)
    ]
    exc = tape_excursion(bars, side=side, entry=entry, risk=risk, quantity=1)

    # Regime at the DECISION bar (fill_idx − 1): fill_idx is the N+1 fill, and the
    # live loader's ADX is likewise from the decision bar N, so both cohorts bucket
    # regime at the same relative bar (bug-hunter LOW 2026-08-13). It's also the
    # regime you'd actually gate the entry on.
    dec = fill - 1
    adx = adx_levels[dec] if 0 <= dec < len(adx_levels) else None
    if adx is not None and math.isnan(adx):
        adx = None  # ADX warmup — no regime yet

    # trade["factors"] is {name: [weight, score]} — take the score (index 1).
    factors = {
        n: float(ws[1])
        for n, ws in (trade.get("factors") or {}).items()
        if isinstance(ws, (list, tuple)) and len(ws) >= 2 and isinstance(ws[1], (int, float))
    }
    return Row(
        status=_status(trade),
        mfe_r=float(exc.mfe_r) if exc is not None else None,
        mae_r=float(exc.mae_r) if exc is not None else None,
        rr=rr,
        confidence=int(trade["confidence"]),
        adx=adx,
        direction=str(trade["direction"]),
        setup="(corpus base)",
        created_at=times[fill],
        timeframe="1d",
        factors=factors,
    )


async def compute_corpus_attribution(
    db: AsyncSession, *, min_confidence: int = 70
) -> AttributionReport:
    """Attribution over the Nifty50 daily backtest corpus (Rust run_universe).
    Read-only; the engine is the parity-pinned tradecore wheel."""
    import tradecore  # heavy wheel — deferred (absent in some CI envs)

    stocks_data = await load_nifty50_daily(db)
    if not stocks_data:
        log.warning("corpus attribution: no Nifty50 daily bars — run scripts/backfill_eod.py")
        return AttributionReport(cohort="corpus", since=datetime.now(tz=UTC), total=0, tables=[])

    universe = [(sym, o, h, lo, c, v) for sym, _t, o, h, lo, c, v in stocks_data]
    results = tradecore.run_universe(universe, "1d", _CORPUS_CAPITAL, _CORPUS_RISK, min_confidence)

    by_sym = {sym: (t, h, lo, c) for sym, t, _o, h, lo, c, _v in stocks_data}
    rows: list[Row] = []
    for sym, trades in results:
        times, high, low, close = by_sym[sym]
        adx_levels, _plus_di, _minus_di = tradecore.adx(high, low, close, _ADX_LEN)
        for trade in trades:
            row = trade_to_row(trade, times, high, low, close, adx_levels)
            if row is not None:
                rows.append(row)

    since = min((r.created_at for r in rows), default=datetime.now(tz=UTC))
    return AttributionReport(
        cohort="corpus", since=since, total=len(rows), tables=attribute_rows(rows)
    )
