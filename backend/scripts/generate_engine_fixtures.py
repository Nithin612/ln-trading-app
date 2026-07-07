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


# ── backtest EXT fixture: weight-multiplier + tp_rule axes (slice 8a) ────────
# Bars are NOT duplicated: the Rust test joins on symbol against the base
# python_backtest_reference.json.

EXT_VARIANTS: list[tuple[str, dict, dict | None]] = [
    ("mult_momentum", {"momentum": 1.5, "trend": 0.5}, None),
    ("tp_rr2", {}, {"kind": "rr", "ratio": "2"}),
    ("tp_flat6", {}, {"kind": "flat_pct", "target_pct": "6"}),
]


def regen_backtest_ext(doc: dict) -> tuple[dict, list[str]]:
    base = json.loads((FIXTURE_DIR / "python_backtest_reference.json").read_text())
    meta = base["_meta"]
    diffs: list[str] = []
    old_cases = {(c["symbol"], c["variant"]): c["trades"] for c in doc.get("cases", [])}
    cases = []
    for variant, mults, tp_rule in EXT_VARIANTS:
        cfg = BacktestConfig(
            timeframe="1d",
            universe="FIXTURE",
            capital=Decimal(meta["capital"]),
            risk_pct=Decimal(meta["risk_pct"]),
            min_confidence=70,
            weight_multipliers=mults,
            tp_rule=tp_rule,
        )
        engine = BacktestEngine(cfg)
        for case in base["cases"]:
            bars = case["bars"]
            idx = pd.date_range("2000-01-03", periods=len(bars), freq="D", tz="UTC")
            df = _df(bars).set_index(idx)
            base_ts = idx[0]
            trades = [
                {
                    "fill_idx": int((t.entry_date - base_ts).days),
                    "exit_idx": int((t.exit_date - base_ts).days),
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
                for t in engine.run_single_stock(case["symbol"], df)
            ]
            key = (case["symbol"], variant)
            if old_cases.get(key) != trades:
                diffs.append(
                    f"{case['symbol']}/{variant}: "
                    f"{len(old_cases.get(key, []))} -> {len(trades)} trades"
                )
            cases.append(
                {
                    "symbol": case["symbol"],
                    "variant": variant,
                    "weight_multipliers": mults,
                    "tp_rule": tp_rule,
                    "trades": trades,
                }
            )
    return (
        {
            "_meta": {
                "canon": "slice 8a ext axes over the base backtest fixture bars",
                "capital": meta["capital"],
                "risk_pct": meta["risk_pct"],
            },
            "cases": cases,
        },
        diffs,
    )


# ── backtest INTRADAY fixture: 5m/15m + session_last_bar axis (slice 8c) ─────
# Bars are cut ONCE from the backfilled dev DB at the pinned windows below
# (QA manifest 2026-07-07: all pinned symbols admitted, full 739-session
# depth) and then live in the fixture verbatim like every other fixture —
# regeneration only recomputes expectations. Flags are data-driven
# (session_last_flags on IST session dates), stored alongside the bars.

INTRADAY_PINS: list[tuple[str, str, str, str]] = [
    # (symbol, timeframe, since, until) — inclusive IST dates
    ("RELIANCE", "15m", "2026-05-15", "2026-06-30"),
    ("TCS", "15m", "2026-05-15", "2026-06-30"),
    ("HDFCBANK", "15m", "2026-05-15", "2026-06-30"),
    ("RELIANCE", "5m", "2026-06-09", "2026-06-30"),
    ("SBIN", "5m", "2026-06-09", "2026-06-30"),
]


def _bootstrap_intraday_cases() -> list[dict]:
    """First cut only: pull pinned windows from the backfilled dev DB."""
    import asyncio
    from datetime import date, datetime, time, timedelta
    from zoneinfo import ZoneInfo

    from app.backtest.walkforward import session_last_flags
    from app.db.session import AsyncSessionFactory
    from app.db.session import engine as app_engine
    from sqlalchemy import text as sa_text

    ist = ZoneInfo("Asia/Kolkata")
    table = {"5m": "ohlcv_5m", "15m": "ohlcv_15m"}

    async def _load() -> list[dict]:
        cases: list[dict] = []
        async with AsyncSessionFactory() as db:
            for symbol, tf, since, until in INTRADAY_PINS:
                t0 = datetime.combine(date.fromisoformat(since), time.min, tzinfo=ist)
                t1 = datetime.combine(
                    date.fromisoformat(until) + timedelta(days=1), time.min, tzinfo=ist
                )
                rows = (
                    await db.execute(
                        sa_text(
                            f"SELECT o.time, o.open, o.high, o.low, o.close, o.volume"  # noqa: S608
                            f" FROM {table[tf]} o JOIN stocks s ON s.id = o.stock_id"
                            " WHERE s.symbol = :sym AND o.time >= :t0 AND o.time < :t1"
                            " AND o.is_complete IS TRUE ORDER BY o.time"
                        ),
                        {"sym": symbol, "t0": t0, "t1": t1},
                    )
                ).fetchall()
                if len(rows) < 200:
                    raise SystemExit(
                        f"intraday bootstrap: {symbol}/{tf} has only {len(rows)} bars "
                        f"in [{since}, {until}] — run scripts/backfill_intraday.py first"
                    )
                cases.append(
                    {
                        "symbol": symbol,
                        "timeframe": tf,
                        "since": since,
                        "until": until,
                        "bars": [
                            {
                                "open": float(r.open),
                                "high": float(r.high),
                                "low": float(r.low),
                                "close": float(r.close),
                                "volume": float(r.volume),
                            }
                            for r in rows
                        ],
                        "session_last": session_last_flags(
                            [r.time.astimezone(ist).date() for r in rows]
                        ),
                        "trades": [],
                    }
                )
        await app_engine.dispose()
        return cases

    return asyncio.run(_load())


def regen_backtest_intraday(doc: dict) -> tuple[dict, list[str]]:
    if not doc.get("cases"):
        doc = {
            "_meta": {"capital": "500000", "risk_pct": "2"},
            "cases": _bootstrap_intraday_cases(),
        }
    diffs: list[str] = []
    for case in doc["cases"]:
        cfg = BacktestConfig(
            timeframe=case["timeframe"],
            universe="FIXTURE",
            capital=Decimal(doc["_meta"]["capital"]),
            risk_pct=Decimal(doc["_meta"]["risk_pct"]),
            min_confidence=70,
        )
        bars = case["bars"]
        idx = pd.date_range("2000-01-03", periods=len(bars), freq="min", tz="UTC")
        df = _df(bars).set_index(idx)
        pos = {ts: i for i, ts in enumerate(idx)}
        trades = [
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
        if case["trades"] != trades:
            diffs.append(
                f"{case['symbol']}/{case['timeframe']}: "
                f"{len(case['trades'])} -> {len(trades)} trades"
            )
        case["trades"] = trades
    doc["_meta"]["canon"] = (
        "slice 8c intraday axis: 5m/15m bars from the backfilled corpus "
        "(QA manifest 2026-07-07) + session_last_bar flags, frozen python oracle"
    )
    total = sum(len(c["trades"]) for c in doc["cases"])
    if total == 0:
        diffs.append("WARNING: intraday fixture minted ZERO trades across all cases")
    return doc, diffs


def main() -> int:
    check_only = "--check" in sys.argv
    jobs = [
        ("python_analysis_reference.json", regen_analysis),
        ("python_confluence_reference.json", regen_confluence),
        ("python_backtest_reference.json", regen_backtest),
        ("python_backtest_ext_reference.json", regen_backtest_ext),
        ("python_backtest_intraday_reference.json", regen_backtest_intraday),
    ]
    dirty = False
    for name, regen in jobs:
        path = FIXTURE_DIR / name
        doc = json.loads(path.read_text()) if path.exists() else {"_meta": {}, "cases": []}
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
