"""make-analysis diagnostics — signal-age-at-entry + market-regime (level vs breadth).

Both are read-only daily-report sidecars. Covers: the pure market-regime summariser (disagree /
agree / insufficient) + the signal-age bucketing over real paper positions (fresh vs stale P&L)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.models.signal import Signal
from app.models.trading import Position
from app.services import market_regime_report as mrr
from app.services import signal_age_report as sar
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, make_stock

D = Decimal


# ── Market-regime summariser (pure) ─────────────────────────────────────────
class TestMarketRegime:
    def test_disagree_below_200dma_but_strong_breadth(self) -> None:
        # High long ago, low-but-rising now: last < 200-DMA (level risk-off) yet above the
        # 20-DMA with 100% up-days (breadth risk-on) → the Window-A tape → DISAGREE.
        closes = [D(200)] * 180 + [D(v) for v in range(80, 101)]  # 201 closes, last = 100
        r = mrr.summarize_regime(closes, D("12.5"))
        assert r.enough is True
        assert r.vs_long_pct < 0 and r.level_bullish is False  # below 200-DMA
        assert r.vs_short_pct > 0 and r.breadth_up_pct == 100.0  # above 20-DMA, all up
        assert r.breadth_bullish is True and r.disagree is True
        assert "DISAGREE" in mrr.summary_line(r)

    def test_agree_bullish_above_both(self) -> None:
        closes = [D(v) for v in range(80, 281)]  # monotonic up, last = 280 well above both DMAs
        r = mrr.summarize_regime(closes, D("11.0"))
        assert r.level_bullish is True and r.breadth_bullish is True and r.disagree is False
        assert "DISAGREE" not in mrr.summary_line(r)

    def test_insufficient_history(self) -> None:
        r = mrr.summarize_regime([D(100)] * 5, None)
        assert r.enough is False and r.disagree is None
        assert "insufficient" in mrr.summary_line(r)

    def test_render_smoke(self) -> None:
        closes = [D(200)] * 180 + [D(v) for v in range(80, 101)]
        r = mrr.summarize_regime(closes, D("13"))
        md = mrr.render_markdown(r, day=datetime.now(UTC).date())
        assert "Market regime" in md and "DISAGREE" in md and "200-DMA" in md


# ── Signal age at entry (DB) ─────────────────────────────────────────────────
def test_band_label_edges() -> None:
    assert sar._band_label(0.0) == "0–20% (fresh)"
    assert sar._band_label(50.0) == "40–60%"
    assert sar._band_label(100.0) == "80–100% (stale)"  # exactly 100 lands in the stale band
    assert sar._band_label(120.0) is None  # after expiry → overflow bucket


async def _signal_and_trade(
    db: AsyncSession, user_id: int, symbol: str, *, created: datetime, span_days: int,
    pct: float, realized: str,
) -> None:
    stock = await make_stock(db, symbol=symbol)
    validity = created + timedelta(days=span_days)
    sig = Signal(
        stock_id=stock.id, direction="BUY", classification="positional", timeframe="1d",
        entry_price="500.0000", stop_loss="480.0000", take_profit="560.0000",
        suggested_qty=10, confidence_pct=80,
        factor_scores={"A": {"weight": 20, "score": 0.8, "explanation": "x"}},
        headline="t", status="active", is_shadow=False, validity_until=validity, created_at=created,
    )
    db.add(sig)
    await db.flush()
    opened = created + timedelta(seconds=span_days * 86_400 * pct / 100.0)
    db.add(
        Position(
            user_id=user_id, stock_id=stock.id, signal_id=sig.id, mode="paper", side="LONG",
            quantity=10, avg_entry_price=D("500"), realized_pnl=D(realized),
            opened_at=opened, closed_at=opened + timedelta(hours=1),
        )
    )


class TestSignalAge:
    async def test_buckets_by_pct_elapsed_and_headline(self, db: AsyncSession) -> None:
        user = await create_test_user(db)
        created = datetime(2026, 8, 1, tzinfo=UTC)
        mk = _signal_and_trade
        await mk(db, user.id, "FRESH", created=created, span_days=30, pct=10, realized="100")
        await mk(db, user.id, "MID", created=created, span_days=30, pct=50, realized="100")
        await mk(db, user.id, "STALE", created=created, span_days=30, pct=90, realized="-500")
        await db.commit()

        r = await sar.compute_signal_age(db)
        assert r.n_trades == 3
        bands = dict(r.bands)
        assert bands["0–20% (fresh)"].n == 1 and bands["0–20% (fresh)"].net == D("100")
        assert bands["40–60%"].n == 1
        assert bands["80–100% (stale)"].n == 1 and bands["80–100% (stale)"].net == D("-500")
        assert r.median_pct == 50.0
        late, early = sar._late_early(r)
        assert late.net == D("-500") and early.net == D("100")  # stale worse than fresh
        assert "STALE ENTRIES ARE WORSE" in sar.render_markdown(r, day=created.date())

    async def test_stale_entry_on_pre_epoch_signal_is_included(self, db: AsyncSession) -> None:
        # Regression (quant-verifier HIGH): an OLD signal committed before OUTCOME_EPOCH that we
        # TRADED stale must NOT be dropped — the cohort is keyed on the trade (opened_at), not the
        # signal's commit date. This is the exact archetype the report exists to catch; under the
        # old `Signal.created_at >= OUTCOME_EPOCH` filter it would be silently missing (n=0).
        user = await create_test_user(db)
        pre_epoch = datetime(2026, 7, 5, tzinfo=UTC)  # before OUTCOME_EPOCH (2026-07-19)
        await _signal_and_trade(
            db, user.id, "OLDSTALE", created=pre_epoch, span_days=30, pct=85, realized="-300"
        )
        await db.commit()
        r = await sar.compute_signal_age(db)
        assert r.n_trades == 1  # opened ~2026-07-30 ≥ since; the old signal is NOT dropped
        assert dict(r.bands)["80–100% (stale)"].n == 1

    async def test_empty_cohort_renders(self, db: AsyncSession) -> None:
        r = await sar.compute_signal_age(db)
        assert r.n_trades == 0
        assert "No resolved paper trades" in sar.render_markdown(r, day=datetime.now(UTC).date())
        assert "no resolved paper trades" in sar.summary_line(r).lower()
