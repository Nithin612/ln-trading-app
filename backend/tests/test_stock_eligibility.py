"""V5 / A2 tier 3 — the stock-detail eligibility verdict.

⭐ **The question it answers: why does THIS stock never produce a signal?** Three
independent reasons exist and only the first was visible anywhere:

  1. the universe rule did not admit it;
  2. the CA detector quarantined it — which removes it from every suggestion **even when
     it is perfectly tradeable** (measured: 5 of the 7 quarantined names are ACTIVE);
  3. it has too few daily bars, so `signal_service` never SCORES it at all rather than
     scoring it and declining. V1 measured **184 of 2,286 priced names** dying here, with
     the whole drop being attributed to the confluence gate.

⚠ Round 5 narrowed Gemini's "Refusal Inspector" to exactly this: the verdict belongs on
the page that already exists, not on a new endpoint, and it must come from the backend
(§28 — never let the frontend derive universe state).
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.models.market_data import OhlcvDaily
from app.services.signal_service import MIN_CANDLES_TO_SCORE
from app.services.stock_resolve import load_coverage, resolve_one
from httpx import AsyncClient
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock


async def _bars(db: AsyncSession, stock_id: int, n: int) -> None:
    start = date(2026, 1, 1)
    await db.execute(
        insert(OhlcvDaily),
        [
            {
                "time": datetime.combine(start + timedelta(days=i), datetime.min.time(), UTC),
                "stock_id": stock_id, "open": Decimal("100"), "high": Decimal("101"),
                "low": Decimal("99"), "close": Decimal("100"), "volume": 1000,
                "is_complete": True,
            }
            for i in range(n)
        ],
    )


class TestDataCoverage:
    async def test_a_thin_name_is_short_of_the_scoring_floor(
        self, db: AsyncSession
    ) -> None:
        """⭐ The reason nothing could explain per-stock. A name with too few bars is not
        rejected by the confluence gate — it is never examined."""
        s = await make_stock(db, symbol="THIN", is_active=True)
        await _bars(db, s.id, MIN_CANDLES_TO_SCORE - 10)
        await db.commit()
        cov = await load_coverage(db, s.id)
        assert cov.daily_bars == MIN_CANDLES_TO_SCORE - 10
        assert cov.enough_history is False
        assert cov.shortfall == 10  # the ACTIONABLE number: how many more sessions

    async def test_a_name_at_the_floor_is_admitted(self, db: AsyncSession) -> None:
        """The boundary is inclusive — `signal_service` refuses `< MIN`, not `<= MIN`."""
        s = await make_stock(db, symbol="EXACT", is_active=True)
        await _bars(db, s.id, MIN_CANDLES_TO_SCORE)
        await db.commit()
        cov = await load_coverage(db, s.id)
        assert cov.enough_history is True and cov.shortfall == 0

    async def test_a_name_with_no_bars_reads_zero_not_an_error(
        self, db: AsyncSession
    ) -> None:
        s = await make_stock(db, symbol="NOBARS", is_active=True)
        await db.commit()
        cov = await load_coverage(db, s.id)
        assert cov.daily_bars == 0 and cov.latest_bar is None
        assert cov.shortfall == MIN_CANDLES_TO_SCORE


class TestScannableNeedsBoth:
    async def test_eligible_but_starved_of_history_is_not_scannable(
        self, db: AsyncSession
    ) -> None:
        """⭐⭐ The combination that had no name before. The stock passes every rule and
        still produces nothing, and until now the only visible explanation would have
        been the confluence gate — which never ran."""
        s = await make_stock(db, symbol="NEWLIST", is_active=True)
        await _bars(db, s.id, 5)
        await db.commit()
        resolved = await resolve_one(db, s)
        cov = await load_coverage(db, s.id)
        assert resolved.suggestible is True  # nothing is wrong with it …
        assert cov.enough_history is False  # … it is simply too young to score
        assert (resolved.suggestible and cov.enough_history) is False

    async def test_plenty_of_history_does_not_rescue_an_excluded_name(
        self, db: AsyncSession
    ) -> None:
        """The converse canary — the two conditions are independent, and a reader must
        not infer one from the other."""
        s = await make_stock(db, symbol="OLDGONE", is_active=False)
        await _bars(db, s.id, MIN_CANDLES_TO_SCORE + 100)
        await db.commit()
        resolved = await resolve_one(db, s)
        cov = await load_coverage(db, s.id)
        assert cov.enough_history is True and resolved.suggestible is False


class TestTheEndpoint:
    async def test_detail_carries_the_verdict_and_the_numbers(
        self, db: AsyncSession, client: AsyncClient
    ) -> None:
        await create_test_user(db)
        s = await make_stock(db, symbol="THINCO", is_active=True)
        await _bars(db, s.id, 12)
        await db.commit()
        headers = await get_auth_headers(client)

        body = (await client.get(f"/api/v1/stocks/{s.id}", headers=headers)).json()
        el = body["eligibility"]
        assert el["in_universe"] is True and el["ca_quarantined"] is False
        assert el["suggestible"] is True
        assert el["scannable"] is False  # eligible, but too few bars
        assert el["coverage"]["daily_bars"] == 12
        assert el["coverage"]["shortfall"] == MIN_CANDLES_TO_SCORE - 12

    async def test_a_quarantined_but_tradeable_name_says_so(
        self, db: AsyncSession, client: AsyncClient
    ) -> None:
        """Measured: 5 of the 7 quarantined names are ACTIVE. They look perfectly
        tradeable on every other surface while being dropped from every suggestion."""
        await create_test_user(db)
        s = await make_stock(db, symbol="SPLITCO", is_active=True)
        s.ca_flagged_at = datetime.now(tz=UTC)
        await _bars(db, s.id, MIN_CANDLES_TO_SCORE + 5)
        await db.commit()
        headers = await get_auth_headers(client)

        el = (await client.get(f"/api/v1/stocks/{s.id}", headers=headers)).json()[
            "eligibility"
        ]
        assert el["in_universe"] is True and el["ca_quarantined"] is True
        assert el["suggestible"] is False and el["scannable"] is False
        assert any("corporate-action detector" in r for r in el["exclusion_reasons"])

    async def test_a_healthy_name_is_scannable_with_no_reasons(
        self, db: AsyncSession, client: AsyncClient
    ) -> None:
        """The canary: without it, a panel that marks everything unusable passes above."""
        await create_test_user(db)
        s = await make_stock(db, symbol="GOODCO", is_active=True)
        await _bars(db, s.id, MIN_CANDLES_TO_SCORE + 50)
        await db.commit()
        headers = await get_auth_headers(client)
        el = (await client.get(f"/api/v1/stocks/{s.id}", headers=headers)).json()[
            "eligibility"
        ]
        assert el["scannable"] is True and el["exclusion_reasons"] == []

    async def test_the_list_endpoint_is_unchanged(
        self, db: AsyncSession, client: AsyncClient
    ) -> None:
        """⚠ `StockDetailOut` SUBCLASSES `StockRead` precisely so the list keeps its
        shape — a list has no business paying for a per-row bar count."""
        await create_test_user(db)
        await make_stock(db, symbol="LISTED", is_active=True)
        await db.commit()
        headers = await get_auth_headers(client)
        row = (await client.get("/api/v1/stocks?q=LISTED", headers=headers)).json()[
            "items"
        ][0]
        assert "eligibility" not in row

    async def test_an_unknown_stock_is_still_404(
        self, db: AsyncSession, client: AsyncClient
    ) -> None:
        await create_test_user(db)
        await db.commit()
        headers = await get_auth_headers(client)
        assert (
            await client.get("/api/v1/stocks/999999", headers=headers)
        ).status_code == 404
