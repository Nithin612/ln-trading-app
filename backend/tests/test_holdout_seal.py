"""Queue items 11 / 11b — the holdout seals, and the proof they can FAIL.

⭐ **The property that matters is not that the seal passes today.** A seal that cannot
detect drift passes forever and is decoration — the same shape as every vacuous test this
project has caught (the M62 canary that survived a re-introduced look-ahead, the bhavcopy
binary cases caught by the wrong check, the wiring lint satisfied by a comment). So most
of this file constructs drift and asserts the seal NOTICES.

⚠ These run on dicts, not the database: `_compare` is the whole decision procedure, and
feeding it a doctored "sealed" state is the only way to test a detector whose real input
is supposed never to change.
"""

from __future__ import annotations

import copy
from datetime import date
from typing import Any

from scripts.holdout_seal import BLOCKS, FORBIDDEN, WHITELIST, _compare


def _seal() -> dict[str, Any]:
    """A minimal two-block seal: one sealed, one open-ended."""
    return {
        "sealed_at": "2026-09-19T00:00:00+00:00",
        "blocks": {
            "holdout-1": {
                "lo": "2021-01-01", "hi": "2023-07-02", "open_ended": False,
                "sessions": 3, "bars": 30, "block_digest": "aaa",
                "session_digests": {"2021-01-01": "s1", "2021-01-04": "s2", "2021-01-05": "s3"},
            },
            "test": {
                "lo": "2023-07-03", "hi": "2099-01-01", "open_ended": True,
                "sessions": 2, "bars": 20, "block_digest": "bbb",
                "session_digests": {"2023-07-03": "t1", "2023-07-04": "t2"},
            },
        },
    }


def test_an_unchanged_block_is_intact() -> None:
    s = _seal()
    assert _compare(s, copy.deepcopy(s)) == 0


def test_a_changed_price_is_caught() -> None:
    """⭐⭐ THE CANARY. This is the event the seal exists for: a holdout silently
    re-ingested, back-filled or CA-adjusted between sealing and opening, so the
    'out-of-sample' test runs on data that moved underneath it."""
    old = _seal()
    new = copy.deepcopy(old)
    new["blocks"]["holdout-1"]["session_digests"]["2021-01-04"] = "MOVED"
    new["blocks"]["holdout-1"]["block_digest"] = "different"

    assert _compare(old, new) == 1, (
        "a changed session digest did not trip the seal — the seal cannot detect the one "
        "event it exists to detect"
    )


def test_a_session_added_to_a_sealed_block_is_caught() -> None:
    """A back-fill landing inside a holdout is drift even though nothing was overwritten."""
    old = _seal()
    new = copy.deepcopy(old)
    new["blocks"]["holdout-1"]["session_digests"]["2021-01-06"] = "s4"
    new["blocks"]["holdout-1"]["sessions"] = 4
    new["blocks"]["holdout-1"]["block_digest"] = "different"

    assert _compare(old, new) == 1


def test_a_session_removed_from_a_sealed_block_is_caught() -> None:
    old = _seal()
    new = copy.deepcopy(old)
    del new["blocks"]["holdout-1"]["session_digests"]["2021-01-05"]
    new["blocks"]["holdout-1"]["sessions"] = 2
    new["blocks"]["holdout-1"]["block_digest"] = "different"

    assert _compare(old, new) == 1


def test_a_vanished_block_is_caught() -> None:
    old = _seal()
    new = copy.deepcopy(old)
    del new["blocks"]["holdout-1"]

    assert _compare(old, new) == 1


def test_the_open_ended_block_growing_is_not_an_alarm() -> None:
    """⭐ The distinction the 797-vs-798 discovery forced. The test block gains a row every
    session; treating that as drift would make the seal fire daily and then be ignored,
    which is worse than having no seal."""
    old = _seal()
    new = copy.deepcopy(old)
    new["blocks"]["test"]["session_digests"]["2023-07-05"] = "t3"
    new["blocks"]["test"]["sessions"] = 3
    new["blocks"]["test"]["block_digest"] = "changed-and-that-is-fine"

    assert _compare(old, new) == 0


def test_the_blocks_are_pinned_by_date_and_partition_without_overlap() -> None:
    """⛔ The defect this script found: `313 + 617 + 797 = 1,727` was quoted as a fact and
    the test block is now 798. Counts are OUTPUTS measured as-of a date; the DATE RANGE is
    the pinned thing. So the structural assertion is about intervals, never counts."""
    spans = sorted(((b["lo"], b["hi"], b["name"]) for b in BLOCKS), key=lambda x: x[0])

    for (_lo1, hi1, n1), (lo2, _hi2, n2) in zip(spans, spans[1:], strict=False):
        assert hi1 < lo2, f"{n1} overlaps {n2}"
        assert (lo2 - hi1).days <= 3, f"gap between {n1} and {n2} — sessions unaccounted for"

    assert sum(1 for b in BLOCKS if b["open_ended"]) == 1, "exactly one block may be open-ended"
    assert spans[0][0] == date(2019, 10, 1), "holdout-2 must start at the archive's first session"


def test_every_block_records_why_it_exists() -> None:
    """A holdout with no stated reason gets opened by whoever inherits it."""
    for b in BLOCKS:
        assert len(b["why"]) > 80, f"{b['name']}: give a real reason"


def test_the_whitelist_is_written_down_and_non_trivial() -> None:
    """⭐ Without the list, 'I only checked the data was fine' is unfalsifiable after the
    fact. The forbidden list must name the eye, because looking at a chart IS a model fit
    with unrecorded parameters."""
    assert len(WHITELIST) >= 4
    assert len(FORBIDDEN) >= 3
    joined = " ".join(FORBIDDEN).lower()
    assert "tuned" in joined or "threshold" in joined
    assert "eye" in joined or "chart" in joined, (
        "the forbidden list does not mention looking at the data — the most likely breach "
        "and the one nobody records"
    )
