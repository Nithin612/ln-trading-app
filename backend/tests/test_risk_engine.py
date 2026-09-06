"""Phase 7.1 — the RiskEngine, and the equivalence pin that makes the refactor safe.

The point of this file is the FIRST class. 7.1 moved every pre-trade rule out of
`place_order` into `app/trading/risk_engine.py`; the plan's requirement was that it be
*equivalence-pinned* — identical verdicts to the pre-7.1 chain before anything moved.

So `_legacy_pre_trade` below is a deliberate, literal transcription of the old sequence
(breaker → lookup → status → restrictions), written against the same underlying
functions, and the pin asserts the two agree case by case. A test that only exercised
the new engine would confirm the new engine is self-consistent, which is not the claim
being made.

The A38 precedent is the standard this is trying to meet: that refactor proved itself
with differential fuzz over 30,000 order-path cases and 0 block diffs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.core.config import Settings, get_settings
from app.models.signal import Signal
from app.models.stock import Stock
from app.models.trading import Position
from app.models.user import User
from app.signals import restrictions
from app.trading import risk_engine as rx
from app.trading.circuit_breaker import check_circuit_breaker
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock

# ── fixtures ──────────────────────────────────────────────────────────────────


async def _make_user(
    db: AsyncSession,
    *,
    email: str = "risk@example.com",
    capital: Decimal = Decimal("100000"),
    daily_loss_pct: Decimal = Decimal("3.00"),
    max_trades: int = 10,
) -> User:
    from app.core.security import hash_password

    user = User(
        email=email,
        password_hash=hash_password("pass123"),
        full_name="Risk Tester",
        capital_inr=capital,
        risk_per_trade_pct=Decimal("2.0"),
        daily_loss_limit_pct=daily_loss_pct,
        max_trades_per_day=max_trades,
        allow_offmarket_entry=True,
    )
    db.add(user)
    await db.flush()
    return user


async def _make_signal(
    db: AsyncSession,
    stock_id: int,
    *,
    direction: str = "BUY",
    entry: str = "500.0000",
    sl: str = "480.0000",
    tp: str = "540.0000",
    status: str = "active",
) -> Signal:
    now = datetime.now(tz=UTC)
    sig = Signal(
        stock_id=stock_id,
        direction=direction,
        classification="swing",
        timeframe="1d",
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
        suggested_qty=100,
        confidence_pct=80,
        # ≥2 scoring factors — the entry-diversity gate is ACTIVE, so a single-factor
        # signal would be blocked for a reason unrelated to what is under test.
        factor_scores={
            "DOW_TREND": {"weight": 20, "score": 0.8, "explanation": "uptrend"},
            "MACD_CROSS": {"weight": 15, "score": 0.6, "explanation": "bull cross"},
        },
        headline=f"{direction} RISK@{entry}",
        status=status,
        validity_until=now + timedelta(days=5),
        created_at=now,
    )
    db.add(sig)
    await db.flush()
    return sig


async def _closed_position(
    db: AsyncSession, user: User, stock: Stock, signal: Signal, *, pnl: Decimal
) -> Position:
    now = datetime.now(tz=UTC)
    pos = Position(
        user_id=user.id, stock_id=stock.id, mode="paper", side="LONG",
        quantity=100, avg_entry_price=Decimal("500"), current_sl=Decimal("480"),
        realized_pnl=pnl, opened_at=now, closed_at=now, signal_id=signal.id,
    )
    db.add(pos)
    await db.flush()
    return pos


async def _open_position(
    db: AsyncSession, user: User, stock: Stock, signal: Signal | None,
    *, qty: int = 100, entry: Decimal = Decimal("500"),
    current_sl: Decimal | None = Decimal("480"), side: str = "LONG",
) -> Position:
    pos = Position(
        user_id=user.id, stock_id=stock.id, mode="paper", side=side,
        quantity=qty, avg_entry_price=entry, current_sl=current_sl,
        realized_pnl=Decimal("0"), opened_at=datetime.now(tz=UTC),
        signal_id=signal.id if signal is not None else None,
    )
    db.add(pos)
    await db.flush()
    return pos


# ── the legacy chain, transcribed ─────────────────────────────────────────────


async def _legacy_pre_trade(
    db: AsyncSession, user: User, signal_id: str, *, side: str, allow_offmarket: bool
) -> tuple[int, str] | None:
    """The pre-7.1 `place_order` prefix, verbatim, returning (status_code, detail).

    `None` means "no refusal — proceed to the broker". Kept as a literal transcription
    rather than a call into the new engine, because a pin that calls the thing it is
    pinning proves nothing.
    """
    triggered, reason = await check_circuit_breaker(db, user)
    if triggered:
        return (409, reason)

    signal = await db.get(Signal, signal_id)
    if not signal:
        return (404, "Signal not found")
    if signal.status not in ("active",):
        return (409, f"Signal is {signal.status}, not active")

    from app.signals.restriction_context import load_restriction_context

    cfg = restrictions.config_from_settings()
    ctx = await load_restriction_context(
        db, signal, side, cfg, allow_offmarket=allow_offmarket
    )
    outcome = restrictions.check(ctx, cfg, enforced_by=restrictions.EnforcedBy.OVERLAY)
    if outcome.blocked:
        return (409, outcome.reason or "")
    return None


def _verdict_as_legacy(v: rx.RiskVerdict) -> tuple[int, str] | None:
    """Map a RiskVerdict onto the legacy (code, detail) shape for comparison."""
    if v.allowed:
        return None
    code = 404 if v.rule == rx.RULE_SIGNAL_MISSING else 409
    return (code, v.reason or "")


# ── 1. the equivalence pin ────────────────────────────────────────────────────


class TestEquivalenceWithLegacyChain:
    """⭐ The claim 7.1 rests on: the engine refuses exactly what the old chain refused."""

    async def test_clean_signal_passes_both(self, db: AsyncSession) -> None:
        user = await _make_user(db)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await db.commit()

        legacy = await _legacy_pre_trade(
            db, user, signal.id, side="BUY", allow_offmarket=True
        )
        verdict = await rx.check_pre_trade(
            db, user, signal, side="BUY", allow_offmarket=True
        )
        assert legacy is None
        assert _verdict_as_legacy(verdict) == legacy

    async def test_tripped_breaker_matches(self, db: AsyncSession) -> None:
        user = await _make_user(db, daily_loss_pct=Decimal("3.00"))
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await _closed_position(db, user, stock, signal, pnl=Decimal("-3500"))
        await db.commit()

        legacy = await _legacy_pre_trade(
            db, user, signal.id, side="BUY", allow_offmarket=True
        )
        verdict = await rx.check_pre_trade(
            db, user, signal, side="BUY", allow_offmarket=True
        )
        assert legacy is not None and legacy[0] == 409
        assert "Daily loss limit reached" in legacy[1]
        assert _verdict_as_legacy(verdict) == legacy
        assert verdict.rule == rx.RULE_BREAKER

    async def test_non_active_signal_matches(self, db: AsyncSession) -> None:
        user = await _make_user(db)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id, status="expired")
        await db.commit()

        legacy = await _legacy_pre_trade(
            db, user, signal.id, side="BUY", allow_offmarket=True
        )
        verdict = await rx.check_pre_trade(
            db, user, signal, side="BUY", allow_offmarket=True
        )
        assert legacy == (409, "Signal is expired, not active")
        assert _verdict_as_legacy(verdict) == legacy

    async def test_missing_signal_matches(self, db: AsyncSession) -> None:
        user = await _make_user(db)
        await db.commit()
        missing = "00000000-0000-0000-0000-000000000000"

        legacy = await _legacy_pre_trade(
            db, user, missing, side="BUY", allow_offmarket=True
        )
        verdict = await rx.check_pre_trade(
            db, user, None, side="BUY", allow_offmarket=True
        )
        assert legacy == (404, "Signal not found")
        assert _verdict_as_legacy(verdict) == legacy

    async def test_single_factor_signal_blocked_by_both(self, db: AsyncSession) -> None:
        """The entry-diversity gate is ACTIVE, so this is a live block on both paths."""
        user = await _make_user(db)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        signal.factor_scores = {
            "RSI_DIVERGENCE": {"weight": 20, "score": 0.8, "explanation": "solo"}
        }
        await db.flush()
        await db.commit()

        legacy = await _legacy_pre_trade(
            db, user, signal.id, side="BUY", allow_offmarket=True
        )
        verdict = await rx.check_pre_trade(
            db, user, signal, side="BUY", allow_offmarket=True
        )
        assert legacy is not None and legacy[0] == 409
        assert _verdict_as_legacy(verdict) == legacy
        assert verdict.rule == rx.RULE_ELIGIBILITY

    async def test_breaker_beats_missing_signal(self, db: AsyncSession) -> None:
        """⭐ The ordering quirk this refactor could easily have inverted.

        The breaker runs BEFORE the signal is looked up, so an unknown id while the
        breaker is tripped answers 409, not 404. Hoisting the lookup into the caller to
        get a non-optional `signal` argument would have silently flipped this — which is
        why "does the signal exist" is a RULE inside the engine rather than a caller-side
        404.
        """
        user = await _make_user(db, daily_loss_pct=Decimal("3.00"))
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await _closed_position(db, user, stock, signal, pnl=Decimal("-3500"))
        await db.commit()
        missing = "00000000-0000-0000-0000-000000000000"

        legacy = await _legacy_pre_trade(
            db, user, missing, side="BUY", allow_offmarket=True
        )
        verdict = await rx.check_pre_trade(
            db, user, None, side="BUY", allow_offmarket=True
        )
        assert legacy is not None
        assert legacy[0] == 409, "breaker must win over the unknown id"
        assert _verdict_as_legacy(verdict) == legacy
        assert verdict.rule == rx.RULE_BREAKER


# ── 2. A13 — the breaker cannot be suppressed ─────────────────────────────────


class TestBreakerUnsuppressible:
    """A13. The daily-loss breaker is never disabled, weakened, or made
    configurable-off — not for tests, not on request (hard constraint).

    7.1 moves the breaker INTO the RiskEngine, which is exactly the moment that
    guarantee could be quietly lost, so it is pinned here rather than left to the
    call site that happens to invoke it today.
    """

    def test_breaker_precedes_every_per_signal_rule(self) -> None:
        """The breaker is an ACCOUNT-level rail: when it has tripped, nothing about this
        particular signal matters, so no per-signal rule may be consulted first.

        ⚠ This assertion used to read `PRE_TRADE_RULES[0] == RULE_BREAKER`, and 7.4
        legitimately broke it by putting the KILL SWITCH first. That was the test doing
        its job — but index 0 was a stricter proxy than the invariant this class is
        actually defending, which its own message already stated. Only another
        account-level rail may precede the breaker; a per-signal rule never may, and the
        second assertion below is what pins that as the ordering evolves.
        """
        account_level = {rx.RULE_KILL_SWITCH, rx.RULE_BREAKER}
        per_signal = [r for r in rx.PRE_TRADE_RULES if r not in account_level]

        idx = rx.PRE_TRADE_RULES.index(rx.RULE_BREAKER)
        for rule in per_signal:
            assert rx.PRE_TRADE_RULES.index(rule) > idx, (
                f"{rule} is a per-signal rule and must not be consulted before the "
                "account-level breaker"
            )
        assert set(rx.PRE_TRADE_RULES[:idx]) <= account_level, (
            "only another account-level rail may precede the breaker"
        )

    def test_no_setting_can_disable_it(self) -> None:
        """There is no knob. The absence IS the guarantee, so assert the absence.

        A `*_mode` for the breaker would let it be set to `off` by the same mechanism
        every selection overlay uses — and the whole point is that it is not one of them.
        """
        suspicious = {
            name
            for name in Settings.model_fields
            if ("breaker" in name or "daily_loss" in name)
            and (name.endswith("_mode") or name.endswith("_enabled"))
        }
        assert suspicious == set(), (
            f"the circuit breaker must have no enable/mode knob, found {suspicious}"
        )

    async def test_denies_with_every_gate_mode_off(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Turning every *other* rule off must not reach the breaker."""
        settings = get_settings()
        for name in Settings.model_fields:
            if name.endswith("_gate_mode"):
                monkeypatch.setattr(settings, name, "off", raising=False)
        monkeypatch.setattr(settings, "heat_cap_mode", "off", raising=False)

        user = await _make_user(db, daily_loss_pct=Decimal("3.00"))
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await _closed_position(db, user, stock, signal, pnl=Decimal("-3500"))
        await db.commit()

        verdict = await rx.check_pre_trade(
            db, user, signal, side="BUY", allow_offmarket=True
        )
        assert verdict.denied
        assert verdict.rule == rx.RULE_BREAKER

    async def test_max_trades_also_denies(self, db: AsyncSession) -> None:
        """The breaker has two limbs; both must refuse."""
        user = await _make_user(db, max_trades=2)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        for _ in range(2):
            await _open_position(db, user, stock, signal)
        await db.commit()

        verdict = await rx.check_pre_trade(
            db, user, signal, side="BUY", allow_offmarket=True
        )
        assert verdict.denied
        assert verdict.rule == rx.RULE_BREAKER
        assert "Max trades per day" in (verdict.reason or "")


# ── 3. the heat primitive ─────────────────────────────────────────────────────


class TestAdmissionRisk:
    def test_long_risk_is_entry_minus_stop(self) -> None:
        assert rx.admission_risk("LONG", Decimal("500"), Decimal("480"), 100) == Decimal(
            "2000"
        )

    def test_short_risk_is_stop_minus_entry(self) -> None:
        assert rx.admission_risk("SHORT", Decimal("480"), Decimal("500"), 100) == Decimal(
            "2000"
        )

    def test_stop_past_entry_clamps_to_zero(self) -> None:
        """A stop already through entry exposes nothing and must not hold budget.

        Not a rounding nicety: an un-clamped negative would CREATE budget, so a book
        full of profitable trailed positions could admit unlimited new risk.
        """
        assert rx.admission_risk("LONG", Decimal("500"), Decimal("520"), 100) == Decimal(0)
        assert rx.admission_risk("SHORT", Decimal("520"), Decimal("500"), 100) == Decimal(0)

    def test_matches_the_counterfactual_primitive(self) -> None:
        """The cap and the counterfactual that justified it must mean the same thing."""
        from app.services.heat_counterfactual import _risk

        for side, entry, stop, qty in [
            ("LONG", "500", "480", 100),
            ("SHORT", "480", "500", 250),
            ("LONG", "100", "120", 7),
        ]:
            assert rx.admission_risk(side, Decimal(entry), Decimal(stop), qty) == _risk(
                side, Decimal(entry), Decimal(stop), qty
            )


class TestOpenHeat:
    async def test_sums_across_open_positions(self, db: AsyncSession) -> None:
        user = await _make_user(db)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)  # commit SL 480, entry 500
        await _open_position(db, user, stock, signal, qty=100)
        await _open_position(db, user, stock, signal, qty=50)
        await db.commit()

        held = await rx.open_heat(db, user)
        assert held.positions == 2
        assert held.total == Decimal("3000")  # 100×20 + 50×20
        assert held.unmeasurable == 0

    async def test_uses_commit_stop_not_trailed_stop(self, db: AsyncSession) -> None:
        """⭐ The trailed stop would let a book gain budget merely by being right.

        The position's `current_sl` has trailed up to 495 (₹5 of risk), but admission
        risk is measured from the signal's COMMIT stop of 480 (₹20). Measuring from the
        trail would report ₹500 of heat where ₹2,000 was actually admitted, and the cap
        would silently loosen as the book moved in its favour.
        """
        user = await _make_user(db)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id, sl="480.0000")
        await _open_position(db, user, stock, signal, qty=100, current_sl=Decimal("495"))
        await db.commit()

        held = await rx.open_heat(db, user)
        assert held.total == Decimal("2000"), "must use the commit stop (480), not 495"

    async def test_falls_back_to_current_sl_when_signal_is_gone(
        self, db: AsyncSession
    ) -> None:
        """`signal_id` is SET NULL on delete; a fallback beats dropping the leg."""
        user = await _make_user(db)
        stock = await make_stock(db)
        await _open_position(db, user, stock, None, qty=100, current_sl=Decimal("470"))
        await db.commit()

        held = await rx.open_heat(db, user)
        assert held.total == Decimal("3000")
        assert held.unmeasurable == 0

    async def test_no_recoverable_stop_is_counted_unmeasurable(
        self, db: AsyncSession
    ) -> None:
        user = await _make_user(db)
        stock = await make_stock(db)
        await _open_position(db, user, stock, None, qty=100, current_sl=None)
        await db.commit()

        held = await rx.open_heat(db, user)
        assert held.unmeasurable == 1
        assert held.total == Decimal(0)

    async def test_closed_positions_are_excluded(self, db: AsyncSession) -> None:
        user = await _make_user(db)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await _closed_position(db, user, stock, signal, pnl=Decimal("-100"))
        await db.commit()

        held = await rx.open_heat(db, user)
        assert held.positions == 0
        assert held.total == Decimal(0)


# ── 4. the heat cap ───────────────────────────────────────────────────────────


class TestHeatCap:
    async def test_off_is_a_true_no_op(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Default `off` must not even query — cycle 1 behaviour is byte-for-byte prior."""
        monkeypatch.setattr(get_settings(), "heat_cap_mode", "off", raising=False)
        user = await _make_user(db, capital=Decimal("100000"))
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        # Far past a 6% (₹6,000) cap.
        await _open_position(db, user, stock, signal, qty=1000)  # ₹20,000 of heat
        await db.commit()

        verdict = await rx.check_sizing(
            db, user, side="LONG", qty=100, fill_price=Decimal("500"),
            stop_loss=Decimal("480"),
        )
        assert verdict.allowed
        assert verdict.stamps == {}

    async def test_active_denies_over_cap(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(get_settings(), "heat_cap_mode", "active", raising=False)
        monkeypatch.setattr(get_settings(), "heat_cap_pct", 6.0, raising=False)
        user = await _make_user(db, capital=Decimal("100000"))  # cap = ₹6,000
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await _open_position(db, user, stock, signal, qty=250)  # ₹5,000 held
        await db.commit()

        verdict = await rx.check_sizing(
            db, user, side="LONG", qty=100, fill_price=Decimal("500"),
            stop_loss=Decimal("480"),  # ₹2,000 incoming ⇒ 7,000 > 6,000
        )
        assert verdict.denied
        assert verdict.rule == rx.RULE_HEAT_CAP
        assert "₹6,000" in (verdict.reason or "")

    async def test_active_allows_within_cap(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(get_settings(), "heat_cap_mode", "active", raising=False)
        monkeypatch.setattr(get_settings(), "heat_cap_pct", 6.0, raising=False)
        user = await _make_user(db, capital=Decimal("100000"))
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await _open_position(db, user, stock, signal, qty=100)  # ₹2,000 held
        await db.commit()

        verdict = await rx.check_sizing(
            db, user, side="LONG", qty=100, fill_price=Decimal("500"),
            stop_loss=Decimal("480"),  # ₹2,000 ⇒ 4,000 ≤ 6,000
        )
        assert verdict.allowed

    async def test_shadow_allows_but_stamps(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(get_settings(), "heat_cap_mode", "shadow", raising=False)
        monkeypatch.setattr(get_settings(), "heat_cap_pct", 6.0, raising=False)
        user = await _make_user(db, capital=Decimal("100000"))
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await _open_position(db, user, stock, signal, qty=250)
        await db.commit()

        verdict = await rx.check_sizing(
            db, user, side="LONG", qty=100, fill_price=Decimal("500"),
            stop_loss=Decimal("480"),
        )
        assert verdict.allowed, "shadow must never suppress"
        assert verdict.stamps["heat_cap"]["would_block"] is True  # type: ignore[index]
        assert verdict.stamps["heat_cap"]["mode"] == "shadow"  # type: ignore[index]

    async def test_fails_closed_on_unmeasurable_risk(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """⭐ The departure from the selection overlays, and the reason for it.

        Every selection gate fails OPEN: on uncertainty, let the trade through, because
        the error to avoid is suppressing a good one. A risk rail inverts that — the
        error to avoid is taking risk you cannot count — so an open position with no
        recoverable stop refuses the next entry instead of contributing zero.
        """
        monkeypatch.setattr(get_settings(), "heat_cap_mode", "active", raising=False)
        user = await _make_user(db, capital=Decimal("100000"))
        stock = await make_stock(db)
        await _open_position(db, user, stock, None, qty=1, current_sl=None)
        await db.commit()

        verdict = await rx.check_sizing(
            db, user, side="LONG", qty=1, fill_price=Decimal("500"),
            stop_loss=Decimal("499"),  # ₹1 — trivially inside any cap
        )
        assert verdict.denied, "unmeasurable open risk must refuse, not count as zero"
        assert verdict.rule == rx.RULE_HEAT_CAP
        assert "cannot be measured" in (verdict.reason or "")

    async def test_uses_live_capital_not_the_sampling_denominator(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`paper_sampling_capital_inr` is reporting-only and 5× larger.

        If the cap read it, the effective limit would silently quintuple — the exact
        misapplication the setting's own docstring warns about.
        """
        monkeypatch.setattr(get_settings(), "heat_cap_mode", "active", raising=False)
        monkeypatch.setattr(get_settings(), "heat_cap_pct", 6.0, raising=False)
        monkeypatch.setattr(
            get_settings(), "paper_sampling_capital_inr", 500000.0, raising=False
        )
        user = await _make_user(db, capital=Decimal("100000"))
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await _open_position(db, user, stock, signal, qty=250)  # ₹5,000
        await db.commit()

        verdict = await rx.check_sizing(
            db, user, side="LONG", qty=100, fill_price=Decimal("500"),
            stop_loss=Decimal("480"),  # ₹2,000 ⇒ 7,000
        )
        # Against ₹1L the cap is ₹6,000 and this is refused; against ₹5L it would be
        # ₹30,000 and sail through.
        assert verdict.denied, "the cap must use capital_inr, never the sampling scale"


# ── 5. the notional cap keeps ONE definition ──────────────────────────────────


class TestNotionalCapSingleDefinition:
    async def test_engine_and_broker_agree(self, db: AsyncSession) -> None:
        """W2: the broker's raising wrapper must be the engine's rule, not a copy."""
        from app.broker.paper_broker import PaperOrderError, _check_notional_cap

        user = await _make_user(db, capital=Decimal("100000"))
        await db.commit()

        kwargs = {
            "qty": 5000, "fill_price": Decimal("500"),
            "existing_qty": 0, "existing_entry": None,
        }
        reason = rx.notional_cap_reason(user, **kwargs)  # type: ignore[arg-type]
        assert reason is not None, "₹25L on ₹1L must breach"

        with pytest.raises(PaperOrderError) as exc:
            _check_notional_cap(user, **kwargs)  # type: ignore[arg-type]
        assert str(exc.value) == reason, "broker and engine must give the same words"

    async def test_within_cap_is_none(self, db: AsyncSession) -> None:
        user = await _make_user(db, capital=Decimal("100000"))
        await db.commit()
        assert (
            rx.notional_cap_reason(
                user, qty=100, fill_price=Decimal("500"),
                existing_qty=0, existing_entry=None,
            )
            is None
        )

    async def test_existing_position_counts_toward_the_cap(
        self, db: AsyncSession
    ) -> None:
        """A repeat entry must not stack past the cap."""
        user = await _make_user(db, capital=Decimal("100000"))
        await db.commit()
        assert (
            rx.notional_cap_reason(
                user, qty=100, fill_price=Decimal("500"),
                existing_qty=150, existing_entry=Decimal("500"),
            )
            is not None
        ), "75,000 held + 50,000 wanted = 125,000 > 100,000"

    async def test_sizing_phase_reports_notional_before_heat(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Order within the phase is part of the contract, so pin it."""
        monkeypatch.setattr(get_settings(), "heat_cap_mode", "active", raising=False)
        user = await _make_user(db, capital=Decimal("100000"))
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        await _open_position(db, user, stock, signal, qty=1000)  # way over heat too
        await db.commit()

        verdict = await rx.check_sizing(
            db, user, side="LONG", qty=5000, fill_price=Decimal("500"),
            stop_loss=Decimal("480"),
        )
        assert verdict.denied
        assert verdict.rule == rx.RULE_NOTIONAL_CAP, "notional is declared first"


# ── 6. the rule vocabulary is declared once ───────────────────────────────────


class TestRuleVocabulary:
    def test_all_rules_is_the_two_phases(self) -> None:
        assert rx.ALL_RULES == rx.PRE_TRADE_RULES + rx.SIZING_RULES

    def test_no_duplicate_rule_names(self) -> None:
        assert len(set(rx.ALL_RULES)) == len(rx.ALL_RULES)

    def test_every_rule_name_is_reachable(self) -> None:
        """A rule constant nobody can return is dead vocabulary — the T7 shape."""
        import inspect

        src = inspect.getsource(rx)
        for rule in rx.ALL_RULES:
            const = next(
                n for n, v in vars(rx).items() if n.startswith("RULE_") and v == rule
            )
            # Declared, listed in a phase tuple, AND used in a _deny/RiskVerdict call.
            assert src.count(const) >= 3, f"{const} is listed but never returned"

    def test_heat_cap_mode_uses_the_shared_vocabulary(self) -> None:
        """The T7 lesson: a moded knob that invents its own values falls through as off."""
        from typing import Literal, get_args, get_origin

        ann = Settings.model_fields["heat_cap_mode"].annotation
        assert get_origin(ann) is Literal
        assert set(get_args(ann)) == set(restrictions.GATE_MODES)
