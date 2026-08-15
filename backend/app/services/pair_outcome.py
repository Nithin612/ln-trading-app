"""Spread-outcome tracker (Phase 6.5b slice 3).

For each OPEN shadow `PairSignal`, walk the spread's z-score forward from the daily tape
(no look-ahead — bars evaluated in date order) and resolve it the first time z reverts to
the exit (win) or hits the stop (loss); mark it expired if validity lapses first. Writes
`outcome_r` (in R, comparable to the single-name attribution) + the exit fields.

The z reference is FROZEN at entry: with mean0 = spread_entry − entry_z·σ, forward
z_t = (spread_t − mean0)/σ where spread_t = A_t − (α + β·B_t). R = favourable-z-move / risk,
risk = |z_stop − entry_z| in z-units. The ACTUAL crossing z is used (so a daily gap through
the stop books worse than −1R — honest, like the single-name gap-through-stop convention).

Read-only except the additive resolution of `pair_signals` rows; mints nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pair import PairSignal
from app.services.pair_universe import load_daily_closes

_IST = ZoneInfo("Asia/Kolkata")
_R_BOUND = 9999.999  # Numeric(7,3) cap; slice-4 attribution winsorizes tiny-risk artifacts


@dataclass(frozen=True)
class SpreadOutcome:
    status: str  # "tp_first" | "sl_first" | "expired"
    exit_z: float
    spread_exit: float
    outcome_r: float
    resolved_at: datetime


def resolve_spread(
    sig: PairSignal,
    a_closes: dict[date, float],
    b_closes: dict[date, float],
    *,
    now: datetime,
) -> SpreadOutcome | None:
    """Resolve one open pair signal from forward closes ({date: close} per leg), or None
    if it is still open (no cross yet and validity not lapsed). Pure — no DB."""
    sigma = float(sig.spread_sigma)
    risk = abs(sig.z_stop - sig.entry_z)
    if sigma <= 0 or risk <= 0:
        return None
    mean0 = float(sig.spread_entry) - sig.entry_z * sigma
    is_long = sig.direction == "long_spread"
    entry_date = sig.created_at.astimezone(_IST).date()
    valid_date = sig.validity_until.astimezone(_IST).date()  # bound resolution to validity

    def outcome(status: str, z: float, spread: float, when: datetime) -> SpreadOutcome:
        fav = (z - sig.entry_z) if is_long else (sig.entry_z - z)
        r = max(-_R_BOUND, min(_R_BOUND, fav / risk))
        return SpreadOutcome(
            status=status, exit_z=z, spread_exit=spread, outcome_r=r, resolved_at=when
        )

    last: tuple[float, float] | None = None  # (z, spread) of the most recent IN-WINDOW bar
    # Only bars strictly after entry and on/before validity — a cross past validity is an
    # EXPIRY, not a tp/sl (quant-verifier HIGH: else post-validity crosses corrupt the A/B,
    # and calendar-day validity can lapse on a weekend when the Mon–Fri tracker isn't running).
    for d in sorted(dd for dd in (set(a_closes) & set(b_closes)) if entry_date < dd <= valid_date):
        spread = a_closes[d] - (sig.alpha + sig.beta * b_closes[d])
        z = (spread - mean0) / sigma
        last = (z, spread)
        when = datetime(d.year, d.month, d.day, 10, 0, tzinfo=UTC)  # ~15:30 IST close
        crossed_stop = z <= sig.z_stop if is_long else z >= sig.z_stop
        crossed_exit = z >= sig.z_exit if is_long else z <= sig.z_exit
        if crossed_stop:
            return outcome("sl_first", z, spread, when)
        if crossed_exit:
            return outcome("tp_first", z, spread, when)

    if now >= sig.validity_until:  # no cross before expiry → mark expired
        if last is not None:
            return outcome("expired", last[0], last[1], sig.validity_until)
        return outcome("expired", sig.entry_z, float(sig.spread_entry), sig.validity_until)
    return None


async def track_pair_outcomes(db: AsyncSession, *, now: datetime | None = None) -> int:
    """Resolve every open PairSignal from the forward tape. Returns the count resolved.
    Additive: only fills the outcome fields on `pair_signals` rows, mints nothing."""
    now = now or datetime.now(tz=UTC)
    open_sigs = (
        (await db.execute(select(PairSignal).where(PairSignal.status == "open"))).scalars().all()
    )

    resolved = 0
    for sig in open_sigs:
        closes = await load_daily_closes(db, [sig.stock_a_id, sig.stock_b_id], since=sig.created_at)
        res = resolve_spread(
            sig, closes.get(sig.stock_a_id, {}), closes.get(sig.stock_b_id, {}), now=now
        )
        if res is None:
            continue
        sig.status = res.status
        sig.exit_z = res.exit_z
        sig.spread_exit = Decimal(str(round(res.spread_exit, 4)))
        sig.outcome_r = Decimal(str(round(res.outcome_r, 3)))
        sig.resolved_at = res.resolved_at
        resolved += 1

    if resolved:
        await db.commit()
    return resolved
