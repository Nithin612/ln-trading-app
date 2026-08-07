"""Integration tests for the corporate filings API — Phase 6."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.models.filing import CorporateFiling
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock


async def _auth(
    client: AsyncClient, email: str = "test@example.com", password: str = "Secret123"
) -> dict:
    return await get_auth_headers(client, email=email, password=password)


async def _admin_auth(client: AsyncClient, db: AsyncSession) -> dict:
    await create_test_user(db, email="admin@example.com", password="adminpass123", role="admin")
    return await get_auth_headers(client, email="admin@example.com", password="adminpass123")


async def _make_filing(
    db: AsyncSession,
    stock_id: int,
    filing_type: str = "earnings",
    hours_ago: float = 1.0,
    source: str = "NSE",
    headline: str | None = None,
) -> CorporateFiling:
    filing_time = datetime.now(tz=UTC) - timedelta(hours=hours_ago)
    f = CorporateFiling(
        stock_id=stock_id,
        filing_type=filing_type,
        headline=headline or f"Test {filing_type}",
        filing_date=filing_time.date(),
        filing_time=filing_time,
        source=source,
    )
    db.add(f)
    await db.flush()
    return f


class TestFilingsRecent:
    async def test_requires_auth(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/filings/recent")
        assert r.status_code == 401

    async def test_empty_when_no_filings(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await _auth(client)
        r = await client.get("/api/v1/filings/recent", headers=headers)
        assert r.status_code == 200
        assert r.json()["total"] == 0

    async def test_returns_recent_filings(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await _auth(client)
        stock = await make_stock(db, symbol="RELIANCE")
        await _make_filing(db, stock.id, filing_type="earnings", hours_ago=2)
        await db.commit()

        r = await client.get("/api/v1/filings/recent?hours=24", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["filings"][0]["filing_type"] == "earnings"
        assert data["filings"][0]["symbol"] == "RELIANCE"

    async def test_excludes_outside_window(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await _auth(client)
        stock = await make_stock(db, symbol="TATAPOWER")
        await _make_filing(db, stock.id, hours_ago=50)  # outside default 24h window
        await db.commit()

        r = await client.get("/api/v1/filings/recent?hours=24", headers=headers)
        assert r.json()["total"] == 0

    async def test_default_page_lookback_is_accepted(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """Regression: the Filings page's own default view used to 422.

        Its date pickers default to a 7-day range, which spans 8 calendar days
        once the end day is included → hours=192, over the old `le=168` cap. The
        page therefore rendered empty on every load. Canary: on the old code
        this assertion sees 422.
        """
        await create_test_user(db)
        headers = await _auth(client)
        stock = await make_stock(db, symbol="LT")
        await _make_filing(db, stock.id, hours_ago=180)
        await db.commit()

        r = await client.get("/api/v1/filings/recent?hours=192", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["total"] == 1

    async def test_hours_over_one_year_still_rejected(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """The cap moved to a year; it did not disappear."""
        await create_test_user(db)
        headers = await _auth(client)
        r = await client.get("/api/v1/filings/recent?hours=8761", headers=headers)
        assert r.status_code == 422

    async def test_date_range_bounds_both_ends(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """Regression: the end date was discarded (only a look-back was sent).

        A range ending days ago must NOT return filings newer than it. Canary:
        the old handler had no upper bound at all, so `recent` came back too.
        """
        await create_test_user(db)
        headers = await _auth(client)
        stock = await make_stock(db, symbol="SBIN")
        ist = ZoneInfo("Asia/Kolkata")
        today_ist = datetime.now(tz=UTC).astimezone(ist).date()
        old = today_ist - timedelta(days=10)

        await _make_filing(db, stock.id, hours_ago=1, headline="recent")
        # Squarely inside the old IST day, immune to the 5:30 offset.
        in_window = datetime.combine(old, time(12, 0), tzinfo=ist).astimezone(UTC)
        db.add(
            CorporateFiling(
                stock_id=stock.id,
                filing_type="earnings",
                headline="in-window",
                filing_date=in_window.date(),
                filing_time=in_window,
                source="NSE",
            )
        )
        await db.commit()

        r = await client.get(
            f"/api/v1/filings/recent?start_date={old - timedelta(days=1)}&end_date={old}",
            headers=headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] == 1
        assert data["filings"][0]["headline"] == "in-window"

    async def test_date_range_includes_the_whole_end_day(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """end_date is INCLUSIVE — an evening IST filing on that day counts."""
        await create_test_user(db)
        headers = await _auth(client)
        stock = await make_stock(db, symbol="ITC")
        ist = ZoneInfo("Asia/Kolkata")
        day = datetime.now(tz=UTC).astimezone(ist).date() - timedelta(days=3)
        evening = datetime.combine(day, time(21, 30), tzinfo=ist).astimezone(UTC)
        db.add(
            CorporateFiling(
                stock_id=stock.id,
                filing_type="earnings",
                headline="late filing",
                filing_date=evening.date(),
                filing_time=evening,
                source="NSE",
            )
        )
        await db.commit()

        r = await client.get(
            f"/api/v1/filings/recent?start_date={day}&end_date={day}", headers=headers
        )
        assert r.status_code == 200, r.text
        assert r.json()["total"] == 1

    async def test_end_date_alone_still_bounds_the_window(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """An upper bound must never be silently dropped for lacking a partner."""
        await create_test_user(db)
        headers = await _auth(client)
        stock = await make_stock(db, symbol="AXISBANK")
        ist = ZoneInfo("Asia/Kolkata")
        day = datetime.now(tz=UTC).astimezone(ist).date() - timedelta(days=2)
        inside = datetime.combine(day, time(12, 0), tzinfo=ist).astimezone(UTC)
        db.add(
            CorporateFiling(
                stock_id=stock.id,
                filing_type="earnings",
                headline="in-window",
                filing_date=inside.date(),
                filing_time=inside,
                source="NSE",
            )
        )
        await _make_filing(db, stock.id, hours_ago=1, headline="after the window")
        await db.commit()

        r = await client.get(
            f"/api/v1/filings/recent?hours=48&end_date={day}", headers=headers
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] == 1
        assert data["filings"][0]["headline"] == "in-window"

    async def test_reversed_date_range_is_rejected(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await _auth(client)
        r = await client.get(
            "/api/v1/filings/recent?start_date=2026-08-07&end_date=2026-08-01", headers=headers
        )
        assert r.status_code == 422

    async def test_filter_by_filing_type(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await _auth(client)
        stock = await make_stock(db, symbol="HDFC")
        await _make_filing(db, stock.id, filing_type="earnings", hours_ago=1)
        await _make_filing(db, stock.id, filing_type="dividend", hours_ago=2)
        await db.commit()

        r = await client.get("/api/v1/filings/recent?filing_type=earnings", headers=headers)
        data = r.json()
        assert data["total"] == 1
        assert data["filings"][0]["filing_type"] == "earnings"

    async def test_sorted_newest_first(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await _auth(client)
        stock = await make_stock(db, symbol="INFY")
        await _make_filing(db, stock.id, hours_ago=5)
        await _make_filing(db, stock.id, hours_ago=2)
        await db.commit()

        r = await client.get("/api/v1/filings/recent?hours=24", headers=headers)
        times = [f["filing_time"] for f in r.json()["filings"]]
        assert times == sorted(times, reverse=True)

    async def test_is_high_impact_flag(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await _auth(client)
        stock = await make_stock(db, symbol="WIPRO")
        await _make_filing(db, stock.id, filing_type="earnings", hours_ago=1)
        await _make_filing(db, stock.id, filing_type="board_meeting", hours_ago=2)
        await db.commit()

        r = await client.get("/api/v1/filings/recent?hours=24", headers=headers)
        by_type = {f["filing_type"]: f["is_high_impact"] for f in r.json()["filings"]}
        assert by_type["earnings"] is True
        assert by_type["board_meeting"] is False


class TestFilingsByStock:
    async def test_returns_404_for_unknown_stock(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await _auth(client)
        r = await client.get("/api/v1/filings/by-stock/99999", headers=headers)
        assert r.status_code == 404

    async def test_returns_filings_for_stock(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await _auth(client)
        stock = await make_stock(db, symbol="BAJFINANCE")
        await _make_filing(db, stock.id, filing_type="earnings")
        await db.commit()

        r = await client.get(f"/api/v1/filings/by-stock/{stock.id}", headers=headers)
        assert r.status_code == 200
        assert r.json()["total"] == 1


class TestEventGuardEndpoint:
    async def test_not_suppressed_when_no_filings(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await _auth(client)
        stock = await make_stock(db, symbol="FREECO")

        r = await client.get(f"/api/v1/filings/guard/{stock.id}", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["suppressed"] is False
        assert data["reason"] is None

    async def test_suppressed_after_earnings(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await _auth(client)
        stock = await make_stock(db, symbol="EARCO2")
        await _make_filing(db, stock.id, filing_type="earnings", hours_ago=0.25)
        await db.commit()

        r = await client.get(f"/api/v1/filings/guard/{stock.id}", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["suppressed"] is True
        assert data["suppressed_until"] is not None

    async def test_guard_404_on_missing_stock(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await _auth(client)
        r = await client.get("/api/v1/filings/guard/99999", headers=headers)
        assert r.status_code == 404


class TestFilingsIngestAdmin:
    async def test_ingest_requires_admin(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await _auth(client)
        r = await client.post("/api/v1/filings/ingest", headers=headers)
        assert r.status_code == 403

    async def test_ingest_returns_202(self, client: AsyncClient, db: AsyncSession) -> None:
        headers = await _admin_auth(client, db)
        # No live network in tests — ingest_filings will return 0 (empty universe or network fail)
        r = await client.post("/api/v1/filings/ingest", headers=headers)
        assert r.status_code == 202
        assert "inserted" in r.json()
