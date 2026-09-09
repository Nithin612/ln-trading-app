"""Reporting-only reconstruction of a committed signal's confluence arithmetic (U10/U15/U17).

READ-ONLY. This reproduces the **frozen** confluence formula
(`app/analysis/confluence.score_from_factors`, lines 159-166) from a signal's *stored*
`factor_scores`, so the signal-detail view can show HOW a confidence was built:

    numerator   = Σ weight·score   over ALL factors
    denominator = Σ weight          over factors whose score ≠ 0   ← abstainers DROP OUT
    normalized  = numerator / denominator
    confidence  = int(|normalized| · 100)                          (truncation, matches int())

The load-bearing surface this exposes is the divisor: a factor that abstains (score == 0)
does not dilute the score, it is *removed* from the denominator — which is exactly how SRTL
entered on a single 0.8 factor that normalised to 80% and cleared the ≥70% gate. Rendering the
division makes that visible at the point of decision instead of only in the post-mortem.

This module is NOT the engine. It never scores, sizes, gates, or writes; it reads a payload the
engine already committed. The engine remains the authority — the stored `confidence_pct` is the
headline number; this reconstructs the derivation and is unit-pinned to reproduce it exactly on
clean inputs. VOLUME's §3 direction-match adjustment is already baked into the stored score
(confluence.py:157 stores the adjusted factor list), so reconstructing from stored scores needs
no re-application of it.

Fails open: any malformed `factor_scores` payload yields `None` (the detail view then simply
omits the breakdown), never an exception — the detail endpoint is a fail-open read path
(one bad row must degrade to "unknown", not a 500; see api/v1/signals `_enrich_page`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class FactorContribution:
    """One factor that scored (score ≠ 0) — it is in the divisor and moves the number."""

    name: str
    weight: float
    score: float
    contribution: float  # weight × score (signed: BUY positive, SELL negative)
    explanation: str


@dataclass(frozen=True)
class FactorAbstention:
    """One factor that abstained (score == 0) — present at evaluation but OUT of the divisor."""

    name: str
    weight: float
    explanation: str


@dataclass(frozen=True)
class ConfidenceBreakdown:
    """The confluence arithmetic reconstructed from stored `factor_scores`."""

    numerator: float      # Σ weight·score over ALL factors
    denominator: float    # Σ weight over scoring factors (score ≠ 0)
    normalized: float     # numerator / denominator ∈ [-1, 1]
    confidence_pct: int   # int(|normalized|·100) — reproduces the stored value on clean inputs
    direction: str        # "BUY" if normalized > 0 else "SELL"
    scoring: list[FactorContribution]    # |contribution| desc — the dominant factor first
    abstained: list[FactorAbstention]    # weight desc


def explain(factor_scores: object) -> ConfidenceBreakdown | None:
    """Reconstruct the confluence arithmetic from a signal's stored `factor_scores`.

    `factor_scores` is the JSONB `{NAME: {weight, score, explanation}}` written at mint. Returns
    a `ConfidenceBreakdown`, or `None` when the payload is missing/malformed or no factor scored
    (a degenerate divisor — which the frozen engine itself treats as "no signal"). Never raises.
    """
    if not isinstance(factor_scores, dict) or not factor_scores:
        return None

    # Parse once, in the stored dict's iteration order — which is the order the engine evaluated
    # the factors (signal_service persists `for f in result.factors`), so summing in this order
    # reproduces the frozen sums bit-for-bit (see below).
    parsed: list[tuple[str, float, float, str]] = []
    try:
        for name, fs in factor_scores.items():
            if not isinstance(fs, dict):
                return None
            weight = float(fs["weight"])
            score = float(fs["score"])
            explanation = str(fs.get("explanation", ""))
            if not (math.isfinite(weight) and math.isfinite(score)):
                # Fail open on a non-finite stored score. Not reachable via the real data path
                # (Postgres JSONB rejects NaN/Infinity on insert), but the "never raises" contract
                # must hold before the int() below (quant-verifier, 2026-09-09).
                return None
            parsed.append((str(name), weight, score, explanation))
    except (KeyError, TypeError, ValueError):
        # Fail open — a malformed factor payload omits the breakdown, never 500s the endpoint.
        return None

    # Sum with the SAME builtin `sum()` the frozen scorer uses (confluence.py:159-160), over the
    # SAME factor order. Python 3.12's `sum()` applies compensated (Neumaier) summation; a naive
    # `+=` fold does NOT, and the resulting ~1e-14 disagreement can flip the int()-truncated
    # confidence by 1 (and direction at an exact-zero crossing) — a reconstruction that then
    # contradicts the authoritative stored headline. This makes it bit-identical on clean inputs
    # (quant-verifier verified 0 mismatches across a 1500-signal sweep after this change).
    numerator = sum(w * s for _, w, s, _ in parsed)
    # The frozen divisor rule (confluence.py:160): only non-zero-score factors count (SRTL surface).
    denominator = sum(w for _, w, s, _ in parsed if s != 0.0)

    if denominator == 0.0:
        return None

    normalized = numerator / denominator
    confidence_pct = int(abs(normalized) * 100)  # truncation — matches confluence.py:166
    direction = "BUY" if normalized > 0 else "SELL"

    scoring = [
        FactorContribution(name=n, weight=w, score=s, contribution=w * s, explanation=e)
        for n, w, s, e in parsed
        if s != 0.0
    ]
    abstained = [
        FactorAbstention(name=n, weight=w, explanation=e)
        for n, w, s, e in parsed
        if s == 0.0
    ]
    scoring.sort(key=lambda c: abs(c.contribution), reverse=True)
    abstained.sort(key=lambda a: a.weight, reverse=True)

    return ConfidenceBreakdown(
        numerator=numerator,
        denominator=denominator,
        normalized=normalized,
        confidence_pct=confidence_pct,
        direction=direction,
        scoring=scoring,
        abstained=abstained,
    )
