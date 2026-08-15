"""Pair attribution (Phase 6.5b slice 4) — shadow pair expectancy, the df-vs-adf verdict."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from app.models.pair import PairSignal
from app.services.pair_attribution import (
    PairAttribution,
    PairRow,
    attribute_pair_rows,
    compute_pair_attribution,
    render_markdown,
)
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock

_VALID = datetime(2025, 3, 1, tzinfo=UTC)


def _arm(rows: list[PairRow]):
    return next(t for t in attribute_pair_rows(rows) if t.dimension.startswith("Arm"))


def test_attribute_splits_by_arm_with_correct_metrics() -> None:
    rows = [
        PairRow("df", "IT", 8.0, "tp_first", 2.0),
        PairRow("df", "IT", 12.0, "sl_first", -1.0),
        PairRow("adf", "IT", 15.0, "tp_first", 1.5),
        PairRow("adf", "Healthcare", 18.0, "expired", 0.5),  # marked, not decided
    ]
    arm = _arm(rows)
    df = next(c for c in arm.cells if c.key == "df")
    assert df.n == 2 and df.decided == 2 and df.wins == 1 and df.win_rate == 0.5
    assert abs(df.mean_r - 0.5) < 1e-9  # (2 + −1)/2
    adf = next(c for c in arm.cells if c.key == "adf")
    assert adf.n == 2 and adf.decided == 1 and adf.wins == 1  # expired excluded from decided
    assert adf.win_rate == 1.0
    assert abs(adf.mean_r - 1.0) < 1e-9  # (1.5 + 0.5)/2 over all resolved (expired marked-to-z)


def test_winsorizes_outsized_r() -> None:
    df = next(c for c in _arm([PairRow("df", "IT", 8.0, "tp_first", 50.0)]).cells if c.key == "df")
    assert df.mean_r == 10.0  # tiny-risk outsized R capped at the ±10 winsor bound


def test_cell_below_rank_floor_is_flagged_unranked() -> None:
    df = next(c for c in _arm([PairRow("df", "IT", 8.0, "tp_first", 1.0)]).cells if c.key == "df")
    assert df.ranked is False  # n=1 < RANK_FLOOR


async def test_compute_excludes_open_signals(db: AsyncSession) -> None:
    a = await make_stock(db, symbol="ATA")
    b = await make_stock(db, symbol="ATB")

    def mk(method: str, status: str, r: float | None) -> PairSignal:
        return PairSignal(
            stock_a_id=a.id,
            stock_b_id=b.id,
            method=method,
            beta=1.0,
            alpha=0.0,
            half_life=10.0,
            df_tstat=-3.5,
            direction="long_spread",
            entry_z=-2.5,
            z_exit=0.0,
            z_stop=-3.5,
            spread_entry=Decimal("-2.5"),
            spread_sigma=Decimal("1.0"),
            validity_until=_VALID,
            status=status,
            outcome_r=(Decimal(str(r)) if r is not None else None),
        )

    db.add(mk("df", "tp_first", 2.0))
    db.add(mk("adf", "sl_first", -1.0))
    db.add(mk("df", "open", None))  # excluded
    await db.commit()

    attr = await compute_pair_attribution(db)
    assert attr.total == 2
    arm = next(t for t in attr.tables if t.dimension.startswith("Arm"))
    assert {c.key for c in arm.cells} == {"df", "adf"}


def test_render_empty_and_populated() -> None:
    empty = render_markdown(PairAttribution(since=None, total=0, tables=[]), day=date(2026, 8, 15))
    assert "No resolved" in empty
    rows = [PairRow("df", "IT", 8.0, "tp_first", 2.0), PairRow("adf", "IT", 10.0, "sl_first", -1.0)]
    md = render_markdown(
        PairAttribution(since=None, total=2, tables=attribute_pair_rows(rows)),
        day=date(2026, 8, 15),
    )
    assert "Arm (df vs adf)" in md and "df" in md
