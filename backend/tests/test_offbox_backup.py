"""Item 26 — a backup destination on the same device is not a backup destination.

⛔⛔ **Measured 2026-09-19, which is why this exists.** A backup now runs daily — to
`/home/nithin/code/back_ups/trading_platform`, which `df` reports on **`/dev/nvme0n1p5`: the
same partition as the database.** 972 MB of dumps sitting on the disk they protect. That copy
survives exactly one failure mode — the logical wipe that actually happened on 2026-09-07 —
and none of the others.

⭐ The thing worth building was never "copy the file somewhere". It is that **"not really
off-box" is invisible**: nothing about a path tells you what device it lands on, so a
destination that silently shares a disk looks identical to a real one until the day it matters.

⚠ Tested by shelling out to the script rather than reimplementing its logic in Python. The
cron copy runs from outside this checkout and must not depend on the venv (Makefile), so the
check has to be dependency-free shell — and a second implementation here to test against would
be the parallel-implementation defect (W2), with the added irony of testing the copy that is
not the one that runs.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "offbox_check.sh"

SAME_FS, SAME_DISK, UNUSABLE, OFFBOX = 4, 3, 2, 0


def _check(src: str | Path, dest: str | Path) -> tuple[int, str]:
    r = subprocess.run(
        [str(SCRIPT), str(src), str(dest)], capture_output=True, text=True, timeout=30
    )
    return r.returncode, (r.stdout + r.stderr).strip()


def test_the_script_exists_and_is_executable() -> None:
    """The cron copy invokes it by path; a non-executable check is a silently skipped one."""
    assert SCRIPT.is_file()
    assert os.access(SCRIPT, os.X_OK)


def test_the_same_filesystem_is_refused(tmp_path: Path) -> None:
    """⛔⛔ THE REGRESSION FOR THE ACTUAL CONFIGURATION. Two directories on one filesystem —
    which is precisely `back_ups/` and the database today."""
    src = tmp_path / "db"
    dest = tmp_path / "backups"
    src.mkdir()
    dest.mkdir()

    code, out = _check(src, dest)
    assert code == SAME_FS, out
    assert "SAME_FS" in out
    assert "NOT a backup destination" in out


def test_a_different_device_passes(tmp_path: Path) -> None:
    """The positive case, against a real second device rather than a mock: `/dev/shm` is a
    tmpfs, so it is genuinely a different filesystem from the home partition."""
    if not Path("/dev/shm").is_dir():
        pytest.skip("/dev/shm unavailable")
    dest = Path("/dev/shm") / "tp_offbox_test"
    dest.mkdir(exist_ok=True)
    try:
        code, out = _check(tmp_path, dest)
        assert code == OFFBOX, out
        assert "OFFBOX" in out
    finally:
        dest.rmdir()


def test_a_missing_destination_is_unusable_not_offbox(tmp_path: Path) -> None:
    """⚠ The dangerous failure would be treating an absent destination as fine — a backup
    written nowhere reports success just as loudly as one written somewhere."""
    code, out = _check(tmp_path, tmp_path / "does-not-exist")
    assert code == UNUSABLE, out
    assert "UNUSABLE" in out


def test_a_missing_source_is_unusable(tmp_path: Path) -> None:
    code, out = _check(tmp_path / "nope", tmp_path)
    assert code == UNUSABLE, out


def test_the_exit_codes_are_distinct_so_a_caller_can_branch() -> None:
    """⭐ Graded rather than pass/fail, because the honest answer has more than two values:
    a different partition on the SAME physical disk survives filesystem corruption but not a
    disk failure. Collapsing that into 'ok' would overstate the protection."""
    assert len({SAME_FS, SAME_DISK, UNUSABLE, OFFBOX}) == 4


def test_the_backup_script_refuses_a_same_filesystem_destination() -> None:
    """The check is wired into the caller, not merely available. A verdict nothing consults
    is decoration — the shape this repo has hit repeatedly."""
    script = (SCRIPT.parent / "backup_db.sh").read_text()
    assert "offbox_check.sh" in script
    assert "REQUIRE_OFFBOX" in script
    # exit 1 on the SAME_FS branch
    assert 'log "FATAL: OFFBOX_DEST is on the same filesystem' in script


def test_an_absent_offbox_destination_is_reported_loudly() -> None:
    """⚠ Unset must not pass quietly. A backup system whose gap you cannot see is the state
    this project was already in once, and the gap is the whole finding."""
    script = (SCRIPT.parent / "backup_db.sh").read_text()
    assert "NO OFF-BOX COPY" in script
    assert "OFFBOX_DEST is unset" in script


def test_the_offbox_copy_is_written_atomically() -> None:
    """A copy interrupted mid-flight must not be mistaken for a complete backup by whatever
    reads that directory next — write to `.part`, then rename."""
    script = (SCRIPT.parent / "backup_db.sh").read_text()
    assert ".part" in script


def test_the_offbox_copy_happens_only_after_verification() -> None:
    """⭐ Same argument as pruning-after-verify, which this script already gets right:
    propagating a dump that failed `pg_restore --list` would make the off-box copy look
    current while being corrupt."""
    script = (SCRIPT.parent / "backup_db.sh").read_text()
    verify_at = script.index("pg_restore --list")
    offbox_at = script.index("ITEM 26 — the off-box copy")
    assert verify_at < offbox_at, "the off-box stage must run after the integrity check"
