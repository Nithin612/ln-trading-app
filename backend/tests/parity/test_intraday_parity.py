"""Intraday parity (Phase 2 slice 8c) — the committed fixture is the oracle.

Unlike the corpus-bound suites, this replays the COMMITTED intraday fixture
(real backfilled 5m/15m bars + session_last flags, python-oracle trades)
through BOTH engines — it runs on any machine, no dev DB required. The
python leg proves the frozen engine still reproduces its own oracle; the
tradecore leg proves cross-language exactness on the intraday axis. The
same file is replayed by cargo (python_backtest_intraday_parity.rs).
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest
from app.backtest.engine import BacktestConfig, BacktestEngine

pytestmark = pytest.mark.parity

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "engine" / "crates" / "engine-core" / "tests" / "fixtures"
    / "python_backtest_intraday_reference.json"
)


@pytest.fixture(scope="module")
def fixture() -> dict:
    if not FIXTURE.exists():
        pytest.skip("intraday fixture not generated yet (scripts/generate_engine_fixtures.py)")
    return json.loads(FIXTURE.read_text())


def _py_trades(case: dict, meta: dict) -> list[dict]:
    cfg = BacktestConfig(
        timeframe=case["timeframe"],
        universe="FIXTURE",
        capital=Decimal(meta["capital"]),
        risk_pct=Decimal(meta["risk_pct"]),
        min_confidence=70,
    )
    df = pd.DataFrame(case["bars"])[["open", "high", "low", "close", "volume"]]
    idx = pd.date_range("2000-01-03", periods=len(df), freq="min", tz="UTC")
    df = df.set_index(idx)
    pos = {ts: i for i, ts in enumerate(idx)}
    return [
        {
            "fill_idx": pos[t.entry_date],
            "exit_idx": pos[t.exit_date],
            "direction": t.direction,
            "confidence": t.confidence_pct,
            "entry": t.entry_price,
            "sl": t.stop_loss,
            "tp": t.take_profit,
            "qty": t.qty,
            "exit_price": t.exit_price,
            "pnl_pct": t.pnl_pct,
            "hit_sl": t.hit_sl,
            "hit_target": t.hit_target,
        }
        for t in BacktestEngine(cfg).run_single_stock(
            case["symbol"], df, session_last=case["session_last"]
        )
    ]


class TestIntradayOracle:
    def test_python_reproduces_its_own_oracle(self, fixture: dict) -> None:
        total = 0
        for case in fixture["cases"]:
            got = _py_trades(case, fixture["_meta"])
            assert got == case["trades"], f"{case['symbol']}/{case['timeframe']}: python drifted"
            total += len(got)
        assert total >= 80, f"only {total} oracle trades — fixture too thin"

    def test_tradecore_matches_the_oracle_exactly(self, fixture: dict) -> None:
        import tradecore

        for case in fixture["cases"]:
            tag = f"{case['symbol']}/{case['timeframe']}"
            bars = case["bars"]
            rust = tradecore.run_backtest_single(
                [b["open"] for b in bars],
                [b["high"] for b in bars],
                [b["low"] for b in bars],
                [b["close"] for b in bars],
                [b["volume"] for b in bars],
                case["timeframe"],
                fixture["_meta"]["capital"],
                fixture["_meta"]["risk_pct"],
                70,
                session_last_bar=case["session_last"],
            )
            assert len(rust) == len(case["trades"]), f"{tag}: count"
            for r, p in zip(rust, case["trades"], strict=True):
                assert r["fill_idx"] == p["fill_idx"], f"{tag}: fill"
                assert r["exit_idx"] == p["exit_idx"], f"{tag}: exit idx"
                assert r["direction"] == p["direction"], tag
                assert r["confidence"] == p["confidence"], tag
                assert r["qty"] == p["qty"], f"{tag}@{p['fill_idx']}: qty"
                assert abs(r["entry"] - p["entry"]) <= 1e-9, tag
                assert abs(r["sl"] - p["sl"]) <= 1e-9, tag
                assert abs(r["tp"] - p["tp"]) <= 1e-9, tag
                assert abs(r["exit_price"] - p["exit_price"]) <= 1e-9, tag
                assert abs(r["pnl_pct"] - p["pnl_pct"]) <= 1e-12, tag
                assert (r["hit_sl"], r["hit_target"]) == (p["hit_sl"], p["hit_target"]), tag

    def test_every_pinned_case_present_and_flagged(self, fixture: dict) -> None:
        cases = {(c["symbol"], c["timeframe"]) for c in fixture["cases"]}
        assert cases == {
            ("RELIANCE", "15m"), ("TCS", "15m"), ("HDFCBANK", "15m"),
            ("RELIANCE", "5m"), ("SBIN", "5m"),
        }
        for c in fixture["cases"]:
            assert len(c["session_last"]) == len(c["bars"]), "flags misaligned"
            assert c["session_last"][-1] is True, "final bar must be flagged"
