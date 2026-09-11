"""B8 — the append-only research/trading ledger. ONE table, five node types.

⛔ **Why this exists, and it is not for this strategy.** `positions` and `orders` are EMPTY —
the dev database was destroyed on 2026-09-07 and there was no backup. That single fact made
ten rounds of live-tape argument unfalsifiable: the human picker's choices, the offered set
they were chosen from, and every realised outcome are **gone and unrecoverable**. Whether the
human adds value over an uninformative sort key is, for all of history, unanswerable
(§18.1). ⭐ **This table is the precondition for any successor programme, and it is the part
of the apparatus that transfers whole.**

⚠ **The E2 result (§12.35) does not change that.** The scorer's unconditional IC is a null, so
*this* strategy is closed as a ranker — but the ledger's value was never conditional on the
strategy working. It is the thing that makes the NEXT question askable.

## ⭐ ONE table, deliberately — with the node type as a discriminated column

The design proposed across rounds 7–10 was five tables
(`DecisionSnapshot → OrderIntent → Execution → PositionLifecycle → PerformanceRecord`) plus
three more for `ExperimentManifest` / `DataSnapshot` / `UniverseSnapshot`. ⛔ **That version
is the one that does not ship.** The base rate is the argument: **one item shipped as code in
the fifty days before this queue started.** A single append-only table with a `node_type`
column carries the same causal chain, is one migration instead of eight, and can be
normalised later by anyone who finds it too coarse — which is a much easier problem than
resurrecting data that was never written.

## The invariants it enforces, each earned by a specific incident

- **`code_commit`** — ⭐ the scorer was verified untouched since its freeze **only because
  git said so** (§18.2 R9). A row that cannot name the code that produced it cannot be
  re-derived by anyone, ever.
- **`spec_version`** — a `SIGNAL_ENGINE.md` change is supposed to force a §8 regression, and
  nothing has ever recorded which spec a given result was computed under.
- **`experiment_id`** — ⭐ **the sample-tag rule, in software.** §16.1 forbids combining two
  quantities whose samples differ, and it has been violated **eight times by five authors**,
  twice by whoever was invoking it. Prose cannot carry that rule; a NOT NULL column can.
- **`data_version`** — ⭐ B4 changed what "gap-clean" means, so `probe-147` became
  `probe-145` mid-programme (§16.1d). Without this, two rows computed either side of that
  change are silently incomparable.
- **`as_of`** — ⭐ the **TIME-dimension** sample-tag rule (§16.1c): a benchmark measured over
  one set of sessions may not be subtracted from a return measured over a different set.
  §12.20a violated it and it cost a published α.
- **`seq`** — ⭐ strictly monotonic insert order, and the chain is walked by it. ⛔ **Not
  `created_at`**: Postgres `now()` is the TRANSACTION timestamp, so every row written inside
  one transaction shares it — and a decision, its order, its fill and its outcome are exactly
  the rows written in one transaction. A ledger that cannot be ordered is not a chain.

## ⛔ Append-only means append-only

There is no `updated_at` and nothing in the application may `UPDATE` or `DELETE` a row. A
correction is a NEW row that references the one it supersedes (`supersedes_id`). ⚠ That is
not fastidiousness: the whole reason this table exists is that the previous record could be
destroyed, and a mutable audit trail is one `TRUNCATE` away from being no audit trail at all.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Identity,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

TZ = DateTime(timezone=True)

#: The five node types of the causal chain, in order. A row is exactly one of them.
NODE_TYPES: tuple[str, ...] = (
    "decision_snapshot",    # what was offered, scored and chosen, and by whom
    "order_intent",         # what we asked for, before any broker saw it
    "execution",            # what actually filled, at what price, with what charges
    "position_lifecycle",   # opens, trails, partial exits, closes
    "performance_record",   # the realised outcome, in every unit
)

#: Experiment/manifest rows describe a RUN rather than a trade. Kept in the same table so a
#: result and the manifest it was produced under cannot drift into separate stores.
MANIFEST_TYPES: tuple[str, ...] = ("experiment_manifest",)

ALL_NODE_TYPES: tuple[str, ...] = NODE_TYPES + MANIFEST_TYPES


class LedgerEntry(Base):
    """One immutable event in the decision → execution → outcome chain.

    ⚠ `payload` is JSONB rather than typed columns **on purpose**: the five node types carry
    genuinely different fields, and a table with the union of them as nullable columns is a
    worse record than a document. The columns that are promoted out of the payload are exactly
    the ones something JOINs or FILTERS on, or that the provenance rules above require.
    """

    __tablename__ = "ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    #: ⭐ STRICTLY MONOTONIC INSERT ORDER, and the chain is walked by THIS.
    #: ⛔ Not `created_at`: Postgres `now()` is the TRANSACTION timestamp, so every row
    #: written inside one transaction shares it to the microsecond — and a decision, its
    #: order, its fill and its outcome are exactly the things written in one transaction.
    #: Ordering by it put `position_lifecycle` before `order_intent` in the first test run,
    #: because the tiebreak fell through to a random UUID. A ledger that cannot be ordered
    #: is not a chain. A sequence depends on no clock and cannot tie.
    seq: Mapped[int] = mapped_column(
        BigInteger, Identity(always=False, start=1, increment=1),
        nullable=False, unique=True,
    )
    #: One of ALL_NODE_TYPES. Not an enum type: adding a node type must not need a migration.
    node_type: Mapped[str] = mapped_column(String(32), nullable=False)

    # ── the causal chain ──────────────────────────────────────────────────────────
    #: Ties every node of one trade together. Assigned at the decision_snapshot.
    chain_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    #: The row this one directly follows, if any — so the chain is walkable both ways.
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    #: ⛔ Corrections are NEW ROWS. This names the row being superseded; the old row stays.
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # ── provenance: the sample-tag rule, in software ──────────────────────────────
    code_commit: Mapped[str] = mapped_column(String(40), nullable=False)
    spec_version: Mapped[str] = mapped_column(String(32), nullable=False)
    experiment_id: Mapped[str] = mapped_column(String(64), nullable=False)
    data_version: Mapped[str] = mapped_column(String(64), nullable=False)

    # ── time: two axes, and they are NOT the same axis ────────────────────────────
    #: The MARKET date this row is about — the session a decision or fill belongs to.
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    #: When the row was written, on the wall clock. ⚠ Descriptive only — `seq` is the
    #: ordering key (see above).
    created_at: Mapped[datetime] = mapped_column(
        TZ, nullable=False, server_default=func.now()
    )

    # ── what it is about ──────────────────────────────────────────────────────────
    stock_id: Mapped[int | None] = mapped_column(nullable=True)
    user_id: Mapped[int | None] = mapped_column(nullable=True)
    #: Free-text label for the run/decision, for humans reading the table directly.
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    __table_args__ = (
        # Walking one trade's chain in order is THE access pattern.
        Index("ix_ledger_chain", "chain_id", "seq"),
        # "what happened on this session" and "what did experiment X produce".
        Index("ix_ledger_as_of", "as_of", "node_type"),
        Index("ix_ledger_experiment", "experiment_id", "seq"),
    )
