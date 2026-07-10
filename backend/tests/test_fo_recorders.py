"""Tests for the Phase 0 F&O data recorders.

Covers: UDiFF bhavcopy parsing + idempotent upsert, India VIX parsing +
upsert, NFO instrument mapping (strike), chain instrument selection,
quote→row mapping, snapshot insertion, and market-hours gating.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.broker.kite_client import map_instrument_rows
from app.models.broker import KiteInstrument
from app.models.fo_data import FoBhavcopy, IndiaVixDaily, OptionChainSnapshot
from app.services.chain_recorder import (
    ChainInstrument,
    insert_snapshot_rows,
    quotes_to_rows,
    record_chain_snapshots,
    select_chain_instruments,
    spot_ltp_key,
)
from app.services.fo_bhavcopy_service import (
    ingest_fo_bhavcopy_date,
    parse_fo_bhavcopy_csv,
)
from app.services.vix_service import ingest_vix_date, parse_vix_row
from app.tasks.fo_tasks import _within_market_hours
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

# ── UDiFF F&O bhavcopy ────────────────────────────────────────────────────────

_UDIFF_HEADER = (
    "TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,"
    "XpryDt,FininstrmActlXpryDt,StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,"
    "LwPric,ClsPric,LastPric,PrvsClsgPric,UndrlygPric,SttlmPric,OpnIntrst,"
    "ChngInOpnIntrst,TtlTradgVol,TtlTrfVal,TtlNbOfTxsExctd,SsnId,NewBrdLotQty"
)

_UDIFF_ROWS = "\n".join([
    _UDIFF_HEADER,
    # Index future
    "2026-07-03,2026-07-03,FO,NSE,IDF,35000,,NIFTY,,2026-07-30,2026-07-30,0,,"
    "NIFTYFUT,24500.5,24620,24480,24600.25,24601,24450,24580.5,24600.25,"
    "14200000,120000,250000,9.9e9,180000,F1,75",
    # Index option CE
    "2026-07-03,2026-07-03,FO,NSE,IDO,35001,,NIFTY,,2026-07-09,2026-07-09,"
    "24600,CE,NIFTYCE,150.5,180,120,165.35,166,140,24580.5,165.35,"
    "5400000,340000,900000,1.1e9,240000,F1,75",
    # Stock option PE
    "2026-07-03,2026-07-03,FO,NSE,STO,35002,INE002A01018,RELIANCE,,2026-07-30,"
    "2026-07-30,1400,PE,RELPE,22.5,30,18,25.85,26,24,1420.6,25.85,"
    "820000,15000,45000,2.2e8,9000,F1,500",
    # Currency-style row that must be skipped
    "2026-07-03,2026-07-03,CD,NSE,FUTCUR,9,,USDINR,,2026-07-28,2026-07-28,0,,"
    "USDFUT,84.1,84.2,84.0,84.15,84.15,84.05,,84.15,100,10,1000,1e6,50,F1,1000",
])


class TestFoBhavcopyParser:
    def test_parses_futures_and_options(self) -> None:
        rows = parse_fo_bhavcopy_csv(_UDIFF_ROWS)
        assert len(rows) == 3

        fut = next(r for r in rows if r.instrument == "FUT")
        assert fut.symbol == "NIFTY"
        assert fut.expiry_date == date(2026, 7, 30)
        assert fut.strike == Decimal("0")
        assert fut.close == Decimal("24600.25")
        assert fut.open_interest == 14200000
        assert fut.change_in_oi == 120000
        assert fut.volume_contracts == 250000

        ce = next(r for r in rows if r.instrument == "CE")
        assert ce.strike == Decimal("24600")
        assert ce.underlying_close == Decimal("24580.5")
        assert ce.change_in_oi == 340000

        pe = next(r for r in rows if r.instrument == "PE")
        assert pe.symbol == "RELIANCE"
        assert pe.strike == Decimal("1400")

    def test_skips_non_derivative_and_garbage(self) -> None:
        garbage = _UDIFF_HEADER + "\n" + ",".join(["x"] * 29)
        assert parse_fo_bhavcopy_csv(garbage) == []


class TestFoBhavcopyIngest:
    async def test_ingest_is_idempotent(self, db: AsyncSession) -> None:
        first = await ingest_fo_bhavcopy_date(db, date(2026, 7, 3), csv_text=_UDIFF_ROWS)
        assert first["status"] == "ok"
        assert first["inserted"] == 3

        second = await ingest_fo_bhavcopy_date(db, date(2026, 7, 3), csv_text=_UDIFF_ROWS)
        assert second["inserted"] == 0  # ON CONFLICT DO NOTHING

        count = (
            await db.execute(select(func.count()).select_from(FoBhavcopy))
        ).scalar_one()
        assert count == 3

    async def test_empty_csv_skipped(self, db: AsyncSession) -> None:
        result = await ingest_fo_bhavcopy_date(db, date(2026, 7, 3), csv_text=_UDIFF_HEADER)
        assert result["status"] == "skipped"


# ── India VIX ─────────────────────────────────────────────────────────────────

_INDICES_CSV = "\n".join([
    "Index Name,Index Date,Open Index Value,High Index Value,Low Index Value,"
    "Closing Index Value,Points Change,Change(%),Volume,Turnover (Rs. Cr.),P/E,P/B,Div Yield",
    'Nifty 50,03-07-2026,24580.10,24650.00,24500.00,24600.25,20.15,0.08,'
    "250000000,25000.5,22.5,3.8,1.2",
    'India VIX,03-07-2026,13.25,14.10,12.90,13.7525,0.50,3.77,0,0,0,0,0',
])


class TestVix:
    def test_parse_vix_row(self) -> None:
        row = parse_vix_row(_INDICES_CSV)
        assert row is not None
        assert row["trade_date"] == date(2026, 7, 3)
        assert row["close"] == Decimal("13.7525")
        assert row["high"] == Decimal("14.10")

    def test_parse_returns_none_without_vix(self) -> None:
        assert parse_vix_row(_INDICES_CSV.split("\n")[0]) is None

    async def test_ingest_idempotent(self, db: AsyncSession) -> None:
        r1 = await ingest_vix_date(db, date(2026, 7, 3), csv_text=_INDICES_CSV)
        r2 = await ingest_vix_date(db, date(2026, 7, 3), csv_text=_INDICES_CSV)
        assert r1["status"] == "ok" and r1["inserted"] is True
        assert r2["inserted"] is False
        count = (
            await db.execute(select(func.count()).select_from(IndiaVixDaily))
        ).scalar_one()
        assert count == 1


# ── Instrument mapping (NFO + strike) ────────────────────────────────────────

class TestInstrumentMapping:
    def test_nfo_rows_kept_with_strike(self) -> None:
        raw = [
            {"instrument_token": 123, "exchange_token": 1, "tradingsymbol": "RELIANCE",
             "exchange": "NSE", "instrument_type": "EQ", "name": "RELIANCE"},
            {"instrument_token": 456, "exchange_token": 2,
             "tradingsymbol": "NIFTY26JUL24600CE", "exchange": "NFO",
             "instrument_type": "CE", "name": "NIFTY", "strike": 24600.0,
             "expiry": "2026-07-30", "lot_size": 75},
            {"instrument_token": 789, "exchange_token": 3, "tradingsymbol": "USDINR",
             "exchange": "CDS", "instrument_type": "FUT", "name": "USDINR"},
        ]
        records = map_instrument_rows(raw)
        assert len(records) == 2  # CDS dropped
        nfo = next(r for r in records if r["exchange"] == "NFO")
        assert nfo["strike"] == Decimal("24600.0")
        assert nfo["expiry"] == "2026-07-30"


# ── Chain selection + snapshot recording ─────────────────────────────────────

# Chain selection filters on expiry >= TODAY, so these fixtures must be
# wall-clock-relative — the original hardcoded 2026-07-09 expired overnight
# on 2026-07-10 and flipped "nearest expiry" to the far one (flake found by
# the slice-3.4 gate run; testing.md: freeze or inject time).
NEAR_EXPIRY = date.today() + timedelta(days=20)
FAR_EXPIRY = date.today() + timedelta(days=69)
FUT_EXPIRY = date.today() + timedelta(days=41)


async def _seed_nfo_chain(db: AsyncSession) -> None:
    """NIFTY options at two expiries plus one future."""
    token = 1000
    for expiry in (NEAR_EXPIRY.isoformat(), FAR_EXPIRY.isoformat()):
        for strike in range(24000, 25201, 100):
            for opt in ("CE", "PE"):
                token += 1
                db.add(KiteInstrument(
                    instrument_token=token, exchange_token=token,
                    tradingsymbol=f"NIFTY{expiry}{strike}{opt}",
                    exchange="NFO", instrument_type=opt, name="NIFTY",
                    segment="NFO-OPT", expiry=expiry, strike=Decimal(strike),
                    lot_size=75,
                ))
    db.add(KiteInstrument(
        instrument_token=9999, exchange_token=9999,
        tradingsymbol="NIFTY26JULFUT", exchange="NFO", instrument_type="FUT",
        name="NIFTY", segment="NFO-FUT", expiry=FUT_EXPIRY.isoformat(), lot_size=75,
    ))
    await db.commit()


class TestChainSelection:
    async def test_nearest_expiry_and_strike_window(self, db: AsyncSession) -> None:
        await _seed_nfo_chain(db)
        chain = await select_chain_instruments(
            db, "NIFTY", spot=Decimal("24580"), strikes_each_side=3
        )
        options = [c for c in chain if c.option_type in ("CE", "PE")]
        futs = [c for c in chain if c.option_type == "FU"]

        assert len(futs) == 1
        assert futs[0].expiry_date == FUT_EXPIRY
        # Only the nearest expiry survives
        assert {o.expiry_date for o in options} == {NEAR_EXPIRY}
        # 2N+1 = 7 distinct strikes nearest 24580, both CE and PE
        strikes = sorted({o.strike for o in options})
        assert len(strikes) == 7
        assert Decimal("24600") in strikes and Decimal("24300") in strikes
        assert len(options) == 14  # 7 strikes × CE+PE

    async def test_no_instruments_returns_empty(self, db: AsyncSession) -> None:
        chain = await select_chain_instruments(
            db, "BANKNIFTY", spot=Decimal("52000"), strikes_each_side=5
        )
        assert chain == []


class TestSnapshotRows:
    def test_quote_mapping_and_missing_depth(self) -> None:
        t = datetime(2026, 7, 3, 4, 30, tzinfo=UTC)
        chain = [
            ChainInstrument(1001, "NIFTY", date(2026, 7, 9), Decimal("24600"), "CE"),
            ChainInstrument(1002, "NIFTY", date(2026, 7, 9), Decimal("24600"), "PE"),
        ]
        quotes = {
            "1001": {
                "last_price": 165.35, "volume": 5400000, "oi": 3400000,
                "depth": {"buy": [{"price": 165.2}], "sell": [{"price": 165.5}]},
            },
            "1002": {"last_price": 120.10, "volume": 100, "oi": 50},  # no depth
        }
        rows = quotes_to_rows(t, chain, quotes)
        assert len(rows) == 2
        ce = next(r for r in rows if r["instrument_token"] == 1001)
        assert ce["ltp"] == Decimal("165.35")
        assert ce["bid"] == Decimal("165.2") and ce["ask"] == Decimal("165.5")
        pe = next(r for r in rows if r["instrument_token"] == 1002)
        assert pe["bid"] is None and pe["ask"] is None

    async def test_insert_idempotent(self, db: AsyncSession) -> None:
        t = datetime(2026, 7, 3, 4, 30, tzinfo=UTC)
        rows = [{
            "time": t, "instrument_token": 1001, "symbol": "NIFTY",
            "expiry_date": date(2026, 7, 9), "strike": Decimal("24600"),
            "option_type": "CE", "ltp": Decimal("165.35"), "bid": None,
            "ask": None, "volume": 100, "oi": 200,
        }]
        assert await insert_snapshot_rows(db, rows) == 1
        assert await insert_snapshot_rows(db, rows) == 0
        count = (
            await db.execute(select(func.count()).select_from(OptionChainSnapshot))
        ).scalar_one()
        assert count == 1


class _FakeKite:
    """Duck-typed KiteConnect for the recorder end-to-end path."""

    def __init__(self, spot: float) -> None:
        self._spot = spot

    def ltp(self, keys: list[str]) -> dict[str, Any]:
        return {k: {"last_price": self._spot} for k in keys}

    def quote(self, tokens: list[int]) -> dict[str, Any]:
        return {
            str(t): {"last_price": 100.0 + t % 7, "volume": 10 * t, "oi": 5 * t,
                     "depth": {"buy": [{"price": 99.9}], "sell": [{"price": 100.1}]}}
            for t in tokens
        }


class TestRecorderEndToEnd:
    async def test_records_rows_for_seeded_chain(self, db: AsyncSession) -> None:
        await _seed_nfo_chain(db)
        result = await record_chain_snapshots(
            db, _FakeKite(spot=24580.0), ["NIFTY"], strikes_each_side=3,
            snapshot_time=datetime(2026, 7, 3, 4, 31, tzinfo=UTC),
        )
        assert result["status"] == "ok"
        assert result["inserted"] == 15  # 14 options + 1 future
        assert result["per_underlying"] == {"NIFTY": 15}

    async def test_unknown_underlying_records_nothing(self, db: AsyncSession) -> None:
        result = await record_chain_snapshots(
            db, _FakeKite(spot=52000.0), ["BANKNIFTY"], strikes_each_side=3,
            snapshot_time=datetime(2026, 7, 3, 4, 31, tzinfo=UTC),
        )
        assert result["status"] == "ok"
        assert result["inserted"] == 0


class TestMarketHoursGate:
    def test_boundaries_ist(self) -> None:
        # 9:15 IST == 3:45 UTC (open) · 15:30 IST == 10:00 UTC (close)
        friday_open = datetime(2026, 7, 3, 3, 45, tzinfo=UTC)
        friday_pre = datetime(2026, 7, 3, 3, 44, tzinfo=UTC)
        friday_close = datetime(2026, 7, 3, 10, 0, tzinfo=UTC)
        friday_post = datetime(2026, 7, 3, 10, 1, tzinfo=UTC)
        saturday = datetime(2026, 7, 4, 5, 0, tzinfo=UTC)

        assert _within_market_hours(friday_open) is True
        assert _within_market_hours(friday_pre) is False
        assert _within_market_hours(friday_close) is True
        assert _within_market_hours(friday_post) is False
        assert _within_market_hours(saturday) is False

    def test_spot_key_mapping(self) -> None:
        assert spot_ltp_key("NIFTY") == "NSE:NIFTY 50"
        assert spot_ltp_key("BANKNIFTY") == "NSE:NIFTY BANK"
        assert spot_ltp_key("RELIANCE") == "NSE:RELIANCE"
