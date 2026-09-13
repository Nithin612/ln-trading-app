"""U15 (2026-09-13) — the backfill must be able to repair a THIN session.

REGRESSION. `backfill_ohlcv_history` decided a date was already done by a FIXED
floor of 500 rows. On 2026-09-07 → 09-11 the universe outage left five sessions
ingested at ~1,170 rows against a normal ~2,630, and every one of them cleared
500 — so running the script over that range printed "nothing to fetch — range
already complete" and did nothing. The U3 repair had to bypass it.

Same blindness as the 6.8.6 feed alarm and `load_frames`: an instrument asserting
PRESENCE where the failure mode is COVERAGE. Completeness is now judged against
the range's own median session.
"""

from __future__ import annotations

from scripts.backfill_ohlcv_history import (
    _COMPLETE_DAY_ROWS,
    complete_day_threshold,
)

# The real shape of the incident: twelve healthy sessions, then the five thin ones.
HEALTHY = [2647, 2646, 2646, 2632, 2633, 2630, 2633, 2639, 2636, 2632, 2623, 2629]
THIN = [1182, 1179, 1175, 1168, 1166]


def test_the_real_incident_sessions_are_judged_incomplete() -> None:
    """The whole point: 1,170-odd rows against a ~2,630 median is NOT a complete
    session, even though it is more than twice the old fixed floor."""
    threshold = complete_day_threshold(HEALTHY + THIN)
    assert all(n < threshold for n in THIN)
    assert all(n >= threshold for n in HEALTHY)


def test_the_old_fixed_floor_would_have_passed_every_thin_session() -> None:
    """Canary for the defect itself — this is what the old code did."""
    assert all(n >= _COMPLETE_DAY_ROWS for n in THIN)


def test_a_healthy_range_marks_everything_done() -> None:
    threshold = complete_day_threshold(HEALTHY)
    assert all(n >= threshold for n in HEALTHY)


def test_an_empty_range_falls_back_to_the_floor() -> None:
    assert complete_day_threshold([]) == _COMPLETE_DAY_ROWS


def test_the_floor_still_binds_when_the_median_is_depressed() -> None:
    """A range that is thin THROUGHOUT has no healthy median to measure against,
    so the absolute floor is what remains — it is a backstop, not the test."""
    assert complete_day_threshold([300, 320, 310]) == _COMPLETE_DAY_ROWS


def test_the_threshold_scales_with_the_universe() -> None:
    """No constant can be right for a quantity that grows with the listed
    universe — which is why raising the old one was the wrong fix."""
    small = complete_day_threshold([1000] * 5)
    large = complete_day_threshold([4000] * 5)
    assert large > small


def test_median_is_used_rather_than_the_mean() -> None:
    """One catastrophic session must not drag the bar down for its neighbours."""
    counts = [2600, 2600, 2600, 2600, 5]
    assert complete_day_threshold(counts) == int(2600 * 0.8)


def test_even_length_ranges_average_the_two_middle_sessions() -> None:
    assert complete_day_threshold([1000, 2000, 3000, 4000]) == int(2500 * 0.8)


def test_a_range_spanning_two_eras_judges_the_thin_era_against_a_blended_median() -> None:
    """Pinned so the behaviour is deliberate rather than accidental. 2019 carried
    ~1,700 EQ rows a day against 2026's ~2,630; a range covering both blends them,
    so some legitimately-complete early sessions fall under the bar and are
    re-fetched. That is WASTE, not corruption — the ingest is idempotent — and
    `--min-rows` exists to pin the bar when backfilling across eras."""
    era_2019 = [1700] * 5
    era_2026 = [2630] * 5
    threshold = complete_day_threshold(era_2019 + era_2026)

    assert any(n < threshold for n in era_2019)   # the blended bar catches them
    assert all(n >= threshold for n in era_2026)
    # …and judged against its own era, 2019 is complete.
    assert all(n >= complete_day_threshold(era_2019) for n in era_2019)
