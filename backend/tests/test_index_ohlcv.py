"""MCE slice 2 — index EOD OHLC ingestion + benchmark provider + order-path wiring.

Index prices come from the NSE indices bhavcopy CSV (the same file the India-VIX recorder
downloads); the sector-RS overlay is wired onto the paper order path. Covers: CSV parse
(registered indices only, VIX/junk excluded), idempotent ingest, the benchmark provider
(membership mapping + date-alignment + gap-drop), and the wiring (off no-op / shadow
measures-not-blocks / active block+allow / fail-open on missing data)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.core.config import settings
from app.models.market_data import OhlcvDaily
from app.models.signal import Signal
from app.models.stock import Index, IndexOhlcvDaily
from app.models.trading import Position
from app.services import benchmark
from app.services import sector_rs_shadow as srs
from app.services.index_ohlcv_service import ingest_index_ohlcv_date, parse_index_rows
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers, make_stock

D = Decimal

_CSV_HEADER = (
    "Index Name,Index Date,Open Index Value,High Index Value,Low Index Value,"
    "Closing Index Value,Points Change,Change(%),Volume,Turnover (Rs. Cr.),P/E,P/B,Div Yield"
)


def _csv(ds: str) -> str:
    """A realistic ind_close_all_*.csv with the three registered indices plus India VIX
    and an unregistered index (both must be ignored). Trailing cols (points/%/vol/PE…)
    are zero-filled — the parser reads only O/H/L/Close."""
    rows = [
        ("Nifty 50", "24580.10", "24650.00", "24500.00", "24600.25"),
        ("Nifty Bank", "52000.00", "52300.00", "51800.00", "52150.75"),
        ("Nifty Financial Services", "23000.00", "23100.00", "22900.00", "23050.40"),
        ("India VIX", "13.25", "14.10", "12.90", "13.7525"),
        ("Nifty Junk Index", "1000.0", "1010.0", "990.0", "1005.0"),
    ]
    lines = [_CSV_HEADER]
    lines += [f"{name},{ds},{o},{h},{lo},{c},0,0,0,0,0,0,0" for name, o, h, lo, c in rows]
    return "\n".join(lines)


async def _seed_indices(db: AsyncSession) -> dict[str, int]:
    rows = [
        Index(symbol="NIFTY50", name="Nifty 50", exchange="NSE", is_active=True),
        Index(symbol="BANKNIFTY", name="Nifty Bank", exchange="NSE", is_active=True),
        Index(symbol="FINNIFTY", name="Nifty Financial Services", exchange="NSE", is_active=True),
    ]
    db.add_all(rows)
    await db.flush()
    return {r.symbol: r.id for r in rows}


# ── CSV parse (pure) ──────────────────────────────────────────────────────────
class TestParse:
    def test_only_registered_indices_kept(self) -> None:
        name_to_id = {"nifty 50": 1, "nifty bank": 2, "nifty financial services": 3}
        rows = parse_index_rows(_csv("20-08-2026"), name_to_id)
        by_id = {r["index_id"]: r for r in rows}
        assert set(by_id) == {1, 2, 3}  # India VIX + "Nifty Junk Index" excluded
        assert by_id[1]["close"] == D("24600.25")
        assert by_id[1]["open"] == D("24580.10")
        assert by_id[1]["trade_date"] == date(2026, 8, 20)
        assert by_id[2]["close"] == D("52150.75")

    def test_missing_close_or_unparseable_date_skipped(self) -> None:
        bad = _CSV_HEADER + "\nNifty 50,not-a-date,1,2,3,4,0,0,0,0,0,0,0"
        assert parse_index_rows(bad, {"nifty 50": 1}) == []
        noclose = _CSV_HEADER + "\nNifty 50,20-08-2026,1,2,3,-,0,0,0,0,0,0,0"
        assert parse_index_rows(noclose, {"nifty 50": 1}) == []


# ── Ingest (DB) ─────────────────────────────────────────────────────────────
class TestIngest:
    async def test_ingest_then_idempotent(self, db: AsyncSession) -> None:
        await _seed_indices(db)
        await db.commit()

        r1 = await ingest_index_ohlcv_date(db, date(2026, 8, 20), csv_text=_csv("20-08-2026"))
        assert r1["status"] == "ok" and r1["parsed"] == 3 and r1["inserted"] == 3

        # Same CSV again → on_conflict_do_nothing, zero new rows.
        r2 = await ingest_index_ohlcv_date(db, date(2026, 8, 20), csv_text=_csv("20-08-2026"))
        assert r2["inserted"] == 0
        stored = (await db.execute(select(IndexOhlcvDaily))).scalars().all()
        assert len(stored) == 3

    async def test_skips_when_no_indices_registered(self, db: AsyncSession) -> None:
        r = await ingest_index_ohlcv_date(db, date(2026, 8, 20), csv_text=_csv("20-08-2026"))
        assert r["status"] == "skipped" and r["message"] == "no indices registered"


# ── Benchmark provider (DB) ────────────────────────────────────────────────
async def _seed_pairs(
    db: AsyncSession,
    stock_id: int,
    index_id: int,
    pairs: list[tuple[str, str]],
    *,
    skip_index_at: int | None = None,
    start: date = date(2026, 3, 2),
) -> None:
    """Aligned daily bars: stock in ohlcv_1d, benchmark in index_ohlcv_1d, same dates.
    `skip_index_at` omits the benchmark row at that position (an alignment gap)."""
    for i, (sc, bc) in enumerate(pairs):
        d = start + timedelta(days=i)
        db.add(
            OhlcvDaily(
                time=datetime(d.year, d.month, d.day, 10, 0, tzinfo=UTC),
                stock_id=stock_id,
                open=D(sc),
                high=D(sc),
                low=D(sc),
                close=D(sc),
                volume=1000,
                is_complete=True,
            )
        )
        if i != skip_index_at:
            db.add(IndexOhlcvDaily(index_id=index_id, trade_date=d, close=D(bc)))
    await db.flush()


class TestBenchmarkProvider:
    async def test_benchmark_symbol_from_flags(self, db: AsyncSession) -> None:
        mkt = await make_stock(db, symbol="MKT")
        bank = await make_stock(db, symbol="BNK", is_banknifty=True)
        fin = await make_stock(db, symbol="FIN", is_finnifty=True)
        assert benchmark.benchmark_symbol_for(mkt) == "NIFTY50"
        assert benchmark.benchmark_symbol_for(bank) == "BANKNIFTY"  # Bank ⊃ Fin ⊃ market
        assert benchmark.benchmark_symbol_for(fin) == "FINNIFTY"

    async def test_load_context_market_default_trailing_and_aligned(self, db: AsyncSession) -> None:
        ids = await _seed_indices(db)
        stock = await make_stock(db, symbol="ACME")
        await _seed_pairs(
            db, stock.id, ids["NIFTY50"], [(str(100 + i), str(200 + i)) for i in range(5)]
        )
        await db.commit()

        ctx = await benchmark.load_rs_context(db, stock.id, lookback=3)
        assert ctx is not None
        assert ctx.benchmark_symbol == "NIFTY50"
        # lookback + 1 = 4 trailing sessions, chronological.
        assert ctx.stock_closes == [D("101"), D("102"), D("103"), D("104")]
        assert ctx.benchmark_closes == [D("201"), D("202"), D("203"), D("204")]

    async def test_banknifty_member_uses_bank_index(self, db: AsyncSession) -> None:
        ids = await _seed_indices(db)
        stock = await make_stock(db, symbol="HDFCBANK", is_banknifty=True)
        await _seed_pairs(
            db, stock.id, ids["BANKNIFTY"], [(str(100 + i), str(300 + i)) for i in range(3)]
        )
        await db.commit()
        ctx = await benchmark.load_rs_context(db, stock.id, lookback=2)
        assert ctx is not None
        assert ctx.benchmark_symbol == "BANKNIFTY"
        assert ctx.benchmark_closes == [D("300"), D("301"), D("302")]

    async def test_alignment_drops_unmatched_sessions(self, db: AsyncSession) -> None:
        ids = await _seed_indices(db)
        stock = await make_stock(db, symbol="GAP")
        # 5 stock bars, benchmark missing the middle day → inner join keeps 4.
        await _seed_pairs(
            db, stock.id, ids["NIFTY50"], [(str(100 + i), str(200 + i)) for i in range(5)],
            skip_index_at=2,
        )
        await db.commit()
        ctx = await benchmark.load_rs_context(db, stock.id, lookback=10)
        assert ctx is not None
        assert len(ctx.stock_closes) == 4 and len(ctx.benchmark_closes) == 4
        assert D("102") not in ctx.stock_closes  # the dropped (gap) session

    async def test_as_of_excludes_bars_after_decision_time(self, db: AsyncSession) -> None:
        # No look-ahead: context is anchored to the signal's decision time, so a bar
        # dated after `as_of` is not considered (matches the entry-quality ATR anchoring).
        ids = await _seed_indices(db)
        stock = await make_stock(db, symbol="ASOF")
        await _seed_pairs(
            db, stock.id, ids["NIFTY50"], [(str(100 + i), str(200 + i)) for i in range(5)]
        )
        await db.commit()
        # _seed_pairs bars are at 10:00 UTC on 2026-03-02 .. 2026-03-06; cut before the 5th.
        as_of = datetime(2026, 3, 6, 9, 0, tzinfo=UTC)
        ctx = await benchmark.load_rs_context(db, stock.id, lookback=10, as_of=as_of)
        assert ctx is not None
        assert ctx.stock_closes == [D("100"), D("101"), D("102"), D("103")]  # 03-06 (104) excluded
        assert D("104") not in ctx.stock_closes

    async def test_unknown_stock_returns_none(self, db: AsyncSession) -> None:
        assert await benchmark.load_rs_context(db, 999_999, lookback=3) is None


# ── Order-path wiring (mirrors the circuit-gate wiring tests) ─────────────────
async def _make_signal(db: AsyncSession, stock_id: int) -> Signal:
    now = datetime.now(tz=UTC)
    sig = Signal(
        stock_id=stock_id,
        direction="BUY",
        classification="swing",
        timeframe="1d",
        entry_price="500.0000",
        stop_loss="480.0000",
        take_profit="540.0000",
        suggested_qty=100,
        confidence_pct=80,
        factor_scores={
            "DOW_TREND": {"weight": 20, "score": 0.8, "explanation": "uptrend"},
            "MACD_CROSS": {"weight": 15, "score": 0.6, "explanation": "bull cross"},
        },  # ≥2 scoring factors — legal confluence (entry-diversity gate is active)
        headline="BUY TEST",
        status="active",
        is_shadow=False,
        validity_until=now + timedelta(days=5),
        created_at=now,
    )
    db.add(sig)
    await db.flush()
    return sig


async def _seed_index_series(
    db: AsyncSession, index_id: int, closes: list[str], *, start: date = date(2026, 3, 2)
) -> None:
    for i, c in enumerate(closes):
        d = start + timedelta(days=i)
        db.add(IndexOhlcvDaily(index_id=index_id, trade_date=d, close=D(c)))
    await db.flush()


async def _seed_stock_series(
    db: AsyncSession, stock_id: int, closes: list[str], *, start: date = date(2026, 3, 2)
) -> None:
    for i, c in enumerate(closes):
        d = start + timedelta(days=i)
        db.add(
            OhlcvDaily(
                time=datetime(d.year, d.month, d.day, 10, 0, tzinfo=UTC),
                stock_id=stock_id,
                open=D(c),
                high=D(c),
                low=D(c),
                close=D(c),
                volume=1,
                is_complete=True,
            )
        )
    await db.flush()


async def _closed_pos(
    db: AsyncSession, user_id: int, stock_id: int, signal_id: str, realized: str
) -> None:
    now = datetime.now(tz=UTC)
    db.add(
        Position(
            user_id=user_id,
            stock_id=stock_id,
            signal_id=signal_id,
            mode="paper",
            side="LONG",
            quantity=100,
            avg_entry_price=D("100"),
            realized_pnl=D(realized),
            trail_state="none",
            opened_at=now,
            closed_at=now,
        )
    )
    await db.flush()


async def _order(client: AsyncClient, headers: dict[str, str], signal_id: int) -> int:
    r = await client.post(
        "/api/v1/trading/orders",
        json={"signal_id": signal_id, "side": "BUY"},
        headers=headers,
    )
    return r.status_code


class TestSectorRsWiring:
    async def test_off_is_true_no_op(self, client, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(settings, "sector_rs_gate_mode", "off")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        sig = await _make_signal(db, stock.id)
        await db.commit()
        assert await _order(client, headers, sig.id) == 201

    async def test_shadow_measures_but_never_blocks(self, client, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        # Even a clear under-performer trades in shadow — the overlay is inert until active.
        monkeypatch.setattr(settings, "sector_rs_gate_mode", "shadow")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        ids = await _seed_indices(db)
        stock = await make_stock(db)
        await _seed_pairs(
            db, stock.id, ids["NIFTY50"],
            [(str(100.0), str(round(100 + i, 4))) for i in range(21)],  # stock flat, bench +20%
        )
        sig = await _make_signal(db, stock.id)
        await db.commit()
        assert await _order(client, headers, sig.id) == 201

    async def test_active_blocks_underperformer(self, client, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(settings, "sector_rs_gate_mode", "active")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        ids = await _seed_indices(db)
        stock = await make_stock(db)
        # 21 aligned bars: stock flat (0%), benchmark 100→120 (+20%) → excess −20% → blocked.
        await _seed_pairs(
            db, stock.id, ids["NIFTY50"],
            [("100.0000", str(round(100 + i, 4))) for i in range(21)],
        )
        sig = await _make_signal(db, stock.id)
        await db.commit()
        assert await _order(client, headers, sig.id) == 409

    async def test_active_allows_outperformer(self, client, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(settings, "sector_rs_gate_mode", "active")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        ids = await _seed_indices(db)
        stock = await make_stock(db)
        # stock 100→130 (+30%), benchmark 100→105 (+5%) → excess +25% → allowed.
        await _seed_pairs(
            db, stock.id, ids["NIFTY50"],
            [(str(round(100 + 1.5 * i, 4)), str(round(100 + 0.25 * i, 4))) for i in range(21)],
        )
        sig = await _make_signal(db, stock.id)
        await db.commit()
        assert await _order(client, headers, sig.id) == 201

    async def test_active_fails_open_when_no_index_data(self, client, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        # Active, but no index_ohlcv_1d rows → no benchmark → fail open (trade allowed).
        monkeypatch.setattr(settings, "sector_rs_gate_mode", "active")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        await _seed_indices(db)  # registry present, but NO price rows
        stock = await make_stock(db)
        sig = await _make_signal(db, stock.id)
        await db.commit()
        assert await _order(client, headers, sig.id) == 201

    async def test_fails_open_when_load_raises_db_error(self, client, db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        # A DB fault in the benchmark read (e.g. the table not yet migrated, a JOIN
        # timeout) must NOT 500 the order nor poison the session: the savepoint rolls
        # back and the overlay fails open, so place_paper_order still runs (201).
        import app.api.v1.trading as trading_mod
        from sqlalchemy.exc import SQLAlchemyError

        async def _boom(*_a: object, **_k: object) -> object:
            raise SQLAlchemyError("index_ohlcv_1d unavailable")

        monkeypatch.setattr(settings, "sector_rs_gate_mode", "active")
        monkeypatch.setattr(trading_mod, "load_rs_context", _boom)
        await create_test_user(db)
        headers = await get_auth_headers(client)
        await _seed_indices(db)
        stock = await make_stock(db)
        sig = await _make_signal(db, stock.id)
        await db.commit()
        assert await _order(client, headers, sig.id) == 201


# ── Shadow sidecar (slice 3): forward-evidence measurement + per-entry context ──
class TestSectorRsShadow:
    async def test_partitions_blocked_passed_no_data_with_outcome(self, db: AsyncSession) -> None:
        user = await create_test_user(db)
        ids = await _seed_indices(db)
        # One NIFTY 50 series (+5% over 21 sessions), stocks judged against it.
        await _seed_index_series(
            db, ids["NIFTY50"], [str(round(100 + 0.25 * i, 4)) for i in range(21)]
        )
        under = await make_stock(db, symbol="UNDER")  # flat vs +5% → would-block
        await _seed_stock_series(db, under.id, ["100.0000"] * 21)
        over = await make_stock(db, symbol="OVER")  # +30% vs +5% → eligible
        await _seed_stock_series(db, over.id, [str(round(100 + 1.5 * i, 4)) for i in range(21)])
        nodata = await make_stock(db, symbol="NODATA")  # no bars → no benchmark data

        su = await _make_signal(db, under.id)
        await _make_signal(db, over.id)
        await _make_signal(db, nodata.id)
        await _closed_pos(db, user.id, under.id, su.id, "-500")  # blocked + resolved (losing)
        await db.commit()

        r = await srs.compute_sector_rs_shadow(db)
        assert r.n_signals == 3
        assert r.blocked.n == 1 and r.passed.n == 1 and r.no_data.n == 1
        assert r.blocked.resolved == 1 and r.blocked.net == D("-500")
        assert r.passed.resolved == 0  # the out-performer has no closed position
        assert len(r.detail) == 2  # under + over assessable; nodata excluded
        ready, reason = srs.rs_flip_ready(r)
        assert ready is False and "keep accruing" in reason  # 1 < 20 resolved

    async def test_render_markdown_shows_per_entry_context(self, db: AsyncSession) -> None:
        ids = await _seed_indices(db)
        await _seed_index_series(
            db, ids["NIFTY50"], [str(round(100 + 0.25 * i, 4)) for i in range(21)]
        )
        stock = await make_stock(db, symbol="ACME")
        await _seed_stock_series(db, stock.id, ["100.0000"] * 21)
        await _make_signal(db, stock.id)
        await db.commit()
        md = srs.render_markdown(await srs.compute_sector_rs_shadow(db), day=date(2026, 8, 20))
        assert "Sector/index relative-strength shadow" in md
        assert "Per-entry context" in md
        assert "ACME" in md and "NIFTY50" in md
