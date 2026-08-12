"""Monthly-return seasonality — service + API tests.

Covers the stats math, the no-look-ahead current-month exclusion, gap handling
(never spanning a missing month), and the endpoint's auth/404/empty paths.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from app.models.market_data import OhlcvDaily
from app.services.seasonality import _current_ym_ist, monthly_seasonality

from tests.helpers import create_test_user, get_auth_headers, make_stock

pytestmark = pytest.mark.asyncio


async def _add_close(db, stock_id, year, month, day, close, *, hour=6, is_complete=True):
    """One daily candle standing in as a candidate for that month's month-end
    close. Hour 6 UTC = 11:30 IST, so by default the IST calendar date never
    rolls off `day`; pass `hour` to probe the UTC↔IST month boundary, and
    `is_complete=False` to probe the incomplete-candle filter."""
    db.add(
        OhlcvDaily(
            time=datetime(year, month, day, hour, 0, tzinfo=UTC),
            stock_id=stock_id,
            open=Decimal(str(close)),
            high=Decimal(str(close)),
            low=Decimal(str(close)),
            close=Decimal(str(close)),
            volume=100_000,
            is_complete=is_complete,
        )
    )


def _shift_month(y: int, m: int, delta: int) -> tuple[int, int]:
    idx = y * 12 + (m - 1) + delta
    return idx // 12, idx % 12 + 1


async def test_monthly_stats_are_correct(db):
    """Feb/Mar across two years give known n, %-positive, avg, best/worst."""
    s = await make_stock(db, symbol="SEASA")
    # Jan-return needs Dec (absent) → uncounted; Feb needs Jan (present) etc.
    await _add_close(db, s.id, 2023, 1, 28, 100.0)
    await _add_close(db, s.id, 2023, 2, 28, 110.0)  # Feb23 +10%
    await _add_close(db, s.id, 2023, 3, 28, 110.0)  # Mar23  0%
    await _add_close(db, s.id, 2024, 1, 28, 200.0)
    await _add_close(db, s.id, 2024, 2, 28, 230.0)  # Feb24 +15%
    await _add_close(db, s.id, 2024, 3, 28, 207.0)  # Mar24 -10%
    await db.commit()

    res = await monthly_seasonality(db, s.id)

    assert res.total_observations == 4
    assert res.years_covered == 2
    assert res.first_month == date(2023, 2, 1)
    assert res.last_month == date(2024, 3, 1)

    jan = res.months[0]
    assert jan.month == 1 and jan.n == 0
    assert jan.pct_positive is None and jan.avg_return_pct is None

    feb = res.months[1]
    assert feb.month == 2 and feb.n == 2 and feb.positive == 2
    assert feb.pct_positive == pytest.approx(100.0)
    assert feb.avg_return_pct == pytest.approx(12.5, rel=1e-6)
    assert feb.best_return_pct == pytest.approx(15.0, rel=1e-6)
    assert feb.worst_return_pct == pytest.approx(10.0, rel=1e-6)
    assert feb.avg_negative_pct is None

    mar = res.months[2]
    assert mar.month == 3 and mar.n == 2 and mar.positive == 0
    assert mar.pct_positive == pytest.approx(0.0)
    assert mar.avg_return_pct == pytest.approx(-5.0, rel=1e-6)
    assert mar.best_return_pct == pytest.approx(0.0, abs=1e-9)
    assert mar.worst_return_pct == pytest.approx(-10.0, rel=1e-6)
    assert mar.avg_positive_pct is None
    assert mar.avg_negative_pct == pytest.approx(-10.0, rel=1e-6)


async def test_gap_never_spans_a_missing_month(db):
    """Oct + Dec with Nov missing must NOT produce an Oct→Dec return."""
    s = await make_stock(db, symbol="SEASGAP")
    await _add_close(db, s.id, 2022, 10, 20, 100.0)
    await _add_close(db, s.id, 2022, 12, 20, 130.0)  # Dec needs Nov (absent)
    await db.commit()

    res = await monthly_seasonality(db, s.id)
    assert res.total_observations == 0
    assert all(mo.n == 0 for mo in res.months)


async def test_current_partial_month_excluded(db):
    """No look-ahead: the return INTO the current (partial) IST month is dropped,
    while the fully-completed prior month still counts. Canary = total is 1, not 2."""
    s = await make_stock(db, symbol="SEASNOW")
    cy, cm = _current_ym_ist()
    pm_y, pm_m = _shift_month(cy, cm, -1)
    ppm_y, ppm_m = _shift_month(cy, cm, -2)
    await _add_close(db, s.id, ppm_y, ppm_m, 15, 100.0)
    await _add_close(db, s.id, pm_y, pm_m, 15, 110.0)  # +10% into prior month → counted
    await _add_close(db, s.id, cy, cm, 1, 130.0)       # return into current month → excluded
    await db.commit()

    res = await monthly_seasonality(db, s.id)
    assert res.total_observations == 1
    assert res.last_month == date(pm_y, pm_m, 1)


async def test_endpoint_happy(client, db):
    await create_test_user(db)
    s = await make_stock(db, symbol="SEASAPI")
    await _add_close(db, s.id, 2023, 1, 28, 100.0)
    await _add_close(db, s.id, 2023, 2, 28, 110.0)  # +10%
    await db.commit()

    headers = await get_auth_headers(client)
    resp = await client.get(f"/api/v1/seasonality/{s.id}", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["stock_id"] == s.id
    assert len(data["months"]) == 12
    assert data["total_observations"] == 1
    assert data["years_covered"] == 1
    feb = data["months"][1]
    assert feb["month"] == 2 and feb["n"] == 1
    assert feb["avg_return_pct"] == pytest.approx(10.0, rel=1e-6)


async def test_endpoint_requires_auth(client, db):
    s = await make_stock(db, symbol="SEASNOAUTH")
    resp = await client.get(f"/api/v1/seasonality/{s.id}")
    assert resp.status_code == 401


async def test_endpoint_unknown_stock_404(client, db):
    await create_test_user(db)
    headers = await get_auth_headers(client)
    resp = await client.get("/api/v1/seasonality/999999", headers=headers)
    assert resp.status_code == 404


async def test_endpoint_insufficient_data_is_empty_not_error(client, db):
    """A stock with <2 month-ends returns 200 with an honest empty result."""
    await create_test_user(db)
    s = await make_stock(db, symbol="SEASTHIN")
    await _add_close(db, s.id, 2023, 5, 20, 100.0)  # single close → no return
    await db.commit()

    headers = await get_auth_headers(client)
    resp = await client.get(f"/api/v1/seasonality/{s.id}", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_observations"] == 0
    assert data["years_covered"] == 0
    assert data["first_month"] is None
    assert all(mo["n"] == 0 for mo in data["months"])


async def test_month_bucketed_in_ist_not_utc(db):
    """A candle stamped 2023-01-31 20:00 UTC is 2023-02-01 01:30 IST, so it is
    FEBRUARY's month-end, not January's.

    Canary for seasonality.py:91 — swapping `ts.astimezone(_IST).date()` for a
    UTC `.date()` re-buckets the boundary candle into Jan (Jan then has two rows,
    month-end 110; no Feb close; Jan needs an absent Dec), erasing the only
    return: total_observations 1 → 0. The prior IST-canary did not catch this
    because every fixture candle sat at 11:30 IST and never crossed a boundary."""
    s = await make_stock(db, symbol="SEASIST")
    await _add_close(db, s.id, 2023, 1, 15, 100.0)             # Jan month-end = 100
    await _add_close(db, s.id, 2023, 1, 31, 110.0, hour=20)    # 01:30 IST Feb 1 → Feb
    await db.commit()

    res = await monthly_seasonality(db, s.id)

    assert res.total_observations == 1
    assert res.last_month == date(2023, 2, 1)
    feb = res.months[1]
    assert feb.month == 2 and feb.n == 1
    assert feb.avg_return_pct == pytest.approx(10.0, rel=1e-6)


async def test_month_end_uses_last_trading_day(db):
    """The month-end close is the LAST trading day's close, not the first/any.
    Canary for seasonality.py:96 (`d > prev[0]`): picking an earlier day (or a
    min) would change June's month-end from 100 to 90 and July's return from
    +10% to +22.2%."""
    s = await make_stock(db, symbol="SEASEND")
    await _add_close(db, s.id, 2023, 6, 10, 90.0)   # earlier day — must NOT win
    await _add_close(db, s.id, 2023, 6, 28, 100.0)  # last trading day — month-end
    await _add_close(db, s.id, 2023, 7, 15, 110.0)  # July → 110/100 - 1 = +10%
    await db.commit()

    res = await monthly_seasonality(db, s.id)

    jul = res.months[6]
    assert jul.month == 7 and jul.n == 1
    assert jul.avg_return_pct == pytest.approx(10.0, rel=1e-6)


async def test_incomplete_candle_never_becomes_month_end(db):
    """`is_complete = False` rows are excluded (no repaint / look-ahead per
    trading-domain §3). Canary for seasonality.py:83: a later, still-forming
    candle must not overwrite the month-end — dropping the filter makes April's
    month-end 999 and the return +899% instead of +10%."""
    s = await make_stock(db, symbol="SEASINC")
    await _add_close(db, s.id, 2023, 3, 28, 100.0)                     # March complete
    await _add_close(db, s.id, 2023, 4, 10, 110.0)                     # April complete
    await _add_close(db, s.id, 2023, 4, 28, 999.0, is_complete=False)  # April forming
    await db.commit()

    res = await monthly_seasonality(db, s.id)

    apr = res.months[3]
    assert apr.month == 4 and apr.n == 1
    assert apr.avg_return_pct == pytest.approx(10.0, rel=1e-6)


async def test_zero_prior_close_is_skipped_not_divided(db):
    """A zero prior-month close is skipped, never divided by (guard at
    seasonality.py:113). Removing `or prev_close == 0` raises ZeroDivisionError
    → a 500; this asserts the return is dropped and nothing is raised."""
    s = await make_stock(db, symbol="SEASZERO")
    await _add_close(db, s.id, 2023, 4, 28, 0.0)    # prior-month close 0
    await _add_close(db, s.id, 2023, 5, 28, 100.0)  # May needs April (0) → skipped
    await db.commit()

    res = await monthly_seasonality(db, s.id)  # must not raise
    assert res.total_observations == 0
    assert all(mo.n == 0 for mo in res.months)


async def test_mixed_up_and_down_month_partitions_correctly(db):
    """A month with one up year and one down year: median, avg, and BOTH partition
    means are reported as values (covers median_return_pct and the
    avg_positive_pct/avg_negative_pct numeric branches, not just their None case)."""
    s = await make_stock(db, symbol="SEASMIX")
    await _add_close(db, s.id, 2022, 4, 28, 100.0)
    await _add_close(db, s.id, 2022, 5, 28, 110.0)  # May 2022 +10%
    await _add_close(db, s.id, 2023, 4, 28, 100.0)
    await _add_close(db, s.id, 2023, 5, 28, 80.0)   # May 2023 -20%
    await db.commit()

    res = await monthly_seasonality(db, s.id)

    may = res.months[4]
    assert may.month == 5 and may.n == 2 and may.positive == 1
    assert may.pct_positive == pytest.approx(50.0)
    assert may.avg_return_pct == pytest.approx(-5.0, rel=1e-6)
    assert may.median_return_pct == pytest.approx(-5.0, rel=1e-6)
    assert may.best_return_pct == pytest.approx(10.0, rel=1e-6)
    assert may.worst_return_pct == pytest.approx(-20.0, rel=1e-6)
    assert may.avg_positive_pct == pytest.approx(10.0, rel=1e-6)
    assert may.avg_negative_pct == pytest.approx(-20.0, rel=1e-6)
