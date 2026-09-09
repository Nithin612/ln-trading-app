"""U19 — the holding-day horizon at which a gate separates winners from losers.

For a gate, split the scanned signals into the set it would BLOCK (flagged) vs LET THROUGH (passed)
using the order path's own verdict (`gate_cohort.split_signals` — one predicate, W2), then trace
each signal's realized R forward, day by day from entry:

    R at holding day d = direction·(close of the d-th session AFTER ENTRY − entry) / |entry − SL|
    reached +1R by day d = the favourable excursion (high for a long, low for a short) hit +1R by d

Holding day 1 is the FIRST session after entry (spec: compute on candle N, valid from N+1) — the
entry candle itself is excluded, because a nightly signal's entry is that candle's close, so its
own R is 0 and its own high/low occurred BEFORE entry (a same-bar artifact, not a captured move).
R is winsorized to ±WINSOR_R.

and report, per day, the MEAN R and the %-reaching-+1R for each set. It answers the question the
horizon finding raised (docs/analysis/horizon-recovery-2026-08-25.md): we grade multi-day trades on
a one-day clock — at what holding day does a gate's flagged set actually underperform the set it
lets through? Read-only; never scores/sizes/gates. Empty when signals are absent (current dev DB).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratios import WINSOR_R
from app.models.market_data import OhlcvDaily
from app.models.signal import Signal
from app.services import gate_cohort

_MAX_DAYS = 10          # holding-day horizon (0 = entry day) — covers swing + the d+3 finding
_LOOKAHEAD_BUFFER = 12  # extra calendar days fetched so ~10 TRADING days are present


@dataclass(frozen=True)
class HorizonPoint:
    day: int
    flagged_mean_r: float | None
    passed_mean_r: float | None
    flagged_hit_ge_1r: float | None   # fraction of the set reaching +1R by this day
    passed_hit_ge_1r: float | None
    flagged_n: int                    # signals with a bar at this day
    passed_n: int


@dataclass(frozen=True)
class GateHorizon:
    gate: str
    supported: bool
    reason: str | None
    flagged_total: int
    passed_total: int
    points: list[HorizonPoint] = field(default_factory=list)


@dataclass
class _SigPath:
    """One signal's realized path from entry: winsorized R at each available day + the first day its
    favourable excursion reached +1R (None if never within the fetched window)."""

    r_by_day: list[float]
    first_hit_day: int | None


def _build_path(sig: Signal, rows: list) -> _SigPath | None:  # type: ignore[type-arg]
    """Post-entry bars (index 0 = FIRST session after entry, N+1) → per-day R + first +1R day
    (both 0-indexed over these bars, so index i is holding day i+1). None if risk is zero."""
    entry = float(sig.entry_price)
    risk = abs(entry - float(sig.stop_loss))
    if risk == 0.0:
        return None
    long = sig.direction != "SELL"
    r_by_day: list[float] = []
    first_hit: int | None = None
    for d, b in enumerate(rows):
        close = float(b.close)
        r = (close - entry) / risk if long else (entry - close) / risk
        r_by_day.append(max(-WINSOR_R, min(WINSOR_R, r)))
        if first_hit is None:
            fav = (float(b.high) - entry) / risk if long else (entry - float(b.low)) / risk
            if fav >= 1.0:
                first_hit = d
    return _SigPath(r_by_day=r_by_day, first_hit_day=first_hit)


async def _paths(
    db: AsyncSession, signals: list[Signal], max_days: int
) -> dict[str, _SigPath]:
    """Batched OHLC load → a forward path per signal (index 0 = entry day)."""
    if not signals:
        return {}
    stock_ids = {s.stock_id for s in signals}
    lo = min(s.created_at for s in signals) - timedelta(days=2)
    hi = max(s.created_at for s in signals) + timedelta(days=max_days + _LOOKAHEAD_BUFFER)
    rows = (
        await db.execute(
            select(OhlcvDaily.stock_id, OhlcvDaily.time, OhlcvDaily.high,
                   OhlcvDaily.low, OhlcvDaily.close)
            # is_complete only — a forming (mid-session) daily bar must never enter the horizon,
            # matching excursion.load_1m_bars' no-repaint convention (quant-verifier, 2026-09-09).
            .where(
                OhlcvDaily.stock_id.in_(stock_ids), OhlcvDaily.time >= lo,
                OhlcvDaily.time <= hi, OhlcvDaily.is_complete.is_(True),
            )
            .order_by(OhlcvDaily.time)
        )
    ).all()
    by_stock: dict[int, list] = {}  # type: ignore[type-arg]
    for r in rows:
        by_stock.setdefault(r.stock_id, []).append(r)

    paths: dict[str, _SigPath] = {}
    for s in signals:
        entry_date = s.created_at.date()
        # STRICTLY after entry (N+1 onward) — the entry candle is N (its close is the entry), so
        # its own R/excursion is a same-bar artifact (finding #1). Holding day 1 = first of these.
        fwd = [
            r for r in by_stock.get(s.stock_id, []) if r.time.date() > entry_date
        ][:max_days]
        path = _build_path(s, fwd)
        if path is not None:
            paths[s.id] = path
    return paths


def _stat(
    signals: list[Signal], paths: dict[str, _SigPath], day: int
) -> tuple[float | None, float | None, int]:
    """(mean R, %-reached-+1R, n) for `signals` at holding `day` (1 = first session after entry).

    n = signals with a bar at that day; the denominator SHRINKS as signals run out of bars (or are
    dropped for risk==0), so `flagged_total`/`passed_total` can exceed `max(n)` and the hit-% can be
    non-monotonic across days — a smaller-sample effect, not trades un-hitting +1R."""
    idx = day - 1  # holding day 1 → the first post-entry bar (index 0)
    r_vals: list[float] = []
    hits = 0
    for s in signals:
        p = paths.get(s.id)
        if p is None or idx >= len(p.r_by_day):
            continue
        r_vals.append(p.r_by_day[idx])
        if p.first_hit_day is not None and p.first_hit_day <= idx:
            hits += 1
    n = len(r_vals)
    if n == 0:
        return None, None, 0
    return round(sum(r_vals) / n, 3), round(hits / n, 3), n


async def compute_gate_horizon(
    db: AsyncSession,
    *,
    gate: str,
    rr_min: Decimal,
    min_scoring_factors: int,
    max_dominant_share: Decimal,
    min_sl_atr_mult: Decimal,
    max_days: int = _MAX_DAYS,
) -> GateHorizon:
    """The flagged-vs-passed R horizon for `gate`. Fails soft: unsupported gate → supported=False;
    absent data → points with None means. Reuses the cohort's isolation split (W2)."""
    if gate not in gate_cohort.SUPPORTED_GATES:
        return GateHorizon(
            gate=gate, supported=False,
            reason="horizon not available for this gate (needs an ATR or live state)",
            flagged_total=0, passed_total=0,
        )

    split = await gate_cohort.split_signals(
        db, gate=gate, rr_min=rr_min, min_scoring_factors=min_scoring_factors,
        max_dominant_share=max_dominant_share, min_sl_atr_mult=min_sl_atr_mult,
    )
    flagged = [s for s, _ in split.flagged]
    passed = split.passed
    paths = await _paths(db, flagged + passed, max_days)

    points: list[HorizonPoint] = []
    for d in range(1, max_days + 1):  # holding days 1..N (day 1 = first session after entry, N+1)
        fr, fh, fn = _stat(flagged, paths, d)
        pr, ph, pn = _stat(passed, paths, d)
        points.append(
            HorizonPoint(
                day=d, flagged_mean_r=fr, passed_mean_r=pr,
                flagged_hit_ge_1r=fh, passed_hit_ge_1r=ph, flagged_n=fn, passed_n=pn,
            )
        )
    return GateHorizon(
        gate=gate, supported=True, reason=None,
        flagged_total=len(flagged), passed_total=len(passed), points=points,
    )
