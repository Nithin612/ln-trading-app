"""Order-eligibility PREVIEW on the display path (2026-09-02).

The bug this closes: `place_order` runs seven eligibility overlays and 409s on the
first ACTIVE rejection, but `GET /signals/active` ran NONE of them — so 41 of 204
listed signals rendered a Buy button that could only fail. These tests pin that the
list's verdict AGREES with the order path's, and that the wording is identical (the
reason is passed through verbatim, not re-phrased into drift).
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.core.config import settings
from app.models.signal import Signal
from app.signals import eligibility, regime_guard
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock

_TWO_FACTORS = {
    "DOW_TREND": {"weight": 20, "score": 0.8, "explanation": "uptrend"},
    "MACD_CROSS": {"weight": 15, "score": 0.6, "explanation": "bull cross"},
}
_ONE_FACTOR = {
    "RSI_DIVERGENCE": {"weight": 20, "score": 0.8, "explanation": "bullish div"},
    "MACD_CROSS": {"weight": 15, "score": 0.0, "explanation": "no cross"},
}

_THRESHOLDS = dict(
    min_scoring_factors=2,
    max_dominant_share=Decimal("0.9"),
    min_sl_atr_mult=Decimal("1.0"),
)

_ALL_OFF = dict.fromkeys(eligibility.COVERED_GATES + eligibility.UNCOVERED_GATES, "off")


def _modes(**over: str) -> dict[str, str]:
    """A COMPLETE mode map (every gate), overridden per test. Complete on purpose:
    `preview` must be handed every gate's mode so it can report an ACTIVE one it cannot
    judge — passing a partial map was the bug bug-hunter found on 2026-09-02."""
    m = dict(_ALL_OFF)
    m.update(over)
    return m


def _signal(**kw: object) -> Signal:
    """An UNSAVED Signal — `eligibility.preview` is pure, so no DB is needed."""
    now = datetime.now(tz=UTC)
    defaults: dict[str, object] = dict(
        stock_id=1,
        direction="BUY",
        classification="swing",
        timeframe="1d",
        entry_price="500.0000",
        stop_loss="480.0000",
        take_profit="560.0000",
        suggested_qty=100,
        confidence_pct=80,
        factor_scores=_TWO_FACTORS,
        headline="BUY TEST",
        status="active",
        validity_until=now + timedelta(days=5),
        created_at=now,
        regime="trending (ADX≥25)",
    )
    defaults.update(kw)
    return Signal(**defaults)  # type: ignore[arg-type]


class TestPreviewPurity:
    def test_clean_signal_is_not_blocked(self) -> None:
        v = eligibility.preview(
            _signal(),
            market_price=Decimal("500"),  # above the ₹480 stop → tradeable
            modes=_modes(
                **{eligibility.GATE_REGIME: "active",
                  eligibility.GATE_DIVERSITY: "active",
                  eligibility.GATE_SL_ATR: "shadow"}
            ),
            **_THRESHOLDS,  # type: ignore[arg-type]
        )
        assert v.blocked is False
        assert v.gate is None and v.reason is None
        assert v.unassessed == ()

    def test_transitional_regime_blocked_when_regime_active(self) -> None:
        sig = _signal(regime="transitional (20–25)")
        v = eligibility.preview(
            sig,
            modes=_modes(
                **{eligibility.GATE_REGIME: "active",
                  eligibility.GATE_DIVERSITY: "active",
                  eligibility.GATE_SL_ATR: "shadow"}
            ),
            **_THRESHOLDS,  # type: ignore[arg-type]
        )
        assert v.blocked is True
        assert v.gate == eligibility.GATE_REGIME
        # Verbatim the order path's 409 detail — no re-wording, no drift.
        assert v.reason == regime_guard.order_block_reason(sig, "active")

    def test_transitional_regime_clear_when_regime_shadow(self) -> None:
        """The 2026-09-02 revert: in shadow the gate must be a true no-op here too,
        or the list would keep hiding what the order path now allows."""
        v = eligibility.preview(
            _signal(regime="transitional (20–25)"),
            modes=_modes(
                **{eligibility.GATE_REGIME: "shadow",
                  eligibility.GATE_DIVERSITY: "active",
                  eligibility.GATE_SL_ATR: "shadow"}
            ),
            **_THRESHOLDS,  # type: ignore[arg-type]
        )
        assert v.blocked is False

    def test_single_factor_blocked_by_diversity(self) -> None:
        v = eligibility.preview(
            _signal(factor_scores=_ONE_FACTOR),
            modes=_modes(
                **{eligibility.GATE_REGIME: "shadow",
                  eligibility.GATE_DIVERSITY: "active",
                  eligibility.GATE_SL_ATR: "shadow"}
            ),
            **_THRESHOLDS,  # type: ignore[arg-type]
        )
        assert v.blocked is True
        assert v.gate == eligibility.GATE_ENTRY_QUALITY
        assert v.reason is not None and "scoring factor" in v.reason

    def test_single_factor_clear_when_diversity_shadow(self) -> None:
        v = eligibility.preview(
            _signal(factor_scores=_ONE_FACTOR),
            modes=_modes(
                **{eligibility.GATE_REGIME: "shadow",
                  eligibility.GATE_DIVERSITY: "shadow",
                  eligibility.GATE_SL_ATR: "shadow"}
            ),
            **_THRESHOLDS,  # type: ignore[arg-type]
        )
        assert v.blocked is False

    def test_regime_is_reported_before_entry_quality(self) -> None:
        """Order must MIRROR the order path so the reason shown is the one actually
        hit first — a signal failing both reports the regime gate."""
        sig = _signal(regime="transitional (20–25)", factor_scores=_ONE_FACTOR)
        v = eligibility.preview(
            sig,
            modes=_modes(
                **{eligibility.GATE_REGIME: "active",
                  eligibility.GATE_DIVERSITY: "active",
                  eligibility.GATE_SL_ATR: "shadow"}
            ),
            **_THRESHOLDS,  # type: ignore[arg-type]
        )
        assert v.gate == eligibility.GATE_REGIME

    def test_unknown_regime_fails_open(self) -> None:
        """A gate that suppresses must never suppress on uncertainty."""
        v = eligibility.preview(
            _signal(regime=None, factor_scores=_TWO_FACTORS),
            modes=_modes(
                **{eligibility.GATE_REGIME: "active",
                  eligibility.GATE_DIVERSITY: "active",
                  eligibility.GATE_SL_ATR: "shadow"}
            ),
            **_THRESHOLDS,  # type: ignore[arg-type]
        )
        assert v.blocked is False

    def test_active_sl_atr_without_atr_is_reported_unassessed(self) -> None:
        """The list supplies no ATR, so an ACTIVE sl_atr gate cannot be judged here.
        That must surface in `unassessed` — 'unknown', never a silent 'clear'. This is
        the tripwire against the display/order drift returning."""
        v = eligibility.preview(
            _signal(),
            atr=None,
            market_price=Decimal("500"),
            modes=_modes(
                **{eligibility.GATE_REGIME: "shadow",
                  eligibility.GATE_DIVERSITY: "active",
                  eligibility.GATE_SL_ATR: "active"}
            ),
            **_THRESHOLDS,  # type: ignore[arg-type]
        )
        assert v.unassessed == ("entry_quality.sl_atr",)

    def test_sl_atr_blocks_when_atr_supplied(self) -> None:
        """With an ATR the tight-stop check works — a ₹20 stop on a ₹40-ATR name is
        half an ATR wide, well under the 1.0× floor."""
        v = eligibility.preview(
            _signal(),
            atr=Decimal("40"),
            market_price=Decimal("500"),
            modes=_modes(
                **{eligibility.GATE_REGIME: "shadow",
                  eligibility.GATE_DIVERSITY: "shadow",
                  eligibility.GATE_SL_ATR: "active"}
            ),
            **_THRESHOLDS,  # type: ignore[arg-type]
        )
        assert v.blocked is True
        assert v.gate == eligibility.GATE_ENTRY_QUALITY
        assert v.unassessed == ()


class TestUnassessedTripwire:
    """The `unassessed` field is the ENFORCEMENT of "extend this module in the same
    commit", not a comment. bug-hunter (2026-09-02) caught the first version claiming a
    safety net it did not have: only sl_atr was ever checked, so flipping the liquidity
    gate active produced `blocked=False` on a row the order path 409s. One case per
    uncovered gate keeps that honest."""

    @pytest.mark.parametrize("gate", eligibility.UNCOVERED_GATES)
    def test_each_uncovered_gate_is_named_when_active(self, gate: str) -> None:
        v = eligibility.preview(
            _signal(),
            market_price=Decimal("500"),
            modes=_modes(**{gate: "active"}),
            **_THRESHOLDS,  # type: ignore[arg-type]
        )
        assert gate in v.unassessed, f"{gate} active but not reported unassessed"
        assert v.blocked is False  # unknown, not blocked — fail-open

    @pytest.mark.parametrize("gate", eligibility.UNCOVERED_GATES)
    def test_shadow_uncovered_gate_is_not_reported(self, gate: str) -> None:
        """Only ACTIVE gates matter — a shadow gate suppresses nothing, so naming it
        would cry wolf on every row."""
        v = eligibility.preview(
            _signal(),
            market_price=Decimal("500"),
            modes=_modes(**{gate: "shadow"}),
            **_THRESHOLDS,  # type: ignore[arg-type]
        )
        assert gate not in v.unassessed

    def test_missing_price_reports_through_stop_unassessed(self) -> None:
        """No live price ⇒ the broker's through-stop rejection cannot be judged. It is
        always on (not settings-moded), so absence is always a real gap."""
        v = eligibility.preview(
            _signal(), market_price=None, modes=_modes(), **_THRESHOLDS  # type: ignore[arg-type]
        )
        assert eligibility.GATE_THROUGH_STOP in v.unassessed
        assert v.blocked is False


class TestThroughStopPreview:
    """The PNCINFRA archetype: a stale BUY whose stock has since traded below the stop.
    For an aged swing signal this is the most likely guaranteed-failure click, and the
    first version of the preview did not model it (bug-hunter, 2026-09-02)."""

    def test_long_below_its_stop_is_blocked(self) -> None:
        v = eligibility.preview(
            _signal(entry_price="238.2100", stop_loss="237.2600", take_profit="273.9400"),
            market_price=Decimal("191.85"),
            modes=_modes(),
            **_THRESHOLDS,  # type: ignore[arg-type]
        )
        assert v.blocked is True
        assert v.gate == eligibility.GATE_THROUGH_STOP
        assert v.reason is not None and "through this signal's stop loss" in v.reason

    def test_short_above_its_stop_is_blocked(self) -> None:
        v = eligibility.preview(
            _signal(direction="SELL", entry_price="100.0000", stop_loss="104.0000",
                    take_profit="88.0000"),
            market_price=Decimal("110"),
            modes=_modes(),
            **_THRESHOLDS,  # type: ignore[arg-type]
        )
        assert v.blocked is True and v.gate == eligibility.GATE_THROUGH_STOP

    def test_price_on_the_tradeable_side_is_clear(self) -> None:
        v = eligibility.preview(
            _signal(),
            market_price=Decimal("505"),
            modes=_modes(),
            **_THRESHOLDS,  # type: ignore[arg-type]
        )
        assert v.blocked is False and v.unassessed == ()

    def test_regime_is_reported_before_through_stop(self) -> None:
        """Order mirrors the order path: the settings-moded overlays run BEFORE the
        broker is called, so a signal failing both reports the regime gate."""
        v = eligibility.preview(
            _signal(regime="transitional (20\u201325)", stop_loss="237.2600"),
            market_price=Decimal("191.85"),
            modes=_modes(**{eligibility.GATE_REGIME: "active"}),
            **_THRESHOLDS,  # type: ignore[arg-type]
        )
        assert v.gate == eligibility.GATE_REGIME


class TestBrokerRejectionsArePreviewed:
    """The paper broker has TWO unconditional pre-fill rejections and BOTH must be
    previewed (quant-verifier, 2026-09-02). The off-market one matters most: it is not
    settings-moded, `allow_offmarket_entry` defaults False, and the list is usually read
    outside market hours — so every row used to read `blocked=False` in the evening while
    the order path 422'd all of them."""

    def test_offmarket_blocks_when_no_price_and_not_opted_in(self) -> None:
        v = eligibility.preview(
            _signal(),
            market_price=None,
            allow_offmarket=False,
            modes=_modes(),
            **_THRESHOLDS,  # type: ignore[arg-type]
        )
        assert v.blocked is True
        assert v.gate == eligibility.GATE_OFFMARKET
        assert v.reason == eligibility.OFFMARKET_REASON

    def test_offmarket_clear_when_user_opted_in(self) -> None:
        v = eligibility.preview(
            _signal(),
            market_price=None,
            allow_offmarket=True,
            modes=_modes(),
            **_THRESHOLDS,  # type: ignore[arg-type]
        )
        assert v.blocked is False

    def test_offmarket_not_triggered_when_a_price_exists(self) -> None:
        v = eligibility.preview(
            _signal(),
            market_price=Decimal("500"),
            allow_offmarket=False,
            modes=_modes(),
            **_THRESHOLDS,  # type: ignore[arg-type]
        )
        assert v.blocked is False

    def test_through_stop_judged_on_the_fill_not_the_raw_ltp(self) -> None:
        """The broker checks its POST-SLIPPAGE fill, so the preview must too. Raw LTP
        237.25 vs SL 237.26 looks through-stop, but the modelled BUY fill lands ABOVE it
        and the order path allows the trade — previewing on the LTP was a false BLOCK,
        which hides a tradeable signal (the worse direction of the two)."""
        sig = _signal(entry_price="237.5000", stop_loss="237.2600", take_profit="245.0000")
        on_ltp = eligibility.preview(
            sig, market_price=Decimal("237.25"), modes=_modes(), **_THRESHOLDS  # type: ignore[arg-type]
        )
        assert on_ltp.blocked is True  # what the LTP alone says

        on_fill = eligibility.preview(
            sig,
            market_price=Decimal("237.25"),
            fill_price=Decimal("237.30"),  # an adverse BUY fill lands above the stop
            modes=_modes(),
            **_THRESHOLDS,  # type: ignore[arg-type]
        )
        assert on_fill.blocked is False, "must agree with the order path, which fills 237.30"


class TestChaseIsCovered:
    """`chase_guard.evaluate` is pure and needs only the price already in hand, so it is
    JUDGED, not reported unassessed (quant-verifier, 2026-09-02)."""

    def test_chase_blocks_when_active_and_price_ran_past_entry(self) -> None:
        # entry 500, SL 480 → 1R = 20; 0.33R ceiling = 506.6. 515 is well past it.
        v = eligibility.preview(
            _signal(),
            market_price=Decimal("515"),
            modes=_modes(**{eligibility.GATE_CHASE: "active"}),
            max_chase_r=Decimal("0.33"),
            **_THRESHOLDS,  # type: ignore[arg-type]
        )
        assert v.blocked is True and v.gate == eligibility.GATE_CHASE

    def test_chase_shadow_does_not_block(self) -> None:
        v = eligibility.preview(
            _signal(),
            market_price=Decimal("515"),
            modes=_modes(**{eligibility.GATE_CHASE: "shadow"}),
            max_chase_r=Decimal("0.33"),
            **_THRESHOLDS,  # type: ignore[arg-type]
        )
        assert v.blocked is False

    def test_chase_is_not_in_the_uncovered_set(self) -> None:
        assert eligibility.GATE_CHASE not in eligibility.UNCOVERED_GATES
        assert eligibility.GATE_CHASE in eligibility.COVERED_GATES


class TestActiveListReportsBlocks:
    async def test_blocked_signal_is_returned_flagged_not_hidden(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A single-factor signal must still LIST (so the gate's effect is visible)
        but carry blocked=True + the reason the order path would 409 with."""
        monkeypatch.setattr(settings, "entry_diversity_gate_mode", "active")
        monkeypatch.setattr(settings, "regime_gate_mode", "shadow")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        db.add(_signal(stock_id=stock.id, factor_scores=_ONE_FACTOR))
        await db.commit()

        r = await client.get(
            "/api/v1/signals/active?include_expiring=true&include_choppy=true",
            headers=headers,
        )
        assert r.status_code == 200
        rows = r.json()["signals"]
        assert len(rows) == 1, "a blocked signal must be flagged, never silently hidden"
        assert rows[0]["blocked"] is True
        assert rows[0]["blocked_by"] == "entry_quality"
        assert "scoring factor" in rows[0]["block_reason"]

    async def test_clean_signal_lists_unblocked(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "entry_diversity_gate_mode", "active")
        monkeypatch.setattr(settings, "regime_gate_mode", "shadow")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        db.add(_signal(stock_id=stock.id))
        await db.commit()

        r = await client.get(
            "/api/v1/signals/active?include_expiring=true&include_choppy=true",
            headers=headers,
        )
        rows = r.json()["signals"]
        assert len(rows) == 1
        assert rows[0]["blocked"] is False
        assert rows[0]["blocked_by"] is None
        assert rows[0]["block_reason"] is None

    async def test_list_verdict_matches_order_path_409(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """THE contract: whatever the list says is blocked, the order path rejects —
        with the SAME message. This is the assertion that keeps the two paths honest."""
        monkeypatch.setattr(settings, "entry_diversity_gate_mode", "active")
        monkeypatch.setattr(settings, "regime_gate_mode", "shadow")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        sig = _signal(stock_id=stock.id, factor_scores=_ONE_FACTOR)
        db.add(sig)
        await db.commit()
        signal_id = str(sig.id)

        listed = (
            await client.get(
                "/api/v1/signals/active?include_expiring=true&include_choppy=true",
                headers=headers,
            )
        ).json()["signals"][0]
        assert listed["blocked"] is True

        order = await client.post(
            "/api/v1/trading/orders",
            json={"signal_id": signal_id, "side": "BUY"},
            headers=headers,
        )
        assert order.status_code == 409
        assert order.json()["detail"] == listed["block_reason"]
