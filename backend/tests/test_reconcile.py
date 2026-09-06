"""Phase 7.4 — kill switch, restart recovery, reconciliation, and T2 lifecycle boundaries.

Two assertions here are the ones that would actually save money:

- **the kill switch does not block exits.** A switch that halts new risk *and* traps you
  in what you already hold is a hazard dressed as a safety feature, and the moment you
  most want to stop trading is often the moment you most need to close something;
- **reconciliation names what it could NOT check.** Against the paper gateway the
  order-matching half verifies nothing at all, and a run that reported "clean" without
  saying so would be actively misleading.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.broker import event_store, reconcile
from app.broker.adapter import BrokerPosition, EventKind
from app.broker.paper_adapter import PaperBrokerAdapter
from app.core.config import get_settings
from app.models.signal import Signal
from app.models.trading import Position
from app.models.user import User
from app.trading import risk_engine as rx
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock

_FACTORS = {
    "DOW_TREND": {"weight": 20, "score": 0.8, "explanation": "uptrend"},
    "MACD_CROSS": {"weight": 15, "score": 0.6, "explanation": "bull cross"},
}


async def _make_signal(db: AsyncSession, stock_id: int) -> Signal:
    now = datetime.now(tz=UTC)
    sig = Signal(
        stock_id=stock_id, direction="BUY", classification="swing", timeframe="1d",
        entry_price="500.0000", stop_loss="480.0000", take_profit="540.0000",
        suggested_qty=100, confidence_pct=80, factor_scores=_FACTORS,
        headline="BUY RECON", status="active",
        validity_until=now + timedelta(days=5), created_at=now,
    )
    db.add(sig)
    await db.flush()
    return sig


async def _open_position(
    db: AsyncSession, user: User, stock_id: int, *, qty: int = 100, side: str = "LONG"
) -> Position:
    pos = Position(
        user_id=user.id, stock_id=stock_id, mode="paper", side=side, quantity=qty,
        avg_entry_price=Decimal("500"), current_sl=Decimal("480"),
        realized_pnl=Decimal("0"), opened_at=datetime.now(tz=UTC),
    )
    db.add(pos)
    await db.flush()
    return pos


def _sink() -> tuple[list, object]:
    events: list = []
    return events, events.append


# ── 1. the kill switch ────────────────────────────────────────────────────────


class TestKillSwitch:
    def test_it_runs_first(self) -> None:
        """Ahead of even the breaker: someone who has hit stop must not have to reason
        about which other rule might still let an order through."""
        assert rx.PRE_TRADE_RULES[0] == rx.RULE_KILL_SWITCH

    def test_it_is_a_plain_bool_with_no_shadow_mode(self) -> None:
        """A kill switch you can set to measure-only is not a kill switch.

        The three-valued gate vocabulary would invite exactly that, so the knob is
        deliberately outside it.
        """
        from app.core.config import Settings

        ann = Settings.model_fields["trading_kill_switch"].annotation
        assert ann is bool

    async def test_it_denies_entries(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(get_settings(), "trading_kill_switch", True, raising=False)
        user = await create_test_user(db)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await db.commit()

        verdict = await rx.check_pre_trade(
            db, user, signal, side="BUY", allow_offmarket=True
        )
        assert verdict.denied
        assert verdict.rule == rx.RULE_KILL_SWITCH

    async def test_it_beats_every_other_rule(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With the breaker ALSO tripped, the kill switch is what answers — it is the
        human's stop and must not be masked by a machine's."""
        monkeypatch.setattr(get_settings(), "trading_kill_switch", True, raising=False)
        user = await create_test_user(db)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        now = datetime.now(tz=UTC)
        db.add(
            Position(
                user_id=user.id, stock_id=stock.id, mode="paper", side="LONG",
                quantity=100, avg_entry_price=Decimal("500"), current_sl=Decimal("480"),
                realized_pnl=Decimal("-99999"), opened_at=now, closed_at=now,
                signal_id=signal.id,
            )
        )
        await db.commit()

        verdict = await rx.check_pre_trade(
            db, user, signal, side="BUY", allow_offmarket=True
        )
        assert verdict.rule == rx.RULE_KILL_SWITCH

    async def test_it_does_not_block_exits(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """⭐ The property that makes it safe to use.

        A switch that halts new risk AND traps you in open positions is a hazard dressed
        as a safety feature. Exits run through `close_position`, which does not consult
        the entry path — asserted end to end so a future refactor that routes exits
        through the RiskEngine cannot silently make the switch a trap.
        """
        user = await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        pos = await _open_position(db, user, stock.id)
        await db.commit()

        monkeypatch.setattr(get_settings(), "trading_kill_switch", True, raising=False)
        r = await client.post(
            f"/api/v1/trading/positions/{pos.id}/close", json={}, headers=headers
        )
        assert r.status_code == 200, (
            "the kill switch must never trap a position — exits stay open"
        )

    async def test_the_endpoint_reports_it(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """And the refusal is recorded, like every other denial."""
        user = await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await db.commit()

        monkeypatch.setattr(get_settings(), "trading_kill_switch", True, raising=False)
        r = await client.post(
            "/api/v1/trading/orders",
            json={"signal_id": signal.id, "side": "BUY"},
            headers=headers,
        )
        assert r.status_code == 409
        assert "kill switch" in r.json()["detail"].lower()

        refusals = await event_store.refusals_between(
            db,
            user_id=user.id,
            start=datetime.now(tz=UTC) - timedelta(minutes=1),
            end=datetime.now(tz=UTC) + timedelta(minutes=1),
        )
        assert len(refusals) == 1
        assert refusals[0].payload["rule"] == rx.RULE_KILL_SWITCH


# ── 2. restart recovery ───────────────────────────────────────────────────────


class TestRecovery:
    async def test_terminal_orders_are_not_recovered(self, db: AsyncSession) -> None:
        """A filled order needs nothing done to it."""
        user = await create_test_user(db)
        await db.commit()
        for kind in (EventKind.SUBMITTED, EventKind.ACCEPTED, EventKind.FILLED):
            await event_store.append(
                db, client_order_id="paper:done", kind=kind, user_id=user.id
            )
        await db.commit()

        assert await reconcile.recover_order_states(db, user_id=user.id) == []

    async def test_active_orders_are_recovered(self, db: AsyncSession) -> None:
        """A process holds no memory of what was in flight; the stream is the only thing
        that does."""
        user = await create_test_user(db)
        await db.commit()
        for kind in (EventKind.SUBMITTED, EventKind.ACCEPTED):
            await event_store.append(
                db, client_order_id="paper:live", kind=kind, user_id=user.id
            )
        await db.commit()

        states = await reconcile.recover_order_states(db, user_id=user.id)
        assert len(states) == 1
        assert states[0].client_order_id == "paper:live"
        assert states[0].active

    async def test_recovery_is_idempotent(self, db: AsyncSession) -> None:
        """⭐ Running it twice must not double anything.

        That is what makes it safe to run unconditionally at startup, rather than behind
        a 'have we recovered yet' flag that would itself need recovering. It holds
        because fill quantities in the stream are CUMULATIVE, not deltas.
        """
        user = await create_test_user(db)
        await db.commit()
        for kind, payload in (
            (EventKind.SUBMITTED, {}),
            (EventKind.ACCEPTED, {}),
            (EventKind.PARTIALLY_FILLED, {"filled_qty": 40}),
        ):
            await event_store.append(
                db, client_order_id="paper:p", kind=kind, user_id=user.id, payload=payload
            )
        await db.commit()

        first = await reconcile.recover_order_states(db, user_id=user.id)
        second = await reconcile.recover_order_states(db, user_id=user.id)
        assert [s.filled_qty for s in first] == [40]
        assert [s.filled_qty for s in second] == [40], "replay must not accumulate"

    async def test_full_rebuild_includes_terminal(self, db: AsyncSession) -> None:
        user = await create_test_user(db)
        await db.commit()
        for kind in (EventKind.SUBMITTED, EventKind.DENIED):
            await event_store.append(
                db, client_order_id="paper:d", kind=kind, user_id=user.id
            )
        await db.commit()

        assert await reconcile.recover_order_states(db, user_id=user.id) == []
        full = await reconcile.recover_order_states(db, user_id=user.id, only_active=False)
        assert len(full) == 1
        assert full[0].kind is EventKind.DENIED


# ── 3. reconciliation ─────────────────────────────────────────────────────────


class TestReconciliation:
    async def test_agreeing_book_is_clean(self, db: AsyncSession) -> None:
        user = await create_test_user(db)
        stock = await make_stock(db)
        await _open_position(db, user, stock.id, qty=100)
        await db.commit()

        _events, sink = _sink()
        result = await reconcile.reconcile(db, user, PaperBrokerAdapter(db, user, sink))
        assert result.clean
        assert result.checked_positions == 1

    async def test_a_clean_run_still_names_what_it_could_not_check(
        self, db: AsyncSession
    ) -> None:
        """⭐ The paper gateway cannot exercise reconciliation's main path at all.

        Every paper submit ends terminal in one transaction, so `fetch_open_orders()` is
        structurally empty and there is never a working order to disagree about. A run
        reporting 'clean' without saying so would be actively misleading — it would read
        as evidence that reconciliation works, when it is evidence that there was nothing
        to reconcile.
        """
        user = await create_test_user(db)
        await db.commit()
        _events, sink = _sink()
        result = await reconcile.reconcile(db, user, PaperBrokerAdapter(db, user, sink))

        assert result.clean
        assert result.caveats, "a clean result must carry its own limitations"
        assert any("verified nothing" in c for c in result.caveats)
        assert "⚠" in result.summary()

    async def test_position_drift_is_reported_not_repaired(
        self, db: AsyncSession
    ) -> None:
        """A reconciler that 'fixes' what it does not understand turns a reporting
        discrepancy into a real position."""
        user = await create_test_user(db)
        stock = await make_stock(db)
        pos = await _open_position(db, user, stock.id, qty=100)
        await db.commit()

        _events, sink = _sink()
        adapter = PaperBrokerAdapter(db, user, sink)

        async def _broker_disagrees() -> list[BrokerPosition]:
            return [
                BrokerPosition(
                    symbol=str(stock.id), quantity=60, average_price=Decimal("500")
                )
            ]

        adapter.fetch_positions = _broker_disagrees  # type: ignore[method-assign]
        result = await reconcile.reconcile(db, user, adapter)

        assert not result.clean
        assert len(result.position_drift) == 1
        drift = result.position_drift[0]
        assert drift.local_qty == 100
        assert drift.broker_qty == 60
        assert drift.delta == -40
        # and the local row is untouched
        await db.refresh(pos)
        assert pos.quantity == 100, "reconcile reports; it must never repair"

    async def test_shorts_compare_as_signed_quantities(self, db: AsyncSession) -> None:
        user = await create_test_user(db)
        stock = await make_stock(db)
        await _open_position(db, user, stock.id, qty=40, side="SHORT")
        await db.commit()

        _events, sink = _sink()
        result = await reconcile.reconcile(db, user, PaperBrokerAdapter(db, user, sink))
        assert result.clean, "a short must reconcile as −40 on both sides, not 40 vs −40"

    async def test_summary_reads_differently_when_dirty(self, db: AsyncSession) -> None:
        user = await create_test_user(db)
        stock = await make_stock(db)
        await _open_position(db, user, stock.id, qty=100)
        await db.commit()
        _events, sink = _sink()
        adapter = PaperBrokerAdapter(db, user, sink)

        async def _empty() -> list[BrokerPosition]:
            return []

        adapter.fetch_positions = _empty  # type: ignore[method-assign]
        result = await reconcile.reconcile(db, user, adapter)
        assert not result.clean
        assert "⛔" in result.summary()


# ── 4. T2 — lifecycle boundaries ──────────────────────────────────────────────


class TestLifecycleBoundaries:
    """T2: first step, start mid-stream, stop early.

    `.claude/rules/testing.md`: *453 green tests once coexisted with a dead live
    pipeline — test the SEAMS.* These are the seams where a restart lands.
    """

    async def test_first_step_on_an_empty_world(self, db: AsyncSession) -> None:
        """Recovery on a system that has never traded must be quiet, not an error."""
        user = await create_test_user(db)
        await db.commit()
        assert await reconcile.recover_order_states(db, user_id=user.id) == []

    async def test_start_mid_stream(self, db: AsyncSession) -> None:
        """A process restarting between ACCEPTED and FILLED must recover the order as
        still active — this is the case that decides whether a restart loses a fill."""
        user = await create_test_user(db)
        await db.commit()
        for kind in (EventKind.SUBMITTED, EventKind.ACCEPTED):
            await event_store.append(
                db, client_order_id="paper:mid", kind=kind, user_id=user.id
            )
        await db.commit()

        states = await reconcile.recover_order_states(db, user_id=user.id)
        assert [s.kind for s in states] == [EventKind.ACCEPTED]

        # …and the stream can then be continued from where it left off.
        assert await event_store.next_seq(db, "paper:mid") == 3
        await event_store.append(
            db, client_order_id="paper:mid", kind=EventKind.FILLED,
            user_id=user.id, payload={"filled_qty": 10},
        )
        await db.commit()
        assert await reconcile.recover_order_states(db, user_id=user.id) == []

    async def test_stop_early_leaves_a_recoverable_stream(self, db: AsyncSession) -> None:
        """An order stopped after `submitted` and never gated again is still ACTIVE, and
        recovery must surface it rather than silently dropping a possibly-live order."""
        user = await create_test_user(db)
        await db.commit()
        await event_store.append(
            db, client_order_id="paper:stopped", kind=EventKind.SUBMITTED, user_id=user.id
        )
        await db.commit()

        states = await reconcile.recover_order_states(db, user_id=user.id)
        assert len(states) == 1
        assert states[0].kind is EventKind.SUBMITTED
        assert states[0].active, "a submitted-but-undecided order still holds capital"

    async def test_multiple_orders_recover_independently(self, db: AsyncSession) -> None:
        user = await create_test_user(db)
        await db.commit()
        await event_store.append(
            db, client_order_id="paper:a", kind=EventKind.SUBMITTED, user_id=user.id
        )
        for kind in (EventKind.SUBMITTED, EventKind.DENIED):
            await event_store.append(
                db, client_order_id="paper:b", kind=kind, user_id=user.id
            )
        await db.commit()

        states = await reconcile.recover_order_states(db, user_id=user.id)
        assert [s.client_order_id for s in states] == ["paper:a"]
