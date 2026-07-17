"""Record/replay harness (Phase 3, slice 3.4).

A live-worker recording (`settings.live_record_path` JSONL) is the exact
input stream the engine consumed: one header per session start, then tick
and pulse lines in processing order. Replaying it through a FRESH
`tradecore.LiveBook` must reproduce the live event stream byte-for-byte —
the LiveEngine is pure, so any diff means non-determinism crept in
somewhere. This is the phase's ground truth: there is no working v1
baseline to compare against (plan §2).

Line shapes (compact keys, one JSON object per line):
  {"k":"h","day":…,"open":…,"close":…,"tfs":[…],"min_tick_ts":…}  header
  {"k":"t","sid":…,"ts":…,"p":"…","dv":…|null,"q":…}              tick
  {"k":"p","ts":…}                                                pulse
  {"k":"lv","sid":…,"levels":[{…}, …]}                            levels (3.5)

Levels are INPUT exactly like ticks: the worker records every accepted
`set_levels` call in stream order, so replay reproduces trigger events
deterministically. Recordings without "lv" lines (all pre-3.5 goldens)
replay to a byte-identical event stream.

Events are canonicalized as sorted-key compact JSON lines; the sha256 of
that stream is the digest goldens pin. `python -m app.broker.replay
<recording> [--emit out.jsonl]` prints counts + digest — the soak-day
ritual for pinning a real session as a golden.

The whole path is STREAMING (2026-07-17): parse → FFI → hash one line at
a time, so a full-day recording (600 MB, ~9.5 M lines) replays in
constant memory — the buffering version materialized every item AND
every event and OOMed exit-137 on real soak days. `load_recording` /
`replay_events` remain as list-building wrappers over the same
generators for tests and small goldens; digests are byte-identical
either way.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, NamedTuple, TextIO

log = logging.getLogger(__name__)


class ReplayError(RuntimeError):
    """Recording the harness refuses to replay (no header, bad line)."""


# Required keys per line kind — validated up front so a trimmed or torn
# recording fails as a typed ReplayError with file:line, never a bare
# KeyError deep inside replay (bug-hunter LOW, 2026-07-10).
_REQUIRED_KEYS: dict[str, set[str]] = {
    "h": {"open", "close", "tfs"},
    "t": {"sid", "ts", "p", "dv", "q"},
    "p": {"ts"},
    "lv": {"sid", "levels"},
}


def iter_recording(path: str | Path) -> Iterator[dict[str, Any]]:
    """Stream validated recording items one line at a time (O(1) memory);
    every line must be one of the known shapes and the first yielded item
    must be a header (self-describing sessions).

    One tolerance, matching how recordings actually break: a NON-JSON line
    immediately followed by a session header is a torn tail from a hard
    crash (the restart's header lands right after it) — skipped with a
    warning instead of poisoning the whole file (bug-hunter MEDIUM,
    2026-07-10). Garbage anywhere else still refuses loudly.

    The torn-tail lookahead needs exactly one line of buffer, so parsing
    stays single-pass: each non-blank line is processed when its successor
    arrives, the last against "".
    """
    first = True
    prev: tuple[int, str] | None = None
    with open(path, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            if prev is not None:
                item = _parse_line(str(path), prev[0], prev[1], stripped)
                if item is not None:
                    first = _check_first(str(path), item, first)
                    yield item
            prev = (lineno, stripped)
        if prev is None:
            raise ReplayError(f"{path}: empty recording")
        item = _parse_line(str(path), prev[0], prev[1], "")
        if item is not None:
            first = _check_first(str(path), item, first)
            yield item
        if first:  # every line was a tolerated crash artifact
            raise ReplayError(f"{path}: empty recording")


def _check_first(path: str, item: dict[str, Any], first: bool) -> bool:
    """Enforce the header-first contract on the first real item."""
    if first and item["k"] != "h":
        raise ReplayError(
            f"{path}: first line must be a session header (k='h') — "
            "recordings are self-describing"
        )
    return False


def load_recording(path: str | Path) -> list[dict[str, Any]]:
    """Buffered wrapper over `iter_recording` — tests and small goldens."""
    return list(iter_recording(path))


def _parse_line(
    path: str, lineno: int, raw: str, next_raw: str
) -> dict[str, Any] | None:
    """One validated recording line, or None for a tolerated crash artifact."""
    try:
        item = json.loads(raw)
    except json.JSONDecodeError as exc:
        if '"k":"h"' in next_raw:
            log.warning(
                "%s:%d: torn line before a session header — skipping "
                "(crash artifact)", path, lineno,
            )
            return None
        raise ReplayError(f"{path}:{lineno}: not JSON: {exc}") from exc
    if not isinstance(item, dict) or item.get("k") not in _REQUIRED_KEYS:
        raise ReplayError(f"{path}:{lineno}: unknown line shape: {raw[:60]}")
    missing = _REQUIRED_KEYS[str(item["k"])] - item.keys()
    if missing:
        raise ReplayError(
            f"{path}:{lineno}: {item['k']!r} line missing {sorted(missing)}"
        )
    return item


def iter_events(items: Iterable[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    """Feed recording items through fresh LiveBooks (one per header) and
    yield the event stream in emission order, each event tagged with the
    session day. Streaming: holds one input item + one FFI batch at a
    time."""
    import tradecore

    book: Any = None
    day = ""
    for item in items:
        kind = item["k"]
        if kind == "h":
            book = tradecore.LiveBook(item["open"], item["close"], list(item["tfs"]))
            day = str(item.get("day", ""))
            continue
        if book is None:  # unreachable via iter_recording; belt-and-braces
            raise ReplayError("tick/pulse before any session header")
        if kind == "t":
            batch_events = book.on_ticks(
                [(item["sid"], item["ts"], item["p"], item["dv"], item["q"])]
            )
        elif kind == "lv":
            # Levels were recorded only when the live engine ACCEPTED them,
            # so a refusal here is real divergence — fail loud.
            book.set_levels(item["sid"], list(item["levels"]))
            continue
        else:
            batch_events = book.on_time(item["ts"])
        for e in batch_events:
            yield {"day": day, **e}


def replay_events(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Buffered wrapper over `iter_events` — tests and small goldens."""
    return list(iter_events(items))


def _canonical(event: dict[str, Any]) -> str:
    return json.dumps(event, sort_keys=True, separators=(",", ":"))


def canonical_lines(events: list[dict[str, Any]]) -> list[str]:
    return [_canonical(e) for e in events]


def events_digest(events: list[dict[str, Any]]) -> str:
    h = hashlib.sha256()
    for e in events:
        h.update(_canonical(e).encode())
        h.update(b"\n")
    return h.hexdigest()


def replay_file(path: str | Path) -> tuple[list[dict[str, Any]], str]:
    """(events, digest) for a recording file — the one-call test surface."""
    events = replay_events(load_recording(path))
    return events, events_digest(events)


class ReplaySummary(NamedTuple):
    """What the digest ritual pins: counts to reconcile against the live
    worker's logged counters, plus the event-stream sha256."""

    lines: int  # validated items consumed (headers + lv included, torn skipped)
    events: int
    committed: int
    triggers: int
    digest: str


@contextmanager
def _atomic_emit(emit: str | Path | None) -> Iterator[TextIO | None]:
    """Emit-file lifecycle: write `<target>.tmp`, rename onto the target
    only on success, unlink on failure — a failed replay must never
    clobber the target or leave a partial stream that looks complete
    (bug-hunter MEDIUM, 2026-07-17)."""
    if emit is None:
        yield None
        return
    tmp = Path(emit).with_name(Path(emit).name + ".tmp")
    out = open(tmp, "w", encoding="utf-8")
    try:
        yield out
    except BaseException:
        out.close()
        tmp.unlink(missing_ok=True)
        raise
    out.close()
    os.replace(tmp, emit)


def replay_stream(path: str | Path, emit: str | Path | None = None) -> ReplaySummary:
    """Constant-memory replay of an arbitrarily large recording: one line
    in → FFI → sha256 update → (optional) one canonical line out. The
    digest is byte-identical to `events_digest(replay_events(...))`.
    The emit file is written atomically; a zero-event replay emits an
    empty file, consistent with the empty-stream digest.
    """
    h = hashlib.sha256()
    lines = events = committed = triggers = 0

    def _counted(it: Iterator[dict[str, Any]]) -> Iterator[dict[str, Any]]:
        nonlocal lines
        for item in it:
            lines += 1
            yield item

    with _atomic_emit(emit) as out:
        for e in iter_events(_counted(iter_recording(path))):
            line = _canonical(e)
            h.update(line.encode())
            h.update(b"\n")
            events += 1
            if e["kind"] == "committed":
                committed += 1
            elif e["kind"] == "trigger":
                triggers += 1
            if out is not None:
                out.write(line + "\n")
    return ReplaySummary(lines, events, committed, triggers, h.hexdigest())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="replay a live-worker recording")
    parser.add_argument("recording")
    parser.add_argument("--emit", help="write the canonical event stream here")
    args = parser.parse_args(argv)

    s = replay_stream(args.recording, emit=args.emit)
    print(
        f"replayed {s.lines} lines -> {s.events} events "
        f"({s.committed} committed, {s.triggers} triggers)\nsha256 {s.digest}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
