"""Shadow profiles — run a profile on its real schedule without trading it.

The intraday trio is negative risk-adjusted on walk-forward (pdh_pdl -1.06
Sharpe, orb_15m -0.60, gainer_925 -0.86), so activating it would put
negative-expectancy suggestions behind a Buy button. Leaving it switched off
produced no evidence either. Shadow is the third state: runs, records, measures
to outcome — never tradeable.

The load-bearing property is UNTRADEABILITY, and these tests assert it at the
seam that enforces it (the order path), not just at the layer that hides it.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.models.profile import StrategyProfile
from app.models.signal import Signal
from app.schemas.profile import (
    RUNNABLE_PROFILE_STATUSES,
    signal_status_for,
)
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock

# asyncio_mode = "auto" — no module-level asyncio mark, or the sync tests below
# each raise a PytestWarning for carrying a mark they cannot use.


def _profile(status: str) -> StrategyProfile:
    return StrategyProfile(status=status)  # type: ignore[call-arg]


class TestSignalStatusMapping:
    def test_active_profile_mints_tradeable_signals(self) -> None:
        assert signal_status_for(_profile("active")) == "active"

    def test_shadow_profile_mints_shadow_signals(self) -> None:
        assert signal_status_for(_profile("shadow")) == "shadow"

    @pytest.mark.parametrize("status", ["inactive", "superseded", "", "typo", "ACTIVE"])
    def test_unknown_status_fails_closed(self, status: str) -> None:
        """An unrecognised profile state must never mint a TRADEABLE signal.

        Canary: a mapping that defaulted to 'active' would turn a typo in a
        status column into live suggestions.
        """
        assert signal_status_for(_profile(status)) == "shadow"

    def test_only_active_and_shadow_are_runnable(self) -> None:
        assert set(RUNNABLE_PROFILE_STATUSES) == {"active", "shadow"}


async def _signal(
    db: AsyncSession,
    stock_id: int,
    status: str,
    validity_hours: float = 6.0,
) -> Signal:
    sig = Signal(
        stock_id=stock_id,
        direction="BUY",
        classification="intraday",
        timeframe="15m",
        entry_price=Decimal("100.0000"),
        stop_loss=Decimal("98.0000"),
        take_profit=Decimal("104.0000"),
        suggested_qty=10,
        confidence_pct=75,
        factor_scores={},
        headline="test",
        status=status,
        is_shadow=(status == "shadow"),
        validity_until=datetime.now(tz=UTC) + timedelta(hours=validity_hours),
        profile_key="pdh_pdl",
    )
    db.add(sig)
    await db.flush()
    return sig


class TestShadowIsUntradeable:
    """The property everything else depends on."""

    async def test_order_path_rejects_a_shadow_signal(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """A shadow suggestion must not be orderable, even by direct API call.

        This is the enforcement point — the UI merely declines to show a button.
        """
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db, symbol="SHADOW1")
        sig = await _signal(db, stock.id, status="shadow")
        await db.commit()

        r = await client.post(
            "/api/v1/trading/orders",
            json={"signal_id": str(sig.id), "side": "BUY"},
            headers=headers,
        )
        assert r.status_code == 409, r.text
        assert "shadow" in r.json()["detail"].lower()
        assert "not active" in r.json()["detail"].lower()

    async def test_shadow_signals_are_absent_from_the_suggestions_table(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db, symbol="SHADOW2")
        await _signal(db, stock.id, status="shadow")
        await db.commit()

        r = await client.get("/api/v1/suggestions/intraday", headers=headers)
        assert r.status_code == 200
        assert r.json()["total"] == 0

    async def test_shadow_signals_are_absent_from_the_dashboard_feed(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db, symbol="SHADOW3")
        await _signal(db, stock.id, status="shadow")
        await db.commit()

        r = await client.get("/api/v1/signals/active", headers=headers)
        assert r.status_code == 200
        body = r.json()
        rows = body if isinstance(body, list) else body.get("signals", [])
        assert all(s.get("symbol") != "SHADOW3" for s in rows)


class TestShadowExpiry:
    async def test_the_sweeper_expires_shadow_signals(self, db: AsyncSession) -> None:
        """Canary: sweeping only 'active' leaves shadow signals live forever.

        Their outcomes would never finalise — so the forward evidence the shadow
        layer exists to produce would never close out — and each run would stack
        another undead row on the same (stock, profile).
        """
        from app.tasks.expiry_tasks import sweep_expired

        stock = await make_stock(db, symbol="SWEEPME")
        sig = await _signal(db, stock.id, status="shadow", validity_hours=-1)
        await db.commit()

        swept = await sweep_expired(db, datetime.now(tz=UTC))
        assert swept >= 1

        await db.refresh(sig)
        assert sig.status == "expired"
        assert sig.expired_at is not None

    async def test_an_unexpired_shadow_signal_survives_the_sweep(
        self, db: AsyncSession
    ) -> None:
        from app.tasks.expiry_tasks import sweep_expired

        stock = await make_stock(db, symbol="KEEPME")
        sig = await _signal(db, stock.id, status="shadow", validity_hours=6)
        await db.commit()

        await sweep_expired(db, datetime.now(tz=UTC))
        await db.refresh(sig)
        assert sig.status == "shadow"


class TestShadowIsMeasured:
    async def test_live_levels_tracks_shadow_signals(self, db: AsyncSession) -> None:
        """Outcome recording runs off these levels.

        Canary: excluding shadow here leaves the layer producing suggestions
        nobody ever scores — the exact opposite of why it exists.
        """
        from app.broker.live_levels import _active_signals

        stock = await make_stock(db, symbol="TRACKED")
        sig = await _signal(db, stock.id, status="shadow")
        await db.commit()

        rows = await _active_signals(db)
        mine = [r for r in rows if r["id"] == str(sig.id)]
        assert len(mine) == 1
        assert mine[0]["shadow"] is True

    async def test_active_signals_are_not_flagged_shadow(self, db: AsyncSession) -> None:
        from app.broker.live_levels import _active_signals

        stock = await make_stock(db, symbol="REALONE")
        sig = await _signal(db, stock.id, status="active")
        await db.commit()

        rows = await _active_signals(db)
        mine = [r for r in rows if r["id"] == str(sig.id)]
        assert mine[0]["shadow"] is False

    async def test_alert_metadata_carries_the_shadow_flag(self) -> None:
        """The flag rides on every alert so the live feed can exclude it."""
        from app.broker.live_levels import _signal_levels

        _levels, meta = _signal_levels(
            {
                "id": "abc",
                "stock_id": 1,
                "entry": Decimal("100"),
                "sl": Decimal("98"),
                "tp": Decimal("104"),
                "classification": "intraday",
                "timeframe": "15m",
                "direction": "BUY",
                "shadow": True,
            }
        )
        assert meta
        assert all(m["shadow"] is True for m in meta.values())


class TestShadowAndActiveDoNotCollide:
    async def test_a_shadow_signal_does_not_block_a_real_one(
        self, db: AsyncSession
    ) -> None:
        """The two layers dedup independently.

        A shadow suggestion on (stock, profile) must not make the tradeable
        pipeline skip that name — that would let the shadow layer suppress real
        signals, which is a trading-behaviour change nobody asked for.
        """
        from app.profiles.pipeline import _resolve_existing

        stock = await make_stock(db, symbol="BOTHLAYERS")
        await _signal(db, stock.id, status="shadow")
        await db.commit()

        assert await _resolve_existing(db, stock.id, "pdh_pdl", "BUY", "active") == "insert"

    async def test_a_shadow_run_dedups_against_its_own_layer(
        self, db: AsyncSession
    ) -> None:
        from app.profiles.pipeline import _resolve_existing

        stock = await make_stock(db, symbol="SHADOWDEDUP")
        await _signal(db, stock.id, status="shadow")
        await db.commit()

        assert await _resolve_existing(db, stock.id, "pdh_pdl", "BUY", "shadow") == "skip"

    async def test_a_shadow_run_never_supersedes_a_tradeable_signal(
        self, db: AsyncSession
    ) -> None:
        """Canary: an unscoped supersede would kill a live signal from shadow."""
        from app.profiles.pipeline import _resolve_existing

        stock = await make_stock(db, symbol="DONTKILL")
        live = await _signal(db, stock.id, status="active")
        await db.commit()

        # Opposite direction is what triggers the supersede branch.
        await _resolve_existing(db, stock.id, "pdh_pdl", "SELL", "shadow")
        await db.refresh(live)
        assert live.status == "active"


class TestScheduledRunnerPicksUpShadow:
    """The scheduler half — without it a shadow profile is just an inactive one.

    `nightly_suggestions` only ever ran the 'eod' schedule and
    `on_close_suggestions` was a stub, so `intraday_15m` / `time_0925` profiles
    had NO caller at all: the Intraday menu was structurally unable to populate
    regardless of profile status.
    """

    async def _seed(self, db: AsyncSession, key: str, status: str, schedule: str) -> None:
        db.add(
            StrategyProfile(
                key=key,
                version=1,
                name=key,
                description="t",
                style="intraday",
                timeframe="15m",
                schedule=schedule,
                # A one-symbol universe that resolves to nothing in the test DB:
                # the runner is what's under test, not the scoring beneath it.
                universe_spec={"kind": "symbols", "value": ["NOSUCHSYM"]},
                setup_conditions=[],
                weight_multipliers={},
                min_confidence=70,
                risk_template={"kind": "rr", "ratio": "1.5"},
                validity_spec=None,
                status=status,
                config_hash=f"hash-{key}",
            )
        )
        await db.flush()

    async def test_runs_shadow_profiles_on_an_intraday_schedule(
        self, db: AsyncSession
    ) -> None:
        """Canary: filtering on status == 'active' returns {} here."""
        from app.profiles.pipeline import run_scheduled_profiles

        await self._seed(db, "shadow_one", "shadow", "intraday_15m")
        await db.commit()

        counts = await run_scheduled_profiles(
            db, "intraday_15m", Decimal("100000"), Decimal("2.0")
        )
        assert "shadow_one" in counts

    async def test_does_not_run_inactive_profiles(self, db: AsyncSession) -> None:
        from app.profiles.pipeline import run_scheduled_profiles

        await self._seed(db, "off_one", "inactive", "intraday_15m")
        await db.commit()

        counts = await run_scheduled_profiles(
            db, "intraday_15m", Decimal("100000"), Decimal("2.0")
        )
        assert "off_one" not in counts

    async def test_schedules_do_not_bleed_into_each_other(
        self, db: AsyncSession
    ) -> None:
        """The 09:25 profile must not fire on every 15-minute beat."""
        from app.profiles.pipeline import run_scheduled_profiles

        await self._seed(db, "at_0925", "shadow", "time_0925")
        await db.commit()

        counts = await run_scheduled_profiles(
            db, "intraday_15m", Decimal("100000"), Decimal("2.0")
        )
        assert "at_0925" not in counts


class TestIntradayTaskGuards:
    async def test_skips_outside_the_market_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The crontab window is coarse by necessity; this guard is authoritative.

        Canary: without it the 03:00-UTC beat fires at 08:30 IST, pre-open —
        the same class of bug that had the position monitor closing positions
        against the previous session's stale close.
        """
        from app.tasks import profile_tasks

        monkeypatch.setattr(profile_tasks, "_IST", profile_tasks._IST)
        monkeypatch.setattr(
            "app.trading.market_hours.is_market_session", lambda _now: False
        )
        out = await profile_tasks._run_intraday("intraday_15m")
        assert out["status"] == "skipped"
        assert "session" in str(out["message"])


class TestShadowEvidenceNeverLeaksIntoTradeableStats:
    """quant-verifier CRITICAL, 2026-08-08.

    `/analytics/outcomes` joined signal_outcomes → signals → strategy_profiles
    and grouped by style with NO shadow filter, so every shadow outcome landed in
    the intraday hit-rate / entry-rate / avg-return the StylePage renders as
    "Tracked outcomes". Shadow profiles are precisely the ones that have NOT
    earned activation, so this dragged the headline numbers toward a strategy
    nobody trades — corrupting the evidence the shadow layer exists to produce.
    """

    async def _outcome(self, db: AsyncSession, signal_id: str, status: str) -> None:
        await db.execute(
            text(
                "INSERT INTO signal_outcomes"
                " (signal_id, stock_id, direction, classification, timeframe,"
                "  validity_until, status, entry_touched_at)"
                " SELECT id, stock_id, direction, classification, timeframe,"
                "        validity_until, :st, now()"
                " FROM signals WHERE id = :sid"
            ),
            {"sid": signal_id, "st": status},
        )

    async def _profiled_signal(
        self, db: AsyncSession, symbol: str, status: str
    ) -> Signal:
        """A signal attached to a REAL intraday profile row — the analytics
        aggregate inner-joins strategy_profiles, so an unprofiled signal would
        pass this test vacuously."""
        prof = StrategyProfile(
            key=f"prof_{symbol}",
            version=1,
            name=symbol,
            description="t",
            style="intraday",
            timeframe="15m",
            schedule="intraday_15m",
            universe_spec={"kind": "symbols", "value": [symbol]},
            setup_conditions=[],
            weight_multipliers={},
            min_confidence=70,
            risk_template={"kind": "rr", "ratio": "1.5"},
            validity_spec=None,
            status="shadow" if status == "shadow" else "active",
            config_hash=f"h-{symbol}",
        )
        db.add(prof)
        await db.flush()

        stock = await make_stock(db, symbol=symbol)
        sig = await _signal(db, stock.id, status=status)
        sig.profile_id = prof.id
        sig.profile_key = prof.key
        sig.outcome_pnl_pct = Decimal("-0.500")
        await db.flush()
        return sig

    async def test_a_shadow_outcome_is_not_counted(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """Canary: on the pre-fix code this returns an intraday row with 1 loss."""
        await create_test_user(db)
        headers = await get_auth_headers(client)
        sig = await self._profiled_signal(db, "SHADOWSTAT", status="shadow")
        await self._outcome(db, str(sig.id), "sl_first")
        await db.commit()

        body = (await client.get("/api/v1/analytics/outcomes", headers=headers)).json()
        intraday = [s for s in body["styles"] if s["style"] == "intraday"]
        # The endpoint emits a row per style regardless; what must be zero are
        # the COUNTS. On the pre-fix code this row reads total=1, losses=1,
        # hit_rate=0.0 — a real strategy's scoreboard showing a shadow result.
        assert len(intraday) == 1
        row = intraday[0]
        assert row["total"] == 0, f"shadow outcome leaked: {row}"
        assert row["losses"] == 0, f"shadow outcome leaked: {row}"
        assert row["entered"] == 0, f"shadow outcome leaked: {row}"
        assert row["hit_rate"] is None, f"shadow outcome leaked: {row}"
        assert row["avg_return_pct"] is None, f"shadow outcome leaked: {row}"

    async def test_a_tradeable_outcome_is_still_counted(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """The filter must not silence real evidence."""
        await create_test_user(db)
        headers = await get_auth_headers(client)
        sig = await self._profiled_signal(db, "REALSTAT", status="active")
        await self._outcome(db, str(sig.id), "sl_first")
        await db.commit()

        body = (await client.get("/api/v1/analytics/outcomes", headers=headers)).json()
        intraday = [s for s in body["styles"] if s["style"] == "intraday"]
        assert len(intraday) == 1
        assert intraday[0]["losses"] == 1

    async def test_provenance_survives_expiry(self, db: AsyncSession) -> None:
        """The deepest part of the finding.

        `status` is a LIFECYCLE field the sweeper overwrites with 'expired' —
        and expiry is exactly when an outcome finalises. Had shadow provenance
        lived only in `status`, a filter on `status <> 'shadow'` would have
        excluded the handful still live and counted the entire finalised
        history. Canary: without `is_shadow` this assertion is unanswerable.
        """
        from app.tasks.expiry_tasks import sweep_expired

        stock = await make_stock(db, symbol="PROVENANCE")
        sig = await _signal(db, stock.id, status="shadow", validity_hours=-1)
        await db.commit()

        await sweep_expired(db, datetime.now(tz=UTC))
        await db.refresh(sig)

        assert sig.status == "expired"      # lifecycle moved on
        assert sig.is_shadow is True        # provenance did not
