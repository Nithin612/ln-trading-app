"""Pair-screen cointegration / mean-reversion math (Phase 6.5a).

Pure numpy — no DB. Statistical estimators (variance ratio, Dickey-Fuller t-stat,
OU half-life) are validated against series with KNOWN properties: an AR(1) is
mean-reverting with a computable half-life; a random walk is not. Randomness is
seeded so every failure reproduces exactly (testing rules)."""

from __future__ import annotations

import math

import numpy as np
import pytest
from app.services import pair_screen as ps

SEED = 20260814


def _rng(seed: int = SEED) -> np.random.Generator:
    return np.random.default_rng(seed)


def _ar1(rng: np.random.Generator, phi: float, n: int, sigma: float = 1.0) -> np.ndarray:
    s = np.zeros(n)
    for t in range(1, n):
        s[t] = phi * s[t - 1] + rng.normal(0.0, sigma)
    return s


def _rwalk(rng: np.random.Generator, n: int, drift: float = 0.0) -> np.ndarray:
    return np.cumsum(rng.normal(drift, 1.0, n))


# --------------------------------------------------------------------------- #
# hedge ratio                                                                 #
# --------------------------------------------------------------------------- #


def test_hedge_ratio_recovers_known_alpha_beta_exactly() -> None:
    b = _rwalk(_rng(), 500) + 100.0
    got = ps.hedge_ratio(5.0 + 2.0 * b, b)
    assert got is not None
    alpha, beta = got
    assert abs(alpha - 5.0) < 1e-6 and abs(beta - 2.0) < 1e-6


def test_hedge_ratio_none_when_b_flat() -> None:
    assert ps.hedge_ratio(np.arange(100.0), np.ones(100)) is None


# --------------------------------------------------------------------------- #
# variance ratio (code correctness, isolated from OLS)                        #
# --------------------------------------------------------------------------- #


def test_variance_ratio_below_one_for_mean_reverting_ar1() -> None:
    # AR(1) phi=0.9 → theory VR(2) = (1+phi)/2 = 0.95
    vr = ps.variance_ratio(_ar1(_rng(), 0.9, 2000), q=2)
    assert vr is not None and 0.88 < vr < 1.0


def test_variance_ratio_near_one_for_random_walk() -> None:
    vr = ps.variance_ratio(_rwalk(_rng(), 4000), q=2)
    assert vr is not None and 0.92 < vr < 1.08


# --------------------------------------------------------------------------- #
# Dickey-Fuller mean-reversion stat + OU half-life                            #
# --------------------------------------------------------------------------- #


def test_mean_reversion_significant_with_correct_half_life_for_ar1() -> None:
    mr = ps.mean_reversion(_ar1(_rng(), 0.9, 2000))
    assert mr is not None
    lam, tstat, hl = mr
    assert lam < 0.0  # mean-reverting
    assert tstat < ps.DF_CRIT_5PCT  # statistically significant stationarity
    hl_true = -math.log(2) / math.log(0.9)  # ≈ 6.58 bars
    assert abs(hl - hl_true) < 2.0


def test_mean_reversion_not_significant_for_random_walk() -> None:
    # a unit-root series must NOT pass the DF 5% bar (None when λ≥0, else t-stat above crit)
    mr = ps.mean_reversion(_rwalk(_rng(), 3000))
    assert mr is None or mr[1] > ps.DF_CRIT_5PCT


def test_mean_reversion_tstat_matches_independent_ols_recompute() -> None:
    """CANARY on the subtlest line — the DF standard error. Recompute λ and its t-stat
    by an independent OLS route (normal equations via solve, not lstsq) and require the
    module to match to ~1e-9, so any future change to the SE formula breaks this test."""
    s = _ar1(_rng(), 0.85, 800).astype(float)
    got = ps.mean_reversion(s)
    assert got is not None
    lam_mod, t_mod, _hl = got
    s_lag, delta = s[:-1], s[1:] - s[:-1]
    x = np.column_stack([s_lag, np.ones_like(s_lag)])
    coef = np.linalg.solve(x.T @ x, x.T @ delta)  # normal equations (different path)
    resid = delta - x @ coef
    sigma2 = float(resid @ resid) / (s_lag.size - 2)
    se_lam = math.sqrt(sigma2 * float(np.linalg.inv(x.T @ x)[0, 0]))
    t_expected = float(coef[0]) / se_lam
    assert abs(lam_mod - float(coef[0])) < 1e-12
    assert abs(t_mod - t_expected) < 1e-9


# --------------------------------------------------------------------------- #
# z-score (the live entry signal)                                             #
# --------------------------------------------------------------------------- #


def test_zscore_measures_current_bar_against_trailing_history() -> None:
    # trailing window ~ alternating ±1 (mean 0, σ ≈ 1); the current bar at +3 → z ≈ +3.
    # The current bar is EXCLUDED from the benchmark window, so it is not dampened.
    s = np.zeros(30)
    s[:-1] = np.tile([1.0, -1.0], 15)[:29]
    s[-1] = 3.0
    z = ps.zscore(s, lookback=20)
    assert z is not None and 2.5 < z < 3.3


def test_zscore_none_on_flat_window() -> None:
    assert ps.zscore(np.ones(50)) is None


# --------------------------------------------------------------------------- #
# screen_pair end-to-end                                                      #
# --------------------------------------------------------------------------- #


def test_screen_pair_accepts_clean_cointegration() -> None:
    # a, b share a dominant stochastic trend + independent stationary noise → a-b stationary
    rng = _rng()
    common = _rwalk(rng, 2000)
    a = 100.0 + common + _ar1(rng, 0.9, 2000, sigma=0.5)
    b = 50.0 + common + _ar1(rng, 0.9, 2000, sigma=0.5)
    stat = ps.screen_pair(a, b)
    assert stat is not None
    assert abs(stat.beta - 1.0) < 0.1  # recovered hedge ratio ~1
    assert stat.df_tstat < ps.DF_CRIT_5PCT  # significant stationarity
    assert ps.MIN_HALF_LIFE <= stat.half_life <= ps.MAX_HALF_LIFE
    assert ps.is_candidate(stat) is True


def test_screen_pair_rejects_independent_random_walks() -> None:
    rng = _rng()
    stat = ps.screen_pair(_rwalk(rng, 2000) + 50.0, _rwalk(rng, 2000) + 50.0)
    # either unusable (no mean reversion) or present-but-not-a-candidate
    assert stat is None or not ps.is_candidate(stat)


def test_screen_pair_none_on_degenerate_inputs() -> None:
    assert ps.screen_pair(np.arange(5.0), np.arange(5.0)) is None  # too short
    assert ps.screen_pair(np.ones(100), np.ones(100)) is None  # flat → no hedge
    mism = ps.screen_pair(np.arange(100.0), np.arange(50.0))  # misaligned lengths
    assert mism is None


def test_screen_pair_rejects_implausible_notional_imbalance() -> None:
    # Same common trend → cointegrated with β≈1, but a ~₹5000 vs b ~₹50 → 100× leg imbalance.
    # Statistically a "pair", economically un-hedgeable market-neutral → rejected by the guard.
    rng = _rng()
    common = _rwalk(rng, 1000)
    a = 5000.0 + common + _ar1(rng, 0.9, 1000, 0.5)
    b = 50.0 + common + _ar1(rng, 0.9, 1000, 0.5)
    assert ps.screen_pair(a, b) is None


def test_is_candidate_gate_thresholds() -> None:
    # CANARY: the gate is exactly (DF t-stat past 5% crit) AND (half-life in [MIN, MAX]).
    def stat(tstat: float, hl: float) -> ps.PairStat:
        return ps.PairStat(
            alpha=0.0,
            beta=1.0,
            half_life=hl,
            df_tstat=tstat,
            variance_ratio=0.9,
            zscore=0.0,
            n=500,
            spread_mean=0.0,
            spread_std=1.0,
        )

    assert ps.is_candidate(stat(-3.0, 10.0)) is True  # significant + tradeable horizon
    assert ps.is_candidate(stat(-2.0, 10.0)) is False  # not significant enough
    assert ps.is_candidate(stat(-5.0, ps.MAX_HALF_LIFE + 1)) is False  # reverts too slowly
    assert ps.is_candidate(stat(-5.0, ps.MIN_HALF_LIFE - 0.5)) is False  # reverts implausibly fast


# --------------------------------------------------------------------------- #
# ADF / Johansen path (statsmodels)                                           #
# --------------------------------------------------------------------------- #


def test_stationarity_adf_significant_for_ar1_not_for_random_walk() -> None:
    mr = ps.stationarity_adf(_ar1(_rng(), 0.9, 1000))
    assert mr is not None and mr[1] < 0.05  # p-value significant → stationary
    rw = ps.stationarity_adf(_rwalk(_rng(), 1000))
    assert rw is not None and rw[1] > 0.05  # unit root → not stationary


def test_hedge_ratio_johansen_recovers_beta() -> None:
    rng = _rng()
    common = _rwalk(rng, 1000)
    a = 100.0 + 2.0 * common + _ar1(rng, 0.9, 1000, 0.3)  # a ≈ 2·b + stationary → β≈2
    b = 50.0 + common + _ar1(rng, 0.9, 1000, 0.3)
    hr = ps.hedge_ratio_johansen(a, b)
    assert hr is not None
    _alpha, beta = hr
    assert abs(beta - 2.0) < 0.2


def test_screen_pair_adf_accepts_cointegration() -> None:
    rng = _rng()
    common = _rwalk(rng, 1000)
    a = 100.0 + common + _ar1(rng, 0.9, 1000, 0.5)
    b = 50.0 + common + _ar1(rng, 0.9, 1000, 0.5)
    stat = ps.screen_pair(a, b, method="adf")
    assert stat is not None
    assert stat.method == "adf" and stat.adf_pvalue is not None
    assert stat.adf_pvalue < ps.ADF_PVALUE_5PCT
    assert ps.is_candidate(stat) is True


def test_is_candidate_adf_gates_on_pvalue_not_df_tstat() -> None:
    # CANARY: on the adf path the gate is the ADF p-value — even a strong df_tstat is ignored.
    base = dict(
        alpha=0.0,
        beta=1.0,
        half_life=10.0,
        variance_ratio=0.9,
        zscore=0.0,
        n=500,
        spread_mean=0.0,
        spread_std=1.0,
        df_tstat=-9.0,
    )
    assert (
        ps.is_candidate(ps.PairStat(**base, method="adf", adf_stat=-4.0, adf_pvalue=0.01)) is True
    )
    assert (
        ps.is_candidate(ps.PairStat(**base, method="adf", adf_stat=-1.0, adf_pvalue=0.30)) is False
    )
    assert ps.is_candidate(ps.PairStat(**base, method="df")) is True  # df path uses df_tstat


def test_hedge_ratio_johansen_recovers_negative_beta() -> None:
    rng = _rng()
    common = _rwalk(rng, 1000)
    a = 100.0 - 2.0 * common + _ar1(rng, 0.9, 1000, 0.3)  # a ≈ −2·b + stationary → β≈−2
    b = 50.0 + common + _ar1(rng, 0.9, 1000, 0.3)
    hr = ps.hedge_ratio_johansen(a, b)
    assert hr is not None and abs(hr[1] - (-2.0)) < 0.2


def test_screen_pair_adf_rejects_non_pair() -> None:
    # a stationary on its own; b an unrelated random walk → no real hedge on the adf path either.
    rng = _rng()
    a = 7000.0 + _ar1(rng, 0.9, 1000, 5.0)
    b = 50.0 + _rwalk(rng, 1000)
    stat = ps.screen_pair(a, b, method="adf")
    assert stat is None or not ps.is_candidate(stat)


def test_screen_pair_raises_on_unknown_method() -> None:
    with pytest.raises(ValueError, match="unknown method"):
        ps.screen_pair(np.zeros(100), np.zeros(100), method="bogus")


def test_is_candidate_adf_none_pvalue_is_false() -> None:
    stat = ps.PairStat(
        alpha=0.0,
        beta=1.0,
        half_life=10.0,
        df_tstat=-9.0,
        variance_ratio=0.9,
        zscore=0.0,
        n=500,
        spread_mean=0.0,
        spread_std=1.0,
        method="adf",
        adf_stat=None,
        adf_pvalue=None,
    )
    assert ps.is_candidate(stat) is False
