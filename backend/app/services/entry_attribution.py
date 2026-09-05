"""Entry-quality attribution (Phase 6 slice 6.2).

The Phase-6 question, made answerable: for each terminal signal outcome, which
*cells* — confidence bucket, ADX/regime bucket, direction, setup, time-of-day —
have positive expectancy and which are systematically negative? That turns
"only 1 of 15 trades reached +1R" into "these cells are the leak."

Read-only over the existing signal_outcomes + signals (+ 6.1's MFE/MAE). No
engine change; never feeds scoring/sizing/gating/backtests.

Expectancy source: `signals.outcome_pnl_pct` is unpopulated for the whole live
cohort, so expectancy is derived — `expectancy_r` = mean over DECIDED signals of
(+RR for tp_first, -1R for sl_first), RR = |tp - entry| / |entry - sl|; and the
6.1 excursions give `reached_1r_rate` (share with mfe_r >= 1) and mean MFE/MAE.

Sample honesty (user ruling 2026-08-12): a cell is always computed but flagged
`ranked = False` below RANK_FLOOR (=20); the renderer must not rank/act on an
unranked cell. Marginals + one 2-D slice (confidence x ADX) — NOT a full
cross-tab, which would shatter the (small) live cohort into empty cells.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratios import MAX_RR, WINSOR_R, clamp_ratio_f, safe_ratio
from app.services.signal_outcomes import OUTCOME_EPOCH
from app.signals import regime as regime_mod

_IST = ZoneInfo("Asia/Kolkata")

RANK_FLOOR = 20  # below this a cell is computed but never ranked (user ruling 2026-08-12)

# R-multiple means are dominated by tiny-SL signals (RR up to ~228 seen live), so
# winsorize per-signal R at ±this bound before averaging — beyond it is a
# near-zero-risk artifact, not a repeatable edge. Count metrics (hit_rate,
# reached_1r_rate) are unaffected. The bound now lives in app/core/ratios.py (H6):
# it was duplicated here and in pair_attribution, alongside two 1000×-larger
# constants doing a different job in signal_excursions and pair_outcome.


def _winsor(x: float) -> float:
    return clamp_ratio_f(x, WINSOR_R)


@dataclass(frozen=True)
class Cell:
    """One attribution cell (a dimension value) and its outcome metrics.

    `ranked` is False when n < RANK_FLOOR — the metrics are still shown, but the
    consumer must not rank or act on them (StyleStatsHeader precedent)."""

    key: str
    n: int
    entered: int
    measured: int                   # rows with an MFE computed — the reach1R / mfe denom
    decided: int                    # tp_first + sl_first
    hit_rate: float | None          # wins / decided
    reached_1r_rate: float | None   # share of MEASURED rows with mfe_r >= 1 (edge available)
    mean_mfe_r: float | None
    mean_mae_r: float | None
    expectancy_r: float | None      # mean over decided of (+RR / -1R)
    ranked: bool


@dataclass(frozen=True)
class Table:
    dimension: str
    cells: list[Cell]


@dataclass(frozen=True)
class AttributionReport:
    cohort: str                     # "tradeable" | "shadow"
    since: datetime
    total: int
    tables: list[Table] = field(default_factory=list)


@dataclass(frozen=True)
class Row:
    status: str
    mfe_r: float | None
    mae_r: float | None
    rr: float | None                # |tp-entry|/|entry-sl|, None if undefined
    confidence: int
    adx: float | None
    direction: str
    setup: str
    created_at: datetime
    timeframe: str
    factors: dict[str, float] = field(default_factory=dict)  # factor name → raw directional score
    # The regime the LIVE gate would enforce on this signal — the persisted
    # signals.regime (branch-recovered at commit), falling back to on-the-fly
    # recovery for legacy NULL rows: identical to regime_guard.signal_regime, so
    # the shadow measurement partitions exactly as the active gate would. None on
    # backtest/corpus rows, which bucket via the raw `adx` level instead.
    regime: str | None = None


def realized_r(row: Row) -> float | None:
    """Realized R for one terminal outcome — the shared expectancy / total-R /
    Sharpe unit. A target hit contributes +winsorized RR (None when RR is
    undefined: a tiny-SL win we cannot size, dropped not guessed); a stop hit
    contributes −1R; anything not decided (expired) is None. Used by the
    attribution cells, the gate experiment, and the §8 walk-forward so a
    signal_outcome and a backtest trade earn R by identical rules."""
    if row.status == "tp_first":
        return _winsor(row.rr) if row.rr is not None else None
    if row.status == "sl_first":
        return -1.0
    return None


_SQL = text(
    "SELECT o.status, o.mfe_r, o.mae_r,"
    "       s.entry_price, s.stop_loss, s.take_profit, s.confidence_pct,"
    "       s.factor_scores, s.direction, COALESCE(s.profile_key, '(base)') AS setup,"
    "       s.created_at, s.timeframe, s.regime"
    "  FROM signal_outcomes o"
    "  JOIN signals s ON s.id = o.signal_id"
    " WHERE s.created_at >= :since"
    "   AND s.is_shadow = :shadow"
    "   AND o.status IN ('tp_first', 'sl_first', 'expired_untouched', 'expired_open')"
)


def _rr(entry: Decimal | None, sl: Decimal | None, tp: Decimal | None) -> float | None:
    """Planned reward:risk. None when undefined (a zero-risk signal has no ratio —
    it is not a ratio of zero), clamped at MAX_RR so one near-zero stop cannot carry
    a cohort's mean or win its sort (H6)."""
    if entry is None or sl is None or tp is None:
        return None
    rr = safe_ratio(abs(tp - entry), abs(entry - sl), cap=MAX_RR)
    return float(rr) if rr is not None else None


def _confidence_bucket(pct: int) -> str:
    if pct < 70:
        return "<70 (sub-gate)"
    if pct < 80:
        return "70–79"
    if pct < 90:
        return "80–89"
    return "90–100"


def _tod_bucket(created: datetime, timeframe: str) -> str:
    """Time-of-day only means something intraday; daily gens run at night."""
    if timeframe == "1d":
        return "eod (1d)"
    ist = created.astimezone(_IST)
    return f"{ist.hour:02d}:00–{ist.hour:02d}:59 IST"


# Regime taxonomy is canonical in app/signals/regime.py — the live gate and this
# measurement must bucket identically. These thin aliases keep the existing
# call sites (and gate_walkforward's import) stable while there is one source.
_parse_adx_level = regime_mod.parse_adx_level
_regime_bucket = regime_mod.adx_regime


_FACTOR_DEADZONE = 0.05


def _factor_bucket(direction: str, score: float) -> str:
    """A factor's stance RELATIVE TO THE TRADE. Factor scores are raw directional
    (>0 = bullish); a SELL's supportive factors are bearish, so align by
    direction — "did this factor agree with the trade, and did agreement predict
    a better outcome?" A near-zero score = the factor didn't weigh in (neutral)."""
    aligned = score if direction == "BUY" else -score
    if aligned > _FACTOR_DEADZONE:
        return "supportive"
    if aligned < -_FACTOR_DEADZONE:
        return "against"
    return "neutral"


def _factor_tables(rows: list[Row]) -> list[Table]:
    """One table per confluence factor that actually fires in the cohort:
    expectancy when it was supportive / against / neutral to the trade. Factors
    that rarely fire (< RANK_FLOOR non-neutral rows — e.g. DOW_TREND is ~always 0)
    can't discriminate, so they're skipped rather than shown as one dead cell."""
    names = sorted({name for r in rows for name in r.factors})
    tables: list[Table] = []
    for name in names:
        def keyfn(r: Row, _n: str = name) -> str:
            return _factor_bucket(r.direction, r.factors.get(_n, 0.0))

        if sum(1 for r in rows if keyfn(r) != "neutral") < RANK_FLOOR:
            continue
        tables.append(_table(f"Factor · {name}", rows, keyfn))
    return tables


def _cell(key: str, rows: list[Row]) -> Cell:
    n = len(rows)
    entered = sum(1 for r in rows if r.status != "expired_untouched")
    decided = [r for r in rows if r.status in ("tp_first", "sl_first")]
    wins = sum(1 for r in decided if r.status == "tp_first")
    mfes = [_winsor(r.mfe_r) for r in rows if r.mfe_r is not None]
    maes = [_winsor(r.mae_r) for r in rows if r.mae_r is not None]
    reached = sum(1 for r in rows if r.mfe_r is not None and r.mfe_r >= 1.0)

    # expectancy_r: mean realized R over decided signals (see realized_r — a win
    # with no defined RR is dropped, not guessed; a loss is -1R regardless).
    exp_terms = [r for r in (realized_r(d) for d in decided) if r is not None]
    return Cell(
        key=key,
        n=n,
        entered=entered,
        measured=len(mfes),
        decided=len(decided),
        hit_rate=(wins / len(decided)) if decided else None,
        # Over MEASURED rows only — a NULL-mfe (tapeless / not-yet-backfilled) row is
        # unmeasured and must not dilute the rate (quant-verifier MEDIUM 2026-08-13).
        reached_1r_rate=(reached / len(mfes)) if mfes else None,
        mean_mfe_r=statistics.fmean(mfes) if mfes else None,
        mean_mae_r=statistics.fmean(maes) if maes else None,
        expectancy_r=statistics.fmean(exp_terms) if exp_terms else None,
        ranked=n >= RANK_FLOOR,
    )


def _table(dimension: str, rows: list[Row], keyfn: Callable[[Row], str]) -> Table:
    groups: dict[str, list[Row]] = {}
    for r in rows:
        groups.setdefault(keyfn(r), []).append(r)
    cells = [_cell(k, grp) for k, grp in groups.items()]

    # Rankable cells first (best expectancy first), unranked cells after.
    def _sort_key(c: Cell) -> tuple[bool, bool, float, str]:
        # "No expectancy" is its own sort position, not a magic -1e9 standing in for
        # one (H6): a sentinel that large is indistinguishable from a real value
        # until it isn't.
        return (not c.ranked, c.expectancy_r is None, -(c.expectancy_r or 0.0), c.key)

    cells.sort(key=_sort_key)
    return Table(dimension=dimension, cells=cells)


def attribute_rows(rows: list[Row]) -> list[Table]:
    """The pure aggregator: rows → the marginal + 2-D attribution tables. Shared
    by the live loader (compute_attribution) and the corpus loader (6.2b), so a
    signal_outcome and a backtest trade are attributed by identical logic."""
    return [
        _table("Confidence", rows, lambda r: _confidence_bucket(r.confidence)),
        _table("Regime (ADX)", rows, lambda r: _regime_bucket(r.adx)),
        _table("Direction", rows, lambda r: r.direction),
        _table("Setup", rows, lambda r: r.setup),
        _table("Time of day", rows, lambda r: _tod_bucket(r.created_at, r.timeframe)),
        _table(
            "Confidence × Regime",
            rows,
            lambda r: f"{_confidence_bucket(r.confidence)} · {_regime_bucket(r.adx)}",
        ),
    ] + _factor_tables(rows)


async def load_attribution_rows(
    db: AsyncSession, *, shadow: bool = False, since: datetime = OUTCOME_EPOCH
) -> list[Row]:
    """The terminal-outcome cohort for one provenance (tradeable = is_shadow
    False, or shadow) as attribution Rows. Read-only. Shared by the attribution
    report and the regime-gate shadow measurement so both see identical live
    signals bucketed by identical rules."""
    raw = (await db.execute(_SQL, {"since": since, "shadow": shadow})).mappings().all()
    rows: list[Row] = []
    for m in raw:
        fs: dict[str, Any] = m["factor_scores"] or {}
        adx_factor = fs.get("ADX")
        adx_expl = adx_factor.get("explanation") if isinstance(adx_factor, dict) else None
        adx = _parse_adx_level(adx_expl)
        factors = {
            n: float(v["score"])
            for n, v in fs.items()
            if isinstance(v, dict) and isinstance(v.get("score"), (int, float))
        }
        rows.append(
            Row(
                status=m["status"],
                mfe_r=float(m["mfe_r"]) if m["mfe_r"] is not None else None,
                mae_r=float(m["mae_r"]) if m["mae_r"] is not None else None,
                rr=_rr(m["entry_price"], m["stop_loss"], m["take_profit"]),
                confidence=int(m["confidence_pct"]),
                adx=adx,
                direction=m["direction"],
                setup=m["setup"],
                created_at=m["created_at"],
                timeframe=m["timeframe"],
                factors=factors,
                # Mirror regime_guard.signal_regime exactly: stored field first,
                # on-the-fly recovery for legacy NULL rows.
                regime=m["regime"] or regime_mod.regime_from_factor_scores(fs),
            )
        )
    return rows


async def compute_attribution(
    db: AsyncSession, *, shadow: bool = False, since: datetime = OUTCOME_EPOCH
) -> AttributionReport:
    """Attribution over the terminal-outcome cohort for one provenance
    (tradeable = is_shadow False, or shadow). Read-only."""
    rows = await load_attribution_rows(db, shadow=shadow, since=since)
    return AttributionReport(
        cohort="shadow" if shadow else "tradeable",
        since=since,
        total=len(rows),
        tables=attribute_rows(rows),
    )


# --------------------------------------------------------------------------- #
# Markdown rendering (the readable decision surface — not a dashboard)         #
# --------------------------------------------------------------------------- #


def _pct(x: float | None) -> str:
    return f"{x:.0%}" if x is not None else "—"


def _r(x: float | None) -> str:
    return f"{x:+.2f}" if x is not None else "—"


def render_attribution_markdown(reports: list[AttributionReport], *, day: date) -> str:
    """One markdown section per cohort/dimension. Unranked (n < RANK_FLOOR)
    cells are shown with a † and never ranked — the honesty affordance."""
    since = reports[0].since.date() if reports else day
    out: list[str] = [
        f"# Entry-quality attribution — {day}",
        "",
        f"_Terminal signal outcomes since {since}. Read-only. Expectancy_r = mean over "
        f"decided of (+RR / −1R), winsorized at ±{WINSOR_R:.0f}R (tiny-SL artifacts). "
        f"reach1R (MFE ≥ +1R), mfe & mae are over `meas` rows (excursion computed), not n. "
        f"Cells with n < {RANK_FLOOR} are shown but **not ranked** (†).__",
        "",
    ]
    for rep in reports:
        out.append(f"## {rep.cohort.title()} cohort — n={rep.total}")
        for t in rep.tables:
            out.append(f"\n### {t.dimension}")
            out.append("| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |")
            out.append("|---|--:|--:|--:|--:|--:|--:|--:|--:|")
            for c in t.cells:
                mark = "" if c.ranked else " †"
                out.append(
                    f"| {c.key}{mark} | {c.n} | {c.entered} | {c.measured} | {_pct(c.hit_rate)} | "
                    f"{_pct(c.reached_1r_rate)} | {_r(c.mean_mfe_r)} | {_r(c.mean_mae_r)} | "
                    f"{_r(c.expectancy_r)} |"
                )
        out.append("")
    out.append(f"† n < {RANK_FLOOR} — shown for completeness, not ranked (insufficient sample).")
    return "\n".join(out)
