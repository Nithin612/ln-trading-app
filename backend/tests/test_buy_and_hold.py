"""Buy-and-hold benchmark — H2.

We report P&L against zero. Zero is the wrong denominator: the question is not "did it
make money" but "did it beat doing nothing with the same money". The external review's
most sobering number was a five-year agent project that buy-and-hold quietly beat, and
nobody saw it until someone opened a CSV.

These pin the arithmetic, the fail-closed conditions, and — the part with real teeth — the
direction-awareness of the partial-deployment caveat, which must not excuse a shortfall it
does not actually excuse.
"""

from datetime import date
from decimal import Decimal

import pytest
from app.models.stock import Index, IndexOhlcvDaily
from app.services import buy_and_hold as bah
from sqlalchemy.ext.asyncio import AsyncSession

D = Decimal


async def _seed(db: AsyncSession, bars: dict[date, str], symbol: str = "NIFTY50") -> int:
    idx = Index(symbol=symbol, name="Nifty 50", exchange="NSE", is_active=True)
    db.add(idx)
    await db.flush()
    for d, close in bars.items():
        db.add(IndexOhlcvDaily(index_id=idx.id, trade_date=d, close=D(close)))
    await db.commit()
    return int(idx.id)


@pytest.mark.asyncio
class TestComparison:
    async def test_returns_and_excess(self, db: AsyncSession) -> None:
        await _seed(db, {date(2026, 8, 17): "24000", date(2026, 9, 4): "24240"})
        r = await bah.compare(
            db,
            start=date(2026, 8, 17),
            end=date(2026, 9, 4),
            book_pnl=D("-17522"),
            capital=D("100000"),
        )
        assert r is not None
        assert r.index_return_pct == pytest.approx(Decimal("1.0"))  # 24000 → 24240
        assert r.book_return_pct == pytest.approx(Decimal("-17.522"))
        assert r.excess_pct == pytest.approx(Decimal("-18.522"))

    async def test_uses_the_last_bar_on_or_before_the_window_edge(
        self, db: AsyncSession
    ) -> None:
        """The paper clock can start on a weekend. The honest baseline is the last price
        you could actually have bought at — never a forward one, which is look-ahead."""
        await _seed(db, {date(2026, 8, 14): "24000", date(2026, 9, 4): "24240"})
        r = await bah.compare(
            db,
            start=date(2026, 8, 16),  # a Sunday: no bar
            end=date(2026, 9, 4),
            book_pnl=D("0"),
            capital=D("100000"),
        )
        assert r is not None
        assert r.start == date(2026, 8, 14)  # reached BACK, not forward

    async def test_never_reaches_forward_for_a_missing_end_bar(
        self, db: AsyncSession
    ) -> None:
        """With bars only at 08-14 and 09-04, a window ending 08-31 resolves BOTH ends to
        08-14 — it must refuse rather than reach forward to the 09-04 bar, which would be
        look-ahead, or report the 0.0% that identical ends imply."""
        await _seed(db, {date(2026, 8, 14): "24000", date(2026, 9, 4): "24240"})
        assert (
            await bah.compare(
                db, start=date(2026, 8, 14), end=date(2026, 8, 31), book_pnl=D("0"),
                capital=D("100000"),
            )
            is None
        )


@pytest.mark.asyncio
class TestFailsClosed:
    """A benchmark line exists to be the number nobody can argue with. A silently
    substituted date or index would defeat the entire point."""

    async def test_no_index_rows(self, db: AsyncSession) -> None:
        assert (
            await bah.compare(
                db, start=date(2026, 8, 17), end=date(2026, 9, 4),
                book_pnl=D("0"), capital=D("100000"),
            )
            is None
        )

    async def test_zero_capital(self, db: AsyncSession) -> None:
        await _seed(db, {date(2026, 8, 17): "24000", date(2026, 9, 4): "24240"})
        assert (
            await bah.compare(
                db, start=date(2026, 8, 17), end=date(2026, 9, 4),
                book_pnl=D("100"), capital=D("0"),
            )
            is None
        )

    async def test_window_inside_one_session(self, db: AsyncSession) -> None:
        """Both ends resolving to the same bar gives a 0.0% benchmark that is an artefact
        of the window, not a fact about the market."""
        await _seed(db, {date(2026, 8, 17): "24000"})
        assert (
            await bah.compare(
                db, start=date(2026, 8, 18), end=date(2026, 8, 19),
                book_pnl=D("100"), capital=D("100000"),
            )
            is None
        )

    async def test_inverted_window(self, db: AsyncSession) -> None:
        await _seed(db, {date(2026, 8, 17): "24000", date(2026, 9, 4): "24240"})
        assert (
            await bah.compare(
                db, start=date(2026, 9, 4), end=date(2026, 8, 17),
                book_pnl=D("100"), capital=D("100000"),
            )
            is None
        )


def _mk(book: str, index: str) -> bah.BuyAndHold:
    return bah.BuyAndHold(
        index_symbol="NIFTY50",
        start=date(2026, 8, 17),
        end=date(2026, 9, 4),
        index_start_close=D("24287.65"),
        index_end_close=D("23897.70"),
        index_return_pct=D(index),
        book_pnl=D("-17522"),
        capital=D("100000"),
        book_return_pct=D(book),
    )


class TestDeploymentCaveatIsDirectionAware:
    """⭐ The caveat must not excuse a shortfall it does not excuse.

    `flip_readiness.tail_guard` learned this the hard way when it announced "the negative
    mean is carried by losses" for a cohort whose mean was positive: a line written to
    prevent misleading banners must not emit one itself.
    """

    def test_both_down_makes_under_deployment_worse_not_better(self) -> None:
        """The real book, 2026-09-05: NIFTY −1.61%, book −17.52%. Less capital was at
        risk and MORE was lost — partial deployment is no defence."""
        out = "\n".join(bah.render_lines(_mk("-17.52", "-1.61"), exposure_pct=D("45.3")))
        assert "makes this WORSE" in out
        assert "no defence" in out

    def test_a_rising_index_genuinely_explains_part_of_the_gap(self) -> None:
        out = "\n".join(bah.render_lines(_mk("-5.0", "8.0"), exposure_pct=D("45.3")))
        assert "genuinely explains part of the gap" in out
        assert "WORSE" not in out

    def test_beating_the_index_on_less_risk_reads_as_stronger(self) -> None:
        out = "\n".join(bah.render_lines(_mk("6.0", "-1.61"), exposure_pct=D("45.3")))
        assert "BEAT" in out
        assert "stronger than the headline" in out

    def test_no_exposure_figure_means_no_caveat(self) -> None:
        out = "\n".join(bah.render_lines(_mk("-17.52", "-1.61")))
        assert "not deployed alike" not in out

    def test_unassessable_says_what_is_missing(self) -> None:
        out = "\n".join(bah.render_lines(None))
        assert "not assessable" in out
        assert "paper-clock" in out
