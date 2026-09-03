"""Entry-quality shadow report — partitions the live signal cohort by each check's
flag, links outcomes, and gates an sl_atr flip on forward evidence."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.models.signal import Signal
from app.models.trading import Position
from app.services import entry_quality_shadow as eqs
from app.services.entry_quality_shadow import Bucket, EntryQualityShadow
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, make_stock

HEALTHY = {
    "DOW_TREND": {"score": 0.7, "weight": 20, "explanation": "up"},
    "MACD_CROSS": {"score": 0.6, "weight": 15, "explanation": "cross"},
    "RSI_LEVEL": {"score": 0.5, "weight": 10, "explanation": "rising"},
}
SINGLE = {"RSI_DIVERGENCE": {"score": 0.8, "weight": 10, "explanation": "div"}}


async def _signal(db, stock_id, factor_scores, *, entry="100.0000", stop_loss="97.0000"):
    now = datetime.now(tz=UTC)
    sig = Signal(
        stock_id=stock_id, direction="BUY", classification="swing", timeframe="1d",
        entry_price=entry, stop_loss=stop_loss, take_profit="115.0000", suggested_qty=100,
        confidence_pct=80, factor_scores=factor_scores, headline="T", status="active",
        is_shadow=False, validity_until=now + timedelta(days=5), created_at=now,
    )
    db.add(sig)
    await db.flush()
    return sig


async def _closed(db, user_id, stock_id, signal_id, realized):
    now = datetime.now(tz=UTC)
    db.add(Position(
        user_id=user_id, stock_id=stock_id, signal_id=signal_id, mode="paper", side="LONG",
        quantity=100, avg_entry_price=Decimal("100"), realized_pnl=Decimal(str(realized)),
        trail_state="none", opened_at=now, closed_at=now,
    ))


async def _open(db, user_id, stock_id, signal_id):
    """An OPEN paper position (no closed_at) — must NOT count as resolved."""
    now = datetime.now(tz=UTC)
    db.add(Position(
        user_id=user_id, stock_id=stock_id, signal_id=signal_id, mode="paper", side="LONG",
        quantity=100, avg_entry_price=Decimal("100"), realized_pnl=Decimal("0"),
        trail_state="none", opened_at=now, closed_at=None,
    ))


class TestEntryQualityShadow:
    async def test_partitions_by_diversity_with_outcomes(self, db: AsyncSession) -> None:
        user = await create_test_user(db)
        stock = await make_stock(db)
        # single-factor (diversity-flagged), traded, lost −1000
        s1 = await _signal(db, stock.id, SINGLE)
        await _closed(db, user.id, stock.id, s1.id, -1000)
        # healthy (passes diversity), traded, won +500
        s2 = await _signal(db, stock.id, HEALTHY)
        await _closed(db, user.id, stock.id, s2.id, 500)
        # healthy, NOT traded (no position) — counted but not resolved
        await _signal(db, stock.id, HEALTHY)
        await db.commit()

        r = await eqs.compute_entry_quality_shadow(db, since=datetime(2026, 7, 19, tzinfo=UTC))
        assert r.n_signals == 3
        f, p = r.div_flagged, r.div_passed
        assert (f.n, f.resolved, f.net) == (1, 1, Decimal("-1000"))
        assert (p.n, p.resolved, p.net) == (2, 1, Decimal("500"))
        # no ATR seeded → sl_atr check never fires → all in sl_passed
        assert r.sl_flagged.n == 0 and r.sl_passed.n == 3
        md = eqs.render_markdown(
            r, day=datetime.now(tz=UTC).date(),
            diversity_mode="active", sl_atr_mode="shadow",
        )
        assert "Entry-quality shadow" in md and "diversity FLAGGED" in md

    async def test_empty_cohort(self, db: AsyncSession) -> None:
        r = await eqs.compute_entry_quality_shadow(db, since=datetime.now(tz=UTC))
        assert r.n_signals == 0
        assert not eqs.sl_flip_ready(r)[0]

    async def test_reopen_counted_once_with_sum(self, db: AsyncSession) -> None:
        """A signal re-entered (2 closed positions) is ONE resolved trade with the
        SUMMED P&L; a signal whose only position is still OPEN is counted but not
        resolved. Guards `_realized_by_signal`'s per-signal `+=` and closed filter."""
        user = await create_test_user(db)
        stock = await make_stock(db)
        # one signal, two closed positions (a reopen) → counted once, +300 + −1000
        s1 = await _signal(db, stock.id, HEALTHY)
        await _closed(db, user.id, stock.id, s1.id, 300)
        await _closed(db, user.id, stock.id, s1.id, -1000)
        # second signal, only an OPEN position → counted in n, not resolved
        s2 = await _signal(db, stock.id, HEALTHY)
        await _open(db, user.id, stock.id, s2.id)
        await db.commit()

        r = await eqs.compute_entry_quality_shadow(db, since=datetime(2026, 7, 19, tzinfo=UTC))
        p = r.div_passed  # both HEALTHY → both pass diversity
        assert (p.n, p.resolved, p.net, p.wins) == (2, 1, Decimal("-700"), 0)

    async def test_sl_atr_partition_with_atr(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With ATR present, a tight-stop signal lands in sl_flagged and a wide-stop
        one in sl_passed; the div and sl partitions are orthogonal splits of the SAME
        cohort, so their nets reconcile. ATR is monkeypatched to avoid seeding candles."""
        async def fake_atr(*_a, **_k):
            return Decimal("5.0")

        monkeypatch.setattr(eqs, "latest_atr", fake_atr)
        user = await create_test_user(db)
        stock = await make_stock(db)
        # tight: |100−97| = 3 < 1.0×5.0 → sl_flagged
        s_tight = await _signal(db, stock.id, HEALTHY, entry="100.0000", stop_loss="97.0000")
        await _closed(db, user.id, stock.id, s_tight.id, -800)
        # wide: |100−90| = 10 ≥ 5.0 → sl_passed
        s_wide = await _signal(db, stock.id, HEALTHY, entry="100.0000", stop_loss="90.0000")
        await _closed(db, user.id, stock.id, s_wide.id, 400)
        await db.commit()

        r = await eqs.compute_entry_quality_shadow(db, since=datetime(2026, 7, 19, tzinfo=UTC))
        assert (r.sl_flagged.n, r.sl_flagged.resolved, r.sl_flagged.net) == (1, 1, Decimal("-800"))
        assert (r.sl_passed.n, r.sl_passed.resolved, r.sl_passed.net) == (1, 1, Decimal("400"))
        # both HEALTHY → diversity passes both; the two partitions cover the same cohort
        assert r.div_passed.resolved == 2
        assert r.div_flagged.net + r.div_passed.net == r.sl_flagged.net + r.sl_passed.net


def _shadow(sl_flagged: Bucket, sl_passed: Bucket) -> EntryQualityShadow:
    return EntryQualityShadow(
        since=datetime(2026, 7, 19, tzinfo=UTC), n_signals=0,
        div_flagged=Bucket(), div_passed=Bucket(), sl_flagged=sl_flagged, sl_passed=sl_passed,
    )


def _bucket(resolved: int, net: str, wins: int = 0) -> Bucket:
    return Bucket(n=resolved, resolved=resolved, net=Decimal(net), wins=wins)


class TestSlFlipReady:
    def test_not_enough_resolved(self) -> None:
        ready, why = eqs.sl_flip_ready(_shadow(_bucket(5, "-4000"), _bucket(20, "1000")))
        assert not ready and "keep accruing" in why

    def test_flagged_not_negative(self) -> None:
        ready, why = eqs.sl_flip_ready(_shadow(_bucket(25, "3000"), _bucket(20, "1000")))
        assert not ready and "not net-negative" in why

    def test_flagged_not_worse_than_passed(self) -> None:
        # flagged avg −40, passed avg −100 → flagged is BETTER → do not flip
        ready, why = eqs.sl_flip_ready(_shadow(_bucket(25, "-1000"), _bucket(20, "-2000")))
        assert not ready and "not worse than passed" in why

    def test_ready(self) -> None:
        # flagged avg −200 (worse), passed avg +50 → ready
        ready, why = eqs.sl_flip_ready(_shadow(_bucket(25, "-5000"), _bucket(20, "1000")))
        assert ready and "READY" in why
