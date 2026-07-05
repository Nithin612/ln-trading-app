"""Cross-language parity suite (Phase 1 exit gate).

Drives the FROZEN Python engine and tradecore (Rust) over real DB data and
demands: exact factor scores, exact confidence integers, exact signal
decisions, exact backtest trade lists. Requires the 3y backfill
(scripts/backfill_eod.py) — skips cleanly on an empty database.
"""

from decimal import Decimal

import pandas as pd
import pytest
import tradecore
from app.analysis.confluence import run_all_factors, score_from_factors
from app.backtest.engine import BacktestConfig, BacktestEngine
from sqlalchemy import text

pytestmark = pytest.mark.parity


def _dev_db_url() -> str:
    """The parity corpus lives in the DEV database (3y backfill), not the
    per-test truncated test DB that conftest points the app at."""
    from pathlib import Path

    env = Path(__file__).resolve().parents[3] / ".env"  # repo root
    for line in env.read_text().splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("DATABASE_URL not found in backend/.env")


async def _load(symbols: list[str], min_rows: int) -> dict[str, pd.DataFrame]:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(_dev_db_url(), poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        rows = (
            await db.execute(
                text(
                    "SELECT s.symbol, o.time, o.open, o.high, o.low, o.close, o.volume"
                    " FROM ohlcv_1d o JOIN stocks s ON s.id = o.stock_id"
                    " WHERE s.symbol = ANY(:syms) ORDER BY s.symbol, o.time"
                ),
                {"syms": symbols},
            )
        ).fetchall()
    await engine.dispose()
    out: dict[str, list] = {}
    for r in rows:
        out.setdefault(r.symbol, []).append(r)
    return {
        sym: pd.DataFrame(
            {
                "open": [float(r.open) for r in rs],
                "high": [float(r.high) for r in rs],
                "low": [float(r.low) for r in rs],
                "close": [float(r.close) for r in rs],
                "volume": [int(r.volume) for r in rs],
            }
        )
        for sym, rs in out.items()
        if len(rs) >= min_rows
    }


SYMBOLS = ["RELIANCE", "TCS", "HDFCBANK", "SBIN", "ITC", "MARUTI", "ADANIENT", "AXISBANK"]


@pytest.fixture(scope="module")
def corpus() -> dict[str, pd.DataFrame]:
    import asyncio

    frames = asyncio.run(_load(SYMBOLS, min_rows=450))
    if not frames:
        pytest.skip("ohlcv_1d empty — run scripts/backfill_eod.py")
    return frames


def _cols(df: pd.DataFrame) -> tuple[list, list, list, list, list]:
    return (
        list(df.open), list(df.high), list(df.low), list(df.close),
        [float(v) for v in df.volume],
    )


class TestConfluenceParity:
    def test_decisions_and_scores_match_on_sampled_windows(self, corpus) -> None:
        evals = fired = 0
        for sym, df in sorted(corpus.items()):
            for end in range(320, len(df), 37):
                w = df.iloc[end - 300 : end]
                factors = run_all_factors(w, timeframe="1d")
                py = score_from_factors(factors, w, 70)
                o, h, lo, c, v = _cols(w)
                rs = tradecore.score_signal(o, h, lo, c, v, "1d", 70)
                evals += 1
                assert (py is None) == (rs is None), f"{sym}@{end}: decision"
                if py is None:
                    continue
                fired += 1
                assert rs["direction"] == py.direction, f"{sym}@{end}"
                assert rs["confidence"] == py.confidence_pct, f"{sym}@{end}"
                assert abs(rs["normalized"] - py.normalized_score) <= 1e-12
                assert rs["multibagger"] == py.is_multibagger
                rust_f = rs["factors"]
                py_f = {f.name: (f.weight, f.score) for f in py.factors}
                assert set(rust_f) == set(py_f), f"{sym}@{end}: factor names"
                for name, (w_, s_) in py_f.items():
                    assert rust_f[name][0] == w_ and rust_f[name][1] == s_, (
                        f"{sym}@{end} {name}: rust {rust_f[name]} vs py ({w_}, {s_})"
                    )
        assert evals >= 90, f"only {evals} evals — corpus too thin"


class TestBacktestParity:
    def test_trade_lists_exact(self, corpus) -> None:
        cfg = BacktestConfig(
            capital=Decimal("500000"), risk_pct=Decimal("2"), min_confidence=70
        )
        eng = BacktestEngine(cfg)
        total = 0
        for sym, df in sorted(corpus.items())[:4]:
            dfi = df.copy()
            dfi.index = pd.date_range("2020-01-01", periods=len(dfi), freq="D")
            date_to_idx = {d: i for i, d in enumerate(dfi.index)}
            py_trades = eng.run_single_stock(sym, dfi)
            o, h, lo, c, v = _cols(df)
            rs_trades = tradecore.run_backtest_single(
                o, h, lo, c, v, "1d", "500000", "2", 70
            )
            assert len(rs_trades) == len(py_trades), f"{sym}: count"
            for rt, pt in zip(rs_trades, py_trades, strict=True):
                assert rt["fill_idx"] == date_to_idx[pt.entry_date], f"{sym}: fill idx"
                assert rt["exit_idx"] == date_to_idx[pt.exit_date], f"{sym}: exit idx"
                assert rt["direction"] == pt.direction
                assert rt["qty"] == pt.qty, f"{sym}@{rt['fill_idx']}: qty"
                assert abs(rt["entry"] - pt.entry_price) <= 1e-9
                assert abs(rt["sl"] - pt.stop_loss) <= 1e-9
                assert abs(rt["exit_price"] - pt.exit_price) <= 1e-9
                assert abs(rt["pnl_pct"] - pt.pnl_pct) <= 1e-12
                assert (rt["hit_sl"], rt["hit_target"]) == (pt.hit_sl, pt.hit_target)
                total += 1
        assert total >= 50, f"only {total} trades compared"
