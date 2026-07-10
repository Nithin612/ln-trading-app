"""Record/replay harness (Phase 3 slice 3.4) — `make replay`.

The committed recording is a synthetic session exercising the engine's
edge semantics (pre-open rejection, volume baseline + counter reset,
cross-bucket commits, a late tick dropped by 1m but absorbed in-bucket
by 5m/1h, pulse-driven closes). Replaying it must reproduce the pinned
event stream BYTE-IDENTICALLY — the only ground truth the realtime
layer has (no working v1 baseline exists). A real-session golden joins
this file after the first soak day.
"""

from pathlib import Path

import pytest
from app.broker.replay import (
    ReplayError,
    canonical_lines,
    events_digest,
    load_recording,
    replay_file,
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
