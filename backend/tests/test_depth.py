"""Phase 6.8.1 — order-book depth capture.

Covers: top-of-book extraction from a Kite MODE_FULL tick (incl. every
malformed/one-sided/crossed fail-open branch), the Decimal-exact serialize↔parse
round trip, the Redis KEY seam (write → get_live_depth read-back + TTL), and the
consumer integration proving depth capture NEVER disturbs the existing `ltp:`
contract (a depth-less tick writes only the LTP key).
"""

from decimal import Decimal
from typing import Any

import pytest
from app.broker.depth import (
    DEPTH_KEY,
    DEPTH_KEY_TTL_SECONDS,
    Depth,
    extract_top_of_book,
    get_live_depth,
    get_live_depths,
    parse_depth,
    serialize_depth,
    write_depth,
)
from app.broker.tick_consumer import LTP_KEY, TickConsumer
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock


def _full_tick(
    token: int = 123,
    ltp: float = 100.0,
    bid: float = 99.95,
    ask: float = 100.05,
    bid_qty: int = 500,
    ask_qty: int = 300,
) -> dict[str, Any]:
    """A Kite MODE_FULL tick with a two-sided 2-level book."""
    return {
        "instrument_token": token,
        "last_price": ltp,
        "depth": {
            "buy": [
                {"price": bid, "quantity": bid_qty, "orders": 3},
                {"price": round(bid - 0.05, 2), "quantity": 100, "orders": 1},
            ],
            "sell": [
                {"price": ask, "quantity": ask_qty, "orders": 2},
                {"price": round(ask + 0.05, 2), "quantity": 200, "orders": 1},
            ],
        },
    }


class _RedisSpy:
    """Records set/publish without a real Redis (unit tests)."""

    def __init__(self) -> None:
        self.sets: dict[str, tuple[str, int | None]] = {}
        self.publishes: list[tuple[str, str]] = []

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.sets[key] = (value, ex)

    async def publish(self, channel: str, payload: str) -> None:
        self.publishes.append((channel, payload))


# ── extract_top_of_book ──────────────────────────────────────────────────────


class TestExtractTopOfBook:
    def test_valid_full_tick(self) -> None:
        d = extract_top_of_book(_full_tick(bid=99.95, ask=100.05, bid_qty=500, ask_qty=300))
        assert d is not None
        assert d.bid == Decimal("99.95")   # float → Decimal via str, exact
        assert d.ask == Decimal("100.05")
        assert d.bid_qty == 500
        assert d.ask_qty == 300

    def test_missing_depth_is_none(self) -> None:
        assert extract_top_of_book({"instrument_token": 1, "last_price": 100.0}) is None

    def test_depth_not_a_mapping_is_none(self) -> None:
        assert extract_top_of_book({"depth": ["not", "a", "map"]}) is None

    def test_empty_buy_side_is_none(self) -> None:
        tick = _full_tick()
        tick["depth"]["buy"] = []
        assert extract_top_of_book(tick) is None

    def test_empty_sell_side_is_none(self) -> None:
        tick = _full_tick()
        tick["depth"]["sell"] = []
        assert extract_top_of_book(tick) is None

    def test_zero_price_empty_level_is_none(self) -> None:
        # Kite pads empty levels with a 0 price — not a tradeable book.
        assert extract_top_of_book(_full_tick(bid=0.0)) is None
        assert extract_top_of_book(_full_tick(ask=0.0)) is None

    def test_crossed_book_is_none(self) -> None:
        # ask < bid is a transient feed glitch; a negative spread must not fill.
        assert extract_top_of_book(_full_tick(bid=100.10, ask=100.00)) is None

    def test_locked_book_is_valid(self) -> None:
        # ask == bid (spread 0) is legal.
        d = extract_top_of_book(_full_tick(bid=100.00, ask=100.00))
        assert d is not None
        assert d.spread == Decimal("0.00")
        assert d.spread_bps == 0.0

    def test_missing_price_key_is_none(self) -> None:
        tick = _full_tick()
        del tick["depth"]["buy"][0]["price"]
        assert extract_top_of_book(tick) is None

    def test_missing_quantity_defaults_zero(self) -> None:
        tick = _full_tick()
        del tick["depth"]["buy"][0]["quantity"]
        d = extract_top_of_book(tick)
        assert d is not None
        assert d.bid_qty == 0

    def test_non_list_book_sides_are_none(self) -> None:
        # Regression: a truthy but non-list depth side (dict/int/bool) must fail
        # open, not raise on `buy[0]` (a dict → KeyError: 0). If this raised it
        # would escape _handle_tick and roll back the batch's candle upserts.
        for bad in ({"a": 1}, 5, True):
            assert extract_top_of_book({"depth": {"buy": bad, "sell": bad}}) is None
        good = [{"price": 100.0, "quantity": 1}]
        assert extract_top_of_book({"depth": {"buy": {"x": 1}, "sell": good}}) is None
        assert extract_top_of_book({"depth": {"buy": good, "sell": 7}}) is None


# ── Depth properties ─────────────────────────────────────────────────────────


class TestDepthProperties:
    def test_spread_mid_and_bps(self) -> None:
        d = Depth(bid=Decimal("99.95"), ask=Decimal("100.05"), bid_qty=1, ask_qty=1)
        assert d.spread == Decimal("0.10")       # exact Decimal
        assert d.mid == Decimal("100.00")
        assert d.spread_bps == pytest.approx(10.0)   # 0.10 / 100.00 * 10000

    def test_wide_spread_bps(self) -> None:
        # A 50-paisa spread on a ~100 stock ≈ 50 bps (the illiquid-name case).
        d = Depth(bid=Decimal("100.00"), ask=Decimal("100.50"), bid_qty=1, ask_qty=1)
        assert d.spread_bps == pytest.approx(0.50 / 100.25 * 10_000)


# ── serialize / parse round trip ─────────────────────────────────────────────


class TestSerializeParse:
    def test_round_trip_is_decimal_exact(self) -> None:
        original = Depth(bid=Decimal("1234.5500"), ask=Decimal("1235.0000"), bid_qty=7, ask_qty=9)
        parsed = parse_depth(serialize_depth(1, 456, original, ts="2026-08-17T09:20:00+00:00"))
        assert parsed is not None
        assert parsed.bid == Decimal("1234.5500")   # no float drift
        assert parsed.ask == Decimal("1235.0000")
        assert parsed.bid_qty == 7
        assert parsed.ask_qty == 9

    def test_parse_none_or_garbage_is_none(self) -> None:
        assert parse_depth(None) is None
        assert parse_depth("") is None
        assert parse_depth("not json") is None
        assert parse_depth('{"bid": "100"}') is None  # missing keys → None, not raise


# ── write_depth (spy) ────────────────────────────────────────────────────────


class TestWriteDepth:
    async def test_sets_key_with_ttl_and_payload(self) -> None:
        spy = _RedisSpy()
        d = Depth(bid=Decimal("99.95"), ask=Decimal("100.05"), bid_qty=500, ask_qty=300)
        await write_depth(
            spy, stock_id=1, instrument_token=123, depth=d, ts="2026-08-17T00:00:00+00:00"
        )

        key = DEPTH_KEY.format(stock_id=1)
        assert key in spy.sets
        value, ex = spy.sets[key]
        assert ex == DEPTH_KEY_TTL_SECONDS
        assert parse_depth(value) == d   # frozen dataclass equality


# ── Redis KEY seam: write → get_live_depth read-back ─────────────────────────


class TestGetLiveDepthSeam:
    async def test_write_then_read_back(self, db: AsyncSession) -> None:
        import redis.asyncio as aioredis

        stock = await make_stock(db, symbol="DEPTHCO")
        await db.commit()

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        d = Depth(bid=Decimal("512.3000"), ask=Decimal("512.9500"), bid_qty=40, ask_qty=25)
        try:
            await write_depth(
                r, stock_id=stock.id, instrument_token=999, depth=d,
                ts="2026-08-17T09:30:00+00:00",
            )

            got = await get_live_depth(stock.id)
            assert got == d
            # TTL is set and bounded by the configured stale window.
            ttl = await r.ttl(DEPTH_KEY.format(stock_id=stock.id))
            assert 0 < ttl <= DEPTH_KEY_TTL_SECONDS
        finally:
            await r.delete(DEPTH_KEY.format(stock_id=stock.id))
            await r.aclose()

    async def test_missing_key_is_none(self) -> None:
        assert await get_live_depth(stock_id=987654) is None

    async def test_corrupt_value_is_none(self) -> None:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        key = DEPTH_KEY.format(stock_id=424242)
        try:
            await r.set(key, "corrupt-not-json", ex=60)
            assert await get_live_depth(424242) is None  # fail open
        finally:
            await r.delete(key)
            await r.aclose()


# ── Consumer integration: never disturb the ltp: contract ────────────────────


def _make_consumer() -> TickConsumer:
    return TickConsumer(
        access_token="test-token",
        token_stock_map={123: 1},
        redis_url=settings.redis_url,
    )


class _NoopAgg:
    def on_tick(self, tick: dict[str, Any]) -> list[Any]:
        return []


class TestConsumerIntegration:
    async def test_full_tick_writes_both_ltp_and_depth(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.broker import tick_consumer as tc

        monkeypatch.setattr(tc._registry, "get_or_create", lambda _sid: _NoopAgg())
        spy = _RedisSpy()
        wrote = await _make_consumer()._handle_tick(_full_tick(), spy, db=None)

        assert wrote is False
        assert LTP_KEY.format(stock_id=1) in spy.sets           # LTP untouched
        depth_val, ex = spy.sets[DEPTH_KEY.format(stock_id=1)]  # depth captured
        assert ex == DEPTH_KEY_TTL_SECONDS
        parsed = parse_depth(depth_val)
        assert parsed is not None
        assert parsed.bid == Decimal("99.95") and parsed.ask == Decimal("100.05")

    async def test_depthless_tick_writes_only_ltp(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regression: a MODE_LTP / partial tick with no book must leave the
        ltp: contract exactly as before — no depth key, no crash."""
        from app.broker import tick_consumer as tc

        monkeypatch.setattr(tc._registry, "get_or_create", lambda _sid: _NoopAgg())
        spy = _RedisSpy()
        await _make_consumer()._handle_tick(
            {"instrument_token": 123, "last_price": 100.0}, spy, db=None
        )

        assert LTP_KEY.format(stock_id=1) in spy.sets
        assert DEPTH_KEY.format(stock_id=1) not in spy.sets

    async def test_flag_off_skips_depth(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.broker import tick_consumer as tc

        monkeypatch.setattr(tc._registry, "get_or_create", lambda _sid: _NoopAgg())
        monkeypatch.setattr(settings, "depth_capture_enabled", False)
        spy = _RedisSpy()
        await _make_consumer()._handle_tick(_full_tick(), spy, db=None)

        assert LTP_KEY.format(stock_id=1) in spy.sets            # LTP still set
        assert DEPTH_KEY.format(stock_id=1) not in spy.sets      # depth suppressed

    async def test_malformed_depth_does_not_raise_and_keeps_ltp(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regression (bug-hunter #1): a malformed book (non-list sides) must
        not raise out of _handle_tick — otherwise it escapes to the batch
        handler and rolls back earlier candle upserts. LTP must still be set."""
        from app.broker import tick_consumer as tc

        monkeypatch.setattr(tc._registry, "get_or_create", lambda _sid: _NoopAgg())
        spy = _RedisSpy()
        tick = {
            "instrument_token": 123,
            "last_price": 100.0,
            "depth": {"buy": {"a": 1}, "sell": {"b": 2}},
        }
        await _make_consumer()._handle_tick(tick, spy, db=None)  # must NOT raise

        assert LTP_KEY.format(stock_id=1) in spy.sets
        assert DEPTH_KEY.format(stock_id=1) not in spy.sets


class TestGetLiveDepths:
    """A21 — the BATCHED read that every live mark now goes through.

    It shipped with zero tests (quant-verifier #4) while feeding three call sites. The
    assertion that matters is the key→stock_id MAPPING: a mis-zip would mark a position
    against ANOTHER stock's order book, which is silent and expensive."""

    async def test_empty_input_makes_no_round_trip(self) -> None:
        assert await get_live_depths([]) == {}

    async def test_each_book_maps_to_its_own_stock_even_with_a_gap(self) -> None:
        """Three ids where the MIDDLE one has no book: the other two must still map to
        the right stocks. This is the mis-zip canary — with a positional bug the third
        stock would receive the second's book."""
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            await write_depth(
                r, 9001, 111, Depth(Decimal("10.00"), Decimal("10.10"), 1, 1), ts="t"
            )
            await write_depth(
                r, 9003, 333, Depth(Decimal("30.00"), Decimal("30.30"), 3, 3), ts="t"
            )
            out = await get_live_depths([9001, 9002, 9003])
            assert set(out) == {9001, 9003}
            assert out[9001].bid == Decimal("10.00")
            assert out[9003].bid == Decimal("30.00")
        finally:
            await r.delete(DEPTH_KEY.format(stock_id=9001))
            await r.delete(DEPTH_KEY.format(stock_id=9003))
            await r.aclose()

    async def test_a_corrupt_value_is_absent_not_raised(self) -> None:
        """Fail open, like every other microstructure read: a poisoned key must not take
        down the positions list."""
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            await r.set(DEPTH_KEY.format(stock_id=9004), "not json at all")
            await write_depth(
                r, 9005, 555, Depth(Decimal("50.00"), Decimal("50.50"), 5, 5), ts="t"
            )
            out = await get_live_depths([9004, 9005])
            assert 9004 not in out
            assert out[9005].bid == Decimal("50.00")
        finally:
            await r.delete(DEPTH_KEY.format(stock_id=9004))
            await r.delete(DEPTH_KEY.format(stock_id=9005))
            await r.aclose()

    async def test_it_agrees_with_the_single_read_through_both_sides(self) -> None:
        """Integration through the real seam (`write_depth` → read), not a mock: mocking
        it would hide exactly the serialisation mismatch worth catching."""
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            book = Depth(Decimal("1234.5500"), Decimal("1235.0000"), 7, 9)
            await write_depth(r, 9006, 666, book, ts="t")
            batched = (await get_live_depths([9006]))[9006]
            single = await get_live_depth(9006)
            assert single is not None
            assert batched == single == book
        finally:
            await r.delete(DEPTH_KEY.format(stock_id=9006))
            await r.aclose()

