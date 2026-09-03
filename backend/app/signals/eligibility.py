"""Order-eligibility PREVIEW — what the ACTIVE gates would do, judged for a LIST.

`api/v1/trading.py::place_order` runs seven eligibility overlays plus the paper broker's
own pre-fill checks, and rejects on the first one that fires. The display path
(`api/v1/signals.py`) ran NONE of them, so a signal the order path was certain to reject
still rendered with a live Buy button: on 2026-09-02, **41 of 204 listed signals** were in
that state. Users spent clicks on guaranteed failures and read the list as "my options".

This module is the single source of truth for "would an ACTIVE gate reject this signal",
so the list, the detail endpoint and the order path cannot word it differently. Every
reason it returns is VERBATIM the string the order path rejects with.

## What it can and cannot judge

`COVERED_GATES` are decidable from the signal row plus two cheap optional inputs (an ATR
and a live price), so a list endpoint can evaluate them without per-row I/O.

`UNCOVERED_GATES` each need live state a list cannot cheaply read — a Redis circuit band,
a 20-session traded-value aggregate, index history. They are all SHADOW as of 2026-09-02,
so nothing they would block is being missed today.

⚠ **If an uncovered gate is flipped ACTIVE, extend this module IN THE SAME COMMIT.** The
`unassessed` field is the enforcement, not a comment: `preview` is handed EVERY gate's
mode, and any ACTIVE gate it cannot judge is NAMED in `unassessed` (with a WARNING logged
by the caller). "Unknown", never a silent "clear". There is a test per uncovered gate
pinning this — bug-hunter 2026-09-02 caught the first version of this module claiming a
safety net it did not actually have (it only ever checked sl_atr).

Evaluation ORDER mirrors the order path, so the reason shown is the one hit first.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from app.models.signal import Signal
from app.signals import chase_guard, entry_quality, regime_guard, rr_guard

# ── Gate identity ─────────────────────────────────────────────────────────────
# Keys are the `settings.<key>_mode` field stems, so a caller builds the mode map
# straight from settings and a missing key is a visible KeyError, not a silent skip.
GATE_REGIME = "regime_gate"
GATE_DIVERSITY = "entry_diversity_gate"
GATE_SL_ATR = "entry_sl_atr_gate"
GATE_CIRCUIT = "circuit_gate"
GATE_SECTOR_RS = "sector_rs_gate"
GATE_MARKET_REGIME = "market_regime_gate"
GATE_LIQUIDITY = "liquidity_gate"
GATE_CHASE = "chase_gate"
GATE_RR = "rr_gate"

#: Judged here (given the optional atr / market_price inputs).
#: `GATE_RR` is fully decidable from the signal row alone (planned levels, no live data),
#: so the display path judges it exactly as the order path does.
COVERED_GATES: tuple[str, ...] = (
    GATE_REGIME,
    GATE_DIVERSITY,
    GATE_SL_ATR,
    GATE_CHASE,
    GATE_RR,
)
#: Need live state a list cannot cheaply read — reported, never silently passed.
#: (`GATE_CHASE` is NOT here: `chase_guard.evaluate` is pure and needs only entry/SL/side
#: plus the live price this module already receives, so it is judged — quant-verifier
#: 2026-09-02 pointed out that listing it as uncovered would log a warning per row for a
#: perfectly decidable gate.)
UNCOVERED_GATES: tuple[str, ...] = (
    GATE_CIRCUIT,
    GATE_SECTOR_RS,
    GATE_MARKET_REGIME,
    GATE_LIQUIDITY,
)

#: Not settings-moded: the paper broker's own unconditional pre-fill rejections. BOTH are
#: previewed. `through_stop` is the most likely failing click for a stale swing signal;
#: `offmarket` is the most likely failing click FULL STOP, because `allow_offmarket_entry`
#: defaults False and the list is usually read outside market hours — every row read
#: `blocked=False` in the evening while the order path 422'd all of them (quant-verifier,
#: 2026-09-02).
GATE_THROUGH_STOP = "through_stop"
GATE_OFFMARKET = "offmarket"

# UI slug for the entry-quality gate — both its checks surface under one badge, matching
# `entry_quality.order_block_reason`, which returns one combined reason.
GATE_ENTRY_QUALITY = "entry_quality"


#: Verbatim the sentence `place_paper_order` raises when there is no live tick and the
#: user has not opted into off-market entry. Owned here for the same reason as
#: `through_stop_reason`: two copies would drift.
OFFMARKET_REASON = (
    "No live market price for this stock right now — the market may be closed "
    "or the stock isn't trading, so a fill would use a stale prior close. "
    "Enable 'Allow off-market entry' in Settings to override."
)


def through_stop_reason(*, side: str, price: Decimal, stop_loss: Decimal) -> str | None:
    """The rejection for a price already at/through the stop, or None if tradeable.

    A long at/below its own stop (or a short at/above) is a position already through the
    stop before it exists — it happens when a signal's entry has gone stale and price has
    travelled past the stop (a BUY planned at ₹238.21 with SL ₹237.26, clicked while the
    stock trades ₹191). Owned here so `place_paper_order` and the preview raise/report the
    IDENTICAL sentence; a copy in two places would drift.

    ⚠ `price` must be the MODELLED FILL, not the raw LTP. The broker checks its
    post-slippage fill, so comparing a raw LTP disagrees inside a half-spread/half-tick
    band **in both directions** — LTP 237.25 vs SL 237.26 previewed as blocked while the
    order path fills 237.30 and allows it (a false BLOCK hides a tradeable signal, the
    worse error), and LTP 40.01 vs SL 40.00 previewed clear while the fill lands 40.00 and
    422s (quant-verifier, 2026-09-02). Callers pass `simulate_fill(ltp, side).fill`, which
    is pure with `depth=None` and therefore list-safe."""
    is_long = side.upper() in ("LONG", "BUY")
    through = price <= stop_loss if is_long else price >= stop_loss
    if not through:
        return None
    pos_side = "LONG" if is_long else "SHORT"
    return (
        f"Price has moved through this signal's stop loss (₹{stop_loss}) — a "
        f"{pos_side} entered at ₹{price} would already be past its own stop. "
        "The setup is void; wait for a fresh signal rather than entering this one."
    )


@dataclass(frozen=True)
class EligibilityPreview:
    """What an ACTIVE gate would do to this signal at order time.

    `reason` is verbatim the order path's rejection detail. `unassessed` names ACTIVE
    gates this preview could not judge — non-empty means "possibly blocked, unknown",
    NEVER "clear"."""

    blocked: bool
    gate: str | None = None
    reason: str | None = None
    unassessed: tuple[str, ...] = field(default_factory=tuple)


CLEAR = EligibilityPreview(blocked=False)


def _unassessed(
    modes: Mapping[str, str], *, atr: Decimal | None, price: Decimal | None
) -> tuple[str, ...]:
    """Every ACTIVE gate this preview cannot decide, given the inputs it was handed."""
    out = [g for g in UNCOVERED_GATES if modes.get(g) == "active"]
    if modes.get(GATE_SL_ATR) == "active" and atr is None:
        out.append(f"{GATE_ENTRY_QUALITY}.sl_atr")
    if price is None:
        # Not settings-moded: always on, so a missing price always leaves a real
        # rejection unjudged. (The off-market rejection is DECIDED on a missing price
        # rather than unassessed — absence of a tick is exactly its trigger.)
        out.append(GATE_THROUGH_STOP)
    return tuple(out)


def preview(  # noqa: C901 — a linear sequence of independent gates, mirroring
    # `trading._apply_eligibility_overlays` (which carries the same exemption for the same
    # reason): the correctness of this function depends on the gates being READABLE IN THE
    # SAME ORDER as the order path. Splitting them into helpers would hide that property.
    signal: Signal,
    *,
    modes: Mapping[str, str],
    atr: Decimal | None = None,
    market_price: Decimal | None = None,
    fill_price: Decimal | None = None,
    allow_offmarket: bool = True,
    max_chase_r: Decimal | None = None,
    rr_min: Decimal | None = None,
    min_scoring_factors: int,
    max_dominant_share: Decimal,
    min_sl_atr_mult: Decimal,
) -> EligibilityPreview:
    """The first ACTIVE gate that would reject `signal`, or a CLEAR verdict.

    Pure: `modes` and the thresholds are arguments (the `regime_guard`/`entry_quality`
    convention), so this cannot read a stale settings singleton and is trivially
    testable. `modes` must carry EVERY gate — covered ones are evaluated, uncovered
    ones are reported in `unassessed` when active.

    Every gate fails open exactly as it does on the order path: a signal that cannot be
    assessed is eligible on that dimension, never suppressed on uncertainty.
    """
    unassessed = _unassessed(modes, atr=atr, price=market_price)

    def verdict(gate: str, reason: str) -> EligibilityPreview:
        return EligibilityPreview(blocked=True, gate=gate, reason=reason, unassessed=unassessed)

    # 0. Off-market: the broker refuses to fill without a live tick unless the user has
    #    opted in. Checked FIRST among the broker's own rejections because it is the one
    #    that fires most — outside market hours it applies to every row.
    if market_price is None and not allow_offmarket:
        return verdict(GATE_OFFMARKET, OFFMARKET_REASON)

    # 1. Regime overlay — first on the order path, so first here.
    regime_reason = regime_guard.order_block_reason(signal, modes.get(GATE_REGIME, "off"))
    if regime_reason:
        return verdict(GATE_REGIME, regime_reason)

    # 2. Entry quality (diversity + sl_atr, independently moded). With atr=None the
    #    sl_atr check is "not assessable" and fails open — correct for the DIVERSITY
    #    verdict, and `unassessed` already records the gap when sl_atr is active.
    diversity_mode = modes.get(GATE_DIVERSITY, "off")
    sl_atr_mode = modes.get(GATE_SL_ATR, "off")
    if diversity_mode != "off" or sl_atr_mode != "off":
        eq = entry_quality.evaluate(
            entry=Decimal(str(signal.entry_price)),
            stop_loss=Decimal(str(signal.stop_loss)),
            factor_scores=signal.factor_scores,
            atr=atr,
            min_scoring_factors=min_scoring_factors,
            max_dominant_share=max_dominant_share,
            min_sl_atr_mult=min_sl_atr_mult,
        )
        eq_reason = entry_quality.order_block_reason(eq, diversity_mode, sl_atr_mode)
        if eq_reason:
            return verdict(GATE_ENTRY_QUALITY, eq_reason)

    # 3. Reward:risk floor — beside entry-quality on the order path (both judge the
    #    SIGNAL ITSELF), and decidable from the signal row alone.
    if modes.get(GATE_RR, "off") != "off":
        rr_verdict = rr_guard.evaluate(
            entry=Decimal(str(signal.entry_price)),
            stop_loss=Decimal(str(signal.stop_loss)),
            take_profit=Decimal(str(signal.take_profit)),
            rr_min=rr_min if rr_min is not None else Decimal("1.0"),
        )
        rr_reason = rr_guard.order_block_reason(rr_verdict, modes.get(GATE_RR, "off"))
        if rr_reason:
            return verdict(GATE_RR, rr_reason)

    # 4. Anti-chase (pure — needs only the live price the caller already fetched).
    if market_price is not None and modes.get(GATE_CHASE, "off") != "off":
        chase_verdict = chase_guard.evaluate(
            entry=Decimal(str(signal.entry_price)),
            stop_loss=Decimal(str(signal.stop_loss)),
            market_price=market_price,
            side=signal.direction,
            max_chase_r=max_chase_r if max_chase_r is not None else Decimal("0.33"),
        )
        chase_reason = chase_guard.order_block_reason(chase_verdict, modes.get(GATE_CHASE, "off"))
        if chase_reason:
            return verdict(GATE_CHASE, chase_reason)

    # 5. The paper broker's through-stop rejection. LAST, mirroring the order path: the
    #    settings-moded overlays all run before `place_paper_order` is called. Judged on
    #    the MODELLED FILL (the caller supplies it) — see `through_stop_reason`.
    judged_price = fill_price if fill_price is not None else market_price
    if judged_price is not None:
        ts_reason = through_stop_reason(
            side=signal.direction,
            price=judged_price,
            stop_loss=Decimal(str(signal.stop_loss)),
        )
        if ts_reason:
            return verdict(GATE_THROUGH_STOP, ts_reason)

    return EligibilityPreview(blocked=False, unassessed=unassessed)


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
    """Every gate's LIVE mode, keyed by this module's gate ids.

    Lives here so all consumers (signals list, signal detail, style suggestions) share
    ONE definition and `preview` is always handed the COMPLETE picture — a partial map
    was what made the `unassessed` tripwire imaginary (bug-hunter, 2026-09-02).

    This is the one function in the module that reads `settings`; `preview` itself stays
    pure (modes are arguments) so it cannot pick up a stale singleton and stays testable.
    """
    from app.core.config import settings

    return {
        GATE_REGIME: settings.regime_gate_mode,
        GATE_DIVERSITY: settings.entry_diversity_gate_mode,
        GATE_SL_ATR: settings.entry_sl_atr_gate_mode,
        GATE_CIRCUIT: settings.circuit_gate_mode,
        GATE_SECTOR_RS: settings.sector_rs_gate_mode,
        GATE_MARKET_REGIME: settings.market_regime_gate_mode,
        GATE_LIQUIDITY: settings.liquidity_gate_mode,
        GATE_CHASE: settings.chase_gate_mode,
        GATE_RR: settings.rr_gate_mode,
    }
