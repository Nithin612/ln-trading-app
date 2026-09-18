"""Queue item 3 — the seed-bearing migration census, and the idempotent re-seed.

⭐ **The structural lesson this file encodes:** a migration that seeds reference data is invisible
to every check we own once alembic marks it applied. `strategy_profiles` held **0 rows at head**
for eleven days, with four dead consumers and a green suite, and nothing in the repository could
have told you. `test_no_unregistered_seed_bearing_migration` is the ratchet that fixes that: add a
migration that INSERTs rows and the suite fails until you say, in `SEED_BEARING`, what re-seeds it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from scripts.seed_strategy_profiles import (
    SEEDING_MIGRATIONS,
    declared_seeds,
    load_migration,
    reseed,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_VERSIONS = Path(__file__).resolve().parent.parent / "alembic" / "versions"

# ⚠ THE REGISTRY. Every migration that writes rows, and what re-seeds it if the DB is rebuilt with
# the revision already marked applied. A new entry here is a deliberate act; an unregistered one
# fails the suite.
SEED_BEARING: dict[str, str] = {
    "o1p2q3r4s5t6_phase2_profile_seeds": (
        "strategy_profiles — the 8 v1 profiles. Re-seedable: scripts/seed_strategy_profiles.py"
    ),
    "d2e3f4a5b6c7_retune_shadow_profiles": (
        "strategy_profiles — retune_base + retune_momentum_x15, the momentum-retune shadow arm. "
        "Re-seedable by the same script. ⚠ Restoring only the other migration leaves this arm "
        "dead, and it is a forward-evidence loop PHASES still lists as open."
    ),
    "c3d4e5f6a7b8_u8_index_registry": (
        "indices — the index registry. Populated (27 rows, measured 2026-09-18): this migration is "
        "HEAD and ran after the 09-07 rebuild, so its seed was not skipped. Would need the same "
        "treatment if the DB is ever rebuilt past it."
    ),
    "c1d2e3f4a5b6_ca_flag_events": (
        "ca_flag_events — EVENT data, not reference data. Not re-seedable by design; it records "
        "what was observed, and an empty table is a true statement about history."
    ),
}


def _migrations_that_insert() -> set[str]:
    found = set()
    for path in sorted(_VERSIONS.glob("*.py")):
        if re.search(r"INSERT\s+INTO", path.read_text(), re.IGNORECASE):
            found.add(path.stem)
    return found


def test_the_scan_actually_found_migrations() -> None:
    """The canary. A changed directory layout would make every assertion below vacuously true —
    the failure mode `apiWiring.test.ts` was written to catch, in a different layer."""
    assert len(list(_VERSIONS.glob("*.py"))) > 30
    assert _migrations_that_insert(), "scanned the migrations and found no INSERTs at all"


def test_no_unregistered_seed_bearing_migration() -> None:
    """⭐ The ratchet. Add a migration that seeds rows and this fails until SEED_BEARING says how
    the data comes back after a rebuild."""
    assert _migrations_that_insert() == set(SEED_BEARING), (
        "a migration seeds data and is not in SEED_BEARING (or a registered one no longer "
        "seeds). Record what re-seeds it — an unregistered seeder is exactly how "
        "strategy_profiles sat empty at head for eleven days."
    )


def test_every_registered_reason_is_a_real_reason() -> None:
    for name, reason in SEED_BEARING.items():
        assert len(reason) > 40, f"{name}: say what re-seeds it, not just that it seeds"


def test_both_profile_seeders_load_and_declare_seeds() -> None:
    for name in SEEDING_MIGRATIONS:
        mod = load_migration(name)
        assert mod.SEEDS, f"{name} declares no SEEDS"
        assert str(mod._INSERT).lstrip().upper().startswith("INSERT INTO STRATEGY_PROFILES")


def test_ten_profiles_are_declared_not_eight() -> None:
    """⭐ The finding that made this script correct: TWO migrations seed this table. Restoring
    only the Phase-2 eight leaves the momentum-retune shadow arm dead."""
    keys = {config["key"] for _m, config, _h, _s, _sql in declared_seeds()}

    assert len(keys) == 10, sorted(keys)
    assert {"retune_base", "retune_momentum_x15"} <= keys
    assert {"dc1", "dc2", "multibagger", "orb_15m", "pdh_pdl", "gainer_925"} <= keys


@pytest.mark.asyncio
async def test_reseed_fills_an_empty_table(db: AsyncSession) -> None:
    """`clean_tables` truncates every ORM table per test, so this starts from exactly the state
    the dev DB has been in since 2026-09-07."""
    before = (await db.execute(text("SELECT count(*) FROM strategy_profiles"))).scalar_one()
    assert before == 0

    report = await reseed(db)

    assert len(report.inserted) == 10
    assert report.present == []
    after = (await db.execute(text("SELECT count(*) FROM strategy_profiles"))).scalar_one()
    assert after == 10


@pytest.mark.asyncio
async def test_reseed_is_idempotent(db: AsyncSession) -> None:
    """The property the migration could not have: running it again is a no-op."""
    await reseed(db)

    second = await reseed(db)

    assert second.inserted == [], "a re-run inserted duplicates"
    assert len(second.present) == 10
    assert (
        await db.execute(text("SELECT count(*) FROM strategy_profiles"))
    ).scalar_one() == 10


@pytest.mark.asyncio
async def test_check_mode_writes_nothing(db: AsyncSession) -> None:
    report = await reseed(db, dry_run=True)

    assert len(report.inserted) == 10, "dry run should still REPORT what is missing"
    assert (
        await db.execute(text("SELECT count(*) FROM strategy_profiles"))
    ).scalar_one() == 0, "dry run wrote rows"


@pytest.mark.asyncio
async def test_reseed_does_not_overwrite_an_existing_row(db: AsyncSession) -> None:
    """Reference data is restored, never restated: a profile someone has edited stays edited."""
    await reseed(db)
    await db.execute(
        text("UPDATE strategy_profiles SET status = 'superseded' WHERE key = 'dc1'")
    )

    await reseed(db)

    status = (
        await db.execute(text("SELECT status FROM strategy_profiles WHERE key = 'dc1'"))
    ).scalar_one()
    assert status == "superseded", "the re-seed clobbered a row that already existed"
