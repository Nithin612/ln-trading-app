"""ADX trend-regime taxonomy — the single source of truth.

The regime buckets (and the standard Wilder thresholds behind them) are used in
two places that must never disagree: the entry-quality attribution / §8
walk-forward (measurement) and the live regime-eligibility overlay (the gate).
Both import from here so a label or threshold can only change in one place.

The ADX numeric level is recovered from the frozen ADX factor's explanation
string ("ADX=27.2 trending" — app/analysis/indicators/adx.py, frozen). The
score alone can't separate transitional from choppy (both score 0.0), so the
level is the only discriminator; the parse is reliable *because* that module is
frozen. Fail to None (→ "regime n/a") rather than misreport.
"""

from __future__ import annotations

import re

# Exact bucket labels. Downstream reports, tests, and the gate policy match on
# these strings — do not reword without updating every consumer.
CHOPPY = "choppy (ADX<20)"
TRANSITIONAL = "transitional (20–25)"
TRENDING = "trending (ADX≥25)"
NA = "regime n/a"

_ADX_RE = re.compile(r"\bADX=([0-9]+(?:\.[0-9]+)?)")


def parse_adx_level(explanation: object) -> float | None:
    """Best-effort raw ADX level from the ADX factor's explanation string.
    None when absent/unparseable (observability only; callers fail open)."""
    if not isinstance(explanation, str):
        return None
    m = _ADX_RE.search(explanation)
    return float(m.group(1)) if m else None


def adx_regime(adx_level: float | None) -> str:
    """Standard ADX regime thresholds: <20 choppy, [20, 25) transitional,
    ≥25 trending; None → 'regime n/a'.

    Boundary note: 25.0 is bucketed as TRENDING here, whereas the frozen ADX
    factor's prose (app/analysis/indicators/adx.py) labels 20–25 "moderate"
    inclusive of 25. This ≥25 boundary is deliberate and load-bearing: the 6.2
    attribution, the gate experiment and the §8 walk-forward all measured
    "transitional is net-negative" with exactly this split, so the live gate
    must skip the same band it validated. (Rounding at the band edges — the
    level is recovered from a 0.1-rounded string — is covered in
    `regime_from_factor_scores`.)"""
    if adx_level is None:
        return NA
    if adx_level < 20:
        return CHOPPY
    if adx_level < 25:
        return TRANSITIONAL
    return TRENDING


def regime_from_factor_scores(factor_scores: object) -> str:
    """Recover a committed signal's ADX regime from its stored `factor_scores`
    payload ({name: {weight, score, explanation}}). Fails open to 'regime n/a'
    when the ADX factor or its level is unavailable.

    Rounding caveat: the level comes from the factor's `f"ADX={x:.1f}"` prose, so
    a raw ADX within 0.05 of a band edge can land in the neighbouring bucket. At
    the 20 edge this is NOT fail-safe — a raw-choppy [19.95, 20.0) signal reads as
    20.0 → transitional, so in ACTIVE mode it would be wrongly suppressed
    (choppy is not in the skip-set). Harmless while the gate only measures
    (shadow), and removed once the active-flip precondition — a first-class ADX
    level on the signal (see regime_guard) — is met (quant-verifier + bug-hunter
    2026-08-13)."""
    if not isinstance(factor_scores, dict):
        return NA
    adx = factor_scores.get("ADX")
    explanation = adx.get("explanation") if isinstance(adx, dict) else None
    return adx_regime(parse_adx_level(explanation))
