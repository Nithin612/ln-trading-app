"""V4 / A2 + A7 — search answers ABSENCE.

⭐ **§45/S2: an absence is not askable.** Everywhere else a name the universe rule
excluded simply is not there, and the user cannot ask why — the UI can only show what it
has. Search is the one surface where the user NAMES a specific stock, so it is the one
place the question can be answered.

⚠ Measured 2026-09-15: **1,104 of 3,395 stocks are invisible to search** — the list
endpoint defaults `is_active=True`, so a third of the master returns nothing, with no
distinction between "no such company" and "excluded, and here is why".
"""
from __future__ import annotations

from datetime import UTC, date, datetime

from app.models.stock import Stock, SymbolHistory
from app.services.stock_resolve import resolve_former_symbol, resolve_search
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock


async def _hits(db: AsyncSession, q: str) -> list:  # type: ignore[type-arg]
    rows = list(
        (await db.execute(select(Stock).where(Stock.symbol.ilike(f"%{q}%")))).scalars()
    )
    return (await resolve_search(db, q, stocks=rows)).hits


class TestAnExcludedNameIsFoundWithItsReason:
    async def test_an_inactive_stock_is_returned_not_hidden(
        self, db: AsyncSession
    ) -> None:
        await make_stock(db, symbol="GONECO", is_active=False)
        await db.commit()
        hits = await _hits(db, "GONECO")
        assert len(hits) == 1
        assert hits[0].in_universe is False and hits[0].suggestible is False
        assert any("Not in the tradeable universe" in r for r in hits[0].exclusion_reasons)

    async def test_a_usable_stock_carries_no_reason(self, db: AsyncSession) -> None:
        """The canary: without it, a resolver that marks EVERYTHING excluded passes the
        test above."""
        await make_stock(db, symbol="GOODCO", is_active=True)
        await db.commit()
        hits = await _hits(db, "GOODCO")
        assert hits[0].suggestible is True
        assert hits[0].exclusion_reasons == ()

    async def test_usable_names_rank_above_excluded_ones(self, db: AsyncSession) -> None:
        """⚠ Excluded names are ranked BELOW, never hidden — the whole point is that they
        stay visible with their reason attached."""
        await make_stock(db, symbol="ZZZGOOD", is_active=True)
        await make_stock(db, symbol="AAABAD", is_active=False)
        await db.commit()
        rows = list((await db.execute(select(Stock))).scalars())
        hits = (await resolve_search(db, "", stocks=rows)).hits
        assert [h.symbol for h in hits] == ["ZZZGOOD", "AAABAD"]


class TestTheTwoExclusionsAreDistinct:
    async def test_a_tradeable_but_quarantined_name_explains_the_gap(
        self, db: AsyncSession
    ) -> None:
        """⭐⭐ THE CASE THAT JUSTIFIES THE FEATURE, and it is live: measured on dev, 5 of
        the 7 CA-quarantined names are ACTIVE. They look perfectly tradeable on every
        surface while `resolve_universe` silently drops them from every suggestion, and
        nothing anywhere could explain the difference."""
        s = await make_stock(db, symbol="SPLITCO", is_active=True)
        s.ca_flagged_at = datetime.now(tz=UTC)
        s.ca_flag_reason = "open 2.26 vs prev close 3.08 (-26.6%)"
        await db.commit()

        hit = (await _hits(db, "SPLITCO"))[0]
        assert hit.in_universe is True  # tradeable …
        assert hit.ca_quarantined is True  # … and quarantined
        assert hit.suggestible is False  # ⇒ absent from suggestions
        assert any("corporate-action detector" in r for r in hit.exclusion_reasons)

    async def test_both_exclusions_are_named_when_both_apply(
        self, db: AsyncSession
    ) -> None:
        """⚠ Two remedies — re-admit vs review the price history. A reader shown only the
        first would chase the wrong one."""
        s = await make_stock(db, symbol="BOTHCO", is_active=False)
        s.ca_flagged_at = datetime.now(tz=UTC)
        await db.commit()
        hit = (await _hits(db, "BOTHCO"))[0]
        assert len(hit.exclusion_reasons) == 2


class TestOldSymbolResolution:
    async def test_a_former_ticker_resolves_to_the_current_row(
        self, db: AsyncSession
    ) -> None:
        """A7 — a rename keeps the row id so bars, signals and positions survive, but the
        old ticker then matches nothing and a user who knows only the old name hits a dead
        end.

        ⛔ Inert in production TODAY by measurement: `symbol_history` holds 3,395 rows and
        **zero closed intervals**, because it was seeded one-open-interval-per-stock and
        no rename has happened since. This fixture creates the closed interval a real
        rename would, so the path is exercised rather than assumed."""
        s = await make_stock(db, symbol="AEROPLANE", is_active=True)
        db.add(
            SymbolHistory(
                stock_id=s.id, symbol="AMIRCHAND", exchange="NSE", isin=None,
                valid_from=date(2020, 1, 1), valid_to=date(2026, 6, 1), reason="rename",
            )
        )
        await db.commit()

        found = await resolve_former_symbol(db, "AMIRCHAND")
        assert found is not None and found.symbol == "AEROPLANE"
        assert found.id == s.id  # the SAME row — positions and bars survive a rename

    async def test_an_open_interval_is_not_a_former_symbol(
        self, db: AsyncSession
    ) -> None:
        """⚠ The canary that stops this matching every stock. Every row has ONE open
        interval carrying its CURRENT ticker; treating those as former symbols would make
        the resolver answer for names that were never renamed."""
        s = await make_stock(db, symbol="CURRENT", is_active=True)
        db.add(
            SymbolHistory(
                stock_id=s.id, symbol="CURRENT", exchange="NSE", isin=None,
                valid_from=date(2020, 1, 1), valid_to=None, reason="seed",
            )
        )
        await db.commit()
        assert await resolve_former_symbol(db, "CURRENT") is None

    async def test_an_unknown_ticker_resolves_to_nothing(self, db: AsyncSession) -> None:
        assert await resolve_former_symbol(db, "NOSUCHTICKER") is None


class TestReasonsDegradeHonestly:
    async def test_no_recorded_inputs_means_no_invented_rule_term(
        self, db: AsyncSession
    ) -> None:
        """⛔ A24. `universe_rule_inputs` is empty until the materialiser beat next runs
        the §73 code, so the rule's per-term reason cannot be justified. The exclusion is
        still reported — it just does not name a term it cannot prove."""
        await make_stock(db, symbol="NOINPUTS", is_active=False)
        await db.commit()
        hit = (await _hits(db, "NOINPUTS"))[0]
        assert hit.reason_as_of is None
        assert hit.exclusion_reasons == ("Not in the tradeable universe.",)
        # …and emphatically not a guess at WHICH term failed.
        assert "EQ series" not in hit.exclusion_reasons[0]


class TestTheEndpoint:
    async def test_search_returns_excluded_names_the_list_endpoint_hides(
        self, db: AsyncSession, client: AsyncClient
    ) -> None:
        """The endpoint must NOT inherit the list's `is_active=True` default — that
        default is the whole defect."""
        await create_test_user(db)
        await make_stock(db, symbol="HIDDEN", is_active=False)
        await db.commit()
        headers = await get_auth_headers(client)

        listed = await client.get("/api/v1/stocks?q=HIDDEN", headers=headers)
        assert listed.json()["total"] == 0  # invisible to the list …

        found = await client.get("/api/v1/stocks/search?q=HIDDEN", headers=headers)
        assert found.status_code == 200, found.text
        body = found.json()
        assert [h["symbol"] for h in body["hits"]] == ["HIDDEN"]  # … but findable here
        assert body["hits"][0]["suggestible"] is False
        assert body["hits"][0]["exclusion_reasons"]

    async def test_the_literal_route_is_not_shadowed_by_the_id_route(
        self, db: AsyncSession, client: AsyncClient
    ) -> None:
        """⚠ FastAPI matches paths in declaration order, so `/search` registered after
        `/{stock_id}` would be swallowed by it and return a 422 for a non-integer id.
        Pinned because the failure looks like a validation bug, not a routing one."""
        await create_test_user(db)
        await db.commit()
        headers = await get_auth_headers(client)
        resp = await client.get("/api/v1/stocks/search?q=ANY", headers=headers)
        assert resp.status_code == 200

    async def test_a_former_ticker_is_reported_as_such(
        self, db: AsyncSession, client: AsyncClient
    ) -> None:
        await create_test_user(db)
        s = await make_stock(db, symbol="AEROPLANE", is_active=True)
        db.add(
            SymbolHistory(
                stock_id=s.id, symbol="AMIRCHAND", exchange="NSE", isin=None,
                valid_from=date(2020, 1, 1), valid_to=date(2026, 6, 1), reason="rename",
            )
        )
        await db.commit()
        headers = await get_auth_headers(client)
        body = (
            await client.get("/api/v1/stocks/search?q=AMIRCHAND", headers=headers)
        ).json()
        assert body["matched_former_symbol"] == "AMIRCHAND"
        assert body["hits"][0]["symbol"] == "AEROPLANE"

    async def test_an_unknown_query_returns_an_empty_list_not_an_error(
        self, db: AsyncSession, client: AsyncClient
    ) -> None:
        await create_test_user(db)
        await db.commit()
        headers = await get_auth_headers(client)
        resp = await client.get("/api/v1/stocks/search?q=NOSUCHTHING", headers=headers)
        assert resp.status_code == 200 and resp.json()["hits"] == []
