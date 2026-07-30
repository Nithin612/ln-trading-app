"""Tests for F&O analytics — Phase 4 slice 4.1.

Pure analytics (PCR, max pain, ATM, ±N window) are hand-computed; the async
loaders and the /fo API are exercised against real recorded-row fixtures.
Money is asserted as exact Decimals; ratios/percentiles as floats.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

from app.models.fo_data import FoBhavcopy, IndiaVixDaily, OptionChainSnapshot
from app.services import fo_analytics as fa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers

NIFTY_EXPIRY = date(2026, 7, 30)


def _row(strike: str, opt: str, oi: int, volume: int = 0, ltp: str | None = None) -> fa.ChainRow:
    return fa.ChainRow(
        strike=Decimal(strike),
        option_type=opt,
        oi=oi,
        volume=volume,
        ltp=Decimal(ltp) if ltp is not None else None,
    )


# ── Pure analytics ──────────────────────────────────────────────────────────

class TestPutCallRatio:
    def test_pcr_by_oi_and_volume(self) -> None:
        rows = [
            _row("100", "CE", oi=100, volume=50),
            _row("110", "CE", oi=200, volume=50),
            _row("100", "PE", oi=300, volume=100),
            _row("110", "PE", oi=150, volume=100),
        ]
        pcr = fa.put_call_ratio(rows)
        assert pcr.total_ce_oi == 300 and pcr.total_pe_oi == 450
        assert pcr.pcr_oi == 1.5          # 450 / 300
        assert pcr.pcr_volume == 2.0      # 200 / 100

    def test_pcr_none_when_no_call_side(self) -> None:
        pcr = fa.put_call_ratio([_row("100", "PE", oi=300, volume=10)])
        assert pcr.pcr_oi is None and pcr.pcr_volume is None
        assert pcr.total_pe_oi == 300 and pcr.total_ce_oi == 0

    def test_pcr_empty_chain(self) -> None:
        pcr = fa.put_call_ratio([])
        assert pcr.pcr_oi is None and pcr.total_ce_oi == 0 and pcr.total_pe_oi == 0


class TestMaxPain:
    def test_hand_computed_pin(self) -> None:
        # Strikes 100/110/120. Writer payout is minimised at 110 (=200);
        # 100 and 120 both cost 400. See the module docstring for the formula.
        rows = [
            _row("100", "CE", 10), _row("110", "CE", 20), _row("120", "CE", 30),
            _row("100", "PE", 30), _row("110", "PE", 20), _row("120", "PE", 10),
        ]
        assert fa.max_pain(rows) == Decimal("110")

    def test_tie_resolves_to_lower_strike(self) -> None:
        # Symmetric single-strike-each-side book: pain equal at 100 and 110.
        rows = [_row("100", "PE", 10), _row("110", "CE", 10)]
        # E=100: call<100 none; put>100: (110-100)? no PE>100 -> PE at? none. =0
        # E=110: call<110: none (CE at 110); put>110: none. =0  -> tie -> lower 100
        assert fa.max_pain(rows) == Decimal("100")

    def test_empty_chain_returns_none(self) -> None:
        assert fa.max_pain([]) is None


class TestAtmAndWindow:
    def test_atm_nearest_strike(self) -> None:
        rows = [_row("100", "CE", 1), _row("110", "CE", 1), _row("120", "CE", 1)]
        assert fa.atm_strike(rows, Decimal("113")) == Decimal("110")

    def test_atm_tie_resolves_to_lower(self) -> None:
        rows = [_row("110", "CE", 1), _row("120", "CE", 1)]
        assert fa.atm_strike(rows, Decimal("115")) == Decimal("110")

    def test_near_atm_keeps_pm_n_strikes(self) -> None:
        rows = [
            _row(str(k), opt, 1)
            for k in range(100, 141, 10)
            for opt in ("CE", "PE")
        ]  # strikes 100,110,120,130,140
        kept = fa.near_atm(rows, Decimal("120"), n=1)
        strikes = sorted({r.strike for r in kept})
        assert strikes == [Decimal("110"), Decimal("120"), Decimal("130")]
        assert len(kept) == 6  # 3 strikes × CE+PE

    def test_near_atm_n_zero_returns_all(self) -> None:
        rows = [_row("100", "CE", 1), _row("110", "CE", 1)]
        assert len(fa.near_atm(rows, Decimal("105"), n=0)) == 2


# ── Async loaders ─────────────────────────────────────────────────────────────

async def _seed_bhav(db: AsyncSession, trade_date: date, *, with_fut: bool = True) -> None:
    for strike, ce_oi, pe_oi in [(24500, 100, 300), (24600, 200, 200), (24700, 300, 100)]:
        db.add(FoBhavcopy(
            trade_date=trade_date, symbol="NIFTY", instrument="CE",
            expiry_date=NIFTY_EXPIRY, strike=Decimal(strike),
            close=Decimal("150.00"), open_interest=ce_oi, volume_contracts=ce_oi * 2,
        ))
        db.add(FoBhavcopy(
            trade_date=trade_date, symbol="NIFTY", instrument="PE",
            expiry_date=NIFTY_EXPIRY, strike=Decimal(strike),
            close=Decimal("120.00"), open_interest=pe_oi, volume_contracts=pe_oi * 2,
        ))
    if with_fut:
        db.add(FoBhavcopy(
            trade_date=trade_date, symbol="NIFTY", instrument="FUT",
            expiry_date=NIFTY_EXPIRY, strike=Decimal("0"),
            close=Decimal("24620.00"), underlying_close=Decimal("24600.00"),
            open_interest=14200000, volume_contracts=250000,
        ))
    await db.commit()


class TestLoadChainEod:
    async def test_returns_latest_day_ce_pe_only(self, db: AsyncSession) -> None:
        await _seed_bhav(db, date(2026, 7, 20))
        await _seed_bhav(db, date(2026, 7, 21))  # newer day, different not needed
        rows = await fa.load_chain(db, "NIFTY", NIFTY_EXPIRY, source="eod")
        assert len(rows) == 6                       # 3 strikes × CE/PE, FUT excluded
        assert {r.option_type for r in rows} == {"CE", "PE"}
        pcr = fa.put_call_ratio(rows)
        assert pcr.total_ce_oi == 600 and pcr.total_pe_oi == 600

    async def test_empty_when_nothing_recorded(self, db: AsyncSession) -> None:
        assert await fa.load_chain(db, "NIFTY", NIFTY_EXPIRY, source="eod") == []


class TestLoadChainIntraday:
    async def test_returns_latest_snapshot(self, db: AsyncSession) -> None:
        t_old = datetime(2026, 7, 21, 4, 30, tzinfo=UTC)
        t_new = datetime(2026, 7, 21, 5, 30, tzinfo=UTC)
        tok = 5000
        for t, oi in ((t_old, 111), (t_new, 222)):
            for opt in ("CE", "PE"):
                tok += 1
                db.add(OptionChainSnapshot(
                    time=t, instrument_token=tok, symbol="NIFTY",
                    expiry_date=NIFTY_EXPIRY, strike=Decimal("24600"),
                    option_type=opt, ltp=Decimal("100.0"), oi=oi, volume=10,
                ))
        await db.commit()
        rows = await fa.load_chain(db, "NIFTY", NIFTY_EXPIRY, source="intraday")
        assert len(rows) == 2 and all(r.oi == 222 for r in rows)  # only the newest snapshot


class TestSpotAndBasis:
    async def test_latest_spot(self, db: AsyncSession) -> None:
        await _seed_bhav(db, date(2026, 7, 21))
        assert await fa.latest_spot(db, "NIFTY", NIFTY_EXPIRY) == Decimal("24600.00")

    async def test_futures_basis(self, db: AsyncSession) -> None:
        await _seed_bhav(db, date(2026, 7, 21))
        b = await fa.futures_basis(db, "NIFTY", NIFTY_EXPIRY)
        assert b is not None
        assert b.basis == Decimal("20.00")           # 24620 − 24600
        assert round(b.basis_pct, 6) == round(20 / 24600 * 100, 6)

    async def test_basis_none_without_fut(self, db: AsyncSession) -> None:
        await _seed_bhav(db, date(2026, 7, 21), with_fut=False)
        assert await fa.futures_basis(db, "NIFTY", NIFTY_EXPIRY) is None


class TestVixRegime:
    async def test_percentile_and_band(self, db: AsyncSession) -> None:
        # 5 sessions; current (latest date) is the max → 4 of 5 below → 80th pct.
        for d, close in [
            (date(2026, 6, 1), "10.00"),
            (date(2026, 6, 2), "12.00"),
            (date(2026, 6, 3), "14.00"),
            (date(2026, 6, 4), "11.00"),
            (date(2026, 6, 5), "20.00"),  # latest = current
        ]:
            db.add(IndiaVixDaily(trade_date=d, close=Decimal(close)))
        await db.commit()
        r = await fa.vix_regime(db)
        assert r is not None
        assert r.current == Decimal("20.00")
        assert r.percentile == 80.0
        assert r.band == "high"
        assert r.sample == 5

    async def test_none_when_no_vix(self, db: AsyncSession) -> None:
        assert await fa.vix_regime(db) is None


# ── API ─────────────────────────────────────────────────────────────────────

class TestFoApi:
    async def test_chain_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/v1/fo/chain", params={"symbol": "NIFTY", "expiry": NIFTY_EXPIRY.isoformat()}
        )
        assert resp.status_code == 401

    async def test_chain_returns_legs(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)
        await _seed_bhav(db, date(2026, 7, 21))
        resp = await client.get(
            "/api/v1/fo/chain",
            params={"symbol": "nifty", "expiry": NIFTY_EXPIRY.isoformat()},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["symbol"] == "NIFTY"                 # upcased
        assert body["spot"] == "24600.0000"
        assert body["atm_strike"] == "24600.00"
        assert len(body["legs"]) == 6

    async def test_analytics_computed(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)
        await _seed_bhav(db, date(2026, 7, 21))
        resp = await client.get(
            "/api/v1/fo/analytics",
            params={"symbol": "NIFTY", "expiry": NIFTY_EXPIRY.isoformat()},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["pcr"]["pcr_oi"] == 1.0             # 600 / 600
        assert body["max_pain"] == "24600.00"           # symmetric OI pins at ATM
        assert body["basis"]["basis"] == "20.0000"
        assert body["vix"] is None                       # no VIX seeded

    async def test_vix_regime_404_when_empty(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)
        resp = await client.get("/api/v1/fo/vix-regime", headers=headers)
        assert resp.status_code == 404

    async def test_vix_regime_ok_when_seeded(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)
        db.add(IndiaVixDaily(trade_date=date(2026, 6, 5), close=Decimal("13.75")))
        await db.commit()
        resp = await client.get("/api/v1/fo/vix-regime", headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["current"] == "13.7500"
