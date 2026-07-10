"""Tick-trigger layer seams (Phase 3 slice 3.5).

Three seams, matching the 3.3/3.4 test discipline:
  - the tradecore.set_levels FFI contract (fail-loud validation, trigger
    event dict shape, armed-state preservation across refreshes);
  - replay of recordings carrying "lv" lines (trigger events reproduce
    deterministically; recordings WITHOUT them are byte-identical to
    pre-3.5 — the golden-compat guarantee);
  - the worker alert seam (lv recording order, XADD field contract,
    meta enrichment, one-bad-stock isolation).
"""

import json
import queue
from datetime import date
from typing import Any

import pytest
import tradecore
from app.broker.live_worker import TF_MINUTES, WorkerState, session_bounds_ist
from app.broker.replay import ReplayError, load_recording, replay_file

DAY = date(2026, 7, 9)
OPEN_TS, CLOSE_TS = session_bounds_ist(DAY)
TOKEN_MAP = {777: 42}

ZONE = {"id": 1001, "kind": "zone", "low": "101.00", "high": "102.00"}
PDH = {"id": 1, "kind": "cross_up", "price": "150.00", "rearm_bp": 10}


def _book() -> Any:
    book = tradecore.LiveBook(OPEN_TS, CLOSE_TS, TF_MINUTES)
    book.ensure_instruments([42])
    return book


class TestSetLevelsFfi:
    def test_zone_touch_emits_trigger_event_after_candles(self) -> None:
        book = _book()
        book.set_levels(42, [ZONE])
        events = book.on_ticks([(42, OPEN_TS + 5, "101.55", None, 10)])
        # 4 forming candles (one per tf) then the trigger, in order
        assert [e["kind"] for e in events] == ["forming"] * 4 + ["trigger"]
        trig = events[-1]
        assert trig == {
            "stock_id": 42,
            "kind": "trigger",
            "id": 1001,
            "tag": "zone_enter",
            "price": 1015500,  # raw i64·1e-4, same canon as candles
            "ts": OPEN_TS + 5,
        }

    def test_validation_fails_loud(self) -> None:
        book = _book()
        with pytest.raises(ValueError, match="unknown kind"):
            book.set_levels(42, [{"id": 1, "kind": "sideways", "price": "1"}])
        with pytest.raises(ValueError, match="missing"):
            book.set_levels(42, [{"id": 1, "kind": "zone", "low": "1.00"}])
        with pytest.raises(ValueError, match="bad money"):
            book.set_levels(
                42, [{"id": 1, "kind": "near", "price": "abc", "within_bp": 10}]
            )
        with pytest.raises(ValueError, match="duplicate"):
            book.set_levels(42, [ZONE, ZONE])
        with pytest.raises(ValueError, match="not in book timeframes"):
            book.set_levels(
                42,
                [{"id": 1, "kind": "vburst", "tf_minutes": 7, "baseline": 1, "mult_bp": 1}],
            )
        # all-or-nothing: the failing batch left no working levels behind
        events = book.on_ticks([(42, OPEN_TS + 5, "101.55", None, 10)])
        assert all(e["kind"] != "trigger" for e in events)

    def test_refresh_with_same_levels_preserves_armed_state(self) -> None:
        book = _book()
        book.set_levels(42, [ZONE])
        events = book.on_ticks([(42, OPEN_TS + 5, "101.55", None, 10)])
        assert events[-1]["kind"] == "trigger"
        # periodic host refresh with the SAME level list...
        book.set_levels(42, [ZONE])
        # ...must not re-fire while price sits inside the zone
        events = book.on_ticks([(42, OPEN_TS + 65, "101.60", None, 10)])
        assert all(e["kind"] != "trigger" for e in events)


class TestReplayWithLevels:
    def _write(self, path: Any, lines: list[dict[str, Any]]) -> str:
        path.write_text(
            "\n".join(json.dumps(line, separators=(",", ":")) for line in lines) + "\n",
            encoding="utf-8",
        )
        return str(path)

    def _lines(self, with_levels: bool) -> list[dict[str, Any]]:
        header = {
            "k": "h",
            "day": DAY.isoformat(),
            "open": OPEN_TS,
            "close": CLOSE_TS,
            "tfs": TF_MINUTES,
            "min_tick_ts": 0,
        }
        lv = [{"k": "lv", "sid": 42, "levels": [ZONE, PDH]}] if with_levels else []
        return [
            header,
            *lv,
            {"k": "t", "sid": 42, "ts": OPEN_TS + 5, "p": "101.55", "dv": None, "q": 10},
            {"k": "t", "sid": 42, "ts": OPEN_TS + 70, "p": "149.00", "dv": None, "q": 5},
            {"k": "t", "sid": 42, "ts": OPEN_TS + 80, "p": "150.10", "dv": None, "q": 5},
            {"k": "p", "ts": OPEN_TS + 120},
        ]

    def test_lv_lines_reproduce_trigger_events_deterministically(self, tmp_path) -> None:
        rec = self._write(tmp_path / "rec.jsonl", self._lines(with_levels=True))
        events, digest = replay_file(rec)
        trigs = [e for e in events if e["kind"] == "trigger"]
        assert [(t["id"], t["tag"]) for t in trigs] == [
            (1001, "zone_enter"),  # first tick lands inside the zone
            (1, "cross_up"),  # 149 → 150.10 crosses the PDH level
        ]
        assert all(t["day"] == DAY.isoformat() for t in trigs)
        events2, digest2 = replay_file(rec)
        assert (events, digest) == (events2, digest2)

    def test_recording_without_lv_replays_exactly_as_pre_35(self, tmp_path) -> None:
        with_lv = self._write(tmp_path / "a.jsonl", self._lines(with_levels=True))
        without = self._write(tmp_path / "b.jsonl", self._lines(with_levels=False))
        ev_with, _ = replay_file(with_lv)
        ev_without, _ = replay_file(without)
        assert all(e["kind"] != "trigger" for e in ev_without)
        # candle stream identical — triggers are additive, never mutating
        assert [e for e in ev_with if e["kind"] != "trigger"] == ev_without

    def test_bad_lv_lines_refuse_loudly(self, tmp_path) -> None:
        lines = self._lines(with_levels=True)
        lines[1] = {"k": "lv", "sid": 42}  # missing "levels"
        rec = self._write(tmp_path / "bad.jsonl", lines)
        with pytest.raises(ReplayError, match="missing"):
            load_recording(rec)
        # a recorded-but-invalid level is real divergence: fail, not skip
        lines[1] = {"k": "lv", "sid": 42, "levels": [{"id": 1, "kind": "nope"}]}
        rec = self._write(tmp_path / "bad2.jsonl", lines)
        with pytest.raises(ValueError, match="unknown kind"):
            replay_file(rec)


class _AlertRedisSpy:
    """Pipeline spy + XADD capture for the alert seam."""

    def __init__(self) -> None:
        self.xadd_calls: list[tuple[str, dict[str, Any], int | None, bool]] = []

    def pipeline(self, transaction: bool = True) -> "_AlertRedisSpy":
        return self

    def set(self, *args: Any, **kwargs: Any) -> None:
        pass

    def publish(self, *args: Any, **kwargs: Any) -> None:
        pass

    def execute(self) -> None:
        pass

    def xadd(
        self,
        stream: str,
        fields: dict[str, Any],
        maxlen: int | None = None,
        approximate: bool = False,
    ) -> None:
        self.xadd_calls.append((stream, fields, maxlen, approximate))


def _tick_item(ts: int, price: str) -> tuple[str, list[dict[str, Any]], None]:
    from datetime import UTC, datetime

    aware = datetime.fromtimestamp(ts, tz=UTC)
    return (
        "ticks",
        [
            {
                "instrument_token": 777,
                "last_price": price,
                "volume_traded": 1000,
                "exchange_timestamp": aware.astimezone().replace(tzinfo=None),
            }
        ],
        None,
    )


class TestWorkerAlertSeam:
    def _state(self, tmp_path) -> tuple[WorkerState, _AlertRedisSpy]:
        spy = _AlertRedisSpy()
        state = WorkerState(
            book=_book(),
            token_map=TOKEN_MAP,
            redis=spy,
            writer_q=queue.Queue(),
            recorder=open(tmp_path / "rec.jsonl", "a", encoding="utf-8"),
            session_day=DAY.isoformat(),
        )
        return state, spy

    def test_levels_apply_record_and_alert_fields(self, tmp_path) -> None:
        state, spy = self._state(tmp_path)
        meta = {
            1001: {"source": "entry_zone", "style": "swing", "signal_id": 7},
        }
        state.process_item(("levels", [(42, [ZONE], meta)], None))
        state.process_item(_tick_item(OPEN_TS + 5, "101.55"))

        assert state.stats["levels"] == 1
        assert state.stats["triggers"] == 1
        assert len(spy.xadd_calls) == 1
        stream, fields, maxlen, approx = spy.xadd_calls[0]
        assert stream == "alerts:live"
        assert (maxlen, approx) == (10_000, True)
        assert fields == {
            "sid": 42,
            "level_id": 1001,
            "tag": "zone_enter",
            "price": "101.55",
            "ts": OPEN_TS + 5,
            "day": DAY.isoformat(),
            "source": "entry_zone",
            "style": "swing",
            "signal_id": 7,
        }
        # recording order: the lv line precedes the tick that fired
        state.recorder.flush()
        kinds = [
            json.loads(line)["k"]
            for line in open(tmp_path / "rec.jsonl", encoding="utf-8")
        ]
        assert kinds == ["lv", "t"]

    def test_unknown_meta_defaults_to_market_style(self, tmp_path) -> None:
        state, spy = self._state(tmp_path)
        state.process_item(("levels", [(42, [PDH], {})], None))
        state.process_item(_tick_item(OPEN_TS + 5, "149.00"))
        state.process_item(_tick_item(OPEN_TS + 6, "150.10"))
        (_, fields, _, _) = spy.xadd_calls[0]
        assert fields["style"] == "market"
        assert fields["tag"] == "cross_up"
        assert "signal_id" not in fields

    def test_one_bad_stock_never_blocks_the_rest(self, tmp_path) -> None:
        state, spy = self._state(tmp_path)
        bad = [{"id": 5, "kind": "nope"}]
        state.process_item(
            ("levels", [(41, bad, {}), (42, [ZONE], {})], None)
        )
        assert state.stats["levels"] == 1  # only the good stock applied
        state.process_item(_tick_item(OPEN_TS + 5, "101.55"))
        assert len(spy.xadd_calls) == 1
        # no lv line was recorded for the refused stock
        state.recorder.flush()
        lv_sids = [
            json.loads(line)["sid"]
            for line in open(tmp_path / "rec.jsonl", encoding="utf-8")
            if json.loads(line)["k"] == "lv"
        ]
        assert lv_sids == [42]
