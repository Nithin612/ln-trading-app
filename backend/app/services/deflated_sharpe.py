"""Deflated Sharpe Ratio + Minimum Track Record Length — the multiple-testing bar.

## Why this exists

Two gates were promoted on favourable-looking evidence in one week and both had to be
reverted (regime: 44 observations vs 88; R:R: an unchecked "identity" premise). The
missing instrument in both cases was a bar that accounts for **how many things we have
tried**. Search enough variants and the best one looks good by luck alone — Aronson's
data-mining bias, formalised by Bailey & López de Prado as the Deflated Sharpe Ratio.

The construction (all stdlib — `statistics.NormalDist` gives the normal CDF and its
inverse, so no new dependency):

  1. **PSR** — the Probabilistic Sharpe Ratio. The probability that the TRUE Sharpe
     exceeds a benchmark, given the observed Sharpe, the sample length, and the return
     distribution's skew and kurtosis. Fat left tails and negative skew make an observed
     Sharpe less trustworthy, and PSR prices that in — which matters here, because our
     return distribution is exactly that shape (one trade was 94% of a cohort's loss).

  2. **E[max SR]** — the Sharpe you would expect from the BEST of N independent trials
     even with zero skill. Grows with N. This is the benchmark a candidate must beat, not
     zero.

  3. **DSR** = PSR evaluated against E[max SR]. "Given that we tried N things, what is the
     probability this one is genuinely better than luck?"

  4. **MinTRL** — the sample size at which a candidate COULD reach the confidence bar if
     its current statistics persisted. This is the most useful output for this project: it
     turns "keep accruing" into "keep accruing until n ≈ X", which is exactly what the
     review calendar needs.

## First read on the live book (2026-09-03) — every gate fails, and one way

| gate (eligible set = the book a flip leaves you holding) | n | Sharpe | 20-trial bar | DSR |
|---|--:|--:|--:|--:|
| market-regime | 33 | −0.004 | +0.331 | 2.9% |
| anti-chase    | 51 | +0.032 | +0.266 | 4.9% |
| sector-RS     | 59 | −0.105 | +0.247 | 0.3% |
| liquidity     | 72 | −0.150 | +0.224 | 0.1% |

**Not one candidate's Sharpe even EXCEEDS its benchmark**, so `min_trl` is `None` for all
four: more data cannot rescue them, because they are not ahead to begin with. The bar is
95%; the best result is 4.9%. That is the quantitative form of a conclusion the ₹ figures
had only hinted at — **no gate currently on the board is promotable, and the constraint is
not sample size.** The book a flip would leave you holding has a Sharpe of roughly zero
either way; the leak is upstream of gating.

## Honest limits

- MinTRL assumes the observed mean/vol/skew/kurtosis persist. It is a planning number, not
  a promise, and it moves as data arrives.
- DSR treats the N trials as independent. Ours are correlated (the same book, overlapping
  cohorts), so the true deflation is *worse* than this reports — the number is optimistic,
  not conservative. Say so wherever it is shown.
- With trade counts in the tens, expect DSR to be far below any sensible bar for
  everything. **That is the correct answer, not a defect** — it is the quantitative form of
  "we do not have the evidence yet."
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import NormalDist

_N = NormalDist()
_EULER = 0.5772156649015329
#: Confidence a candidate must reach to clear the bar.
DEFAULT_CONFIDENCE = 0.95
#: Trials attempted so far on this book — gates × modes × threshold variants. Deliberately
#: a documented constant rather than a guess: bump it when a new variant is tested, and
#: never lower it. As of 2026-09-03: 8 eligibility gates, plus threshold variants for
#: sl_atr / chase / liquidity / R:R / market-regime, plus 4 exit policies and 2 breakeven
#: rungs ≈ 20.
DEFAULT_TRIALS = 20


@dataclass(frozen=True)
class Moments:
    n: int
    mean: float
    stdev: float
    skew: float
    kurtosis: float  # Pearson (normal = 3.0), not excess
    sharpe: float


@dataclass(frozen=True)
class DsrResult:
    moments: Moments
    trials: int
    benchmark_sharpe: float   # E[max SR] under the null for `trials`
    psr_vs_zero: float        # P(true SR > 0)
    dsr: float                # P(true SR > benchmark) — the deflated number
    confidence: float
    passes: bool
    min_trl: float | None     # observations needed to reach `confidence`; None if hopeless
    note: str


def moments(returns: Sequence[float]) -> Moments | None:
    """Sample moments and the per-observation Sharpe. None when n < 3 or vol is zero."""
    n = len(returns)
    if n < 3:
        return None
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / (n - 1)
    sd = math.sqrt(var)
    if sd <= 0:
        return None
    m3 = sum((r - mean) ** 3 for r in returns) / n
    m4 = sum((r - mean) ** 4 for r in returns) / n
    pop_sd = math.sqrt(sum((r - mean) ** 2 for r in returns) / n)
    skew = m3 / pop_sd**3 if pop_sd > 0 else 0.0
    kurt = m4 / pop_sd**4 if pop_sd > 0 else 3.0
    return Moments(n=n, mean=mean, stdev=sd, skew=skew, kurtosis=kurt, sharpe=mean / sd)


def psr(m: Moments, benchmark_sharpe: float = 0.0) -> float:
    """P(true Sharpe > benchmark), adjusted for sample length, skew and kurtosis.

    Bailey & López de Prado: Z[ (SR − SR*)·√(T−1) / √(1 − γ₃·SR + ((γ₄−1)/4)·SR²) ].
    Negative skew and fat tails inflate the denominator, so the same observed Sharpe buys
    less confidence — which is the whole point for a return series whose losses cluster in
    a few large trades."""
    sr = m.sharpe
    denom_sq = 1.0 - m.skew * sr + ((m.kurtosis - 1.0) / 4.0) * sr**2
    if denom_sq <= 0 or m.n < 2:
        return float("nan")
    z = (sr - benchmark_sharpe) * math.sqrt(m.n - 1) / math.sqrt(denom_sq)
    return _N.cdf(z)


def expected_max_sharpe(trials: int, trial_stdev: float) -> float:
    """E[max SR] across `trials` independent zero-skill trials whose Sharpes have this
    dispersion. The bar a candidate must clear instead of zero."""
    if trials < 2 or trial_stdev <= 0:
        return 0.0
    a = _N.inv_cdf(1.0 - 1.0 / trials)
    b = _N.inv_cdf(1.0 - 1.0 / (trials * math.e))
    return trial_stdev * ((1.0 - _EULER) * a + _EULER * b)


def min_track_record_length(
    m: Moments, benchmark_sharpe: float, confidence: float = DEFAULT_CONFIDENCE
) -> float | None:
    """Observations needed for PSR to reach `confidence`, if today's moments persisted.

    None when the observed Sharpe does not exceed the benchmark at all — no amount of
    additional data rescues a candidate that is not ahead to begin with."""
    sr = m.sharpe
    if sr <= benchmark_sharpe:
        return None
    denom_sq = 1.0 - m.skew * sr + ((m.kurtosis - 1.0) / 4.0) * sr**2
    if denom_sq <= 0:
        return None
    z = _N.inv_cdf(confidence)
    return 1.0 + denom_sq * (z / (sr - benchmark_sharpe)) ** 2


def deflated_sharpe(
    returns: Sequence[float],
    *,
    trials: int = DEFAULT_TRIALS,
    trial_stdev: float | None = None,
    confidence: float = DEFAULT_CONFIDENCE,
) -> DsrResult | None:
    """The full bar for one candidate. None when the sample cannot support the maths.

    `trial_stdev` is the dispersion of Sharpes across the things we tried. Absent a
    measured value it defaults to the candidate's own sampling error (1/√n) — a deliberately
    CONSERVATIVE stand-in, since under the null the trial Sharpes scatter at roughly that
    scale."""
    m = moments(returns)
    if m is None:
        return None
    sd = trial_stdev if trial_stdev is not None else 1.0 / math.sqrt(m.n)
    bench = expected_max_sharpe(trials, sd)
    d = psr(m, bench)
    p0 = psr(m, 0.0)
    trl = min_track_record_length(m, bench, confidence)
    passes = (not math.isnan(d)) and d >= confidence
    if passes:
        note = f"clears the bar: DSR {d:.1%} ≥ {confidence:.0%} after deflating for {trials} trials"
    elif trl is None:
        note = (
            f"observed Sharpe {m.sharpe:+.3f} does not exceed the {trials}-trial benchmark "
            f"{bench:+.3f} — more data cannot rescue it; the candidate is not ahead"
        )
    else:
        note = (
            f"DSR {d:.1%} < {confidence:.0%}: needs ≈{trl:,.0f} observations at these moments "
            f"(have {m.n}) to clear a {trials}-trial benchmark of {bench:+.3f}"
        )
    return DsrResult(
        moments=m, trials=trials, benchmark_sharpe=bench, psr_vs_zero=p0, dsr=d,
        confidence=confidence, passes=passes, min_trl=trl, note=note,
    )


def _implied_sample(r: DsrResult) -> str:
    """The headline half of H11: the observed sample AND the sample this candidate would
    need, always in the same breath.

    Required sample scales with the INVERSE SQUARE of effect size, so halving an edge
    quadruples the evidence needed. Our edges are small, so our required samples are
    enormous — and "n=44" read on its own has repeatedly looked like progress toward a bar
    that was never within reach. On 4,843 published replications the median strategy
    (Sharpe 0.37) needs ~28 years of daily data to separate from zero; the units do not
    transfer to per-trade evidence, which is why MinTRL exists, but the shape does.
    """
    if r.min_trl is None:
        return f"n={r.moments.n}, and MORE DATA CANNOT RESCUE IT (not ahead of the bar)"
    return f"n={r.moments.n} of ≈{r.min_trl:,.0f} needed"


def render_lines(r: DsrResult | None, *, label: str) -> list[str]:
    """Compact markdown for a daily report — the numbers, not just the verdict."""
    if r is None:
        return [f"- **{label} — deflated Sharpe:** not assessable (need ≥3 resolved, non-zero vol)"]
    m = r.moments
    return [
        f"- **{label} — deflated Sharpe bar:** {'✅ CLEARS' if r.passes else '⏳ does NOT clear'}"
        f" · **{_implied_sample(r)}**",
        f"  - {r.note}",
        f"  - n={m.n} · mean {m.mean:+.4f} · sd {m.stdev:.4f} · **Sharpe {m.sharpe:+.3f}**"
        f" · skew {m.skew:+.2f} · kurtosis {m.kurtosis:.2f}",
        f"  - P(true Sharpe > 0) = {r.psr_vs_zero:.1%} · **after deflating for"
        f" {r.trials} trials: {r.dsr:.1%}** (bar {r.confidence:.0%})",
        "  - ⚠ trials are treated as INDEPENDENT; ours overlap (same book, shared cohorts),"
        " so the true deflation is WORSE than shown — this number is optimistic.",
    ]
