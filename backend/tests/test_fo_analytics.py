"""Tests for F&O analytics — Phase 4 slice 4.1.

Pure analytics (PCR, max pain, ATM, ±N window) are hand-computed; the async
loaders and the /fo API are exercised against real recorded-row fixtures.
Money is asserted as exact Decimals; ratios/percentiles as floats.
"""

import math
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
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


# ── IV rank (round-trips a known vol series through the DB + tradecore) ────────

_BN_EXPIRY = date(2026, 9, 25)
# (trade day, ATM vol) — front-month BANKNIFTY history. current (last) = 0.18;
# min 0.10 / max 0.30 → rank 40; two days below 0.18 → 40th percentile.
_BN_DAYS_VOLS = [
    (date(2026, 8, 3), 0.10),
    (date(2026, 8, 4), 0.22),
    (date(2026, 8, 5), 0.14),
    (date(2026, 8, 6), 0.30),
    (date(2026, 8, 7), 0.18),
]
_RATE = 0.065


async def _seed_iv_history(db: AsyncSession, tc: object) -> None:
    """Seed BANKNIFTY FUT + CE bhavcopy whose ATM call closes are generated by
    tradecore at each day's known vol, so iv_rank must recover that vol."""
    fwd = 50000.0
    for d, vol in _BN_DAYS_VOLS:
        t = (_BN_EXPIRY - d).days / 365.0
        db.add(FoBhavcopy(
            trade_date=d, symbol="BANKNIFTY", instrument="FUT", expiry_date=_BN_EXPIRY,
            strike=Decimal("0"), close=Decimal(str(fwd)), underlying_close=Decimal(str(fwd)),
            open_interest=1000, volume_contracts=100,
        ))
        for k in (49900.0, 50000.0, 50100.0):
            px = tc.option_price("call", [(fwd, k, t, _RATE, 0.0, vol)])[0]  # type: ignore[attr-defined]
            db.add(FoBhavcopy(
                trade_date=d, symbol="BANKNIFTY", instrument="CE", expiry_date=_BN_EXPIRY,
                strike=Decimal(str(k)), close=Decimal(str(round(px, 4))),
                open_interest=500, volume_contracts=50,
            ))
    await db.commit()


class TestIvRank:
    async def test_recovers_seeded_series(self, db: AsyncSession) -> None:
        tc = pytest.importorskip("tradecore")
        await _seed_iv_history(db, tc)
        r = await fa.iv_rank(db, "BANKNIFTY", rate=_RATE)
        assert r is not None
        assert r.sample == 5
        assert r.as_of == date(2026, 8, 7)
        assert abs(r.current_iv - 0.18) < 2e-3
        assert abs(r.min_iv - 0.10) < 2e-3 and abs(r.max_iv - 0.30) < 2e-3
        assert abs(r.rank - 40.0) < 1.0
        assert r.percentile == 40.0            # exactly 2 of 5 below current

    async def test_none_when_no_history(self, db: AsyncSession) -> None:
        assert await fa.iv_rank(db, "BANKNIFTY", rate=_RATE) is None

    async def test_iv_rank_api(self, client: AsyncClient, db: AsyncSession) -> None:
        tc = pytest.importorskip("tradecore")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        await _seed_iv_history(db, tc)
        resp = await client.get(
            "/api/v1/fo/iv-rank", params={"symbol": "banknifty", "rate": _RATE}, headers=headers
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["symbol"] == "BANKNIFTY" and body["sample"] == 5
        assert abs(body["current_iv"] - 0.18) < 2e-3

    async def test_iv_rank_api_404_when_empty(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)
        resp = await client.get("/api/v1/fo/iv-rank", params={"symbol": "NOPE"}, headers=headers)
        assert resp.status_code == 404


# ── Chain pickers: underlyings + open expiries (Phase 5 slice 5.2) ────────────

class TestAvailablePickers:
    async def test_underlyings_from_latest_day_only(self, db: AsyncSession) -> None:
        # BANKNIFTY only traded on the older day — it must not be offered as
        # currently tradeable once a newer day exists.
        db.add(FoBhavcopy(
            trade_date=date(2026, 7, 20), symbol="BANKNIFTY", instrument="CE",
            expiry_date=NIFTY_EXPIRY, strike=Decimal("52000"), close=Decimal("100.00"),
            open_interest=10, volume_contracts=5,
        ))
        await db.commit()
        await _seed_bhav(db, date(2026, 7, 21))
        day, symbols = await fa.available_underlyings(db)
        assert day == date(2026, 7, 21)
        assert symbols == ["NIFTY"]

    async def test_underlyings_empty_when_nothing_recorded(self, db: AsyncSession) -> None:
        assert await fa.available_underlyings(db) == (None, [])

    async def test_expiries_drop_settled_contracts(self, db: AsyncSession) -> None:
        """A settled expiry has no tradeable chain (t <= 0 → no Greeks), so it
        must not be offered."""
        past = date(2026, 7, 16)
        for inst, strike in (("CE", 24600), ("PE", 24600)):
            db.add(FoBhavcopy(
                trade_date=date(2026, 7, 20), symbol="NIFTY", instrument=inst,
                expiry_date=past, strike=Decimal(strike), close=Decimal("10.00"),
                open_interest=10, volume_contracts=5,
            ))
        await _seed_bhav(db, date(2026, 7, 20))     # the 07-30 expiry
        day, expiries = await fa.available_expiries(db, "NIFTY")
        assert day == date(2026, 7, 20)
        assert expiries == [NIFTY_EXPIRY]

    async def test_expiries_sorted_nearest_first(self, db: AsyncSession) -> None:
        far = date(2026, 8, 27)
        for inst in ("CE", "PE"):
            db.add(FoBhavcopy(
                trade_date=date(2026, 7, 20), symbol="NIFTY", instrument=inst,
                expiry_date=far, strike=Decimal("24600"), close=Decimal("300.00"),
                open_interest=10, volume_contracts=5,
            ))
        await _seed_bhav(db, date(2026, 7, 20))
        _day, expiries = await fa.available_expiries(db, "NIFTY")
        assert expiries == [NIFTY_EXPIRY, far]      # nearest first

    async def test_expiries_empty_for_unknown_symbol(self, db: AsyncSession) -> None:
        await _seed_bhav(db, date(2026, 7, 20))
        assert await fa.available_expiries(db, "NOPE") == (None, [])

    async def test_pickers_api(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)
        await _seed_bhav(db, date(2026, 7, 20))

        u = await client.get("/api/v1/fo/underlyings", headers=headers)
        assert u.status_code == 200, u.text
        assert u.json() == {"as_of": "2026-07-20", "symbols": ["NIFTY"]}

        e = await client.get("/api/v1/fo/expiries", params={"symbol": "nifty"}, headers=headers)
        assert e.status_code == 200, e.text
        body = e.json()
        assert body["symbol"] == "NIFTY" and body["as_of"] == "2026-07-20"
        assert body["expiries"] == [{"expiry": "2026-07-30", "dte": 10}]

    async def test_pickers_require_auth(self, client: AsyncClient) -> None:
        assert (await client.get("/api/v1/fo/underlyings")).status_code == 401
        assert (
            await client.get("/api/v1/fo/expiries", params={"symbol": "NIFTY"})
        ).status_code == 401

    async def test_pickers_empty_states(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)
        u = await client.get("/api/v1/fo/underlyings", headers=headers)
        assert u.status_code == 200 and u.json() == {"as_of": None, "symbols": []}
        e = await client.get("/api/v1/fo/expiries", params={"symbol": "NIFTY"}, headers=headers)
        assert e.status_code == 200 and e.json()["expiries"] == []


# ── Per-leg IV + Greeks for the chain ladder (Phase 5 slice 5.2) ──────────────

class TestChainDay:
    """Greeks need the chain's OWN trading day — dating them off `today` would
    misprice every chain loaded on a Monday from Friday's close."""

    async def test_eod_returns_latest_recorded_day(self, db: AsyncSession) -> None:
        await _seed_bhav(db, date(2026, 7, 20))
        await _seed_bhav(db, date(2026, 7, 21))
        assert await fa.chain_day(db, "NIFTY", NIFTY_EXPIRY) == date(2026, 7, 21)

    async def test_eod_respects_as_of(self, db: AsyncSession) -> None:
        await _seed_bhav(db, date(2026, 7, 20))
        await _seed_bhav(db, date(2026, 7, 21))
        day = await fa.chain_day(
            db, "NIFTY", NIFTY_EXPIRY, as_of=datetime(2026, 7, 20, 18, 0, tzinfo=UTC)
        )
        assert day == date(2026, 7, 20)

    async def test_none_when_nothing_recorded(self, db: AsyncSession) -> None:
        assert await fa.chain_day(db, "NIFTY", NIFTY_EXPIRY) is None

    async def test_matches_the_day_load_chain_used(self, db: AsyncSession) -> None:
        # The contract that makes the Greeks honest: same day, same rows.
        await _seed_bhav(db, date(2026, 7, 20))
        await _seed_bhav(db, date(2026, 7, 21))
        day = await fa.chain_day(db, "NIFTY", NIFTY_EXPIRY)
        rows = await fa.load_chain(db, "NIFTY", NIFTY_EXPIRY)
        assert day == date(2026, 7, 21)
        assert len(rows) == 6          # 3 strikes × CE/PE, latest day only

    async def test_intraday_uses_snapshot_date(self, db: AsyncSession) -> None:
        db.add(OptionChainSnapshot(
            time=datetime(2026, 7, 21, 9, 30, tzinfo=UTC), instrument_token=5001,
            symbol="NIFTY", expiry_date=NIFTY_EXPIRY, strike=Decimal("24600"),
            option_type="CE", oi=100, volume=10, ltp=Decimal("150.00"),
        ))
        await db.commit()
        assert await fa.chain_day(db, "NIFTY", NIFTY_EXPIRY, source="intraday") == date(2026, 7, 21)

    async def test_intraday_day_is_the_ist_trading_day_not_the_utc_one(
        self, db: AsyncSession
    ) -> None:
        """Snapshots are stored UTC; the trading day is IST. 19:00 UTC on the
        20th is 00:30 IST on the 21st — taking `.date()` on the UTC instant
        would date the whole ladder a day early and put dte out by one."""
        db.add(OptionChainSnapshot(
            time=datetime(2026, 7, 20, 19, 0, tzinfo=UTC), instrument_token=5002,
            symbol="NIFTY", expiry_date=NIFTY_EXPIRY, strike=Decimal("24600"),
            option_type="CE", oi=100, volume=10, ltp=Decimal("150.00"),
        ))
        await db.commit()
        day = await fa.chain_day(db, "NIFTY", NIFTY_EXPIRY, source="intraday")
        assert day == date(2026, 7, 21)

    async def test_unknown_source_raises(self, db: AsyncSession) -> None:
        with pytest.raises(ValueError, match="unknown chain source"):
            await fa.chain_day(db, "NIFTY", NIFTY_EXPIRY, source="tea-leaves")


class TestForwardForExpiry:
    """Index options are WEEKLY, index futures MONTHLY — on a real NIFTY day
    only 3 of 12 option expiries have a future of their own. Requiring an
    exact-expiry future left every Greek null for the default (nearest) expiry.
    """

    async def test_exact_expiry_future_used_directly(self, db: AsyncSession) -> None:
        day = date(2026, 7, 20)
        await _seed_bhav(db, day)                     # FUT expiring 07-30
        fwd = await fa.forward_for_expiry(db, "NIFTY", NIFTY_EXPIRY, on_day=day)
        assert fwd is not None
        assert fwd.price == Decimal("24620.00")
        assert fwd.source == "fut_exact"
        assert fwd.fut_expiry == NIFTY_EXPIRY
        assert fwd.trade_date == day

    async def test_weekly_expiry_implies_carry_from_the_nearest_future(
        self, db: AsyncSession
    ) -> None:
        day = date(2026, 7, 20)
        weekly = date(2026, 7, 23)                    # 3 days out, NO future
        await _seed_bhav(db, day)                     # monthly FUT 07-30 @24620, spot 24600
        # Weekly option legs so the expiry exists in the chain.
        for inst in ("CE", "PE"):
            db.add(FoBhavcopy(
                trade_date=day, symbol="NIFTY", instrument=inst, expiry_date=weekly,
                strike=Decimal("24600"), close=Decimal("100.00"),
                open_interest=10, volume_contracts=5, underlying_close=Decimal("24600.00"),
            ))
        await db.commit()

        fwd = await fa.forward_for_expiry(db, "NIFTY", weekly, on_day=day)
        assert fwd is not None
        assert fwd.source == "fut_carry_implied"
        assert fwd.fut_expiry == NIFTY_EXPIRY        # the monthly it leaned on
        # carry b = ln(24620/24600)/(10/365); F(3d) = 24600·e^(b·3/365)
        t_fut, t_opt = 10 / 365.0, 3 / 365.0
        b = math.log(24620.0 / 24600.0) / t_fut
        expected = 24600.0 * math.exp(b * t_opt)
        assert abs(float(fwd.price) - expected) < 1e-3
        # Sanity: between spot and the monthly future, and much nearer spot.
        assert Decimal("24600") < fwd.price < Decimal("24620")

    async def test_none_when_no_future_reaches_the_expiry(self, db: AsyncSession) -> None:
        # A LEAP-style expiry beyond the futures curve must not be priced.
        day = date(2026, 7, 20)
        await _seed_bhav(db, day)
        assert await fa.forward_for_expiry(db, "NIFTY", date(2028, 6, 27), on_day=day) is None

    async def test_pinned_to_the_day_so_a_stale_future_cannot_leak_in(
        self, db: AsyncSession
    ) -> None:
        """An INTRADAY chain dated today must not be priced against yesterday's
        futures close — EOD bhavcopy only lands ~18:45 IST, and a stale forward
        skews every IV and delta."""
        await _seed_bhav(db, date(2026, 7, 20))       # yesterday's futures exist
        assert (
            await fa.forward_for_expiry(db, "NIFTY", NIFTY_EXPIRY, on_day=date(2026, 7, 21))
        ) is None

    async def test_zero_or_missing_spot_is_refused(self, db: AsyncSession) -> None:
        day = date(2026, 7, 20)
        weekly = date(2026, 7, 23)
        db.add(FoBhavcopy(
            trade_date=day, symbol="NIFTY", instrument="FUT", expiry_date=NIFTY_EXPIRY,
            strike=Decimal("0"), close=Decimal("24620.00"), underlying_close=None,
            open_interest=1, volume_contracts=1,
        ))
        await db.commit()
        # No spot → no carry → refuse rather than invent a forward.
        assert await fa.forward_for_expiry(db, "NIFTY", weekly, on_day=day) is None


class TestSpotOnDay:
    async def test_spot_from_any_contract_including_option_rows(
        self, db: AsyncSession
    ) -> None:
        # Weekly expiries have no FUT row, so `latest_spot` finds nothing and the
        # ATM strike (and therefore the +/-N window) silently disappears.
        day = date(2026, 7, 20)
        for inst in ("CE", "PE"):
            db.add(FoBhavcopy(
                trade_date=day, symbol="NIFTY", instrument=inst,
                expiry_date=date(2026, 7, 23), strike=Decimal("24600"),
                close=Decimal("100.00"), open_interest=10, volume_contracts=5,
                underlying_close=Decimal("24600.00"),
            ))
        await db.commit()
        assert await fa.latest_spot(db, "NIFTY", date(2026, 7, 23)) is None   # no FUT
        assert await fa.spot_on_day(db, "NIFTY", day) == Decimal("24600.00")

    async def test_none_when_nothing_recorded(self, db: AsyncSession) -> None:
        assert await fa.spot_on_day(db, "NIFTY", date(2026, 7, 20)) is None


class TestPriceChainGreeks:
    def test_prices_every_quoted_leg_with_sane_greek_signs(self) -> None:
        pytest.importorskip("tradecore")
        # ATM-ish chain on a 24600 forward, 30 days out.
        rows = [
            _row("24400", "CE", 100, ltp="320.00"), _row("24400", "PE", 100, ltp="130.00"),
            _row("24600", "CE", 200, ltp="210.00"), _row("24600", "PE", 200, ltp="205.00"),
            _row("24800", "CE", 300, ltp="125.00"), _row("24800", "PE", 300, ltp="325.00"),
        ]
        g = fa.price_chain_greeks(rows, fwd=24600.0, t=30 / 365.0, rate=0.065)
        assert len(g) == 6

        for (_strike, kind), leg in g.items():
            assert 0.01 < leg.iv < 3.0, f"implausible IV for {kind}: {leg.iv}"
            assert leg.gamma > 0            # long gamma either side
            assert leg.vega > 0             # long vega either side
            if kind == "CE":
                assert 0.0 < leg.delta < 1.0
            else:
                assert -1.0 < leg.delta < 0.0    # puts are short delta

        # Moneyness ordering: a call's delta falls as the strike rises.
        ce = {s: v.delta for (s, k), v in g.items() if k == "CE"}
        assert ce[Decimal("24400")] > ce[Decimal("24600")] > ce[Decimal("24800")]

    def test_iv_matches_the_iv_rank_convention(self) -> None:
        """Black-76 on the FUTURE (carry=0) — so a ladder IV is comparable to
        the IV-rank history rather than a second, subtly different number."""
        tc = pytest.importorskip("tradecore")
        fwd, t, rate = 24600.0, 30 / 365.0, 0.065
        target_iv = 0.18
        premium = tc.option_price("CE", [(fwd, 24600.0, t, rate, 0.0, target_iv)])[0]
        g = fa.price_chain_greeks(
            [_row("24600", "CE", 100, ltp=f"{premium:.4f}")], fwd=fwd, t=t, rate=rate
        )
        assert abs(g[(Decimal("24600"), "CE")].iv - target_iv) < 1e-4

    def test_unquoted_and_zero_legs_are_absent_not_zero_filled(self) -> None:
        pytest.importorskip("tradecore")
        rows = [
            _row("24600", "CE", 100, ltp="210.00"),
            _row("24700", "CE", 100),                # no quote at all
            _row("24800", "CE", 100, ltp="0.00"),     # zero quote
        ]
        g = fa.price_chain_greeks(rows, fwd=24600.0, t=30 / 365.0, rate=0.065)
        # A 0.0 delta/IV would read as a real, tradeable value on screen.
        assert set(g) == {(Decimal("24600"), "CE")}

    def test_degenerate_inputs_return_empty(self) -> None:
        rows = [_row("24600", "CE", 100, ltp="210.00")]
        assert fa.price_chain_greeks(rows, fwd=24600.0, t=0.0, rate=0.065) == {}
        assert fa.price_chain_greeks(rows, fwd=24600.0, t=-1.0, rate=0.065) == {}
        assert fa.price_chain_greeks(rows, fwd=0.0, t=0.1, rate=0.065) == {}
        assert fa.price_chain_greeks([], fwd=24600.0, t=0.1, rate=0.065) == {}


class TestChainGreeksApi:
    async def test_greeks_absent_by_default(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)
        await _seed_bhav(db, date(2026, 7, 20))
        resp = await client.get(
            "/api/v1/fo/chain",
            params={"symbol": "nifty", "expiry": NIFTY_EXPIRY.isoformat()},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # `as_of` is always reported — the UI must be able to date the chain
        # even without Greeks, or an EOD chain reads as live.
        assert body["as_of"] == "2026-07-20"
        # ...but nothing pricing-related is resolved unless greeks were asked for.
        assert body["fut_price"] is None
        assert body["forward_source"] is None
        assert body["dte"] is None
        assert all(leg["iv"] is None and leg["delta"] is None for leg in body["legs"])

    async def test_greeks_true_prices_the_ladder(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        pytest.importorskip("tradecore")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        await _seed_bhav(db, date(2026, 7, 20))       # 10 days before expiry
        resp = await client.get(
            "/api/v1/fo/chain",
            params={"symbol": "nifty", "expiry": NIFTY_EXPIRY.isoformat(), "greeks": "true"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # The UI must be able to state exactly what the Greeks were priced off.
        assert body["as_of"] == "2026-07-20"
        assert Decimal(body["fut_price"]) == Decimal("24620.00")
        assert body["forward_source"] == "fut_exact"
        assert body["dte"] == 10

        priced = [leg for leg in body["legs"] if leg["iv"] is not None]
        assert len(priced) == 6
        for leg in priced:
            assert leg["gamma"] > 0 and leg["vega"] > 0
            assert (leg["delta"] > 0) if leg["option_type"] == "CE" else (leg["delta"] < 0)

    async def test_weekly_expiry_still_prices_and_still_windows(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """The regression that mattered: the DEFAULT (nearest) index expiry is a
        weekly with no future of its own. Before the carry-implied forward and
        the spot fallback, this returned every Greek null AND silently dropped
        the +/-N strike window (rendering the whole 200+ leg chain)."""
        pytest.importorskip("tradecore")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        day, weekly = date(2026, 7, 20), date(2026, 7, 23)
        await _seed_bhav(db, day)                      # monthly FUT only
        for strike in (24400, 24500, 24600, 24700, 24800):
            for inst, px in (("CE", "150.00"), ("PE", "120.00")):
                db.add(FoBhavcopy(
                    trade_date=day, symbol="NIFTY", instrument=inst, expiry_date=weekly,
                    strike=Decimal(strike), close=Decimal(px),
                    open_interest=100, volume_contracts=50,
                    underlying_close=Decimal("24600.00"),
                ))
        await db.commit()

        resp = await client.get(
            "/api/v1/fo/chain",
            params={
                "symbol": "nifty", "expiry": weekly.isoformat(),
                "greeks": "true", "strikes": 1,
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["forward_source"] == "fut_carry_implied"
        assert body["fut_price"] is not None and body["dte"] == 3
        # Spot resolved off the option rows, so ATM and the window still work.
        assert Decimal(body["spot"]) == Decimal("24600.00")
        assert Decimal(body["atm_strike"]) == Decimal("24600.00")
        assert len(body["legs"]) == 6                  # +/-1 strike => 3 strikes x CE/PE
        assert all(leg["iv"] is not None for leg in body["legs"])

    async def test_greeks_none_without_a_futures_close(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """No forward → no Black-76 input. Report None, never guess a forward."""
        pytest.importorskip("tradecore")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        await _seed_bhav(db, date(2026, 7, 20), with_fut=False)
        resp = await client.get(
            "/api/v1/fo/chain",
            params={"symbol": "nifty", "expiry": NIFTY_EXPIRY.isoformat(), "greeks": "true"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["fut_price"] is None and body["dte"] is None
        assert all(leg["iv"] is None for leg in body["legs"])
        assert len(body["legs"]) == 6      # the chain itself still renders

    async def test_greeks_none_on_an_expired_chain(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """as_of ON/after expiry → t <= 0; pricing must stand down, not divide."""
        pytest.importorskip("tradecore")
        await create_test_user(db)
        headers = await get_auth_headers(client)
        await _seed_bhav(db, NIFTY_EXPIRY)     # chain dated the expiry day itself
        resp = await client.get(
            "/api/v1/fo/chain",
            params={"symbol": "nifty", "expiry": NIFTY_EXPIRY.isoformat(), "greeks": "true"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["as_of"] == NIFTY_EXPIRY.isoformat()
        assert body["dte"] is None
        assert all(leg["iv"] is None for leg in body["legs"])
