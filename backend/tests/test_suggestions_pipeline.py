"""Suggestions pipeline + API (Phase 2 slice 7).

Seam tests: the scorer is stubbed (its math is pinned by the parity suite);
everything else — universe resolution, setup gating, risk-template TP,
sizing, supersede policy, persistence, API join — runs for real against
the test database.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.analysis.confluence import ConfluenceResult
from app.analysis.types import FactorResult
from app.models.signal import Signal
from app.profiles import pipeline
from app.profiles.pipeline import run_profile, run_scheduled_profiles
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import (
    create_test_user,
    get_auth_headers,
    make_daily_candles,
    make_intraday_candles,
    make_profile,
    make_stock,
)

CAPITAL = Decimal("500000")
RISK_PCT = Decimal("2")

# ── Intraday session fixtures (Phase-3 pre-work) ─────────────────────────────
# Flat anchor bar reused across sessions; the interesting geometry lives in
# the decision session. Scalp/intraday SL cap is 0.5%, so every fixture puts
# its most recent pivot low within 0.5% of the decision close.

_FLAT = (100.0, 100.4, 99.6, 100.0)

# Previous session: day high 101.0 minted MID-session (bar 12) while the
# session's LAST bar high is only 100.2 — distinguishes true prev-DAY
# context from any previous-BAR fallback.
_PDH_PREV_SESSION = [_FLAT] * 12 + [(100.0, 101.0, 99.6, 100.0)] + [_FLAT] * 11 + [
    (100.0, 100.2, 99.6, 100.0)
]

# Decision session, PASS variant: rises to close 101.50 > PDH 101.0; the
# designed pivot low at bar 15 (101.05) keeps SL risk at 0.44% (< 0.5% cap).
_PDH_TODAY_PASS = [
    (100.60, 100.75, 100.55, 100.70),
    (100.70, 100.85, 100.65, 100.80),
    (100.80, 100.95, 100.75, 100.90),
    (100.90, 101.05, 100.85, 101.00),
    (101.00, 101.15, 100.95, 101.10),
    (101.10, 101.20, 101.06, 101.15),
    (101.15, 101.25, 101.10, 101.20),
    (101.20, 101.30, 101.15, 101.25),
    (101.25, 101.35, 101.20, 101.30),
    (101.30, 101.40, 101.25, 101.35),
    (101.35, 101.45, 101.30, 101.40),
    (101.35, 101.45, 101.28, 101.38),
    (101.30, 101.42, 101.22, 101.32),
    (101.28, 101.40, 101.18, 101.30),
    (101.25, 101.38, 101.12, 101.28),
    (101.20, 101.35, 101.05, 101.30),  # pivot low 101.05
    (101.30, 101.42, 101.15, 101.35),
    (101.35, 101.45, 101.20, 101.40),
    (101.38, 101.48, 101.25, 101.42),
    (101.40, 101.50, 101.30, 101.45),
    (101.42, 101.52, 101.35, 101.46),
    (101.44, 101.54, 101.38, 101.48),
    (101.46, 101.56, 101.40, 101.50),
    (101.45, 101.55, 101.42, 101.48),
    (101.48, 101.58, 101.44, 101.50),  # decision close 101.50 > PDH 101.0
]

# Decision session, DROP variant: closes 100.90 < PDH 101.0 — but ABOVE the
# previous BAR's high (100.88), which is exactly the window the pre-fix
# pipeline (prev_day never wired → iloc[-2] fallback) wrongly passed.
_PDH_TODAY_DROP = (
    [
        (
            round(100.10 + 0.04 * i, 2),
            round(100.16 + 0.04 * i, 2),
            round(100.06 + 0.04 * i, 2),
            round(100.12 + 0.04 * i, 2),
        )
        for i in range(15)
    ]
    + [(100.60, 100.70, 100.45, 100.65)]  # pivot low 100.45
    + [
        (
            round(100.62 + 0.03 * (i - 16), 2),
            round(100.68 + 0.03 * (i - 16), 2),
            round(100.58 + 0.03 * (i - 16), 2),
            round(100.64 + 0.03 * (i - 16), 2),
        )
        for i in range(16, 23)
    ]
    + [(100.85, 100.88, 100.82, 100.86), (100.86, 100.95, 100.84, 100.90)]
)


def _confluence(direction: str = "BUY", sr_score: float = 0.95) -> ConfluenceResult:
    sr = sr_score if direction == "BUY" else -sr_score
    return ConfluenceResult(
        direction=direction,
        confidence_pct=78,
        normalized_score=0.78 if direction == "BUY" else -0.78,
        factors=[
            FactorResult("DOW_TREND", 20, 0.7 if direction == "BUY" else -0.7, "t", ["trend"]),
            FactorResult("SR_ZONE", 10, sr, "t", ["structure"]),
        ],
        triggering_patterns=["BULLISH_ENGULFING"],
        triggering_indicators=[],
        is_multibagger=False,
    )


def _stub_scorer(monkeypatch: pytest.MonkeyPatch, result: ConfluenceResult | None) -> None:
    monkeypatch.setattr(pipeline, "score_signal", lambda *a, **k: result)


@pytest.fixture
async def rrbo_env(db: AsyncSession):
    stock = await make_stock(db, symbol="PIPE1", is_nifty50=True)
    await make_daily_candles(db, stock.id)
    profile = await make_profile(
        db,
        key="rrbo_test",
        universe_spec={"kind": "index", "value": "NIFTY50"},
        setup_conditions=[
            {"type": "factor_score", "params": {"factor": "SR_ZONE", "min_score": 0.9}}
        ],
        risk_template={"kind": "flat_pct", "target_pct": "6"},
    )
    return stock, profile


class TestRunProfile:
    async def test_fires_and_persists_tagged_suggestion(
        self, db: AsyncSession, rrbo_env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stock, profile = rrbo_env
        _stub_scorer(monkeypatch, _confluence("BUY", sr_score=0.95))

        created = await run_profile(db, profile, CAPITAL, RISK_PCT)
        assert len(created) == 1
        sig = created[0]

        assert sig.profile_key == "rrbo_test"
        assert sig.profile_id == profile.id
        assert sig.setup_trigger["factor_score"]["passed"] is True
        assert sig.volatility_reduced is False
        # entry = last close (100), flat 6% template → TP exactly 106
        assert sig.entry_price == Decimal("100")
        assert sig.take_profit == Decimal("106.0000")
        # pivot swing low (96) is the SL — inside the 8% swing cap
        assert sig.stop_loss == Decimal("96.0")
        # floor(10000 / 4) = 2500 shares
        assert sig.suggested_qty == 2500
        assert sig.status == "active"
        assert sig.validity_until > datetime.now(tz=UTC)

    async def test_setup_gate_drops_below_threshold(
        self, db: AsyncSession, rrbo_env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _, profile = rrbo_env
        _stub_scorer(monkeypatch, _confluence("BUY", sr_score=0.5))
        created = await run_profile(db, profile, CAPITAL, RISK_PCT)
        assert created == []
        count = (await db.execute(select(Signal))).scalars().all()
        assert count == []

    async def test_idempotent_second_run_skips(
        self, db: AsyncSession, rrbo_env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _, profile = rrbo_env
        _stub_scorer(monkeypatch, _confluence("BUY"))
        first = await run_profile(db, profile, CAPITAL, RISK_PCT)
        assert len(first) == 1
        second = await run_profile(db, profile, CAPITAL, RISK_PCT)
        assert second == []
        rows = (await db.execute(select(Signal))).scalars().all()
        assert len(rows) == 1

    async def test_opposite_direction_supersedes(
        self, db: AsyncSession, rrbo_env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _, profile = rrbo_env
        _stub_scorer(monkeypatch, _confluence("BUY"))
        (buy_sig,) = await run_profile(db, profile, CAPITAL, RISK_PCT)

        _stub_scorer(monkeypatch, _confluence("SELL"))
        (sell_sig,) = await run_profile(db, profile, CAPITAL, RISK_PCT)

        await db.refresh(buy_sig)
        assert buy_sig.status == "superseded"
        assert buy_sig.expired_at is not None
        assert sell_sig.direction == "SELL"
        assert sell_sig.status == "active"
        # SELL flat 6%: TP = 100 × 0.94
        assert sell_sig.take_profit == Decimal("94.0000")

    async def test_rr_template_tp(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stock = await make_stock(db, symbol="PIPE2", is_nifty50=True)
        await make_daily_candles(db, stock.id)
        profile = await make_profile(
            db,
            key="rr_test",
            universe_spec={"kind": "index", "value": "NIFTY50"},
            setup_conditions=[],
            risk_template={"kind": "rr", "ratio": "2"},
        )
        _stub_scorer(monkeypatch, _confluence("BUY"))
        (sig,) = await run_profile(db, profile, CAPITAL, RISK_PCT)
        # entry 100, SL 96 → risk 4 → TP = 100 + 2×4 = 108
        assert sig.take_profit == Decimal("108.0000")

    async def test_no_signal_no_row(
        self, db: AsyncSession, rrbo_env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _, profile = rrbo_env
        _stub_scorer(monkeypatch, None)
        assert await run_profile(db, profile, CAPITAL, RISK_PCT) == []

    async def test_profile_multipliers_reach_the_scorer(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Phase-3 pre-work regression (slice-7 gap): profile
        weight_multipliers must flow into scoring — the walk-forward always
        honored them, the live pipeline silently dropped them."""
        stock = await make_stock(db, symbol="PIPE4", is_nifty50=True)
        await make_daily_candles(db, stock.id)
        profile = await make_profile(
            db,
            key="mult_test",
            universe_spec={"kind": "index", "value": "NIFTY50"},
            weight_multipliers={"trend": 2.0},
        )
        captured: dict = {}

        def capture(window, **kw):
            captured.update(kw)
            return _confluence("BUY")

        monkeypatch.setattr(pipeline, "score_signal", capture)
        created = await run_profile(db, profile, CAPITAL, RISK_PCT)
        assert len(created) == 1
        assert captured["weight_multipliers"] == {"trend": 2.0}


class TestRunScheduledProfiles:
    async def test_runs_only_matching_active_profiles(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stock = await make_stock(db, symbol="PIPE3", is_nifty50=True)
        await make_daily_candles(db, stock.id)
        await make_profile(
            db, key="eod_active", universe_spec={"kind": "index", "value": "NIFTY50"}
        )
        await make_profile(
            db,
            key="intraday_inactive",
            style="intraday",
            timeframe="15m",
            schedule="intraday_15m",
            status="inactive",
        )
        _stub_scorer(monkeypatch, _confluence("BUY"))

        counts = await run_scheduled_profiles(db, "eod", CAPITAL, RISK_PCT)
        assert counts == {"eod_active": 1}


class TestIntradayContext:
    """Phase-3 pre-work: the live pipeline must build the same session
    context the walk-forward reconstructs — prev-day OHLC from the window's
    own sessions and the 9:25 cross-section from the universe's bars. The
    pre-fix pipeline passed neither (prev-day silently degraded to the
    previous BAR; the 9:25 screen failed closed for every stock)."""

    async def _pdh_profile(self, db: AsyncSession):
        return await make_profile(
            db,
            key="pdh_test",
            style="intraday",
            timeframe="15m",
            schedule="intraday_15m",
            universe_spec={"kind": "index", "value": "NIFTY50"},
            setup_conditions=[{"type": "pdh_breakout", "params": {}}],
            risk_template={"kind": "flat_pct", "target_pct": "2"},
        )

    async def test_pdh_gate_uses_previous_session_high(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stock = await make_stock(db, symbol="INTRA1", is_nifty50=True)
        await make_intraday_candles(
            db, stock.id, "15m", [[_FLAT] * 25, _PDH_PREV_SESSION, _PDH_TODAY_PASS]
        )
        profile = await self._pdh_profile(db)
        _stub_scorer(monkeypatch, _confluence("BUY"))

        created = await run_profile(db, profile, CAPITAL, RISK_PCT)
        assert len(created) == 1
        evidence = created[0].setup_trigger["pdh_breakout"]
        assert evidence["passed"] is True
        # the SESSION high (101.0, minted mid-previous-day), not the
        # previous bar's high (101.55) — the old fallback's value
        assert evidence["pdh"] == 101.0
        assert created[0].entry_price == Decimal("101.5")

    async def test_close_below_true_pdh_drops_even_above_prev_bar_high(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Canary that fails on the pre-fix code: decision close 100.90 is
        above the previous BAR's high (100.88) — the old iloc[-2] fallback
        minted a suggestion here — but below the true PDH 101.0."""
        stock = await make_stock(db, symbol="INTRA2", is_nifty50=True)
        await make_intraday_candles(
            db, stock.id, "15m", [[_FLAT] * 25, _PDH_PREV_SESSION, list(_PDH_TODAY_DROP)]
        )
        profile = await self._pdh_profile(db)
        _stub_scorer(monkeypatch, _confluence("BUY"))

        created = await run_profile(db, profile, CAPITAL, RISK_PCT)
        assert created == []
        assert (await db.execute(select(Signal))).scalars().all() == []

    async def _gainer_env(
        self, db: AsyncSession, today_gain1: list, today_gain2: list
    ):
        gain1 = await make_stock(db, symbol="GAIN1", is_nifty50=True)
        gain2 = await make_stock(db, symbol="GAIN2", is_nifty50=True)
        tight_tail = [_FLAT] * 60 + [(100.0, 100.4, 99.96, 100.0)] * 15
        await make_intraday_candles(
            db, gain1.id, "5m", [[_FLAT] * 75, tight_tail, today_gain1]
        )
        await make_intraday_candles(
            db, gain2.id, "5m", [[_FLAT] * 75, [_FLAT] * 75, today_gain2]
        )
        profile = await make_profile(
            db,
            key="gainer_test",
            style="intraday",
            timeframe="5m",
            schedule="time_0925",
            universe_spec={"kind": "index", "value": "NIFTY50"},
            setup_conditions=[{"type": "top_gainer_925", "params": {"top_n": 1}}],
            risk_template={"kind": "flat_pct", "target_pct": "1"},
        )
        return gain1, gain2, profile

    async def test_925_cross_section_ranks_universe(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gain1, gain2, profile = await self._gainer_env(
            db,
            # 09:20 bar closes 100.45 → +0.45% vs prev close 100 (rank 1)
            [(100.10, 100.50, 100.05, 100.40), (100.40, 100.50, 100.30, 100.45)],
            # −0.5% → wrong sign for BUY and outside top_n=1
            [(100.0, 100.05, 99.40, 99.60), (99.60, 99.65, 99.40, 99.50)],
        )
        _stub_scorer(monkeypatch, _confluence("BUY"))

        created = await run_profile(db, profile, CAPITAL, RISK_PCT)
        assert len(created) == 1
        assert created[0].stock_id == gain1.id
        evidence = created[0].setup_trigger["top_gainer_925"]
        assert evidence["passed"] is True
        assert evidence["pct_change_925"] == pytest.approx(0.45)

    async def test_screen_not_consulted_before_0925(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Look-ahead guard (mirrors the walk-forward's 8c-4 fix): a
        decision bar starting before 09:20 predates the 9:25 screen — the
        cross-section exists in the data but must not be consulted."""
        _, _, profile = await self._gainer_env(
            db,
            [(100.10, 100.50, 100.05, 100.40)],  # only the 09:15 bar so far
            [(100.0, 100.05, 99.40, 99.60)],
        )
        _stub_scorer(monkeypatch, _confluence("BUY"))

        created = await run_profile(db, profile, CAPITAL, RISK_PCT)
        assert created == []


class TestSuggestionsApi:
    async def test_list_by_style_with_profile_join(
        self, db: AsyncSession, client: AsyncClient, rrbo_env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _, profile = rrbo_env
        _stub_scorer(monkeypatch, _confluence("BUY"))
        await run_profile(db, profile, CAPITAL, RISK_PCT)

        await create_test_user(db, email="sugg@example.com")
        headers = await get_auth_headers(client, email="sugg@example.com")

        r = await client.get("/api/v1/suggestions/swing", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["style"] == "swing"
        assert body["total"] == 1
        s = body["suggestions"][0]
        assert s["symbol"] == "PIPE1"
        assert s["profile_key"] == "rrbo_test"
        assert s["profile_version"] == 1
        assert s["take_profit"] == "106.0000"
        assert s["setup_trigger"]["factor_score"]["passed"] is True

        # profile filter: no match → empty
        r = await client.get(
            "/api/v1/suggestions/swing?profile=other_key", headers=headers
        )
        assert r.json()["total"] == 0

    async def test_unknown_style_404(self, db: AsyncSession, client: AsyncClient) -> None:
        await create_test_user(db, email="sugg2@example.com")
        headers = await get_auth_headers(client, email="sugg2@example.com")
        r = await client.get("/api/v1/suggestions/yolo", headers=headers)
        assert r.status_code == 404

    async def test_empty_style_ok(self, db: AsyncSession, client: AsyncClient) -> None:
        await create_test_user(db, email="sugg3@example.com")
        headers = await get_auth_headers(client, email="sugg3@example.com")
        r = await client.get("/api/v1/suggestions/fno", headers=headers)
        assert r.status_code == 200
        assert r.json() == {"style": "fno", "total": 0, "suggestions": []}

    async def test_requires_auth(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/suggestions/swing")
        assert r.status_code == 401
