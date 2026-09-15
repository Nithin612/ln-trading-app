"""V3 / A4 — a held name that leaves the tradeable universe is HOLD-ONLY.

⭐ **The state PART XVIII missed entirely, and the one with money attached (Kimi).** After
D2′b the universe rule owns `stocks.is_active` and evaluates nightly, so a name you HOLD
can leave the universe overnight. U17 keeps its ticks alive — the position can still be
priced, monitored and exited — but until now **nothing stopped you buying more of it**:
there was no restriction for membership anywhere in the registry.

The message has to be specific, and it is a different sentence from every other block in
the system: *you can exit an existing position, not open or add to one.*
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.signal import Signal
from app.services.universe_materialiser import apply_to_stocks
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock

EXIT_NOT_REENTER = "exit an existing position"


async def _make_signal(db: AsyncSession, stock_id: int) -> Signal:
    now = datetime.now(tz=UTC)
    sig = Signal(
        stock_id=stock_id, direction="BUY", classification="swing", timeframe="1d",
        entry_price="500.0000", stop_loss="480.0000", take_profit="560.0000",
        suggested_qty=100, confidence_pct=80,
        # Two scoring factors: the ACTIVE diversity gate rejects a single-factor signal,
        # and a fixture that trips a DIFFERENT gate would prove nothing about this one.
        factor_scores={
            "DOW_TREND": {"weight": 20, "score": 0.8, "explanation": "up"},
            "MACD_CROSS": {"weight": 15, "score": 0.6, "explanation": "x"},
        },
        headline="t", status="active", is_shadow=False,
        created_at=now, validity_until=now + timedelta(days=5),
    )
    db.add(sig)
    await db.flush()
    return sig


async def _order(client: AsyncClient, headers: dict[str, str], signal_id: str):  # type: ignore[no-untyped-def]
    return await client.post(
        "/api/v1/trading/orders",
        json={"signal_id": signal_id, "side": "BUY"},
        headers=headers,
    )


class TestTheOrderPathRefusesReEntry:
    async def test_a_name_outside_the_universe_409s_with_the_exit_not_reenter_reason(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db, symbol="GONE", is_active=False)
        sig = await _make_signal(db, stock.id)
        await db.commit()

        resp = await _order(client, headers, str(sig.id))
        assert resp.status_code == 409, resp.text
        assert EXIT_NOT_REENTER in resp.json()["detail"]

    async def test_a_name_inside_the_universe_still_fills(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """The canary: without it, a gate that blocks EVERYTHING passes the test above."""
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db, symbol="HERE", is_active=True)
        sig = await _make_signal(db, stock.id)
        await db.commit()

        resp = await _order(client, headers, str(sig.id))
        assert resp.status_code == 201, resp.text

    async def test_the_block_has_no_mode_and_cannot_be_switched_off(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """⚠ `always_on`, like U11's quarantine. Membership is a RECORDED VERDICT of the
        universe rule, not a claim about the tape that might be wrong — giving it a mode
        would create an `off` that silently re-admits a name the rule excluded, and
        `is_active` is precisely the flag whose uncoordinated writers broke the system on
        2026-09-07. This asserts there is no knob to find."""
        from app.signals import restrictions

        assert restrictions.GATE_UNIVERSE not in restrictions.MODED_GATES
        rule = next(
            r for r in restrictions.REGISTRY if r.gate == restrictions.GATE_UNIVERSE
        )
        assert rule.always_on is True


class TestDisplayAndOrderPathsAgree:
    async def test_the_listed_reason_is_the_409_verbatim(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """⭐ The contract that keeps the five Buy surfaces honest: what the list renders
        as `⊘ Blocked` must be the exact sentence the order path returns. A row that is
        offered and then 409s is how this project collected toast screenshots once."""
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db, symbol="GONE2", is_active=False)
        sig = await _make_signal(db, stock.id)
        await db.commit()

        listed = await client.get("/api/v1/signals/active", headers=headers)
        assert listed.status_code == 200
        row = next(r for r in listed.json()["signals"] if r["id"] == str(sig.id))
        assert row["blocked"] is True
        assert row["blocked_by"] == "universe_membership"

        refused = await _order(client, headers, str(sig.id))
        assert refused.status_code == 409
        assert row["block_reason"] == refused.json()["detail"]

    async def test_the_row_is_still_listed_rather_than_hidden(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """⚠ Blocked, never hidden. A filtered signal simply vanishes, which is the
        invisibility PART XVIII objects to; a restriction keeps it on screen with its
        reason attached."""
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db, symbol="GONE3", is_active=False)
        sig = await _make_signal(db, stock.id)
        await db.commit()

        listed = await client.get("/api/v1/signals/active", headers=headers)
        assert str(sig.id) in {r["id"] for r in listed.json()["signals"]}


class TestItTracksTheRuleRatherThanASnapshot:
    async def test_a_name_the_rule_deactivates_becomes_hold_only(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """⭐⭐ End-to-end through the REAL writer, not by setting the flag by hand: the
        universe rule is applied by `apply_to_stocks` (the only path a database trigger
        permits), and the block must follow from that rather than from a fixture. This is
        the overnight sequence A4 describes, in one test."""
        await create_test_user(db)
        headers = await get_auth_headers(client)
        keep = await make_stock(db, symbol="KEEP", is_active=True)
        drop = await make_stock(db, symbol="DROP", is_active=True)
        sig_keep = await _make_signal(db, keep.id)
        sig_drop = await _make_signal(db, drop.id)
        # Tonight's snapshot contains KEEP only — DROP left the universe.
        for sid in (keep.id,):
            await db.execute(
                text(
                    "INSERT INTO universe_snapshot (as_of, stock_id, rule_version)"
                    " VALUES (CURRENT_DATE, :s, 'v1')"
                ),
                {"s": sid},
            )
        await db.commit()

        # min_fraction=0 so the collapse rail does not refuse a deliberately tiny fixture.
        await apply_to_stocks(db, as_of=datetime.now(tz=UTC).date(), min_fraction=0.0)

        assert (await _order(client, headers, str(sig_drop.id))).status_code == 409
        assert (await _order(client, headers, str(sig_keep.id))).status_code == 201
