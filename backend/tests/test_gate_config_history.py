"""Queue item 22 — the gate configuration, versioned.

⛔⛔ **The measured gap:** of 57 tables, the only one matching `%config%`/`%setting%`/`%gate%`
was `alembic_version`, and `signals` had no column referencing a config. **No signal could be
attributed to the configuration that produced it** — while the regime gate had run active for
19 days and the R:R floor for one, both since reverted. Those windows are currently
reconstructible only from CHANGELOG prose plus process-restart times.

⭐ The property that most needs a test is the one a modes-only design would have missed: the
snapshot must show that a RULE DID NOT EXIST YET. Two rules have been added since signals
started being minted.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.services.gate_config_history import (
    config_hash,
    diff,
    record_current,
    snapshot,
    version_as_of,
)
from app.signals import restrictions
from sqlalchemy.ext.asyncio import AsyncSession


def _cfg(**over: object) -> restrictions.RestrictionConfig:
    base = dict(
        modes=dict.fromkeys(restrictions.MODED_GATES, "off"),
        min_scoring_factors=2,
        max_dominant_share=Decimal("0.9"),
        min_sl_atr_mult=Decimal("1.0"),
        rr_min=Decimal("1.0"),
        max_chase_r=Decimal("0.33"),
        circuit_proximity_pct=Decimal("1.5"),
        sector_rs_lookback=20,
        sector_rs_min_excess_pct=Decimal("0"),
        market_regime_dma_period=200,
        market_regime_dma_buffer_pct=Decimal("0"),
        market_regime_vix_threshold=Decimal("20"),
        market_regime_market_symbol="NIFTY50",
        liquidity_lookback=20,
        liquidity_min_traded_value=Decimal("0"),
    )
    base.update(over)
    return restrictions.RestrictionConfig(**base)  # type: ignore[arg-type]


# ── The snapshot ─────────────────────────────────────────────────────────────

def test_the_snapshot_records_which_rules_exist_not_only_their_modes() -> None:
    """⭐⭐ The property a modes-only design cannot express. `settlement` shipped 2026-09-19
    and `universe_membership` in PART XXI — a signal from before either was produced by a
    different rule SET, and a mode map renders that invisible."""
    snap = snapshot(_cfg())
    gates = [r["gate"] for r in snap["rules"]]

    assert restrictions.GATE_SETTLEMENT in gates
    assert restrictions.GATE_QUARANTINE in gates
    assert len(gates) == len(restrictions.REGISTRY)
    # always_on rules have no mode at all, so a modes-only snapshot would omit them entirely
    assert any(r["always_on"] for r in snap["rules"])
    assert restrictions.GATE_SETTLEMENT not in snap["config"]["modes"]


def test_the_snapshot_preserves_registry_order() -> None:
    """Order is a user-facing contract — it decides which reason a user sees first — so a
    reordering is a configuration change and must hash differently."""
    snap = snapshot(_cfg())
    assert [r["order"] for r in snap["rules"]] == list(range(len(restrictions.REGISTRY)))
    assert snap["rules"][0]["gate"] == restrictions.REGISTRY[0].gate


def test_decimals_are_strings_never_floats() -> None:
    """⛔ `float(Decimal)` would let two machines holding the IDENTICAL configuration hash
    differently, which makes the dedup emit spurious changes — the failure that gets a history
    table ignored."""
    snap = snapshot(_cfg())
    assert snap["config"]["rr_min"] == "1.0"
    assert isinstance(snap["config"]["max_dominant_share"], str)


# ── The hash ─────────────────────────────────────────────────────────────────

def test_the_same_config_hashes_the_same_and_a_changed_one_does_not() -> None:
    a = config_hash(snapshot(_cfg()))
    again = config_hash(snapshot(_cfg()))
    flipped = config_hash(
        snapshot(_cfg(modes={**dict.fromkeys(restrictions.MODED_GATES, "off"),
                             restrictions.GATE_RR: "active"}))
    )
    threshold = config_hash(snapshot(_cfg(rr_min=Decimal("1.5"))))

    assert a == again
    assert a != flipped, "a mode flip must produce a new version"
    assert a != threshold, "a threshold change must produce a new version"


# ── Recording ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_recording_is_idempotent_by_content(db: AsyncSession) -> None:
    """⭐ Called on every generation run, it must write only on an actual change — otherwise
    the table buries the handful of moments that matter under thousands of identical rows."""
    first = await record_current(db, _cfg())
    second = await record_current(db, _cfg())

    assert first.id == second.id
    assert first.code_commit, "a config with no commit cannot be re-derived"


@pytest.mark.asyncio
async def test_a_changed_config_records_a_new_version(db: AsyncSession) -> None:
    first = await record_current(db, _cfg())
    changed = await record_current(
        db,
        _cfg(modes={**dict.fromkeys(restrictions.MODED_GATES, "off"),
                    restrictions.GATE_RR: "active"}),
    )

    assert changed.id != first.id
    assert changed.config_hash != first.config_hash


# ── Attribution ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_attribution_returns_the_version_in_force_at_that_time(db: AsyncSession) -> None:
    row = await record_current(db, _cfg())
    await db.flush()

    found = await version_as_of(db, datetime.now(tz=UTC) + timedelta(minutes=1))
    assert found is not None and found.id == row.id


@pytest.mark.asyncio
async def test_before_the_history_begins_the_answer_is_none_not_todays_config(
    db: AsyncSession,
) -> None:
    """⛔⛔ The whole point. Presenting today's settings as the ones that produced a 2026-08
    signal is exactly the fabrication this table exists to prevent — so a question the history
    cannot answer returns None, never a plausible-looking default."""
    await record_current(db, _cfg())
    await db.flush()

    assert await version_as_of(db, datetime(2026, 8, 1, tzinfo=UTC)) is None


# ── The diff ─────────────────────────────────────────────────────────────────

def test_diff_separates_a_rule_appearing_from_a_mode_being_flipped() -> None:
    """⭐ Different events: a gate flipped shadow→active is a DECISION; a gate appearing for
    the first time is a DEPLOYMENT. Collapsing them would hide which one happened."""
    old = snapshot(_cfg())
    old["rules"] = [r for r in old["rules"] if r["gate"] != restrictions.GATE_SETTLEMENT]
    new = snapshot(
        _cfg(modes={**dict.fromkeys(restrictions.MODED_GATES, "off"),
                    restrictions.GATE_RR: "active"})
    )

    d = diff(old, new)
    assert d["rules_added"] == [restrictions.GATE_SETTLEMENT]
    assert d["modes_changed"] == {restrictions.GATE_RR: ["off", "active"]}
    assert d["rules_removed"] == []


def test_diff_reports_threshold_changes_separately_from_modes() -> None:
    d = diff(snapshot(_cfg()), snapshot(_cfg(rr_min=Decimal("1.5"))))
    assert d["modes_changed"] == {}
    assert d["thresholds_changed"] == {"rr_min": ["1.0", "1.5"]}
