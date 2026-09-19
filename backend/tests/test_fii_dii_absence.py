"""Queue item 28 — "FII/DII flows neutral" must not be said from an empty table.

⛔⛔ **The defect, measured on the live book before the fix:** 30 of 52 signals carried the
string `"FII/DII flows neutral"` while `fii_dii_daily` held **14 rows in total**. That is a
positive claim about institutional flows made from no data — the same shape as the feed alarm
that read ✅ straight through the 2026-09-07 outage.

⭐ **The frozen §2.7 factor is NOT the bug and is NOT touched.** It is handed `Decimal("0")`
and correctly describes zero; its signature has no way to express "absent". The lie was
manufactured one layer out, in `get_market_flow_5d`, which resolved a missing row to zero —
`signal_service` even carried a comment recording the choice as *"empty tables → zeros,
identical to the pre-wiring behaviour"*. So the fix lives at the boundary that knows, and
needs no engine change and no sign-off.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from app.models.market_data import FiiDiiDaily
from app.services.fii_dii_service import (
    ABSENT_EXPLANATION,
    FROZEN_NEUTRAL_EXPLANATION,
    FlowWindow,
    correct_absent_flow_explanation,
    get_market_flow_5d,
)
from sqlalchemy.ext.asyncio import AsyncSession


def _scores(explanation: str = FROZEN_NEUTRAL_EXPLANATION) -> dict[str, dict[str, object]]:
    return {
        "FII_DII_FLOW": {"weight": 5, "score": 0.0, "explanation": explanation},
        "RSI_LEVEL": {"weight": 10, "score": 0.6, "explanation": "RSI 62"},
    }


# ── The distinction the whole item is about ──────────────────────────────────

def test_absent_is_not_the_same_as_a_measured_zero() -> None:
    """⭐ The property that did not exist before: `fii == dii == 0` is a legitimate, if
    unlikely, MEASUREMENT. Telling it apart from "nobody published anything" is the point."""
    absent = FlowWindow(Decimal("0"), Decimal("0"), sessions_expected=5, sessions_with_data=0)
    measured_zero = FlowWindow(
        Decimal("0"), Decimal("0"), sessions_expected=5, sessions_with_data=5
    )

    assert absent.is_absent is True
    assert measured_zero.is_absent is False
    # ...and they are indistinguishable on the values alone, which is why the old bare tuple
    # could not carry the difference.
    assert (absent.fii, absent.dii) == (measured_zero.fii, measured_zero.dii)


def test_a_partial_window_is_flagged_as_partial_not_absent() -> None:
    """A 5-day aggregate built from 2 days is not a 5-day aggregate. Neither "fine" nor
    "missing" — its own state."""
    w = FlowWindow(Decimal("100"), Decimal("50"), sessions_expected=5, sessions_with_data=2)
    assert w.is_partial is True
    assert w.is_absent is False


def test_it_still_unpacks_as_a_two_tuple() -> None:
    """⚠ Six call sites do `fii, dii = await get_market_flow_5d(...)`. Keeping that working is
    deliberate — the alternative was migrating all six in one commit for a display-string fix."""
    fii, dii = FlowWindow(Decimal("7"), Decimal("3"), 5, 5)
    assert (fii, dii) == (Decimal("7"), Decimal("3"))


# ── The relabel ──────────────────────────────────────────────────────────────

def test_an_absent_window_relabels_the_frozen_neutral_string() -> None:
    out = correct_absent_flow_explanation(
        _scores(), FlowWindow(Decimal("0"), Decimal("0"), 5, 0)
    )
    assert out["FII_DII_FLOW"]["explanation"] == ABSENT_EXPLANATION
    assert "not assessable" in str(out["FII_DII_FLOW"]["explanation"])


def test_a_measured_zero_keeps_the_frozen_wording() -> None:
    """⛔ The other half, and the one that stops this becoming a blanket rewrite: when flows
    really were measured and really were flat, "neutral" is TRUE and must survive."""
    out = correct_absent_flow_explanation(
        _scores(), FlowWindow(Decimal("0"), Decimal("0"), 5, 5)
    )
    assert out["FII_DII_FLOW"]["explanation"] == FROZEN_NEUTRAL_EXPLANATION


def test_a_real_explanation_is_never_overwritten() -> None:
    """Only the EXACT frozen default is rewritten. A loose substring match would destroy a
    genuine explanation that merely mentioned flows."""
    real = "FII net sell ₹9588 Cr > 2000; DII absorbing FII selling: DII net ₹13206 Cr"
    out = correct_absent_flow_explanation(
        _scores(real), FlowWindow(Decimal("-9588"), Decimal("13206"), 5, 0)
    )
    assert out["FII_DII_FLOW"]["explanation"] == real


def test_other_factors_are_untouched() -> None:
    out = correct_absent_flow_explanation(
        _scores(), FlowWindow(Decimal("0"), Decimal("0"), 5, 0)
    )
    assert out["RSI_LEVEL"]["explanation"] == "RSI 62"


def test_a_missing_factor_entry_is_not_an_error() -> None:
    """The factor can be absent from the dict entirely (a variant scorer, a future change).
    Correcting nothing is the right answer, not a KeyError on the money path."""
    assert correct_absent_flow_explanation({}, FlowWindow(Decimal("0"), Decimal("0"), 5, 0)) == {}


# ── Against the real database ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_an_empty_table_reports_absent_not_zero(db: AsyncSession) -> None:
    """⛔ THE REGRESSION. Before this, an empty table returned (0, 0) and the caller could not
    tell — which is exactly how 30 live signals came to claim flows were neutral."""
    w = await get_market_flow_5d(db, date(2026, 9, 18))

    assert w.is_absent is True
    assert w.sessions_with_data == 0
    assert (w.fii, w.dii) == (Decimal("0"), Decimal("0"))


@pytest.mark.asyncio
async def test_real_rows_report_coverage_and_values(db: AsyncSession) -> None:
    """With data present the window is not absent, and the coverage counts SESSIONS rather
    than rows — two investor types on one day is one day of coverage, not two."""
    for d in (date(2026, 9, 17), date(2026, 9, 18)):
        for who, buy, sell in (("FII", "1000", "3000"), ("DII", "4000", "1000")):
            db.add(FiiDiiDaily(
                trade_date=d, investor_type=who, segment="cash",
                buy_value_cr=Decimal(buy), sell_value_cr=Decimal(sell),
            ))
    await db.flush()

    w = await get_market_flow_5d(db, date(2026, 9, 18))

    assert w.is_absent is False
    assert w.sessions_with_data == 2, "coverage counts distinct SESSIONS, not rows"
    assert w.fii == Decimal("-4000")   # (1000-3000) x 2 days
    assert w.dii == Decimal("6000")    # (4000-1000) x 2 days
