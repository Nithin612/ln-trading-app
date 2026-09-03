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
