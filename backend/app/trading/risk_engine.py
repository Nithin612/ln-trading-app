"""Phase 7.1 — the RiskEngine: ONE pre-trade gate, composed from the rules that exist.

Before this module the risk rules were scattered across three files and two call sites:

    api/v1/trading.py     check_circuit_breaker → signal status → restrictions.check()
    broker/paper_broker.py  offmarket → through-stop → size → _check_notional_cap
    (nowhere)               the portfolio heat cap

Scatter is not merely untidy here. `place_order` is not the only way an order can be
born — the position monitor closes positions, and Phase 7 will add a broker adapter and
a repair queue — so "the rules" being a sequence typed out at one call site means every
new caller re-derives them, and the ones it forgets are the ones that never fire.

**This module composes; it does not reimplement.** Each rule keeps exactly one
definition and this is the place that knows their ORDER. `restrictions.py` (A38) stays
the single declaration of the eligibility gates and is walked, not copied — adding a
second sequence is precisely what W2 forbids and what the display/order drift of
2026-09-02 cost us.

**Two phases, and that is honest rather than convenient.** The plan says "one pre-trade
gate", but two rules cannot run pre-trade:

    check_pre_trade()  needs only the signal        → breaker, status, eligibility
    check_sizing()     needs `qty` AND `fill_price` → notional cap, heat cap

`qty` does not exist until the fill price is resolved, and after A37 the fill price
itself depends on `qty` (the participation term is quadratic, so `q → size(fill(q))`
has no fixed point). Pretending it is one call would mean either sizing before the
gates — which prices a trade we may refuse — or checking the caps against a price the
trade will not get. The split is the shape of the problem, not a compromise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.core.config import get_settings
from app.models.signal import Signal
from app.models.trading import Position
from app.models.user import User
from app.trading.circuit_breaker import check_circuit_breaker

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.ext.asyncio import AsyncSession

# Rule names. These are the vocabulary the audit trail and the daily report speak, so
# they are declared once here and never spelled inline — the T7 lesson, where the gate
# mode `Literal` was written out NINE times and tied together nowhere.
RULE_BREAKER = "circuit_breaker"
RULE_SIGNAL_MISSING = "signal_missing"
RULE_SIGNAL_STATUS = "signal_status"
RULE_ELIGIBILITY = "eligibility"
RULE_NOTIONAL_CAP = "notional_cap"
RULE_HEAT_CAP = "heat_cap"

PRE_TRADE_RULES: tuple[str, ...] = (
    RULE_BREAKER,
    RULE_SIGNAL_MISSING,
    RULE_SIGNAL_STATUS,
    RULE_ELIGIBILITY,
)
SIZING_RULES: tuple[str, ...] = (RULE_NOTIONAL_CAP, RULE_HEAT_CAP)
ALL_RULES: tuple[str, ...] = PRE_TRADE_RULES + SIZING_RULES


@dataclass(frozen=True)
class RiskVerdict:
    """The outcome of a risk phase.

    `allowed=False` carries BOTH the rule that refused and its reason, because the two
    answer different questions: the rule is what a report groups by, the reason is what
    a human reads. Collapsing them into one string — which is what raising an exception
    did — makes the first question unanswerable without parsing prose.
    """

    allowed: bool
    rule: str | None = None
    reason: str | None = None
    # Restriction verdicts to persist on the order (shadow + active; `off` stamps
    # nothing). Passed through verbatim from the A38 registry.
    stamps: dict[str, object] = field(default_factory=dict)
    # ACTIVE gates that could not be judged for want of context (e.g. no ATR history).
    # Named, never silently treated as clear — "unknown" and "verified clear" must stay
    # distinguishable.
    unassessed: tuple[str, ...] = ()

    @property
    def denied(self) -> bool:
        return not self.allowed


ALLOWED = RiskVerdict(allowed=True)


def _deny(rule: str, reason: str) -> RiskVerdict:
    return RiskVerdict(allowed=False, rule=rule, reason=reason)


# ──────────────────────────────────────────────────────────────────────────────
# Rule: per-position notional cap
# ──────────────────────────────────────────────────────────────────────────────


def notional_cap_reason(
    user: User,
    *,
    qty: int,
    fill_price: Decimal,
    existing_qty: int,
    existing_entry: Decimal | None,
) -> str | None:
    """Why this size breaches the per-position notional cap, or `None` if it does not.

    `qty = risk_budget / risk_per_share` bounds the trade's RISK but says nothing about
    its SIZE: a stop a few paise wide sized 50,000 shares = ₹1,18,65,000 on ₹1,00,000 of
    capital (found 2026-09-02) — 119× the account — and that row then polluted the paper
    book, the R statistics and the 30-day clock. NSE cash delivery grants no leverage, so
    the default cap is capital × 1.0.

    Includes any existing position in the same name, so a repeat entry cannot stack past
    the cap. **Reject, never clamp** — a clamped size silently changes the trade's risk,
    the one thing sizing exists to hold fixed.

    Extracted here from `paper_broker._check_notional_cap`, which now calls it. One
    definition, two callers (the broker raises, the RiskEngine returns a verdict).
    """
    settings = get_settings()
    cap = user.capital_inr * Decimal(str(settings.paper_max_notional_leverage))
    if cap <= 0:
        return None
    held = (
        Decimal(existing_qty) * existing_entry
        if existing_qty > 0 and existing_entry is not None
        else Decimal(0)
    )
    wanted = Decimal(qty) * fill_price
    if held + wanted <= cap:
        return None
    return (
        f"Position size {qty} × ₹{fill_price} = ₹{wanted:,.0f} exceeds your "
        f"₹{cap:,.0f} per-position cap (capital ₹{user.capital_inr:,.0f} × "
        f"{settings.paper_max_notional_leverage})"
        + (f", with ₹{held:,.0f} already held" if held else "")
        + ". The stop is so tight that risk-first sizing asks for more stock than the "
        "account can hold — wait for a setup with a sane stop."
    )


# ──────────────────────────────────────────────────────────────────────────────
# Rule: portfolio heat cap
# ──────────────────────────────────────────────────────────────────────────────


def admission_risk(side: str, entry: Decimal, stop: Decimal, qty: int) -> Decimal:
    """Clamped, direction-aware admission risk — the heat primitive.

    Clamped at zero because a stop at or past entry exposes nothing and must not hold
    budget. Deliberately identical to `heat_counterfactual._risk`, which is re-exported
    from there rather than re-derived: the counterfactual's numbers and the cap's must
    mean the same thing, or the cap cannot be argued from the counterfactual that
    justified it.
    """
    per_share = (entry - stop) if side.upper() == "LONG" else (stop - entry)
    return Decimal(qty) * max(Decimal(0), per_share)


@dataclass(frozen=True)
class OpenHeat:
    """Portfolio heat currently held, and what could not be measured."""

    total: Decimal
    positions: int
    # Open positions with NO recoverable commit stop. These are why the cap fails
    # CLOSED: unmeasured risk is still risk, and a cap that ignores it is not a cap.
    unmeasurable: int


async def open_heat(db: AsyncSession, user: User, *, mode: str = "paper") -> OpenHeat:
    """Sum admission risk across the user's OPEN positions.

    Risk comes from the **commit** stop (`Signal.stop_loss`), never the trailed
    `current_sl`: a trailed stop leaks price action the admission decision could not
    have seen, so a book would silently gain budget merely because trades moved in its
    favour. `current_sl` is the fallback only when the signal is gone (SET NULL on
    delete), which is strictly better than dropping the leg.

    Initial risk, NOT mark-to-market — a from-the-mark definition *loosens* as the book
    deteriorates, which is perverse for a risk cap.
    """
    rows = (
        await db.execute(
            select(Position, Signal.stop_loss)
            .outerjoin(Signal, Signal.id == Position.signal_id)
            .where(
                Position.user_id == user.id,
                Position.mode == mode,
                Position.closed_at.is_(None),
            )
        )
    ).all()

    total = Decimal(0)
    unmeasurable = 0
    for pos, commit_sl in rows:
        stop = commit_sl if commit_sl is not None else pos.current_sl
        if stop is None:
            unmeasurable += 1
            continue
        total += admission_risk(
            pos.side, Decimal(str(pos.avg_entry_price)), Decimal(str(stop)), pos.quantity
        )
    return OpenHeat(total=total, positions=len(rows), unmeasurable=unmeasurable)


def heat_cap_reason(
    user: User,
    *,
    held: OpenHeat,
    incoming_risk: Decimal,
) -> str | None:
    """Why admitting `incoming_risk` breaches the portfolio heat cap, or `None`.

    ⚠ **It fails CLOSED** — a deliberate departure from the six selection overlays. For
    a selection gate the error to avoid is suppressing a good trade on uncertainty; for
    a risk rail it is *taking risk you cannot measure*. Same logic as the
    non-disableable daily-loss breaker. So an open position whose risk cannot be
    computed refuses the next entry rather than being counted as zero.

    ⚠ The denominator is `capital_inr`, the LIVE figure — never
    `paper_sampling_capital_inr`, which is declared reporting-only and must never touch
    sizing or admission. The two differ 5×, so misapplying it would silently quintuple
    the cap.
    """
    settings = get_settings()
    pct = Decimal(str(settings.heat_cap_pct))
    if pct <= 0:
        return None
    cap = (user.capital_inr * pct / Decimal(100)).quantize(Decimal("0.01"))

    if held.unmeasurable:
        return (
            f"Portfolio heat cannot be measured: {held.unmeasurable} open position(s) "
            "have no recoverable commit stop, so the risk already carried is unknown. "
            "The heat cap fails CLOSED — a risk rail may not admit risk it cannot "
            "count. Close or re-stop those positions."
        )

    if held.total + incoming_risk <= cap:
        return None
    return (
        f"Portfolio heat ₹{held.total:,.0f} + ₹{incoming_risk:,.0f} this trade = "
        f"₹{held.total + incoming_risk:,.0f} exceeds your ₹{cap:,.0f} cap "
        f"({pct}% of ₹{user.capital_inr:,.0f}) across {held.positions} open position(s). "
        "Close something, or wait for one to resolve."
    )


# ──────────────────────────────────────────────────────────────────────────────
# The phases
# ──────────────────────────────────────────────────────────────────────────────


async def check_pre_trade(
    db: AsyncSession,
    user: User,
    signal: Signal | None,
    *,
    side: str,
    allow_offmarket: bool,
) -> RiskVerdict:
    """Rules that need only the signal: breaker → exists → status → eligibility.

    **Order is preserved exactly** from the pre-7.1 `place_order`, and equivalence is
    pinned by test. The breaker runs first on purpose: it is the account-level rail, and
    when it has tripped nothing else about this particular signal matters.

    ⚠ `signal` is deliberately `Signal | None` and "does it exist" is a RULE rather
    than a caller-side 404. Today the breaker runs *before* the signal is looked up, so
    a request carrying an unknown id while the breaker is tripped answers 409, not 404.
    Hoisting the lookup into the caller to get a non-optional argument would silently
    invert that pair — a real, observable change, and exactly the kind an "equivalent"
    refactor is supposed to not make. The caller maps this rule to 404 and the rest to
    409, so the HTTP surface is unchanged.
    """
    # 1. Daily-loss circuit breaker. NEVER disableable — not for tests, not on request.
    triggered, reason = await check_circuit_breaker(db, user)
    if triggered:
        return _deny(RULE_BREAKER, reason)

    # 2. Existence, then lifecycle. The order path admits `active` only, which is also
    #    what keeps the intraday SHADOW profiles untradeable.
    if signal is None:
        return _deny(RULE_SIGNAL_MISSING, "Signal not found")
    if signal.status not in ("active",):
        return _deny(RULE_SIGNAL_STATUS, f"Signal is {signal.status}, not active")

    # 3. Eligibility overlays — walked from the A38 registry, never re-listed here.
    #    OVERLAY only: the paper broker enforces its own unconditional pre-fill
    #    rejections (offmarket, through-stop) downstream, and running them here too
    #    would double-reject.
    from app.signals import restrictions
    from app.signals.restriction_context import load_restriction_context

    cfg = restrictions.config_from_settings()
    ctx = await load_restriction_context(
        db, signal, side, cfg, allow_offmarket=allow_offmarket
    )
    outcome = restrictions.check(ctx, cfg, enforced_by=restrictions.EnforcedBy.OVERLAY)
    if outcome.blocked:
        return RiskVerdict(
            allowed=False,
            rule=RULE_ELIGIBILITY,
            reason=outcome.reason,
            stamps=outcome.stamps(),
            unassessed=tuple(outcome.unassessed),
        )
    return RiskVerdict(
        allowed=True, stamps=outcome.stamps(), unassessed=tuple(outcome.unassessed)
    )


async def check_sizing(
    db: AsyncSession,
    user: User,
    *,
    side: str,
    qty: int,
    fill_price: Decimal,
    stop_loss: Decimal,
    existing_qty: int = 0,
    existing_entry: Decimal | None = None,
) -> RiskVerdict:
    """Rules that need a size: notional cap → heat cap.

    `side` is the POSITION side (LONG/SHORT), matching `admission_risk`.

    The heat cap is moded and defaults **off**, so this is byte-for-byte the previous
    behaviour until someone turns it on. That default is not timidity: a 6% cap cuts
    cycle-1 entries by ~74%, and cycle 1 exists to accrue evidence volume. It flips to
    enforce at the cycle-2 reset, not before.
    """
    reason = notional_cap_reason(
        user,
        qty=qty,
        fill_price=fill_price,
        existing_qty=existing_qty,
        existing_entry=existing_entry,
    )
    if reason is not None:
        return _deny(RULE_NOTIONAL_CAP, reason)

    mode = get_settings().heat_cap_mode
    # `"off"` is a TRUTHY string — never `mode or other`. That exact bug silently
    # stopped the entry_quality stamp being written (2026-09-05).
    if mode == "off":
        return ALLOWED

    held = await open_heat(db, user)
    incoming = admission_risk(side, fill_price, stop_loss, qty)
    reason = heat_cap_reason(user, held=held, incoming_risk=incoming)
    if reason is None:
        return ALLOWED
    if mode == "shadow":
        # Measure-only: the verdict is stamped for the sidecar, nothing is suppressed.
        return RiskVerdict(
            allowed=True,
            stamps={
                "heat_cap": {
                    "mode": "shadow",
                    "would_block": True,
                    "reason": reason,
                    "held_inr": str(held.total),
                    "incoming_inr": str(incoming),
                    "open_positions": held.positions,
                }
            },
        )
    return _deny(RULE_HEAT_CAP, reason)
