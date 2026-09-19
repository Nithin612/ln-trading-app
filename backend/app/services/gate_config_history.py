"""Queue item 22 — record the gate configuration whenever it changes, and look it up later.

See `app/models/gate_config.py` for why this exists. In one line: **no signal in the database
can currently be attributed to the configuration that produced it**, and two gates have already
been promoted and reverted, so the windows where that matters are not hypothetical.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import fields
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gate_config import GateConfigVersion
from app.services.ledger import current_commit
from app.signals import restrictions


def _plain(value: Any) -> Any:
    """JSON-safe, and Decimals as STRINGS.

    ⛔ Never `float(Decimal)`. A threshold that round-trips through binary floating point can
    hash differently on two machines that hold the identical configuration, which would make
    the dedup emit spurious "changes" — the failure mode that gets a history table ignored.
    """
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in sorted(value.items())}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    return value


def snapshot(cfg: restrictions.RestrictionConfig) -> dict[str, Any]:
    """The complete tradability configuration: WHICH rules exist, and how they are set.

    ⭐ Both halves. A modes-only snapshot cannot express "this rule did not exist yet", and
    two rules have been ADDED since signals started being minted (`universe_membership`,
    `settlement`) — so a signal from before either came from a different rule SET, which a
    mode map renders invisible.

    ⚠ Read from `REGISTRY` and the composed `RestrictionConfig` rather than from a
    hand-maintained list (W2). A list that has to be updated by hand when a gate is added is a
    list that will disagree with the registry the first time someone forgets.
    """
    return {
        "rules": [
            {
                "gate": r.gate,
                "order": i,
                "always_on": r.always_on,
                "enforced_by": r.enforced_by.value,
                "requires": sorted(r.requires),
            }
            for i, r in enumerate(restrictions.REGISTRY)
        ],
        "config": {
            f.name: _plain(getattr(cfg, f.name))
            for f in fields(cfg)
        },
    }


def config_hash(snap: dict[str, Any]) -> str:
    """sha256 over the canonical JSON. Deterministic: sorted keys, no whitespace drift."""
    return hashlib.sha256(
        json.dumps(snap, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


async def record_current(
    db: AsyncSession, cfg: restrictions.RestrictionConfig | None = None
) -> GateConfigVersion:
    """Record the effective configuration if it is new; otherwise return the existing row.

    ⭐ Idempotent by content. Called on every generation run, it writes only when something
    actually changed — so the table IS the change history rather than a log of runs.

    ⚠ Does NOT commit. The caller owns the transaction, and a config row written by a run that
    then rolled back would claim a configuration was in force when nothing was produced under
    it.
    """
    cfg = cfg if cfg is not None else restrictions.config_from_settings()
    snap = snapshot(cfg)
    digest = config_hash(snap)

    existing = (
        await db.execute(
            select(GateConfigVersion).where(GateConfigVersion.config_hash == digest)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    row = GateConfigVersion(config_hash=digest, config=snap, code_commit=current_commit())
    db.add(row)
    await db.flush()
    return row


async def version_as_of(db: AsyncSession, when: datetime) -> GateConfigVersion | None:
    """The configuration in force at `when` — the latest recorded at or before it.

    ⚠ `None` means the history does not reach back that far, which is the honest answer for
    every signal minted before this table existed. It is NOT "the current config": presenting
    today's settings as the ones that produced a 2026-08 signal is precisely the fabrication
    this table exists to prevent.
    """
    return (
        await db.execute(
            select(GateConfigVersion)
            .where(GateConfigVersion.recorded_at <= when)
            .order_by(GateConfigVersion.recorded_at.desc(), GateConfigVersion.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


def diff(older: dict[str, Any], newer: dict[str, Any]) -> dict[str, Any]:
    """What changed between two snapshots — modes, thresholds and the rule set itself.

    ⭐ Rule membership is reported separately from mode changes because they are different
    events: a gate flipped from shadow to active is a decision, a gate appearing for the first
    time is a deployment.
    """
    old_rules = {r["gate"] for r in older.get("rules", [])}
    new_rules = {r["gate"] for r in newer.get("rules", [])}
    o_cfg, n_cfg = older.get("config", {}), newer.get("config", {})
    o_modes = o_cfg.get("modes", {}) or {}
    n_modes = n_cfg.get("modes", {}) or {}

    return {
        "rules_added": sorted(new_rules - old_rules),
        "rules_removed": sorted(old_rules - new_rules),
        "modes_changed": {
            k: [o_modes.get(k), n_modes.get(k)]
            for k in sorted(set(o_modes) | set(n_modes))
            if o_modes.get(k) != n_modes.get(k)
        },
        "thresholds_changed": {
            k: [o_cfg.get(k), n_cfg.get(k)]
            for k in sorted(set(o_cfg) | set(n_cfg))
            if k != "modes" and o_cfg.get(k) != n_cfg.get(k)
        },
    }
