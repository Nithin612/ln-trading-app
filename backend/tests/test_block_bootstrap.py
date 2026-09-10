"""Moving-block bootstrap on a trade series — H1.

`deflated_sharpe` is parametric and assumes independence — its own stated weakness. Our
trades are not independent: concurrent positions in one book share a market move, so a bad
day is several correlated bad trades and an iid instrument reads that as several
independent pieces of evidence.

These pin the instrument itself, in the style H8 established for the DSR bar: does it
reject noise, does it accept a real edge, and — the property that justifies *blocks* rather
than an iid resample at all — does it actually widen when the series is autocorrelated.
"""

import math
import random
import statistics

import pytest
from app.services.block_bootstrap import (
    DEFAULT_SEED,
    MAX_DEGENERATE_SHARE,
    MIN_N,
    block_length,
    moving_block_bootstrap,
    newey_west_t,
    render_lines,
)


def _normal(n: int, mu: float, seed: int, sd: float = 1.0) -> list[float]:
    g = random.Random(seed)
    return [g.gauss(mu, sd) for _ in range(n)]


def _ar1(n: int, phi: float, seed: int, mu: float = 0.15) -> list[float]:
    """A series where a bad run clusters — the shape a shared book actually produces."""
    g = random.Random(seed)
    out: list[float] = []
    prev = 0.0
    for _ in range(n):
        prev = phi * prev + g.gauss(0, 1)
        out.append(mu + prev)
    return out


class TestBlockLength:
    def test_follows_the_cube_root_rate(self) -> None:
        # Hall-Horowitz-Jing. At the sizes this project has, L is 3-5: enough to keep a
        # cluster together, not so much that the resample is one block.
        assert block_length(8) == 2
        assert block_length(20) == 3
        assert block_length(44) == 4
        assert block_length(65) == 5

    def test_clamped_to_the_series(self) -> None:
        assert block_length(1) == 1
        assert block_length(0) == 1


class TestRefusals:
    """Absence is the honest answer — never a fabricated interval."""

    def test_too_few_observations(self) -> None:
        assert moving_block_bootstrap(_normal(MIN_N - 1, 0.5, 1)) is None

    def test_zero_variance_series(self) -> None:
        assert moving_block_bootstrap([0.3] * 40) is None

    def test_degenerate_resamples_are_refused_not_silently_dropped(self) -> None:
        """⭐ The module's own failure mode, found while validating it.

        43 identical trades plus one −40 outlier produces zero-variance resamples whenever
        the outlier is not drawn — 76% of them. Dropping those silently leaves only the
        draws that CONTAIN the outlier, so the reported "interval" describes a filtered
        subpopulation and reads as if the negative sign were robust. It is one trade.
        """
        series = [0.2] * 43 + [-40.0]
        assert moving_block_bootstrap(series) is None
        # Canary on the old behaviour: if degenerate draws are kept and simply skipped,
        # a result comes back at all — and it looks confident.
        kept = [s for s in _sharpes_of_resamples(series) if s is not None]
        assert len(kept) / 2000 < 1 - MAX_DEGENERATE_SHARE, (
            "this series must be mostly-degenerate, or the test proves nothing"
        )

    def test_a_healthy_series_reports_no_degeneracy(self) -> None:
        r = moving_block_bootstrap(_normal(44, 0.5, 3))
        assert r is not None
        assert r.degenerate_share == 0.0


def _sharpes_of_resamples(series: list[float]) -> list[float | None]:
    """Re-run the resampling loop with the refusal removed, to show the old path."""
    import math
    import statistics

    n = len(series)
    length = block_length(n)
    n_blocks = n - length + 1
    k = math.ceil(n / length)
    rng = random.Random(DEFAULT_SEED)
    out: list[float | None] = []
    for _ in range(2000):
        sample: list[float] = []
        for _ in range(k):
            start = rng.randrange(n_blocks)
            sample.extend(series[start : start + length])
        s = sample[:n]
        sd = statistics.stdev(s)
        out.append(statistics.fmean(s) / sd if sd > 0 else None)
    return out


class TestDeterminism:
    def test_same_seed_same_answer(self) -> None:
        """A readiness number that moves between two runs on identical data is worse than
        no number — the banner would look like news."""
        a = moving_block_bootstrap(_normal(44, 0.3, 11))
        b = moving_block_bootstrap(_normal(44, 0.3, 11))
        assert a == b

    def test_a_different_draw_gives_a_similar_answer(self) -> None:
        """The result must be a property of the data, not of the seed."""
        xs = _normal(60, 0.4, 12)
        a = moving_block_bootstrap(xs, seed=1)
        b = moving_block_bootstrap(xs, seed=999)
        assert a is not None and b is not None
        assert a.p5 == pytest.approx(b.p5, abs=0.08)


class TestBlocksActuallyDoSomething:
    def test_blocks_widen_the_interval_only_when_the_series_clusters(self) -> None:
        """⭐ The property that justifies moving-BLOCK over an iid bootstrap.

        With no autocorrelation, blocks cost nothing (the intervals match). With strong
        autocorrelation, the iid resample destroys the dependence and reports a falsely
        TIGHT interval — measured here at ~1.8× too narrow. That is exactly the error a
        book of concurrent positions would make about its own uncertainty.
        """

        def mean_width(phi: float, block_len: int | None) -> float:
            widths = []
            for s in range(40):
                r = moving_block_bootstrap(
                    _ar1(60, phi, 100 + s), block_len=block_len, resamples=600, seed=5
                )
                assert r is not None
                widths.append(r.p95 - r.p5)
            return sum(widths) / len(widths)

        indep = mean_width(0.0, None) / mean_width(0.0, 1)
        assert 0.9 < indep < 1.1, "blocks must not distort an independent series"

        clustered = mean_width(0.8, None) / mean_width(0.8, 1)
        assert clustered > 1.4, "blocks must widen a clustered series"


class TestCalibrationAndPower:
    """The H8 pattern: a bar that cannot come out badly is not a bar."""

    def _survives_rate(self, mu: float, base_seed: int, trials: int = 200) -> float:
        hits = 0
        for i in range(trials):
            r = moving_block_bootstrap(_normal(44, mu, base_seed + i), resamples=400, seed=99)
            if r is not None and r.observed_sharpe > 0 and r.sign_survives:
                hits += 1
        return hits / trials

    def test_rejects_noise_near_the_design_rate(self) -> None:
        """One-sided 5% design. Percentile bootstraps under-cover at small n, so a little
        liberal is expected and is recorded here rather than hidden."""
        rate = self._survives_rate(0.0, 1000)
        assert rate < 0.12, f"zero-edge series clear too often ({rate:.1%})"

    def test_accepts_a_real_edge(self) -> None:
        """Power at the same effect size H8 used for the DSR bar."""
        rate = self._survives_rate(0.5, 5000)
        assert rate > 0.80, f"a true Sharpe of 0.5 should survive far more often ({rate:.1%})"


class TestSignSemantics:
    def test_a_clear_positive_edge_survives(self) -> None:
        r = moving_block_bootstrap(_normal(44, 1.5, 4))
        assert r is not None
        assert r.p5 > 0 and r.sign_survives and r.share_negative == 0.0

    def test_noise_does_not_claim_a_sign(self) -> None:
        r = moving_block_bootstrap(_normal(44, 0.0, 7))
        assert r is not None
        assert r.p5 < 0 < r.p95
        assert r.sign_survives is False

    def test_a_clear_negative_edge_also_survives(self) -> None:
        """Direction-agnostic: for a gate's would-block cohort, a stable NEGATIVE sign is
        the useful finding."""
        r = moving_block_bootstrap(_normal(44, -1.5, 8))
        assert r is not None
        assert r.p95 < 0 and r.sign_survives and r.share_negative == 1.0


class TestRender:
    def test_refusal_explains_which_condition_failed(self) -> None:
        out = "\n".join(render_lines(None, label="eligible set"))
        assert "not assessable" in out
        assert "degenerate" in out  # the non-obvious one must be named

    def test_result_names_the_sign_not_just_survival(self) -> None:
        r = moving_block_bootstrap(_normal(44, -1.5, 8))
        out = "\n".join(render_lines(r, label="eligible set"))
        assert "negative sign SURVIVES" in out
        assert "90% interval" in out
        assert "SAMPLING uncertainty only" in out  # the honest limit rides along


# --------------------------------------------------------------- newey_west_t (H1 sibling)


class TestNeweyWestT:
    """The overlap-aware t for the MEAN of a daily series.

    Added 2026-09-10 after a quant-verifier HIGH: the reading-study scripts averaged each
    day's cross-section and then t-tested that series, which removes same-day correlation
    but NOT the overlap between day t and day t+1 when both measure a k-session forward
    return. The naive t was inflated ~sqrt(k).
    """

    def test_iid_series_matches_the_naive_t_at_lag_zero(self) -> None:
        """lag=0 is the ordinary t (population sd), so the correction is opt-in, not hidden."""
        xs = [1.0, -2.0, 3.0, 0.5, -1.5, 2.5, -0.5, 1.0]
        n = len(xs)
        mean = sum(xs) / n
        var = sum((x - mean) ** 2 for x in xs) / n
        expected = mean / math.sqrt(var / n)
        got = newey_west_t(xs, lag=0)
        assert got is not None
        assert got == pytest.approx(expected, rel=1e-12)

    def test_positive_autocorrelation_shrinks_the_t(self) -> None:
        """The whole point: a persistent series carries less information than its length."""
        # A strongly persistent series: each value repeats the previous one's sign and size.
        xs = [1.0, 1.0, 1.0, 1.0, -1.0, -1.0, -1.0, -1.0] * 6
        xs = [x + 0.4 for x in xs]  # non-zero mean so a t exists
        naive = newey_west_t(xs, lag=0)
        corrected = newey_west_t(xs, lag=3)
        assert naive is not None and corrected is not None
        assert abs(corrected) < abs(naive), (
            f"lag=3 t {corrected} should be smaller in magnitude than naive {naive}"
        )

    def test_overlapping_windows_under_null_are_no_longer_significant(self) -> None:
        """The canary for the defect itself, on a synthetic panel with a KNOWN null.

        Build daily means of a k-session forward return from iid noise: consecutive days
        share k-1 sessions, exactly the study's shape. The naive t routinely clears 2 on a
        series with no edge at all; the corrected t must be far tamer. Asserting on the
        MEDIAN over many trials keeps this deterministic-ish without a fixed-seed illusion.
        """
        rng = random.Random(20260910)
        k = 10
        naive_ts: list[float] = []
        corrected_ts: list[float] = []
        for _ in range(40):
            daily_noise = [rng.gauss(0.0, 1.0) for _ in range(400)]
            # day t's observation is the sum of the next k daily moves -> overlap of k-1
            series = [sum(daily_noise[t : t + k]) for t in range(len(daily_noise) - k)]
            nt = newey_west_t(series, lag=0)
            ct = newey_west_t(series, lag=k - 1)
            if nt is not None and ct is not None:
                naive_ts.append(abs(nt))
                corrected_ts.append(abs(ct))
        assert len(naive_ts) == 40
        naive_med = statistics.median(naive_ts)
        corrected_med = statistics.median(corrected_ts)
        # Under H0 a correct |t| has median ~0.67. The naive one is inflated by ~sqrt(k).
        assert corrected_med < naive_med, (
            f"corrected median |t| {corrected_med:.2f} should be below naive {naive_med:.2f}"
        )
        assert corrected_med < 1.5, (
            f"under H0 the corrected median |t| should stay near 0.67, got {corrected_med:.2f}"
        )
        assert naive_med > 1.5, (
            "the synthetic panel is meant to REPRODUCE the inflation; if the naive median "
            f"|t| is only {naive_med:.2f} the canary is not exercising the defect"
        )

    def test_degenerate_inputs_return_none_rather_than_a_number(self) -> None:
        assert newey_west_t([], lag=0) is None
        assert newey_west_t([1.0, 2.0], lag=0) is None  # n < 3
        assert newey_west_t([2.0, 2.0, 2.0, 2.0], lag=1) is None  # zero variance

    def test_lag_is_clamped_to_the_series_length(self) -> None:
        xs = [1.0, -1.0, 2.0, 0.0, 1.5]
        assert newey_west_t(xs, lag=999) is not None
        assert newey_west_t(xs, lag=-5) == newey_west_t(xs, lag=0)
