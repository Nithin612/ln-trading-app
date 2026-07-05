"""Regenerate the Rust oracle fixtures from the CURRENT Python engine.

The committed fixtures under `engine/crates/engine-core/tests/fixtures/`
are the cross-language parity oracle. Any sanctioned change to the frozen
Python engine (adjudication or bugfix per trading-domain.md) must
regenerate them IN THE SAME COMMIT. Phase 1 generated them ad-hoc; this
script makes the ritual repeatable:

  - `bars` in each fixture are kept verbatim (real market data, immutable);
  - every expected value is recomputed from the live Python code;
  - a per-fixture diff summary is printed so the operator can verify that
    ONLY the values the change was supposed to move actually moved.

pandas_ta_reference.json is NOT touched here — it pins pandas-ta itself,
not our engine, and only changes when the pinned pandas-ta version does.

Usage:
  uv run python scripts/generate_engine_fixtures.py           # regenerate
  uv run python scripts/generate_engine_fixtures.py --check   # verify only
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
from app.analysis.confluence import run_all_factors, score_from_factors  # noqa: E402
from app.analysis.patterns.multi import (  # noqa: E402
    detect_engulfing,
    detect_harami,
    detect_morning_evening_star,
    detect_piercing_dark_cloud,
)
from app.analysis.patterns.single import (  # noqa: E402
    detect_doji,
    detect_hammer,
    detect_hanging_man,
    detect_marubozu,
    detect_shooting_star,
    detect_spinning_top,
)
from app.analysis.structure.dow import dow_trend_factor  # noqa: E402
from app.analysis.structure.fibonacci import fibonacci_factor  # noqa: E402
from app.analysis.structure.levels import sr_zone_factor  # noqa: E402
from app.backtest.engine import BacktestConfig, BacktestEngine  # noqa: E402

FIXTURE_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "engine" / "crates" / "engine-core" / "tests" / "fixtures"
)


def _df(bars: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(bars)[["open", "high", "low", "close", "volume"]]


# ── analysis fixture: pattern + structure scores per window ─────────────────

def analysis_expected(df: pd.DataFrame) -> dict[str, float]:
    return {
        "marubozu": detect_marubozu(df).score,
        "doji": detect_doji(df).score,
        "spinning_top": detect_spinning_top(df).score,
        "engulfing": detect_engulfing(df).score,
        "harami": detect_harami(df).score,
        "piercing_dcc": detect_piercing_dark_cloud(df).score,
        "star": detect_morning_evening_star(df).score,
        "hammer_false": detect_hammer(df, at_swing_low=False).score,
        "hammer_true": detect_hammer(df, at_swing_low=True).score,
        "hanging_man_false": detect_hanging_man(df, at_swing_high=False).score,
        "hanging_man_true": detect_hanging_man(df, at_swing_high=True).score,
        "shooting_star_false": detect_shooting_star(df, at_swing_high=False).score,
        "shooting_star_true": detect_shooting_star(df, at_swing_high=True).score,
        "dow": dow_trend_factor(df, lookback=20, swing_n=3).score,
        "sr_none": sr_zone_factor(df, None, False, False, False).score,
        "sr_bull": sr_zone_factor(df, None, True, False, False).score,
        "sr_bear": sr_zone_factor(df, None, False, True, False).score,
        "sr_brk": sr_zone_factor(df, None, False, False, True).score,
        "fib": fibonacci_factor(df, swing_n=5).score,
    }


def regen_analysis(doc: dict) -> tuple[dict, list[str]]:
    diffs: list[str] = []
    for case in doc["cases"]:
        new = analysis_expected(_df(case["bars"]))
        old = case["expected"]
        for key, val in new.items():
            if old.get(key) != val:
                diffs.append(f"{case['symbol']}@{case['end']} {key}: {old.get(key)} -> {val}")
        case["expected"] = new
    doc["_meta"]["source"] = "app.analysis canon A-E 2026-07-04 + F/G 2026-07-05"
    return doc, diffs


# ── confluence fixture: factor dicts + outcome per window ───────────────────

def volume_adjusted(factors: list) -> list:
    """The scorer's item-A volume adjustment (fixture stores POST-adjust)."""
    rest = sum(f.weight * f.score for f in factors if f.name != "VOLUME")
    out = []
    for f in factors:
        if f.name == "VOLUME" and f.score > 0:
            s = 0.5 if rest > 0 else (-0.5 if rest < 0 else 0.0)
            f = type(f)(f.name, f.weight, s, f.explanation, f.tags)
        out.append(f)
    return out


def regen_confluence(doc: dict) -> tuple[dict, list[str]]:
    diffs: list[str] = []
    for case in doc["cases"]:
        df = _df(case["bars"])
        raw = run_all_factors(df, "1d")
        factors = {
            f.name: {"w": f.weight, "s": f.score} for f in volume_adjusted(raw)
        }
        res = score_from_factors(raw, df, 70)
        outcome = (
            None
            if res is None
            else {
                "direction": res.direction,
                "confidence": res.confidence_pct,
                "normalized": res.normalized_score,
                "multibagger": res.is_multibagger,
            }
        )
        tag = f"{case['symbol']}@{case['end']}"
        if case["factors"] != factors:
            changed = sorted(
                set(case["factors"]) ^ set(factors)
                | {k for k in set(case["factors"]) & set(factors)
                   if case["factors"][k] != factors[k]}
            )
            diffs.append(f"{tag} factors: {changed}")
        if case["outcome"] != outcome:
            diffs.append(f"{tag} outcome: {case['outcome']} -> {outcome}")
        case["factors"] = factors
        case["outcome"] = outcome
    doc["_meta"]["canon"] = "A-E 2026-07-04 + F/G 2026-07-05"
    return doc, diffs


# ── backtest fixture: exact trade lists per stock ───────────────────────────

def regen_backtest(doc: dict) -> tuple[dict, list[str]]:
    meta = doc["_meta"]
    cfg = BacktestConfig(
        timeframe="1d",
        universe="FIXTURE",
        capital=Decimal(meta["capital"]),
        risk_pct=Decimal(meta["risk_pct"]),
        min_confidence=70,
    )
    engine = BacktestEngine(cfg)
    diffs: list[str] = []
    for case in doc["cases"]:
        bars = case["bars"]
        idx = pd.date_range("2000-01-03", periods=len(bars), freq="D", tz="UTC")
        df = _df(bars).set_index(idx)
        base = idx[0]
        trades = []
        for t in engine.run_single_stock(case["symbol"], df):
            trades.append(
                {
                    "fill_idx": int((t.entry_date - base).days),
                    "exit_idx": int((t.exit_date - base).days),
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
            )
        if case["trades"] != trades:
            diffs.append(
                f"{case['symbol']}: {len(case['trades'])} -> {len(trades)} trades"
            )
        case["trades"] = trades
    meta["canon"] = "adjudicated A-E 2026-07-04 + F/G 2026-07-05"
    return doc, diffs


def main() -> int:
    check_only = "--check" in sys.argv
    jobs = [
        ("python_analysis_reference.json", regen_analysis),
        ("python_confluence_reference.json", regen_confluence),
        ("python_backtest_reference.json", regen_backtest),
    ]
    dirty = False
    for name, regen in jobs:
        path = FIXTURE_DIR / name
        doc = json.loads(path.read_text())
        doc, diffs = regen(doc)
        print(f"{name}: {len(diffs)} case-level diffs")
        for d in diffs[:12]:
            print(f"  {d}")
        if len(diffs) > 12:
            print(f"  … {len(diffs) - 12} more")
        if diffs:
            dirty = True
        if not check_only:
            path.write_text(json.dumps(doc))
    if check_only and dirty:
        print("CHECK FAILED: fixtures do not match the current Python engine")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
