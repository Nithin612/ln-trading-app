"""Phase 9 — Strategy Lab API.

POST /strategy/runs          — run a single backtest with given config, save result
GET  /strategy/runs          — list all saved runs (sorted by Sharpe desc by default)
GET  /strategy/runs/{id}     — get a single run (includes equity_curve + trades_json)
DELETE /strategy/runs/{id}   — delete a saved run
POST /strategy/preset-scan   — run all named presets, return ranked comparison (not saved)
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.backtest.engine import BacktestConfig, BacktestEngine
from app.backtest.grid_search import run_preset_scan
from app.core.deps import get_current_user, get_db
from app.models.stock import Stock
from app.models.strategy import StrategyRun
from app.models.user import User
from app.schemas.strategy import (
    PresetScanEntry,
    PresetScanRequest,
    PresetScanResponse,
    RunBacktestRequest,
    StrategyRunListResponse,
    StrategyRunOut,
)

router = APIRouter(prefix="/strategy", tags=["strategy"])

_TIMEFRAME_TABLE: dict[str, str] = {
    "1d":  "ohlcv_1d",
    "1h":  "ohlcv_1h",
    "15m": "ohlcv_15m",
    "5m":  "ohlcv_5m",
    "1m":  "ohlcv_1m",
}


async def _load_candles(
    db: AsyncSession,
    stock_ids: list[int],
    symbol_map: dict[int, str],
    timeframe: str,
    period_start: datetime,
    period_end: datetime,
) -> dict[str, pd.DataFrame]:
    """Fetch OHLCV rows from DB and return as {symbol: DataFrame}."""
    table = _TIMEFRAME_TABLE.get(timeframe, "ohlcv_1d")
    result: dict[str, pd.DataFrame] = {}

    for sid in stock_ids:
        rows = await db.execute(
            text(
                f"SELECT time, open, high, low, close, volume "  # noqa: S608
                f"FROM {table} "
                f"WHERE stock_id = :sid AND time >= :from_t AND time <= :to_t "
                f"ORDER BY time ASC"
            ),
            {"sid": sid, "from_t": period_start, "to_t": period_end},
        )
        data = rows.fetchall()
        if not data:
            continue
        df = pd.DataFrame(
            data, columns=["time", "open", "high", "low", "close", "volume"]
        )
        df["open"] = df["open"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)
        df.set_index("time", inplace=True)
        result[symbol_map[sid]] = df

    return result


async def _resolve_stock_ids(
    db: AsyncSession,
    universe: str,
    symbols: list[str] | None,
) -> tuple[list[int], dict[int, str]]:
    """Return (stock_id_list, {stock_id: symbol}) for the requested universe/symbols."""
    if symbols:
        q = select(Stock.id, Stock.symbol).where(
            Stock.symbol.in_(symbols), Stock.is_active.is_(True)
        )
    elif universe.upper() == "NIFTY50":
        q = select(Stock.id, Stock.symbol).where(
            Stock.is_nifty50.is_(True), Stock.is_active.is_(True)
        )
    elif universe.upper() == "BANKNIFTY":
        q = select(Stock.id, Stock.symbol).where(
            Stock.is_banknifty.is_(True), Stock.is_active.is_(True)
        )
    elif universe.upper() == "FNO":
        q = select(Stock.id, Stock.symbol).where(
            Stock.is_fno.is_(True), Stock.is_active.is_(True)
        )
    else:
        q = select(Stock.id, Stock.symbol).where(Stock.is_active.is_(True))

    rows = await db.execute(q)
    pairs = rows.fetchall()
    ids = [r[0] for r in pairs]
    sym_map = {r[0]: r[1] for r in pairs}
    return ids, sym_map


def _trades_to_json(trades: list[Any]) -> list[dict[str, Any]]:
    out = []
    for t in trades:
        out.append({
            "stock": t.stock,
            "direction": t.direction,
            "classification": t.classification,
            "confidence_pct": t.confidence_pct,
            "entry_date": t.entry_date.isoformat() if t.entry_date else None,
            "entry_price": t.entry_price,
            "stop_loss": t.stop_loss,
            "take_profit": t.take_profit,
            "qty": t.qty,
            "exit_date": t.exit_date.isoformat() if t.exit_date else None,
            "exit_price": t.exit_price,
            "pnl_pct": t.pnl_pct,
            "hit_target": t.hit_target,
            "hit_sl": t.hit_sl,
        })
    return out


@router.post("/runs", response_model=StrategyRunOut, status_code=status.HTTP_201_CREATED)
async def create_run(
    req: RunBacktestRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> StrategyRunOut:
    """Run a backtest with the given configuration and save the result."""
    if req.period_end <= req.period_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="period_end must be after period_start",
        )

    stock_ids, symbol_map = await _resolve_stock_ids(db, req.universe, req.symbols)
    if not stock_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No active stocks found for universe '{req.universe}'",
        )

    def _utc(dt: datetime) -> datetime:
        return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt

    candles = await _load_candles(
        db, stock_ids, symbol_map, req.timeframe,
        _utc(req.period_start), _utc(req.period_end),
    )

    cfg = BacktestConfig(
        timeframe=req.timeframe,
        universe=req.universe,
        capital=req.capital,
        risk_pct=req.risk_pct,
        min_confidence=req.min_confidence,
        weight_multipliers=req.weight_multipliers,
    )
    # CPU-bound pandas loop — run it on a worker thread so it can't freeze
    # the event loop (REST + /ws/live share it). Proper job-queue offload
    # arrives with the Rust engine in Phase 1/6.
    bt_result = await asyncio.to_thread(BacktestEngine(cfg).run, candles)

    run = StrategyRun(
        name=req.name,
        description=req.description,
        factor_weights=req.weight_multipliers or {},
        timeframe=req.timeframe,
        universe=req.universe,
        period_start=req.period_start,
        period_end=req.period_end,
        status="done",
        capital=req.capital,
        risk_pct=req.risk_pct,
        min_confidence=req.min_confidence,
        total_trades=bt_result.total_trades,
        winning_trades=bt_result.winning_trades,
        losing_trades=bt_result.losing_trades,
        win_rate_pct=Decimal(str(bt_result.win_rate_pct)),
        total_pnl_pct=Decimal(str(bt_result.total_pnl_pct)),
        avg_pnl_pct=Decimal(str(bt_result.avg_pnl_pct)),
        avg_rr=Decimal(str(bt_result.avg_rr)),
        sharpe=Decimal(str(bt_result.sharpe)),
        sortino=Decimal(str(bt_result.sortino)),
        max_drawdown_pct=Decimal(str(bt_result.max_drawdown_pct)),
        avg_holding_days=Decimal(str(bt_result.avg_holding_days)),
        equity_curve=bt_result.equity_curve,
        trades_json=_trades_to_json(bt_result.trades),
    )
    db.add(run)
    await db.flush()
    await _assign_rankings(db)
    await db.commit()
    await db.refresh(run)
    return StrategyRunOut.model_validate(run)


_SORT_PATTERN = r"^(sharpe|win_rate_pct|max_drawdown_pct|created_at)$"


@router.get("/runs", response_model=StrategyRunListResponse)
async def list_runs(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    sort_by: str = Query(default="sharpe", pattern=_SORT_PATTERN),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> StrategyRunListResponse:
    sort_col = {
        "sharpe": StrategyRun.sharpe,
        "win_rate_pct": StrategyRun.win_rate_pct,
        "max_drawdown_pct": StrategyRun.max_drawdown_pct,
        "created_at": StrategyRun.created_at,
    }[sort_by]

    order = asc(sort_col) if sort_by == "max_drawdown_pct" else desc(sort_col)

    count_q = await db.execute(select(func.count(StrategyRun.id)))
    total = int(count_q.scalar() or 0)

    result = await db.execute(
        select(StrategyRun).order_by(order).offset(offset).limit(limit)
    )
    runs = result.scalars().all()
    return StrategyRunListResponse(
        total=total,
        runs=[StrategyRunOut.model_validate(r) for r in runs],
    )


@router.get("/runs/{run_id}", response_model=StrategyRunOut)
async def get_run(
    run_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> StrategyRunOut:
    run = await db.get(StrategyRun, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return StrategyRunOut.model_validate(run)


@router.delete("/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_run(
    run_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> None:
    run = await db.get(StrategyRun, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    await db.delete(run)
    await db.commit()


@router.post("/preset-scan", response_model=PresetScanResponse)
async def preset_scan(
    req: PresetScanRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> PresetScanResponse:
    """Run all named presets on the requested universe and return ranked results.

    Results are NOT saved to the database — use this to quickly compare strategies
    before committing to a full saved run.
    """
    if req.period_end <= req.period_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="period_end must be after period_start",
        )

    stock_ids, symbol_map = await _resolve_stock_ids(db, req.universe, req.symbols)
    if not stock_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No active stocks found for universe '{req.universe}'",
        )

    def _utc(dt: datetime) -> datetime:
        return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt

    candles = await _load_candles(
        db, stock_ids, symbol_map, req.timeframe,
        _utc(req.period_start), _utc(req.period_end),
    )

    # Same event-loop protection as create_run: N backtests, CPU-bound.
    entries = await asyncio.to_thread(
        run_preset_scan,
        candles,
        timeframe=req.timeframe,
        capital=req.capital,
        risk_pct=req.risk_pct,
        min_confidence=req.min_confidence,
    )

    return PresetScanResponse(entries=[
        PresetScanEntry(
            preset_name=e.preset_name,
            weight_multipliers=e.weight_multipliers,
            total_trades=e.result.total_trades,
            win_rate_pct=e.result.win_rate_pct,
            sharpe=e.result.sharpe,
            sortino=e.result.sortino,
            max_drawdown_pct=e.result.max_drawdown_pct,
            avg_rr=e.result.avg_rr,
            avg_holding_days=e.result.avg_holding_days,
            equity_curve=e.result.equity_curve,
        )
        for e in entries
    ])


async def _assign_rankings(db: AsyncSession) -> None:
    """Re-rank all strategy_runs by Sharpe descending (1 = best)."""
    await db.execute(
        text(
            "UPDATE strategy_runs SET ranking = ranked.rn "
            "FROM (SELECT id, ROW_NUMBER() OVER (ORDER BY sharpe DESC NULLS LAST) AS rn "
            "FROM strategy_runs) ranked "
            "WHERE strategy_runs.id = ranked.id"
        )
    )
