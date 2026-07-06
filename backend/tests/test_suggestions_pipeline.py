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
    make_profile,
    make_stock,
)

CAPITAL = Decimal("500000")
RISK_PCT = Decimal("2")


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
