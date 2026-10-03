"""scripts/timebox.sh under a REAL terminal (2026-10-03).

The canary: `make replay` timed out at 300 s in the author's terminal while passing in 19 s in
every non-interactive run. `timeout` (without --foreground) runs its command in a BACKGROUND
process group, and a background process that reads the TTY is frozen by SIGTTIN — state `T`,
until the bound kills it. `uv run pytest` reads stdin, so every pytest leg of `make check` froze.
These tests drive the script through `script(1)`, which gives it a real pseudo-terminal — a
non-TTY test would pass on the broken version too, which is how the bug shipped.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

TIMEBOX = Path(__file__).resolve().parents[2] / "scripts" / "timebox.sh"

pytestmark = pytest.mark.skipif(shutil.which("script") is None, reason="needs script(1) for a pty")


def _in_pty(cmd: str, limit: float) -> tuple[int, float, str]:
    start = time.monotonic()
    try:
        p = subprocess.run(
            ["script", "-qec", cmd, "/dev/null"],
            capture_output=True, text=True, timeout=limit,
        )
    except subprocess.TimeoutExpired:
        return -1, time.monotonic() - start, ""
    return p.returncode, time.monotonic() - start, p.stdout


def test_a_leg_that_reads_stdin_is_not_frozen_in_a_terminal() -> None:
    reader = f"{sys.executable} -c 'import sys; sys.stdin.read(1); print(\"read-done\")'"
    rc, secs, out = _in_pty(f"{TIMEBOX} t 20 1 -- {reader}", limit=15)
    assert rc == 0, f"frozen or failed (rc={rc}, {secs:.1f}s) — SIGTTIN regression?"
    assert "read-done" in out
    assert secs < 10


def test_the_bound_still_kills_a_hung_child_in_a_terminal() -> None:
    sleeper = f"{sys.executable} -c 'import time; time.sleep(60)'"
    rc, secs, out = _in_pty(f"{TIMEBOX} hang 2 1 -- {sleeper}", limit=40)
    assert rc == 124
    assert secs < 30
    assert "exceeded 2s" in out
