"""B8 — writing to the append-only ledger, and exporting it off-box.

⛔ **The two rules this module exists to enforce, both earned by the same incident.**

1. **Append-only.** `record()` INSERTs and nothing here updates or deletes. A correction is a
   new row naming the one it supersedes (`correct()`), and the superseded row stays. A
   mutable audit trail is one `TRUNCATE` away from being no audit trail at all — which is
   precisely what happened on 2026-09-07.
2. ⭐ **Provenance is mandatory, not optional.** Every row must name the code, the spec, the
   experiment and the data version that produced it. §16.1's sample-tag rule — *no formula may
   combine two quantities whose sample tags differ* — has been violated **eight times by five
   authors**, twice by whoever was invoking it, and once in the TIME dimension (§16.1c). Prose
   cannot carry that rule. A NOT NULL column can.

⚠ **The export is the point, not a nicety.** A ledger on the same disk as the database it
describes protects against nothing: the 2026-09-07 loss took the data and would have taken
this with it. `export_day()` writes newline-delimited JSON to a directory the caller chooses,
and the caller is expected to point it somewhere off this machine.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger import ALL_NODE_TYPES, LedgerEntry

#: What a row means when the spec version cannot be determined. Never silently blank:
#: an unknown provenance must be *visible* as unknown, not indistinguishable from a value.
UNKNOWN = "unknown"


@lru_cache(maxsize=1)
def current_commit() -> str:
    """The HEAD commit, or `UNKNOWN`.

    ⚠ Cached for the process lifetime, which is correct: a running process cannot change the
    code it is running. ⚠ Fails to `UNKNOWN` rather than raising — a ledger that refuses to
    record because git is unavailable would be worse than one that records "I don't know",
    and the whole point is that the row gets written.
    """
    try:
        out = subprocess.run(  # noqa: S603
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            capture_output=True, text=True, timeout=5, check=False,
            cwd=Path(__file__).resolve().parents[2],
        )
    except (OSError, subprocess.SubprocessError):
        return UNKNOWN
    return out.stdout.strip()[:40] if out.returncode == 0 else UNKNOWN


class LedgerError(ValueError):
    """A write that would have violated an invariant of the ledger."""


async def record(
    db: AsyncSession,
    *,
    node_type: str,
    chain_id: uuid.UUID,
    as_of: date,
    experiment_id: str,
    data_version: str,
    spec_version: str = UNKNOWN,
    parent_id: uuid.UUID | None = None,
    supersedes_id: uuid.UUID | None = None,
    stock_id: int | None = None,
    user_id: int | None = None,
    label: str | None = None,
    payload: dict[str, Any] | None = None,
) -> LedgerEntry:
    """Append one row. ⛔ There is no update path, by design.

    ⚠ `node_type` is validated against the declared set rather than left free: a typo'd node
    type is a row that no reader will ever find, which is the same as not having written it.
    ⚠ `experiment_id` and `data_version` are REQUIRED arguments with no defaults — making
    either optional would let the sample-tag rule be violated by omission, which is how it was
    violated the previous eight times.
    """
    if node_type not in ALL_NODE_TYPES:
        raise LedgerError(
            f"unknown node_type {node_type!r}; expected one of {ALL_NODE_TYPES}"
        )
    if not experiment_id or not data_version:
        raise LedgerError(
            "experiment_id and data_version are mandatory — a row that cannot name the "
            "sample it belongs to cannot be combined with any other row (§16.1)"
        )
    row = LedgerEntry(
        id=uuid.uuid4(),
        node_type=node_type,
        chain_id=chain_id,
        parent_id=parent_id,
        supersedes_id=supersedes_id,
        code_commit=current_commit(),
        spec_version=spec_version,
        experiment_id=experiment_id,
        data_version=data_version,
        as_of=as_of,
        stock_id=stock_id,
        user_id=user_id,
        label=label,
        payload=payload or {},
    )
    db.add(row)
    await db.flush()
    return row


async def correct(
    db: AsyncSession, original: LedgerEntry, *, payload: dict[str, Any], label: str | None = None
) -> LedgerEntry:
    """Supersede a row with a corrected one. ⛔ The original is NOT touched.

    ⭐ This is the whole append-only contract in one function: a reader walking the chain sees
    both the wrong value and the right one, and can tell which came first and why. Editing in
    place would destroy exactly the information that makes an audit trail an audit trail.
    """
    return await record(
        db,
        node_type=original.node_type,
        chain_id=original.chain_id,
        as_of=original.as_of,
        experiment_id=original.experiment_id,
        data_version=original.data_version,
        spec_version=original.spec_version,
        parent_id=original.parent_id,
        supersedes_id=original.id,
        stock_id=original.stock_id,
        user_id=original.user_id,
        label=label if label is not None else original.label,
        payload=payload,
    )


async def chain(db: AsyncSession, chain_id: uuid.UUID) -> list[LedgerEntry]:
    """Every row of one causal chain, oldest first."""
    rows = await db.execute(
        select(LedgerEntry)
        .where(LedgerEntry.chain_id == chain_id)
        .order_by(LedgerEntry.seq)
    )
    return list(rows.scalars().all())


def _json_default(o: object) -> str:
    if isinstance(o, datetime | date):
        return o.isoformat()
    if isinstance(o, uuid.UUID):
        return str(o)
    return str(o)


async def export_day(db: AsyncSession, day: date, out_dir: str | Path) -> Path:
    """Write one session's rows as newline-delimited JSON. Returns the file path.

    ⚠ **Point `out_dir` OFF THIS MACHINE.** A ledger stored beside the database it describes
    protects against nothing — the 2026-09-07 loss took the data and would have taken this
    with it. The function does not enforce that (it cannot know what is off-box), which is
    why it is said here and in the runbook rather than assumed.

    ⚠ Overwrites the day's file rather than appending: the ledger is the source of truth and
    the export is a projection of it, so a re-export must reproduce, not accumulate.
    """
    rows = await db.execute(
        select(LedgerEntry)
        .where(LedgerEntry.as_of == day)
        .order_by(LedgerEntry.seq)
    )
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"ledger-{day.isoformat()}.jsonl"
    with path.open("w") as fh:
        for r in rows.scalars().all():
            fh.write(json.dumps({
                "id": str(r.id), "node_type": r.node_type,
                "chain_id": str(r.chain_id),
                "parent_id": str(r.parent_id) if r.parent_id else None,
                "supersedes_id": str(r.supersedes_id) if r.supersedes_id else None,
                "code_commit": r.code_commit, "spec_version": r.spec_version,
                "experiment_id": r.experiment_id, "data_version": r.data_version,
                "as_of": r.as_of.isoformat(),
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "stock_id": r.stock_id, "user_id": r.user_id,
                "label": r.label, "payload": r.payload,
            }, default=_json_default) + "\n")
    return path
