"""Portfolio-heat counterfactual (2026-09-02) — measurement only, enforces nothing.

It exists because the paper book is a deliberately WIDE evidence sampler (~5 entries/day,
~5-day holds ⇒ ~25 concurrent positions), so the 30-day profit-days clock — the go-live
gate — is otherwise measuring a book that will never be traded (live is ₹1 lakh, 1–2
positions). This replays the same signals against a cap and reports both subsets.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.models.trading import Position
from app.services import heat_counterfactual as hcf
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, make_stock

BASE = datetime(2026, 8, 20, 4, 0, tzinfo=UTC)


class TestAdmissionRisk:
    def test_long_risk_is_entry_minus_stop(self) -> None:
        assert hcf._risk("LONG", Decimal("100"), Decimal("96"), 50) == Decimal("200")

    def test_short_risk_is_stop_minus_entry(self) -> None:
        assert hcf._risk("SHORT", Decimal("100"), Decimal("104"), 50) == Decimal("200")

    def test_stop_past_entry_consumes_no_budget(self) -> None:
        """Clamped at zero: a long whose stop has trailed ABOVE entry exposes nothing, so
        it must not hold heat budget hostage. This is also the reward for de-risking —
        and it is the same clamp the `used = abs(...)` bug gets wrong."""
        assert hcf._risk("LONG", Decimal("100"), Decimal("110"), 50) == Decimal("0")
        assert hcf._risk("SHORT", Decimal("100"), Decimal("90"), 50) == Decimal("0")


async def _pos(
    db: AsyncSession, user_id: int, stock_id: int, *, qty: int, entry: str, sl: str,
    opened: datetime, closed: datetime | None = None, pnl: str = "0", side: str = "LONG",
) -> Position:
    p = Position(
        user_id=user_id, stock_id=stock_id, mode="paper", side=side, quantity=qty,
        avg_entry_price=Decimal(entry), current_sl=Decimal(sl), trail_state="none",
        realized_pnl=Decimal(pnl), opened_at=opened, closed_at=closed,
    )
    db.add(p)
    await db.flush()
    return p


class TestChronologicalAdmission:
    async def test_cap_admits_until_full_then_skips(self, db: AsyncSession) -> None:
        user = await create_test_user(db)
        stock = await make_stock(db)
        # ₹6,000 cap. Three ₹2,000-risk entries fit; the fourth does not.
        for i in range(4):
            await _pos(
                db, user.id, stock.id, qty=100, entry="100", sl="80",  # risk ₹2,000
                opened=BASE + timedelta(minutes=i), pnl="-100",
                closed=BASE + timedelta(days=30),
            )
        await db.commit()
        r = await hcf.compute_heat_counterfactual(
            db, capital=Decimal("100000"), cap_pct=Decimal("6"), since=BASE - timedelta(days=1)
        )
        assert r.cap_inr == Decimal("6000.00")
        assert r.admitted.n == 3 and r.skipped.n == 1
        assert r.peak_concurrent == 3 and r.full_peak_concurrent == 4

    async def test_a_close_frees_budget_for_a_later_entry(self, db: AsyncSession) -> None:
        """The walk must interleave closes with opens. Applying closes at the end would
        make the cap permanently full and understate what a disciplined book could hold."""
        user = await create_test_user(db)
        stock = await make_stock(db)
        # Fills the cap, then closes, then a 4th arrives and SHOULD be admitted.
        for i in range(3):
            await _pos(
                db, user.id, stock.id, qty=100, entry="100", sl="80",
                opened=BASE + timedelta(minutes=i), closed=BASE + timedelta(hours=1), pnl="10",
            )
        await _pos(
            db, user.id, stock.id, qty=100, entry="100", sl="80",
            opened=BASE + timedelta(hours=2), closed=BASE + timedelta(hours=3), pnl="10",
        )
        await db.commit()
        r = await hcf.compute_heat_counterfactual(
            db, capital=Decimal("100000"), cap_pct=Decimal("6"), since=BASE - timedelta(days=1)
        )
        assert r.admitted.n == 4, "budget released on close must admit the later entry"
        assert r.skipped.n == 0
        assert r.peak_concurrent == 3

    async def test_one_oversized_entry_can_eat_the_whole_budget(
        self, db: AsyncSession
    ) -> None:
        """The documented method limit, pinned: admission is by ARRIVAL TIME, not quality,
        so a single large-risk entry arriving first blocks three good ones behind it. This
        is why the report compares PER-TRADE figures and not just the total."""
        user = await create_test_user(db)
        stock = await make_stock(db)
        await _pos(  # risk ₹6,000 — the entire cap
            db, user.id, stock.id, qty=300, entry="100", sl="80",
            opened=BASE, closed=BASE + timedelta(days=30), pnl="-5000",
        )
        for i in range(3):
            await _pos(
                db, user.id, stock.id, qty=100, entry="100", sl="80",
                opened=BASE + timedelta(minutes=i + 1), closed=BASE + timedelta(days=30),
                pnl="1000",
            )
        await db.commit()
        r = await hcf.compute_heat_counterfactual(
            db, capital=Decimal("100000"), cap_pct=Decimal("6"), since=BASE - timedelta(days=1)
        )
        assert r.admitted.n == 1 and r.skipped.n == 3
        assert r.admitted.net == Decimal("-5000")
        assert r.skipped.net == Decimal("3000")
        # …and the summary must call that out rather than saying "the cap helped".
        assert "COSTS money" in hcf.summary_line(r)

    async def test_since_is_respected(self, db: AsyncSession) -> None:
        """The epoch matters: the first version defaulted to OUTCOME_EPOCH and silently
        spanned the 2026-08-17 cut, where risk-first sizing moved from the signal entry to
        the actual fill AND the honest fill model started — so pre-cut risk recomputed
        from the fill was never the trade's real budget (₹5,663 vs a ₹2,000 budget)."""
        user = await create_test_user(db)
        stock = await make_stock(db)
        await _pos(
            db, user.id, stock.id, qty=100, entry="100", sl="80",
            opened=BASE - timedelta(days=10), closed=BASE, pnl="-500",
        )
        await _pos(
            db, user.id, stock.id, qty=100, entry="100", sl="80",
            opened=BASE + timedelta(days=1), closed=BASE + timedelta(days=2), pnl="100",
        )
        await db.commit()
        r = await hcf.compute_heat_counterfactual(
            db, capital=Decimal("100000"), cap_pct=Decimal("6"), since=BASE
        )
        assert r.admitted.n + r.skipped.n == 1, "entries before `since` must be excluded"
        assert r.admitted.net == Decimal("100")

    async def test_missing_stop_is_excluded_not_treated_as_zero_risk(
        self, db: AsyncSession
    ) -> None:
        """A leg with no recoverable stop has UNKNOWN risk. Treating it as zero would
        admit it free and silently overstate what the cap could hold."""
        user = await create_test_user(db)
        stock = await make_stock(db)
        p = await _pos(
            db, user.id, stock.id, qty=100, entry="100", sl="80",
            opened=BASE, closed=BASE + timedelta(days=1), pnl="50",
        )
        p.current_sl = None
        await db.commit()
        r = await hcf.compute_heat_counterfactual(
            db, capital=Decimal("100000"), cap_pct=Decimal("6"), since=BASE - timedelta(days=1)
        )
        assert r.no_stop == 1
        assert r.admitted.n == 0 and r.skipped.n == 0


class TestSummaryHonesty:
    async def test_total_better_but_per_trade_worse_is_reported_as_a_risk_control(
        self, db: AsyncSession
    ) -> None:
        """The verdict that matters. A cap can cut TOTAL loss purely by taking fewer trades
        at an unchanged negative expectancy — that is a risk control working, not a
        profitability fix, and the line must say so instead of "the cap HELPED"."""
        user = await create_test_user(db)
        stock = await make_stock(db)
        # Admitted: one big loser. Skipped: many small losers (worse in total, better each).
        await _pos(
            db, user.id, stock.id, qty=300, entry="100", sl="80",
            opened=BASE, closed=BASE + timedelta(days=30), pnl="-3000",
        )
        for i in range(6):
            await _pos(
                db, user.id, stock.id, qty=100, entry="100", sl="80",
                opened=BASE + timedelta(minutes=i + 1), closed=BASE + timedelta(days=30),
                pnl="-700",
            )
        await db.commit()
        r = await hcf.compute_heat_counterfactual(
            db, capital=Decimal("100000"), cap_pct=Decimal("6"), since=BASE - timedelta(days=1)
        )
        line = hcf.summary_line(r)
        assert "per-trade is WORSE" in line
        assert "RISK control, not a profitability fix" in line

    async def test_render_smoke(self, db: AsyncSession) -> None:
        user = await create_test_user(db)
        stock = await make_stock(db, symbol="HEATCO")
        await _pos(
            db, user.id, stock.id, qty=100, entry="100", sl="80",
            opened=BASE, closed=BASE + timedelta(days=1), pnl="250",
        )
        await db.commit()
        r = await hcf.compute_heat_counterfactual(
            db, capital=Decimal("100000"), cap_pct=Decimal("6"), since=BASE - timedelta(days=1)
        )
        md = hcf.render_markdown(r, day="2026-09-02")
        assert "Portfolio-heat counterfactual" in md
        assert "ENFORCES NOTHING" in md
        assert "HEATCO" in md
        assert "Method limit" in md  # the chronological-admission caveat must ship with it
