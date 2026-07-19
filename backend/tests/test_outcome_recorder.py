"""Signal-outcome tick evaluation (Phase 3, slice 3.6).

Covers the whole outcome path on real seams (real Postgres, real Redis):
  - direction-aware SL/TP touch levels (SELL mirror; BUY is pinned in
    test_live_levels.py);
  - idempotent first-touch writes + the monotonic status ladder
    (open → entry_touched → tp_first/sl_first; validity-guarded);
  - SL/TP touches WITHOUT a prior entry touch stamp but never resolve;
  - the recorder's consumer-group drain: ack-after-commit, at-least-once
    redelivery harmless, non-touch alerts acked and skipped;
  - expiry finalization: expired_untouched / expired_open, terminal rows
    never reopened, alert-less expired signals still get rows;
  - REST GET /signals/{id}/outcome.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import redis as redis_sync
from app.broker.live_levels import _signal_levels, signal_level_ids
from app.broker.outcome_recorder import GROUP, drain_once, ensure_group
from app.core.config import settings
from app.models.signal import Signal, SignalOutcome
from app.services.signal_outcomes import (
    apply_touch,
    ensure_outcome_row,
    finalize_expired_outcomes,
)
from sqlalchemy import text

from tests.helpers import create_test_user, get_auth_headers, make_stock

# Post-OUTCOME_EPOCH clock (the epoch floors finalizer seeding — signals
# that lapsed before the recorder existed must never get fabricated rows).
NOW = datetime(2026, 7, 20, 6, 3, tzinfo=UTC)
VALID_UNTIL = datetime(2026, 7, 27, 10, 0, tzinfo=UTC)


async def _seed_signal(db, sid: int, direction: str = "BUY",
                       validity_until: datetime = VALID_UNTIL) -> Signal:
    signal = Signal(
        stock_id=sid,
        direction=direction,
        classification="swing",
        timeframe="1h",
        entry_price=Decimal("100"),
        stop_loss=Decimal("98"),
        take_profit=Decimal("104"),
        suggested_qty=10,
        confidence_pct=75,
        factor_scores={},
        headline="outcome test signal",
        status="active",
        validity_until=validity_until,
    )
    db.add(signal)
    await db.commit()
    return signal


@pytest.fixture
def sync_redis():
    r = redis_sync.from_url(settings.redis_url, decode_responses=True)
    yield r
    r.close()


@pytest.fixture
def alert_stream(monkeypatch, sync_redis) -> str:
    stream = f"alerts:test:{uuid.uuid4().hex}"
    monkeypatch.setattr(settings, "live_alert_stream", stream)
    yield stream
    sync_redis.delete(stream)


# ── Direction-aware touch levels ──────────────────────────────────────────────


class TestTouchLevels:
    def test_sell_signal_mirrors_cross_kinds(self) -> None:
        """A SELL's TP is hit crossing DOWN and its SL crossing UP."""
        sig = {"id": "aaaaaaaa-0000-0000-0000-000000000000", "stock_id": 1,
               "entry": Decimal("100"), "sl": Decimal("102"),
               "tp": Decimal("96"), "classification": "intraday",
               "timeframe": "5m", "direction": "SELL"}
        levels, meta = _signal_levels(sig)
        _zone, _sl_near, _tp_near, sl_touch_id, tp_touch_id = signal_level_ids(sig["id"])
        by_id = {lv["id"]: lv for lv in levels}
        assert by_id[sl_touch_id]["kind"] == "cross_up"
        assert by_id[sl_touch_id]["price"] == "102.0000"
        assert by_id[tp_touch_id]["kind"] == "cross_down"
        assert by_id[tp_touch_id]["price"] == "96.0000"
        assert meta[sl_touch_id]["source"] == "sl_touch"
        assert meta[tp_touch_id]["source"] == "tp_touch"


# ── Status ladder ─────────────────────────────────────────────────────────────


class TestStatusLadder:
    async def _outcome(self, db, signal_id: str) -> SignalOutcome:
        db.expire_all()
        return await db.get(SignalOutcome, signal_id)

    @pytest.mark.asyncio
    async def test_entry_then_tp_resolves_tp_first(self, db) -> None:
        stock = await make_stock(db, symbol="OUTTPF")
        sig_id = (await _seed_signal(db, stock.id)).id
        assert await ensure_outcome_row(db, sig_id) is True

        await apply_touch(db, signal_id=sig_id, source="entry_zone",
                          ts=NOW, price="100.10")
        await db.commit()
        row = await self._outcome(db, sig_id)
        assert row.status == "entry_touched"
        assert row.entry_touch_price == Decimal("100.1000")

        await apply_touch(db, signal_id=sig_id, source="tp_touch",
                          ts=NOW + timedelta(minutes=30), price="104.05")
        await db.commit()
        row = await self._outcome(db, sig_id)
        assert row.status == "tp_first"
        assert row.tp_touched_at == NOW + timedelta(minutes=30)
        assert row.resolved_at == NOW + timedelta(minutes=30)

        # SL after resolution: stamps, never reopens the ladder
        await apply_touch(db, signal_id=sig_id, source="sl_touch",
                          ts=NOW + timedelta(hours=1), price="97.90")
        await db.commit()
        row = await self._outcome(db, sig_id)
        assert row.status == "tp_first"
        assert row.sl_touched_at is not None

    @pytest.mark.asyncio
    async def test_sl_or_tp_without_entry_never_resolves(self, db) -> None:
        """A TP cross on a never-entered setup is a missed trade, not a
        win — the stamp records, the status stays open."""
        stock = await make_stock(db, symbol="OUTMISS")
        sig_id = (await _seed_signal(db, stock.id)).id
        await ensure_outcome_row(db, sig_id)

        await apply_touch(db, signal_id=sig_id, source="tp_touch",
                          ts=NOW, price="104.10")
        await db.commit()
        row = await self._outcome(db, sig_id)
        assert row.status == "open"
        assert row.tp_touched_at == NOW
        assert row.resolved_at is None

    @pytest.mark.asyncio
    async def test_first_touch_wins_and_late_touches_dont_transition(self, db) -> None:
        stock = await make_stock(db, symbol="OUTIDEM")
        sig_id = (await _seed_signal(db, stock.id)).id
        await ensure_outcome_row(db, sig_id)

        await apply_touch(db, signal_id=sig_id, source="entry_zone",
                          ts=NOW, price="100.10")
        # redelivered / repeated entry alert with a different price
        await apply_touch(db, signal_id=sig_id, source="entry_zone",
                          ts=NOW + timedelta(minutes=5), price="99.90")
        await db.commit()
        row = await self._outcome(db, sig_id)
        assert row.entry_touched_at == NOW  # first touch wins
        assert row.entry_touch_price == Decimal("100.1000")

        # a touch AFTER validity stamps nothing new and never transitions
        late = VALID_UNTIL + timedelta(minutes=1)
        await apply_touch(db, signal_id=sig_id, source="tp_touch",
                          ts=late, price="104.20")
        await db.commit()
        row = await self._outcome(db, sig_id)
        assert row.tp_touched_at == late  # stamped (Phase-6 honesty)
        assert row.status == "entry_touched"  # but NOT tp_first

    @pytest.mark.asyncio
    async def test_redelivered_pre_entry_touch_never_resolves(self, db) -> None:
        """quant-verifier HIGH (2026-07-19): PEL reorder — tp_touch@T1
        lands before entry@T2, batch crashes post-commit pre-ack, and the
        redelivered tp_touch@T1 replays AFTER the entry is stamped. A TP
        you couldn't have taken must never become a recorded win."""
        stock = await make_stock(db, symbol="OUTREORD")
        sig_id = (await _seed_signal(db, stock.id)).id
        await ensure_outcome_row(db, sig_id)

        # original order: tp@T1 (pre-entry: stamps only), entry@T2
        await apply_touch(db, signal_id=sig_id, source="tp_touch",
                          ts=NOW, price="104.10")
        await apply_touch(db, signal_id=sig_id, source="entry_zone",
                          ts=NOW + timedelta(minutes=5), price="100.10")
        await db.commit()
        # PEL redelivery of the SAME pre-entry tp_touch@T1
        await apply_touch(db, signal_id=sig_id, source="tp_touch",
                          ts=NOW, price="104.10")
        await db.commit()

        row = await self._outcome(db, sig_id)
        assert row.status == "entry_touched"  # NOT tp_first
        assert row.resolved_at is None
        # a genuine POST-entry touch still resolves
        await apply_touch(db, signal_id=sig_id, source="tp_touch",
                          ts=NOW + timedelta(minutes=20), price="104.30")
        await db.commit()
        row = await self._outcome(db, sig_id)
        assert row.status == "tp_first"
        assert row.tp_touched_at == NOW  # first-touch stamp untouched

    @pytest.mark.asyncio
    async def test_ensure_row_unknown_signal_false(self, db) -> None:
        assert await ensure_outcome_row(db, str(uuid.uuid4())) is False


# ── Expiry finalization ───────────────────────────────────────────────────────


class TestExpiryFinalization:
    @pytest.mark.asyncio
    async def test_finalizes_untouched_touched_and_leaves_terminal(self, db) -> None:
        stock = await make_stock(db, symbol="OUTEXP")
        past = NOW - timedelta(minutes=1)
        untouched_id = (await _seed_signal(db, stock.id, validity_until=past)).id
        touched_id = (await _seed_signal(db, stock.id, validity_until=past)).id
        resolved_id = (await _seed_signal(db, stock.id, validity_until=past)).id
        alive_id = (await _seed_signal(db, stock.id, validity_until=VALID_UNTIL)).id

        # `touched`: entry inside validity; `resolved`: full tp_first path
        for sig_id in (touched_id, resolved_id):
            await ensure_outcome_row(db, sig_id)
            await apply_touch(db, signal_id=sig_id, source="entry_zone",
                              ts=past - timedelta(hours=1), price="100.00")
        await apply_touch(db, signal_id=resolved_id, source="tp_touch",
                          ts=past - timedelta(minutes=30), price="104.00")
        await db.commit()

        n = await finalize_expired_outcomes(db, NOW)
        await db.commit()

        assert n == 2  # untouched (seeded here) + touched; resolved terminal
        db.expire_all()
        assert (await db.get(SignalOutcome, untouched_id)).status == "expired_untouched"
        assert (await db.get(SignalOutcome, touched_id)).status == "expired_open"
        assert (await db.get(SignalOutcome, resolved_id)).status == "tp_first"
        assert await db.get(SignalOutcome, alive_id) is None  # not lapsed

        # idempotent: a second sweep moves nothing
        assert await finalize_expired_outcomes(db, NOW) == 0

    @pytest.mark.asyncio
    async def test_late_touch_still_finalizes_untouched(self, db) -> None:
        """bug-hunter MEDIUM (2026-07-19, executed repro): a touch stamped
        AFTER validity (armed-level lag) must not flip the terminal verdict
        — classification follows the LADDER, not the raw stamp."""
        stock = await make_stock(db, symbol="OUTLATE")
        past = NOW - timedelta(minutes=10)
        sig_id = (await _seed_signal(db, stock.id, validity_until=past)).id
        await ensure_outcome_row(db, sig_id)
        # entry touch 30s AFTER expiry: stamp recorded, status stays open
        await apply_touch(db, signal_id=sig_id, source="entry_zone",
                          ts=past + timedelta(seconds=30), price="100.10")
        await db.commit()

        await finalize_expired_outcomes(db, NOW)
        await db.commit()

        db.expire_all()
        row = await db.get(SignalOutcome, sig_id)
        assert row.status == "expired_untouched"  # NOT expired_open
        assert row.entry_touched_at is not None  # the stamp still records

    @pytest.mark.asyncio
    async def test_pre_epoch_lapsed_signals_never_seeded(self, db) -> None:
        """Signals that lapsed before the recorder existed were never
        observed — seeding them expired_untouched would fabricate data."""
        stock = await make_stock(db, symbol="OUTPREEP")
        ancient = datetime(2026, 7, 10, 10, 0, tzinfo=UTC)  # < OUTCOME_EPOCH
        sig_id = (await _seed_signal(db, stock.id, validity_until=ancient)).id

        assert await finalize_expired_outcomes(db, NOW) == 0
        await db.commit()
        assert await db.get(SignalOutcome, sig_id) is None

    @pytest.mark.asyncio
    async def test_crash_window_upgrades_toward_truth(self, db) -> None:
        """A recorder outage overlapping the expiry sweep: PEL-recovered
        IN-VALIDITY touches upgrade the finalized verdict (monotonic
        toward truth — never back to a live state)."""
        stock = await make_stock(db, symbol="OUTCRASH")
        past = NOW - timedelta(minutes=10)
        sig_id = (await _seed_signal(db, stock.id, validity_until=past)).id
        await ensure_outcome_row(db, sig_id)
        n = await finalize_expired_outcomes(db, NOW)
        await db.commit()
        assert n == 1  # sweeper got there first: expired_untouched

        # recovered entry touch from INSIDE validity → expired_open
        await apply_touch(db, signal_id=sig_id, source="entry_zone",
                          ts=past - timedelta(hours=1), price="100.10")
        await db.commit()
        db.expire_all()
        assert (await db.get(SignalOutcome, sig_id)).status == "expired_open"

        # recovered in-validity SL touch (entry proven) → sl_first
        await apply_touch(db, signal_id=sig_id, source="sl_touch",
                          ts=past - timedelta(minutes=30), price="97.95")
        await db.commit()
        db.expire_all()
        assert (await db.get(SignalOutcome, sig_id)).status == "sl_first"


# ── Recorder drain (consumer group, both sides of the stream seam) ───────────


def _alert_fields(signal: Signal, source: str, price: str,
                  ts: datetime = NOW) -> dict:
    zone_id, sl_id, tp_id, sl_touch_id, tp_touch_id = signal_level_ids(signal.id)
    level_id = {"entry_zone": zone_id, "sl_near": sl_id, "tp_near": tp_id,
                "sl_touch": sl_touch_id, "tp_touch": tp_touch_id}[source]
    return {"sid": signal.stock_id, "level_id": level_id,
            "tag": "zone_enter" if source == "entry_zone" else "cross_up",
            "price": price, "ts": int(ts.timestamp()), "day": "2026-07-16",
            "source": source, "style": "swing", "signal_id": signal.id}


class TestRecorderDrain:
    @pytest.mark.asyncio
    async def test_drain_applies_touches_and_acks_after_commit(
        self, db, sync_redis, alert_stream
    ) -> None:
        stock = await make_stock(db, symbol="OUTDRAIN")
        signal = await _seed_signal(db, stock.id)
        sig_id = signal.id
        ensure_group(sync_redis)  # group at "$" BEFORE entries land

        sync_redis.xadd(alert_stream, _alert_fields(signal, "entry_zone", "100.10"))
        sync_redis.xadd(alert_stream, _alert_fields(
            signal, "tp_touch", "104.05", ts=NOW + timedelta(minutes=10)))
        sync_redis.xadd(alert_stream, _alert_fields(signal, "sl_near", "98.20"))
        sync_redis.xadd(alert_stream, {"sid": stock.id, "level_id": 1,
                                       "tag": "cross_up", "price": "150.00",
                                       "ts": int(NOW.timestamp()),
                                       "day": "2026-07-16", "source": "pdh",
                                       "style": "market"})

        n = await drain_once(db, sync_redis)
        assert n == 4

        db.expire_all()
        row = await db.get(SignalOutcome, sig_id)
        assert row.status == "tp_first"
        assert row.entry_touch_price == Decimal("100.1000")
        assert row.tp_touch_price == Decimal("104.0500")
        assert row.sl_touched_at is None  # proximity is NOT a touch

        pending = sync_redis.xpending(alert_stream, GROUP)
        assert pending["pending"] == 0  # everything acked, incl. skips

    @pytest.mark.asyncio
    async def test_redelivery_is_harmless_and_unknown_signals_skipped(
        self, db, sync_redis, alert_stream
    ) -> None:
        stock = await make_stock(db, symbol="OUTREDLV")
        signal = await _seed_signal(db, stock.id)
        sig_id = signal.id
        ensure_group(sync_redis)

        fields = _alert_fields(signal, "entry_zone", "100.10")
        sync_redis.xadd(alert_stream, fields)
        sync_redis.xadd(alert_stream, fields)  # duplicate delivery
        ghost = dict(fields, signal_id=str(uuid.uuid4()))
        sync_redis.xadd(alert_stream, ghost)  # unknown signal

        n = await drain_once(db, sync_redis)
        assert n == 3
        db.expire_all()
        row = await db.get(SignalOutcome, sig_id)
        assert row.status == "entry_touched"
        assert row.entry_touched_at == NOW
        assert sync_redis.xpending(alert_stream, GROUP)["pending"] == 0
        # the ghost signal never minted a row
        count = (await db.execute(text("SELECT count(*) FROM signal_outcomes"))).scalar()
        assert count == 1

    @pytest.mark.asyncio
    async def test_empty_stream_returns_zero(self, db, sync_redis, alert_stream,
                                             monkeypatch) -> None:
        import app.broker.outcome_recorder as rec

        monkeypatch.setattr(rec, "_BLOCK_MS", 10)  # don't block the suite
        ensure_group(sync_redis)
        assert await drain_once(db, sync_redis) == 0

    @pytest.mark.asyncio
    async def test_poison_entry_rolls_back_only_itself(
        self, db, sync_redis, alert_stream
    ) -> None:
        """bug-hunter MEDIUM (2026-07-19, executed repro): a driver-level
        poison entry (unbindable price) must not abort its batch-mates,
        must be ACKed as a documented drop (never pinning the PEL), and
        the batch's good writes must commit."""
        stock = await make_stock(db, symbol="OUTPOIS")
        signal = await _seed_signal(db, stock.id)
        sig_id = signal.id
        ensure_group(sync_redis)

        # poison FIRST so a naive shared transaction would poison the good
        # entry behind it (the InFailedSQLTransaction failure mode)
        poison = _alert_fields(signal, "entry_zone", "100.10")
        poison["price"] = "not-a-price"
        sync_redis.xadd(alert_stream, poison)
        sync_redis.xadd(alert_stream, _alert_fields(signal, "entry_zone", "100.10"))

        n = await drain_once(db, sync_redis)
        assert n == 2

        db.expire_all()
        row = await db.get(SignalOutcome, sig_id)
        assert row is not None and row.status == "entry_touched"
        assert row.entry_touch_price == Decimal("100.1000")
        # both entries acked — the poison never pins the PEL
        assert sync_redis.xpending(alert_stream, GROUP)["pending"] == 0


# ── REST ──────────────────────────────────────────────────────────────────────


class TestOutcomeRest:
    @pytest.mark.asyncio
    async def test_get_outcome_roundtrip_and_404(self, db, client) -> None:
        await create_test_user(db, email="outcome-rest@test.com")
        headers = await get_auth_headers(client, email="outcome-rest@test.com")
        stock = await make_stock(db, symbol="OUTREST")
        sig_id = (await _seed_signal(db, stock.id)).id

        resp = await client.get(f"/api/v1/signals/{sig_id}/outcome",
                                headers=headers)
        assert resp.status_code == 404  # lazily written — nothing yet

        await ensure_outcome_row(db, sig_id)
        await apply_touch(db, signal_id=sig_id, source="entry_zone",
                          ts=NOW, price="100.10")
        await db.commit()

        resp = await client.get(f"/api/v1/signals/{sig_id}/outcome",
                                headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "entry_touched"
        assert body["entry_touch_price"] == "100.1000"
        assert body["sl_touched_at"] is None
