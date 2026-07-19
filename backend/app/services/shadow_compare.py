"""Shadow comparison — Rust vs frozen-Python decision double-check
(Phase 3, slice 3.7).

UPGRADE_PLAN §Phase 3: "One shadow week: Rust decisions vs frozen-Python
double-check on closes; zero diffs required." Cross-language parity is
already EXACT on the committed golden fixtures (tests/parity, 96 windows
+ 2y×49 backtest); this harness extends that guarantee to LIVE data —
catching any live-only price pattern the fixtures don't cover — by
re-scoring each 1d close under BOTH engine implementations and asserting
zero decision diffs.

SCOPE — the BASE (flow-free) 1d decision, NOT the committed nightly
decision. tradecore.score_signal raises on FII/DII flows and weight
multipliers (signal_service dispatch), so the only apples-to-apples
Rust-vs-Python domain is exactly the fixture-pinned one: 1d, zero flows,
no multipliers. The committed nightly signal additionally folds §2.7
flows (which shift the market-wide FII/DII factor for every stock) — so
"zero diffs" here proves rust-base == python-base on live windows, NOT
that Rust could reproduce the flow-inclusive committed signal. The
day's excluded flows are stamped into the report so a reader never reads
more into a clean run than it earns. Corollary: the frozen Python engine
is NOT deletable (per trading-domain.md) until flows are plumbed through
tradecore — the shadow week clears the base-decision half of that gate,
not the flow half. Granularity is the DECISION (emit / direction /
confidence integer); per-factor score exactness stays fixture-covered
(rules/rust.md tolerances) since the committed signal stores only the
integer confidence + direction.

Design: an EOD SWEEP, not a live-worker hook. The Rust engine is only
parity-pinned for the base 1d confluence decision (zero flows, no
multipliers — the exact fixture domain; `score_signal` falls back to the
Python reference for every other case), so the meaningful shadow check
is over 1d committed closes, which land at EOD. Running it as an
after-close sweep over the active universe is the same order of work as
nightly signal generation (never on the latency-critical tick path) and
needs no new architecture. The "shadow week" is this sweep run daily for
a week; `scripts/shadow_week.py` is the runner and exits nonzero on ANY
diff (the zero-diffs gate).

Both sides go through the SAME `score_signal` entrypoint with an explicit
`impl=` argument — never a third reimplementation of the mapping (the
same discipline the provisional layer follows), and never a global-flag
mutation (a peer thread like the provisional refresher reads
settings.engine_impl concurrently — a pure parameter is thread-safe).
Read-only: this never writes signals, outcomes, or engine state.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from typing import Any

import pandas as pd
from sqlalchemy import text

log = logging.getLogger(__name__)

# Rust is fixture-pinned only for the base 1d decision. Other timeframes
# fall back to the Python reference inside score_signal, so a comparison
# there is trivially equal and proves nothing — the sweep skips them.
_PINNED_TIMEFRAME = "1d"
_WINDOW_CAP = 300  # the decision-window canon: last 300 completed candles

_TIMEFRAME_TABLE = {
    "1d": "ohlcv_1d",
    "1h": "ohlcv_1h",
    "15m": "ohlcv_15m",
    "5m": "ohlcv_5m",
    "1m": "ohlcv_1m",
}


@dataclass
class ShadowDiff:
    """A single (stock, close) where the two engines disagree."""

    stock_id: int
    symbol: str
    timeframe: str
    as_of: str  # ISO date of the close being scored
    py_decision: bool  # did the reference engine emit a signal?
    rust_decision: bool
    py_direction: str | None
    rust_direction: str | None
    py_confidence: int | None
    rust_confidence: int | None

    def kind(self) -> str:
        if self.py_decision != self.rust_decision:
            return "decision"
        if self.py_direction != self.rust_direction:
            return "direction"
        return "confidence"

    def to_dict(self) -> dict[str, Any]:
        return {
            "stock_id": self.stock_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "as_of": self.as_of,
            "kind": self.kind(),
            "py": {"decision": self.py_decision, "direction": self.py_direction,
                   "confidence": self.py_confidence},
            "rust": {"decision": self.rust_decision, "direction": self.rust_direction,
                     "confidence": self.rust_confidence},
        }


@dataclass
class ShadowError:
    """A stock whose comparison raised — recorded, never silently lost."""

    stock_id: int
    symbol: str
    detail: str


@dataclass
class ShadowReport:
    as_of: str
    timeframe: str
    compared: int = 0
    matched: int = 0
    # of `compared`, how many the reference engine actually EMITTED a
    # signal for — so "matched" is decomposable (no-signal agreement vs
    # real direction/confidence agreement). Both-emitted is the strongest
    # parity evidence a clean day carries.
    signals_emitted: int = 0
    both_emitted: int = 0
    skipped_no_data: int = 0
    diffs: list[ShadowDiff] = field(default_factory=list)
    errors: list[ShadowError] = field(default_factory=list)
    # The §2.7 flows the base comparison EXCLUDES (see module docstring):
    # nonzero here means the committed nightly decision may differ.
    flows_excluded: dict[str, str] = field(default_factory=dict)

    @property
    def clean(self) -> bool:
        return not self.diffs and not self.errors

    def summary(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of,
            "timeframe": self.timeframe,
            "compared": self.compared,
            "matched": self.matched,
            "signals_emitted": self.signals_emitted,
            "both_emitted": self.both_emitted,
            "diffs": len(self.diffs),
            "errors": len(self.errors),
            "skipped_no_data": self.skipped_no_data,
            "flows_excluded": self.flows_excluded,
            "clean": self.clean,
        }


@dataclass
class PairResult:
    """Both engines' verdicts on one window: emit flags (for the report's
    decomposable counts) and the diff (None iff they agree)."""

    py_emitted: bool
    rust_emitted: bool
    diff: ShadowDiff | None


def compare_pair(
    candles: pd.DataFrame,
    *,
    stock_id: int,
    symbol: str,
    timeframe: str,
    as_of: str,
    min_confidence: int = 70,
) -> PairResult:
    """Score the SAME window under both engines (base decision — zero
    flows, no multipliers, the parity domain) and return their verdicts +
    a ShadowDiff iff they disagree on decision, direction, or confidence
    integer."""
    from app.services.signal_service import score_signal

    py = score_signal(
        candles, timeframe=timeframe, min_confidence=min_confidence, impl="python"
    )
    rust = score_signal(
        candles, timeframe=timeframe, min_confidence=min_confidence, impl="rust"
    )

    py_dir = py.direction if py is not None else None
    rust_dir = rust.direction if rust is not None else None
    py_conf = py.confidence_pct if py is not None else None
    rust_conf = rust.confidence_pct if rust is not None else None

    agree = (py is None) == (rust is None) and py_dir == rust_dir and py_conf == rust_conf
    diff = None if agree else ShadowDiff(
        stock_id=stock_id,
        symbol=symbol,
        timeframe=timeframe,
        as_of=as_of,
        py_decision=py is not None,
        rust_decision=rust is not None,
        py_direction=py_dir,
        rust_direction=rust_dir,
        py_confidence=py_conf,
        rust_confidence=rust_conf,
    )
    return PairResult(py_emitted=py is not None, rust_emitted=rust is not None, diff=diff)


async def _load_window(
    db: Any, stock_id: int, timeframe: str, as_of_end: datetime
) -> pd.DataFrame:
    """Last ≤300 completed candles at or before `as_of_end` — the exact
    decision window the committed run scored (mirrors profiles.pipeline
    `_load_window` with an as-of cutoff so historical days re-compare
    faithfully). Table name from a fixed whitelist."""
    table = _TIMEFRAME_TABLE.get(timeframe)
    if table is None:
        raise ValueError(f"unknown timeframe {timeframe!r}")
    rows = (
        await db.execute(
            text(
                f"SELECT time, open, high, low, close, volume FROM {table}"  # noqa: S608
                " WHERE stock_id = :sid AND is_complete IS TRUE AND time <= :end"
                " ORDER BY time DESC LIMIT :lim"
            ),
            {"sid": stock_id, "end": as_of_end, "lim": _WINDOW_CAP},
        )
    ).fetchall()
    if not rows:
        return pd.DataFrame()
    rows = list(reversed(rows))
    return pd.DataFrame(
        {
            "open": [float(r.open) for r in rows],
            "high": [float(r.high) for r in rows],
            "low": [float(r.low) for r in rows],
            "close": [float(r.close) for r in rows],
            "volume": [int(r.volume) for r in rows],
        },
        index=pd.DatetimeIndex([r.time for r in rows]),
    )


async def sweep_day(
    db: Any,
    as_of: date,
    *,
    timeframe: str = _PINNED_TIMEFRAME,
    min_confidence: int = 70,
) -> ShadowReport:
    """Compare both engines on every active stock's committed close for
    `as_of`. Only the Rust-pinned timeframe (1d) is a real check; others
    are refused loudly (the Python fallback would make the comparison
    trivially equal — a green that proves nothing).

    Universe = raw `is_active` — exactly what nightly generation scores
    (signal_service), CA-flagged stocks included: they produce identical
    garbage under both engines, so they broaden parity coverage without
    harm and keep shadow coverage == committed coverage."""
    from sqlalchemy import select

    from app.models.stock import Stock
    from app.services.fii_dii_service import get_market_flow_5d

    if timeframe != _PINNED_TIMEFRAME:
        raise ValueError(
            f"shadow compare is meaningful only for {_PINNED_TIMEFRAME} "
            f"(Rust is unpinned for {timeframe}; score_signal would fall back "
            "to the Python reference and the comparison would be a no-op)"
        )
    report = ShadowReport(as_of=as_of.isoformat(), timeframe=timeframe)
    # Stamp the flows the base comparison excludes (module docstring):
    # nonzero → the committed nightly decision may differ from this base.
    fii, dii = await get_market_flow_5d(db, as_of)
    report.flows_excluded = {"fii_net_5d": str(fii), "dii_net_5d": str(dii)}

    # End of the as-of trading day in UTC — bars are stored at UTC
    # midnight of the session day (ohlcv_1d canon), so an inclusive
    # end-of-day cutoff captures exactly through the as-of close.
    as_of_end = datetime.combine(as_of, time(23, 59, 59), tzinfo=UTC)

    rows = (
        await db.execute(
            select(Stock.id, Stock.symbol).where(Stock.is_active.is_(True))
        )
    ).fetchall()
    symbols = {r[0]: r[1] for r in rows}
    for sid in sorted(symbols):
        # One pathological stock — a failed load OR a failed score — must
        # not discard the whole day's report. The load is INSIDE the try
        # (a raising SELECT aborts the tx; roll back so the next stock's
        # query doesn't cascade InFailedSQLTransaction — bug-hunter LOW).
        try:
            window = await _load_window(db, sid, timeframe, as_of_end)
            if window.empty or len(window) < 50:
                report.skipped_no_data += 1
                continue
            result = compare_pair(
                window,
                stock_id=sid,
                symbol=symbols[sid],
                timeframe=timeframe,
                as_of=report.as_of,
                min_confidence=min_confidence,
            )
        except Exception as exc:
            await db.rollback()
            log.exception("shadow: stock=%s failed", symbols[sid])
            report.errors.append(ShadowError(sid, symbols[sid], repr(exc)))
            continue
        report.compared += 1
        if result.py_emitted:
            report.signals_emitted += 1
        if result.py_emitted and result.rust_emitted:
            report.both_emitted += 1
        if result.diff is None:
            report.matched += 1
        else:
            diff = result.diff
            report.diffs.append(diff)
            log.warning(
                "shadow: DIFF stock=%s %s %s py=%s rust=%s",
                diff.symbol,
                diff.kind(),
                report.as_of,
                (diff.py_decision, diff.py_direction, diff.py_confidence),
                (diff.rust_decision, diff.rust_direction, diff.rust_confidence),
            )
    return report
