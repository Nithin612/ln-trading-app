"""D2′a — the tradeable universe as a NAMED, VERSIONED RULE.

⭐ **The shape of the fix, and why it is not a repair script.** `is_active` is a
mutable boolean with three writers and no owner. Repairing its *value* leaves the
data model that produced the 2026-09-07 failure intact; every one of the 3,392
`stocks` rows was minted that night, so there was never an "original" to restore
(plan §25a). The universe is therefore DERIVED — evaluated from dated facts, and
materialised — rather than written.

⚠ **SHADOW-FIRST, on purpose.** This module computes and records; it does NOT touch
`is_active`. Removing the flag's three writers is D2′b and waits on a measured diff,
because that is the same discipline this project applies to every gate — and the two
gates it ever promoted on an argument were both refuted within weeks.

## Where the rule lives, and the honest limitation

The rule's DEFINITION is in code (git is already versioned, reviewable and diffable);
its EVALUATION is in the database, which is what needs point-in-time answers. That
split is deliberate rather than lazy.

⚠ **What this cannot do: reconstruct why a name was EXCLUDED on a past date.** The
rule is deterministic given its inputs, but its inputs — today's `EQUITY_L.csv` and
today's `kite_instruments` — are not themselves snapshotted. So the snapshot answers
*"was X in the universe on D"* exactly, and *"why was Y out on D"* only as far as the
recorded reason goes. Storing a reason per excluded name would triple the table to
answer a question whose inputs we do not keep.

## The rule, v1

    EQ_LISTED ∧ KITE_TRADABLE

`EQ_LISTED`      — the symbol appears in `EQUITY_L.csv` with series `EQ`.
`KITE_TRADABLE`  — a plain `EQ` instrument exists in `kite_instruments` for it.

⛔ **No bar-count term**, against the original §8 draft, and this is load-bearing:
bar coverage is a fact about OUR OWN data completeness, and *a rule that reads its own
completeness shrinks when our ingestion breaks* — which is 2026-09-07 rebuilt inside
the mechanism meant to prevent it. The engine's 300-bar window is a SCORING-TIME
eligibility question: a name with too little history is unscoreable today, never
unlisted. Two layers, two questions (plan §25e/1).

⛔ **No liquidity, price or market-cap term.** Those are EMPIRICAL claims under §6/2
and need the project's `t ≈ 3.6` bar or an explicit user ruling; the liquidity floor
in particular was measured and REJECTED (the illiquid set was net-positive).
"""

from __future__ import annotations

from dataclasses import dataclass

RULE_VERSION = "v1"

REASON_OK = "eligible"
REASON_NOT_EQ_LISTED = "not_eq_listed"
REASON_NOT_KITE_TRADABLE = "not_kite_tradable"


@dataclass(frozen=True)
class UniverseInputs:
    """Everything the rule reads, passed explicitly so it is testable without a
    database or a network call."""

    eq_listed: frozenset[str]
    """Symbols with series `EQ` in EQUITY_L."""

    kite_tradable: frozenset[str]
    """Symbols with a plain `EQ` row in kite_instruments."""


def evaluate(symbol: str, inputs: UniverseInputs) -> tuple[bool, str]:
    """Return `(included, reason)` for one symbol. Pure.

    Reasons are ordered most-fundamental first: a name NSE does not list as `EQ` is
    reported that way even if Kite happens to carry an instrument for it, because the
    listing is the more basic fact.
    """
    if symbol not in inputs.eq_listed:
        return False, REASON_NOT_EQ_LISTED
    if symbol not in inputs.kite_tradable:
        return False, REASON_NOT_KITE_TRADABLE
    return True, REASON_OK


def evaluate_all(symbols: list[str], inputs: UniverseInputs) -> dict[str, tuple[bool, str]]:
    return {s: evaluate(s, inputs) for s in symbols}


@dataclass(frozen=True)
class ShadowDiff:
    """What flipping `is_active` to the rule's output WOULD do — measured, not done.

    `would_activate` and `would_deactivate` are the two directions of the 2026-09-07
    damage, and they must be reported separately: the outage made good names inactive
    AND left bad ones active, and a count that blends them hides half the defect.
    """

    would_activate: list[str]
    would_deactivate: list[tuple[str, str]]
    agree_active: int
    agree_inactive: int

    @property
    def total_changed(self) -> int:
        return len(self.would_activate) + len(self.would_deactivate)


def shadow_diff(
    live: dict[str, bool], verdicts: dict[str, tuple[bool, str]]
) -> ShadowDiff:
    """Compare the live flag against the rule, for symbols present in both."""
    would_activate: list[str] = []
    would_deactivate: list[tuple[str, str]] = []
    agree_active = agree_inactive = 0
    for symbol in sorted(live):
        verdict = verdicts.get(symbol)
        if verdict is None:
            continue
        included, reason = verdict
        if included and not live[symbol]:
            would_activate.append(symbol)
        elif not included and live[symbol]:
            would_deactivate.append((symbol, reason))
        elif included:
            agree_active += 1
        else:
            agree_inactive += 1
    return ShadowDiff(
        would_activate=would_activate,
        would_deactivate=would_deactivate,
        agree_active=agree_active,
        agree_inactive=agree_inactive,
    )
