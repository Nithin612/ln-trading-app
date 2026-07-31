"""Emergency-exit watcher — the downside twin of the profit-lock.

Pure, deterministic assessment of an OPEN position's health. It answers one
question: *is this trade structurally dead, and should it be cut?* It never
executes — the trail-SL and circuit breaker own real exits. This is advisory,
surfaced on the Positions page so a losing thesis gets cut on evidence instead
of hope. Born from the 2026-07-30/31 review, where week-old choppy swings that
never hit 1R bled out one small loss at a time.

No I/O, no clocks: price, levels, regime ER and `now` all enter as arguments,
so it is trivially testable and matches the frozen-engine discipline. Money
stays Decimal; only the dimensionless diagnostics (R-multiples, ratios, ER)
are floats.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum


class HealthVerdict(StrEnum):
    HOLD = "hold"    # nothing structurally wrong
    WATCH = "watch"  # one or more soft warnings — manage closely
    CUT = "cut"      # structurally dead — exit


# Reason codes (stable strings for the UI / logs).
THESIS_BREAK = "thesis_break"
TREND_DEAD = "trend_dead"
RR_INVERTED = "rr_inverted"
DEEP_MAE = "deep_mae"
STALE = "stale"


@dataclass(frozen=True)
class HealthReason:
    code: str
    severity: HealthVerdict  # WATCH or CUT
    detail: str


@dataclass(frozen=True)
class HealthParams:
    choppy_er: float = 0.30   # daily ER below this = trend dead (matches regime.CHOPPY_ER)
    rr_floor: float = 1.0     # remaining reward:risk below this = inverted
    deep_mae_r: float = 0.8   # drawdown ≥ this many R = deep adverse excursion


DEFAULT_PARAMS = HealthParams()


@dataclass(frozen=True)
class PositionHealth:
    verdict: HealthVerdict
    reasons: list[HealthReason]
    drawdown_r: float | None    # current adverse excursion in R (+ = underwater); None without SL
    rr_remaining: float | None  # remaining reward / remaining risk; None without SL+TP
    regime_er: float | None     # daily Kaufman ER passed through, for display


def _has(reasons: list[HealthReason], code: str) -> bool:
    return any(r.code == code for r in reasons)


def _verdict(reasons: list[HealthReason]) -> HealthVerdict:
    if any(r.severity is HealthVerdict.CUT for r in reasons):
        return HealthVerdict.CUT
    if reasons:
        return HealthVerdict.WATCH
    return HealthVerdict.HOLD


def assess_position_health(  # noqa: C901 — a flat list of independent checks, not deep nesting
    *,
    side: str,
    entry: Decimal,
    current_price: Decimal | None,
    stop_loss: Decimal | None,
    take_profit: Decimal | None,
    regime_er: float | None,
    validity_until: datetime | None,
    now: datetime,
    params: HealthParams = DEFAULT_PARAMS,
) -> PositionHealth:
    """Assess one open position. Soft conditions escalate to CUT only when the
    position is also underwater (`adverse`) — a green trade in chop is a hold,
    a red trade in dead chop is a cut."""
    is_long = side.upper() == "LONG"
    px = current_price
    reasons: list[HealthReason] = []
    drawdown_r: float | None = None
    rr_remaining: float | None = None

    adverse = px is not None and ((px < entry) if is_long else (px > entry))

    def soft_cut(condition_adverse: bool) -> HealthVerdict:
        return HealthVerdict.CUT if condition_adverse else HealthVerdict.WATCH

    # 1. Thesis break — price at/through the structural stop (hard invalidation).
    if px is not None and stop_loss is not None:
        broken = (px <= stop_loss) if is_long else (px >= stop_loss)
        if broken:
            reasons.append(
                HealthReason(
                    THESIS_BREAK,
                    HealthVerdict.CUT,
                    f"Price ₹{px} through stop ₹{stop_loss} — thesis invalidated.",
                )
            )

    # Risk unit R = |entry − SL|.
    risk_r: Decimal | None = None
    if stop_loss is not None:
        r = abs(entry - stop_loss)
        risk_r = r if r != 0 else None

    # 2. Deep MAE — how far underwater now, in R (proxy for max adverse excursion
    #    without replaying candles). Suppressed if the stop is already breached.
    if px is not None and risk_r is not None:
        adverse_amt = (entry - px) if is_long else (px - entry)
        drawdown_r = float(adverse_amt / risk_r)
        if drawdown_r >= params.deep_mae_r and not _has(reasons, THESIS_BREAK):
            reasons.append(
                HealthReason(
                    DEEP_MAE,
                    HealthVerdict.CUT,
                    f"Down {drawdown_r:.2f}R — deep in the red, at the doorstep of the stop.",
                )
            )

    # 3. Remaining reward:risk inversion — from HERE, is there more to lose than
    #    to gain? Only meaningful while both target and stop are still ahead, and
    #    only actionable when underwater: a green trade near its target just wants
    #    a trailed stop, not a cut.
    if px is not None and stop_loss is not None and take_profit is not None:
        reward_rem = (take_profit - px) if is_long else (px - take_profit)
        risk_rem = (px - stop_loss) if is_long else (stop_loss - px)
        if reward_rem > 0 and risk_rem > 0:
            rr_remaining = float(reward_rem / risk_rem)
            if adverse and rr_remaining < params.rr_floor:
                reasons.append(
                    HealthReason(
                        RR_INVERTED,
                        HealthVerdict.CUT,
                        f"Remaining reward:risk {rr_remaining:.2f} — "
                        "risking more than it can still make.",
                    )
                )

    # 4. Trend death — the regime that justified the entry is gone.
    if regime_er is not None and regime_er < params.choppy_er:
        reasons.append(
            HealthReason(
                TREND_DEAD,
                soft_cut(adverse),
                f"Daily trend efficiency {regime_er:.2f} — choppy, the move has stalled.",
            )
        )

    # 5. Stale — held past the signal's validity window with no payoff.
    #    Storage is UTC; coerce a naive input rather than raise on a tz mismatch,
    #    so a mis-fed caller degrades gracefully instead of 500-ing the list.
    if validity_until is not None:
        if validity_until.tzinfo is None:
            validity_until = validity_until.replace(tzinfo=UTC)
        now = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    if validity_until is not None and now >= validity_until:
        reasons.append(
            HealthReason(
                STALE,
                soft_cut(adverse),
                "Held past the signal's validity window — the setup has expired.",
            )
        )

    return PositionHealth(
        verdict=_verdict(reasons),
        reasons=reasons,
        drawdown_r=drawdown_r,
        rr_remaining=rr_remaining,
        regime_er=regime_er,
    )
