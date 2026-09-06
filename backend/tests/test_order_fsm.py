"""Phase 7.3 — the order FSM, the projection, and the event bus (A32).

The assertions that carry weight:

- a **sequence gap** raises rather than projecting a state that merely looks fine;
- **fill quantities are CUMULATIVE**, so replaying a duplicated event cannot double a
  position — which matters because replay is how the projection is rebuilt on restart;
- **`CANCEL_REQUESTED → FILLED` is legal**, because a cancel losing the race to a fill is
  a routine market outcome, not corruption;
- **a stopped bus raises on publish**, because a bus that silently accepted them would be
  indistinguishable from a quiet market.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.broker import order_fsm as fsm
from app.broker.adapter import ACTIVE_KINDS, TERMINAL_KINDS, EventKind, OrderEvent
from app.broker.event_bus import (
    BusOverflowError,
    BusStoppedError,
    EventBus,
    OverflowPolicy,
)

_T0 = datetime(2026, 9, 7, 3, 30, tzinfo=UTC)


def _ev(seq: int, kind: EventKind, oid: str = "paper:o1", **payload: object) -> OrderEvent:
    return OrderEvent(
        client_order_id=oid,
        seq=seq,
        kind=kind,
        at=_T0 + timedelta(seconds=seq),
        payload=dict(payload),
    )


# ── 1. the transition table ───────────────────────────────────────────────────


class TestTransitions:
    def test_a_stream_must_open_with_submitted(self) -> None:
        """`submitted` is written BEFORE the gates run — that is what makes a decision
        impossible to lose. So nothing else may be an order's first event."""
        assert fsm.can_follow(None, EventKind.SUBMITTED)
        for kind in EventKind:
            if kind is not EventKind.SUBMITTED:
                assert not fsm.can_follow(None, kind), f"{kind} cannot open a stream"

    def test_both_refusals_follow_submitted(self) -> None:
        """⭐ DENIED (ours) and REJECTED (the broker's) are reachable from the same
        state — which is precisely why they must be distinct KINDS rather than one kind
        with a flag. The projection cannot recover the distinction afterwards."""
        assert fsm.can_follow(EventKind.SUBMITTED, EventKind.DENIED)
        assert fsm.can_follow(EventKind.SUBMITTED, EventKind.REJECTED)

    def test_cancel_can_lose_the_race_to_a_fill(self) -> None:
        """A cancel that arrives too late is Tuesday, not corruption.

        Modelling it as illegal would make the FSM raise on a routine outcome, and the
        natural 'fix' for a noisy assertion is to stop asserting at all.
        """
        assert fsm.can_follow(EventKind.CANCEL_REQUESTED, EventKind.FILLED)
        assert fsm.can_follow(EventKind.CANCEL_REQUESTED, EventKind.CANCELLED)

    def test_partial_fills_may_repeat(self) -> None:
        assert fsm.can_follow(EventKind.PARTIALLY_FILLED, EventKind.PARTIALLY_FILLED)

    @pytest.mark.parametrize("terminal", sorted(TERMINAL_KINDS, key=lambda k: k.value))
    def test_terminal_states_accept_nothing(self, terminal: EventKind) -> None:
        for kind in EventKind:
            assert not fsm.can_follow(terminal, kind), f"{terminal} → {kind} must be illegal"

    def test_every_kind_appears_in_the_table(self) -> None:
        """A kind with no row would be silently unreachable — the T7 shape again."""
        for kind in EventKind:
            assert kind in fsm._TRANSITIONS, f"{kind} has no transition row"

    def test_assert_raises_with_both_states_named(self) -> None:
        with pytest.raises(fsm.IllegalTransitionError, match="filled cannot follow denied"):
            fsm.assert_can_follow(EventKind.DENIED, EventKind.FILLED)


# ── 2. the projection ─────────────────────────────────────────────────────────


class TestProjection:
    def test_happy_path_fill(self) -> None:
        state = fsm.project(
            [
                _ev(1, EventKind.SUBMITTED),
                _ev(2, EventKind.ACCEPTED, broker_order_id="paper:b1"),
                _ev(3, EventKind.FILLED, filled_qty=100, filled_price="499.5000"),
            ]
        )
        assert state.kind is EventKind.FILLED
        assert state.terminal and not state.active
        assert state.filled_qty == 100
        assert state.avg_fill_price == Decimal("499.5000")
        assert state.broker_order_id == "paper:b1"

    def test_denial_keeps_its_reason_and_rule(self) -> None:
        """The whole point of the table: the refusal record must survive."""
        state = fsm.project(
            [
                _ev(1, EventKind.SUBMITTED),
                _ev(2, EventKind.DENIED, reason="Daily loss limit reached",
                    rule="circuit_breaker"),
            ]
        )
        assert state.kind is EventKind.DENIED
        assert state.refused and state.terminal
        assert state.reason == "Daily loss limit reached"
        assert state.rule == "circuit_breaker"

    def test_denied_and_rejected_stay_distinguishable_after_projection(self) -> None:
        denied = fsm.project([_ev(1, EventKind.SUBMITTED), _ev(2, EventKind.DENIED)])
        rejected = fsm.project([_ev(1, EventKind.SUBMITTED), _ev(2, EventKind.REJECTED)])
        assert denied.refused and rejected.refused, "both are refusals…"
        assert denied.kind is not rejected.kind, "…but WHICH must survive the fold"

    def test_partially_filled_is_still_active(self) -> None:
        """The remainder can still fill, so it still holds capital (A42)."""
        state = fsm.project(
            [
                _ev(1, EventKind.SUBMITTED),
                _ev(2, EventKind.ACCEPTED),
                _ev(3, EventKind.PARTIALLY_FILLED, filled_qty=40),
            ]
        )
        assert state.active
        assert state.filled_qty == 40

    def test_fill_quantities_are_cumulative_not_deltas(self) -> None:
        """⭐ Idempotent under replay, which is how the projection survives a restart.

        With deltas, a duplicated event would silently double the position. Here the
        second partial REPLACES the running total, so replaying it changes nothing.
        """
        events = [
            _ev(1, EventKind.SUBMITTED),
            _ev(2, EventKind.ACCEPTED),
            _ev(3, EventKind.PARTIALLY_FILLED, filled_qty=40),
            _ev(4, EventKind.FILLED, filled_qty=100),
        ]
        assert fsm.project(events).filled_qty == 100, "cumulative, not 40+100"

    def test_sequence_gap_raises(self) -> None:
        """A gap means the projection is a guess. Say so instead of guessing."""
        with pytest.raises(fsm.IllegalTransitionError, match="sequence gap"):
            fsm.project([_ev(1, EventKind.SUBMITTED), _ev(3, EventKind.FILLED)])

    def test_illegal_transition_raises(self) -> None:
        with pytest.raises(fsm.IllegalTransitionError):
            fsm.project([_ev(1, EventKind.SUBMITTED), _ev(2, EventKind.CANCELLED)])

    def test_non_strict_tolerates_a_damaged_stream(self) -> None:
        """Forensics only — never the live path."""
        state = fsm.project(
            [_ev(1, EventKind.SUBMITTED), _ev(3, EventKind.FILLED, filled_qty=5)],
            strict=False,
        )
        assert state.kind is EventKind.FILLED
        assert state.filled_qty == 5

    def test_out_of_order_input_is_sorted(self) -> None:
        state = fsm.project([_ev(2, EventKind.ACCEPTED), _ev(1, EventKind.SUBMITTED)])
        assert state.kind is EventKind.ACCEPTED
        assert state.history == (EventKind.SUBMITTED, EventKind.ACCEPTED)

    def test_mixed_streams_are_refused(self) -> None:
        with pytest.raises(ValueError, match="mixed streams"):
            fsm.project(
                [_ev(1, EventKind.SUBMITTED, oid="paper:a"),
                 _ev(2, EventKind.ACCEPTED, oid="paper:b")]
            )

    def test_empty_stream_is_refused(self) -> None:
        with pytest.raises(ValueError, match="empty event stream"):
            fsm.project([])

    def test_active_matches_the_adapter_vocabulary(self) -> None:
        """One definition of 'active', shared with `adapter.is_active`."""
        for kind in ACTIVE_KINDS:
            events = [_ev(1, EventKind.SUBMITTED)]
            if kind is not EventKind.SUBMITTED:
                events.append(_ev(2, EventKind.ACCEPTED))
                if kind not in (EventKind.ACCEPTED,):
                    events.append(_ev(3, kind))
            assert fsm.project(events).active is True


# ── 3. the event bus (A32) ────────────────────────────────────────────────────


class TestEventBus:
    def test_delivers_to_every_handler(self) -> None:
        bus = EventBus()
        seen_a: list[OrderEvent] = []
        seen_b: list[OrderEvent] = []
        bus.subscribe(seen_a.append)
        bus.subscribe(seen_b.append)

        assert bus.publish(_ev(1, EventKind.SUBMITTED)) == 2
        assert len(seen_a) == len(seen_b) == 1

    def test_one_broken_handler_does_not_stop_the_others(self) -> None:
        """⭐ A reporting bug is not a reason to fail a fill."""
        bus = EventBus()
        seen: list[OrderEvent] = []

        def _explodes(_e: OrderEvent) -> None:
            raise RuntimeError("handler is broken")

        bus.subscribe(_explodes)
        bus.subscribe(seen.append)

        delivered = bus.publish(_ev(1, EventKind.SUBMITTED))
        assert delivered == 1, "the good handler still ran"
        assert len(seen) == 1
        assert bus.stats.handler_errors == 1
        assert "RuntimeError" in (bus.stats.last_error or ""), (
            "swallowed is not the same as invisible — an alarm watches this"
        )

    def test_unsubscribe_during_dispatch_is_safe(self) -> None:
        """Snapshot iteration: mutating the handler list mid-walk must not skip or raise."""
        bus = EventBus()
        seen: list[OrderEvent] = []
        unsub_holder: list[object] = []

        def _self_removing(_e: OrderEvent) -> None:
            unsub_holder[0]()  # type: ignore[operator]

        unsub_holder.append(bus.subscribe(_self_removing))
        bus.subscribe(seen.append)

        bus.publish(_ev(1, EventKind.SUBMITTED))
        assert len(seen) == 1, "the later handler still ran"
        assert bus.handler_count == 1

    def test_unsubscribe_is_idempotent(self) -> None:
        bus = EventBus()
        unsub = bus.subscribe(lambda _e: None)
        unsub()
        unsub()  # must not raise
        assert bus.handler_count == 0

    def test_stopped_bus_raises_on_publish(self) -> None:
        """⭐ A dead bus must be LOUD.

        Ignoring publishes after stop makes shutdown tidy and makes a bus that died
        early look exactly like a market with no events.
        """
        bus = EventBus()
        bus.stop()
        assert not bus.running
        with pytest.raises(BusStoppedError, match="quiet market"):
            bus.publish(_ev(1, EventKind.SUBMITTED))

    def test_refuse_policy_raises_at_capacity(self) -> None:
        """Order events are not droppable — losing one loses a fill."""
        bus = EventBus(maxlen=2, overflow=OverflowPolicy.REFUSE)
        bus.publish(_ev(1, EventKind.SUBMITTED, oid="paper:a"))
        bus.publish(_ev(1, EventKind.SUBMITTED, oid="paper:b"))
        with pytest.raises(BusOverflowError, match="not droppable"):
            bus.publish(_ev(1, EventKind.SUBMITTED, oid="paper:c"))
        assert bus.stats.dropped == 1

    def test_drop_oldest_policy_counts_what_it_drops(self) -> None:
        """A silent drop is the failure; a counted one is a metric."""
        bus = EventBus(maxlen=2, overflow=OverflowPolicy.DROP_OLDEST)
        for i, oid in enumerate(("paper:a", "paper:b", "paper:c"), start=1):
            bus.publish(_ev(1, EventKind.SUBMITTED, oid=oid))
            assert bus.stats.published == i
        assert bus.stats.dropped == 1
        assert len(bus.recent()) == 2

    def test_recent_filters_by_order(self) -> None:
        bus = EventBus()
        bus.publish(_ev(1, EventKind.SUBMITTED, oid="paper:a"))
        bus.publish(_ev(1, EventKind.SUBMITTED, oid="paper:b"))
        assert len(bus.recent("paper:a")) == 1
        assert len(bus.recent()) == 2

    def test_bus_and_projection_compose(self) -> None:
        """The seam: what the bus carried must fold into the state the FSM reports."""
        bus = EventBus()
        captured: list[OrderEvent] = []
        bus.subscribe(captured.append)

        for ev in (
            _ev(1, EventKind.SUBMITTED),
            _ev(2, EventKind.ACCEPTED, broker_order_id="paper:b9"),
            _ev(3, EventKind.FILLED, filled_qty=25, filled_price="101.2500"),
        ):
            bus.publish(ev)

        state = fsm.project(captured)
        assert state.kind is EventKind.FILLED
        assert state.filled_qty == 25
        assert state.broker_order_id == "paper:b9"
        assert bus.stats.published == 3
