"""Degenerate-ratio hygiene — H6.

A ratio whose denominator goes to zero has exactly three honest outcomes, and the
codebase used to conflate all three:

  UNDEFINED   the denominator is zero — there is no ratio. The answer is ``None``,
              never ``0.0``. Returning zero for "undefined" is how a zero-risk
              signal came to read as *the worst possible reward:risk* rather than
              *not assessable*, and how a bookless stock reads as a perfectly
              tight spread.
  OFF-SCALE   the denominator is tiny but real, so the ratio is finite and
              enormous. `RR ≈ 228` is on record. Reporting it as-is lets one row
              dominate a mean, win a sort, or overflow a Numeric column;
              silently truncating it to the cap is worse, because it then reads
              as a real 50:1 setup. So it is clamped AND marked.
  NORMAL      the number.

⚠ **THE RULE: clamp what you REPORT, never what you DECIDE.** A gate's verdict is
computed from the raw ratio; only the value it stamps or prints is clamped. Every
cap here is set above any threshold that reads it, so the two cannot disagree —
but the ordering matters and is pinned by test.

**Why the caps are these numbers.** Measured on the real book, 2026-09-05, all 656
signals carrying levels: planned R:R p50 **1.97**, p90 **3.67**, p99 **28.5**, max
**228.06**, and **exactly one row (0.15%) exceeds 50** — the known tiny-SL artifact,
whose stop is 2.6 bps of its own price. So `MAX_RR = 50` sits above the 99th
percentile of genuine signals and below the artifact: it touches the artifacts and
nothing else. It is a reporting bound chosen from the distribution, not a claim
that a 60:1 setup is impossible.

`MAX_R` is a different kind of number — a *representability* bound taken from the
`Numeric(7,3)` columns that store excursion R (`signal_excursions`, `pair_outcome`),
where exceeding it aborts a batch commit. `WINSOR_R` is different again: a
*statistical* winsor applied when averaging R into an expectancy, so one tail trade
cannot carry the mean. Three jobs, three constants, defined once here — they were
previously four literals in four modules, two of them silently disagreeing by 1000×.
"""

from __future__ import annotations

from decimal import Decimal

# Planned/realised reward:risk. Reporting bound — see the module docstring for the
# distribution it was read off. Above every rr threshold in the codebase
# (`rr_guard.rr_min` 1.0, `position_health.rr_floor` 1.0), so clamping can never
# flip a verdict.
MAX_RR: Decimal = Decimal("50")

# Excursion R (move ÷ risk). A COLUMN bound, not a domain one: mfe_r/mae_r persist
# as Numeric(7,3), and an overflow aborts the batch commit rather than storing a
# wrong number.
MAX_R: Decimal = Decimal("9999.999")

# The statistical winsor used when R is AVERAGED into an expectancy. Not a cap on
# what may be reported — a bound on what one trade may contribute to a mean.
WINSOR_R: float = 10.0


def safe_ratio(
    numerator: Decimal | None,
    denominator: Decimal | None,
    *,
    cap: Decimal | None = None,
) -> Decimal | None:
    """``numerator / denominator``, or ``None`` when it is undefined.

    ``None`` for a zero, negative-zero, or absent denominator — the caller must
    distinguish "no ratio" from "a ratio of zero", and a value sentinel makes that
    impossible. With ``cap``, the magnitude is clamped to ±cap; the sign is kept, so
    a clamped negative stays negative. Never returns a non-finite value: Decimal
    division by zero raises rather than yielding ``inf``, and that path is taken
    before the division.
    """
    if numerator is None or denominator is None or denominator == 0:
        return None
    value = numerator / denominator
    return clamp_ratio(value, cap) if cap is not None else value


def safe_ratio_f(
    numerator: float | None,
    denominator: float | None,
    *,
    cap: float | None = None,
) -> float | None:
    """Float twin of `safe_ratio`, for the indicator/statistics paths where a ratio
    is already a float. Same contract: ``None`` is undefined, never zero."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    value = numerator / denominator
    return clamp_ratio_f(value, cap) if cap is not None else value


def clamp_ratio(value: Decimal, cap: Decimal | None) -> Decimal:
    """Clamp an already-computed ratio to ±cap, sign preserved."""
    if cap is None:
        return value
    if value > cap:
        return cap
    return -cap if value < -cap else value


def clamp_ratio_f(value: float, cap: float | None) -> float:
    if cap is None:
        return value
    return max(-cap, min(cap, value))


def is_capped(value: Decimal | float | None, cap: Decimal | float | None) -> bool:
    """Did this value land ON the cap — i.e. is it an artifact rather than a
    measurement? Callers render `>cap` rather than the number itself, so nothing
    downstream mistakes a truncated 228 for a real 50."""
    if value is None or cap is None:
        return False
    return abs(Decimal(str(value))) >= Decimal(str(cap))


def format_ratio(
    value: Decimal | float | None,
    *,
    cap: Decimal | float | None = None,
    places: int = 2,
    undefined: str = "—",
) -> str:
    """Render a ratio honestly: ``—`` when undefined, ``>50`` when it hit the cap,
    the number otherwise. The three cases must stay visually distinct — that is the
    whole point of H6."""
    if value is None:
        return undefined
    if cap is not None and is_capped(value, cap):
        sign = "-" if Decimal(str(value)) < 0 else ""
        return f"{sign}>{_trim(Decimal(str(cap)))}"
    return f"{Decimal(str(value)):.{places}f}"


def _trim(cap: Decimal) -> str:
    """`50` not `50.00`, `9999.999` unchanged — the cap reads as a bound, not a
    measurement."""
    normalized = cap.normalize()
    return f"{normalized:f}"
