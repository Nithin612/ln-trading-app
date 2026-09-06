"""MCE slice 5a — liquidity junk gate (overlay + provider + order-path wiring + sidecar).

Blocks entries into names too illiquid to exit (median daily traded value below a floor) —
the SRTL 'un-exitable ₹39 micro-cap' archetype, from ohlcv_1d, no new data. Side-independent.
Covers: pure median/floor logic + fail-open; the provider (traded value = close×volume, as-of
anchored); wiring (off/shadow/active block+allow/fail-open); the shadow sidecar partition."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.core.config import settings
from app.models.market_data import OhlcvDaily
from app.models.signal import Signal
from app.models.trading import Position
from app.services import liquidity, liquidity_shadow
from app.signals import liquidity_guard as lg
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock

D = Decimal
FLOOR = D(10_000_000)  # ₹1 crore/day (the config default)


async def _seed_ohlcv(
    db: AsyncSession, stock_id: int, bars: list[tuple[str, int]], *, start: date = date(2026, 8, 1)
) -> None:
    """bars = [(close, volume), …] on consecutive calendar days from `start`."""
    for i, (c, v) in enumerate(bars):
        d = start + timedelta(days=i)
        db.add(
            OhlcvDaily(
                time=datetime(d.year, d.month, d.day, 10, 0, tzinfo=UTC),
                stock_id=stock_id,
                open=D(c),
                high=D(c),
                low=D(c),
                close=D(c),
                volume=v,
                is_complete=True,
            )
        )
    await db.flush()


async def _recent_ohlcv(db: AsyncSession, stock_id: int, bars: list[tuple[str, int]]) -> None:
    # Strictly-past days (…today−n … today−1) so their 10:00-UTC timestamps are < the
    # signal's `created_at` (= now) regardless of the hour the test runs.
    today = datetime.now(tz=UTC).date()
    n = len(bars)
    for i, (c, v) in enumerate(bars):
        d = today - timedelta(days=n - i)
        db.add(
            OhlcvDaily(
                time=datetime(d.year, d.month, d.day, 10, 0, tzinfo=UTC),
                stock_id=stock_id,
                open=D(c),
                high=D(c),
                low=D(c),
                close=D(c),
                volume=v,
                is_complete=True,
            )
        )
    await db.flush()


# ── Pure overlay ──────────────────────────────────────────────────────────────
class TestOverlay:
    def test_median_odd_and_even(self) -> None:
        assert lg._median([D(3), D(1), D(2)]) == D(2)
        assert lg._median([D(1), D(2), D(3), D(4)]) == D("2.5")

    def test_illiquid_blocks_both_sides(self) -> None:
        thin = [D(39_000)] * 3  # ₹39 × 1000 sh — far below the ₹1cr floor
        for side in ("BUY", "SELL"):
            v = lg.evaluate(traded_values=thin, side=side, lookback=3, min_traded_value=FLOOR)
            assert v.has_data is True and v.blocked is True  # side-independent
            assert v.median_traded_value == D(39_000)

    def test_liquid_is_eligible(self) -> None:
        liquid = [D(50_000_000)] * 3  # ₹5cr/day
        v = lg.evaluate(traded_values=liquid, side="BUY", lookback=3, min_traded_value=FLOOR)
        assert v.blocked is False

    def test_boundary_at_floor_is_eligible(self) -> None:
        v = lg.evaluate(traded_values=[FLOOR] * 3, side="BUY", lookback=3, min_traded_value=FLOOR)
        assert v.blocked is False  # median == floor → not strictly below

    def test_insufficient_history_fails_open(self) -> None:
        v = lg.evaluate(traded_values=[D(1)], side="BUY", lookback=5, min_traded_value=FLOOR)
        assert v.has_data is False and v.blocked is False
        assert v.reasons == ["fewer than lookback sessions"]

    def test_as_payload_strings(self) -> None:
        v = lg.evaluate(
            traded_values=[D(39_000)] * 3, side="BUY", lookback=3, min_traded_value=FLOOR
        )
        p = v.as_payload()
        assert p["median_traded_value"] == "39000.00" and p["blocked"] is True
        assert p["side"] == "LONG"

    def test_order_block_reason_modes(self) -> None:
        blocked = lg.evaluate(
            traded_values=[D(1)] * 3, side="BUY", lookback=3, min_traded_value=FLOOR
        )
        assert lg.order_block_reason(blocked, "off") is None
        assert lg.order_block_reason(blocked, "shadow") is None
        assert "liquidity overlay" in (lg.order_block_reason(blocked, "active") or "")
        liquid = lg.evaluate(
            traded_values=[D(50_000_000)] * 3, side="BUY", lookback=3, min_traded_value=FLOOR
        )
        assert lg.order_block_reason(liquid, "active") is None


# ── Provider ────────────────────────────────────────────────────────────────
class TestProvider:
    async def test_traded_value_is_close_times_volume_chronological(self, db: AsyncSession) -> None:
        stock = await make_stock(db, symbol="ACME")
        await _seed_ohlcv(db, stock.id, [("100", 1000), ("110", 2000), ("120", 3000)])
        await db.commit()
        vals = await liquidity.load_traded_values(db, stock.id, lookback=3)
        assert vals == [D(100_000), D(220_000), D(360_000)]  # close×volume, chronological

    async def test_as_of_excludes_future(self, db: AsyncSession) -> None:
        stock = await make_stock(db, symbol="ASOF")
        await _seed_ohlcv(db, stock.id, [("100", 1000), ("100", 1000), ("100", 1000)])
        await db.commit()
        vals = await liquidity.load_traded_values(
            db, stock.id, lookback=10, as_of=datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
        )
        assert len(vals) == 2  # only 2026-08-01 and 08-02

    async def test_unknown_stock_empty(self, db: AsyncSession) -> None:
        assert await liquidity.load_traded_values(db, 999_999, lookback=3) == []


# ── Batched ADV provider (A37) ──────────────────────────────────────────────
class TestBatchedMedianProvider:
    """The denominator of the participation impact. The assertion that matters is the
    stock_id MAPPING: getting it wrong would price one stock's order against another's
    liquidity, silently."""

    async def test_each_stock_gets_its_own_median(self, db: AsyncSession) -> None:
        thin = await make_stock(db, symbol="THINCO")
        deep = await make_stock(db, symbol="DEEPCO")
        await _seed_ohlcv(db, thin.id, [("10", 1000), ("10", 2000), ("10", 3000)])
        await _seed_ohlcv(db, deep.id, [("100", 10_000), ("100", 20_000), ("100", 30_000)])
        await db.commit()
        out = await liquidity.load_median_traded_values(db, [thin.id, deep.id], lookback=3)
        assert out[thin.id] == D(20_000)     # median of 10k/20k/30k
        assert out[deep.id] == D(2_000_000)  # median of 1M/2M/3M

    async def test_a_stock_with_too_little_history_is_absent_not_zero(
        self, db: AsyncSession
    ) -> None:
        """Absent means "unknown" and the caller charges no impact. ZERO would mean
        infinite participation and would make every order in that name unfillable."""
        short = await make_stock(db, symbol="SHORTCO")
        await _seed_ohlcv(db, short.id, [("10", 1000), ("10", 2000)])
        await db.commit()
        out = await liquidity.load_median_traded_values(db, [short.id], lookback=3)
        assert short.id not in out

    async def test_it_agrees_with_the_single_stock_provider(self, db: AsyncSession) -> None:
        """Through both sides: the batch query and the per-stock query must not drift."""
        stock = await make_stock(db, symbol="AGREECO")
        await _seed_ohlcv(db, stock.id, [("100", 1000), ("110", 2000), ("120", 3000)])
        await db.commit()
        batched = (await liquidity.load_median_traded_values(db, [stock.id], lookback=3))[stock.id]
        singles = await liquidity.load_traded_values(db, stock.id, lookback=3)
        assert batched == liquidity.median_traded_value(singles)

    async def test_as_of_excludes_future_sessions(self, db: AsyncSession) -> None:
        stock = await make_stock(db, symbol="BASOF")
        await _seed_ohlcv(db, stock.id, [("100", 1000), ("100", 1000), ("100", 9999)])
        await db.commit()
        out = await liquidity.load_median_traded_values(
            db, [stock.id], lookback=2, as_of=datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
        )
        assert out[stock.id] == D(100_000)  # the 9999-volume bar is after the cutoff

    async def test_empty_and_unknown_are_handled(self, db: AsyncSession) -> None:
        assert await liquidity.load_median_traded_values(db, [], lookback=3) == {}
        assert await liquidity.load_median_traded_values(db, [999_999], lookback=3) == {}


# ── Order-path wiring ─────────────────────────────────────────────────────────
async def _make_signal(
    db: AsyncSession, stock_id: int, *, entry: str = "500.0000", sl: str = "480.0000",
    tp: str = "540.0000",
) -> Signal:
    """Levels are overridable because they must MATCH whatever candles the test seeds.

    With no Redis LTP in tests the paper fill falls back to the newest candle close, so a
    signal priced ₹500 on a ₹39 micro-cap fills ₹441 BELOW its own stop — which
    `place_paper_order` now correctly REJECTS as a position already through its stop
    (2026-09-02). Tests that seed cheap candles must pass matching levels; the ₹39
    archetype itself is worth keeping (it is the SRTL case the liquidity gate targets)."""
    now = datetime.now(tz=UTC)
    sig = Signal(
        stock_id=stock_id, direction="BUY", classification="swing", timeframe="1d",
        entry_price=entry, stop_loss=sl, take_profit=tp,
        suggested_qty=100, confidence_pct=80,
        factor_scores={
            "DOW_TREND": {"weight": 20, "score": 0.8, "explanation": "up"},
            "MACD_CROSS": {"weight": 15, "score": 0.6, "explanation": "x"},
        },
        headline="t", status="active", is_shadow=False,
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


class TestWiring:
    async def test_off_is_true_no_op(self, client, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(settings, "liquidity_gate_mode", "off")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        sig = await _make_signal(db, stock.id)
        await db.commit()
        assert await _order(client, headers, sig.id) == 201

    async def test_active_blocks_illiquid(self, client, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(settings, "liquidity_gate_mode", "active")
        monkeypatch.setattr(settings, "liquidity_lookback", 3)
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        await _recent_ohlcv(db, stock.id, [("39", 1000), ("39", 1200), ("39", 900)])  # ~₹40k/day
        sig = await _make_signal(db, stock.id)
        await db.commit()
        assert await _order(client, headers, sig.id) == 409

    async def test_active_allows_liquid(self, client, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(settings, "liquidity_gate_mode", "active")
        monkeypatch.setattr(settings, "liquidity_lookback", 3)
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        await _recent_ohlcv(db, stock.id, [("500", 100_000)] * 3)  # ₹5cr/day
        sig = await _make_signal(db, stock.id)
        await db.commit()
        assert await _order(client, headers, sig.id) == 201

    async def test_shadow_never_blocks_illiquid(self, client, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(settings, "liquidity_gate_mode", "shadow")
        monkeypatch.setattr(settings, "liquidity_lookback", 3)
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        await _recent_ohlcv(db, stock.id, [("39", 1000)] * 3)
        # Levels matched to the seeded ₹39 candles — see _make_signal's docstring.
        sig = await _make_signal(db, stock.id, entry="39.0000", sl="37.0000", tp="45.0000")
        await db.commit()
        assert await _order(client, headers, sig.id) == 201

    async def test_active_fails_open_no_history(self, client, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(settings, "liquidity_gate_mode", "active")
        monkeypatch.setattr(settings, "liquidity_lookback", 3)
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)  # no ohlcv → fail open
        sig = await _make_signal(db, stock.id)
        await db.commit()
        assert await _order(client, headers, sig.id) == 201

    async def test_active_fails_open_when_load_raises(self, client, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        # Moved to the context loader in Phase 7.1 — patch it where it now lives.
        import app.signals.restriction_context as trading_mod
        from sqlalchemy.exc import SQLAlchemyError

        async def _boom(*_a: object, **_k: object) -> object:
            raise SQLAlchemyError("ohlcv_1d unavailable")

        monkeypatch.setattr(settings, "liquidity_gate_mode", "active")
        monkeypatch.setattr(trading_mod, "load_traded_values", _boom)
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        sig = await _make_signal(db, stock.id)
        await db.commit()
        assert await _order(client, headers, sig.id) == 201


# ── Shadow sidecar ──────────────────────────────────────────────────────────
async def _closed_pos(db: AsyncSession, user_id: int, stock_id: int, sig_id: str, pnl: str) -> None:
    now = datetime.now(tz=UTC)
    db.add(Position(
        user_id=user_id, stock_id=stock_id, signal_id=sig_id, mode="paper", side="LONG",
        quantity=100, avg_entry_price=D("100"), realized_pnl=D(pnl),
        trail_state="none", opened_at=now, closed_at=now,
    ))
    await db.flush()


class TestShadowSidecar:
    async def test_partitions_illiquid_liquid_no_data(self, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(settings, "liquidity_lookback", 3)
        user = await create_test_user(db)
        thin = await make_stock(db, symbol="THIN")
        await _seed_ohlcv(db, thin.id, [("39", 1000)] * 3)  # illiquid
        fat = await make_stock(db, symbol="FAT")
        await _seed_ohlcv(db, fat.id, [("500", 100_000)] * 3)  # liquid
        none = await make_stock(db, symbol="NONE")  # no ohlcv → no data

        s_thin = await _make_signal(db, thin.id)
        await _make_signal(db, fat.id)
        await _make_signal(db, none.id)
        await _closed_pos(db, user.id, thin.id, s_thin.id, "-500")
        await db.commit()

        r = await liquidity_shadow.compute_liquidity_shadow(db)
        assert r.n_signals == 3
        assert r.illiquid.n == 1 and r.liquid.n == 1 and r.no_data.n == 1
        assert r.illiquid.resolved == 1 and r.illiquid.net == D("-500")
        assert len(r.detail) == 2
        ready, reason = liquidity_shadow.liquidity_flip_ready(r)
        assert ready is False and "keep accruing" in reason

    async def test_render_smoke(self, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(settings, "liquidity_lookback", 3)
        stock = await make_stock(db, symbol="ACME")
        await _seed_ohlcv(db, stock.id, [("39", 1000)] * 3)
        await _make_signal(db, stock.id)
        await db.commit()
        md = liquidity_shadow.render_markdown(
            await liquidity_shadow.compute_liquidity_shadow(db), day=date(2026, 8, 21)
        )
        assert "Liquidity shadow" in md and "Per-entry context" in md and "ACME" in md
