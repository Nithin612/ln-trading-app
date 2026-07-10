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

Events are canonicalized as sorted-key compact JSON lines; the sha256 of
that stream is the digest goldens pin. `python -m app.broker.replay
<recording> [--emit out.jsonl]` prints counts + digest — the soak-day
ritual for pinning a real session as a golden.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

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
}


def load_recording(path: str | Path) -> list[dict[str, Any]]:
    """Parse a recording; every line must be one of the known shapes and
    the first line must be a header (self-describing sessions).

    One tolerance, matching how recordings actually break: a NON-JSON line
    immediately followed by a session header is a torn tail from a hard
    crash (the restart's header lands right after it) — skipped with a
    warning instead of poisoning the whole file (bug-hunter MEDIUM,
    2026-07-10). Garbage anywhere else still refuses loudly.
    """
    raw_lines: list[tuple[int, str]] = []
    with open(path, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            stripped = raw.strip()
            if stripped:
                raw_lines.append((lineno, stripped))
    if not raw_lines:
        raise ReplayError(f"{path}: empty recording")

    items: list[dict[str, Any]] = []
    for idx, (lineno, raw) in enumerate(raw_lines):
        nxt = raw_lines[idx + 1][1] if idx + 1 < len(raw_lines) else ""
        item = _parse_line(str(path), lineno, raw, nxt)
        if item is not None:
            items.append(item)
    if not items:
        raise ReplayError(f"{path}: empty recording")
    if items[0]["k"] != "h":
        raise ReplayError(
            f"{path}: first line must be a session header (k='h') — "
            "recordings are self-describing"
        )
    return items


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


def replay_events(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Feed a recording through fresh LiveBooks (one per header) and
    return the full event stream in emission order, each event tagged
    with the session day."""
    import tradecore

    events: list[dict[str, Any]] = []
    book: Any = None
    day = ""
    for item in items:
        kind = item["k"]
        if kind == "h":
            book = tradecore.LiveBook(item["open"], item["close"], list(item["tfs"]))
            day = str(item.get("day", ""))
            continue
        if book is None:  # unreachable via load_recording; belt-and-braces
            raise ReplayError("tick/pulse before any session header")
        if kind == "t":
            batch_events = book.on_ticks(
                [(item["sid"], item["ts"], item["p"], item["dv"], item["q"])]
            )
        else:
            batch_events = book.on_time(item["ts"])
        for e in batch_events:
            events.append({"day": day, **e})
    return events


def canonical_lines(events: list[dict[str, Any]]) -> list[str]:
    return [json.dumps(e, sort_keys=True, separators=(",", ":")) for e in events]


def events_digest(events: list[dict[str, Any]]) -> str:
    h = hashlib.sha256()
    for line in canonical_lines(events):
        h.update(line.encode())
        h.update(b"\n")
    return h.hexdigest()


def replay_file(path: str | Path) -> tuple[list[dict[str, Any]], str]:
    """(events, digest) for a recording file — the one-call test surface."""
    events = replay_events(load_recording(path))
    return events, events_digest(events)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="replay a live-worker recording")
    parser.add_argument("recording")
    parser.add_argument("--emit", help="write the canonical event stream here")
    args = parser.parse_args(argv)

    items = load_recording(args.recording)
    events, digest = replay_events(items), ""
    digest = events_digest(events)
    committed = sum(1 for e in events if e["kind"] == "committed")
    if args.emit:
        Path(args.emit).write_text(
            "\n".join(canonical_lines(events)) + "\n", encoding="utf-8"
        )
    print(
        f"replayed {len(items)} lines -> {len(events)} events "
        f"({committed} committed)\nsha256 {digest}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
