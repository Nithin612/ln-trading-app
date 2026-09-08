"""A9/A10 — the progress envelope for long-running jobs.

A dependency-free `{phase, step, total_steps, message}` envelope (+ elapsed, + an optional
mid-flight `result`) that any long job can emit so a watcher renders progress without knowing
the pipeline. These tests cover the envelope arithmetic (percent, unknown-total), both
renderings (human line, JSON), the reporter's stepping + mid-flight result, and the rule that
a broken sink can never break the job it reports on.
"""

import itertools
import json

from app.core.progress import ProgressEvent, ProgressReporter, stream_sink


def _clock():
    """A deterministic monotonic clock: 0, 1, 2, 3, … one tick per call."""
    return itertools.count(0, 1).__next__


class TestEvent:
    def test_pct_is_a_rounded_percentage(self) -> None:
        assert ProgressEvent("j", "p", 3, 12, "m", 1.0).pct == 25

    def test_pct_is_none_when_total_is_unknown(self) -> None:
        assert ProgressEvent("j", "p", 5, 0, "m", 1.0).pct is None

    def test_pct_never_exceeds_100(self) -> None:
        assert ProgressEvent("j", "p", 13, 12, "m", 1.0).pct == 100

    def test_human_line_carries_the_envelope(self) -> None:
        line = ProgressEvent("analysis", "shadow gates", 3, 12, "regime", 4.25).to_line()
        assert "[analysis 3/12 25% · 4.2s] shadow gates: regime" == line

    def test_human_line_shows_step_count_when_total_unknown(self) -> None:
        line = ProgressEvent("analysis", "ingest", 2, 0, "eod", 1.0).to_line()
        assert "step 2" in line and "%" not in line

    def test_human_line_appends_a_midflight_result(self) -> None:
        line = ProgressEvent("j", "p", 1, 2, "m", 1.0, result="BUY 60%").to_line()
        assert line.endswith("→ BUY 60%")

    def test_json_is_valid_and_complete(self) -> None:
        ev = ProgressEvent("analysis", "gates", 3, 12, "regime", 4.25, result="ready")
        d = json.loads(ev.to_json())
        assert d["label"] == "analysis" and d["step"] == 3 and d["total_steps"] == 12
        assert d["pct"] == 25 and d["result"] == "ready" and d["message"] == "regime"


class TestReporter:
    def test_step_advances_and_emits(self) -> None:
        seen: list[ProgressEvent] = []
        r = ProgressReporter(3, label="analysis", sink=seen.append, clock=_clock())
        e1 = r.step("first", phase="a")
        e2 = r.step("second", phase="b")
        assert (e1.step, e2.step) == (1, 2)
        assert [e.message for e in seen] == ["first", "second"]
        assert e1.total_steps == 3 and e1.label == "analysis"

    def test_elapsed_grows_with_the_clock(self) -> None:
        r = ProgressReporter(2, sink=lambda _e: None, clock=_clock())
        # start consumed tick 0; first step reads tick 1 → elapsed 1.0
        assert r.step("x").elapsed_s == 1.0

    def test_result_does_not_advance_the_step(self) -> None:
        seen: list[ProgressEvent] = []
        r = ProgressReporter(3, sink=seen.append, clock=_clock())
        r.step("stage")
        ev = r.result("running tally: 4 blocked")
        assert ev.step == 1 and ev.result == "running tally: 4 blocked" and ev.message == ""

    def test_negative_total_is_clamped_to_unknown(self) -> None:
        r = ProgressReporter(-5, sink=lambda _e: None)
        assert r.step("x").total_steps == 0

    def test_a_broken_sink_never_breaks_the_job(self) -> None:
        def _boom(_ev: ProgressEvent) -> None:
            raise RuntimeError("sink exploded")

        r = ProgressReporter(1, sink=_boom)
        ev = r.step("still returns")  # must not raise
        assert ev.step == 1

    def test_default_sink_writes_a_line_to_stderr(self, capsys) -> None:
        ProgressReporter(2, label="analysis").step("daily report", phase="report")
        err = capsys.readouterr().err
        assert "[analysis 1/2" in err and "report: daily report" in err


def test_stream_sink_json_mode_emits_one_json_object(capsys) -> None:
    import sys

    sink = stream_sink(sys.stdout, json_mode=True)
    sink(ProgressEvent("j", "p", 1, 4, "m", 0.5))
    out = capsys.readouterr().out.strip()
    assert json.loads(out)["pct"] == 25
