"""A37 + T3 — the volume-participation impact, and its parametrised fill tests.

Our 6.8.2 model charged the real half-spread plus a size-vs-TOP-OF-BOOK impact. Neither
notices that an order is large relative to the stock's DAILY VOLUME: the notional cap
bounds a position in rupees, not in liquidity. **SRTL is the named case** — a ₹39
micro-cap, 2,666 shares; a ₹1 lakh position in a name trading ₹5 lakh a day is a fifth of
a session and is not fillable at the quoted price, yet we modelled it as free.

T3's shape is `(participation, expected_fill)` — given a market-impact model, assert the
resulting fill. That is what `TestParticipationCurve` is.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from app.broker.depth import Depth
from app.broker.paper_broker import (
    exit_mark,
    participation_bps,
    place_paper_order,
    simulate_fill,
    update_position_pnl,
)
from app.core.config import settings
from app.models.market_data import Ohlcv1m, OhlcvDaily
from app.models.signal import Signal
from app.models.trading import Position
from app.services.daily_report import _open_book_mtm
from app.services.liquidity import load_median_traded_values, median_traded_value
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, make_stock

#: ₹5 lakh a day — the SRTL shape.
_THIN_ADV = Decimal("500000")
#: ₹100 crore a day — a liquid large-cap.
_DEEP_ADV = Decimal("1000000000")
_BOOK = Depth(bid=Decimal("38.95"), ask=Decimal("39.05"), bid_qty=5000, ask_qty=5000)


@pytest.fixture(autouse=True)
def _knobs(monkeypatch: pytest.MonkeyPatch) -> None:
    """`conftest` zeroes `paper_slippage_bps`, which would let a flat-path assertion pass
    for the wrong reason. Pin every knob this module depends on."""
    monkeypatch.setattr(settings, "paper_slippage_bps", 2.0)
    monkeypatch.setattr(settings, "paper_participation_enabled", True)
    monkeypatch.setattr(settings, "paper_participation_k", 0.1)


class TestParticipationCurve:
    """T3: given a participation fraction, assert the impact. Values are `k × p² × 10⁴`
    with k = 0.1, the zipline `VolumeShareSlippage` calibration."""

    @pytest.mark.parametrize(
        ("participation", "expected_bps"),
        [
            (Decimal("0.001"), Decimal("0.001")),   # 0.1% — negligible
            (Decimal("0.025"), Decimal("0.625")),   # zipline's 2.5% bar cap
            (Decimal("0.05"), Decimal("2.5")),
            (Decimal("0.10"), Decimal("10")),
            (Decimal("0.20"), Decimal("40")),       # the SRTL neighbourhood
            (Decimal("0.50"), Decimal("250")),
            (Decimal("1.00"), Decimal("1000")),     # a whole day's volume
        ],
    )
    def test_impact_matches_the_quadratic_model(
        self, participation: Decimal, expected_bps: Decimal
    ) -> None:
        adv = Decimal("1000000")
        bps, got = participation_bps(adv * participation, adv)
        assert got == participation
        assert bps == pytest.approx(expected_bps, rel=Decimal("1e-9"))

    def test_impact_grows_faster_than_linearly(self) -> None:
        """The whole point of quadratic: doubling your size must more than double the
        cost, or a large order is just a lot of small ones."""
        adv = Decimal("1000000")
        single, _ = participation_bps(Decimal("50000"), adv)   # 5%
        double, _ = participation_bps(Decimal("100000"), adv)  # 10%
        assert double > single * 2


class TestFailsOpen:
    """Unknown liquidity must never read as infinitely illiquid."""

    @pytest.mark.parametrize("adv", [None, Decimal("0"), Decimal("-1")])
    def test_missing_or_unusable_adv_charges_nothing(self, adv: Decimal | None) -> None:
        bps, part = participation_bps(Decimal("100000"), adv)
        assert bps == Decimal(0)
        assert part == Decimal(0)

    def test_a_zero_size_order_charges_nothing(self) -> None:
        assert participation_bps(Decimal("0"), _THIN_ADV) == (Decimal(0), Decimal(0))

    def test_the_knob_switches_it_off_entirely(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "paper_participation_enabled", False)
        assert participation_bps(Decimal("100000"), _THIN_ADV) == (Decimal(0), Decimal(0))


class TestItReachesTheFill:
    """The impact is worthless if it does not change a price."""

    def test_the_srtl_order_is_no_longer_modelled_as_free(self) -> None:
        """2,666 shares of a ₹39 stock = ₹103,974 against ₹5 lakh a day ≈ 20.8%."""
        f = simulate_fill(
            Decimal("39"), "BUY", depth=None, quantity=2666, adv_value=_THIN_ADV
        )
        assert f.participation > Decimal("0.20")
        assert f.participation_bps > Decimal("40")
        # Was 2 bps (the flat floor) before A37.
        assert f.slippage_bps > Decimal("40")
        assert f.fill > Decimal("39.15")

    def test_a_small_order_in_the_same_stock_is_untouched(self) -> None:
        """The model must bite on SIZE, not on the stock. 100 shares is 0.78% of the day."""
        f = simulate_fill(
            Decimal("39"), "BUY", depth=None, quantity=100, adv_value=_THIN_ADV
        )
        assert f.participation_bps < Decimal("0.1")

    def test_the_same_order_in_a_liquid_name_is_untouched(self) -> None:
        f = simulate_fill(
            Decimal("39"), "BUY", depth=None, quantity=2666, adv_value=_DEEP_ADV
        )
        assert f.participation_bps < Decimal("0.01")

    def test_it_applies_on_the_spread_path_too(self) -> None:
        with_adv = simulate_fill(
            Decimal("39"), "BUY", depth=_BOOK, quantity=2666, adv_value=_THIN_ADV
        )
        without = simulate_fill(Decimal("39"), "BUY", depth=_BOOK, quantity=2666)
        assert with_adv.slippage_bps > without.slippage_bps

    def test_it_applies_on_the_flat_path_too(self) -> None:
        """A thin stock usually has NO live book, so charging participation only on the
        spread path would exempt exactly the names the model exists for."""
        with_adv = simulate_fill(
            Decimal("39"), "BUY", depth=None, quantity=2666, adv_value=_THIN_ADV
        )
        without = simulate_fill(Decimal("39"), "BUY", depth=None, quantity=2666)
        assert with_adv.model == "flat"
        assert with_adv.slippage_bps > without.slippage_bps

    def test_the_total_is_still_bounded_by_the_ceiling(self) -> None:
        """Participation overlaps the top-of-book term rather than being orthogonal to it,
        so an illiquid name trips both. The ceiling is what stops the sum running away."""
        f = simulate_fill(
            Decimal("39"), "BUY", depth=_BOOK, quantity=2_000_000, adv_value=_THIN_ADV
        )
        assert f.slippage_bps <= Decimal(str(settings.paper_slippage_max_bps))

    def test_the_verdict_is_stamped_for_the_audit_trail(self) -> None:
        f = simulate_fill(
            Decimal("39"), "BUY", depth=None, quantity=2666, adv_value=_THIN_ADV
        )
        payload = f.as_payload()
        assert Decimal(payload["participation_bps"]) > Decimal("40")  # type: ignore[arg-type]
        assert Decimal(payload["participation_pct"]) > Decimal("20")  # type: ignore[arg-type]


class TestMarksPayItToo:
    """A31: charging participation on the FILL but not on the MARK would re-open exactly
    the optimism A21 closed. Getting out of a fifth of a day's volume costs what getting
    in cost."""

    def test_an_exit_mark_charges_participation(self) -> None:
        marked = exit_mark(Decimal("39"), "LONG", depth=None, quantity=2666, adv_value=_THIN_ADV)
        plain = exit_mark(Decimal("39"), "LONG", depth=None, quantity=2666)
        assert marked.participation_bps > Decimal("40")
        assert marked.fill < plain.fill  # a long marks further DOWN

    def test_a_short_mark_moves_the_other_way(self) -> None:
        marked = exit_mark(Decimal("39"), "SHORT", depth=None, quantity=2666, adv_value=_THIN_ADV)
        plain = exit_mark(Decimal("39"), "SHORT", depth=None, quantity=2666)
        assert marked.fill > plain.fill


class TestMedianHelper:
    def test_median_of_an_even_series_is_the_midpoint(self) -> None:
        assert median_traded_value(
            [Decimal("10"), Decimal("20"), Decimal("30"), Decimal("40")]
        ) == Decimal("25")

    def test_median_of_an_odd_series(self) -> None:
        assert median_traded_value([Decimal("30"), Decimal("10"), Decimal("20")]) == Decimal("20")

    def test_empty_is_zero(self) -> None:
        assert median_traded_value([]) == Decimal("0")

    def test_it_is_a_median_not_a_mean(self) -> None:
        """One freak volume day must not make an illiquid stock look tradeable — the
        reason the liquidity gate uses a median, and why this shares its helper."""
        spiky = [Decimal("1000")] * 19 + [Decimal("100000000")]
        assert median_traded_value(spiky) == Decimal("1000")


# ── The SEAMS ───────────────────────────────────────────────────────────────
# Everything above tests the pure model. quant-verifier showed that was not enough:
# reverting the sizing refinement, nulling the ADV in `place_paper_order`, and dropping
# `adv_value` at all five mark surfaces each left the suite fully GREEN — the feature
# could be made completely inert without a single test noticing. These go through the
# real order path and the real mark path, against a real database.


async def _signal_for(db: AsyncSession, stock_id: int) -> Signal:
    """A ₹39 BUY with a ₹2 stop — the SRTL price shape. Two scoring factors so the ACTIVE
    entry-diversity gate does not reject it for an unrelated reason."""
    now = datetime.now(tz=UTC)
    sig = Signal(
        stock_id=stock_id,
        direction="BUY",
        classification="swing",
        timeframe="1d",
        entry_price="39.0000",
        stop_loss="37.0000",
        take_profit="45.0000",
        suggested_qty=100,
        confidence_pct=80,
        factor_scores={
            "DOW_TREND": {"weight": 20, "score": 0.8, "explanation": "uptrend"},
            "MACD_CROSS": {"weight": 15, "score": 0.6, "explanation": "bull cross"},
        },
        headline="BUY PARTICIPATION TEST",
        status="active",
        validity_until=now + timedelta(days=5),
        created_at=now,
    )
    db.add(sig)
    await db.flush()
    return sig


async def _seed_adv(
    db: AsyncSession, stock_id: int, close: str, volume: int, *, sessions: int = 20
) -> None:
    """`sessions` completed daily bars, so `load_median_traded_values` returns a median
    instead of treating the stock as unknown. 20 is `paper_participation_lookback`;
    fewer and the model correctly fails open, which is why no existing fixture triggers
    it."""
    start = date(2026, 7, 1)
    for i in range(sessions):
        d = start + timedelta(days=i)
        db.add(
            OhlcvDaily(
                time=datetime(d.year, d.month, d.day, 10, 0, tzinfo=UTC),
                stock_id=stock_id,
                open=Decimal(close), high=Decimal(close),
                low=Decimal(close), close=Decimal(close),
                volume=volume, is_complete=True,
            )
        )
    await db.flush()


class TestTheOrderPathSeam:
    """Kills the `adv = None` and `if fill.model == "spread"` mutations."""

    async def test_a_thin_stock_order_records_participation_and_is_sized_down(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """₹39 stock trading ~₹5 lakh a day, NO live book (so the FLAT path) — the SRTL
        shape. The order must (a) stamp a non-zero participation on its fill telemetry and
        (b) ship FEWER shares than the same order in a liquid name, because the impact
        widens |fill − SL| and risk-first sizing holds the budget."""
        monkeypatch.setattr(settings, "paper_slippage_bps", 2.0)
        monkeypatch.setattr(settings, "paper_participation_enabled", True)

        user = await create_test_user(db, email="thin@example.com")
        thin = await make_stock(db, symbol="THINSRTL")
        deep = await make_stock(db, symbol="DEEPLIQ")
        # ⚠ ₹1 lakh/day, not ₹5 lakh: on a ₹39 stock one ₹0.05 tick is 12.8 bps, so a
        # participation impact SMALLER than that rounds to the same tick and the size does
        # not move. The first version of this test used ₹5 lakh (≈5.8 bps) and failed for
        # that reason — the tick grid, not the model.
        await _seed_adv(db, thin.id, "39", 2_564)         # ≈ ₹1 lakh/day
        await _seed_adv(db, deep.id, "39", 25_641_025)    # ≈ ₹100 crore/day
        sig_thin = await _signal_for(db, thin.id)
        sig_deep = await _signal_for(db, deep.id)
        await db.commit()

        order_thin, pos_thin = await place_paper_order(db, user, sig_thin, side="BUY")
        order_deep, pos_deep = await place_paper_order(db, user, sig_deep, side="BUY")
        await db.commit()

        fill_thin = order_thin.broker_payload["fill"]
        fill_deep = order_deep.broker_payload["fill"]
        # (a) the audit trail records it — kills `adv = None`
        assert Decimal(fill_thin["participation_bps"]) > Decimal("1")
        assert Decimal(fill_deep["participation_bps"]) < Decimal("0.01")
        # (b) it reaches the SIZE — kills the `model == "spread"` refinement gate, since
        #     neither of these orders has a live book at all.
        assert fill_thin["model"] == "flat"
        assert pos_thin.quantity < pos_deep.quantity

    async def test_risk_still_respects_the_budget_after_refinement(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The refinement re-prices at the FINAL size, so the recorded entry belongs to the
        quantity shipped. The invariant that must survive: realised risk ≤ the budget."""
        monkeypatch.setattr(settings, "paper_slippage_bps", 2.0)
        monkeypatch.setattr(settings, "paper_participation_enabled", True)

        user = await create_test_user(db, email="budget@example.com")
        thin = await make_stock(db, symbol="THINBUD")
        await _seed_adv(db, thin.id, "39", 5_128)  # ≈ ₹2 lakh/day — very thin
        sig = await _signal_for(db, thin.id)
        await db.commit()

        _order, pos = await place_paper_order(db, user, sig, side="BUY")
        await db.commit()

        entry = Decimal(str(pos.avg_entry_price))
        stop = Decimal(str(pos.current_sl))
        budget = Decimal("100000") * Decimal("2") / 100
        assert pos.quantity * (entry - stop) <= budget

    async def test_the_recorded_price_belongs_to_the_recorded_size(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The A37 sizing defect: the order recorded `fill(q1)` while shipping `q2`, so on
        a thin name the entry was priced for an order up to 16.8× larger. Re-deriving the
        fill from the SHIPPED quantity must now reproduce the recorded price."""
        monkeypatch.setattr(settings, "paper_slippage_bps", 2.0)
        monkeypatch.setattr(settings, "paper_participation_enabled", True)

        user = await create_test_user(db, email="reprice@example.com")
        thin = await make_stock(db, symbol="THINREP")
        await _seed_adv(db, thin.id, "39", 5_128)
        sig = await _signal_for(db, thin.id)
        await db.commit()

        _order, pos = await place_paper_order(db, user, sig, side="BUY")
        await db.commit()

        adv = (await load_median_traded_values(db, [thin.id], lookback=20))[thin.id]
        redone = simulate_fill(
            Decimal("39"), "BUY", depth=None, quantity=pos.quantity, adv_value=adv
        )
        assert Decimal(str(pos.avg_entry_price)) == redone.fill


class TestTheMarkSeam:
    """Kills the "drop adv_value at the mark surfaces" mutation."""

    async def test_unrealized_pnl_charges_participation(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A31: exiting a fifth of a day's volume costs what entering cost. A long in a
        thin name must mark WORSE than the identical long in a liquid one."""
        monkeypatch.setattr(settings, "paper_slippage_bps", 2.0)
        monkeypatch.setattr(settings, "paper_participation_enabled", True)

        user = await create_test_user(db, email="markseam@example.com")
        thin = await make_stock(db, symbol="THINMARK")
        deep = await make_stock(db, symbol="DEEPMARK")
        await _seed_adv(db, thin.id, "39", 12_820)
        await _seed_adv(db, deep.id, "39", 25_641_025)
        positions = []
        for st in (thin, deep):
            pos = Position(
                user_id=user.id, stock_id=st.id, mode="paper", side="LONG", quantity=2000,
                avg_entry_price=Decimal("39"), current_sl=Decimal("37"),
                trail_state="none", realized_pnl=Decimal("0"),
                opened_at=datetime(2026, 8, 3, 4, 0, tzinfo=UTC),
            )
            db.add(pos)
            positions.append(pos)
        await db.commit()

        advs = await load_median_traded_values(db, [thin.id, deep.id], lookback=20)
        for pos in positions:
            await update_position_pnl(
                db, pos, price=Decimal("40"), adv_value=advs.get(pos.stock_id)
            )
        thin_pos, deep_pos = positions
        assert thin_pos.unrealized_pnl is not None and deep_pos.unrealized_pnl is not None
        assert thin_pos.unrealized_pnl < deep_pos.unrealized_pnl

    async def test_dropping_the_adv_makes_the_mark_more_optimistic(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Directly pins the mutation: the SAME position, marked with and without its ADV.
        Without it the book reads better than it is."""
        monkeypatch.setattr(settings, "paper_slippage_bps", 2.0)
        monkeypatch.setattr(settings, "paper_participation_enabled", True)

        user = await create_test_user(db, email="advdrop@example.com")
        thin = await make_stock(db, symbol="THINDROP")
        await _seed_adv(db, thin.id, "39", 12_820)
        pos = Position(
            user_id=user.id, stock_id=thin.id, mode="paper", side="LONG", quantity=2000,
            avg_entry_price=Decimal("39"), current_sl=Decimal("37"),
            trail_state="none", realized_pnl=Decimal("0"),
            opened_at=datetime(2026, 8, 3, 4, 0, tzinfo=UTC),
        )
        db.add(pos)
        await db.commit()

        adv = (await load_median_traded_values(db, [thin.id], lookback=20))[thin.id]
        await update_position_pnl(db, pos, price=Decimal("40"), adv_value=adv)
        with_adv = pos.unrealized_pnl
        await update_position_pnl(db, pos, price=Decimal("40"), adv_value=None)
        without = pos.unrealized_pnl
        assert with_adv is not None and without is not None
        assert with_adv < without

    async def test_the_open_book_mtm_charges_participation(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The report surface, through its real entry point."""
        monkeypatch.setattr(settings, "paper_slippage_bps", 2.0)
        monkeypatch.setattr(settings, "paper_participation_enabled", True)

        user = await create_test_user(db, email="mtmseam@example.com")
        thin = await make_stock(db, symbol="THINMTM")
        await _seed_adv(db, thin.id, "39", 12_820)
        opened = datetime(2026, 8, 3, 4, 0, tzinfo=UTC)
        db.add(Position(
            user_id=user.id, stock_id=thin.id, mode="paper", side="LONG", quantity=2000,
            avg_entry_price=Decimal("39"), current_sl=Decimal("37"),
            trail_state="none", realized_pnl=Decimal("0"), opened_at=opened,
        ))
        db.add(Ohlcv1m(
            time=opened + timedelta(minutes=5), stock_id=thin.id,
            open=Decimal("40"), high=Decimal("40"), low=Decimal("40"),
            close=Decimal("40"), volume=1, is_complete=True,
        ))
        await db.commit()

        cutoff = datetime(2026, 8, 3, 4, 30, tzinfo=UTC)
        charged = await _open_book_mtm(db, user.id, cutoff)
        monkeypatch.setattr(settings, "paper_participation_enabled", False)
        plain = await _open_book_mtm(db, user.id, cutoff)
        assert charged < plain

