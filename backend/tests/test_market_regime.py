"""MCE slice 4 — market-regime overlay (200-DMA + VIX), provider, order-path wiring,
shadow sidecar, and the deep index/VIX backfill.

The broadest top-down filter: a long into a market below its N-DMA (a short into one above)
is fighting the tape. Overlay-lane, shadow-first, fail-open. VIX is reported but never gates
(shallow history). Covers: pure overlay math + both sides + fail-open branches + VIX
informational; the market-wide provider (as-of anchoring, missing index); order-path wiring
(off/shadow/active block+allow/fail-open); the shadow sidecar partition + banner; and the
backfill's one-download-serves-both-feeds contract."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.core.config import settings
from app.models.fo_data import IndiaVixDaily
from app.models.signal import Signal
from app.models.stock import Index, IndexOhlcvDaily
from app.models.trading import Position
from app.services import benchmark
from app.services import market_regime_shadow as mrs
from app.signals import market_regime as mr
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock

D = Decimal


async def _seed_nifty(db: AsyncSession, closes: list[tuple[date, str]]) -> int:
    """Seed NIFTY50 index bars; returns the index_id."""
    idx = Index(symbol="NIFTY50", name="Nifty 50", exchange="NSE", is_active=True)
    db.add(idx)
    await db.flush()
    for d, c in closes:
        db.add(IndexOhlcvDaily(index_id=idx.id, trade_date=d, close=D(c)))
    await db.flush()
    return idx.id


# ── Pure overlay ──────────────────────────────────────────────────────────────
class TestOverlay:
    def test_long_below_dma_blocked_short_eligible(self) -> None:
        # closes 110,100,90 → DMA=100, latest=90 → below (gap −10%).
        for side, blocked in (("BUY", True), ("SELL", False)):
            v = mr.evaluate(side=side, market_closes=[D("110"), D("100"), D("90")], dma_period=3)
            assert v.has_data is True
            assert v.dma == D("100")
            assert v.gap_pct == D("-10")
            assert v.blocked is blocked

    def test_long_above_dma_eligible_short_blocked(self) -> None:
        # closes 90,100,110 → DMA=100, latest=110 → above (gap +10%).
        for side, blocked in (("BUY", False), ("SELL", True)):
            v = mr.evaluate(side=side, market_closes=[D("90"), D("100"), D("110")], dma_period=3)
            assert v.gap_pct == D("10")
            assert v.blocked is blocked

    def test_at_the_dma_is_eligible_both_sides(self) -> None:
        for side in ("BUY", "SELL"):
            v = mr.evaluate(side=side, market_closes=[D("100"), D("100"), D("100")], dma_period=3)
            assert v.blocked is False  # close == DMA, neither strictly below nor above

    def test_buffer_prevents_flag_just_across_the_line(self) -> None:
        closes = [D("100"), D("100"), D("98")]  # DMA≈99.33, latest 98 → 0.67% below
        assert mr.evaluate(side="BUY", market_closes=closes, dma_period=3).blocked is True
        # a 2% buffer moves the trigger to ~97.35 → 98 is inside → not flagged
        v = mr.evaluate(side="BUY", market_closes=closes, dma_period=3, buffer_pct=D("2"))
        assert v.blocked is False

    def test_insufficient_history_fails_open(self) -> None:
        v = mr.evaluate(side="BUY", market_closes=[D("100"), D("101")], dma_period=5)
        assert v.has_data is False and v.blocked is False
        assert v.reasons == ["market history shorter than dma_period"]

    def test_degenerate_dma_fails_open(self) -> None:
        v = mr.evaluate(side="BUY", market_closes=[D("0"), D("0"), D("0")], dma_period=3)
        assert v.blocked is False and v.reasons == ["degenerate DMA"]

    def test_vix_is_informational_never_blocks(self) -> None:
        # Above-DMA long (eligible) with a screaming VIX must still be eligible.
        v = mr.evaluate(
            side="BUY", market_closes=[D("90"), D("100"), D("110")], dma_period=3,
            vix=D("35"), vix_threshold=D("20"),
        )
        assert v.vix == D("35") and v.vix_elevated is True
        assert v.blocked is False  # VIX never gates

    def test_as_payload_decimals_as_strings(self) -> None:
        v = mr.evaluate(side="BUY", market_closes=[D("110"), D("100"), D("90")], dma_period=3)
        p = v.as_payload()
        assert p["gap_pct"] == "-10.0000" and p["dma"] == "100.0000"
        assert p["market_symbol"] == "NIFTY50" and p["blocked"] is True

    def test_order_block_reason_modes(self) -> None:
        blocked = mr.evaluate(side="BUY", market_closes=[D("110"), D("100"), D("90")], dma_period=3)
        assert mr.order_block_reason(blocked, "off") is None
        assert mr.order_block_reason(blocked, "shadow") is None
        assert "market-regime overlay" in (mr.order_block_reason(blocked, "active") or "")
        elig = mr.evaluate(side="BUY", market_closes=[D("90"), D("100"), D("110")], dma_period=3)
        assert mr.order_block_reason(elig, "active") is None


# ── Provider (market-wide, DB) ─────────────────────────────────────────────
class TestProvider:
    async def test_loads_trailing_closes_and_vix_chronological(self, db: AsyncSession) -> None:
        base = date(2026, 8, 1)
        await _seed_nifty(db, [(base + timedelta(days=i), str(100 + i)) for i in range(5)])
        db.add(IndiaVixDaily(trade_date=base + timedelta(days=4), close=D("14.25")))
        await db.commit()
        ctx = await benchmark.load_market_regime_context(db, dma_period=3)
        assert ctx.market_symbol == "NIFTY50"
        assert ctx.market_closes == [D("102"), D("103"), D("104")]  # last 3, chronological
        assert ctx.vix == D("14.25")

    async def test_as_of_excludes_future_sessions(self, db: AsyncSession) -> None:
        base = date(2026, 8, 1)
        await _seed_nifty(db, [(base + timedelta(days=i), str(100 + i)) for i in range(5)])
        await db.commit()
        # as-of the 3rd bar (2026-08-03) → only 100,101,102 visible
        ctx = await benchmark.load_market_regime_context(
            db, dma_period=10, as_of=datetime(2026, 8, 3, 12, 0, tzinfo=UTC)
        )
        assert ctx.market_closes == [D("100"), D("101"), D("102")]

    async def test_missing_index_returns_empty(self, db: AsyncSession) -> None:
        ctx = await benchmark.load_market_regime_context(db, dma_period=3)
        assert ctx.market_closes == [] and ctx.vix is None


# ── Order-path wiring ─────────────────────────────────────────────────────────
async def _make_signal(db: AsyncSession, stock_id: int) -> Signal:
    now = datetime.now(tz=UTC)
    sig = Signal(
        stock_id=stock_id, direction="BUY", classification="swing", timeframe="1d",
        entry_price="500.0000", stop_loss="480.0000", take_profit="540.0000",
        suggested_qty=100, confidence_pct=80,
        factor_scores={
            "DOW_TREND": {"weight": 20, "score": 0.8, "explanation": "uptrend"},
            "MACD_CROSS": {"weight": 15, "score": 0.6, "explanation": "bull cross"},
        },
        headline="BUY TEST", status="active", is_shadow=False,
        validity_until=now + timedelta(days=5), created_at=now,
    )
    db.add(sig)
    await db.flush()
    return sig


async def _order(client: AsyncClient, headers: dict[str, str], signal_id: int) -> int:
    r = await client.post(
        "/api/v1/trading/orders", json={"signal_id": signal_id, "side": "BUY"}, headers=headers
    )
    return r.status_code


async def _recent_nifty(db: AsyncSession, closes: list[str]) -> None:
    today = datetime.now(tz=UTC).date()
    n = len(closes)
    await _seed_nifty(db, [(today - timedelta(days=n - 1 - i), c) for i, c in enumerate(closes)])


class TestWiring:
    async def test_off_is_true_no_op(self, client, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(settings, "market_regime_gate_mode", "off")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        sig = await _make_signal(db, stock.id)
        await db.commit()
        assert await _order(client, headers, sig.id) == 201

    async def test_active_blocks_long_in_down_market(self, client, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(settings, "market_regime_gate_mode", "active")
        monkeypatch.setattr(settings, "market_regime_dma_period", 3)
        await create_test_user(db)
        headers = await get_auth_headers(client)
        await _recent_nifty(db, ["110", "100", "90"])  # latest 90 < DMA 100 → down
        stock = await make_stock(db)
        sig = await _make_signal(db, stock.id)
        await db.commit()
        assert await _order(client, headers, sig.id) == 409

    async def test_active_allows_long_in_up_market(self, client, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(settings, "market_regime_gate_mode", "active")
        monkeypatch.setattr(settings, "market_regime_dma_period", 3)
        await create_test_user(db)
        headers = await get_auth_headers(client)
        await _recent_nifty(db, ["90", "100", "110"])  # latest 110 > DMA 100 → up
        stock = await make_stock(db)
        sig = await _make_signal(db, stock.id)
        await db.commit()
        assert await _order(client, headers, sig.id) == 201

    async def test_shadow_never_blocks_even_down_market(self, client, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(settings, "market_regime_gate_mode", "shadow")
        monkeypatch.setattr(settings, "market_regime_dma_period", 3)
        await create_test_user(db)
        headers = await get_auth_headers(client)
        await _recent_nifty(db, ["110", "100", "90"])
        stock = await make_stock(db)
        sig = await _make_signal(db, stock.id)
        await db.commit()
        assert await _order(client, headers, sig.id) == 201

    async def test_active_fails_open_no_index_data(self, client, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(settings, "market_regime_gate_mode", "active")
        monkeypatch.setattr(settings, "market_regime_dma_period", 3)
        await create_test_user(db)
        headers = await get_auth_headers(client)  # no NIFTY50 seeded → fail open
        stock = await make_stock(db)
        sig = await _make_signal(db, stock.id)
        await db.commit()
        assert await _order(client, headers, sig.id) == 201

    async def test_active_fails_open_when_load_raises(self, client, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        # Moved to the context loader in Phase 7.1 — patch it where it now lives.
        import app.signals.restriction_context as trading_mod
        from sqlalchemy.exc import SQLAlchemyError

        async def _boom(*_a: object, **_k: object) -> object:
            raise SQLAlchemyError("index_ohlcv_1d unavailable")

        monkeypatch.setattr(settings, "market_regime_gate_mode", "active")
        monkeypatch.setattr(trading_mod, "load_market_regime_context", _boom)
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        sig = await _make_signal(db, stock.id)
        await db.commit()
        assert await _order(client, headers, sig.id) == 201  # DB fault → fail open


# ── Shadow sidecar ──────────────────────────────────────────────────────────
async def _sig_at(db: AsyncSession, stock_id: int, created_at: datetime) -> Signal:
    sig = Signal(
        stock_id=stock_id, direction="BUY", classification="swing", timeframe="1d",
        entry_price="500.0000", stop_loss="480.0000", take_profit="540.0000",
        suggested_qty=100, confidence_pct=80,
        factor_scores={"DOW_TREND": {"weight": 20, "score": 0.8, "explanation": "up"}},
        headline="t", status="active", is_shadow=False,
        validity_until=created_at + timedelta(days=5), created_at=created_at,
    )
    db.add(sig)
    await db.flush()
    return sig


async def _closed_pos(db: AsyncSession, user_id: int, stock_id: int, sig_id: str, pnl: str) -> None:
    now = datetime.now(tz=UTC)
    db.add(Position(
        user_id=user_id, stock_id=stock_id, signal_id=sig_id, mode="paper", side="LONG",
        quantity=100, avg_entry_price=D("100"), realized_pnl=D(pnl),
        trail_state="none", opened_at=now, closed_at=now,
    ))
    await db.flush()


class TestShadowSidecar:
    async def test_partitions_eligible_blocked_no_data(self, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(settings, "market_regime_dma_period", 3)
        user = await create_test_user(db)
        # NIFTY50 up-then-down so different as-ofs see opposite regimes (all >= OUTCOME_EPOCH).
        days = [date(2026, 8, d) for d in (1, 4, 5, 6, 7)]
        await _seed_nifty(db, list(zip(days, ["90", "100", "110", "100", "90"], strict=True)))
        stock = await make_stock(db)
        # as-of 08-05 → window [90,100,110] DMA100 close110 → BUY eligible
        s_elig = await _sig_at(db, stock.id, datetime(2026, 8, 5, 12, 0, tzinfo=UTC))
        # as-of 08-07 → window [110,100,90] DMA100 close90 → BUY blocked
        s_block = await _sig_at(db, stock.id, datetime(2026, 8, 7, 12, 0, tzinfo=UTC))
        # as-of 07-31 (>= epoch, before any bar) → no data
        await _sig_at(db, stock.id, datetime(2026, 7, 31, 12, 0, tzinfo=UTC))
        await _closed_pos(db, user.id, stock.id, s_block.id, "-500")
        await db.commit()

        r = await mrs.compute_market_regime_shadow(db)
        assert r.n_signals == 3
        assert r.eligible.n == 1 and r.blocked.n == 1 and r.no_data.n == 1
        assert r.blocked.resolved == 1 and r.blocked.net == D("-500")
        assert len(r.detail) == 2  # the two with market data
        ready, reason = mrs.regime_flip_ready(r)
        assert ready is False and "keep accruing" in reason
        assert s_elig.id  # (referenced)

    async def test_render_smoke(self, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(settings, "market_regime_dma_period", 3)
        await _seed_nifty(db, [(date(2026, 8, 1 + i), str(100 + i)) for i in range(3)])
        stock = await make_stock(db, symbol="ACME")
        await _sig_at(db, stock.id, datetime(2026, 8, 3, 12, 0, tzinfo=UTC))
        await db.commit()
        md = mrs.render_markdown(await mrs.compute_market_regime_shadow(db), day=date(2026, 8, 20))
        assert "Market-regime shadow" in md and "Per-entry context" in md and "ACME" in md


# ── Deep backfill (one download serves both index + VIX) ──────────────────────
_CSV_HEADER = (
    "Index Name,Index Date,Open Index Value,High Index Value,Low Index Value,"
    "Closing Index Value,Points Change,Change(%),Volume,Turnover (Rs. Cr.),P/E,P/B,Div Yield"
)


def _indices_csv(ds: str) -> str:
    rows = [("Nifty 50", "24580.10"), ("India VIX", "13.75")]
    lines = [_CSV_HEADER] + [f"{n},{ds},0,0,0,{c},0,0,0,0,0,0,0" for n, c in rows]
    return "\n".join(lines)


class TestBackfill:
    async def test_one_download_feeds_index_and_vix_idempotent(self, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        import scripts.backfill_indices as bf
        from sqlalchemy import func, select

        # NIFTY50 must be registered for the index ingest to key on it.
        db.add(Index(symbol="NIFTY50", name="Nifty 50", exchange="NSE", is_active=True))
        await db.commit()

        calls = {"n": 0}

        async def _fake_download(d: date) -> str | None:
            calls["n"] += 1
            return _indices_csv(d.strftime("%d-%m-%Y"))

        monkeypatch.setattr(bf, "download_indices_csv", _fake_download)
        # 2026-08-03 is a Mon; 08-04 Tue → 2 weekday sessions.
        rc = await bf.backfill(date(2026, 8, 3), date(2026, 8, 4), delay=0.0, db=db)
        assert rc == 0
        assert calls["n"] == 2  # ONE download per session (serves both feeds)

        idx_n = (await db.execute(select(func.count()).select_from(IndexOhlcvDaily))).scalar()
        vix_n = (await db.execute(select(func.count()).select_from(IndiaVixDaily))).scalar()
        assert idx_n == 2 and vix_n == 2

        # Idempotent: a second pass inserts nothing new.
        await bf.backfill(date(2026, 8, 3), date(2026, 8, 4), delay=0.0, db=db)
        assert (await db.execute(select(func.count()).select_from(IndexOhlcvDaily))).scalar() == 2
        assert (await db.execute(select(func.count()).select_from(IndiaVixDaily))).scalar() == 2

    async def test_network_blip_on_one_session_does_not_abort_run(self, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        import httpx
        import scripts.backfill_indices as bf
        from sqlalchemy import select

        db.add(Index(symbol="NIFTY50", name="Nifty 50", exchange="NSE", is_active=True))
        await db.commit()

        async def _flaky(d: date) -> str | None:
            if d == date(2026, 8, 4):  # session 2 of 3 blips transiently
                raise httpx.ConnectError("NSE archive timeout")
            return _indices_csv(d.strftime("%d-%m-%Y"))

        monkeypatch.setattr(bf, "download_indices_csv", _flaky)
        # 08-03 Mon · 08-04 Tue (fails) · 08-05 Wed — the blip must NOT abort the run.
        rc = await bf.backfill(date(2026, 8, 3), date(2026, 8, 5), delay=0.0, db=db)
        assert rc == 0
        idx_dates = (await db.execute(select(IndexOhlcvDaily.trade_date))).scalars().all()
        assert set(idx_dates) == {date(2026, 8, 3), date(2026, 8, 5)}  # 1 & 3 survived


class TestVixTrailingPercentile:
    """H3 — the VIX companion is a trailing percentile, not an inherited absolute.

    A fixed `20` is a US-derived number that does not describe this market: across the 784
    sessions in `india_vix_daily` (2023-07-03 → 2026-09-04) India VIX has a **median of
    13.35** and exceeds 20 on only **5.1%** of days, so "20 = elevated" is really the
    **94.8th percentile** — an extreme, not the "somewhat nervous" marker it reads as. The
    80th percentile sits at 15.73.

    VIX never blocks, so none of this changes a gate decision — it changes what the shadow
    sidecar reports about market conditions, and it does so self-calibratingly.
    """

    def _history(self) -> list[Decimal]:
        # 300 sessions spanning 10.0–16.5, shaped like the real distribution's body.
        return [Decimal(str(10 + (i % 14) * 0.5)) for i in range(300)]

    def test_percentile_is_preferred_when_history_is_deep_enough(self) -> None:
        elevated, pct, basis = mr.vix_standing(
            Decimal("15.80"),
            self._history(),
            percentile_threshold=Decimal("0.80"),
            absolute_threshold=Decimal(20),
        )
        assert basis == "percentile"
        assert pct is not None and pct > Decimal("0.80")
        assert elevated is True

    def test_a_quiet_tape_is_not_elevated_even_though_it_would_pass_no_absolute(
        self,
    ) -> None:
        elevated, pct, basis = mr.vix_standing(
            Decimal("10.68"),  # the real latest VIX, at its own 7th percentile
            self._history(),
            percentile_threshold=Decimal("0.80"),
            absolute_threshold=Decimal(20),
        )
        assert elevated is False and basis == "percentile"
        assert pct is not None and pct < Decimal("0.30")

    def test_the_inherited_absolute_would_almost_never_fire(self) -> None:
        """⭐ The point of H3, stated as a test. A threshold that fires on ~5% of sessions
        is not a regime marker, and the percentile threshold sits far below it."""
        hist = self._history()
        over_20 = sum(1 for h in hist if h > Decimal(20))
        assert over_20 == 0, "this body-of-distribution history never reaches the absolute"
        elevated, _, basis = mr.vix_standing(
            Decimal("16.40"), hist,
            percentile_threshold=Decimal("0.80"), absolute_threshold=Decimal(20),
        )
        assert elevated is True and basis == "percentile", (
            "a session near the top of its own range must read as elevated even though it "
            "is nowhere near the inherited absolute"
        )

    def test_falls_back_to_the_absolute_when_history_is_too_shallow(self) -> None:
        """Below MIN_VIX_HISTORY a rank is a handful of atoms; the absolute is more honest
        than a percentile computed from nothing."""
        elevated, pct, basis = mr.vix_standing(
            Decimal("21"),
            self._history()[: mr.MIN_VIX_HISTORY - 1],
            percentile_threshold=Decimal("0.80"),
            absolute_threshold=Decimal(20),
        )
        assert basis == "absolute"
        assert pct is None
        assert elevated is True

    def test_no_history_at_all_falls_back(self) -> None:
        _, pct, basis = mr.vix_standing(
            Decimal("21"), None,
            percentile_threshold=Decimal("0.80"), absolute_threshold=Decimal(20),
        )
        assert basis == "absolute" and pct is None

    def test_absent_vix_reports_nothing_rather_than_false(self) -> None:
        """`False` would claim "not elevated", which we did not measure."""
        assert mr.vix_standing(
            None, self._history(),
            percentile_threshold=Decimal("0.80"), absolute_threshold=Decimal(20),
        ) == (None, None, None)

    def test_the_basis_reaches_the_payload(self) -> None:
        """The two bases must never be confused, so the verdict says which one ran."""
        v = mr.evaluate(
            side="BUY",
            market_closes=[Decimal(100)] * 200,
            vix=Decimal("15.80"),
            vix_history=self._history(),
        )
        assert v.as_payload()["vix_basis"] == "percentile"
        assert v.as_payload()["vix_percentile"] is not None

    def test_vix_still_never_blocks(self) -> None:
        """The invariant H3 must not disturb: VIX is informational, full stop."""
        rising = [Decimal(100 + i) for i in range(300)]  # market well above its DMA
        v = mr.evaluate(
            side="BUY",
            market_closes=rising,
            vix=Decimal("27"),
            vix_history=self._history(),
        )
        assert v.vix_elevated is True
        assert v.blocked is False
