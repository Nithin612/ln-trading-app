"""Queue item 6 — the clustered estimators, tested against a KNOWN NULL.

⭐⭐ The rule this file exists to satisfy (`instrument_self_validation`): *an instrument
never run against a known null has not been validated.* So the central test plants a
dependence structure, confirms the NAIVE t over-rejects exactly as theory says, and
confirms the clustered t does not. A test that only checked "the function returns a
number" would have passed while the estimator was wrong, which is how `t = +3.67` was
published and later collapsed to +0.98.

⚠ These are deterministic: a seeded generator, fixed replication count. An unseeded
Monte-Carlo test that fails one run in twenty gets marked flaky and then ignored.
"""

from __future__ import annotations

import random

from app.services.block_bootstrap import (
    cluster_robust_mean_t,
    design_effect,
    intraclass_correlation,
)


def _naive_t(xs: list[float]) -> float:
    n = len(xs)
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / (n - 1)
    return mean / ((var / n) ** 0.5) if var > 0 else 0.0


def _clustered_sample(
    rng: random.Random, n_groups: int, per_group: int, icc_shock: float
) -> tuple[list[float], list[int]]:
    """Each group gets a shared shock; `icc_shock` scales it against unit within-noise."""
    values: list[float] = []
    groups: list[int] = []
    for g in range(n_groups):
        shock = rng.gauss(0.0, icc_shock)
        for _ in range(per_group):
            values.append(shock + rng.gauss(0.0, 1.0))
            groups.append(g)
    return values, groups


# ── The canary ───────────────────────────────────────────────────────────────

def test_the_naive_t_over_rejects_under_clustering_and_the_clustered_one_does_not() -> None:
    """⭐⭐ THE H0 CANARY, and it must FIRST REPRODUCE THE FAILURE.

    Truth is mean zero. Every observation in a day shares a day shock — exactly the
    structure of 185 trades on 92 dates with a market-wide daily regressor. At a nominal 5%
    level the naive t should reject far too often and the clustered t should land near 5%.

    If the first assertion ever fails, the generator has stopped producing dependence and
    the second assertion is no longer evidence of anything.
    """
    rng = random.Random(20260919)
    reps = 300
    naive_rejects = clustered_rejects = 0

    for _ in range(reps):
        values, groups = _clustered_sample(rng, n_groups=40, per_group=10, icc_shock=1.0)
        if abs(_naive_t(values)) > 1.96:
            naive_rejects += 1
        res = cluster_robust_mean_t(values, groups)
        assert res is not None
        if abs(res[2]) > 1.96:
            clustered_rejects += 1

    naive_rate = naive_rejects / reps
    clustered_rate = clustered_rejects / reps

    assert naive_rate > 0.30, (
        f"naive rejection rate {naive_rate:.1%} — the generator is not producing clustered "
        "dependence any more, so this test proves nothing about the estimator"
    )
    assert clustered_rate < 0.12, (
        f"clustered rejection rate {clustered_rate:.1%} against a 5% nominal level — the "
        "cluster-robust SE is not absorbing the within-date correlation"
    )


def test_independent_data_is_left_alone() -> None:
    """The other half: the correction must not fire when there is nothing to correct, or it
    would simply be a device for making every result insignificant."""
    rng = random.Random(7)
    values = [rng.gauss(0.5, 1.0) for _ in range(600)]
    groups = list(range(600))  # every observation its own cluster ⇒ no clustering at all

    icc, _m0, n_groups = intraclass_correlation(values, groups)
    assert n_groups == 600
    assert icc == 0.0

    res = cluster_robust_mean_t(values, groups)
    assert res is not None
    _mean, _se, t_clustered, _g = res
    assert abs(t_clustered - _naive_t(values)) < 0.05, (
        "with singleton clusters the robust t must coincide with the naive one"
    )


# ── The components ───────────────────────────────────────────────────────────

def test_icc_recovers_a_planted_value() -> None:
    """shock variance 1 against within variance 1 ⇒ ICC ≈ 0.5."""
    rng = random.Random(11)
    values, groups = _clustered_sample(rng, n_groups=400, per_group=8, icc_shock=1.0)
    icc, m0, n_groups = intraclass_correlation(values, groups)

    assert n_groups == 400
    assert abs(m0 - 8.0) < 0.01, "balanced groups ⇒ effective size equals the real size"
    assert 0.40 < icc < 0.60, f"ICC {icc:.3f} — expected ≈0.5"


def test_design_effect_matches_its_own_formula() -> None:
    rng = random.Random(3)
    values, groups = _clustered_sample(rng, n_groups=200, per_group=6, icc_shock=0.7)
    icc, m0, _ = intraclass_correlation(values, groups)

    assert abs(design_effect(values, groups) - (1.0 + (m0 - 1.0) * icc)) < 1e-9
    assert design_effect(values, groups) > 1.0, "clustering can only cost precision"


def test_a_negative_sample_icc_is_clamped_rather_than_buying_precision() -> None:
    """⛔ An un-clamped negative ICC yields a design effect BELOW 1 — a claim that
    clustering made the estimate *more* precise. That is noise presented as information,
    and it would silently inflate every t it touched."""
    # Anti-correlated within groups: between-group variance collapses below within.
    values = [1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0]
    groups = [0, 0, 1, 1, 2, 2, 3, 3]

    icc, _, _ = intraclass_correlation(values, groups)
    assert icc == 0.0
    assert design_effect(values, groups) == 1.0


def test_one_cluster_is_not_assessable() -> None:
    """All observations on a single date carries no information about between-date variance.
    `None` — never a number that looks like an answer."""
    assert cluster_robust_mean_t([1.0, 2.0, 3.0], ["d", "d", "d"]) is None


def test_too_few_observations_is_not_assessable() -> None:
    assert cluster_robust_mean_t([1.0], ["a"]) is None


def test_mismatched_lengths_raise_rather_than_silently_truncate() -> None:
    import pytest

    with pytest.raises(ValueError, match="against"):
        intraclass_correlation([1.0, 2.0, 3.0], ["a", "b"])
