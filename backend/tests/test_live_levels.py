"""Trigger-level construction (Phase 3 slice 3.5) against the real DB.

Pins the host side of the trigger layer: PDH/PDL come from the PREVIOUS
session's 1d candle only, volume baselines from completed 5m candles,
signal levels carry stable UUID-hashed ids, and every constructed payload
is accepted verbatim by the real tradecore FFI (the two sides can't
drift silently).
"""

from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
import tradecore
from app.broker.live_levels import (
    PDH_ID,
    PDL_ID,
    VBURST_ID,
    LevelDirectory,
    build_directory,
    load_static_levels,
    signal_level_ids,
)
from app.broker.live_worker import TF_MINUTES, session_bounds_ist
from app.models.signal import Signal
from sqlalchemy import text

from tests.helpers import make_stock

IST = ZoneInfo("Asia/Kolkata")
TODAY = datetime(2026, 7, 9, 12, 0, tzinfo=IST)


async def _seed_1d(db, sid: int, day_offset: int, high: str, low: str) -> None:
    ts = datetime.combine(
        (TODAY - timedelta(days=day_offset)).date(), time(0), tzinfo=IST
    ).astimezone(UTC)
    await db.execute(
        text(
            "INSERT INTO ohlcv_1d (time, stock_id, open, high, low, close,"
            " volume, is_complete) VALUES (:t, :sid, :l, :h, :l, :h, 1000, true)"
        ),
        {"t": ts, "sid": sid, "h": Decimal(high), "l": Decimal(low)},
    )


async def _seed_5m(db, sid: int, minutes_ago: int, volume: int) -> None:
    await db.execute(
        text(
            "INSERT INTO ohlcv_5m (time, stock_id, open, high, low, close,"
            " volume, is_complete) VALUES (:t, :sid, 1, 1, 1, 1, :v, true)"
        ),
        {"t": TODAY - timedelta(minutes=minutes_ago), "sid": sid, "v": volume},
    )


async def _seed_signal(db, sid: int, status: str = "active") -> Signal:
    signal = Signal(
        stock_id=sid,
        direction="BUY",
        classification="swing",
        timeframe="1h",
        entry_price=Decimal("100"),
        stop_loss=Decimal("98"),
        take_profit=Decimal("104"),
        suggested_qty=10,
        confidence_pct=75,
        factor_scores={},
        headline="test signal",
        status=status,
        validity_until=datetime(2030, 1, 1, tzinfo=UTC),
    )
    db.add(signal)
    await db.commit()
    return signal


class TestStaticLevels:
    @pytest.mark.asyncio
    async def test_pdh_pdl_from_previous_session_only(self, db) -> None:
        stock = await make_stock(db, symbol="PDHTEST")
        await _seed_1d(db, stock.id, 1, "150.50", "140.25")  # yesterday
        await _seed_1d(db, stock.id, 0, "999.00", "1.00")  # TODAY — excluded
        await db.commit()

        levels, meta = await load_static_levels(db, TODAY, [stock.id])
        pdh = next(lv for lv in levels[stock.id] if lv["id"] == PDH_ID)
        pdl = next(lv for lv in levels[stock.id] if lv["id"] == PDL_ID)
        assert pdh == {
            "id": PDH_ID, "kind": "cross_up", "price": "150.5000", "rearm_bp": 10,
        }
        assert pdl == {
            "id": PDL_ID, "kind": "cross_down", "price": "140.2500", "rearm_bp": 10,
        }
        assert meta[stock.id][PDH_ID] == {"source": "pdh", "style": "market"}

    @pytest.mark.asyncio
    async def test_vburst_baseline_is_completed_5m_average(self, db) -> None:
        stock = await make_stock(db, symbol="VBTEST")
        await _seed_5m(db, stock.id, 60, 100)
        await _seed_5m(db, stock.id, 120, 200)
        await db.commit()

        levels, meta = await load_static_levels(db, TODAY, [stock.id])
        vb = next(lv for lv in levels[stock.id] if lv["id"] == VBURST_ID)
        assert vb == {
            "id": VBURST_ID,
            "kind": "vburst",
            "tf_minutes": 5,
            "baseline": 150,  # avg(100, 200)
            "mult_bp": 30_000,  # settings default 3.0×
        }
        assert meta[stock.id][VBURST_ID]["source"] == "vburst"


class TestLevelDirectory:
    @pytest.mark.asyncio
    async def test_signal_levels_merge_with_statics_and_ids_are_stable(self, db) -> None:
        stock = await make_stock(db, symbol="SIGTEST")
        await _seed_1d(db, stock.id, 1, "150.00", "140.00")
        signal = await _seed_signal(db, stock.id)
        await db.commit()

        directory = await build_directory(db, TODAY, [stock.id])
        changed = await directory.refresh(db)
        by_sid = {sid: (levels, meta) for sid, levels, meta in changed}
        levels, meta = by_sid[stock.id]

        zone_id, sl_id, tp_id, sl_touch_id, tp_touch_id = signal_level_ids(signal.id)
        by_id = {lv["id"]: lv for lv in levels}
        assert by_id[zone_id] == {
            "id": zone_id, "kind": "zone", "low": "99.5000", "high": "100.5000",
        }
        assert by_id[sl_id] == {
            "id": sl_id, "kind": "near", "price": "98.0000", "within_bp": 25,
        }
        assert by_id[tp_id] == {
            "id": tp_id, "kind": "near", "price": "104.0000", "within_bp": 25,
        }
        # 3.6 touch levels: BUY → SL hit crossing DOWN, TP hit crossing UP
        assert by_id[sl_touch_id] == {
            "id": sl_touch_id, "kind": "cross_down", "price": "98.0000",
            "rearm_bp": 10,
        }
        assert by_id[tp_touch_id] == {
            "id": tp_touch_id, "kind": "cross_up", "price": "104.0000",
            "rearm_bp": 10,
        }
        assert meta[sl_touch_id]["source"] == "sl_touch"
        assert meta[tp_touch_id]["source"] == "tp_touch"
        assert PDH_ID in by_id and PDL_ID in by_id  # statics preserved
        assert meta[zone_id] == {
            "source": "entry_zone", "style": "swing", "signal_id": signal.id,
        }
        # ids are a pure function of the signal uuid — stable across calls
        assert signal_level_ids(signal.id) == (
            zone_id, sl_id, tp_id, sl_touch_id, tp_touch_id,
        )

    @pytest.mark.asyncio
    async def test_refresh_reports_only_changes_and_expiry_falls_back(self, db) -> None:
        stock = await make_stock(db, symbol="EXPTEST")
        await _seed_1d(db, stock.id, 1, "150.00", "140.00")
        signal = await _seed_signal(db, stock.id)
        await db.commit()

        directory = await build_directory(db, TODAY, [stock.id])
        for sid, levels, _meta in await directory.refresh(db):
            directory.mark_sent(sid, levels)
        assert await directory.refresh(db) == []  # steady state: no churn

        await db.execute(
            text("UPDATE signals SET status = 'expired' WHERE id = :id"),
            {"id": signal.id},
        )
        await db.commit()
        changed = await directory.refresh(db)
        assert len(changed) == 1
        sid, levels, _meta = changed[0]
        assert sid == stock.id
        # fallback to statics only — no zone/near levels left
        assert sorted(lv["id"] for lv in levels) == [PDH_ID, PDL_ID]

    @pytest.mark.asyncio
    async def test_constructed_payloads_pass_the_real_ffi(self, db) -> None:
        """The canary that keeps host construction and engine validation
        from drifting apart: every payload refresh() emits must be
        accepted verbatim by tradecore.set_levels."""
        stock = await make_stock(db, symbol="FFITEST")
        await _seed_1d(db, stock.id, 1, "150.00", "140.00")
        await _seed_5m(db, stock.id, 60, 500)
        await _seed_signal(db, stock.id)
        await db.commit()

        directory = await build_directory(db, TODAY, [stock.id])
        open_ts, close_ts = session_bounds_ist(TODAY.date())
        book = tradecore.LiveBook(open_ts, close_ts, TF_MINUTES)
        for sid, levels, _meta in await directory.refresh(db):
            book.set_levels(sid, levels)  # must not raise

    @pytest.mark.asyncio
    async def test_two_signals_one_stock_pass_the_real_ffi(self, db) -> None:
        """Regression (quant-verifier HIGH + bug-hunter HIGH, 2026-07-10,
        both with executed repros): rank-indexed S/R ids duplicated when a
        stock carried two active signals, and the engine's all-or-nothing
        validation killed the stock's ENTIRE alert layer for the session.
        S/R must compute once per (stock, timeframe) with identity-derived
        ids — the merged payload must pass the real FFI."""
        stock = await make_stock(db, symbol="TWOSIG")
        await _seed_1d(db, stock.id, 1, "150.00", "140.00")
        # 25 hourly candles with a double-top at 110 (indices 6 and 16,
        # strict local maxima over the detector's ±3 window) → at least
        # one resistance zone; flat lows cluster into a support zone.
        for i in range(25):
            high = "110" if i in (6, 16) else "100"
            await db.execute(
                text(
                    "INSERT INTO ohlcv_1h (time, stock_id, open, high, low,"
                    " close, volume, is_complete)"
                    " VALUES (:t, :sid, 95, :h, 90, 95, 1000, true)"
                ),
                {
                    "t": TODAY - timedelta(hours=30 - i),
                    "sid": stock.id,
                    "h": Decimal(high),
                },
            )
        sig_a = await _seed_signal(db, stock.id)
        sig_b = await _seed_signal(db, stock.id)
        await db.commit()

        directory = await build_directory(db, TODAY, [stock.id])
        changed = await directory.refresh(db)
        (sid, levels, meta) = next(c for c in changed if c[0] == stock.id)

        ids = [lv["id"] for lv in levels]
        assert len(ids) == len(set(ids)), f"duplicate level ids: {ids}"
        # both signals' zones AND at least one S/R level made it in
        assert signal_level_ids(sig_a.id)[0] in ids
        assert signal_level_ids(sig_b.id)[0] in ids
        sr_sources = [
            m["source"]
            for m in meta.values()
            if str(m.get("source", "")).startswith("sr_")
        ]
        assert sr_sources, "expected S/R zones from the seeded double-top"
        # the engine must accept the merged payload verbatim
        open_ts, close_ts = session_bounds_ist(TODAY.date())
        book = tradecore.LiveBook(open_ts, close_ts, TF_MINUTES)
        book.set_levels(sid, levels)  # must not raise
        # identity-derived ids are stable across recomputes
        changed2 = await directory.refresh(db)
        (_, levels2, _) = next(c for c in changed2 if c[0] == stock.id)
        assert [lv["id"] for lv in levels2] == ids

    @pytest.mark.asyncio
    async def test_unacked_levels_resend_until_consumer_ack(self, db) -> None:
        """Regression (bug-hunter MEDIUM CONFIRMED, 2026-07-10): an
        evicted or engine-rejected levels item used to be marked sent by
        the PRODUCER and never retried. The ack now fires only from the
        consumer after engine accept — anything unacked re-sends."""
        import queue as queue_mod

        from app.broker.live_worker import WorkerState

        directory = LevelDirectory(
            static_levels={
                7: [{"id": 1, "kind": "cross_up", "price": "100.00", "rearm_bp": 10}],
                # low > high: host-corrupt payload the engine must refuse
                8: [{"id": 1, "kind": "zone", "low": "101.00", "high": "100.00"}],
            },
        )
        changed = await directory.refresh(db)
        assert {c[0] for c in changed} == {7, 8}

        open_ts, close_ts = session_bounds_ist(TODAY.date())
        state = WorkerState(
            book=tradecore.LiveBook(open_ts, close_ts, TF_MINUTES),
            token_map={},
            redis=None,
            writer_q=queue_mod.Queue(),
            on_levels_applied=directory.mark_sent,
        )
        state.process_item(("levels", changed, None))
        assert state.stats["levels"] == 1  # only stock 7 applied

        # stock 7 is acked and quiet; stock 8 re-sends every cycle (loud)
        changed2 = await directory.refresh(db)
        assert [c[0] for c in changed2] == [8]

    @pytest.mark.asyncio
    async def test_empty_levels_clear_and_stop_reporting(self, db) -> None:
        directory = LevelDirectory()
        directory.last_sent = {99: [{"id": 1, "kind": "cross_up"}]}
        changed = await directory.refresh(db)
        assert changed == [(99, [], {})]
        directory.mark_sent(99, [])
        assert await directory.refresh(db) == []
