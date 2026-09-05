"""Deflated Sharpe Ratio + MinTRL (2026-09-03).

Built after two gates were promoted on favourable evidence and reverted within a week. The
missing instrument was a bar that accounts for HOW MANY things we have tried — search
enough variants and the best looks good by luck alone.
"""

import math
from statistics import NormalDist

from app.services import deflated_sharpe as ds


class TestMoments:
    def test_too_few_observations_is_none(self) -> None:
        assert ds.moments([0.1, 0.2]) is None

    def test_zero_volatility_is_none(self) -> None:
        """A constant series has an infinite Sharpe; refuse rather than divide by zero."""
        assert ds.moments([0.05] * 10) is None

    def test_sharpe_is_mean_over_stdev(self) -> None:
        m = ds.moments([1.0, 2.0, 3.0, 4.0])
        assert m is not None
        # mean 2.5, sample sd = sqrt(5/3) ≈ 1.29099
        assert abs(m.mean - 2.5) < 1e-12
        assert abs(m.stdev - math.sqrt(5 / 3)) < 1e-12
        assert abs(m.sharpe - 2.5 / math.sqrt(5 / 3)) < 1e-12

    def test_kurtosis_is_pearson_not_excess(self) -> None:
        """Normal ≈ 3.0, not ≈ 0.0 — the PSR formula expects Pearson."""
        xs = [NormalDist(0, 1).inv_cdf((i + 0.5) / 400) for i in range(400)]
        m = ds.moments(xs)
        assert m is not None
        assert 2.5 < m.kurtosis < 3.2


class TestPsr:
    def test_matches_the_closed_form(self) -> None:
        """SR=0.5, n=100, normal moments: denom = 1 + (3−1)/4·0.25 = 1.125,
        z = 0.5·√99/√1.125."""
        m = ds.Moments(n=100, mean=0.5, stdev=1.0, skew=0.0, kurtosis=3.0, sharpe=0.5)
        expected = NormalDist().cdf(0.5 * math.sqrt(99) / math.sqrt(1.125))
        assert abs(ds.psr(m, 0.0) - expected) < 1e-9

    def test_negative_skew_and_fat_tails_reduce_confidence(self) -> None:
        """The reason this metric is right for us: our losses cluster in a few large
        trades, and that must cost confidence rather than being ignored."""
        clean = ds.Moments(n=60, mean=0.2, stdev=1.0, skew=0.0, kurtosis=3.0, sharpe=0.2)
        nasty = ds.Moments(n=60, mean=0.2, stdev=1.0, skew=-1.5, kurtosis=9.0, sharpe=0.2)
        assert ds.psr(nasty, 0.0) < ds.psr(clean, 0.0)

    def test_more_observations_raise_confidence(self) -> None:
        small = ds.Moments(n=20, mean=0.2, stdev=1.0, skew=0.0, kurtosis=3.0, sharpe=0.2)
        large = ds.Moments(n=200, mean=0.2, stdev=1.0, skew=0.0, kurtosis=3.0, sharpe=0.2)
        assert ds.psr(large, 0.0) > ds.psr(small, 0.0)


class TestExpectedMaxSharpe:
    def test_one_trial_needs_no_deflation(self) -> None:
        assert ds.expected_max_sharpe(1, 0.1) == 0.0

    def test_grows_with_the_number_of_trials(self) -> None:
        """The core of the bar: trying more things raises the score luck alone produces."""
        vals = [ds.expected_max_sharpe(n, 0.1) for n in (2, 5, 20, 100)]
        assert vals == sorted(vals)
        assert all(v > 0 for v in vals)

    def test_zero_dispersion_needs_no_deflation(self) -> None:
        assert ds.expected_max_sharpe(50, 0.0) == 0.0


class TestMinTrl:
    def test_none_when_not_ahead_of_the_benchmark(self) -> None:
        """No amount of extra data rescues a candidate that is not ahead — saying
        'keep accruing' there would be false comfort."""
        m = ds.Moments(n=30, mean=0.01, stdev=1.0, skew=0.0, kurtosis=3.0, sharpe=0.01)
        assert ds.min_track_record_length(m, benchmark_sharpe=0.4) is None

    def test_shrinks_as_the_edge_grows(self) -> None:
        weak = ds.Moments(n=30, mean=0.15, stdev=1.0, skew=0.0, kurtosis=3.0, sharpe=0.15)
        strong = ds.Moments(n=30, mean=0.60, stdev=1.0, skew=0.0, kurtosis=3.0, sharpe=0.60)
        a = ds.min_track_record_length(weak, 0.05)
        b = ds.min_track_record_length(strong, 0.05)
        assert a is not None and b is not None and b < a


class TestDeflatedSharpe:
    def test_a_thin_sample_does_not_clear_and_says_how_much_is_needed(self) -> None:
        xs = [0.05 + 0.4 * math.sin(i) for i in range(25)]
        r = ds.deflated_sharpe(xs, trials=20)
        assert r is not None and r.passes is False
        assert ("needs ≈" in r.note) or ("does not exceed" in r.note)

    def test_more_trials_make_the_bar_harder(self) -> None:
        xs = [0.10 + 0.3 * math.sin(i) for i in range(120)]
        few = ds.deflated_sharpe(xs, trials=2)
        many = ds.deflated_sharpe(xs, trials=200)
        assert few is not None and many is not None
        assert many.benchmark_sharpe > few.benchmark_sharpe
        assert many.dsr < few.dsr

    def test_unassessable_sample_returns_none(self) -> None:
        assert ds.deflated_sharpe([0.1, 0.2]) is None
        assert ds.deflated_sharpe([0.1] * 10) is None

    def test_render_carries_the_numbers_not_just_the_verdict(self) -> None:
        """The record must be self-contained — a verdict without its data cannot be
        re-judged months later (user request 2026-09-03)."""
        xs = [0.05 + 0.4 * math.sin(i) for i in range(40)]
        lines = "\n".join(ds.render_lines(ds.deflated_sharpe(xs), label="test gate"))
        for token in ("n=40", "Sharpe", "skew", "kurtosis", "P(true Sharpe > 0)", "trials"):
            assert token in lines
        assert "optimistic" in lines, "the independence caveat must ship with the number"

    def test_render_handles_none(self) -> None:
        assert "not assessable" in "\n".join(ds.render_lines(None, label="x"))


class TestT11PinnedAgainstKnownGood:
    """T11 — pin PSR/DSR to independently-derived values so the kurtosis convention can
    never silently flip.

    Background: cross-checking this module against QuantStats (the best-known reference in
    the field) found **QuantStats wrong and us right**. Its PSR feeds pandas' **excess**
    kurtosis into a formula that expects **Pearson**, which turns the `SR²` coefficient
    from `+0.5` into `−0.25` and systematically **overstates** PSR. That check was manual
    and one-off; these make it permanent, and every expectation below is written out from
    Bailey & López de Prado rather than by calling the code under test.
    """

    def test_the_sr_squared_coefficient_is_plus_half_on_a_normal_series(self) -> None:
        """The single number the whole bug turns on. Pearson kurtosis 3.0 gives
        (3−1)/4 = **+0.5**; excess kurtosis 0.0 would give (0−1)/4 = **−0.25**."""
        pearson_coeff = (3.0 - 1.0) / 4.0
        excess_coeff = (0.0 - 1.0) / 4.0
        assert pearson_coeff == 0.5
        assert excess_coeff == -0.25

        sr = 0.8
        m = ds.Moments(n=50, mean=0.8, stdev=1.0, skew=0.0, kurtosis=3.0, sharpe=sr)
        # Denominator written out longhand, not taken from the module.
        denom_sq = 1.0 - 0.0 * sr + pearson_coeff * sr**2
        expected = NormalDist().cdf(sr * math.sqrt(49) / math.sqrt(denom_sq))
        assert abs(ds.psr(m, 0.0) - expected) < 1e-12

    def test_the_quantstats_convention_would_flip_a_decision(self) -> None:
        """⭐ Not merely "a different number" — a different VERDICT.

        Passing EXCESS kurtosis where Pearson is expected shrinks the denominator and
        inflates PSR. At n=10, SR=0.585 the correct PSR is **0.9476 (fails a 95% bar)**
        while the QuantStats convention reports **0.9668 (clears it)**. Chosen precisely
        because a test that only asserts "bigger" would pass just as happily in the
        saturated region where both round to 1.0 and nothing is at stake.
        """
        sr = 0.585
        correct = ds.Moments(n=10, mean=sr, stdev=1.0, skew=0.0, kurtosis=3.0, sharpe=sr)
        as_if_excess = ds.Moments(
            n=10, mean=sr, stdev=1.0, skew=0.0, kurtosis=0.0, sharpe=sr
        )
        got, buggy = ds.psr(correct, 0.0), ds.psr(as_if_excess, 0.0)
        assert got < 0.95 <= buggy
        assert abs(got - 0.94757) < 1e-4
        assert abs(buggy - 0.96677) < 1e-4

    def test_the_seam_moments_feeds_psr_pearson(self) -> None:
        """The bug can only reach `psr` through `moments`, so pin the actual handoff — a
        unit test of either half alone would not have caught QuantStats' version either."""
        xs = [NormalDist(0, 1).inv_cdf((i + 0.5) / 2000) for i in range(2000)]
        m = ds.moments(xs)
        assert m is not None
        assert 2.9 < m.kurtosis < 3.1, "moments must emit PEARSON kurtosis"
        # And that value, fed through, reproduces the +0.5-coefficient denominator.
        denom_sq = 1.0 - m.skew * m.sharpe + ((m.kurtosis - 1.0) / 4.0) * m.sharpe**2
        expected = NormalDist().cdf(m.sharpe * math.sqrt(m.n - 1) / math.sqrt(denom_sq))
        assert abs(ds.psr(m, 0.0) - expected) < 1e-12

    def test_expected_max_sharpe_pinned(self) -> None:
        """E[max SR] over N zero-skill trials, written out from the Bailey–López de Prado
        approximation with the Euler–Mascheroni constant."""
        euler = 0.5772156649015329
        trials, sd = 20, 0.25
        a = NormalDist().inv_cdf(1.0 - 1.0 / trials)
        b = NormalDist().inv_cdf(1.0 - 1.0 / (trials * math.e))
        expected = sd * ((1.0 - euler) * a + euler * b)
        assert abs(ds.expected_max_sharpe(trials, sd) - expected) < 1e-9
        # Sanity: the 20-trial bar on our own trial dispersion is a real hurdle, not ~0.
        assert 0.2 < ds.expected_max_sharpe(20, 0.25) < 0.6

    def test_min_trl_pinned(self) -> None:
        """MinTRL = 1 + denom² · (z_conf / (SR − SR*))², longhand."""
        sr = 0.5
        m = ds.Moments(n=40, mean=0.5, stdev=1.0, skew=0.0, kurtosis=3.0, sharpe=sr)
        bench = 0.2
        denom_sq = 1.0 - 0.0 * sr + ((3.0 - 1.0) / 4.0) * sr**2
        z = NormalDist().inv_cdf(0.95)
        expected = 1.0 + denom_sq * (z / (sr - bench)) ** 2
        got = ds.min_track_record_length(m, bench, 0.95)
        assert got is not None
        assert abs(got - expected) < 1e-9

    def test_end_to_end_dsr_on_a_fixed_series(self) -> None:
        """The whole pipeline pinned on a deterministic series, so a refactor anywhere in
        moments → E[max] → psr → dsr moves a number a human has to look at."""
        xs = [0.1 * ((i % 7) - 3) + 0.05 for i in range(120)]
        r = ds.deflated_sharpe(xs, trials=20)
        assert r is not None
        m = r.moments
        # Recompute the reported DSR longhand from the reported moments + benchmark.
        denom_sq = 1.0 - m.skew * m.sharpe + ((m.kurtosis - 1.0) / 4.0) * m.sharpe**2
        z = (m.sharpe - r.benchmark_sharpe) * math.sqrt(m.n - 1) / math.sqrt(denom_sq)
        assert abs(r.dsr - NormalDist().cdf(z)) < 1e-12
        assert r.trials == 20
        # A near-zero-Sharpe series must NOT clear a 20-trial bar.
        assert r.passes is False
