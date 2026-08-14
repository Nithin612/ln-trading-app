"""ADX trend-regime taxonomy — the single source of truth.

The regime buckets (and the standard Wilder thresholds behind them) are used in
two places that must never disagree: the entry-quality attribution / §8
walk-forward (measurement) and the live regime-eligibility overlay (the gate).
Both import from here so a label or threshold can only change in one place.

Regime is recovered from the frozen ADX factor's explanation
(app/analysis/indicators/adx.py, frozen). Two recoveries live here:

  - `regime_from_factor_scores` (committed signals, incl. the money-path gate)
    prefers the factor's DECISION BRANCH — the phrase it emits ("…trending…",
    "…weak trend…", "…moderate…") reflects the comparison it made on the
    FULL-PRECISION adx before the display rounds to 0.1. Matching the branch is
    strictly more faithful than re-bucketing the rounded number, which misreads a
    raw-choppy [19.95, 20) as 20.0→transitional and a raw-transitional [24.95, 25)
    as 25.0→trending. The numeric parse is the fallback.
  - `parse_adx_level` + `adx_regime` (the numeric path) buckets a RAW level and is
    used where the precise number is in hand — the corpus / §8 backtest, which
    computes ADX itself. Kept unchanged so the banked §8 evidence carries over.

Fail to None (→ "regime n/a") rather than misreport.
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


# The frozen ADX factor emits a distinct phrase per branch, decided on the
# full-precision adx (app/analysis/indicators/adx.py): ">25" → "…trending…",
# "<20" → "…weak trend…", else (the inclusive 20–25 band) → "…moderate…".
_BRANCH_TRENDING = "trending"
_BRANCH_CHOPPY = "weak trend"
_BRANCH_TRANSITIONAL = "moderate"


def regime_from_branch(explanation: object) -> str | None:
    """Regime from the frozen ADX factor's decision-branch phrase — full-precision
    (no 0.1-rounding edge), because the factor chose the branch before rounding the
    display. None when no branch phrase is present, so the caller can fall back to
    the numeric parse. (Checked trending → choppy → transitional; the phrases don't
    overlap — "weak trend" is not "trending", "moderate" is neither.)"""
    if not isinstance(explanation, str):
        return None
    if _BRANCH_TRENDING in explanation:
        return TRENDING
    if _BRANCH_CHOPPY in explanation:
        return CHOPPY
    if _BRANCH_TRANSITIONAL in explanation:
        return TRANSITIONAL
    return None


def regime_from_factor_scores(factor_scores: object) -> str:
    """Recover a committed signal's ADX regime from its stored `factor_scores`
    payload ({name: {weight, score, explanation}}). Fails open to 'regime n/a'
    when the ADX factor is unavailable.

    Prefers the factor's DECISION BRANCH over the 0.1-rounded number, which fixes
    the band-edge misbucket the numeric parse cannot: a raw-choppy [19.95, 20.0)
    signal prints "ADX=20.0 weak trend" — the branch reads CHOPPY (eligible),
    whereas re-bucketing the rounded 20.0 read TRANSITIONAL (wrongly suppressed in
    ACTIVE mode). The numeric parse remains the fallback for any non-standard
    explanation. This is the recovery the money-path gate reads (via regime_guard)
    and what is persisted to `signals.regime` at commit."""
    if not isinstance(factor_scores, dict):
        return NA
    adx = factor_scores.get("ADX")
    explanation = adx.get("explanation") if isinstance(adx, dict) else None
    return regime_from_branch(explanation) or adx_regime(parse_adx_level(explanation))
