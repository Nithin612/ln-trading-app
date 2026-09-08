"""A9/A10 — a progress envelope for long-running jobs.

## Why this exists

We have several long jobs with **no progress protocol at all**: `make analysis` (a dozen
report + sidecar stages), backtests, the ~8-minute walk-forward replay, EOD ingestion with
its ≤21-day self-heal. Today each is opaque until it finishes or a stray log line appears —
so a run that has silently wedged is indistinguishable from one that is merely slow.

The reference (repo 3) carried one good idea, independent of its LLM framing: every streamed
message is a small envelope — `phase · step · total_steps · message · timestamp` — so a
watcher renders a phase label and a progress tally **without knowing anything about the
pipeline**. A10 is the same idea applied to the *result*: a mid-flight value (`result`) can
ride the envelope so the running answer is visible before the job ends, not only at the end.

This module is that envelope, and nothing more. It is deliberately dependency-free and
framework-agnostic: a `ProgressReporter` any long job can hold, emitting `ProgressEvent`s to a
stream (human lines by default, one JSON object per line under `json_mode` for a machine
consumer). It knows nothing about analysis, backtests or Celery.

## Discipline

- **Emission must never break the job it reports on.** A progress line is worth nothing if a
  formatting bug in it can fail a backtest, so every emit is wrapped and swallowed — the same
  rule the notifier follows for a different reason.
- **`total_steps` may be unknown.** A job that cannot count its stages up front passes 0; the
  line then shows `step N` without a percentage rather than dividing by zero.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TextIO

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProgressEvent:
    """One point on a long job's timeline — the envelope a watcher renders."""

    label: str  # which job, e.g. "analysis"
    phase: str  # coarse stage, e.g. "shadow gates"
    step: int  # 1-based
    total_steps: int  # 0 ⇒ unknown
    message: str
    elapsed_s: float
    result: str | None = None  # A10 — a mid-flight result/consensus, if any
    timestamp: str = ""

    @property
    def pct(self) -> int | None:
        """Completion percent, or None when the total is unknown (never divide by zero)."""
        if self.total_steps <= 0:
            return None
        return min(100, int(round(100 * self.step / self.total_steps)))

    def to_line(self) -> str:
        """A compact human line for a terminal/stderr."""
        head = f"{self.step}/{self.total_steps}" if self.total_steps > 0 else f"step {self.step}"
        pct = f" {self.pct}%" if self.pct is not None else ""
        line = f"[{self.label} {head}{pct} · {self.elapsed_s:.1f}s] {self.phase}: {self.message}"
        if self.result:
            line += f" → {self.result}"
        return line

    def to_json(self) -> str:
        """One JSON object per line — the machine-readable envelope (A9)."""
        return json.dumps(
            {
                "label": self.label,
                "phase": self.phase,
                "step": self.step,
                "total_steps": self.total_steps,
                "pct": self.pct,
                "message": self.message,
                "elapsed_s": round(self.elapsed_s, 3),
                "result": self.result,
                "timestamp": self.timestamp,
            }
        )


#: A sink consumes one event. Swap it in tests to capture events instead of writing them.
Sink = Callable[[ProgressEvent], None]


def stream_sink(stream: TextIO, *, json_mode: bool = False) -> Sink:
    """A sink that writes each event to `stream` — a JSON line under `json_mode`, else the
    compact human line. Progress goes to stderr by convention so a job's real stdout (a
    report, a JSON result) stays clean and pipeable."""

    def _emit(ev: ProgressEvent) -> None:
        stream.write((ev.to_json() if json_mode else ev.to_line()) + "\n")
        stream.flush()

    return _emit


class ProgressReporter:
    """Held by a long job; call `step()` at each stage boundary.

    Not thread-safe and not meant to be — a single sequential pipeline owns one reporter. For
    concurrent stages, give each its own reporter and label, or emit from the coordinator.
    """

    def __init__(
        self,
        total_steps: int,
        *,
        label: str = "job",
        sink: Sink | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.label = label
        self.total_steps = max(0, total_steps)
        self._sink: Sink = sink if sink is not None else stream_sink(sys.stderr)
        self._clock = clock
        self._start = clock()
        self._step = 0

    def step(
        self, message: str, *, phase: str = "", result: str | None = None, advance: int = 1
    ) -> ProgressEvent:
        """Advance by `advance` (default 1) and emit an event. Returns it so a caller can also
        log or store it. Emission failures are swallowed — reporting must not break the job."""
        self._step += advance
        ev = ProgressEvent(
            label=self.label,
            phase=phase,
            step=self._step,
            total_steps=self.total_steps,
            message=message,
            elapsed_s=self._clock() - self._start,
            result=result,
            timestamp=datetime.now(tz=UTC).isoformat(),
        )
        self._safe_emit(ev)
        return ev

    def result(self, message: str, *, phase: str = "") -> ProgressEvent:
        """A10 — emit a mid-flight RESULT without advancing the step counter. Use for a
        running tally that updates between stage boundaries."""
        ev = ProgressEvent(
            label=self.label,
            phase=phase,
            step=self._step,
            total_steps=self.total_steps,
            message="",
            elapsed_s=self._clock() - self._start,
            result=message,
            timestamp=datetime.now(tz=UTC).isoformat(),
        )
        self._safe_emit(ev)
        return ev

    def _safe_emit(self, ev: ProgressEvent) -> None:
        try:
            self._sink(ev)
        except Exception:  # noqa: BLE001 — a progress line must never break the job
            log.debug("progress emit failed (non-fatal)", exc_info=True)
