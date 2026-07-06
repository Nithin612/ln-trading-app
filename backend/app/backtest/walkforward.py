"""Walk-forward runner (Phase 2 slice 8b) — Rust engine, quarterly folds.

One CONTINUOUS tradecore run per (profile, universe) over [since, eval_end],
then python owns everything calendar- and profile-shaped:

  - trade indices → IST dates (the engine never sees a calendar);
  - setup gates applied as an exact post-filter — setups only DROP trades,
    identical evaluators to the live pipeline (app/profiles/setups.py);
  - fills before eval_start dropped (warm-up region, window-canon context);
  - surviving trades binned into CALENDAR-QUARTER folds by fill date
    (lossless: trades are independent, holiday-table edits can't shift
    fold bounds);
  - metrics via app.backtest.metrics.aggregate_trades (fixed ordering canon).

Window-canon invariance: a symbol only qualifies if it has ≥300 completed
bars BEFORE eval_start, so every in-eval decision window is the full
300-candle canon — results can't depend on `since`. Symbols failing the
check are EXCLUDED and recorded, never patched.

TP-rule mapping (documented approximations, per the approved slice plan):
rr / flat_pct map directly; flat_pct_trailing → flat_pct (basic-target
economics, no partial booking); ema_trail → flat_pct(min_target_pct).
Rust has no trailing execution this phase — goldens carry `tp_approximated`
so nobody mistakes those folds for trailing economics.

Timeframe guard: 1d ONLY until slice 8c lands intraday parity fixtures
(tradecore is parity-pinned on 1d; see docs/PHASES.md).

Known slice-7 gap (flagged for the phase gate): the live pipeline does not
yet feed profile.weight_multipliers into score_signal — all seeded profiles
carry {} so behavior is identical today, but a multiplier-carrying profile
must not be activated until the pipeline is wired.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.backtest.engine import BacktestResult, TradeRecord
from app.backtest.metrics import aggregate_trades
from app.models.profile import StrategyProfile
from app.profiles.setups import SetupContext, evaluate_conditions
from app.services.universe_service import resolve_universe

_IST = ZoneInfo("Asia/Kolkata")

# Decision-window canon (adjudicated 2026-07-04): factors see exactly the
# last ≤300 completed candles. In-eval trades must all have the FULL canon.
WINDOW_BARS = 300

# Setups evaluable from a 1d decision window + the trade's factor snapshot.
# The others need context walk-forward can't reconstruct offline yet
# (benchmark series, session bars, 9:25 cross-section) — reject, don't
# silently produce a zero-trade golden.
SUPPORTED_SETUPS_1D = {
    "dc1",
    "dc2",
    "factor_score",
    "pdh_breakout",
    "pdl_breakdown",
    "opening_gap",
}

# Metrics compared by the §8 golden harness (BacktestResult scalar fields;
# equity_curve/trades excluded — the digest pins the trade list).
METRIC_FIELDS: tuple[str, ...] = (
    "total_trades",
    "winning_trades",
    "losing_trades",
    "total_pnl_pct",
    "avg_pnl_pct",
    "win_rate_pct",
    "avg_rr",
    "max_drawdown_pct",
    "sharpe",
    "sortino",
    "avg_holding_days",
)


class WalkForwardError(RuntimeError):
    """Profile/spec combination the walk-forward runner refuses to run."""


@dataclass(frozen=True)
class WalkForwardSpec:
    """Pinned run bounds. Goldens embed these; the harness replays them."""

    since: date
    eval_start: date
    eval_end: date
    capital: Decimal = Decimal("500000")
    risk_pct: Decimal = Decimal("2")  # WHOLE percent (2.0 = 2%)


@dataclass(frozen=True)
class SymbolExclusion:
    symbol: str
    reason: str
    bars_before_eval: int


@dataclass
class WalkForwardReport:
    profile_key: str
    config_hash: str
    tp_rule: tuple[str, str]
    tp_approximated: bool
    symbols: list[str]  # symbols that actually ran (post-exclusion)
    row_counts: dict[str, int]
    exclusions: list[SymbolExclusion]
    folds: list[tuple[str, BacktestResult]]  # ("2024Q4", metrics) — every quarter present
    aggregate: BacktestResult
    trades: list[TradeRecord]  # post-filter, in-eval, ordering canon
    pre_filter_trade_count: int  # in-eval trades BEFORE setup gating (gate selectivity)
    trades_digest: str


# ── Pure helpers (unit-tested without DB or tradecore) ───────────────────────


def validate_profile(timeframe: str, setup_conditions: list[dict[str, Any]]) -> None:
    """Reject profile shapes the runner can't faithfully walk-forward yet."""
    if timeframe != "1d":
        raise WalkForwardError(
            f"walk-forward supports timeframe '1d' only until slice 8c "
            f"(intraday parity fixtures land with the Kite backfill); got {timeframe!r}"
        )
    unsupported = {str(c.get("type")) for c in setup_conditions} - SUPPORTED_SETUPS_1D
    if unsupported:
        raise WalkForwardError(
            f"setup types {sorted(unsupported)} need context the offline runner "
            f"cannot reconstruct (supported: {sorted(SUPPORTED_SETUPS_1D)})"
        )


def map_tp_rule(risk_template: dict[str, Any]) -> tuple[tuple[str, str], bool]:
    """Profile risk_template → tradecore (kind, value) + approximated flag.

    flat_pct_trailing and ema_trail have no Rust execution this phase —
    they map to flat targets (approved approximations, pinned in goldens).
    """
    kind = str(risk_template.get("kind"))
    if kind == "rr":
        return ("rr", str(risk_template["ratio"])), False
    if kind == "flat_pct":
        return ("flat_pct", str(risk_template["target_pct"])), False
    if kind == "flat_pct_trailing":
        return ("flat_pct", str(risk_template["target_pct"])), True
    if kind == "ema_trail":
        return ("flat_pct", str(risk_template["min_target_pct"])), True
    raise WalkForwardError(f"unknown risk_template kind {kind!r}")


def quarter_key(d: date) -> str:
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"


def quarter_folds(eval_start: date, eval_end: date) -> list[str]:
    """Every calendar quarter touched by [eval_start, eval_end], in order."""
    if eval_end < eval_start:
        raise WalkForwardError(f"eval_end {eval_end} before eval_start {eval_start}")
    folds: list[str] = []
    year, q = eval_start.year, (eval_start.month - 1) // 3 + 1
    while (year, q) <= (eval_end.year, (eval_end.month - 1) // 3 + 1):
        folds.append(f"{year}Q{q}")
        year, q = (year, q + 1) if q < 4 else (year + 1, 1)
    return folds


def trade_record_from(symbol: str, t: dict[str, Any], dates: list[date]) -> TradeRecord:
    """Rust trade dict (integer indices) → python TradeRecord (IST dates).

    classification is not exported by the FFI trade dict and no metric
    consumes it — left empty rather than recomputed (recomputing would be a
    second implementation that could drift).
    """
    return TradeRecord(
        stock=symbol,
        direction=str(t["direction"]),
        classification="",
        confidence_pct=int(t["confidence"]),
        entry_date=pd.Timestamp(dates[int(t["fill_idx"])]),
        entry_price=float(t["entry"]),
        stop_loss=float(t["sl"]),
        take_profit=float(t["tp"]),
        qty=int(t["qty"]),
        exit_date=pd.Timestamp(dates[int(t["exit_idx"])]),
        exit_price=float(t["exit_price"]),
        pnl_pct=float(t["pnl_pct"]),
        hit_target=bool(t["hit_target"]),
        hit_sl=bool(t["hit_sl"]),
    )


def apply_setup_filter(
    symbol: str,
    df: pd.DataFrame,
    raw_trades: list[dict[str, Any]],
    conditions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Exact live-pipeline setup gating, replayed per trade.

    The decision candle is fill_idx − 1; its window is the engine's canon
    (last ≤300 candles ENDING at the decision candle) — df.iloc[fill-300:fill].
    ctx.factors comes from the trade's factor snapshot (Phase-1 parity:
    scores are EXACT vs python), so gates behave identically to live.
    """
    if not conditions:
        return list(raw_trades)
    kept: list[dict[str, Any]] = []
    for t in raw_trades:
        fill_idx = int(t["fill_idx"])
        window = df.iloc[max(0, fill_idx - WINDOW_BARS) : fill_idx]
        ctx = SetupContext(
            direction=str(t["direction"]),
            factors={str(k): (float(w), float(s)) for k, (w, s) in dict(t["factors"]).items()},
            symbol=symbol,
        )
        passed, _evidence = evaluate_conditions(conditions, window, ctx)
        if passed:
            kept.append(t)
    return kept


def bin_folds(
    trades: list[TradeRecord], eval_start: date, eval_end: date
) -> list[tuple[str, BacktestResult]]:
    """Quarterly fold metrics — every quarter in range present, even empty."""
    by_fold: dict[str, list[TradeRecord]] = {f: [] for f in quarter_folds(eval_start, eval_end)}
    for t in trades:
        by_fold[quarter_key(t.entry_date.date())].append(t)
    return [(fold, aggregate_trades(members)) for fold, members in by_fold.items()]


def trades_digest(trades: list[TradeRecord]) -> str:
    """sha256 over the canonical trade serialization, ordering canon
    (entry_date, stock). Money at the 1e-4 canon; pnl/exit at full float
    repr (rust-deterministic — goldens are generated AND replayed on
    tradecore, python never recomputes these numbers)."""
    lines = []
    for t in sorted(trades, key=lambda t: (t.entry_date, t.stock)):
        exit_d = t.exit_date.date().isoformat() if t.exit_date is not None else "-"
        lines.append(
            f"{t.stock}|{t.entry_date.date().isoformat()}|{exit_d}|{t.direction}"
            f"|{t.qty}|{t.entry_price:.4f}|{t.stop_loss:.4f}|{t.take_profit:.4f}"
            f"|{t.exit_price!r}|{t.pnl_pct!r}|{t.confidence_pct}"
        )
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def metrics_dict(r: BacktestResult) -> dict[str, float | int]:
    return {name: getattr(r, name) for name in METRIC_FIELDS}


@dataclass(frozen=True)
class MetricDelta:
    name: str
    golden: float
    rerun: float

    @property
    def within_tolerance(self) -> bool:
        # §8 gate: max(5% relative, 0.05 absolute).
        return abs(self.rerun - self.golden) <= max(0.05, 0.05 * abs(self.golden))


def metric_deltas(
    golden: dict[str, Any], rerun: dict[str, Any], prefix: str = ""
) -> list[MetricDelta]:
    return [
        MetricDelta(f"{prefix}{name}", float(golden[name]), float(rerun[name]))
        for name in METRIC_FIELDS
    ]


def format_delta_table(deltas: list[MetricDelta], only_moves: bool = True) -> str:
    """The Δ-table printed on harness failure / regen dry-run."""
    rows = [d for d in deltas if d.golden != d.rerun] if only_moves else list(deltas)
    if not rows:
        return "  (no metric moves)"
    width = max(len(d.name) for d in rows)
    out = [f"  {'metric':<{width}}  {'golden':>12}  {'rerun':>12}  {'Δ':>10}"]
    for d in rows:
        delta = d.rerun - d.golden
        rel = f"{delta / d.golden * 100:+.1f}%" if d.golden else f"{delta:+.3f}"
        tag = "" if d.within_tolerance else "  [§8 APPROVAL REQUIRED]"
        out.append(f"  {d.name:<{width}}  {d.golden:>12.3f}  {d.rerun:>12.3f}  {rel:>10}{tag}")
    return "\n".join(out)


# ── Golden schema (ONE implementation — generator and harness both import
#    these, so the two sides can't drift on field names or fold structure) ────


def build_golden(
    profile: StrategyProfile, spec: WalkForwardSpec, report: WalkForwardReport
) -> dict[str, Any]:
    """The walkforward-golden-v1 document persisted per active profile."""
    import tradecore  # deferred: parity-gated wheel

    return {
        "schema": "walkforward-golden-v1",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "profile": {
            "key": profile.key,
            "version": profile.version,
            "name": profile.name,
            "style": profile.style,
            "timeframe": profile.timeframe,
            "universe_spec": profile.universe_spec,
            "setup_conditions": profile.setup_conditions,
            "weight_multipliers": profile.weight_multipliers,
            "min_confidence": profile.min_confidence,
            "risk_template": profile.risk_template,
            "validity_spec": profile.validity_spec,
        },
        "config_hash": profile.config_hash,
        "tradecore_version": tradecore.version(),
        "run": {
            "since": spec.since.isoformat(),
            "eval_start": spec.eval_start.isoformat(),
            "eval_end": spec.eval_end.isoformat(),
            "capital": str(spec.capital),
            "risk_pct": str(spec.risk_pct),
            "tp_rule": list(report.tp_rule),
            "tp_approximated": report.tp_approximated,
        },
        "symbols": report.symbols,
        "row_counts": report.row_counts,
        "exclusions": [
            {"symbol": e.symbol, "reason": e.reason, "bars_before_eval": e.bars_before_eval}
            for e in report.exclusions
        ],
        "pre_filter_trade_count": report.pre_filter_trade_count,
        "folds": [
            {"fold": fold, "metrics": metrics_dict(result)} for fold, result in report.folds
        ],
        "aggregate": metrics_dict(report.aggregate),
        "trades_digest": report.trades_digest,
    }


def spec_from_golden(golden: dict[str, Any]) -> WalkForwardSpec:
    """Rehydrate the pinned run bounds a golden was generated with."""
    run = golden["run"]
    return WalkForwardSpec(
        since=date.fromisoformat(run["since"]),
        eval_start=date.fromisoformat(run["eval_start"]),
        eval_end=date.fromisoformat(run["eval_end"]),
        capital=Decimal(run["capital"]),
        risk_pct=Decimal(run["risk_pct"]),
    )


def _stripped(golden: dict[str, Any]) -> dict[str, Any]:
    """Golden minus the informational timestamp — content identity."""
    return {k: v for k, v in golden.items() if k != "generated_at"}


def compare_against_existing(old: dict[str, Any], new: dict[str, Any]) -> tuple[bool, bool, str]:
    """§8 write gate: (content_changed, needs_approval, delta_table_text).

    needs_approval is True when any fold/aggregate metric moved beyond
    max(5% rel, 0.05 abs) — the generator refuses --write without
    --i-have-approval in that case.
    """
    if _stripped(old) == _stripped(new):
        return False, False, "  (unchanged)"
    deltas = metric_deltas(old["aggregate"], new["aggregate"], "aggregate.")
    old_folds = {f["fold"]: f["metrics"] for f in old.get("folds", [])}
    new_folds = {f["fold"]: f["metrics"] for f in new.get("folds", [])}
    for fold in sorted(old_folds.keys() | new_folds.keys()):
        if fold in old_folds and fold in new_folds:
            deltas.extend(metric_deltas(old_folds[fold], new_folds[fold], f"{fold}."))
    lines = [format_delta_table(deltas)]
    if old.get("trades_digest") != new.get("trades_digest"):
        lines.append(
            f"  trades_digest: {old.get('trades_digest', '?')[:16]}… → "
            f"{new.get('trades_digest', '?')[:16]}…"
        )
    if set(old_folds) != set(new_folds):
        lines.append(f"  fold set changed: {sorted(old_folds)} → {sorted(new_folds)}")
    if old.get("config_hash") != new.get("config_hash"):
        lines.append("  config_hash changed — the profile version moved underneath the golden")
    if old.get("symbols") != new.get("symbols"):
        lines.append(
            f"  pinned symbols changed: {len(old.get('symbols', []))} → "
            f"{len(new.get('symbols', []))}"
        )
    needs_approval = any(not d.within_tolerance for d in deltas)
    return True, needs_approval, "\n".join(lines)


# ── Data loading ─────────────────────────────────────────────────────────────


@dataclass
class _Frame:
    """One symbol's loaded candles — parallel arrays + IST session dates."""

    open: list[float] = field(default_factory=list)
    high: list[float] = field(default_factory=list)
    low: list[float] = field(default_factory=list)
    close: list[float] = field(default_factory=list)
    volume: list[float] = field(default_factory=list)
    dates: list[date] = field(default_factory=list)

    def df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "open": self.open,
                "high": self.high,
                "low": self.low,
                "close": self.close,
                "volume": self.volume,
            }
        )


_LOAD_CHUNK = 400  # symbols per query — caps asyncpg row buffering on all_active


async def _load_frames(
    db: AsyncSession, symbols: list[str], since: date, eval_end: date
) -> dict[str, _Frame]:
    """Completed 1d candles per symbol in [since, eval_end], IST-bounded.

    Table name is a literal from the 1d-only whitelist (validate_profile
    guarantees the timeframe); values are bind parameters.
    """
    t0 = datetime.combine(since, time.min, tzinfo=_IST)
    t1 = datetime.combine(eval_end + timedelta(days=1), time.min, tzinfo=_IST)
    frames: dict[str, _Frame] = {}
    for i in range(0, len(symbols), _LOAD_CHUNK):
        rows = (
            await db.execute(
                text(
                    "SELECT s.symbol, o.time, o.open, o.high, o.low, o.close, o.volume"
                    " FROM ohlcv_1d o JOIN stocks s ON s.id = o.stock_id"
                    " WHERE s.symbol = ANY(:syms) AND o.time >= :t0 AND o.time < :t1"
                    " AND o.is_complete IS TRUE"
                    " ORDER BY s.symbol, o.time"
                ),
                {"syms": symbols[i : i + _LOAD_CHUNK], "t0": t0, "t1": t1},
            )
        ).fetchall()
        for r in rows:
            f = frames.setdefault(r.symbol, _Frame())
            f.open.append(float(r.open))
            f.high.append(float(r.high))
            f.low.append(float(r.low))
            f.close.append(float(r.close))
            f.volume.append(float(r.volume))
            f.dates.append(r.time.astimezone(_IST).date())
    return frames


# ── The runner ───────────────────────────────────────────────────────────────


async def run_walkforward(
    db: AsyncSession,
    profile: StrategyProfile,
    spec: WalkForwardSpec,
    symbols: list[str] | None = None,
) -> WalkForwardReport:
    """Walk one ACTIVE profile forward over pinned bounds.

    symbols=None resolves the profile universe fresh (golden generation);
    the harness passes the golden's pinned list so reruns never depend on
    universe drift. ONE tradecore.run_universe call per profile.
    """
    validate_profile(profile.timeframe, list(profile.setup_conditions))
    if not spec.since < spec.eval_start <= spec.eval_end:
        raise WalkForwardError(
            f"bounds must satisfy since < eval_start <= eval_end "
            f"(got {spec.since} / {spec.eval_start} / {spec.eval_end})"
        )

    if symbols is None:
        _, sym_map = await resolve_universe(db, profile.universe_spec)
        symbols = sorted(sym_map.values())
    if not symbols:
        raise WalkForwardError(f"profile {profile.key}: universe resolved empty")

    frames = await _load_frames(db, symbols, spec.since, spec.eval_end)

    ran: list[str] = []
    exclusions: list[SymbolExclusion] = []
    for sym in symbols:
        f = frames.get(sym)
        if f is None:
            exclusions.append(SymbolExclusion(sym, "no candles in range", 0))
            continue
        pre = sum(1 for d in f.dates if d < spec.eval_start)
        if pre < WINDOW_BARS:
            exclusions.append(
                SymbolExclusion(sym, f"<{WINDOW_BARS} bars before eval_start", pre)
            )
            continue
        ran.append(sym)
    if not ran:
        raise WalkForwardError(
            f"profile {profile.key}: every symbol excluded — pins don't fit the data "
            f"(need ≥{WINDOW_BARS} bars before {spec.eval_start})"
        )

    tp_rule, tp_approximated = map_tp_rule(dict(profile.risk_template))
    stocks = [(s, frames[s].open, frames[s].high, frames[s].low, frames[s].close,
               frames[s].volume) for s in ran]

    import tradecore  # deferred: parity-gated wheel, same idiom as signal_service

    universe_trades: list[tuple[str, list[dict[str, Any]]]] = tradecore.run_universe(
        stocks,
        "1d",
        str(spec.capital),
        str(spec.risk_pct),
        profile.min_confidence,
        weight_multipliers=sorted(dict(profile.weight_multipliers).items()),
        tp_rule=tp_rule,
    )

    conditions = list(profile.setup_conditions)
    records: list[TradeRecord] = []
    pre_filter_count = 0
    for sym, raw in universe_trades:
        f = frames[sym]
        in_eval = [t for t in raw if f.dates[int(t["fill_idx"])] >= spec.eval_start]
        pre_filter_count += len(in_eval)
        if not in_eval:
            continue
        kept = apply_setup_filter(sym, f.df(), in_eval, conditions)
        records.extend(trade_record_from(sym, t, f.dates) for t in kept)

    records.sort(key=lambda t: (t.entry_date, t.stock))
    return WalkForwardReport(
        profile_key=profile.key,
        config_hash=profile.config_hash,
        tp_rule=tp_rule,
        tp_approximated=tp_approximated,
        symbols=ran,
        row_counts={s: len(frames[s].dates) for s in ran},
        exclusions=exclusions,
        folds=bin_folds(records, spec.eval_start, spec.eval_end),
        aggregate=aggregate_trades(records),
        trades=records,
        pre_filter_trade_count=pre_filter_count,
        trades_digest=trades_digest(records),
    )
