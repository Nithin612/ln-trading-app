"""Record/replay harness (Phase 3 slice 3.4) — `make replay`.

The committed recording is a synthetic session exercising the engine's
edge semantics (pre-open rejection, volume baseline + counter reset,
cross-bucket commits, a late tick dropped by 1m but absorbed in-bucket
by 5m/1h, pulse-driven closes). Replaying it must reproduce the pinned
event stream BYTE-IDENTICALLY — the only ground truth the realtime
layer has (no working v1 baseline exists). A real-session golden joins
this file after the first soak day.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from app.broker.replay import (
    ReplayError,
    canonical_lines,
    events_digest,
    iter_events,
    iter_recording,
    load_recording,
    replay_file,
    replay_stream,
)

GOLDENS = Path(__file__).parent / "goldens"
RECORDING = GOLDENS / "replay_session_v1.jsonl"
EXPECTED_EVENTS = GOLDENS / "replay_session_v1.events.jsonl"

PINNED_DIGEST = "da288d247fb8bd16098c9f4d026181bb654a26c0c217de3491f9342034f48725"


@pytest.mark.replay
class TestReplayGolden:
    def test_replay_is_byte_identical_to_the_pinned_stream(self) -> None:
        events, digest = replay_file(RECORDING)
        assert digest == PINNED_DIGEST
        got = "\n".join(canonical_lines(events)) + "\n"
        assert got == EXPECTED_EVENTS.read_text(encoding="utf-8")

    def test_replay_is_deterministic_across_runs(self) -> None:
        first, d1 = replay_file(RECORDING)
        second, d2 = replay_file(RECORDING)
        assert d1 == d2
        assert first == second

    def test_pinned_edge_semantics(self) -> None:
        events, _ = replay_file(RECORDING)
        committed = [e for e in events if e["kind"] == "committed"]
        # pre-open tick minted nothing: first committed period is the open
        assert min(e["time"] for e in committed) == load_recording(RECORDING)[0]["open"]
        # late tick: absent from every 1m candle, present in the 1h high
        assert not any(e["high"] == 9990000 for e in committed if e["tf_minutes"] == 1)
        assert any(e["high"] == 9990000 for e in committed if e["tf_minutes"] == 60)
        # day-volume counter reset contributes zero, never the whole day
        sid12_1m = [e["volume"] for e in committed if e["stock_id"] == 12 and e["tf_minutes"] == 1]
        assert sid12_1m == [0, 600, 0, 310]


@pytest.mark.replay
class TestRecordingValidation:
    def test_headerless_recording_refused(self, tmp_path: Path) -> None:
        p = tmp_path / "r.jsonl"
        p.write_text('{"k":"t","sid":1,"ts":1,"p":"1","dv":null,"q":0}\n', encoding="utf-8")
        with pytest.raises(ReplayError, match="header"):
            load_recording(p)

    def test_garbage_line_refused_with_location(self, tmp_path: Path) -> None:
        p = tmp_path / "r.jsonl"
        p.write_text('{"k":"h","open":1,"close":2,"tfs":[1]}\nnot json\n', encoding="utf-8")
        with pytest.raises(ReplayError, match=":2"):
            load_recording(p)

    def test_empty_recording_refused(self, tmp_path: Path) -> None:
        p = tmp_path / "r.jsonl"
        p.write_text("", encoding="utf-8")
        with pytest.raises(ReplayError, match="empty"):
            load_recording(p)

    def test_digest_is_order_sensitive(self) -> None:
        a = [{"kind": "forming", "x": 1}, {"kind": "forming", "x": 2}]
        assert events_digest(a) != events_digest(list(reversed(a)))


@pytest.mark.replay
class TestStreamingReplay:
    """The 2026-07-17 streaming refactor: full-day recordings (600 MB,
    ~9.5 M lines) OOMed exit-137 because the harness materialized every
    item AND every event. The streaming path must be byte-identical to
    the buffered one — same digest, same emit file, same counts — while
    parsing single-pass."""

    def test_streaming_digest_matches_buffered_and_pin(self) -> None:
        s = replay_stream(RECORDING)
        events, digest = replay_file(RECORDING)
        assert s.digest == digest == PINNED_DIGEST
        assert s.events == len(events)
        assert s.committed == sum(1 for e in events if e["kind"] == "committed")
        assert s.triggers == sum(1 for e in events if e["kind"] == "trigger")
        assert s.lines == len(load_recording(RECORDING))

    def test_streaming_emit_matches_the_pinned_stream(self, tmp_path: Path) -> None:
        out = tmp_path / "emit.jsonl"
        replay_stream(RECORDING, emit=out)
        assert out.read_text(encoding="utf-8") == EXPECTED_EVENTS.read_text(encoding="utf-8")

    def test_iter_recording_is_single_pass(self, tmp_path: Path) -> None:
        """Canary for the OOM fix: the parser must yield items BEFORE
        reading the rest of the file. The old buffered loader parsed the
        whole file up front, so it could never hand back the header of a
        file whose later lines are garbage — the streaming one must."""
        p = tmp_path / "r.jsonl"
        p.write_text(
            '{"k":"h","open":1,"close":2,"tfs":[1]}\n'
            "garbage-later-in-file\n"
            '{"k":"p","ts":1}\n',
            encoding="utf-8",
        )
        it = iter_recording(p)
        assert next(it)["k"] == "h"  # yielded before the garbage is reached
        with pytest.raises(ReplayError, match="not JSON"):
            next(it)

    def test_streaming_tolerates_torn_tail_like_buffered(self, tmp_path: Path) -> None:
        rec = RECORDING.read_text(encoding="utf-8")
        header = rec.splitlines()[0]
        torn = '{"k":"t","sid":11,"ts":17835'
        run2 = header + "\n" + rec[len(header) + 1 :]
        p = tmp_path / "crashed.jsonl"
        p.write_text(rec + torn + "\n" + run2, encoding="utf-8")
        s = replay_stream(p)
        events, digest = replay_file(p)
        assert s.digest == digest
        assert s.events == len(events)

    def test_streaming_headerless_refused(self, tmp_path: Path) -> None:
        p = tmp_path / "r.jsonl"
        p.write_text('{"k":"t","sid":1,"ts":1,"p":"1","dv":null,"q":0}\n', encoding="utf-8")
        with pytest.raises(ReplayError, match="header"):
            replay_stream(p)

    def test_streaming_empty_refused(self, tmp_path: Path) -> None:
        p = tmp_path / "r.jsonl"
        p.write_text("", encoding="utf-8")
        with pytest.raises(ReplayError, match="empty"):
            replay_stream(p)

    def test_failed_replay_never_clobbers_the_emit_target(self, tmp_path: Path) -> None:
        """bug-hunter MEDIUM (2026-07-17): the first streaming cut opened
        the emit target with truncate BEFORE replaying, so a failed run
        (typo'd path, torn recording) destroyed whatever --emit pointed
        at — e.g. a pinned golden — and left partial streams that look
        complete. Emit must be atomic: target untouched on failure, no
        stray partial file."""
        target = tmp_path / "pinned.jsonl"
        target.write_text("PRECIOUS PINNED CONTENT\n", encoding="utf-8")
        # (a) unreadable recording path
        with pytest.raises(FileNotFoundError):
            replay_stream(tmp_path / "nope.jsonl", emit=target)
        assert target.read_text(encoding="utf-8") == "PRECIOUS PINNED CONTENT\n"
        # (b) recording that fails mid-replay (garbage tail, no rescuing header)
        bad = tmp_path / "bad.jsonl"
        bad.write_text(
            RECORDING.read_text(encoding="utf-8") + "torn-with-no-restart\n",
            encoding="utf-8",
        )
        with pytest.raises(ReplayError, match="not JSON"):
            replay_stream(bad, emit=target)
        assert target.read_text(encoding="utf-8") == "PRECIOUS PINNED CONTENT\n"
        assert not (tmp_path / "pinned.jsonl.tmp").exists()

    def test_iter_events_is_lazy(self) -> None:
        """Canary for the OOM fix at the event level: a buffering
        iter_events (or a replay_stream that secretly list()s it) would
        consume the whole feed before yielding — the exit-137 class. The
        first event must arrive before the input is exhausted."""
        items = load_recording(RECORDING)
        consumed = 0

        def feed() -> Iterator[dict[str, Any]]:
            nonlocal consumed
            for item in items:
                consumed += 1
                yield item

        first = next(iter_events(feed()))
        assert first["kind"] in {"forming", "committed", "trigger"}
        assert consumed < len(items)


@pytest.mark.replay
class TestBugHunterRegressions:
    """Pinned after the 2026-07-10 bug-hunter pass on 3.4."""

    def test_torn_tail_before_header_is_tolerated(self, tmp_path: Path) -> None:
        """A hard crash leaves a torn partial line; the restart appends a
        new header right after it. That one shape must not poison the
        whole file — run 2's session stays replayable."""
        rec = RECORDING.read_text(encoding="utf-8")
        header = rec.splitlines()[0]
        torn = '{"k":"t","sid":11,"ts":17835'  # cut mid-write by the crash
        run2 = header + "\n" + rec[len(header) + 1 :]
        p = tmp_path / "crashed.jsonl"
        p.write_text(rec + torn + "\n" + run2, encoding="utf-8")
        events, _ = replay_file(p)
        # both sessions replay: exactly twice the single-session events
        single, _ = replay_file(RECORDING)
        assert len(events) == 2 * len(single)

    def test_garbage_not_followed_by_header_still_refuses(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.jsonl"
        p.write_text(
            RECORDING.read_text(encoding="utf-8") + "torn-mid-file\n"
            + '{"k":"p","ts":1}' + "\n",
            encoding="utf-8",
        )
        with pytest.raises(ReplayError, match="not JSON"):
            load_recording(p)

    def test_missing_key_refused_with_location(self, tmp_path: Path) -> None:
        p = tmp_path / "trimmed.jsonl"
        p.write_text(
            '{"k":"h","open":1,"close":2,"tfs":[1]}\n'
            '{"k":"t","sid":1,"ts":1,"p":"1","q":0}\n',  # dv missing
            encoding="utf-8",
        )
        with pytest.raises(ReplayError, match=r":2.*missing.*dv"):
            load_recording(p)

    def test_non_object_line_refused_typed(self, tmp_path: Path) -> None:
        p = tmp_path / "int.jsonl"
        p.write_text('{"k":"h","open":1,"close":2,"tfs":[1]}\n123\n', encoding="utf-8")
        with pytest.raises(ReplayError, match="unknown line shape"):
            load_recording(p)
