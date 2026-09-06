"""A27 — config dry-run: what does `.env` say, and which running process has heard it?

    uv run python scripts/config_dryrun.py            # full report
    uv run python scripts/config_dryrun.py --gates    # just the gate modes + rails
    uv run python scripts/config_dryrun.py --quiet    # exit code only

Exit codes: **0** verified clean · **1** could NOT check (no `.env` at this checkout's
path — normal in an isolated worktree) · **2** a live process predates the last `.env`
change. `1` is deliberately not `0`: "I could not look" and "I looked and it was fine"
are different answers and must not share a code.

## The trap this exists to close

`get_settings()` is an `@lru_cache` singleton, so **a `.env` edit reaches a running
backend or worker only when that process re-imports `app.core.config`.** Editing the file
and assuming the change took effect has bitten this project repeatedly — it is why
CLAUDE.md carries a whole hand-run recipe for verifying a gate's live mode (fresh settings
load · the uvicorn **reload-CHILD** start time, since the parent never restarts on reload ·
the celery start time · compared against the flip commit's timestamp).

This is that recipe as a command.

## Why it matters more now than it did

**The cycle-2 reset is itself a config event**: the heat cap flips to `active` and the paper
clock restarts. Getting that wrong silently does not cost a day — it invalidates the
*window*, which is 45–50 trading days. That is the most expensive version of this bug
available, and it is coming.

## What it does NOT do

⚠ **It never prints a secret, and it never reads `.env` itself.** Values arrive through
pydantic's own loader; anything whose name looks like a credential is reported as
`set/unset`, never shown. The file is only ever `stat`-ed for its mtime.

⚠ **A "stale" verdict is a WARNING, not a diagnosis.** `.env` being newer than a process
start proves the process *may* be running old values — not that the specific knob you care
about changed. It is deliberately over-sensitive: the failure it guards is silent, so a
false alarm costs a re-read and a miss costs a window.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_IST = ZoneInfo("Asia/Kolkata")

#: Substrings that mark a field as a credential. Matched on the FIELD NAME, so a new
#: secret named conventionally is masked without anyone remembering to add it here.
_SECRET_HINTS = ("secret", "password", "passwd", "token", "api_key", "_key", "url", "dsn")

#: The knobs that decide what trades. These lead the report because they are what a person
#: is almost always actually checking.
_RAIL_HINTS = ("gate_mode", "kill_switch", "heat_cap", "notional", "risk_", "capital", "loss")


def _is_secret(name: str) -> bool:
    return any(h in name.lower() for h in _SECRET_HINTS)


def _is_rail(name: str) -> bool:
    return any(h in name.lower() for h in _RAIL_HINTS)


def _fmt(name: str, value: object) -> str:
    if _is_secret(name):
        return "‹set›" if value not in (None, "", 0) else "‹unset›"
    return repr(value)


def _role_of(cmd_low: str, parent_low: str) -> str | None:
    """Which settings-holding role a process is, or None if it holds none.

    ⚠ uvicorn is split deliberately. On `--reload` the PARENT never re-imports config, so
    reading its start time is the classic way to conclude a flip has landed when it has
    not — the child is the process that actually holds the current values.
    """
    if "uvicorn" in cmd_low:
        return (
            "uvicorn (reload CHILD — the one that re-imports)"
            if "uvicorn" in parent_low
            else "uvicorn (parent — does NOT re-import on reload)"
        )
    if "celery" in cmd_low and "worker" in cmd_low:
        return "celery worker"
    if "celery" in cmd_low and "beat" in cmd_low:
        return "celery beat"
    if "live_worker" in cmd_low:
        return "live_worker"
    return None


def _proc_starts() -> list[tuple[str, datetime, str]]:
    """(role, start time, cmd) for the processes that hold a settings singleton.

    ⚠ For uvicorn we want the **--reload CHILD**, not the parent: the parent does not
    re-import config on reload, so reading its start time is the classic way to conclude a
    flip has landed when it has not. Children are identified by having a uvicorn parent.
    """
    try:
        out = subprocess.run(  # noqa: S603
            ["ps", "-eo", "pid,ppid,lstart,cmd", "--no-headers"],  # noqa: S607
            capture_output=True, text=True, timeout=20, check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []

    rows: list[tuple[int, int, datetime, str]] = []
    for line in out.splitlines():
        m = re.match(r"\s*(\d+)\s+(\d+)\s+(\w{3}\s+\w{3}\s+\d+\s+[\d:]+\s+\d{4})\s+(.*)", line)
        if not m:
            continue
        pid, ppid, when, cmd = int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)
        try:
            started = datetime.strptime(when, "%a %b %d %H:%M:%S %Y").astimezone()
        except ValueError:
            continue
        rows.append((pid, ppid, started, cmd))

    by_pid = {r[0]: r for r in rows}
    found: list[tuple[str, datetime, str]] = []
    for _pid, ppid, started, cmd in rows:
        low = cmd.lower()
        if "config_dryrun" in low or "ps -eo" in low:
            continue
        parent_low = by_pid.get(ppid, (0, 0, started, ""))[3].lower()
        role = _role_of(low, parent_low)
        if role is not None:
            found.append((role, started, cmd))
    return found


def main() -> int:  # noqa: C901 — a linear report: load, diff, inspect processes, verdict.
    ap = argparse.ArgumentParser(description="A27 config dry-run")
    ap.add_argument("--gates", action="store_true", help="only the rails and gate modes")
    ap.add_argument("--quiet", action="store_true", help="exit code only")
    args = ap.parse_args()

    from app.core.config import _ENV_FILE, Settings, get_settings

    # A FRESH load, deliberately not `get_settings()` — that one is the cached singleton
    # this whole script exists to distrust. Comparing the two would compare a value to
    # itself.
    fresh = Settings()
    cached = get_settings()

    defaults = {
        name: f.default for name, f in Settings.model_fields.items()
    }
    overridden = {
        name: getattr(fresh, name)
        for name in Settings.model_fields
        if getattr(fresh, name) != defaults.get(name)
    }
    drifted = {
        name: (getattr(cached, name), getattr(fresh, name))
        for name in Settings.model_fields
        if getattr(cached, name) != getattr(fresh, name)
    }

    env_mtime: datetime | None = None
    if _ENV_FILE.exists():
        env_mtime = datetime.fromtimestamp(os.stat(_ENV_FILE).st_mtime, tz=UTC).astimezone()

    procs = _proc_starts()
    stale = [(role, started) for role, started, _cmd in procs
             if env_mtime is not None and started < env_mtime]

    if args.quiet:
        if env_mtime is None:
            return 1  # could not check — distinct from "checked and clean"
        return 2 if stale else 0

    now = datetime.now(UTC).astimezone(_IST)
    print(f"\n═══ config dry-run — {now.isoformat(timespec='seconds')} ═══\n")
    print(f".env: {_ENV_FILE}")
    print(f"  exists: {_ENV_FILE.exists()}")
    if env_mtime:
        print(f"  last modified: {env_mtime.astimezone(_IST).isoformat(timespec='seconds')}")
    print("  ⚠ never read by this script — only stat-ed. Values come via pydantic.\n")

    rails = {k: v for k, v in overridden.items() if _is_rail(k)}
    print(f"── Rails and gate modes overridden by .env ({len(rails)}) ──")
    if not rails:
        print("  (none — every rail is at its code default)")
    for name in sorted(rails):
        print(f"  {name:<38} = {_fmt(name, rails[name])}   (default {defaults.get(name)!r})")

    if not args.gates:
        others = {k: v for k, v in overridden.items() if not _is_rail(k)}
        print(f"\n── Other settings overridden by .env ({len(others)}) ──")
        for name in sorted(others):
            print(f"  {name:<38} = {_fmt(name, others[name])}")

    # "matching" not "unset": this script never reads `.env`, so it cannot tell a knob
    # absent from the file from one set there to the same value the code already uses.
    # Both are safe (the effective value is identical), but claiming "nothing in .env"
    # would be an assertion about a file we deliberately do not open.
    print("\n── Rails MATCHING the code default (absent from .env, or set to the same) ──")
    unset_rails = [
        n for n in Settings.model_fields
        if _is_rail(n) and n not in overridden
    ]
    for name in sorted(unset_rails):
        print(f"  {name:<38} = {_fmt(name, getattr(fresh, name))}")

    if drifted:
        print("\n⛔ THIS PROCESS's cached settings DISAGREE with a fresh load:")
        for name, (was, now_v) in sorted(drifted.items()):
            print(f"  {name}: cached {_fmt(name, was)} vs .env {_fmt(name, now_v)}")
        print("  → this process is holding stale values RIGHT NOW.")

    print(f"\n── Live processes holding a settings singleton ({len(procs)}) ──")
    if not procs:
        print("  (none running — nothing to be stale)")
    for role, started, _cmd in procs:
        mark = "⛔ STALE" if env_mtime and started < env_mtime else "✅ current"
        print(f"  {mark}  {role}")
        print(f"           started {started.astimezone(_IST).isoformat(timespec='seconds')}")

    print("\n── Verdict ──")
    if env_mtime is None:
        # The case where this knows LEAST must not print the same tick as the case where
        # it verified everything.
        print("NO .env FILE at the path this checkout resolves to, so the staleness")
        print("  check could not run at all. Every value above came from the environment")
        print("  or a code default. Normal in an isolated worktree (.env is not copied);")
        print("  a real finding anywhere else.")
        print()
        return 1
    if stale:
        print(f"⛔ {len(stale)} process(es) started BEFORE .env was last modified.")
        print("   They may be running values the file no longer contains. Restart them,")
        print("   or verify the specific knob in the live process before trusting it.")
        print("   ⚠ Over-sensitive by design: .env may have changed a knob you do not care")
        print("   about. The failure this guards is SILENT, so a false alarm is the cheap")
        print("   side of the trade.")
    else:
        print("✅ every running process started after the last .env change.")
    print()
    return 2 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
