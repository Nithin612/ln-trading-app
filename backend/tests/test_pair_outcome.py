"""Spread-outcome tracker (Phase 6.5b slice 3) — resolve open pair signals from the tape.

`resolve_spread` is pure; with β=1, α=0, σ=1 and b≡100 the spread A−B equals the z, so the
forward closes ARE the z-path — making the win/loss/expire logic exact and readable."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.models.pair import PairSignal
from app.services.pair_outcome import resolve_spread, track_pair_outcomes
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock

_ENTRY = datetime(2025, 1, 6, 10, 0, tzinfo=UTC)
_VALID = datetime(2025, 3, 1, tzinfo=UTC)


def _sig(
    direction: str,
    entry_z: float,
    *,
    z_stop: float,
    spread_entry: float,
    validity: datetime = _VALID,
) -> PairSignal:
    return PairSignal(
        stock_a_id=1,
        stock_b_id=2,
        method="df",
        beta=1.0,
        alpha=0.0,
        half_life=8.0,
        df_tstat=-3.5,
        direction=direction,
        entry_z=entry_z,
        z_exit=0.0,
        z_stop=z_stop,
        spread_entry=Decimal(str(spread_entry)),
        spread_sigma=Decimal("1.0"),
        created_at=_ENTRY,
        validity_until=validity,
    )


def _weekdays(start: date, n: int) -> list[date]:
    out: list[date] = []
    d = start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _closes(vals: list[float]) -> dict[date, float]:
    return dict(zip(_weekdays(date(2025, 1, 7), len(vals)), vals, strict=True))


def _b(n: int) -> dict[date, float]:
    return _closes([100.0] * n)


# --------------------------------------------------------------------------- #
# resolve_spread (pure)                                                       #
# --------------------------------------------------------------------------- #


def test_long_spread_reverts_to_exit_is_tp_first() -> None:
    sig = _sig("long_spread", entry_z=-2.5, z_stop=-3.5, spread_entry=-2.5)
    out = resolve_spread(
        sig, _closes([98.0, 99.0, 100.5]), _b(3), now=datetime(2025, 2, 1, tzinfo=UTC)
    )
    assert out is not None and out.status == "tp_first"
    assert out.exit_z >= 0.0 and out.outcome_r > 0  # reverted through the mean → a win


def test_long_spread_hits_stop_is_sl_first_and_gap_is_worse_than_minus_one() -> None:
    sig = _sig("long_spread", entry_z=-2.5, z_stop=-3.5, spread_entry=-2.5)
    out = resolve_spread(sig, _closes([97.0, 96.0]), _b(2), now=datetime(2025, 2, 1, tzinfo=UTC))
    assert out is not None and out.status == "sl_first"
    assert out.outcome_r < -1.0  # z gapped to −4 past the −3.5 stop → honest gap-through-stop


def test_short_spread_reverts_is_tp_first() -> None:
    sig = _sig("short_spread", entry_z=2.5, z_stop=3.5, spread_entry=2.5)
    out = resolve_spread(sig, _closes([102.0, 100.0]), _b(2), now=datetime(2025, 2, 1, tzinfo=UTC))
    assert out is not None and out.status == "tp_first" and out.outcome_r > 0


def test_unresolved_when_no_cross_within_validity() -> None:
    sig = _sig("long_spread", entry_z=-2.5, z_stop=-3.5, spread_entry=-2.5)
    out = resolve_spread(sig, _closes([98.0, 98.5]), _b(2), now=datetime(2025, 1, 15, tzinfo=UTC))
    assert out is None  # no cross, still inside validity → stays open


def test_expired_marks_partial_revert_when_validity_lapsed() -> None:
    sig = _sig("long_spread", entry_z=-2.5, z_stop=-3.5, spread_entry=-2.5)
    out = resolve_spread(sig, _closes([98.0, 98.5]), _b(2), now=datetime(2025, 4, 1, tzinfo=UTC))
    assert out is not None and out.status == "expired"
    assert abs(out.outcome_r - 1.0) < 0.01  # last z=−1.5 → (−1.5−(−2.5))/1.0 = +1.0 R marked


def test_cross_after_validity_is_expired_not_a_win() -> None:
    # validity lapses 2025-01-10; a big revert on 2025-01-13 (PAST validity) must NOT book as a
    # win — the signal expired first, marked at the last in-window bar (quant-verifier HIGH).
    sig = _sig(
        "long_spread",
        entry_z=-2.5,
        z_stop=-3.5,
        spread_entry=-2.5,
        validity=datetime(2025, 1, 10, tzinfo=UTC),
    )
    # weekdays from 01-07: 07,08,09,10 (in-window, no cross), then 13 (past validity, big revert)
    a = _closes([98.0, 98.5, 98.5, 98.5, 102.0])  # spreads −2,−1.5,−1.5,−1.5,+2
    out = resolve_spread(sig, a, _b(5), now=datetime(2025, 2, 1, tzinfo=UTC))
    assert out is not None and out.status == "expired"  # NOT tp_first
    assert abs(out.outcome_r - 1.0) < 0.01  # marked at the last in-window z=−1.5 → +1.0R


# --------------------------------------------------------------------------- #
# track_pair_outcomes (DB)                                                    #
# --------------------------------------------------------------------------- #


async def _insert_daily(
    db: AsyncSession, stock_id: int, closes: list[float], days: list[date]
) -> None:
    from app.models.market_data import OhlcvDaily

    for d, close in zip(days, closes, strict=True):
        px = Decimal(str(round(float(close), 4)))
        db.add(
            OhlcvDaily(
                stock_id=stock_id,
                time=datetime(d.year, d.month, d.day, 10, 0, tzinfo=UTC),
                open=px,
                high=px,
                low=px,
                close=px,
                volume=1000,
                is_complete=True,
            )
        )
    await db.flush()


async def test_track_resolves_open_signal_from_tape(db: AsyncSession) -> None:
    a = await make_stock(db, symbol="TRA")
    b = await make_stock(db, symbol="TRB")
    sig = PairSignal(
        stock_a_id=a.id,
        stock_b_id=b.id,
        method="df",
        beta=1.0,
        alpha=0.0,
        half_life=8.0,
        df_tstat=-3.5,
        direction="long_spread",
        entry_z=-2.5,
        z_exit=0.0,
        z_stop=-3.5,
        spread_entry=Decimal("-2.5"),
        spread_sigma=Decimal("1.0"),
        created_at=_ENTRY,
        validity_until=_VALID,
    )
    db.add(sig)
    await db.flush()
    days = _weekdays(date(2025, 1, 7), 5)
    await _insert_daily(db, a.id, [98.0, 99.0, 100.0, 100.0, 100.0], days)  # spread reverts to 0
    await _insert_daily(db, b.id, [100.0] * 5, days)
    await db.commit()

    n = await track_pair_outcomes(db, now=datetime(2025, 2, 1, tzinfo=UTC))
    assert n == 1
    await db.refresh(sig)
    assert sig.status == "tp_first"
    assert sig.outcome_r is not None and sig.outcome_r > 0
    assert sig.resolved_at is not None and sig.exit_z is not None


async def test_track_leaves_unresolved_signal_open(db: AsyncSession) -> None:
    a = await make_stock(db, symbol="TRC")
    b = await make_stock(db, symbol="TRD")
    sig = PairSignal(
        stock_a_id=a.id,
        stock_b_id=b.id,
        method="df",
        beta=1.0,
        alpha=0.0,
        half_life=8.0,
        df_tstat=-3.5,
        direction="long_spread",
        entry_z=-2.5,
        z_exit=0.0,
        z_stop=-3.5,
        spread_entry=Decimal("-2.5"),
        spread_sigma=Decimal("1.0"),
        created_at=_ENTRY,
        validity_until=_VALID,
    )
    db.add(sig)
    await db.flush()
    days = _weekdays(date(2025, 1, 7), 3)
    await _insert_daily(db, a.id, [98.0, 98.2, 98.4], days)  # drifts, never crosses
    await _insert_daily(db, b.id, [100.0] * 3, days)
    await db.commit()

    n = await track_pair_outcomes(db, now=datetime(2025, 1, 20, tzinfo=UTC))  # inside validity
    assert n == 0
    await db.refresh(sig)
    assert sig.status == "open" and sig.outcome_r is None
