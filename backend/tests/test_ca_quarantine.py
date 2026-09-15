"""§77 / Q-R3 — the CA quarantine gets a clearing path, and a log of both sides.

⭐ **The defect was measured, not suspected.** `stocks.ca_flagged_at` had exactly one
writer (`ca_detector`) and **no clearer anywhere** — no script, no endpoint — while
`ca_detector`'s own docstring promised "unflag via admin after verifying". On 2026-09-14
the dev DB held 7 flagged stocks, 5 of them active, **4 flagged that same day**: the
tradeable universe was shrinking by roughly four names a week, permanently, and the only
symptom would have been suggestions quietly covering fewer names.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from app.models.corporate_action import CaFlagEvent
from app.models.market_data import OhlcvDaily
from app.models.stock import Stock
from app.services.ca_detector import scan_for_discontinuities
from app.services.ca_quarantine import (
    NotFlaggedError,
    clear_flag,
    history,
    list_flagged,
)
from app.services.universe_service import resolve_universe
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock

CLEAR_REASON = "Verified against NSE: a genuine 22% circuit move, no corporate action."


async def _flag(db: AsyncSession, stock: Stock, *, reason: str = "gap 45%") -> None:
    stock.ca_flagged_at = datetime.now(tz=UTC)
    stock.ca_flag_reason = reason
    await db.flush()


class TestClearing:
    async def test_clearing_releases_the_stock_back_into_universes(
        self, db: AsyncSession
    ) -> None:
        """⭐ The consequence that matters: a flagged stock is excluded from every
        suggestion universe, so this asserts through `resolve_universe`, not just the
        column."""
        stock = await make_stock(db, symbol="AAA", is_active=True)
        user = await create_test_user(db)
        await _flag(db, stock)
        await db.commit()

        spec = {"kind": "all_active", "value": None}
        ids, _syms = await resolve_universe(db, spec)
        assert stock.id not in ids  # quarantined, invisible to every universe

        cleared = await clear_flag(
            db, stock_id=stock.id, actor_user_id=user.id, reason=CLEAR_REASON
        )
        assert cleared.symbol == "AAA"
        ids_after, syms_after = await resolve_universe(db, spec)
        assert stock.id in ids_after and syms_after[stock.id] == "AAA"
        await db.refresh(stock)
        assert stock.ca_flagged_at is None and stock.ca_flag_reason is None

    async def test_clearing_an_unflagged_stock_is_refused(
        self, db: AsyncSession
    ) -> None:
        """A no-op that returned success would teach the caller nothing."""
        stock = await make_stock(db, symbol="AAA")
        user = await create_test_user(db)
        await db.commit()
        with pytest.raises(NotFlaggedError):
            await clear_flag(
                db, stock_id=stock.id, actor_user_id=user.id, reason=CLEAR_REASON
            )

    async def test_clearing_an_unknown_stock_is_refused_the_same_way(
        self, db: AsyncSession
    ) -> None:
        user = await create_test_user(db)
        await db.commit()
        with pytest.raises(NotFlaggedError):
            await clear_flag(
                db, stock_id=999_999, actor_user_id=user.id, reason=CLEAR_REASON
            )


class TestTheLogIsAppendOnly:
    async def test_a_reflag_does_not_erase_the_review_that_released_it(
        self, db: AsyncSession
    ) -> None:
        """⭐⭐ THE REASON THIS IS A LOG AND NOT THREE COLUMNS ON `stocks`.

        The detector skips rows where `ca_flagged_at IS NULL`, so a cleared name CAN be
        flagged again — and a single `ca_cleared_at/_by/_reason` triple would be
        OVERWRITTEN by that next flag. §41 named the trap when it refused to drop
        `uq_stocks_symbol_exchange`: **the merge overwrites its own evidence**, and the
        rate of the thing you wanted to measure becomes unmeasurable retrospectively."""
        stock = await make_stock(db, symbol="AAA")
        user = await create_test_user(db)
        await _flag(db, stock, reason="first gap 45%")
        db.add(CaFlagEvent(stock_id=stock.id, event="flagged", reason="first gap 45%"))
        await db.commit()

        await clear_flag(
            db, stock_id=stock.id, actor_user_id=user.id, reason=CLEAR_REASON
        )
        await _flag(db, stock, reason="second gap 38%")  # the detector strikes again
        db.add(CaFlagEvent(stock_id=stock.id, event="flagged", reason="second gap 38%"))
        await db.commit()

        events = await history(db, stock_id=stock.id)
        assert [e.event for e in events] == ["flagged", "cleared", "flagged"]
        # The review survives the re-flag, with its author and its justification.
        review = events[1]
        assert review.reason == CLEAR_REASON and review.actor_user_id == user.id
        # …and the machine's flags carry no actor, which is the asymmetry: a machine may
        # quarantine, only a person may release.
        assert events[0].actor_user_id is None and events[2].actor_user_id is None

    async def test_the_detector_writes_its_own_side_of_the_log(
        self, db: AsyncSession
    ) -> None:
        """The flag and its event must land in ONE transaction — a log that can disagree
        with `stocks` is worse than no log."""
        stock = await make_stock(db, symbol="AAA")
        d1, d2 = date(2026, 9, 10), date(2026, 9, 11)
        for d, o, c in ((d1, 100, 100), (d2, 45, 45)):  # a 55% gap down
            db.add(
                OhlcvDaily(
                    time=datetime(d.year, d.month, d.day, tzinfo=UTC), stock_id=stock.id,
                    open=Decimal(o), high=Decimal(o), low=Decimal(o), close=Decimal(c),
                    volume=1000, is_complete=True,
                )
            )
        await db.commit()

        flagged = await scan_for_discontinuities(db, d2)
        assert len(flagged) == 1
        await db.refresh(stock)
        assert stock.ca_flagged_at is not None

        events = await history(db, stock_id=stock.id)
        assert len(events) == 1 and events[0].event == "flagged"
        assert events[0].actor_user_id is None
        assert "possible corporate action" in events[0].reason

    async def test_clearing_adds_a_row_rather_than_editing_one(
        self, db: AsyncSession
    ) -> None:
        stock = await make_stock(db, symbol="AAA")
        user = await create_test_user(db)
        await _flag(db, stock)
        db.add(CaFlagEvent(stock_id=stock.id, event="flagged", reason="gap"))
        await db.commit()
        before = (
            await db.execute(select(func.count()).select_from(CaFlagEvent))
        ).scalar()
        await clear_flag(
            db, stock_id=stock.id, actor_user_id=user.id, reason=CLEAR_REASON
        )
        after = (
            await db.execute(select(func.count()).select_from(CaFlagEvent))
        ).scalar()
        assert after == (before or 0) + 1


class TestTheReviewQueue:
    async def test_the_queue_is_oldest_first_and_includes_inactive_names(
        self, db: AsyncSession
    ) -> None:
        """⚠ Inactive names are included deliberately: the quarantine and the universe
        rule are independent, and a reviewer should see the whole set rather than the
        subset that happens to be tradeable today."""
        old = await make_stock(db, symbol="OLD", is_active=False)
        new = await make_stock(db, symbol="NEW", is_active=True)
        await make_stock(db, symbol="CLEAN", is_active=True)
        now = datetime.now(tz=UTC)
        old.ca_flagged_at, old.ca_flag_reason = now - timedelta(days=3), "old gap"
        new.ca_flagged_at, new.ca_flag_reason = now, "new gap"
        await db.commit()

        queue = await list_flagged(db)
        assert [f.symbol for f in queue] == ["OLD", "NEW"]  # oldest first, CLEAN absent
        assert queue[0].is_active is False and queue[1].is_active is True
        assert queue[0].reason == "old gap"


class TestTheApi:
    async def test_admin_can_list_clear_and_read_the_history(
        self, db: AsyncSession, client: AsyncClient
    ) -> None:
        stock = await make_stock(db, symbol="AAA", is_active=True)
        admin = await create_test_user(db, email="admin@example.com", role="admin")
        await _flag(db, stock)
        db.add(CaFlagEvent(stock_id=stock.id, event="flagged", reason="gap 45%"))
        await db.commit()
        headers = await get_auth_headers(client, "admin@example.com")

        listed = await client.get(
            "/api/v1/corporate-actions/quarantine", headers=headers
        )
        assert listed.status_code == 200
        assert [r["symbol"] for r in listed.json()] == ["AAA"]

        cleared = await client.post(
            f"/api/v1/corporate-actions/quarantine/{stock.id}/clear",
            headers=headers, json={"reason": CLEAR_REASON},
        )
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["symbol"] == "AAA"

        empty = await client.get(
            "/api/v1/corporate-actions/quarantine", headers=headers
        )
        assert empty.json() == []

        log = await client.get(
            f"/api/v1/corporate-actions/quarantine/{stock.id}/history", headers=headers
        )
        assert [e["event"] for e in log.json()] == ["flagged", "cleared"]
        assert log.json()[1]["actor_user_id"] == admin.id

    async def test_clearing_an_unflagged_stock_is_404(
        self, db: AsyncSession, client: AsyncClient
    ) -> None:
        stock = await make_stock(db, symbol="AAA")
        await create_test_user(db, email="admin@example.com", role="admin")
        await db.commit()
        headers = await get_auth_headers(client, "admin@example.com")
        resp = await client.post(
            f"/api/v1/corporate-actions/quarantine/{stock.id}/clear",
            headers=headers, json={"reason": CLEAR_REASON},
        )
        assert resp.status_code == 404

    async def test_a_thin_reason_is_rejected(
        self, db: AsyncSession, client: AsyncClient
    ) -> None:
        """⚠ "cleared" with no justification is not an audit trail — it is the same
        monotonic-accumulator problem one step later, where nobody can tell a reviewed
        release from a careless one."""
        stock = await make_stock(db, symbol="AAA")
        await create_test_user(db, email="admin@example.com", role="admin")
        await _flag(db, stock)
        await db.commit()
        headers = await get_auth_headers(client, "admin@example.com")
        resp = await client.post(
            f"/api/v1/corporate-actions/quarantine/{stock.id}/clear",
            headers=headers, json={"reason": "ok"},
        )
        assert resp.status_code == 422

    async def test_a_non_admin_cannot_clear(
        self, db: AsyncSession, client: AsyncClient
    ) -> None:
        stock = await make_stock(db, symbol="AAA")
        await create_test_user(db, email="plain@example.com")
        await _flag(db, stock)
        await db.commit()
        headers = await get_auth_headers(client, "plain@example.com")
        resp = await client.post(
            f"/api/v1/corporate-actions/quarantine/{stock.id}/clear",
            headers=headers, json={"reason": CLEAR_REASON},
        )
        assert resp.status_code in (401, 403)
