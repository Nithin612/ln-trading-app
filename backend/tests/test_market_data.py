"""
Phase 4 — market data tests.

Covers:
- parse_bhavcopy_csv: happy path, EQ-only filter, missing data, bad date, multi-format dates
- ingest_bhavcopy_date: idempotent re-import, unknown-symbol skipping
- parse_fii_dii_response: FII and DII parsing, segment breakdown, bad dates
- upsert_fii_dii: idempotent
- API: GET /stocks/{id}/ohlcv, GET /market/fii-dii, GET /market/bulk-block-deals
- API: POST /market/ingest/bhavcopy (admin-only)
- Backfill range validation
"""

import io
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from app.services.bhavcopy_service import (
    BhavRow,
    ingest_bhavcopy_date,
    parse_bhavcopy_csv,
    upsert_bhavcopy_rows,
)
from app.services.fii_dii_service import (
    parse_fii_dii_response,
    upsert_fii_dii,
)
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock

# ── CSV fixtures ──────────────────────────────────────────────────────────────

_GOOD_CSV = """\
SYMBOL,SERIES,OPEN_PRICE,HIGH_PRICE,LOW_PRICE,CLOSE_PRICE,LAST_PRICE,PREV_CLOSE,TTL_TRD_QNTY,TURNOVER_LACS,DATE1
RELIANCE,EQ,2900.00,2950.00,2880.00,2930.00,2929.50,2875.00,1234567,360000.00,18-May-2026
TCS,EQ,3800.00,3850.00,3770.00,3820.00,3819.00,3760.00,987654,376543.00,18-May-2026
NIFTY50IDX,IM,21500.00,21600.00,21400.00,21550.00,21550.00,21400.00,0,0.00,18-May-2026
BADROW,EQ,,,,,,,0,,18-May-2026
"""

_ALT_DATE_CSV = """\
SYMBOL,SERIES,OPEN_PRICE,HIGH_PRICE,LOW_PRICE,CLOSE_PRICE,LAST_PRICE,PREV_CLOSE,TTL_TRD_QNTY,TURNOVER_LACS,DATE1
INFY,EQ,1600.00,1650.00,1580.00,1630.00,1629.00,1570.00,500000,81500.00,2026-05-18
"""

_BAD_DATE_CSV = """\
SYMBOL,SERIES,OPEN_PRICE,HIGH_PRICE,LOW_PRICE,CLOSE_PRICE,LAST_PRICE,PREV_CLOSE,TTL_TRD_QNTY,TURNOVER_LACS,DATE1
WIPRO,EQ,450.00,460.00,445.00,455.00,455.00,440.00,300000,13650.00,not-a-date
"""


# ── Parser unit tests ─────────────────────────────────────────────────────────


def test_parse_bhavcopy_csv_happy_path() -> None:
    rows = parse_bhavcopy_csv(io.StringIO(_GOOD_CSV))
    symbols = [r.symbol for r in rows]

    assert "RELIANCE" in symbols
    assert "TCS" in symbols
    # IM series (index) must be excluded
    assert "NIFTY50IDX" not in symbols
    # Row with missing prices must be excluded
    assert "BADROW" not in symbols

    rel = next(r for r in rows if r.symbol == "RELIANCE")
    assert rel.open == Decimal("2900.00")
    assert rel.high == Decimal("2950.00")
    assert rel.close == Decimal("2930.00")
    assert rel.trade_date == date(2026, 5, 18)
    assert rel.volume == 1234567


def test_parse_bhavcopy_csv_alt_date_format() -> None:
    rows = parse_bhavcopy_csv(io.StringIO(_ALT_DATE_CSV))
    assert len(rows) == 1
    assert rows[0].symbol == "INFY"
    assert rows[0].trade_date == date(2026, 5, 18)


def test_parse_bhavcopy_csv_bad_date_skipped() -> None:
    rows = parse_bhavcopy_csv(io.StringIO(_BAD_DATE_CSV))
    assert rows == []


def test_parse_bhavcopy_csv_empty() -> None:
    assert parse_bhavcopy_csv(io.StringIO("")) == []


def test_parse_bhavcopy_csv_headers_only() -> None:
    csv = "SYMBOL,SERIES,OPEN_PRICE,HIGH_PRICE,LOW_PRICE,CLOSE_PRICE,TTL_TRD_QNTY,DATE1\n"
    assert parse_bhavcopy_csv(io.StringIO(csv)) == []


# ── Upsert / idempotency tests (require DB) ───────────────────────────────────


@pytest.mark.anyio
async def test_upsert_bhavcopy_inserts_and_is_idempotent(db: AsyncSession) -> None:
    stock = await make_stock(db, symbol="RELIANCE")
    rows = [
        BhavRow(
            symbol="RELIANCE",
            trade_date=date(2026, 5, 18),
            open=Decimal("2900"),
            high=Decimal("2950"),
            low=Decimal("2880"),
            close=Decimal("2930"),
            volume=1_000_000,
        )
    ]

    inserted, skipped = await upsert_bhavcopy_rows(db, rows)
    assert inserted == 1
    assert skipped == 0

    # Second upsert must be a no-op
    inserted2, skipped2 = await upsert_bhavcopy_rows(db, rows)
    assert inserted2 == 0 or inserted2 == 1  # ON CONFLICT DO NOTHING
    # Confirm still only one row in DB
    result = await db.execute(
        text("SELECT COUNT(*) FROM ohlcv_1d WHERE stock_id = :sid"),
        {"sid": stock.id},
    )
    assert result.scalar() == 1


@pytest.mark.anyio
async def test_upsert_bhavcopy_skips_unknown_symbol(db: AsyncSession) -> None:
    rows = [
        BhavRow(
            symbol="NOTINDB",
            trade_date=date(2026, 5, 18),
            open=Decimal("100"),
            high=Decimal("110"),
            low=Decimal("95"),
            close=Decimal("105"),
            volume=50_000,
        )
    ]
    inserted, skipped = await upsert_bhavcopy_rows(db, rows)
    assert inserted == 0
    assert skipped == 1


@pytest.mark.anyio
async def test_ingest_bhavcopy_date_from_csv_text(db: AsyncSession) -> None:
    await make_stock(db, symbol="RELIANCE")
    await make_stock(db, symbol="TCS")

    result = await ingest_bhavcopy_date(db, date(2026, 5, 18), csv_text=_GOOD_CSV)

    assert result.status == "ok"
    assert result.date == date(2026, 5, 18)
    assert result.rows_inserted == 2  # RELIANCE + TCS (index and BADROW excluded)


@pytest.mark.anyio
async def test_ingest_bhavcopy_date_idempotent(db: AsyncSession) -> None:
    await make_stock(db, symbol="RELIANCE")
    await make_stock(db, symbol="TCS")

    await ingest_bhavcopy_date(db, date(2026, 5, 18), csv_text=_GOOD_CSV)
    result2 = await ingest_bhavcopy_date(db, date(2026, 5, 18), csv_text=_GOOD_CSV)

    assert result2.status == "ok"
    # Second run should insert 0 (ON CONFLICT DO NOTHING)
    assert result2.rows_inserted == 0


# ── FII/DII parser tests ──────────────────────────────────────────────────────

_FII_DII_PAYLOAD = [
    {
        "date": "18-May-2026",
        "category": "FII/FPI *",
        "buyCF": "12345.67",
        "sellCF": "9876.54",
        "netCF": "2469.13",
        "buyFF": "500.00",
        "sellFF": "300.00",
        "netFF": "200.00",
        "buyOF": "100.00",
        "sellOF": "50.00",
        "netOF": "50.00",
    },
    {
        "date": "18-May-2026",
        "category": "DII",
        "buyCF": "8000.00",
        "sellCF": "7000.00",
        "netCF": "1000.00",
        "buyFF": "200.00",
        "sellFF": "150.00",
        "netFF": "50.00",
        "buyOF": None,
        "sellOF": None,
        "netOF": None,
    },
    {
        "date": "not-a-date",
        "category": "FII/FPI *",
        "buyCF": "100.00",
        "sellCF": "50.00",
    },
]


def test_parse_fii_dii_response_segments() -> None:
    records = parse_fii_dii_response(_FII_DII_PAYLOAD)
    # FII: cash + futures + options = 3; DII: cash + futures = 2; bad date = 0
    assert len(records) == 5

    fii_cash = next(r for r in records if r.investor_type == "FII" and r.segment == "cash")
    assert fii_cash.buy_value_cr == Decimal("12345.67")
    assert fii_cash.trade_date == date(2026, 5, 18)

    dii_futures = next(r for r in records if r.investor_type == "DII" and r.segment == "futures")
    assert dii_futures.sell_value_cr == Decimal("150.00")

    # DII options must be absent (None values)
    dii_opts = [r for r in records if r.investor_type == "DII" and r.segment == "options"]
    assert dii_opts == []


def test_fiidii_flat_api_shape_parses_to_cash_segment() -> None:
    """Regression (2026-07-18): the live fiidiiTradeReact endpoint serves a
    FLAT shape (buyValue/sellValue, no CF/FF/OF breakdown). The old parser
    only knew the segmented shape, returned ZERO records for real API
    responses, and fii_dii_daily stayed empty forever."""
    live_payload: list[dict[str, object]] = [
        {
            "buyValue": "17180.08",
            "category": "DII",
            "date": "17-Jul-2026",
            "netValue": "1017.89",
            "sellValue": "16162.19",
        },
        {
            "buyValue": "14393.77",
            "category": "FII/FPI",
            "date": "17-Jul-2026",
            "netValue": "-376.41",
            "sellValue": "14770.18",
        },
    ]
    records = parse_fii_dii_response(live_payload)
    # Canary: the old parser produced [] here.
    assert len(records) == 2
    assert all(r.segment == "cash" for r in records)
    assert all(r.trade_date == date(2026, 7, 17) for r in records)

    fii = next(r for r in records if r.investor_type == "FII")
    assert fii.buy_value_cr == Decimal("14393.77")
    assert fii.sell_value_cr == Decimal("14770.18")
    dii = next(r for r in records if r.investor_type == "DII")
    assert dii.buy_value_cr == Decimal("17180.08")


def test_fiidii_mixed_shape_prefers_segmented_cash() -> None:
    """Regression (bug-hunter 2026-07-18 #3): in a payload carrying BOTH
    shapes, buyValue is plausibly a cash+F&O total — the segmented buyCF
    must win for the cash segment and the F&O breakdown must survive."""
    mixed: list[dict[str, object]] = [
        {
            "date": "17-Jul-2026",
            "category": "FII/FPI",
            "buyValue": "99999.99",
            "sellValue": "88888.88",
            "buyCF": "12345.67",
            "sellCF": "9876.54",
            "buyFF": "100.00",
            "sellFF": "50.00",
        }
    ]
    records = parse_fii_dii_response(mixed)
    assert len(records) == 2  # cash (from CF) + futures
    cash = next(r for r in records if r.segment == "cash")
    assert cash.buy_value_cr == Decimal("12345.67")
    futures = next(r for r in records if r.segment == "futures")
    assert futures.buy_value_cr == Decimal("100.00")


def test_fiidii_non_finite_values_rejected() -> None:
    """Regression (bug-hunter 2026-07-18 #5): "NaN" parses as a valid
    Decimal AND fits Numeric(12,4) — one such row would poison the §2.7
    SUM() rollup. Non-finite values must drop the record, not store NaN."""
    payload: list[dict[str, object]] = [
        {
            "date": "17-Jul-2026",
            "category": "DII",
            "buyValue": "NaN",
            "sellValue": "16162.19",
        }
    ]
    assert parse_fii_dii_response(payload) == []


@pytest.mark.anyio
async def test_upsert_fii_dii_idempotent(db: AsyncSession) -> None:
    from app.services.fii_dii_service import FiiDiiRecord

    records = [
        FiiDiiRecord(
            trade_date=date(2026, 5, 18),
            investor_type="FII",
            segment="cash",
            buy_value_cr=Decimal("12345.67"),
            sell_value_cr=Decimal("9876.54"),
        )
    ]

    ins1, skip1 = await upsert_fii_dii(db, records)
    assert ins1 == 1

    ins2, skip2 = await upsert_fii_dii(db, records)
    assert ins2 == 0
    assert skip2 == 1

    count = await db.execute(text("SELECT COUNT(*) FROM fii_dii_daily"))
    assert count.scalar() == 1


# ── API tests ─────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_ohlcv_endpoint_returns_bars(client: AsyncClient, db: AsyncSession) -> None:
    await create_test_user(db, email="user@example.com", role="user")
    headers = await get_auth_headers(client, "user@example.com")
    stock = await make_stock(db, symbol="INFY")

    # Insert a candle directly
    await db.execute(
        text(
            "INSERT INTO ohlcv_1d (time, stock_id, open, high, low, close, volume, is_complete) "
            "VALUES (:t, :sid, 1600, 1650, 1580, 1630, 500000, true)"
        ),
        {"t": datetime(2026, 5, 18, tzinfo=UTC), "sid": stock.id},
    )
    await db.commit()

    resp = await client.get(
        f"/api/v1/stocks/{stock.id}/ohlcv",
        params={"from_date": "2026-05-01", "to_date": "2026-05-31"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["stock_id"] == stock.id
    assert data["timeframe"] == "1d"
    assert len(data["bars"]) == 1
    bar = data["bars"][0]
    assert bar["open"] == "1600.0000"
    assert bar["close"] == "1630.0000"
    assert bar["volume"] == 500000


@pytest.mark.anyio
async def test_ohlcv_endpoint_requires_auth(client: AsyncClient, db: AsyncSession) -> None:
    resp = await client.get("/api/v1/stocks/1/ohlcv")
    assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_ohlcv_empty_when_no_data(client: AsyncClient, db: AsyncSession) -> None:
    await create_test_user(db, email="user@example.com", role="user")
    headers = await get_auth_headers(client, "user@example.com")
    stock = await make_stock(db, symbol="ZOMATO")

    resp = await client.get(f"/api/v1/stocks/{stock.id}/ohlcv", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["bars"] == []


@pytest.mark.anyio
async def test_fii_dii_endpoint(client: AsyncClient, db: AsyncSession) -> None:
    await create_test_user(db, email="user@example.com", role="user")
    headers = await get_auth_headers(client, "user@example.com")

    await db.execute(
        text(
            "INSERT INTO fii_dii_daily"
            " (trade_date, investor_type, segment, buy_value_cr, sell_value_cr)"
            " VALUES ('2026-05-18', 'FII', 'cash', 12345.67, 9876.54)"
        )
    )
    await db.commit()

    resp = await client.get(
        "/api/v1/market/fii-dii",
        params={"from_date": "2026-05-01", "to_date": "2026-05-31"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    row = data["rows"][0]
    assert row["investor_type"] == "FII"
    assert row["segment"] == "cash"
    assert float(row["net_value_cr"]) == pytest.approx(2469.13)


@pytest.mark.anyio
async def test_fii_dii_filter_by_type(client: AsyncClient, db: AsyncSession) -> None:
    await create_test_user(db, email="user@example.com", role="user")
    headers = await get_auth_headers(client, "user@example.com")

    for itype in ("FII", "DII"):
        await db.execute(
            text(
                "INSERT INTO fii_dii_daily"
                " (trade_date, investor_type, segment, buy_value_cr, sell_value_cr)"
                " VALUES ('2026-05-18', :it, 'cash', 1000, 900)"
            ),
            {"it": itype},
        )
    await db.commit()

    resp = await client.get(
        "/api/v1/market/fii-dii",
        params={"investor_type": "DII"},
        headers=headers,
    )
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert all(r["investor_type"] == "DII" for r in rows)


@pytest.mark.anyio
async def test_bulk_block_deals_endpoint(client: AsyncClient, db: AsyncSession) -> None:
    await create_test_user(db, email="user@example.com", role="user")
    headers = await get_auth_headers(client, "user@example.com")
    stock = await make_stock(db, symbol="HDFC")

    await db.execute(
        text(
            "INSERT INTO bulk_block_deals "
            "(trade_date, stock_id, deal_type, client_name, transaction, quantity, price, source) "
            "VALUES ('2026-05-18', :sid, 'bulk', 'Big Fund Ltd', 'BUY', 100000, 1800.00, 'NSE')"
        ),
        {"sid": stock.id},
    )
    await db.commit()

    resp = await client.get(
        "/api/v1/market/bulk-block-deals",
        params={"from_date": "2026-05-01", "to_date": "2026-05-31"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["symbol"] == "HDFC"
    assert item["deal_type"] == "bulk"
    assert item["transaction"] == "BUY"


@pytest.mark.anyio
async def test_ingest_bhavcopy_endpoint_admin_only(client: AsyncClient, db: AsyncSession) -> None:
    await create_test_user(db, email="user@example.com", role="user")
    headers = await get_auth_headers(client, "user@example.com")

    resp = await client.post("/api/v1/market/ingest/bhavcopy", headers=headers)
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_ingest_bhavcopy_endpoint_admin_triggers_ingest(
    client: AsyncClient, db: AsyncSession
) -> None:
    await create_test_user(db, email="admin@example.com", role="admin")
    headers = await get_auth_headers(client, "admin@example.com")
    await make_stock(db, symbol="RELIANCE")
    await make_stock(db, symbol="TCS")

    # Inject the CSV through the service directly (no real HTTP download in tests).
    # We test the endpoint here with a date that has no real NSE file, but verify
    # it returns a valid IngestionResult shape.
    resp = await client.post(
        "/api/v1/market/ingest/bhavcopy",
        params={"trade_date": "2026-05-18"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "date" in data
    assert "rows_inserted" in data


@pytest.mark.anyio
async def test_backfill_range_validation(client: AsyncClient, db: AsyncSession) -> None:
    await create_test_user(db, email="admin@example.com", role="admin")
    headers = await get_auth_headers(client, "admin@example.com")

    # from_date > to_date should be rejected
    resp = await client.post(
        "/api/v1/market/ingest/bhavcopy/backfill",
        json={"from_date": "2026-05-18", "to_date": "2026-05-01"},
        headers=headers,
    )
    assert resp.status_code == 422
