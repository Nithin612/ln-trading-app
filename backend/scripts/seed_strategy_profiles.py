"""Queue item 3 — re-seed `strategy_profiles` idempotently, from the migrations that own the data.

## ⛔⛔ The defect

`strategy_profiles` holds **0 rows at head**, and has since the 2026-09-07 rebuild. The eight v1
profiles were seeded by migration `o1p2q3r4s5t6`; the rebuild restored the schema with alembic
*already marked applied*, so the seed never re-ran **and cannot** — `alembic upgrade` is a no-op on
a revision it thinks is done. Four consumers (`profiles/pipeline`, `broker/provisional`,
`api/v1/suggestions`, `daily_report`) have been structurally unable to produce anything since, at
head, with a green suite.

⭐ **The lesson is structural, and it is why this script exists rather than another migration: a
migration that seeds reference data is invisible to every check we own once it is marked applied.**
Reference data needs a re-runnable owner. Schema changes are one-shot; the rows are not.

## ⭐ TEN profiles, not eight

Two migrations seed this table, and only one of them was ever named in the review:

- `o1p2q3r4s5t6_phase2_profile_seeds` — the **8** v1 profiles (dc1, dc2, rrbo_basic,
  rrbo_trailing, multibagger, orb_15m, pdh_pdl, gainer_925)
- `d2e3f4a5b6c7_retune_shadow_profiles` — **2** more (`retune_base`, `retune_momentum_x15`)

⚠ Restoring only the eight would leave the **momentum-retune shadow arm dead** — one of the
forward-evidence loops `docs/PHASES.md` still lists as open. It cannot resolve anything while its
profiles do not exist.

## Why it loads the migrations instead of copying their data

The seed literals live in the migration files and they stay there (**W2** — one owner). Those files
must never import app code (their own docstring says so, for import-free replay), so the dependency
runs the other way: this script loads each migration module **by path** and reuses its `SEEDS` and
its `_INSERT` statement verbatim, appending `ON CONFLICT DO NOTHING` for idempotency. Nothing about
a profile is restated here, so the two can never disagree.

    uv run python scripts/seed_strategy_profiles.py --check    # report, write nothing
    uv run python scripts/seed_strategy_profiles.py            # insert what is missing
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402

_VERSIONS = Path(__file__).resolve().parent.parent / "alembic" / "versions"

# ⚠ Every migration that seeds `strategy_profiles`. `tests/test_seed_migrations.py` fails if a new
# one appears and is not listed here — which is the guard that makes the 09-07 outage unrepeatable.
SEEDING_MIGRATIONS = (
    "o1p2q3r4s5t6_phase2_profile_seeds",
    "d2e3f4a5b6c7_retune_shadow_profiles",
)


@dataclass
class SeedReport:
    present: list[str] = field(default_factory=list)
    inserted: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.present) + len(self.inserted)

    def lines(self) -> list[str]:
        out = [
            f"strategy_profiles: {self.total} seeds declared across "
            f"{len(SEEDING_MIGRATIONS)} migrations",
            f"  already present : {len(self.present)}  {sorted(self.present)}",
            f"  inserted now    : {len(self.inserted)}  {sorted(self.inserted)}",
        ]
        if not self.inserted:
            out.append("  nothing to do — idempotent, safe to re-run")
        return out


def load_migration(name: str) -> ModuleType:
    """Import a migration module by PATH — `alembic/versions` is not an importable package."""
    path = _VERSIONS / f"{name}.py"
    if not path.exists():
        raise FileNotFoundError(f"{path} — a seeding migration was renamed or removed")
    spec = importlib.util.spec_from_file_location(f"_seedsrc_{name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def declared_seeds() -> list[tuple[str, dict[str, Any], str, str, str]]:
    """(migration, config, config_hash, status, insert_sql) for every declared profile."""
    out: list[tuple[str, dict[str, Any], str, str, str]] = []
    for name in SEEDING_MIGRATIONS:
        mod = load_migration(name)
        insert_sql = str(mod._INSERT)  # noqa: SLF001 — reusing the migration's own statement
        for config, config_hash, status in mod.SEEDS:
            out.append((name, config, config_hash, status, insert_sql))
    return out


async def reseed(db: AsyncSession, *, dry_run: bool = False) -> SeedReport:
    """Insert every declared profile that is missing. Existing rows are never modified."""
    report = SeedReport()
    existing = {
        r[0]
        for r in (
            await db.execute(text("SELECT key FROM strategy_profiles WHERE version = 1"))
        ).all()
    }

    for _name, config, config_hash, status, insert_sql in declared_seeds():
        key = config["key"]
        if key in existing:
            report.present.append(key)
            continue
        report.inserted.append(key)
        if dry_run:
            continue
        # The migration's own INSERT, made idempotent. Nothing about the row is restated here.
        await db.execute(
            text(f"{insert_sql} ON CONFLICT (key, version) DO NOTHING"),
            {
                "key": key,
                "name": config["name"],
                "description": config["description"],
                "style": config["style"],
                "timeframe": config["timeframe"],
                "schedule": config["schedule"],
                "universe_spec": json.dumps(config["universe_spec"]),
                "setup_conditions": json.dumps(config["setup_conditions"]),
                "weight_multipliers": json.dumps(config["weight_multipliers"]),
                "min_confidence": config["min_confidence"],
                "risk_template": json.dumps(config["risk_template"]),
                "validity_spec": json.dumps(config["validity_spec"]),
                "status": status,
                "config_hash": config_hash,
            },
        )
    return report


async def _main(dry_run: bool) -> int:
    async with AsyncSessionFactory() as db:
        report = await reseed(db, dry_run=dry_run)
        if not dry_run:
            await db.commit()
    for line in report.lines():
        print(line)
    if dry_run and report.inserted:
        print("\n  --check only: nothing was written. Re-run without --check to insert.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="report what is missing, write nothing")
    return asyncio.run(_main(ap.parse_args().check))


if __name__ == "__main__":
    raise SystemExit(main())
