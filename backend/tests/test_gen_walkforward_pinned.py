"""`gen_walkforward_goldens --pinned`: a data-only refresh must not move the universe.

The canary: the generator's default path re-resolves the universe from LIVE state, so after
the 2026-09-14 universe repair a plain regenerate would have swapped names in and out of a
golden while claiming to refresh its data. 2026-10-03, multibagger: 8 previously excluded
names now cross the 300-bar canon — exactly the move `--pinned` must refuse.
"""

from __future__ import annotations

from scripts.gen_walkforward_goldens import pinned_universe, run_set_moved

GOLDEN = {
    "symbols": ["ABB", "TCS"],
    "exclusions": [{"symbol": "JIOFIN", "reason": "<300 bars", "bars_before_eval": 265}],
}


def test_pinned_universe_is_run_set_plus_exclusions() -> None:
    assert pinned_universe(GOLDEN) == ["ABB", "JIOFIN", "TCS"]


def test_same_run_set_is_a_data_refresh() -> None:
    assert run_set_moved(GOLDEN, {"symbols": ["TCS", "ABB"]}) is None


def test_an_excluded_name_now_running_is_refused() -> None:
    assert run_set_moved(GOLDEN, {"symbols": ["ABB", "JIOFIN", "TCS"]}) == (["JIOFIN"], [])


def test_a_lost_name_is_refused() -> None:
    assert run_set_moved(GOLDEN, {"symbols": ["ABB"]}) == ([], ["TCS"])


def test_refusal_needs_an_explicit_sign_off_flag() -> None:
    from scripts.gen_walkforward_goldens import refuse_run_set_move

    moved = {"symbols": ["ABB", "JIOFIN", "TCS"]}
    assert refuse_run_set_move("k", GOLDEN, moved, allow=False) is True
    assert refuse_run_set_move("k", GOLDEN, moved, allow=True) is False
    assert refuse_run_set_move("k", GOLDEN, {"symbols": ["ABB", "TCS"]}, allow=False) is False
