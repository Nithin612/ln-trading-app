"""Signal-level MFE/MAE recorder — Phase 6 slice 6.1.

Covers the excursion math (LONG + SHORT), the R convention, the no-look-ahead /
validity-cap window, the is_complete filter, idempotency, the terminal-only
gate, the same-day defer guard, and the OUTCOME_EPOCH cohort floor. Canaries are
marked — each fails on a specific plausible bug.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.models.market_data import Ohlcv1m
from app.models.signal import Signal, SignalOutcome
from app.services.signal_excursions import compute_outcome_excursions

from tests.helpers import make_stock

pytestmark = pytest.mark.asyncio

# A window comfortably after OUTCOME_EPOCH (2026-07-19); NOW is a later day so
# the same-day defer guard never fires for the tape-present tests.
CREATED = datetime(2026, 7, 20, 3, 45, tzinfo=UTC)   # 09:15 IST
VALIDITY = datetime(2026, 7, 20, 4, 30, tzinfo=UTC)  # 10:00 IST
NOW = datetime(2026, 8, 1, 0, 0, tzinfo=UTC)


async def _seed(
    db,
    stock,
    *,
    direction="BUY",
    status="expired_open",
    created_at=CREATED,
    validity_until=VALIDITY,
    resolved_at=None,
    entry="100",
    sl="98",
    tp="110",
) -> str:
    """Create a Signal + matching SignalOutcome row directly (bypasses the
    recorder — we are testing the excursion filler, not touch detection)."""
    sig = Signal(
        stock_id=stock.id,
        direction=direction,
        classification="swing",
        timeframe="1h",
        entry_price=Decimal(entry),
        stop_loss=Decimal(sl),
        take_profit=Decimal(tp),
        suggested_qty=10,
        confidence_pct=75,
        factor_scores={},
        headline="6.1 excursion test",
        status="expired",
        validity_until=validity_until,
        created_at=created_at,
    )
    db.add(sig)
    await db.flush()
    db.add(
        SignalOutcome(
            signal_id=sig.id,
            stock_id=stock.id,
            direction=direction,
            classification="swing",
            timeframe="1h",
            validity_until=validity_until,
            status=status,
            resolved_at=resolved_at,
        )
    )
    await db.commit()
    return sig.id


async def _bar(db, stock, minute, *, high, low, close, complete=True) -> None:
    db.add(
        Ohlcv1m(
            time=minute,
            stock_id=stock.id,
            open=Decimal(close),
            high=Decimal(high),
            low=Decimal(low),
            close=Decimal(close),
            volume=1000,
            is_complete=complete,
        )
    )


async def _get(db, sid: str) -> SignalOutcome:
    db.expire_all()
    return await db.get(SignalOutcome, sid)


def _t(minute: int) -> datetime:
    """A UTC bar-time `minute` minutes past CREATED."""
    return CREATED + timedelta(minutes=minute)


async def test_long_excursion_values_and_window(db) -> None:
    """LONG MFE/MAE anchored at entry, in R; pre-window and post-resolution bars
    are excluded (no look-ahead + resolution cap)."""
    s = await make_stock(db, symbol="EXCLONG")
    sid = await _seed(
        db, s, direction="BUY", status="tp_first",
        resolved_at=_t(30), entry="100", sl="98",  # risk = 2, resolves at +30m
    )
    await _bar(db, s, _t(-5), high="500", low="499", close="500")  # BEFORE start → excluded
    await _bar(db, s, _t(5), high="105", low="99", close="104")    # MFE 105 @ +5
    await _bar(db, s, _t(15), high="103", low="97", close="98")    # MAE low 97 @ +15
    await _bar(db, s, _t(45), high="200", low="199", close="200")  # AFTER resolution → excluded
    await db.commit()

    n = await compute_outcome_excursions(db, now=NOW)
    assert n == 1
    oc = await _get(db, sid)
    assert oc.mfe_price == Decimal("105") and oc.mfe_at == _t(5)
    assert oc.mfe_r == Decimal("2.500")           # (105-100)/2
    assert oc.mae_price == Decimal("97") and oc.mae_at == _t(15)
    assert oc.mae_r == Decimal("-1.500")          # (97-100)/2, adverse = negative fav R
    assert oc.excursion_computed_at is not None


async def test_short_direction_is_mapped(db) -> None:
    """CANARY (BUY/SELL→LONG/SHORT mapping): for a SELL the favourable extreme is
    the LOW and the adverse extreme is the HIGH. If SELL were treated as LONG
    these invert and the asserts fail."""
    s = await make_stock(db, symbol="EXCSHORT")
    sid = await _seed(
        db, s, direction="SELL", status="sl_first",
        resolved_at=_t(30), entry="100", sl="102", tp="90",  # risk = 2
    )
    await _bar(db, s, _t(5), high="101", low="95", close="96")
    await db.commit()

    assert await compute_outcome_excursions(db, now=NOW) == 1
    oc = await _get(db, sid)
    assert oc.mfe_price == Decimal("95")    # favourable for a short = the low
    assert oc.mfe_r == Decimal("2.500")     # (100-95)/2
    assert oc.mae_price == Decimal("101")   # adverse for a short = the high
    assert oc.mae_r == Decimal("-0.500")    # (100-101)/2


async def test_window_capped_at_validity_not_sweep_time(db) -> None:
    """CANARY (resolved_at on a swept row is the SWEEP time, later than validity):
    the window must cap at validity_until, so a post-validity bar cannot inflate
    MFE. Using resolved_at as the end would pull in the 999 bar."""
    s = await make_stock(db, symbol="EXCCAP")
    sid = await _seed(
        db, s, direction="BUY", status="expired_open",
        resolved_at=datetime(2026, 7, 25, 6, 0, tzinfo=UTC),  # sweep, days after validity
        entry="100", sl="98",
    )
    await _bar(db, s, _t(15), high="106", low="99", close="105")   # inside validity
    await _bar(db, s, _t(120), high="999", low="998", close="999")  # AFTER validity → excluded
    await db.commit()

    assert await compute_outcome_excursions(db, now=NOW) == 1
    oc = await _get(db, sid)
    assert oc.mfe_price == Decimal("106")   # NOT 999
    assert oc.mfe_r == Decimal("3.000")


async def test_incomplete_bar_excluded(db) -> None:
    """CANARY (is_complete filter): a forming candle never enters the excursion
    (no repaint / look-ahead)."""
    s = await make_stock(db, symbol="EXCINC")
    sid = await _seed(db, s, direction="BUY", status="expired_open",
                      resolved_at=datetime(2026, 7, 25, 6, 0, tzinfo=UTC))
    await _bar(db, s, _t(10), high="105", low="99", close="104", complete=True)
    await _bar(db, s, _t(20), high="200", low="199", close="200", complete=False)  # forming
    await db.commit()

    assert await compute_outcome_excursions(db, now=NOW) == 1
    oc = await _get(db, sid)
    assert oc.mfe_price == Decimal("105")   # NOT the forming 200


async def test_idempotent(db) -> None:
    """Second run computes nothing and leaves the values untouched."""
    s = await make_stock(db, symbol="EXCIDEM")
    sid = await _seed(db, s, direction="BUY", status="tp_first", resolved_at=_t(30))
    await _bar(db, s, _t(5), high="105", low="99", close="104")
    await db.commit()

    assert await compute_outcome_excursions(db, now=NOW) == 1
    first = await _get(db, sid)
    stamp = first.excursion_computed_at
    assert await compute_outcome_excursions(db, now=NOW) == 0  # nothing left
    again = await _get(db, sid)
    assert again.excursion_computed_at == stamp
    assert again.mfe_price == Decimal("105")


async def test_non_terminal_rows_are_skipped(db) -> None:
    """open / entry_touched still have price to come — never computed."""
    s1 = await make_stock(db, symbol="EXCOPEN")
    s2 = await make_stock(db, symbol="EXCENTRY")
    sid_open = await _seed(db, s1, status="open")
    sid_entry = await _seed(db, s2, status="entry_touched")
    await _bar(db, s1, _t(5), high="105", low="99", close="104")
    await _bar(db, s2, _t(5), high="105", low="99", close="104")
    await db.commit()

    assert await compute_outcome_excursions(db, now=NOW) == 0
    assert (await _get(db, sid_open)).excursion_computed_at is None
    assert (await _get(db, sid_entry)).excursion_computed_at is None


async def test_no_tape_deferred_until_the_day_passes(db) -> None:
    """CANARY (same-day defer): a terminal row with no tape is left uncomputed
    while its window's IST day is current (tape may still be ingesting), then
    marked computed-with-NULL once the day has passed."""
    s = await make_stock(db, symbol="EXCNOTAPE")
    sid = await _seed(db, s, direction="BUY", status="expired_untouched",
                      resolved_at=datetime(2026, 7, 25, 6, 0, tzinfo=UTC))
    # No bars for this stock at all.

    same_ist_day = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)  # 17:30 IST, 07-20
    assert await compute_outcome_excursions(db, now=same_ist_day) == 0
    assert (await _get(db, sid)).excursion_computed_at is None  # deferred

    next_ist_day = datetime(2026, 7, 21, 6, 0, tzinfo=UTC)  # 11:30 IST, 07-21
    assert await compute_outcome_excursions(db, now=next_ist_day) == 1
    oc = await _get(db, sid)
    assert oc.excursion_computed_at is not None
    assert oc.mfe_r is None and oc.mfe_price is None  # computed, but no tape


async def test_pre_epoch_cohort_excluded(db) -> None:
    """Signals created before OUTCOME_EPOCH are not in the Phase-6 cohort."""
    s = await make_stock(db, symbol="EXCEPOCH")
    sid = await _seed(
        db, s, direction="BUY", status="tp_first",
        created_at=datetime(2026, 7, 10, 3, 45, tzinfo=UTC),   # < 2026-07-19 epoch
        validity_until=datetime(2026, 7, 10, 4, 30, tzinfo=UTC),
        resolved_at=datetime(2026, 7, 10, 4, 15, tzinfo=UTC),
    )
    await _bar(db, s, datetime(2026, 7, 10, 3, 50, tzinfo=UTC), high="105", low="99", close="104")
    await db.commit()

    assert await compute_outcome_excursions(db, now=NOW) == 0
    assert (await _get(db, sid)).excursion_computed_at is None


async def test_tiny_risk_r_winsorized_and_batch_not_poisoned(db) -> None:
    """CANARY (Numeric(7,3) overflow poison pill): a near-zero-risk signal makes
    R huge; it must winsorize to the ±9999.999 bound and NOT abort the batch — a
    normal row in the SAME batch still commits. Without the clamp the overflowing
    UPDATE aborts the transaction and neither row persists. (quant-verifier MEDIUM.)"""
    s_tiny = await make_stock(db, symbol="EXCTINY")
    s_norm = await make_stock(db, symbol="EXCNORM")
    tiny = await _seed(db, s_tiny, direction="BUY", status="tp_first",
                       resolved_at=_t(30), entry="100", sl="99.99")  # risk 0.01
    norm = await _seed(db, s_norm, direction="BUY", status="tp_first",
                       resolved_at=_t(30), entry="100", sl="98")     # risk 2
    await _bar(db, s_tiny, _t(5), high="300", low="100", close="300")  # raw R = 20000
    await _bar(db, s_norm, _t(5), high="105", low="99", close="104")   # R = 2.5
    await db.commit()

    assert await compute_outcome_excursions(db, now=NOW) == 2
    oc_tiny = await _get(db, tiny)
    assert oc_tiny.excursion_computed_at is not None
    assert oc_tiny.mfe_r == Decimal("9999.999")   # winsorized, not an overflow/abort
    oc_norm = await _get(db, norm)                 # _get expires oc_tiny — assert it above first
    assert oc_norm.excursion_computed_at is not None
    assert oc_norm.mfe_r == Decimal("2.500")      # same batch still committed


async def test_ready_row_not_starved_by_same_day_deferred(db) -> None:
    """CANARY (order by EFFECTIVE window-end, not raw validity): a ready row
    (resolved yesterday, tape present) whose raw validity_until is *today* must
    still be computed even when same-day no-tape deferred rows have an EARLIER
    raw validity and would otherwise fill the LIMIT first. Regression for the
    defer+LIMIT starvation (bug-hunter MEDIUM)."""
    now = datetime(2026, 7, 21, 8, 0, tzinfo=UTC)  # 13:30 IST, 07-21

    # 3 deferred rows: validity today (08:30 IST), no tape → skipped. Their raw
    # validity is EARLIER than the ready row's, so `ORDER BY validity ASC` would
    # put them first and (with limit=2) starve the ready row every sweep.
    for i in range(3):
        d = await make_stock(db, symbol=f"EXCDEF{i}")
        await _seed(
            db, d, status="expired_untouched",
            created_at=datetime(2026, 7, 21, 1, 0, tzinfo=UTC),
            validity_until=datetime(2026, 7, 21, 3, 0, tzinfo=UTC),
            resolved_at=datetime(2026, 7, 25, 6, 0, tzinfo=UTC),
        )

    # Ready row: resolved YESTERDAY (07-20), raw validity TODAY (07-21 05:00).
    sr = await make_stock(db, symbol="EXCRDY")
    ready = await _seed(
        db, sr, direction="BUY", status="tp_first",
        created_at=datetime(2026, 7, 20, 3, 45, tzinfo=UTC),
        validity_until=datetime(2026, 7, 21, 5, 0, tzinfo=UTC),
        resolved_at=datetime(2026, 7, 20, 4, 15, tzinfo=UTC),
        entry="100", sl="98",
    )
    await _bar(db, sr, datetime(2026, 7, 20, 3, 50, tzinfo=UTC),
               high="106", low="99", close="105")
    await db.commit()

    # limit=2 < the 3 deferred rows: effective-end ordering sorts the ready row
    # (end = resolved 07-20) ahead of the deferred wall (end = validity 07-21).
    n = await compute_outcome_excursions(db, limit=2, now=now)
    assert n == 1
    oc = await _get(db, ready)
    assert oc.excursion_computed_at is not None
    assert oc.mfe_r == Decimal("3.000")


async def test_unmappable_direction_is_retired(db) -> None:
    """A row whose direction can't map to LONG/SHORT is retired (stamped, NULL) —
    never re-selected each sweep, never mis-computed as SHORT. Can't occur via
    the BUY/SELL NOT NULL domain; exercises the defensive _stamp branch."""
    s = await make_stock(db, symbol="EXCBADDIR")
    sid = await _seed(db, s, direction="HOLD", status="expired_untouched",
                      resolved_at=datetime(2026, 7, 25, 6, 0, tzinfo=UTC))
    await db.commit()

    assert await compute_outcome_excursions(db, now=NOW) == 1
    oc = await _get(db, sid)
    assert oc.excursion_computed_at is not None       # retired, not re-selected
    assert oc.mfe_r is None and oc.mfe_price is None   # never computed
