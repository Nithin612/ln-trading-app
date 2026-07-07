"""Walk-forward golden harness (§8 drift gate, Phase 2 slice 8b).

Each committed golden under tests/goldens/walkforward/ pins one ACTIVE
profile's walk-forward: config_hash, run bounds, resolved symbols, fold +
aggregate metrics, and a sha256 trade digest. This suite replays the run
on the DEV database (parity precedent — skips cleanly when the corpus or
the goldens are absent) and demands:

  1. the profile's config_hash still matches the golden (drift guard —
     a profile edit inserts a new version and MUST regenerate its golden);
  2. the rerun trade digest is EXACT;
  3. every fold + aggregate metric is within max(5% rel, 0.05 abs).

Failures print the Δ-table with [§8 APPROVAL REQUIRED] rows; regeneration
goes through scripts/gen_walkforward_goldens.py (dry-run by default,
--write refuses out-of-tolerance moves without --i-have-approval).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from app.backtest.walkforward import (
    WalkForwardReport,
    format_delta_table,
    metric_deltas,
    metrics_dict,
    run_walkforward,
    spec_from_golden,
)
from app.models.profile import StrategyProfile
from sqlalchemy import select, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.parity.test_engine_parity import _dev_db_url

pytestmark = pytest.mark.walkforward

GOLDEN_DIR = Path(__file__).resolve().parent / "walkforward"
GOLDEN_FILES = sorted(GOLDEN_DIR.glob("*.json"))

_NO_GOLDENS = pytest.param(
    None,
    marks=pytest.mark.skip(
        reason="no walkforward goldens committed yet — scripts/gen_walkforward_goldens.py --write"
    ),
    id="no-goldens",
)


async def _with_dev_db(fn: Any) -> Any:
    """Run `fn(db)` on a NullPool dev-DB session; skip cleanly when the
    corpus/schema is absent (fresh clone, CI without the dev DB)."""
    engine = create_async_engine(_dev_db_url(), poolclass=NullPool)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as db:
            try:
                bars = (await db.execute(text("SELECT count(*) FROM ohlcv_1d"))).scalar_one()
                if not bars:
                    pytest.skip("ohlcv_1d empty — run scripts/backfill_eod.py")
                return await fn(db)
            except ProgrammingError:
                pytest.skip("dev DB schema missing — run make migrate")
    finally:
        await engine.dispose()


async def _active_profile(db: Any, key: str) -> StrategyProfile:
    """The golden's live profile row: active OR defined-but-inactive (8c —
    intraday profiles carry goldens before Phase-3 activation). Superseded
    rows are never golden-backed."""
    profile = (
        await db.execute(
            select(StrategyProfile).where(
                StrategyProfile.key == key, StrategyProfile.status != "superseded"
            )
        )
    ).scalar_one_or_none()
    if profile is None:
        pytest.fail(
            f"golden exists for {key!r} but no live profile row — a superseded/"
            f"deleted profile must have its golden removed or regenerated"
        )
    return profile


def _diagnostics(golden: dict[str, Any], report: WalkForwardReport) -> str:
    """Root-cause hints printed under a digest failure."""
    lines: list[str] = []
    old_counts: dict[str, int] = golden["row_counts"]
    for sym in sorted(old_counts.keys() | report.row_counts.keys()):
        a, b = old_counts.get(sym), report.row_counts.get(sym)
        if a != b:
            lines.append(f"  row_count {sym}: {a} → {b}")
    newly_excluded = {e.symbol for e in report.exclusions} & set(golden["symbols"])
    if newly_excluded:
        lines.append(f"  pinned symbols newly excluded: {sorted(newly_excluded)}")
    if golden.get("tradecore_version"):
        import tradecore

        if tradecore.version() != golden["tradecore_version"]:
            lines.append(
                f"  tradecore {golden['tradecore_version']} → {tradecore.version()}"
            )
    if golden["pre_filter_trade_count"] != report.pre_filter_trade_count:
        lines.append(
            f"  pre-gate trade count: {golden['pre_filter_trade_count']} → "
            f"{report.pre_filter_trade_count}"
        )
    return "\n".join(lines) if lines else "  (row counts, exclusions, wheel unchanged)"


@pytest.mark.parametrize(
    "golden_path", GOLDEN_FILES or [_NO_GOLDENS], ids=lambda p: p.stem if p else "none"
)
def test_walkforward_matches_golden(golden_path: Path) -> None:
    golden = json.loads(golden_path.read_text())

    async def _run(db: Any) -> tuple[StrategyProfile, WalkForwardReport]:
        profile = await _active_profile(db, golden["profile"]["key"])
        assert profile.config_hash == golden["config_hash"], (
            f"[§8 APPROVAL REQUIRED] profile {profile.key} v{profile.version} config_hash "
            f"drifted from the golden — regenerate via gen_walkforward_goldens.py "
            f"after user sign-off"
        )
        report = await run_walkforward(db, profile, spec_from_golden(golden), golden["symbols"])
        return profile, report

    _profile, report = asyncio.run(_with_dev_db(_run))

    deltas = metric_deltas(golden["aggregate"], metrics_dict(report.aggregate), "aggregate.")
    golden_folds = {f["fold"]: f["metrics"] for f in golden["folds"]}
    rerun_folds = {fold: metrics_dict(r) for fold, r in report.folds}
    assert set(golden_folds) == set(rerun_folds), (
        f"fold set drifted: {sorted(golden_folds)} vs {sorted(rerun_folds)}"
    )
    for fold in sorted(golden_folds):
        deltas.extend(metric_deltas(golden_folds[fold], rerun_folds[fold], f"{fold}."))

    if report.trades_digest != golden["trades_digest"]:
        pytest.fail(
            f"{golden['profile']['key']}: trade digest drifted from golden\n"
            f"{format_delta_table(deltas)}\n"
            f"diagnostics:\n{_diagnostics(golden, report)}\n"
            f"Out-of-tolerance rows above are [§8 APPROVAL REQUIRED]; regenerate via "
            f"scripts/gen_walkforward_goldens.py only with user sign-off."
        )

    # Digest matched — metrics can still move if the aggregation code drifts.
    bad = [d for d in deltas if not d.within_tolerance]
    assert not bad, (
        f"{golden['profile']['key']}: trades identical but metrics moved "
        f"(aggregation drift?)\n{format_delta_table(deltas)}"
    )


@pytest.mark.skipif(not GOLDEN_FILES, reason="no walkforward goldens committed yet")
def test_every_active_1d_profile_has_a_golden() -> None:
    """Phase-2 exit demands walk-forward evidence per ACTIVE profile — an
    active 1d profile without a committed golden is unevidenced."""

    async def _run(db: Any) -> list[str]:
        rows = (
            (
                await db.execute(
                    select(StrategyProfile.key).where(
                        StrategyProfile.status == "active",
                        StrategyProfile.timeframe == "1d",
                    )
                )
            )
            .scalars()
            .all()
        )
        return list(rows)

    active = asyncio.run(_with_dev_db(_run))
    missing = set(active) - {p.stem for p in GOLDEN_FILES}
    assert not missing, f"active 1d profiles without goldens: {sorted(missing)}"
