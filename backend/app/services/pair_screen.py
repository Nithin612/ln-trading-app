"""Pair-trading cointegration / mean-reversion screen (Phase 6.5, slice 6.5a).

Pure numpy — no DB, no clock, no randomness (a DB-loading wrapper lives above it,
so this core stays unit-testable on synthetic series). The math is indicator-class
f64 (rules: floats are allowed inside indicator math); money/P&L stays Decimal in
the layers above. Two stationarity paths: a zero-dep **numpy plain-DF** path (default)
and a more-rigorous **statsmodels Augmented-DF + Johansen** path (`method="adf"`) — see
phase-06-6.5-pairtrading-plan.md.

Given two aligned close-price series A, B over COMPLETED candles, we fit a hedge
ratio by OLS, form the spread s = A − (α + β·B), and measure whether/how fast that
spread mean-reverts:

  - hedge_ratio    — OLS α, β of A on B.
  - mean_reversion — the Dickey-Fuller regression Δs_t = c + λ·s_{t-1} + ε. λ < 0 is
                     mean reversion; its t-statistic is the DF test statistic (the
                     stationarity evidence), and half-life = −ln 2 / λ (OU, in bars).
  - variance_ratio — Lo-MacKinlay VR(q), reported for information (<1 ⇒ mean-reverting;
                     at q=2 it is a weak discriminator for slow pairs, so it does NOT
                     gate — the DF t-stat does).
  - zscore         — the spread's current standardized distance from its trailing mean,
                     i.e. the live entry signal (long the cheap leg when z ≤ −z_entry).

Two stationarity paths: the numpy plain Dickey-Fuller (no lag augmentation; t-stat vs the
−2.86 5% CV) is the zero-dep default; `method="adf"` uses statsmodels' Augmented DF (AIC
lag selection + MacKinnon p-value) with a Johansen hedge ratio — more rigorous, and the
A/B (`docs/analysis/pairs-*.md`) checks whether it changes the candidate set. The lag
augmentation absorbs serial correlation the plain-DF t-stat cannot, so the ADF path is
less prone to false-stationary calls at the borderline.

No look-ahead: every statistic is computed only from the window handed in (completed
bars ≤ N); the caller keeps the signal for N+1. Degenerate inputs (too short, zero
variance, non-finite, no mean reversion) return None rather than a misleading number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]

# Minimum completed observations before any statistic is trustworthy. Pair stats on
# a handful of bars are noise; the caller must not rank below this (the n-floor
# precedent from 6.2 attribution).
MIN_OBS = 60

# Screen policy. A pair is a mean-reversion CANDIDATE only if its spread is
# stationary with statistical evidence (DF t-stat past the 5% critical value) AND it
# reverts fast enough to trade (half-life within a horizon). Conservative on purpose —
# the shadow evidence, not this file, sets the final thresholds.
DF_CRIT_5PCT = -2.86  # plain Dickey-Fuller 5% critical value, constant case, large-N (df path)
ADF_PVALUE_5PCT = 0.05  # Augmented DF (statsmodels) p-value gate (adf path)
MAX_HALF_LIFE = 30.0  # bars; slower than this is untradeable drift, not reversion
MIN_HALF_LIFE = 1.0  # bars; faster is noise/discretization, not a real spread
# Notional plausibility: a dollar-neutral pair trades ~1 unit of A against β units of B, so
# β·price_B should be within this factor of price_A. A wild imbalance (a fragile cointegrating
# vector — e.g. Johansen on raw price levels giving β≈132) is not tradeable market-neutral and
# is rejected, not surfaced as an un-hedgeable "pair". Guards both methods.
MAX_NOTIONAL_IMBALANCE = 5.0


@dataclass(frozen=True)
class PairStat:
    """One candidate pair's mean-reversion profile over the observed window. All
    fields are display/analysis f64; the None-returning screen filters the degenerate
    cases out before this is built."""

    alpha: float  # OLS intercept  (A ≈ alpha + beta·B)
    beta: float  # OLS hedge ratio
    half_life: float  # OU half-life in bars (> 0, finite)
    df_tstat: float  # DF t-stat of the mean-reversion coefficient (< 0; more neg = stronger)
    variance_ratio: float  # Lo-MacKinlay VR(2); informational (< 1 ⇒ mean-reverting)
    zscore: float  # current spread z over the trailing window
    n: int  # observations used
    spread_mean: float
    spread_std: float
    # Which stationarity test gated this pair: "df" (numpy plain-DF t-stat + OLS β) or
    # "adf" (statsmodels Augmented DF p-value + Johansen β). The adf_* fields are populated
    # only on the adf path; df_tstat is always computed (numpy) for the record / comparison.
    method: str = "df"
    adf_stat: float | None = None
    adf_pvalue: float | None = None


def _finite_2d(a: FloatArray, b: FloatArray) -> tuple[FloatArray, FloatArray] | None:
    """Align + drop non-finite rows; None if the arrays disagree in length or go
    too short after cleaning."""
    if a.shape != b.shape or a.ndim != 1:
        return None
    mask = np.isfinite(a) & np.isfinite(b)
    a2, b2 = a[mask], b[mask]
    if a2.size < MIN_OBS:
        return None
    return a2, b2


def hedge_ratio(a: FloatArray, b: FloatArray) -> tuple[float, float] | None:
    """OLS α, β of A on B (A ≈ α + β·B). None if B has no variance (β undefined) or
    the fit is non-finite."""
    if a.shape != b.shape or a.size < 2:
        return None
    if not np.isfinite(b).all() or float(np.var(b)) == 0.0:
        return None
    design = np.column_stack([b, np.ones_like(b)])
    sol, *_ = np.linalg.lstsq(design, a, rcond=None)
    beta, alpha = float(sol[0]), float(sol[1])
    if not (math.isfinite(beta) and math.isfinite(alpha)):
        return None
    return alpha, beta


def mean_reversion(spread: FloatArray) -> tuple[float, float, float] | None:
    """Dickey-Fuller regression of the spread: Δs_t = c + λ·s_{t-1} + ε. Returns
    (lambda, t_stat, half_life) where λ < 0 is mean reversion, t_stat is λ/SE(λ) (the
    DF statistic — the more negative, the stronger the stationarity evidence), and
    half_life = −ln 2 / λ in bars. None when there is no mean reversion (λ ≥ 0), the
    regressor has no variance, or the fit is degenerate/non-finite."""
    s = np.asarray(spread, dtype=float)
    if s.size < 4 or not np.isfinite(s).all():
        return None
    s_lag = s[:-1]
    delta = s[1:] - s_lag
    n = s_lag.size
    if float(np.var(s_lag)) == 0.0:
        return None
    x = np.column_stack([s_lag, np.ones_like(s_lag)])  # [s_{t-1}, 1]
    sol, *_ = np.linalg.lstsq(x, delta, rcond=None)
    lam = float(sol[0])
    if not math.isfinite(lam) or lam >= 0.0:
        return None
    # Standard error of λ: σ²·(XᵀX)⁻¹[0,0], σ² = RSS/(n−2).
    resid = delta - x @ sol
    dof = n - 2
    if dof <= 0:
        return None
    sigma2 = float(resid @ resid) / dof
    xtx_inv = np.linalg.inv(x.T @ x)
    var_lam = sigma2 * float(xtx_inv[0, 0])
    if var_lam <= 0.0 or not math.isfinite(var_lam):
        return None
    t_stat = lam / math.sqrt(var_lam)
    half_life = -math.log(2.0) / lam
    if not (math.isfinite(t_stat) and math.isfinite(half_life) and half_life > 0.0):
        return None
    return lam, t_stat, half_life


def variance_ratio(spread: FloatArray, q: int = 2) -> float | None:
    """Lo-MacKinlay variance ratio VR(q) of the spread, overlapping + unbiased
    estimator. VR<1 ⇒ negative autocorrelation ⇒ mean-reverting; ≈1 ⇒ random walk;
    >1 ⇒ trending. Informational (weak at q=2 for slow pairs). None if too short or
    the 1-period variance is zero."""
    s = np.asarray(spread, dtype=float)
    t = s.size
    if q < 2 or t < q + 1 or not np.isfinite(s).all():
        return None
    diffs1 = np.diff(s)
    mu = float(np.mean(diffs1))
    var1 = float(np.sum((diffs1 - mu) ** 2)) / (t - 1)
    if var1 == 0.0:
        return None
    diffs_q = s[q:] - s[:-q]
    m = q * (t - q + 1) * (1.0 - q / t)  # Lo-MacKinlay unbiased normalizer
    if m <= 0.0:
        return None
    var_q = float(np.sum((diffs_q - q * mu) ** 2)) / m
    vr = var_q / var1
    return vr if math.isfinite(vr) else None


def zscore(spread: FloatArray, lookback: int = 20) -> float | None:
    """Standardized distance of the CURRENT spread from its trailing-`lookback`
    history — the bars BEFORE it, so a fresh extreme is measured against established
    normal rather than distorting its own benchmark (a spread sitting on its own
    window inflates that window's σ and saturates its z). The live entry signal:
    long the cheap leg when z ≤ −z_entry. None when the trailing window has no
    variance or there are fewer than lookback+1 bars."""
    s = np.asarray(spread, dtype=float)
    if s.size < lookback + 1 or lookback < 2 or not np.isfinite(s).all():
        return None
    window = s[-(lookback + 1) : -1]  # the `lookback` bars before the current
    mu = float(np.mean(window))
    sd = float(np.std(window, ddof=1))
    if sd == 0.0 or not math.isfinite(sd):
        return None
    z = (float(s[-1]) - mu) / sd
    return z if math.isfinite(z) else None


def stationarity_adf(spread: FloatArray) -> tuple[float, float] | None:
    """Augmented Dickey-Fuller (statsmodels, AIC lag selection, constant term): returns
    (adf_stat, p_value). The lag augmentation absorbs serial correlation in the spread's
    increments that the plain-DF t-stat cannot — fewer false 'stationary' calls at the
    borderline. None on degenerate input or if statsmodels is unavailable.

    CAVEAT (quant-verifier F1, 2026-08-15): adfuller's p-value uses UNIVARIATE-DF (MacKinnon)
    critical values, which are anti-conservative for a FITTED spread residual — β estimation
    consumes degrees of freedom, so the true cointegration CVs are more stringent (à la
    Engle-Granger). Partly why the adf path is a wider net (23 vs 8). Fine while adf is a
    non-default cross-check that mints NO signal; **switch to Engle-Granger cointegration CVs
    (or tighten the gate) before adf ever gates a real signal — a 6.5b precondition.**"""
    s = np.asarray(spread, dtype=float)
    if s.size < MIN_OBS or not np.isfinite(s).all() or float(np.var(s)) == 0.0:
        return None
    try:
        from statsmodels.tsa.stattools import adfuller

        stat, pval = adfuller(s, regression="c", autolag="AIC")[:2]
    except (ImportError, ValueError, np.linalg.LinAlgError):
        return None
    if not (math.isfinite(stat) and math.isfinite(pval)):
        return None
    return float(stat), float(pval)


def hedge_ratio_johansen(a: FloatArray, b: FloatArray) -> tuple[float, float] | None:
    """Symmetric hedge ratio from the Johansen cointegrating vector (statsmodels) —
    order-independent and more robust than the two-step OLS β (which differs A-on-B vs
    B-on-A). Returns (alpha, beta) with alpha = mean of the spread a−β·b (Johansen has no
    intercept, so we centre the spread). None on failure/degenerate input."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.shape != b.shape or a.size < MIN_OBS:
        return None
    if not (np.isfinite(a).all() and np.isfinite(b).all()):
        return None
    if float(np.var(a)) == 0.0 or float(np.var(b)) == 0.0:
        return None
    try:
        from statsmodels.tsa.vector_ar.vecm import coint_johansen

        evec = coint_johansen(np.column_stack([a, b]), det_order=0, k_ar_diff=1).evec[:, 0]
    except (ImportError, ValueError, np.linalg.LinAlgError):
        return None
    if not np.isfinite(evec).all() or evec[0] == 0.0:
        return None
    beta = float(-evec[1] / evec[0])
    if not math.isfinite(beta):
        return None
    alpha = float(np.mean(a - beta * b))  # centre the spread (Johansen has no intercept)
    return alpha, beta


def _notional_plausible(beta: float, a: FloatArray, b: FloatArray) -> bool:
    """The two legs' dollar exposures are within MAX_NOTIONAL_IMBALANCE× — i.e. a dollar-
    neutral 1:β trade is actually balanced. Rejects fragile hedge ratios (β from a raw-level
    Johansen fit can be ≈132) that aren't tradeable market-neutral. Medians for robustness."""
    med_a, med_b = float(np.median(a)), float(np.median(b))
    if med_a <= 0.0 or med_b <= 0.0:
        return False
    imbalance = abs(beta) * med_b / med_a
    return 1.0 / MAX_NOTIONAL_IMBALANCE <= imbalance <= MAX_NOTIONAL_IMBALANCE


def screen_pair(
    a: FloatArray,
    b: FloatArray,
    *,
    method: str = "df",
    z_lookback: int = 20,
) -> PairStat | None:
    """Full profile for one candidate pair, or None when the pair is unusable
    (misaligned, too short, no hedge fit, no mean reversion, degenerate variance).
    `method` picks the hedge ratio + stationarity test: "df" = OLS β + numpy plain-DF
    t-stat (zero-dep, default); "adf" = Johansen β + statsmodels Augmented-DF p-value
    (more rigorous). None is the honest 'not a pair' — never a fabricated number."""
    if method not in ("df", "adf"):
        raise ValueError(f"unknown method {method!r}; expected 'df' or 'adf'")
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    cleaned = _finite_2d(a, b)
    if cleaned is None:
        return None
    a2, b2 = cleaned
    hr = hedge_ratio_johansen(a2, b2) if method == "adf" else hedge_ratio(a2, b2)
    if hr is None:
        return None
    alpha, beta = hr
    if not _notional_plausible(beta, a2, b2):  # implausible hedge ratio → not market-neutral
        return None
    spread = a2 - (alpha + beta * b2)
    mr = mean_reversion(spread)  # numpy DF t-stat + OU half-life (always — record + horizon)
    if mr is None:
        return None
    _lam, t_stat, half_life = mr
    adf_stat: float | None = None
    adf_pvalue: float | None = None
    if method == "adf":
        adf = stationarity_adf(spread)
        if adf is None:
            return None
        adf_stat, adf_pvalue = adf
    vr = variance_ratio(spread, q=2)
    if vr is None:
        return None
    z = zscore(spread, lookback=z_lookback)
    if z is None:
        return None
    return PairStat(
        alpha=alpha,
        beta=beta,
        half_life=half_life,
        df_tstat=t_stat,
        variance_ratio=vr,
        zscore=z,
        n=int(a2.size),
        spread_mean=float(np.mean(spread)),
        spread_std=float(np.std(spread, ddof=1)),
        method=method,
        adf_stat=adf_stat,
        adf_pvalue=adf_pvalue,
    )


def is_candidate(stat: PairStat) -> bool:
    """Policy gate: statistically-significant stationarity AND a tradeable reversion
    horizon (half-life in [MIN, MAX]). Stationarity uses the ADF p-value on the adf path,
    else the plain-DF t-stat."""
    horizon = MIN_HALF_LIFE <= stat.half_life <= MAX_HALF_LIFE
    if stat.method == "adf":
        return horizon and stat.adf_pvalue is not None and stat.adf_pvalue <= ADF_PVALUE_5PCT
    return horizon and stat.df_tstat <= DF_CRIT_5PCT
