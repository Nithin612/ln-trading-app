"""Queue item 4 — find the backtest trades the live engine would have REFUSED.

## ⛔⛔ The defect

`_simulate_trade` fills at the open of bar N+1. When that open has already gapped through the
stop, it fills there anyway and then "stops out" at the stop — which is now on the *profitable*
side of the fill. Executed (**M5**): signal close 100 / stop 99 / next open 95 ⇒ entry 95, exit 99,
`hit_sl=True`, **+4.211%**. Live is immune by explicit rejection (**M8**): `place_paper_order`
computes the fill and then calls `through_stop_reason`, raising `PaperOrderError`.

⭐⭐ **The trades are invisible in the R distribution, and that is the interesting part (M64).**
D1, D5 and the positional probe all divide by the **fill**-referenced risk — `abs(entry_price −
stop) / entry_price` — and the fill IS the gap open, so the ratio is

    (stop − fill) / |fill − stop| = +1.0000   exactly, at every gap size

Measured at gaps of 2%, 5%, 10% and 20%: `+1.0000, +1.0000, +1.0000, +1.0000`. A contaminated
trade is arithmetically indistinguishable from a genuine +1R winner. **You cannot find these by
looking at R.** You find them by asking whether the fill was already through the stop — which is
what this module does, and it asks the LIVE path's own predicate so the backtest corpus is exactly
the set live would accept (**W2**: `through_stop_reason` is owned by `app/signals/restrictions.py`
and is not re-derived here).

## Why DELETE and not "refill at a worse price"

These are not mispriced trades, they are **trades that could not exist**. The live engine refuses
them; a corpus containing them is a population error, not a magnitude error (Claude BT7). Refilling
at the open and exiting immediately is a coherent sensitivity check — it books 0.000R rather than
+1.000R — but the primary treatment is removal.

## What to expect, measured before the fix (M85)

The contamination rate is the archive's entry-bar gap exposure at the trade's own stop width, and
because each affected trade contributes exactly +1.000R the shift on a mean is arithmetic:

| stop width | P(gap through) | bias on mean R |
|---|--:|--:|
| p10 0.65% | 10.068% | **+0.1231** |
| order-path floor 2% | 2.499% | +0.0282 |
| median 5% | 0.470% | +0.0052 |
| swing cap 8% | 0.191% | +0.0021 |

⇒ **item 4's 0.05R falsifier can only fire below a 2% stop**, which the notional cap already
refuses. Expect D1/D5/B7 to move materially only through their sub-2% cohorts.

⚠ **`app/backtest/engine.py` is FROZEN and is NOT touched here.** Repairing the simulator itself
would change every walk-forward golden and the Rust parity oracle, and needs sign-off plus an §8
regression. This module lets every study filter its own corpus today, at no such cost.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.backtest.engine import TradeRecord
from app.signals.restrictions import through_stop_reason


def is_unfillable(record: TradeRecord) -> bool:
    """True when the live engine would have refused this trade at its own fill price.

    Delegates to `through_stop_reason`, the predicate `place_paper_order` uses, so "what the
    backtest kept" and "what live would accept" cannot drift apart.

    ⚠ A fill landing EXACTLY on the stop counts as refused — that is the live rule (`price <=
    stop_loss` for a long), and it is also the case where fill-referenced R is undefined (÷0) and
    every study's `risk_pct <= 0` guard silently drops the row anyway.
    """
    return (
        through_stop_reason(
            side=record.direction,
            price=Decimal(str(record.entry_price)),
            stop_loss=Decimal(str(record.stop_loss)),
        )
        is not None
    )


def partition(
    records: Iterable[TradeRecord],
) -> tuple[list[TradeRecord], list[TradeRecord]]:
    """Split into (tradeable, refused). The second list is the population error."""
    tradeable: list[TradeRecord] = []
    refused: list[TradeRecord] = []
    for r in records:
        (refused if is_unfillable(r) else tradeable).append(r)
    return tradeable, refused


@dataclass(frozen=True)
class DeleteTreatment:
    """What removing the impossible trades did to a mean, reported so it can be checked.

    `shift` is `mean_after − mean_before`. It should come out NEGATIVE: every removed trade
    contributed exactly +1.000R (M64), so deleting them can only pull a mean down.
    """

    n_before: int
    n_dropped: int
    mean_before: float
    mean_after: float

    @property
    def shift(self) -> float:
        return self.mean_after - self.mean_before

    @property
    def dropped_fraction(self) -> float:
        return self.n_dropped / self.n_before if self.n_before else 0.0

    def line(self) -> str:
        return (
            f"delete treatment: n {self.n_before} → {self.n_before - self.n_dropped} "
            f"(dropped {self.n_dropped}, {self.dropped_fraction * 100:.3f}%)  "
            f"mean {self.mean_before:+.4f} → {self.mean_after:+.4f} "
            f"(shift {self.shift:+.4f})"
        )


def apply_delete_treatment(
    records: Sequence[TradeRecord], values: Sequence[float]
) -> DeleteTreatment:
    """Recompute a mean with the refused trades removed.

    `values` is whatever the study averages — R, raw %, bps — one per record, same order. The
    module deliberately does not compute R itself: three definitions of R are live in this
    codebase (M60), and picking one here would silently impose it on every caller.
    """
    if len(records) != len(values):
        raise ValueError(f"{len(records)} records against {len(values)} values")
    kept = [v for r, v in zip(records, values, strict=True) if not is_unfillable(r)]
    n_dropped = len(records) - len(kept)
    return DeleteTreatment(
        n_before=len(records),
        n_dropped=n_dropped,
        mean_before=sum(values) / len(values) if values else 0.0,
        mean_after=sum(kept) / len(kept) if kept else 0.0,
    )
