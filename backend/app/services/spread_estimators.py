"""Effective-spread estimators from OHLC bars.

⛔ **Why these exist at all.** There is no historical record of the order book in this
system: ``depth:{stock_id}`` is Redis-only at a 60-second TTL and is never persisted
(``app/broker/depth.py``), and the soak recordings carry ticks with the book stripped.
So a *retrospective* question about execution cost — item 17 — cannot be answered by
looking anything up. It has to be estimated from the bars we do keep.

⚠ **These are ESTIMATORS, and the distinction is load-bearing.** They infer the spread
from the geometry of price ranges. They do not observe it. Every number they produce
carries that tag until the forward top-of-book capture (item 17b) can validate them
against a real book.

⚠ **Known bias, and it is asymmetric — this is why the caller reports both.** Both
estimators conflate spread with volatility, Corwin-Schultz upward when volatility is
high. ⇒ a HIGH reading is the weaker result (it may be volatility) and a LOW reading is
the stronger one (volatility bias cannot manufacture a small spread). The pre-registered
decision tree in ``docs/analysis/item17-spread-impact-preregistration-2026-09-20.md``
depends on that asymmetry.

References
----------
Corwin, S. A., & Schultz, P. (2012). *A Simple Way to Estimate Bid-Ask Spreads from
Daily High and Low Prices.* Journal of Finance 67(2), 719-759.

Abdi, F., & Ranaldo, A. (2017). *A Simple Estimation of Bid-Ask Spreads from Daily Close,
High, and Low Prices.* Review of Financial Studies 30(12), 4437-4480.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass

__all__ = [
    "MIN_SESSIONS_FOR_STABILITY",
    "NullCalibration",
    "calibrate",
    "simulate_session",
    "Bar",
    "abdi_ranaldo",
    "abdi_ranaldo_sessions",
    "corwin_schultz",
    "corwin_schultz_pair",
    "corwin_schultz_sessions",
    "proportional_to_half_spread_bps",
]

# ⭐ **Measured, not chosen.** A single-session Abdi-Ranaldo estimate is knife-edge at
# high volatility: under a true zero spread roughly half of sessions clamp to zero, so
# the cohort median sits exactly on the clamp boundary and flips between 0 and ~5 bps —
# which is the pre-registered decision boundary. Pooling the expectation across sessions
# fixes it. At 80 bps/bar volatility, recovery of a planted 5 bps half-spread goes
# 3.58 (1 session) -> 4.24 (5) -> **5.07 (21)** -> 4.86 (63), and a planted 10 bps goes
# from 35.3% of windows clamping to 2.5% at 21. 21 sessions ~ one trading month, which is
# also the window Abdi & Ranaldo apply the estimator over.
MIN_SESSIONS_FOR_STABILITY = 21

# (3 - 2*sqrt(2)) — the Corwin-Schultz constant, named rather than inlined so the
# formula below reads like the paper.
_K = 3.0 - 2.0 * math.sqrt(2.0)


@dataclass(frozen=True, slots=True)
class Bar:
    """One OHLC bar. Only high/low/close are used; open is not part of either estimator."""

    high: float
    low: float
    close: float

    @property
    def is_degenerate(self) -> bool:
        """A bar with no range carries no spread evidence.

        Common on thin names and single-trade intervals. Kept rather than filtered —
        dropping them biases the estimate UP by discarding exactly the quiet intervals —
        but counted by the caller, because a cohort that is mostly degenerate bars is a
        cohort the estimator cannot describe.
        """
        return not (self.high > self.low)


def proportional_to_half_spread_bps(proportional: float) -> float:
    """Both estimators return a PROPORTIONAL (relative) spread; the falsifier is in
    half-spread bps. One trip crosses half the spread."""
    return proportional / 2.0 * 10_000.0


def _usable(bar: Bar) -> bool:
    return bar.high > 0.0 and bar.low > 0.0 and bar.close > 0.0 and bar.high >= bar.low


def corwin_schultz_pair(b0: Bar, b1: Bar) -> float | None:
    """Corwin-Schultz proportional spread from one adjacent pair of bars.

    Returns ``None`` when the pair cannot be evaluated (non-positive prices) — **never
    0.0 for undefined**, which is the ``app/core/ratios`` rule: "not assessable" and
    "measured zero" must stay distinguishable. A NEGATIVE alpha is a genuine measurement
    and is clamped to 0.0 exactly as the paper specifies.
    """
    if not (_usable(b0) and _usable(b1)):
        return None

    beta = math.log(b0.high / b0.low) ** 2 + math.log(b1.high / b1.low) ** 2
    hi = max(b0.high, b1.high)
    lo = min(b0.low, b1.low)
    gamma = math.log(hi / lo) ** 2

    alpha = (math.sqrt(2.0 * beta) - math.sqrt(beta)) / _K - math.sqrt(gamma / _K)
    spread = 2.0 * (math.exp(alpha) - 1.0) / (1.0 + math.exp(alpha))
    # The paper sets negative estimates to zero: a negative alpha means the observed
    # ranges are smaller than a zero-spread diffusion would produce, i.e. noise.
    return max(0.0, spread)


def _cs_estimates(bars: Sequence[Bar]) -> list[float]:
    return [
        e
        for e in (corwin_schultz_pair(b0, b1) for b0, b1 in zip(bars, bars[1:], strict=False))
        if e is not None
    ]


def corwin_schultz(bars: Sequence[Bar]) -> float | None:
    """Corwin-Schultz over ONE run of contiguous bars — the mean of the per-pair estimates.

    ⛔ **Never hand this bars from two different sessions.** An overnight gap inflates
    gamma so far that alpha goes sharply negative and the estimate **clamps to zero** —
    it UNDERSTATES rather than overstating, which is the more dangerous direction because
    it looks like a cheap stock. Use ``corwin_schultz_sessions`` instead, which cannot
    make that mistake.
    """
    estimates = _cs_estimates(bars)
    if not estimates:
        return None
    return sum(estimates) / len(estimates)


def corwin_schultz_sessions(sessions: Sequence[Sequence[Bar]]) -> float | None:
    """Corwin-Schultz pooled over several sessions, pairing only WITHIN each.

    ⭐ The session boundary is handled by the type rather than by a caller remembering a
    docstring — the sequence-of-sessions shape makes the unsafe pairing unexpressible.
    """
    estimates: list[float] = []
    for session in sessions:
        estimates.extend(_cs_estimates(session))
    if not estimates:
        return None
    return sum(estimates) / len(estimates)


def abdi_ranaldo(bars: Sequence[Bar]) -> float | None:
    """Abdi-Ranaldo close-high-low proportional spread.

    S^2 = 4 * E[(c_t - eta_t) * (c_t - eta_{t+1})], eta = log mid-range.

    ⭐ Independent of Corwin-Schultz in construction — it uses the close's position
    within the range rather than the range's size — which is why agreement between the
    two is evidence and disagreement is information.

    The expectation is taken BEFORE the square root and the clamp, per the paper: a
    per-pair clamp would discard the negative draws that make the estimator unbiased and
    would bias every result upward.
    """
    return _from_products(_ar_products(bars))


def _ar_products(bars: Sequence[Bar]) -> list[float]:
    products: list[float] = []
    for b0, b1 in zip(bars, bars[1:], strict=False):
        if not (_usable(b0) and _usable(b1)):
            continue
        eta0 = (math.log(b0.high) + math.log(b0.low)) / 2.0
        eta1 = (math.log(b1.high) + math.log(b1.low)) / 2.0
        c0 = math.log(b0.close)
        products.append((c0 - eta0) * (c0 - eta1))
    return products


def _from_products(products: Sequence[float]) -> float | None:
    if not products:
        return None
    mean = sum(products) / len(products)
    if mean <= 0.0:
        return 0.0
    return 2.0 * math.sqrt(mean)


def abdi_ranaldo_sessions(sessions: Sequence[Sequence[Bar]]) -> float | None:
    """Abdi-Ranaldo pooled over several sessions — **the form the study uses.**

    Pairs are formed only within a session; the expectation is taken over the pooled
    products. Pooling is what makes the estimate stable: see
    ``MIN_SESSIONS_FOR_STABILITY`` for the measured reason.
    """
    products: list[float] = []
    for session in sessions:
        products.extend(_ar_products(session))
    return _from_products(products)


# --------------------------------------------------------------------------- calibration
#
# ⭐ **Why a synthetic generator lives in the library and not only in the tests.** These
# estimators cannot be read without knowing what they report on a series with NO spread,
# and that null depends on volatility — sharply, for Corwin-Schultz. A study that quotes a
# measured spread without quoting the null at ITS OWN cohort volatility invites the reader
# to compare a number against the wrong baseline. So the calibration is part of using the
# instrument, and the test and the study share ONE generator rather than each keeping a
# copy (W2).
#
# ⚠ The generator IS the estimators' own assumed model — a diffusion observed through a
# bid-ask bounce. It validates the arithmetic and calibrates the null; it says nothing
# about robustness to real microstructure. Only item 17b can do that.

_DEFAULT_BARS = 75  # a 9:15-15:30 session in 5-minute bars
_DEFAULT_SUBSTEPS = 12


def simulate_session(
    *,
    half_spread_bps: float,
    sigma_bar_bps: float,
    rng: random.Random,
    bars: int = _DEFAULT_BARS,
    substeps: int = _DEFAULT_SUBSTEPS,
    start_price: float = 500.0,
) -> list[Bar]:
    """One session of bars from an efficient price that prints at bid or ask.

    The high prints at the ask, the low at the bid and the close on a random side, so the
    planted spread is a property of the OBSERVED bars and nothing tells the estimator what
    it is.
    """
    price = start_price
    half = half_spread_bps / 10_000.0
    step_sigma = (sigma_bar_bps / 10_000.0) / math.sqrt(substeps)
    out: list[Bar] = []
    for _ in range(bars):
        high = low = price
        for _ in range(substeps):
            price *= math.exp(rng.gauss(0.0, step_sigma))
            high = max(high, price)
            low = min(low, price)
        side = 1.0 if rng.random() < 0.5 else -1.0
        out.append(
            Bar(high=high * (1.0 + half), low=low * (1.0 - half), close=price * (1.0 + side * half))
        )
    return out


@dataclass(frozen=True, slots=True)
class NullCalibration:
    """What each estimator reports at a given volatility when the truth is known."""

    sigma_bar_bps: float
    planted_half_bps: float
    cs_median_bps: float
    ar_median_bps: float
    ar_clamp_share: float


def calibrate(
    *,
    sigma_bar_bps: float,
    planted_half_bps: float = 0.0,
    sessions: int = MIN_SESSIONS_FOR_STABILITY,
    replications: int = 300,
    seed: int = 20260920,
) -> NullCalibration:
    """Run both estimators against a KNOWN planted half-spread at this volatility.

    Deterministic for a given seed. With ``planted_half_bps=0`` this is the zero-spread
    null — the number a measured reading must be compared against.
    """
    cs: list[float] = []
    ar: list[float] = []
    for i in range(replications):
        rng = random.Random(seed + i * 13)
        panel = [
            simulate_session(
                half_spread_bps=planted_half_bps, sigma_bar_bps=sigma_bar_bps, rng=rng
            )
            for _ in range(sessions)
        ]
        c = corwin_schultz_sessions(panel)
        a = abdi_ranaldo_sessions(panel)
        if c is not None:
            cs.append(proportional_to_half_spread_bps(c))
        if a is not None:
            ar.append(proportional_to_half_spread_bps(a))
    cs.sort()
    ar.sort()
    return NullCalibration(
        sigma_bar_bps=sigma_bar_bps,
        planted_half_bps=planted_half_bps,
        cs_median_bps=cs[len(cs) // 2],
        ar_median_bps=ar[len(ar) // 2],
        ar_clamp_share=sum(1 for v in ar if v <= 1e-12) / len(ar),
    )
