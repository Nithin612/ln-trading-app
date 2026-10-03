"""`GET /stocks/sparklines` — REAL recent closes for the table sparklines.

The canary: three tables drew a sparkline per row from invented data — `seededSpark(stock.id)`
(a PRNG seeded by the row id) on Stocks/Screener and `generateFakeSpark(entry, sl, tp)` on the
Dashboard — and coloured it green/red by the invented path's direction. A row with no history
must come back ABSENT so the UI renders "not assessable", never a placeholder line.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.models.market_data import OhlcvDaily
from app.services.stock_service import load_sparklines
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock

NOW = datetime(2027, 3, 31, 12, tzinfo=UTC)


def _bar(stock_id: int, days_ago: int, close: str, complete: bool = True) -> OhlcvDaily:
    t = (NOW - timedelta(days=days_ago)).replace(hour=0)
    c = Decimal(close)
    return OhlcvDaily(time=t, stock_id=stock_id, open=c, high=c, low=c, close=c, volume=1,
                      is_complete=complete)


async def test_last_n_completed_closes_oldest_first(db: AsyncSession) -> None:
    s = await make_stock(db, symbol="SPK")
    for i, close in enumerate(["10", "11", "12", "13", "14"]):
        db.add(_bar(s.id, days_ago=5 - i, close=close))
    db.add(_bar(s.id, days_ago=0, close="99", complete=False))  # forming — never drawn
    await db.commit()
    assert await load_sparklines(db, [s.id], 3, now=NOW) == {s.id: [12.0, 13.0, 14.0]}


async def test_history_outside_the_lookback_or_single_bar_is_absent(db: AsyncSession) -> None:
    stale = await make_stock(db, symbol="STALE")
    one = await make_stock(db, symbol="ONEBAR")
    empty = await make_stock(db, symbol="EMPTY")
    db.add_all([_bar(stale.id, 60, "5"), _bar(stale.id, 59, "6"), _bar(one.id, 1, "7")])
    await db.commit()
    assert await load_sparklines(db, [stale.id, one.id, empty.id], 20, now=NOW) == {}


async def test_endpoint_batches_and_is_not_swallowed_by_the_detail_route(
    client: AsyncClient, db: AsyncSession
) -> None:
    a = await make_stock(db, symbol="AAA")
    b = await make_stock(db, symbol="BBB")
    now = datetime.now(tz=UTC)
    for i in range(3):
        c = Decimal(100 + i)
        db.add(OhlcvDaily(time=now - timedelta(days=3 - i), stock_id=a.id, open=c, high=c,
                          low=c, close=c, volume=1))
    await create_test_user(db, email="spark@example.com")
    await db.commit()
    headers = await get_auth_headers(client, email="spark@example.com")
    r = await client.get(f"/api/v1/stocks/sparklines?ids={a.id},{b.id}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["points"] == 20
    assert body["series"] == {str(a.id): [100.0, 101.0, 102.0]}  # b absent, not []


async def test_endpoint_rejects_garbage_and_oversized_batches(
    client: AsyncClient, db: AsyncSession
) -> None:
    await create_test_user(db, email="spark2@example.com")
    headers = await get_auth_headers(client, email="spark2@example.com")
    url = "/api/v1/stocks/sparklines?ids="
    assert (await client.get(url + "1,x", headers=headers)).status_code == 422
    too_many = ",".join(str(i) for i in range(1, 502))
    assert (await client.get(url + too_many, headers=headers)).status_code == 422
    assert (await client.get(url + "1")).status_code in (401, 403)
