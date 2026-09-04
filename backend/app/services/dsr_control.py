"""H8 — the negative control on our own deflated-Sharpe bar.

`deflated_sharpe.py` currently says NO to every gate we have. That verdict is about to
justify abandoning the gating programme, so the instrument itself needs testing before we
act on it. This module is that test.

**Why the finding's original framing is not enough.** `docs/quant-agent-findings.md` (H8)
asks only *"does the bar reject pure noise?"* — modelled on an external repo whose worked
example feeds noise through an audit and shows it caught. But **a bar that rejects
everything passes that check trivially**, and ours currently rejects everything. A test that
cannot come out badly is not a test; that is the project's own standing rule, applied here
to the test rather than to the strategy. So this module runs BOTH directions:

* **specificity** — under a true-zero-edge null, the bar must reject. Two variants:
  `random_partition_rate` does literally what H8 asks (random, content-free partitions of
  the real trade set), and `best_of_trials_rate` runs the *selection procedure we actually
  perform* — generate `trials` zero-edge candidates, keep the best-looking one, judge it.
  The second is the one that matters, because looking at eight gates and getting interested
  in the best is exactly how we came to promote two gates that were later refuted.
* **power** — when a real edge of known size IS present, the bar must accept it.
  `power_rate` measures that, and `minimum_detectable_sharpe` reports the smallest true
  edge the bar can see at a given sample size.

Only both arms together separate *"our gates are genuinely not good enough"* from *"our bar
cannot say yes to anything"*. Those two readings imply opposite next actions.

**Synthetic series are bootstrapped from the real book, then shifted**, never drawn from a
normal. PSR is explicitly skew- and kurtosis-aware — it charges more for fat tails and
negative skew — so a Gaussian control would flatter the bar by feeding it the one
distribution it has no complaint about. Resampling the real P&L preserves the shape and
shifting by a constant moves the mean without touching sd, skew or kurtosis, which makes
the planted Sharpe exact by construction.

Pure and deterministic: every entry point takes an explicit `random.Random`, so a finding
here reproduces. Stdlib only, matching `deflated_sharpe.py`.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import NormalDist

from app.services import deflated_sharpe as ds

#: Simulation counts. Large enough that a 5% rate is resolved to well under a point.
DEFAULT_SIMS = 2_000
#: Power is reported at these thresholds; 80% is the conventional design target.
POWER_TARGETS = (0.50, 0.80)


@dataclass(frozen=True)
class ArmResult:
    """One arm of the control: how often the bar said yes, and whether that is correct."""

    label: str
    sims: int
    cleared: int
    n: int
    verdict_ok: bool
    note: str

    @property
    def rate(self) -> float:
        return self.cleared / self.sims if self.sims else 0.0


def centered(pnl: Sequence[float]) -> list[float]:
    """The real book's shape with its edge removed — a true-zero-mean null that keeps the
    real sd, skew and kurtosis. Subtracting the sample mean is what makes it a null; keeping
    every deviation is what stops it being a Gaussian flatter."""
    if not pnl:
        return []
    mu = sum(pnl) / len(pnl)
    return [x - mu for x in pnl]


def resample(pool: Sequence[float], n: int, rng: random.Random) -> list[float]:
    """`n` draws with replacement — an i.i.d. bootstrap of the pool's distribution."""
    return [pool[rng.randrange(len(pool))] for _ in range(n)]


def shifted_to_sharpe(sample: Sequence[float], target_sharpe: float) -> list[float]:
    """Shift a sample so its *realised* per-observation Sharpe is exactly `target_sharpe`.

    A constant shift moves the mean and leaves sd, skew and kurtosis alone, so the planted
    edge is exact and the distribution shape is still the real book's. Returns the sample
    unchanged when its dispersion is degenerate."""
    n = len(sample)
    if n < 2:
        return list(sample)
    mu = sum(sample) / n
    sd = math.sqrt(sum((x - mu) ** 2 for x in sample) / (n - 1))
    if sd <= 0:
        return list(sample)
    return [x + (target_sharpe * sd - mu) for x in sample]


def _clears(series: Sequence[float], *, trials: int,
            confidence: float = ds.DEFAULT_CONFIDENCE) -> bool:
    """The bar, reached by exactly the path `flip_readiness.evidence_lines` uses.

    `confidence` is exposed only so the suite can construct a deliberately impossible bar
    and prove the power arm goes red — a canary for the canary. Production callers leave
    it at the default."""
    r = ds.deflated_sharpe(list(series), trials=trials, confidence=confidence)
    return bool(r and r.passes)


def _best_by_sharpe(candidates: Sequence[Sequence[float]]) -> list[float]:
    """The candidate a human would get interested in. Selection is the whole hazard: the
    max of many noisy Sharpes is biased upward, which is the bias DSR exists to undo."""
    best: Sequence[float] = candidates[0]
    best_sr = -math.inf
    for c in candidates:
        m = ds.moments(list(c))
        if m is not None and m.sharpe > best_sr:
            best_sr, best = m.sharpe, c
    return list(best)


def random_partition_rate(
    pnl: Sequence[float],
    *,
    block_frac: float,
    trials: int = ds.DEFAULT_TRIALS,
    sims: int = DEFAULT_SIMS,
    rng: random.Random,
) -> ArmResult:
    """H8 as literally specified: content-free partitions of the REAL trade set.

    Each sim splits the real trades at random into would-block / eligible in the same
    proportion a real gate uses, then judges the eligible side. A random partition carries
    no information, so the bar must essentially never clear one. Uses the real trades
    themselves, so it inherits the book's real (negative) mean — which makes this the weaker
    of the two specificity arms and the reason `best_of_trials_rate` exists."""
    n_total = len(pnl)
    keep = max(3, round(n_total * (1.0 - block_frac)))
    cleared = 0
    for _ in range(sims):
        shuffled = list(pnl)
        rng.shuffle(shuffled)
        if _clears(shuffled[:keep], trials=trials):
            cleared += 1
    rate = cleared / sims if sims else 0.0
    ok = rate <= 0.05
    return ArmResult(
        label="specificity · random partitions of the real book",
        sims=sims, cleared=cleared, n=keep, verdict_ok=ok,
        note=(
            f"{rate:.2%} of {sims:,} content-free partitions cleared the bar"
            f" ({'≤' if ok else '>'} the 5% nominal false-positive rate)"
        ),
    )


def best_of_trials_rate(
    pnl: Sequence[float],
    *,
    n: int,
    trials: int = ds.DEFAULT_TRIALS,
    sims: int = DEFAULT_SIMS,
    rng: random.Random,
) -> ArmResult:
    """The specificity arm that matches what we actually do: try `trials` things with NO
    edge, keep the best-looking one, and judge it.

    This is the honest null for a shop that runs eight shadow gates and reads the most
    promising banner. If the bar clears these at much above 5%, every readiness banner
    built on it is worthless — the number would be measuring selection, not skill."""
    pool = centered(pnl)
    cleared = 0
    for _ in range(sims):
        cands = [resample(pool, n, rng) for _ in range(trials)]
        if _clears(_best_by_sharpe(cands), trials=trials):
            cleared += 1
    rate = cleared / sims if sims else 0.0
    ok = rate <= 0.05
    return ArmResult(
        label=f"specificity · best of {trials} zero-edge candidates",
        sims=sims, cleared=cleared, n=n, verdict_ok=ok,
        note=(
            f"{rate:.2%} of {sims:,} best-of-{trials} selections from pure noise cleared"
            f" ({'≤' if ok else '>'} the 5% nominal false-positive rate)"
        ),
    )


def power_rate(
    pnl: Sequence[float],
    *,
    n: int,
    true_sharpe: float,
    trials: int = ds.DEFAULT_TRIALS,
    confidence: float = ds.DEFAULT_CONFIDENCE,
    sims: int = DEFAULT_SIMS,
    rng: random.Random,
) -> float:
    """Fraction of samples carrying a REAL per-trade edge of `true_sharpe` that the bar
    accepts. This is the half H8's original framing omits, and the half that decides whether
    'fails the bar' means 'has no edge' or 'is invisible at this sample size'."""
    pool = centered(pnl)
    cleared = 0
    for _ in range(sims):
        s = shifted_to_sharpe(resample(pool, n, rng), true_sharpe)
        if _clears(s, trials=trials, confidence=confidence):
            cleared += 1
    return cleared / sims if sims else 0.0


def minimum_detectable_sharpe(
    pnl: Sequence[float],
    *,
    n: int,
    target_power: float,
    trials: int = ds.DEFAULT_TRIALS,
    sims: int = 400,
    rng: random.Random,
    lo: float = 0.0,
    hi: float = 1.5,
    tol: float = 0.005,
) -> float | None:
    """The smallest true per-trade Sharpe the bar detects `target_power` of the time at
    sample size `n`. Bisection — power is monotone in the planted edge. None if even `hi`
    cannot be seen, which would itself be the finding."""
    if power_rate(pnl, n=n, true_sharpe=hi, trials=trials, sims=sims, rng=rng) < target_power:
        return None
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if power_rate(pnl, n=n, true_sharpe=mid, trials=trials, sims=sims, rng=rng) >= target_power:
            hi = mid
        else:
            lo = mid
    return hi


def implied_t_hurdle(n: int, *, trials: int = ds.DEFAULT_TRIALS,
                     confidence: float = ds.DEFAULT_CONFIDENCE) -> float:
    """The bar restated as a plain t-statistic on the trade series.

    Solves for the observed Sharpe at which DSR exactly equals `confidence` (holding the
    Gaussian case, skew 0 / kurtosis 3, so the number is the bar's FLOOR — real fat tails
    make it stricter), then returns `sharpe · √n`. This is the single most communicable
    output of the whole control: it converts an opaque probability into the hurdle the
    finance literature already argues about."""
    z = NormalDist().inv_cdf(confidence)
    bench = ds.expected_max_sharpe(trials, 1.0 / math.sqrt(n))
    lo, hi = 0.0, 5.0
    for _ in range(200):
        sr = (lo + hi) / 2
        denom_sq = 1.0 - 0.0 * sr + ((3.0 - 1.0) / 4.0) * sr**2
        got = (sr - bench) * math.sqrt(n - 1) / math.sqrt(denom_sq) if denom_sq > 0 else -math.inf
        if got >= z:
            hi = sr
        else:
            lo = sr
    return hi * math.sqrt(n)
