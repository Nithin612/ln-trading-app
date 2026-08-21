"""Market-regime study — the pure analytical core (classify / aggregate / episodes / dispersion).

The study produced a surprising result (below+weak beat below+strong over 3y), so the math that
produced it must be exactly right: forward-return alignment, quadrant classification, contiguous
below-episode detection, and index dispersion grouping."""

from __future__ import annotations

from datetime import date, timedelta

from app.services import regime_study as rs


def _dates(n: int) -> list[date]:
    d0 = date(2024, 1, 1)
    return [d0 + timedelta(days=i) for i in range(n)]


class TestClassifyDays:
    def test_needs_200_history_and_computes_forward_returns(self) -> None:
        # 200 flat @100 then a clean +1/session ramp to 110 → 210 closes.
        closes = [100.0] * 200 + [100.0 + i for i in range(1, 11)]
        dates = _dates(len(closes))
        vix = [12.0] * len(closes)
        days = rs.classify_days(dates, closes, vix)
        # classifiable days: t = 199..209 → 11.
        assert len(days) == 11
        first = days[0]  # t=199, close 100, flat history
        assert first.t == 199
        # flat 200-DMA (=100), flat 20-DMA, zero up-days → above(vs200=0≥0) + weak breadth.
        assert first.quadrant == 'above+weak'
        # forward-5 = closes[204]/closes[199]-1 = 105/100-1 = +5%.
        assert first.fwd[5] is not None and abs(first.fwd[5] - 5.0) < 1e-9
        # forward-20 runs past the data for a late day → None.
        assert days[-1].fwd[20] is None
        # last day (rising, above both DMAs, all up-days) → above+strong.
        assert days[-1].quadrant == 'above+strong'


def _ds(quadrant: str, close: float, *, t: int = 0, vix: float | None = 15.0,
        fwd: dict[int, float | None] | None = None) -> rs.DayState:
    return rs.DayState(
        t=t, d=date(2024, 1, 1) + timedelta(days=t), close=close, quadrant=quadrant,
        vs200=0.0, breadth=0.0, vix=vix, fwd=fwd or {},
    )


class TestQuadrantStats:
    def test_aggregates_avg_win_and_vix(self) -> None:
        days = [
            _ds('below+weak', 100, fwd={20: 2.0}, vix=16.0),
            _ds('below+weak', 100, fwd={20: -1.0}, vix=18.0),
            _ds('below+weak', 100, fwd={20: 4.0}, vix=14.0),
        ]
        s = rs.quadrant_stats(days)['below+weak']
        assert s.n == 3
        assert abs(s.avg_fwd(20) - (2.0 - 1.0 + 4.0) / 3) < 1e-9
        assert s.win20_pct is not None and abs(s.win20_pct - (100 * 2 / 3)) < 1e-9  # 2 of 3 up
        assert abs(s.avg_vix - 16.0) < 1e-9
        assert rs.quadrant_stats(days)['above+strong'].n == 0  # empty bucket safe


class TestBelowEpisodes:
    def test_contiguous_runs_depth_and_recovery(self) -> None:
        days = [
            _ds('above+strong', 100, t=0),
            _ds('below+weak', 100, t=1),   # episode 1 start (cross-below close 100)
            _ds('below+strong', 90, t=2),  # trough 90 → depth -10%
            _ds('above+weak', 105, t=3),   # recovered → episode 1 ends
            _ds('below+weak', 80, t=4),    # episode 2, still below at end
        ]
        eps = rs.below_episodes(days)
        assert len(eps) == 2
        assert eps[0].sessions == 2 and abs(eps[0].depth_pct - (-10.0)) < 1e-9
        assert eps[0].recovered is True
        assert eps[1].sessions == 1 and eps[1].recovered is False  # never crossed back


class TestRobustness:
    def test_nonoverlap_gap_and_bootstrap_direction(self) -> None:
        # 10 below+weak days (fwd 5) then 10 below+strong (fwd 1); horizon/block 2 so the
        # non-overlapping subsample is meaningful.
        weak = [_ds('below+weak', 100, t=i, fwd={2: 5.0}) for i in range(10)]
        strong = [_ds('below+strong', 100, t=10 + i, fwd={2: 1.0}) for i in range(10)]
        r = rs.robustness(weak + strong, horizon=2, block=2, n_boot=300, seed=1)
        assert r.no_gap is not None and abs(r.no_gap - 4.0) < 1e-9  # 5 − 1
        assert r.boot_p_positive is not None and r.boot_p_positive > 0.9  # weak clearly > strong
        assert r.boot_ci_lo is not None and r.boot_ci_hi is not None
        assert r.boot_ci_lo <= r.boot_gap_mean <= r.boot_ci_hi

    def test_deterministic_for_a_seed(self) -> None:
        days = [_ds('below+weak', 100, t=i, fwd={2: 3.0}) for i in range(6)] + [
            _ds('below+strong', 100, t=6 + i, fwd={2: 1.0}) for i in range(6)
        ]
        assert rs.robustness(days, horizon=2, block=2, n_boot=100, seed=7) == rs.robustness(
            days, horizon=2, block=2, n_boot=100, seed=7
        )


class TestDispersion:
    def test_per_index_forward_return_grouped_by_quadrant(self) -> None:
        # Two indices; each +10%/session. Three below+weak days at t=0,1,2; horizon 1.
        xs = [100.0, 110.0, 121.0, 133.1]
        ys = [50.0, 55.0, 60.5, 66.55]
        days = [_ds('below+weak', xs[i], t=i) for i in range(3)]
        d = rs.dispersion(days, {'X': xs, 'Y': ys}, horizon=1)
        assert abs(d['below+weak']['X'] - 10.0) < 1e-6
        assert abs(d['below+weak']['Y'] - 10.0) < 1e-6
        assert d['above+strong']['X'] is None  # empty quadrant
