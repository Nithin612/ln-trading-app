"""Entry-quality attribution — Phase 6 slice 6.2.

Covers the cell math (n / entered / decided / hit_rate / reached_1r_rate / mean
MFE·MAE / expectancy_r), and canaries for the R-winsor, the n>=20 rank floor, the
ADX-level regime parse, and the tradeable/shadow cohort split.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.models.signal import Signal, SignalOutcome
from app.services.entry_attribution import (
    RANK_FLOOR,
    WINSOR_R,
    compute_attribution,
    render_attribution_markdown,
)

from tests.helpers import make_stock

pytestmark = pytest.mark.asyncio

CREATED = datetime(2026, 7, 20, 3, 45, tzinfo=UTC)   # >= OUTCOME_EPOCH
VALID = datetime(2026, 7, 20, 10, 0, tzinfo=UTC)
NOW = datetime(2026, 8, 1, 0, 0, tzinfo=UTC)


async def _seed(
    db, stock, *, shadow=False, status="tp_first", confidence=75,
    entry="100", sl="98", tp="106", mfe_r="2.0", mae_r="-0.5",
    adx="ADX=27.2 trending", direction="BUY", timeframe="1d", created_at=CREATED,
    factors=None, regime=None,
) -> str:
    fs = {"ADX": {"score": 0.6, "weight": 5, "explanation": adx}} if adx else {}
    for name, score in (factors or {}).items():
        fs[name] = {"score": score, "weight": 5, "explanation": ""}
    sig = Signal(
        stock_id=stock.id, direction=direction, classification="swing", timeframe=timeframe,
        entry_price=Decimal(entry), stop_loss=Decimal(sl), take_profit=Decimal(tp),
        suggested_qty=10, confidence_pct=confidence, factor_scores=fs, regime=regime,
        headline="attr test",
        status="expired", is_shadow=shadow, validity_until=VALID, created_at=created_at,
    )
    db.add(sig)
    await db.flush()
    db.add(
        SignalOutcome(
            signal_id=sig.id, stock_id=stock.id, direction=direction, classification="swing",
            timeframe=timeframe, validity_until=VALID, status=status,
            mfe_r=Decimal(mfe_r) if mfe_r is not None else None,
            mae_r=Decimal(mae_r) if mae_r is not None else None,
            excursion_computed_at=NOW,
        )
    )
    await db.commit()
    return sig.id


def _cell(rep, dimension, key):
    t = next(t for t in rep.tables if t.dimension == dimension)
    return next((c for c in t.cells if c.key == key), None)


async def test_cell_metrics_exact(db) -> None:
    """One confidence cell, mixed outcomes → every metric computed exactly.
    entry 100 / sl 98 / tp 106 → RR = 3, so tp_first = +3R, sl_first = -1R."""
    s = await make_stock(db, symbol="ATTRA")
    await _seed(db, s, status="tp_first", mfe_r="2.0")            # +3R, reached 1R
    await _seed(db, s, status="tp_first", mfe_r="1.5")            # +3R, reached 1R
    await _seed(db, s, status="sl_first", mfe_r="0.4")            # -1R, no
    await _seed(db, s, status="expired_untouched", mfe_r="0.2")   # not entered, no
    await db.commit()

    rep = await compute_attribution(db, shadow=False)
    c = _cell(rep, "Confidence", "70–79")
    assert c.n == 4 and c.entered == 3 and c.decided == 3
    assert c.hit_rate == pytest.approx(2 / 3)
    assert c.reached_1r_rate == pytest.approx(0.5)              # 2 of 4 mfe_r >= 1
    assert c.mean_mfe_r == pytest.approx((2.0 + 1.5 + 0.4 + 0.2) / 4)
    assert c.expectancy_r == pytest.approx((3 + 3 - 1) / 3)     # +3, +3, -1 over decided
    assert c.ranked is False                                    # n=4 < 20


async def test_expectancy_and_mfe_are_winsorized(db) -> None:
    """CANARY (R-winsor): a tiny-SL win (RR≈10000, MFE 5000) must clamp to
    ±WINSOR_R in the means — without the winsor the cell would read +10000R."""
    s = await make_stock(db, symbol="ATTRWIN")
    # entry 100 / sl 99.99 → risk 0.01; tp 200 → RR = 10000. confidence 85 → its own cell.
    await _seed(db, s, status="tp_first", confidence=85, entry="100", sl="99.99",
                tp="200", mfe_r="5000")
    await db.commit()

    c = _cell(await compute_attribution(db, shadow=False), "Confidence", "80–89")
    assert c.expectancy_r == pytest.approx(WINSOR_R)   # not 10000
    assert c.mean_mfe_r == pytest.approx(WINSOR_R)     # not 5000


async def test_rank_floor(db) -> None:
    """CANARY (n>=20 floor): a cell at RANK_FLOOR is ranked; below it is not."""
    s = await make_stock(db, symbol="ATTRRANK")
    for _ in range(RANK_FLOOR):                        # 20 in the 70–79 bucket
        await _seed(db, s, confidence=75)
    await _seed(db, s, confidence=95)                  # 1 in the 90–100 bucket
    await db.commit()

    rep = await compute_attribution(db, shadow=False)
    assert _cell(rep, "Confidence", "70–79").ranked is True
    assert _cell(rep, "Confidence", "90–100").ranked is False


async def test_regime_parsed_from_adx_level(db) -> None:
    """CANARY (ADX-level parse): the raw ADX from the explanation buckets by the
    20/25 thresholds; an unparseable explanation → 'regime n/a', never misreport."""
    s = await make_stock(db, symbol="ATTRADX")
    await _seed(db, s, adx="ADX=27.2 trending")        # >= 25 → trending
    await _seed(db, s, adx="ADX=15.0 ranging")         # < 20  → choppy
    await _seed(db, s, adx="ADX=22.0 building")        # 20–25 → transitional
    await _seed(db, s, adx="no adx here")              # unparseable → n/a
    await db.commit()

    rep = await compute_attribution(db, shadow=False)
    assert _cell(rep, "Regime (ADX)", "trending (ADX≥25)").n == 1
    assert _cell(rep, "Regime (ADX)", "choppy (ADX<20)").n == 1
    assert _cell(rep, "Regime (ADX)", "transitional (20–25)").n == 1
    assert _cell(rep, "Regime (ADX)", "regime n/a").n == 1


async def test_row_regime_comes_from_the_stored_signal_field(db) -> None:
    """SEAM: `Row.regime` (what the shadow measurement partitions by) is the
    persisted `signals.regime` — so it matches exactly what the active gate reads,
    not a re-derivation. Proven with a stored regime that DISAGREES with the payload;
    and a NULL-regime (legacy) row falls back to on-the-fly recovery. A wrong SQL
    column or mapping key would silently drop to the fallback and fail the first
    assertion."""
    from app.services.entry_attribution import load_attribution_rows

    s = await make_stock(db, symbol="ATTRREG")
    # stored regime deliberately contradicts the "ADX=22 building" (transitional) payload
    await _seed(db, s, adx="ADX=22.0 building", regime="trending (ADX≥25)", created_at=CREATED)
    await _seed(db, s, adx="ADX=22.0 building", regime=None,
                created_at=CREATED + timedelta(minutes=1))  # legacy → fallback
    await db.commit()

    rows = sorted(await load_attribution_rows(db, shadow=False), key=lambda r: r.created_at)
    assert rows[0].regime == "trending (ADX≥25)"       # stored field wins (not re-derived)
    assert rows[1].regime == "transitional (20–25)"    # NULL → on-the-fly recovery


async def test_tradeable_and_shadow_cohorts_are_separate(db) -> None:
    """A shadow signal appears only in the shadow cohort, tradeable only in
    tradeable — the is_shadow provenance split (feeds 6.4)."""
    s = await make_stock(db, symbol="ATTRSHA")
    await _seed(db, s, shadow=False)
    await _seed(db, s, shadow=True)
    await _seed(db, s, shadow=True)
    await db.commit()

    assert (await compute_attribution(db, shadow=False)).total == 1
    assert (await compute_attribution(db, shadow=True)).total == 2


async def test_empty_cohort(db) -> None:
    """No outcomes → total 0, every dimension present with no cells."""
    rep = await compute_attribution(db, shadow=False)
    assert rep.total == 0
    assert all(t.cells == [] for t in rep.tables)


async def test_renderer_marks_unranked_cells(db) -> None:
    """The markdown shows the dimension sections and flags n<20 cells with †."""
    s = await make_stock(db, symbol="ATTRMD")
    await _seed(db, s, confidence=75)                  # single cell, n=1 → unranked
    await db.commit()

    rep = await compute_attribution(db, shadow=False)
    md = render_attribution_markdown([rep], day=CREATED.date())
    assert "### Regime (ADX)" in md and "### Confidence" in md
    assert "†" in md                                   # the unranked marker
    assert "not ranked" in md


async def test_reach1r_denominator_is_measured_not_n(db) -> None:
    """CANARY (quant-verifier MEDIUM): a NULL-mfe (unmeasured) row must not
    dilute reach1R — the denominator is measured rows, not n."""
    s = await make_stock(db, symbol="ATTRMEAS")
    await _seed(db, s, status="tp_first", mfe_r="2.0")     # measured, reached 1R
    await _seed(db, s, status="tp_first", mfe_r=None)       # unmeasured (no excursion)
    await db.commit()

    c = _cell(await compute_attribution(db, shadow=False), "Confidence", "70–79")
    assert c.n == 2 and c.measured == 1
    assert c.reached_1r_rate == pytest.approx(1.0)         # 1/1 measured, NOT 1/2


async def test_rrless_win_dropped_from_expectancy(db) -> None:
    """A win with undefined RR (entry == sl → risk 0) is counted in `decided`
    but dropped from expectancy_r, never guessed. Unreachable in production (SL
    caps reject entry==sl); the branch must still behave."""
    s = await make_stock(db, symbol="ATTRRRLESS")
    await _seed(db, s, status="tp_first", entry="100", sl="100", tp="106")  # RR undefined
    await db.commit()

    c = _cell(await compute_attribution(db, shadow=False), "Confidence", "70–79")
    assert c.decided == 1
    assert c.expectancy_r is None                          # only decided had no RR → dropped


def test_factor_bucket_aligns_by_direction() -> None:
    """CANARY: a factor's stance is aligned to the TRADE direction — a bullish
    score supports a BUY but opposes a SELL (else BUY/SELL cohorts mix)."""
    from app.services.entry_attribution import _factor_bucket
    assert _factor_bucket("BUY", 0.6) == "supportive"
    assert _factor_bucket("BUY", -0.6) == "against"
    assert _factor_bucket("BUY", 0.0) == "neutral"
    assert _factor_bucket("SELL", -0.6) == "supportive"    # bearish factor supports a short
    assert _factor_bucket("SELL", 0.6) == "against"


async def test_factor_tables_included_only_when_factor_fires(db) -> None:
    """A factor firing on >= RANK_FLOOR rows gets a 'Factor · X' table; a factor
    that never fires (DOW_TREND) is skipped, not shown as one dead cell."""
    s = await make_stock(db, symbol="ATTRFAC")
    for _ in range(RANK_FLOOR):
        await _seed(db, s, direction="BUY", factors={"SR_ZONE": 0.9})  # supportive
    await db.commit()

    rep = await compute_attribution(db, shadow=False)
    dims = [t.dimension for t in rep.tables]
    assert "Factor · SR_ZONE" in dims
    assert "Factor · DOW_TREND" not in dims                # never set → no table
    fac = next(t for t in rep.tables if t.dimension == "Factor · SR_ZONE")
    sup = next(c for c in fac.cells if c.key == "supportive")
    assert sup.n == RANK_FLOOR and sup.ranked is True
