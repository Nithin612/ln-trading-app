"""Order-eligibility PREVIEW — what the ACTIVE gates would do, judged for a LIST.

`api/v1/trading.py::place_order` rejects on the first eligibility rule that fires. The
display path (`api/v1/signals.py`, `api/v1/suggestions.py`) once ran NONE of them, so a
signal the order path was certain to reject still rendered with a live Buy button: on
2026-09-02, **41 of 204 listed signals** were in that state. Users spent clicks on
guaranteed failures and read the list as "my options".

## What changed with A38

The first fix (2026-09-02) was a second, hand-written copy of the gate sequence, kept in
step with the order path by a contract test and a comment. That is a synchronisation
ritual, and the ritual is what had just failed. **The rules now live once, in
`app/signals/restrictions.py`**, and this module is the display-path ADAPTER over them:
it decides what a list can cheaply supply, then reports the composed result in the shape
the API schema wants. There is no longer a second list of gates to forget to update.

`COVERED_GATES` and `UNCOVERED_GATES` are consequently **derived** from the registry's
`requires` declarations rather than typed out. Adding a restriction that needs live state
makes it uncovered automatically, and an ACTIVE uncovered gate is NAMED in `unassessed` —
"unknown", never a silent "clear". That is the enforcement, and unlike the comment it
replaces, it cannot lapse.

Evaluation order is the registry's, which is the order path's.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from app.models.signal import Signal
from app.signals import restrictions
from app.signals.restrictions import (  # re-exported: ONE definition of each
    GATE_CHASE,
    GATE_CIRCUIT,
    GATE_DIVERSITY,
    GATE_ENTRY_QUALITY,
    GATE_LIQUIDITY,
    GATE_MARKET_REGIME,
    GATE_OFFMARKET,
    GATE_REGIME,
    GATE_RR,
    GATE_SECTOR_RS,
    GATE_SL_ATR,
    GATE_THROUGH_STOP,
    OFFMARKET_REASON,
    through_stop_reason,
)

__all__ = [
    "CLEAR",
    "COVERED_GATES",
    "GATE_CHASE",
    "GATE_CIRCUIT",
    "GATE_DIVERSITY",
    "GATE_ENTRY_QUALITY",
    "GATE_LIQUIDITY",
    "GATE_MARKET_REGIME",
    "GATE_OFFMARKET",
    "GATE_REGIME",
    "GATE_RR",
    "GATE_SECTOR_RS",
    "GATE_SL_ATR",
    "GATE_THROUGH_STOP",
    "OFFMARKET_REASON",
    "UNCOVERED_GATES",
    "EligibilityPreview",
    "gate_modes",
    "mode_banner",
    "preview",
    "through_stop_reason",
]

#: The context a LIST endpoint can supply per row without per-row I/O. Everything else —
#: a Redis circuit band, a 20-session traded-value aggregate, index history — is why a
#: gate is "uncovered".
#:
#: ⚠ This is the SAME set `preview` declares from, not a parallel list: the two diverging
#: meant a rule requiring `CTX_FILL_PRICE` would be classified UNCOVERED (so callers
#: believed it was reported, not judged) while `check` in fact judged it against the
#: stand-in thresholds below (bug-hunter LOW, 2026-09-05).
LIST_AVAILABLE = frozenset(
    {
        restrictions.CTX_MARKET_PRICE,
        restrictions.CTX_FILL_PRICE,
        restrictions.CTX_ATR,
        # V3 — membership is ONE already-joined boolean per row, not per-row I/O, so the
        # display path can judge it exactly as the order path does. Leaving it out would
        # have made the most important new block in the document render as `unassessed`.
        restrictions.CTX_IN_UNIVERSE,
    }
)


def _moded_ids(gate: str) -> tuple[str, ...]:
    """Registry ids → settings-moded ids. Entry-quality is two independently-moded checks
    (diversity + sl_atr) behind one badge, because it returns one combined reason."""
    return (GATE_DIVERSITY, GATE_SL_ATR) if gate == GATE_ENTRY_QUALITY else (gate,)


#: DERIVED, not hand-listed: any overlay needing context a list cannot cheaply read.
UNCOVERED_GATES: tuple[str, ...] = tuple(
    g
    for r in restrictions.REGISTRY
    if r.enforced_by is restrictions.EnforcedBy.OVERLAY and not r.requires <= LIST_AVAILABLE
    for g in _moded_ids(r.gate)
)
#: The complement — every other settings-moded gate is judged here exactly as on the
#: order path. Together they cover `MODED_GATES`, which is what `preview` must be handed.
COVERED_GATES: tuple[str, ...] = tuple(
    g for g in restrictions.MODED_GATES if g not in set(UNCOVERED_GATES)
)


@dataclass(frozen=True)
class EligibilityPreview:
    """What an ACTIVE gate would do to this signal at order time.

    `reason` is verbatim the order path's rejection detail — same registry, same string.
    `unassessed` names ACTIVE gates this preview could not judge: non-empty means
    "possibly blocked, unknown", NEVER "clear"."""

    blocked: bool
    gate: str | None = None
    reason: str | None = None
    unassessed: tuple[str, ...] = field(default_factory=tuple)


CLEAR = EligibilityPreview(blocked=False)


def preview(
    signal: Signal,
    *,
    modes: Mapping[str, str],
    atr: Decimal | None = None,
    market_price: Decimal | None = None,
    fill_price: Decimal | None = None,
    in_universe: bool | None = None,
    allow_offmarket: bool = True,
    max_chase_r: Decimal | None = None,
    rr_min: Decimal | None = None,
    min_scoring_factors: int,
    max_dominant_share: Decimal,
    min_sl_atr_mult: Decimal,
) -> EligibilityPreview:
    """The first rule that would reject `signal`, or a CLEAR verdict.

    Pure: modes and thresholds are arguments, so this cannot read a stale settings
    singleton. `modes` must carry EVERY gate in `restrictions.MODED_GATES` — a missing key
    raises rather than defaulting to "off", because a partial map is exactly what made the
    original `unassessed` tripwire imaginary (bug-hunter, 2026-09-02).

    Runs BOTH the settings-moded overlays and the paper broker's own unconditional
    pre-fill rejections, because a user clicking Buy meets both. Every rule fails open
    exactly as it does on the order path: a signal that cannot be assessed is eligible on
    that dimension, never suppressed on uncertainty.

    ⚠ `fill_price`, when given, is judged instead of `market_price` for the through-stop
    check — the broker tests its POST-SLIPPAGE fill, and a raw-LTP comparison disagrees
    inside a half-spread band in both directions.
    """
    available: set[str] = set()
    if market_price is not None:
        available.add(restrictions.CTX_MARKET_PRICE)
    if fill_price is not None:
        # Declared separately from the LTP: `through_stop` accepts EITHER, and treating a
        # fill as "no price" skipped the check and reported a void setup as clear.
        available.add(restrictions.CTX_FILL_PRICE)
    if atr is not None:
        available.add(restrictions.CTX_ATR)
    if in_universe is not None:
        available.add(restrictions.CTX_IN_UNIVERSE)
    # Intersect, so what a list SUPPLIES can never exceed what `LIST_AVAILABLE` claims it
    # supplies — the derivation of COVERED/UNCOVERED depends on those being the same set.
    available &= LIST_AVAILABLE

    ctx = restrictions.RestrictionContext(
        signal=signal,
        side=signal.direction,
        as_of=signal.created_at,
        available=frozenset(available),
        atr=atr,
        market_price=market_price,
        fill_price=fill_price,
        in_universe=in_universe,
        allow_offmarket=allow_offmarket,
    )
    cfg = restrictions.RestrictionConfig(
        modes=modes,
        min_scoring_factors=min_scoring_factors,
        max_dominant_share=max_dominant_share,
        min_sl_atr_mult=min_sl_atr_mult,
        rr_min=rr_min if rr_min is not None else Decimal("1.0"),
        max_chase_r=max_chase_r if max_chase_r is not None else Decimal("0.33"),
        # ── Thresholds for the UNCOVERED gates ────────────────────────────────────
        # Unreachable by construction: those restrictions need context a list cannot
        # supply, so `check` skips them before any threshold is read. They are therefore
        # deliberately set to values that BLOCK EVERYTHING rather than to plausible ones.
        # If `LIST_AVAILABLE` ever grows and a gate becomes reachable here, the display
        # path starts rejecting every row — loud and immediate — instead of quietly
        # judging against fabricated numbers that look like settings but are not
        # (quant-verifier MEDIUM). Failing CLOSED is right in this branch specifically:
        # the module's whole thesis is that "unknown" must never render as "clear".
        # `test_restrictions.py` pins the unreachability directly.
        circuit_proximity_pct=Decimal("100"),
        sector_rs_lookback=1,
        sector_rs_min_excess_pct=Decimal("1e9"),
        market_regime_dma_period=1,
        market_regime_dma_buffer_pct=Decimal("1e9"),
        market_regime_vix_threshold=Decimal("-1"),
        market_regime_market_symbol="__UNREACHABLE__",
        liquidity_lookback=1,
        liquidity_min_traded_value=Decimal("1e18"),
    )
    out = restrictions.check(ctx, cfg)
    return EligibilityPreview(
        blocked=out.blocked, gate=out.gate, reason=out.reason, unassessed=out.unassessed
    )


def mode_banner(mode: str, *, since: str | None = None) -> str:
    """The clause a shadow REPORT must print to state what its gate is actually doing.

    `regime_gate_shadow` and `circuit_gate_shadow` used to HARDCODE "SHADOW: nothing is
    suppressed." in their preamble. That sentence was FALSE for the 19 days the regime
    gate ran active (2026-08-14 → 2026-09-02): every reader of those reports — including
    the readings used to justify keeping the gate on — was told nothing was being
    suppressed while the order path rejected transitional entries outright. A report that
    misstates its own regime is worse than no report, so the wording is derived from the
    live mode and lives in ONE place.

    `since` guards the inverse error (bug-hunter LOW, 2026-09-02): the mode is read at
    RENDER time while the cohort spans a window in which it may have changed, so a report
    generated after a revert would otherwise claim "nothing is suppressed" about trades
    that WERE suppressed. Pass the date the current mode took effect and it is stated.
    """
    if mode == "active":
        body = (
            "⚠ **THE GATE IS ACTIVE** — these signals ARE being suppressed on the order "
            "path right now, so the 'would-block' set below is a live counterfactual, not "
            "a hypothetical."
        )
    elif mode == "off":
        body = "GATE OFF: nothing is suppressed and no verdict is stamped."
    else:
        body = "SHADOW: nothing is suppressed."
    if since:
        body += (
            f" (Mode as of report time, effective {since} — the cohort below may span an "
            "earlier period under a DIFFERENT mode; check the changelog before reading a "
            "suppressed-set number as counterfactual.)"
        )
    return body


def gate_modes() -> dict[str, str]:
    """Every gate's LIVE mode, keyed by the registry's ids.

    Delegates to `restrictions.config_from_settings` so there is ONE reading of settings
    and `preview` is always handed the COMPLETE picture.
    """
    return dict(restrictions.config_from_settings().modes)
