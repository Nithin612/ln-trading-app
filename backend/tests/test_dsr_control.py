"""H8 — the negative control on our own deflated-Sharpe bar, as a standing test.

`docs/analysis/dsr-negative-control-<date>.md` is a snapshot; this file is the guard. It
fails if `deflated_sharpe.py` ever drifts into being either too permissive (noise clears)
or unable to accept a genuine edge.

The second half matters as much as the first. H8 as written in `quant-agent-findings.md`
only asks whether the bar rejects noise — but **a bar that rejects everything passes that
trivially**, and ours currently rejects every real gate we have. A specificity test alone
would have gone green on a bar that had silently become useless, which is precisely the
class of hollow coverage `.claude/rules/testing.md` warns about.

Deterministic: every test seeds its own `random.Random`.
"""

from __future__ import annotations

import math
import random

import pytest
from app.services import deflated_sharpe as ds
from app.services import dsr_control as ctrl

#: A fat-tailed, negatively skewed stand-in for the paper book (kurtosis ≈ 11 in reality).
#: Built explicitly rather than sampled so failures reproduce and reviewers can see the shape.
_BOOK: list[float] = (
    [-2200.0, -1800.0, -1500.0, -1200.0, -900.0, -700.0, -500.0, -300.0] * 4
    + [200.0, 350.0, 500.0, 700.0, 900.0, 1200.0, 1600.0, 2100.0] * 4
    + [-9000.0, -7000.0, 6500.0, 8000.0]  # the tails that PSR is supposed to charge for
)


def _rng() -> random.Random:
    return random.Random(90210)


class TestHelpers:
    def test_centered_removes_the_edge_but_not_the_shape(self) -> None:
        c = ctrl.centered(_BOOK)
        m_raw, m_c = ds.moments(_BOOK), ds.moments(c)
        assert m_raw is not None and m_c is not None
        assert m_c.mean == pytest.approx(0.0, abs=1e-9)
        # sd, skew and kurtosis must survive: a Gaussian null would flatter a bar that
        # explicitly penalises skew and fat tails.
        assert m_c.stdev == pytest.approx(m_raw.stdev, rel=1e-12)
        assert m_c.skew == pytest.approx(m_raw.skew, rel=1e-12)
        assert m_c.kurtosis == pytest.approx(m_raw.kurtosis, rel=1e-12)

    def test_shifted_to_sharpe_plants_the_edge_exactly(self) -> None:
        s = ctrl.shifted_to_sharpe(ctrl.centered(_BOOK), 0.42)
        m = ds.moments(s)
        assert m is not None
        assert m.sharpe == pytest.approx(0.42, abs=1e-9)

    def test_shift_leaves_dispersion_and_shape_untouched(self) -> None:
        base = ctrl.centered(_BOOK)
        m0, m1 = ds.moments(base), ds.moments(ctrl.shifted_to_sharpe(base, 0.8))
        assert m0 is not None and m1 is not None
        assert m1.stdev == pytest.approx(m0.stdev, rel=1e-12)
        assert m1.skew == pytest.approx(m0.skew, rel=1e-9)
        assert m1.kurtosis == pytest.approx(m0.kurtosis, rel=1e-9)

    def test_resample_is_deterministic_under_a_seed(self) -> None:
        a = ctrl.resample(_BOOK, 50, random.Random(7))
        b = ctrl.resample(_BOOK, 50, random.Random(7))
        assert a == b


class TestSpecificity:
    """The bar must reject what carries no information."""

    def test_random_partitions_of_the_real_book_do_not_clear(self) -> None:
        r = ctrl.random_partition_rate(_BOOK, block_frac=0.22, sims=200, rng=_rng())
        assert r.verdict_ok, r.note
        assert r.rate <= 0.05

    def test_best_of_twenty_pure_noise_candidates_does_not_clear(self) -> None:
        """The selection we actually perform: run several gates, judge the best-looking.

        This is the failure mode that cost us the regime gate and the R:R floor, so it is
        the arm that matters. Under a true-zero-edge null it must fool the bar no more
        often than the 5% the bar is designed to allow."""
        r = ctrl.best_of_trials_rate(_BOOK, n=78, sims=200, rng=_rng())
        assert r.verdict_ok, r.note
        assert r.rate <= 0.05


class TestPower:
    """The bar must accept what does carry an edge — otherwise 'fails the bar' is
    uninformative and every readiness banner is theatre."""

    def test_a_large_real_edge_is_accepted(self) -> None:
        p = ctrl.power_rate(_BOOK, n=78, true_sharpe=0.90, sims=200, rng=_rng())
        assert p >= 0.80, f"the bar could not see a true per-trade Sharpe of 0.90 (power {p:.1%})"

    def test_power_is_monotone_in_the_size_of_the_planted_edge(self) -> None:
        rng = _rng()
        ps = [
            ctrl.power_rate(_BOOK, n=78, true_sharpe=s, sims=150, rng=rng)
            for s in (0.10, 0.45, 0.90)
        ]
        assert ps[0] <= ps[1] <= ps[2], ps

    def test_a_zero_edge_is_essentially_never_accepted(self) -> None:
        p = ctrl.power_rate(_BOOK, n=78, true_sharpe=0.0, sims=200, rng=_rng())
        assert p <= 0.05, f"the bar accepted a zero edge {p:.1%} of the time"


class TestImpliedHurdle:
    """The bar restated as a t-statistic — the number that makes it arguable."""

    def test_hurdle_is_near_three_point_six_and_flat_in_n(self) -> None:
        hs = [ctrl.implied_t_hurdle(n) for n in (50, 100, 400, 1000)]
        for h in hs:
            assert 3.0 < h < 4.5, hs
        # It barely moves with sample size — which is WHY MinTRL keeps returning None:
        # the benchmark falls as 1/√n while the required t stays put, so more data does
        # not lower the bar, it only sharpens an estimate that must be large regardless.
        assert max(hs) - min(hs) < 0.3, hs

    def test_hurdle_agrees_with_where_power_actually_turns_on(self) -> None:
        """A canary tying the algebra to the simulation: an edge comfortably above the
        hurdle is seen, one comfortably below is not."""
        n = 78
        hurdle_sharpe = ctrl.implied_t_hurdle(n) / math.sqrt(n)
        rng = _rng()
        below = ctrl.power_rate(_BOOK, n=n, true_sharpe=hurdle_sharpe * 0.5, sims=150, rng=rng)
        above = ctrl.power_rate(_BOOK, n=n, true_sharpe=hurdle_sharpe * 1.6, sims=150, rng=rng)
        assert below <= 0.05, below
        assert above >= 0.80, above


class TestTheBarWouldFailIfItBroke:
    """Canaries: these assert the tests above can actually go red."""

    def test_a_permissive_bar_is_caught_by_the_specificity_arm(self) -> None:
        """With confidence dropped to 1%, noise clears constantly. If this ever stops
        being true, the specificity arm has stopped measuring anything."""
        rng = _rng()
        cleared = 0
        pool = ctrl.centered(_BOOK)
        for _ in range(150):
            s = ctrl.resample(pool, 78, rng)
            r = ds.deflated_sharpe(s, trials=20, confidence=0.01)
            if r and r.passes:
                cleared += 1
        assert cleared / 150 > 0.05

    def test_an_impossible_bar_is_caught_by_the_power_arm(self) -> None:
        """A bar demanding 99.99999% confidence rejects even a huge real edge — the 'bar
        that can never say yes' this suite exists to detect.

        Note what does NOT work as a break, because it is worth knowing: cranking `trials`
        does not. E[max SR] grows only as √(2·ln N), so even 10,000 trials leaves the
        benchmark at ≈0.44 and a true Sharpe of 0.90 still clears ~99% of the time. The
        confidence threshold is the parameter that actually makes the bar unreachable."""
        p = ctrl.power_rate(
            _BOOK, n=78, true_sharpe=0.90, confidence=0.9999999, sims=120, rng=_rng()
        )
        assert p < 0.80

    def test_more_trials_alone_does_not_make_the_bar_impossible(self) -> None:
        """Pins the observation above, because it is counter-intuitive and someone will
        otherwise 'fix' the trials count expecting it to tighten the bar meaningfully."""
        p = ctrl.power_rate(_BOOK, n=78, true_sharpe=0.90, trials=10_000, sims=120, rng=_rng())
        assert p >= 0.80, (
            "raising trials 500x was expected to leave a large edge detectable; "
            f"got power {p:.1%}"
        )
