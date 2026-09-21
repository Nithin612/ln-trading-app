"""Validation of the effective-spread estimators — item 17's gating step.

⭐ **This file is the reason the item-17 numbers can be believed at all.** Per
``instrument_self_validation``: an instrument never run against a known answer has not
been validated. Every test here plants a spread the estimator is not told about and
checks it is FOUND — and, per M64, that the number MOVES with the planted value rather
than merely failing to raise.

⭐⭐ **The validation changed the design twice before any real data was touched, which is
the whole argument for doing it first.**

1. **Corwin-Schultz cannot decide this question.** Its zero-spread null is linear in
   volatility — ~4.3 bps of pure artifact at 30 bps/bar, ~11.4 at 80 — and the
   pre-registered branch boundary is 5 bps. ⛔ **Pooling does not help: a bias is not
   noise.** It is kept only as a corroborating upper bound, and that is asserted here.
2. **A single-session Abdi-Ranaldo estimate is knife-edge.** Under a true zero spread
   about half of windows clamp to zero, so the cohort median sits exactly on the clamp
   boundary. Pooling to ``MIN_SESSIONS_FOR_STABILITY`` sessions fixes it.
"""

from __future__ import annotations

import random
import statistics

import pytest
from app.services.spread_estimators import (
    MIN_SESSIONS_FOR_STABILITY,
    Bar,
    abdi_ranaldo,
    abdi_ranaldo_sessions,
    calibrate,
    corwin_schultz,
    corwin_schultz_pair,
    corwin_schultz_sessions,
    proportional_to_half_spread_bps,
    simulate_session,
)

# Deterministic throughout: every draw is seeded, so a failure reproduces exactly.
_BARS_PER_SESSION = 75  # a 9:15-15:30 session in 5-minute bars
_SUBSTEPS = 12
_REPLICATIONS = 60


def _simulate_session(
    *, half_spread_bps: float, sigma_bar_bps: float, rng: random.Random
) -> list[Bar]:
    """Delegates to the library generator — the study calibrates its null with the SAME
    code these tests validate against, so the two can never drift apart (W2)."""
    return simulate_session(
        half_spread_bps=half_spread_bps,
        sigma_bar_bps=sigma_bar_bps,
        rng=rng,
        bars=_BARS_PER_SESSION,
        substeps=_SUBSTEPS,
    )


def _cohort(estimator, *, half_spread_bps: float, sigma_bar_bps: float) -> list[float]:
    """The pooled estimates a whole cohort of names would produce, in half-spread bps."""
    out: list[float] = []
    for i in range(_REPLICATIONS):
        rng = random.Random(90_000 + i * 13 + int(sigma_bar_bps))
        sessions = [
            _simulate_session(
                half_spread_bps=half_spread_bps, sigma_bar_bps=sigma_bar_bps, rng=rng
            )
            for _ in range(MIN_SESSIONS_FOR_STABILITY)
        ]
        value = estimator(sessions)
        if value is not None:
            out.append(proportional_to_half_spread_bps(value))
    return out


# ---------------------------------------------------------------- Abdi-Ranaldo


@pytest.mark.parametrize("planted", [5.0, 10.0, 25.0])
@pytest.mark.parametrize("sigma", [30.0, 80.0])
def test_abdi_ranaldo_recovers_a_planted_spread_at_every_volatility(
    planted: float, sigma: float
) -> None:
    """The cohort median recovers the planted half-spread within 10% and does so
    INDEPENDENTLY of volatility — the property that lets it decide the 5 bps boundary
    that Corwin-Schultz cannot."""
    median = statistics.median(
        _cohort(abdi_ranaldo_sessions, half_spread_bps=planted, sigma_bar_bps=sigma)
    )
    assert median == pytest.approx(planted, rel=0.10), (
        f"planted {planted} bps at sigma {sigma} bps/bar recovered as {median:.2f}"
    )


def test_abdi_ranaldo_zero_spread_null_is_zero_at_every_volatility() -> None:
    """⭐ The property Corwin-Schultz lacks: no spread reads as no spread, however
    volatile the series. Canary — this fails on an estimator that clamps per-pair instead
    of after the expectation, which biases every reading upward."""
    for sigma in (30.0, 80.0):
        median = statistics.median(
            _cohort(abdi_ranaldo_sessions, half_spread_bps=0.0, sigma_bar_bps=sigma)
        )
        assert median == pytest.approx(0.0, abs=0.5), (
            f"zero-spread null at sigma {sigma} read {median:.2f} bps"
        )


def test_abdi_ranaldo_zero_clamp_fraction_discriminates_spread_from_none() -> None:
    """The share of windows clamping to zero is an INDEPENDENT read on the same question:
    about half under a true zero spread, near none once a real spread is present. It is
    reported beside the median precisely because it does not share its failure mode."""

    def zero_share(planted: float) -> float:
        values = _cohort(abdi_ranaldo_sessions, half_spread_bps=planted, sigma_bar_bps=30.0)
        return sum(1 for v in values if v <= 1e-12) / len(values)

    assert zero_share(0.0) > 0.35
    assert zero_share(10.0) < 0.05


def test_abdi_ranaldo_median_moves_monotonically_with_the_planted_spread() -> None:
    """M64's lesson made executable: a metric that does not MOVE with what it reports is
    worthless, so movement is asserted, not assumed."""
    medians = [
        statistics.median(_cohort(abdi_ranaldo_sessions, half_spread_bps=p, sigma_bar_bps=30.0))
        for p in (0.0, 5.0, 10.0, 25.0)
    ]
    assert medians == sorted(medians)
    assert medians[-1] - medians[0] > 20.0


def test_abdi_ranaldo_pooling_is_what_makes_the_low_end_resolvable() -> None:
    """⭐ The measured reason ``MIN_SESSIONS_FOR_STABILITY`` exists. At high volatility a
    ONE-session estimate of a planted 5 bps spread is badly short; pooled it is accurate.
    Pinned so the window cannot be quietly shortened."""
    rng_seeds = range(_REPLICATIONS)
    single = []
    for i in rng_seeds:
        rng = random.Random(90_000 + i * 13 + 80)
        single_value = abdi_ranaldo(
            _simulate_session(half_spread_bps=5.0, sigma_bar_bps=80.0, rng=rng)
        )
        if single_value is not None:
            single.append(proportional_to_half_spread_bps(single_value))
    pooled = _cohort(abdi_ranaldo_sessions, half_spread_bps=5.0, sigma_bar_bps=80.0)

    assert statistics.median(pooled) == pytest.approx(5.0, rel=0.10)
    assert statistics.median(single) < 4.5


# ------------------------------------------------------------- Corwin-Schultz


def test_corwin_schultz_null_is_linear_in_volatility_and_straddles_the_falsifier() -> None:
    """⛔⛔ The defect that disqualifies Corwin-Schultz from the branch decision.

    On a ZERO-spread series it reports a positive spread that scales with volatility, and
    at ordinary intraday volatility that artifact lands on top of the pre-registered 5 bps
    boundary. Pinned so nobody re-promotes the estimator for this purpose.
    """
    nulls = {
        sigma: statistics.median(
            _cohort(corwin_schultz_sessions, half_spread_bps=0.0, sigma_bar_bps=sigma)
        )
        for sigma in (30.0, 80.0)
    }
    assert nulls[30.0] < nulls[80.0]
    assert nulls[30.0] > 3.0, "the artifact at ordinary volatility must be material"
    assert nulls[80.0] > 8.0


def test_pooling_cannot_fix_corwin_schultz_because_a_bias_is_not_noise() -> None:
    """⭐ The contrast that justifies reporting the two estimators differently: pooling
    collapses Abdi-Ranaldo's sampling noise and leaves Corwin-Schultz's bias untouched."""
    cs_null = statistics.median(
        _cohort(corwin_schultz_sessions, half_spread_bps=0.0, sigma_bar_bps=30.0)
    )
    ar_null = statistics.median(
        _cohort(abdi_ranaldo_sessions, half_spread_bps=0.0, sigma_bar_bps=30.0)
    )
    assert cs_null > 3.0
    assert ar_null < 0.5


def test_corwin_schultz_still_recovers_spreads_far_above_its_own_null() -> None:
    """It is not broken — it is unusable NEAR THE BOUNDARY. Well above its artifact floor
    it tracks the planted value, which is why it is kept as a corroborating upper bound."""
    median = statistics.median(
        _cohort(corwin_schultz_sessions, half_spread_bps=25.0, sigma_bar_bps=30.0)
    )
    assert median == pytest.approx(25.0, rel=0.20)


# ----------------------------------------------------------------- unit level


def test_undefined_returns_none_never_zero() -> None:
    """``app/core/ratios``' rule: 'not assessable' and 'measured zero' must stay
    distinguishable. A zero here would read as 'no spread', which is a claim."""
    assert corwin_schultz_pair(Bar(0.0, 0.0, 0.0), Bar(1.0, 1.0, 1.0)) is None
    assert corwin_schultz([]) is None
    assert corwin_schultz([Bar(10.0, 9.0, 9.5)]) is None  # one bar forms no pair
    assert abdi_ranaldo([]) is None
    assert abdi_ranaldo_sessions([]) is None
    assert corwin_schultz_sessions([[], []]) is None


def test_a_degenerate_bar_is_flagged_not_silently_dropped() -> None:
    """Dropping ranless bars biases the estimate UP by discarding the quiet intervals, so
    they are kept and counted instead."""
    assert Bar(10.0, 10.0, 10.0).is_degenerate
    assert not Bar(10.0, 9.0, 9.5).is_degenerate


def test_a_gap_between_bars_clamps_corwin_schultz_to_zero() -> None:
    """⛔ The direction matters and it is the opposite of the intuitive one.

    A gap inflates the COMBINED range without inflating either bar's own range, driving
    alpha sharply negative — so the estimate clamps to zero and **understates**. That is
    the more dangerous direction, because a stock with no measurable spread looks cheap to
    trade. It is also why ``*_sessions`` exists: the unsafe pairing is unexpressible there.
    """
    contiguous = [Bar(101.0, 99.0, 100.0), Bar(101.5, 99.5, 100.5)]
    across_gap = [Bar(101.0, 99.0, 100.0), Bar(111.5, 109.5, 110.5)]
    near = corwin_schultz(contiguous)
    far = corwin_schultz(across_gap)
    assert near is not None and near > 0.0
    assert far == 0.0


def test_negative_estimates_clamp_to_zero_as_the_paper_specifies() -> None:
    """A range narrower than a zero-spread diffusion implies a negative spread, which is
    noise — not a measurement of a negative cost."""
    assert corwin_schultz_pair(Bar(101.0, 99.0, 100.0), Bar(111.5, 109.5, 110.5)) == 0.0


def test_proportional_converts_to_half_spread_bps() -> None:
    assert proportional_to_half_spread_bps(0.001) == pytest.approx(5.0)


# ------------------------------------------------- calibration at the cohort's own sigma


def test_corwin_schultz_null_at_the_measured_cohort_volatility_is_material() -> None:
    """⛔ The reading defect this pins: the report first quoted CS's null at 30 and 80
    bps/bar while the cohort's measured volatility is ~18, where the null is SMALLER. A
    reader comparing a measured 3.28 against 4.33 would conclude CS reads below its own
    null — the opposite of the truth. The study now calibrates at the measured sigma; this
    asserts that number is materially positive there, so the comparison is never skipped."""
    null = calibrate(sigma_bar_bps=18.0, replications=120)
    assert 1.5 < null.cs_median_bps < 4.0, null.cs_median_bps
    assert null.ar_median_bps == pytest.approx(0.0, abs=0.5)


def test_calibrate_is_deterministic_and_moves_with_the_planted_spread() -> None:
    """A calibration that did not move with its own input would make every null it reports
    meaningless (M64)."""
    a = calibrate(sigma_bar_bps=18.0, replications=80)
    b = calibrate(sigma_bar_bps=18.0, replications=80)
    assert a == b

    planted = calibrate(sigma_bar_bps=18.0, planted_half_bps=5.0, replications=80)
    assert planted.ar_median_bps > a.ar_median_bps + 3.0
    assert planted.cs_median_bps > a.cs_median_bps
    assert planted.ar_clamp_share < a.ar_clamp_share
