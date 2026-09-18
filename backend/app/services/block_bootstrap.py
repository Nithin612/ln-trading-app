"""Moving-block bootstrap for the Sharpe of a trade series — H1.

## Why this exists

`deflated_sharpe.py` gives us a multiple-testing bar, and H8 proved that bar is sound.
But it is **parametric and assumes independence** — its own stated weakness. Our trades
are not independent: concurrent positions in one book share the same market move, so a
bad day is several correlated bad trades, and an iid instrument reads that as several
independent pieces of evidence.

This is the non-parametric complement. It answers a different question from DSR:

    DSR   — "given that we tried N things, is this one better than luck?"
    p5    — "if the same process ran again, how bad could this Sharpe plausibly be?"

and in particular whether the SIGN survives resampling. That is the automated form of the
check constraint #8 currently asks to be done by hand, and that `flip_readiness.tail_guard`
does by trimming the worst 10%: the market-regime cohort flipped from −₹15,986 to +₹10,861
when 3 of 65 trades were dropped. A hand-trim answers "is it one outlier"; the bootstrap
answers "across every plausible resampling, how often does the edge disappear at all".

## Construction

Künsch's **moving-block** bootstrap. Blocks of `L` consecutive trades are drawn with
replacement from the `n − L + 1` overlapping blocks and concatenated to length `n`.
Blocks — not individual trades — are the unit precisely so that short-range dependence
survives the resampling; an iid bootstrap would destroy the thing we are trying to price
in and would report a falsely tight interval.

`L = ceil(n ** (1/3))` — the standard Hall–Horowitz–Jing rate for a variance-type
statistic. At the sample sizes this project actually has (tens of trades) that is 3–4,
which is the right order for "a bad week clusters" without collapsing to iid (L=1) or to
a single block (L=n, which just returns the observed value).

## First read on the live book (2026-09-05)

All 105 closed paper positions, in chronological order, ₹ realised per trade:

    observed Sharpe   −0.033      (total −₹10,218)
    90% interval      [−0.223, +0.118]     blocks of 5, 0% degenerate
    Sharpe ≤ 0 in     70.5% of resampled histories
    DSR, same series  1.3% (fails, as it does for everything)

**The loss is not statistically established either.** The interval contains zero
comfortably and the sign fails to survive resampling in ~30% of histories — so at n=105
the book is indistinguishable from zero in BOTH directions. That is a sharper statement of
the standing conclusion than the ₹ figure alone: it is not that we have measured a small
negative edge, it is that we have not yet measured anything. Any gate partitioning this
series is partitioning noise, which is why no partition of it has ever cleared the bar.

Worth noting for the method's own sake: the block interval is **9% wider than the iid
one** (0.342 vs 0.314). Small, but non-zero and in the expected direction — the trade
series does carry the dependence blocks exist to preserve, so an independence-assuming
instrument reports slightly more confidence than the data supports.

## Honest limits

- **Order matters.** Blocks only mean something if the series is in CHRONOLOGICAL order;
  handed a sorted or grouped series the blocks are arbitrary and the result silently
  becomes an iid bootstrap with extra steps. Callers must pass trades in time order.
- It prices SAMPLING uncertainty, not selection. It says nothing about how many variants
  were tried — that is DSR's job, and the two must be read together.
- The bootstrap resamples the observed distribution, so it cannot know about a regime it
  never saw. A p5 above zero is evidence the sign is not one lucky trade; it is not
  evidence the edge persists out of sample.
- Deterministic by construction (explicit seed). A readiness number that changes between
  two runs on identical data is worse than no number at all.
"""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

#: Resamples per run. 2000 puts the Monte-Carlo error on a 5th percentile well below the
#: sampling error it is measuring, and costs milliseconds at our n.
DEFAULT_RESAMPLES = 2000

#: Fixed seed so a banner is reproducible. Exposed as a parameter for the tests that need
#: to show the result is not an artefact of this particular draw.
DEFAULT_SEED = 20260905

#: Below this, a bootstrap is theatre: with 7 trades the resampling distribution is a
#: handful of atoms and its 5th percentile is noise pretending to be a bound.
MIN_N = 8

#: Refuse to report once this fraction of resamples has no defined Sharpe (a constant
#: resample). Found while validating this module, and it is the module's own failure mode:
#: a series of 43 identical trades plus one −40 outlier produced 76% zero-variance
#: resamples, all dropped — so the surviving 24% were exactly the ones CONTAINING the
#: outlier, and the "interval" described a filtered subpopulation rather than the
#: resampling distribution. Silently dropping degenerate draws biases the answer toward
#: whatever made them non-degenerate. Refusing is the only honest option.
MAX_DEGENERATE_SHARE = 0.10


@dataclass(frozen=True)
class BootstrapResult:
    n: int
    block_len: int
    resamples: int  # resamples that produced a usable Sharpe
    degenerate_share: float  # fraction of draws with no defined Sharpe (see the constant)
    observed_sharpe: float
    p5: float
    p50: float
    p95: float
    share_negative: float  # fraction of resamples whose Sharpe is ≤ 0
    seed: int

    @property
    def sign_survives(self) -> bool:
        """Does the edge keep its sign across the resampling distribution?

        One-sided at 5%: `p5 > 0` for a positive edge, `p95 < 0` for a negative one. A
        cohort whose interval straddles zero has not shown a sign at all — which is the
        state nearly everything in this book is in, and the point of measuring it.
        """
        if self.observed_sharpe > 0:
            return self.p5 > 0
        if self.observed_sharpe < 0:
            return self.p95 < 0
        return False


def block_length(n: int) -> int:
    """`ceil(n ** (1/3))`, clamped to [1, n] — the Hall–Horowitz–Jing rate."""
    if n <= 1:
        return max(n, 1)
    return max(1, min(n, int(math.ceil(n ** (1.0 / 3.0)))))


def _sharpe(sample: Sequence[float]) -> float | None:
    """Per-observation Sharpe (mean ÷ sample sd). None when the sd is zero — a constant
    resample has no Sharpe, and treating it as 0.0 would drag the percentile toward the
    middle for exactly the degenerate draws that carry no information (H6's rule: an
    undefined ratio is None, never a value)."""
    if len(sample) < 2:
        return None
    sd = statistics.stdev(sample)
    if sd <= 0:
        return None
    return statistics.fmean(sample) / sd


def _percentile(sorted_xs: Sequence[float], q: float) -> float:
    """Linear-interpolated percentile on an already-sorted sequence (`q` in [0, 1])."""
    if len(sorted_xs) == 1:
        return sorted_xs[0]
    pos = q * (len(sorted_xs) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_xs[lo]
    return sorted_xs[lo] + (sorted_xs[hi] - sorted_xs[lo]) * (pos - lo)


def moving_block_bootstrap(
    returns: Sequence[float],
    *,
    resamples: int = DEFAULT_RESAMPLES,
    block_len: int | None = None,
    seed: int = DEFAULT_SEED,
) -> BootstrapResult | None:
    """Resample `returns` (CHRONOLOGICAL order) and report the Sharpe distribution.

    ``None`` when the series cannot support a bootstrap: fewer than `MIN_N` observations,
    zero variance, or a draw that produced no usable resample. Absence is the honest answer
    — never a fabricated interval.
    """
    xs = [float(x) for x in returns]
    n = len(xs)
    if n < MIN_N:
        return None
    observed = _sharpe(xs)
    if observed is None:
        return None

    length = block_length(n) if block_len is None else max(1, min(n, block_len))
    n_blocks = n - length + 1  # overlapping blocks — the "moving" in moving-block
    k = math.ceil(n / length)  # blocks per resample, truncated back to n
    rng = random.Random(seed)

    sharpes: list[float] = []
    for _ in range(resamples):
        sample: list[float] = []
        for _ in range(k):
            start = rng.randrange(n_blocks)
            sample.extend(xs[start : start + length])
        s = _sharpe(sample[:n])
        if s is not None:
            sharpes.append(s)
    if not sharpes:
        return None
    degenerate = 1.0 - len(sharpes) / resamples
    if degenerate > MAX_DEGENERATE_SHARE:
        # The percentiles below would describe only the draws that happened to have
        # variance — see MAX_DEGENERATE_SHARE. Report nothing rather than that.
        return None

    sharpes.sort()
    return BootstrapResult(
        n=n,
        block_len=length,
        resamples=len(sharpes),
        degenerate_share=degenerate,
        observed_sharpe=observed,
        p5=_percentile(sharpes, 0.05),
        p50=_percentile(sharpes, 0.50),
        p95=_percentile(sharpes, 0.95),
        share_negative=sum(1 for s in sharpes if s <= 0) / len(sharpes),
        seed=seed,
    )


def render_lines(r: BootstrapResult | None, *, label: str) -> list[str]:
    """One block for a readiness banner — the interval, and what it does or does not say."""
    if r is None:
        return [
            f"- **{label} — block bootstrap:** not assessable (need ≥{MIN_N} resolved "
            f"trades, non-zero variance, and <{MAX_DEGENERATE_SHARE:.0%} degenerate "
            "resamples — a near-constant series with one outlier fails the last of these, "
            "and reporting an interval for it would describe only the draws that contain "
            "the outlier)"
        ]
    sign = "positive" if r.observed_sharpe > 0 else "negative"
    verdict = f"✅ the {sign} sign SURVIVES" if r.sign_survives else "⏳ the sign does NOT survive"
    return [
        f"- **{label} — block bootstrap ({r.resamples:,} resamples, "
        f"blocks of {r.block_len}):** {verdict} resampling",
        f"  - observed Sharpe **{r.observed_sharpe:+.3f}** · "
        f"90% interval [**{r.p5:+.3f}**, {r.p95:+.3f}] · median {r.p50:+.3f}",
        f"  - the Sharpe comes out ≤ 0 in **{r.share_negative:.0%}** of plausible histories",
        "  - ⚠ prices SAMPLING uncertainty only, not selection (that is DSR's job), and "
        "assumes the series was passed in chronological order.",
    ]


def newey_west_t(series: Sequence[float], *, lag: int) -> float | None:
    """t-statistic for the MEAN of an autocorrelated series (Newey-West, Bartlett kernel).

    ## Why this sits here and is not a second bootstrap

    `moving_block_bootstrap` above prices dependence in a *trade* series and reports a
    *Sharpe* interval. This prices dependence in a *daily* series and corrects the *mean*'s
    standard error. Same problem — short-range dependence makes an iid statistic overconfident
    — different statistic, so the two are complements, not duplicates.

    ## The specific defect it fixes (quant-verifier HIGH, 2026-09-10)

    A study that measures a k-session forward return on every day produces DAILY OBSERVATIONS
    THAT OVERLAP: day t and day t+1 share k−1 sessions of the same future. Averaging across
    the cross-section each day removes the same-day correlation but leaves that overlap
    untouched, so a naive `mean / (sd/sqrt(n))` on the daily series is inflated by roughly
    `sqrt(k)`. Measured under H0 on a full panel the naive t had sd 0.98 at k=1 but **3.32 at
    k=10 and 4.45 at k=20** — i.e. an apparent "t of 9" at a 20-session horizon is about 1.9
    sigma. Reporting the naive t made a never-significant gradient look decisive.

    `lag` should be `k − 1` for a k-session forward window (the number of overlapping
    sessions). Bartlett weights `1 − l/(lag+1)` guarantee a non-negative variance estimate.

    Returns ``None`` when the series is too short or has no variance — absence is the honest
    answer, never a fabricated statistic.
    """
    xs = [float(x) for x in series]
    n = len(xs)
    if n < 3:
        return None
    mean = sum(xs) / n
    dev = [x - mean for x in xs]
    gamma0 = sum(d * d for d in dev) / n
    if gamma0 <= 0.0:
        return None
    lag = max(0, min(int(lag), n - 1))
    var = gamma0
    for lg in range(1, lag + 1):
        cov = sum(dev[i] * dev[i - lg] for i in range(lg, n)) / n
        var += 2.0 * (1.0 - lg / (lag + 1.0)) * cov
    if var <= 0.0:
        # Bartlett weights make this rare but not impossible in tiny samples; refuse rather
        # than emit a t from a negative variance.
        return None
    return mean / math.sqrt(var / n)


# ─────────────────────────────────────────────────────────────────────────────
# Queue item 6 — CLUSTERED inference, for dependence that is not serial.
#
# ⭐⭐ Why these live here and not in a new module: this file already owns
# "dependence-corrected inference" (`newey_west_t`), and the whole point of item 6 is
# that **the three studies have three DIFFERENT dependence structures and therefore need
# three different estimators** — D1 is per-date (a market-wide regressor), D5 is
# paired-by-signal, B7 is overlapping-per-trade. The queue says, in as many words, *not*
# "apply Newey-West". Newey-West corrects SERIAL correlation along one axis; it is the
# wrong instrument for "many trades share one day", where the dependence is a grouping,
# not a lag.
#
# ⛔ The failure these prevent is documented and expensive: RVOL's `t = +3.67` was an
# IID-SE artifact that collapsed to +0.98 once clustered by date, because 185 trades sat
# on 92 dates and the regressor was market-wide daily. The point estimate was fine. The
# standard error was off by 6×.
# ─────────────────────────────────────────────────────────────────────────────


def intraclass_correlation(
    values: Sequence[float], groups: Sequence[Any]
) -> tuple[float, float, int]:
    """One-way random-effects ICC, the average cluster size, and the cluster count.

    Returns `(icc, m0, n_groups)`. `m0` is the *effective* average cluster size for
    unbalanced groups — `(n - Σm²/n) / (G-1)` — not the plain mean, because using the plain
    mean on unbalanced clusters understates the design effect.

    ⚠ ICC is clamped at 0 below. A negative sample ICC means the between-group variance
    estimate came out under the within-group one, which is noise, not evidence of negative
    dependence — and letting it through would produce a design effect < 1, i.e. a claim
    that clustering BOUGHT precision.
    """
    n = len(values)
    if n != len(groups):
        raise ValueError(f"{n} values against {len(groups)} group labels")
    by: dict[Any, list[float]] = {}
    for v, g in zip(values, groups, strict=True):
        by.setdefault(g, []).append(v)
    n_groups = len(by)
    if n_groups < 2 or n <= n_groups:
        return 0.0, float(n) / max(n_groups, 1), n_groups

    grand = sum(values) / n
    ss_between = sum(len(vs) * (sum(vs) / len(vs) - grand) ** 2 for vs in by.values())
    ss_within = sum(sum((v - sum(vs) / len(vs)) ** 2 for v in vs) for vs in by.values())
    ms_between = ss_between / (n_groups - 1)
    ms_within = ss_within / (n - n_groups)

    m0 = (n - sum(len(vs) ** 2 for vs in by.values()) / n) / (n_groups - 1)
    denom = ms_between + (m0 - 1) * ms_within
    icc = 0.0 if denom <= 0 else (ms_between - ms_within) / denom
    return max(icc, 0.0), m0, n_groups


def design_effect(values: Sequence[float], groups: Sequence[Any]) -> float:
    """`1 + (m0 - 1)·ICC` — the factor by which the naive VARIANCE is understated.

    Divide the nominal n by this to get an effective n; multiply the naive SE by its square
    root to get the approximate corrected SE. Reported alongside the exact cluster-robust SE
    because the two disagreeing is itself informative (it means a few large clusters dominate).
    """
    icc, m0, _ = intraclass_correlation(values, groups)
    return 1.0 + (m0 - 1.0) * icc


def cluster_robust_mean_t(
    values: Sequence[float], groups: Sequence[Any], *, null: float = 0.0
) -> tuple[float, float, float, int] | None:
    """Mean, cluster-robust SE, t, and cluster count — for a simple mean.

    The sandwich for a mean reduces to summing the within-cluster deviations FIRST and then
    taking the variance across clusters, which is exactly what makes it robust to any
    within-cluster correlation structure (it never has to be modelled).

    Small-G correction `G/(G-1)` applied. ⚠ With very few clusters this is anti-conservative
    whatever the correction — the number of CLUSTERS, not observations, is the sample size
    here, so it is returned for the caller to report rather than hidden.
    """
    n = len(values)
    if n < 2:
        return None
    mean = sum(values) / n
    by: dict[Any, float] = {}
    for v, g in zip(values, groups, strict=True):
        by[g] = by.get(g, 0.0) + (v - mean)
    n_groups = len(by)
    if n_groups < 2:
        return None
    meat = sum(s * s for s in by.values())
    var = (n_groups / (n_groups - 1)) * meat / (n * n)
    if var <= 0:
        return mean, 0.0, 0.0, n_groups
    se = var**0.5
    return mean, se, (mean - null) / se, n_groups
