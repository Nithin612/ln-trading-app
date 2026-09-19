"""Queue item 22 — the gate configuration, versioned.

⛔⛔ **Measured before building (M80, re-confirmed 2026-09-19): of 57 tables, the only one
matching `%config%` / `%setting%` / `%gate%` / `%version%` is `alembic_version`, and `signals`
carries no column referencing a config, gate or mode.** So **no signal in the database can be
attributed to the configuration that produced it.**

⚠ **Why that is not academic here.** Gate modes live in `.env`, read through an `@lru_cache`
settings singleton, so a flip is an untracked file edit plus a process restart. **Two gates
have already been promoted and reverted** — the regime gate (active 2026-08-14, reverted
2026-09-02 after 19 days) and the R:R≥1 floor (active 2026-09-02, reverted 09-03). Every
signal minted in those windows was produced under a configuration that is now recoverable only
by reading CHANGELOG prose and correlating it with process restart times. That is the recipe
the mode-verification section of CLAUDE.md exists to describe — and it is a recipe, not a
record.

## ⭐ What is snapshotted, and why it is more than the modes

The obvious design records the ten `*_gate_mode` settings. That is not enough: **it cannot
show that a RULE did not exist yet.** `settlement` shipped 2026-09-19 and `universe_membership`
in PART XXI — a signal from before either was produced by a different rule SET, not merely a
different mode map, and a modes-only snapshot renders the two indistinguishable.

So the snapshot is taken from `restrictions.REGISTRY` and `RestrictionConfig` together — the
composed objects the order path actually walks (W2: not a hand-maintained list that can drift
from the thing it describes).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GateConfigVersion(Base):
    """One distinct tradability configuration, recorded the first time it is seen.

    ⭐ **Append-only and deduplicated by content hash.** Recording every generation run would
    write thousands of identical rows and bury the handful of moments that matter; recording
    only on change means the table IS the history of changes. A run that finds its hash already
    present writes nothing.

    ⚠ **Attribution is by TIME, not by foreign key.** A signal at `t` was produced under the
    latest version whose `recorded_at <= t`. That is weaker than a column on `signals` and it
    is deliberate for now: the FK needs a migration on a large hot table plus a backfill that
    would be *invented* for every existing row, since the information does not exist. An
    honest gap beats a fabricated column.
    """

    __tablename__ = "gate_config_versions"
    __table_args__ = (
        Index("ix_gate_config_versions_recorded_at", "recorded_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    #: When this configuration was FIRST observed. ⚠ Not when it was changed — nothing
    #: observes `.env`. It is a lower bound on the change, and the gap is the interval between
    #: the change and the next generation run.
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    #: sha256 over the canonical JSON. UNIQUE — this is what makes recording idempotent.
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    #: The full snapshot: the rule registry (ids, always_on, enforced_by, order) AND the
    #: moded config and thresholds. Both halves, because either alone is ambiguous.
    config: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)

    #: ⭐ The code that produced it. A mode map means nothing without the rules it indexes,
    #: and those live in code — same argument as `ledger_entries.code_commit`.
    code_commit: Mapped[str] = mapped_column(String(40), nullable=False)
