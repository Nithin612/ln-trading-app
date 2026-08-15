"""Pair-signal shadow minter (Phase 6.5b slice 2).

Runs the pair screen (BOTH the `df` and `adf` arms — the A/B) and mints a SHADOW
`PairSignal` for every candidate whose spread is currently at an entry extreme
(|z| ≥ entry_z). Long the cheap leg / short the rich one; exit toward z≈0, stop at
±z_stop. Writes only to `pair_signals` (is_shadow=True) — never the single-name path,
never a real order. De-dups against still-open pair signals so a persistently-extreme
pair is minted once, not every night.

The entry-time z reference (spread value + its z-unit σ) is frozen on the row so the
outcome tracker (slice 3) can compute z forward deterministically: with mean0 =
spread_entry − entry_z·σ, forward z_t = (spread_t − mean0)/σ.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pair import PairSignal
from app.services.pair_universe import screen_universe

# Entry / exit / stop in z-units. Conservative defaults; the shadow evidence tunes them.
ENTRY_Z = 2.0
EXIT_Z = 0.0
STOP_Z = 3.5
VALIDITY_DAYS = 30

_METHODS = ("df", "adf")


async def mint_pair_signals(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    entry_z: float = ENTRY_Z,
    z_exit: float = EXIT_Z,
    z_stop: float = STOP_Z,
    validity_days: int = VALIDITY_DAYS,
) -> list[PairSignal]:
    """Mint shadow PairSignals for currently-extreme candidate pairs (both arms).
    Read-only except the additive `pair_signals` inserts; de-duped against open rows.
    `now` injectable for deterministic tests (no hidden clock)."""
    now = now or datetime.now(tz=UTC)
    validity = now + timedelta(days=validity_days)

    open_keys: set[tuple[int, int, str]] = {
        (a, b, m)
        for a, b, m in (
            await db.execute(
                select(
                    PairSignal.stock_a_id, PairSignal.stock_b_id, PairSignal.method
                ).where(PairSignal.status == "open")
            )
        ).all()
    }

    minted: list[PairSignal] = []
    for method in _METHODS:
        for cand in await screen_universe(db, method=method, now=now):
            z = cand.stat.zscore
            # Skip if not at an extreme, OR already beyond its own stop — a signal born past
            # z_stop would book a favourable reversion as a stop-loss (bug-hunter MEDIUM).
            if abs(z) < entry_z or abs(z) >= abs(z_stop):
                continue
            a_id, b_id = cand.stock_a_id, cand.stock_b_id
            if a_id is None or b_id is None:
                continue
            if (a_id, b_id, method) in open_keys:
                continue  # already have an open signal for this pair+arm
            sigma = Decimal(str(round(cand.stat.z_sigma, 4)))
            if sigma <= 0:
                continue  # sub-tick σ rounds to 0 → un-usable z divisor (bug-hunter Finding 3)
            if z <= -entry_z:
                direction, signed_stop = "long_spread", -abs(z_stop)
            else:
                direction, signed_stop = "short_spread", abs(z_stop)
            sig = PairSignal(
                stock_a_id=a_id,
                stock_b_id=b_id,
                sector=cand.sector,
                method=method,
                beta=cand.stat.beta,
                alpha=cand.stat.alpha,
                half_life=cand.stat.half_life,
                df_tstat=cand.stat.df_tstat,
                adf_pvalue=cand.stat.adf_pvalue,
                direction=direction,
                entry_z=z,
                z_exit=z_exit,
                z_stop=signed_stop,
                spread_entry=Decimal(str(round(cand.stat.spread_last, 4))),
                spread_sigma=sigma,
                validity_until=validity,
            )
            db.add(sig)
            open_keys.add((a_id, b_id, method))  # avoid a dup within this same run
            minted.append(sig)

    if minted:
        await db.commit()
    return minted
