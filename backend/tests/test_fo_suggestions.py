"""Tests for the F&O option-selling suggestion engine — Phase 4 slice 4.3
(STRAWMAN). The payoff math is settled and hand-computed here; the DRAFT
orchestration is covered at the gate short-circuits only (the happy-path chain
test lands once the rules are calibrated — see docs/phases/phase-04-fo-suggestions.md).
"""

from datetime import date
from decimal import Decimal

from app.services import fo_suggestions as fs
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers

_EXPIRY = date(2026, 9, 25)


def _leg(action: str, opt: str, strike: str, premium: str) -> fs.OptionLeg:
    return fs.OptionLeg(action=action, option_type=opt, strike=Decimal(strike),
                        premium=Decimal(premium))


# ── Payoff math (hand-computed) ───────────────────────────────────────────────

class TestBullPut:
    def test_economics(self) -> None:
        c = fs.bull_put(
            sell=_leg("sell", "PE", "95", "2.0"), buy=_leg("buy", "PE", "90", "0.8"),
            short_delta=0.18, dte=30, expiry=_EXPIRY,
        )
        assert c is not None
        assert c.structure == "bull_put"
        assert c.net_credit == Decimal("1.2")     # 2.0 − 0.8
        assert c.width == Decimal("5")
        assert c.max_profit == Decimal("1.2")
        assert c.max_loss == Decimal("3.8")       # width − credit
        assert c.breakevens == (Decimal("93.8"),)  # short − credit
        assert abs(c.pop - 0.82) < 1e-9           # 1 − 0.18
        assert c.margin_est == Decimal("3.8")
        assert abs(c.return_on_margin - float(Decimal("1.2") / Decimal("3.8"))) < 1e-12

    def test_rejects_wrong_leg_types(self) -> None:
        # buy strike not below sell strike → not a bull put.
        assert fs.bull_put(
            sell=_leg("sell", "PE", "90", "2.0"), buy=_leg("buy", "PE", "95", "0.8"),
            short_delta=0.2, dte=30, expiry=_EXPIRY,
        ) is None

    def test_rejects_non_credit(self) -> None:
        # sell premium ≤ buy premium → no credit.
        assert fs.bull_put(
            sell=_leg("sell", "PE", "95", "0.5"), buy=_leg("buy", "PE", "90", "0.8"),
            short_delta=0.2, dte=30, expiry=_EXPIRY,
        ) is None


class TestBearCall:
    def test_economics(self) -> None:
        c = fs.bear_call(
            sell=_leg("sell", "CE", "105", "2.0"), buy=_leg("buy", "CE", "110", "0.8"),
            short_delta=0.18, dte=30, expiry=_EXPIRY,
        )
        assert c is not None
        assert c.net_credit == Decimal("1.2") and c.width == Decimal("5")
        assert c.max_loss == Decimal("3.8")
        assert c.breakevens == (Decimal("106.2"),)  # short + credit
        assert abs(c.pop - 0.82) < 1e-9


class TestIronCondor:
    def test_combines_both_wings(self) -> None:
        put = fs.bull_put(
            sell=_leg("sell", "PE", "95", "2.0"), buy=_leg("buy", "PE", "90", "0.8"),
            short_delta=0.18, dte=30, expiry=_EXPIRY,
        )
        call = fs.bear_call(
            sell=_leg("sell", "CE", "105", "2.0"), buy=_leg("buy", "CE", "110", "0.8"),
            short_delta=0.18, dte=30, expiry=_EXPIRY,
        )
        assert put is not None and call is not None
        ic = fs.iron_condor(put=put, call=call, dte=30, expiry=_EXPIRY)
        assert ic is not None
        assert ic.structure == "iron_condor"
        assert len(ic.legs) == 4
        assert ic.net_credit == Decimal("2.4")           # 1.2 + 1.2
        assert ic.max_loss == Decimal("2.6")             # max(5,5) − 2.4
        assert ic.breakevens == (Decimal("92.6"), Decimal("107.4"))
        assert abs(ic.pop - 0.64) < 1e-9                 # 1 − (0.18 + 0.18)


class TestPopAndRank:
    def test_pop_clamped(self) -> None:
        assert fs._pop_from_delta(0.2) == 0.8
        assert fs._pop_from_delta(0.6, 0.6) == 0.0       # clamps at 0, never negative
        assert fs._pop_from_delta(0.0) == 1.0

    def test_rank_orders_by_rom_times_pop(self) -> None:
        a = fs.bull_put(
            sell=_leg("sell", "PE", "95", "2.0"), buy=_leg("buy", "PE", "90", "0.8"),
            short_delta=0.18, dte=30, expiry=_EXPIRY,
        )
        b = fs.bear_call(
            sell=_leg("sell", "CE", "105", "1.2"), buy=_leg("buy", "CE", "110", "0.9"),
            short_delta=0.30, dte=30, expiry=_EXPIRY,
        )
        assert a is not None and b is not None
        ranked = fs.rank_candidates([b, a])
        # a: RoM .316×pop .82 ≈ .259 ; b: RoM (.3/4.7=.0638)×pop .70 ≈ .0447 → a first
        assert ranked[0] is a and ranked[1] is b


def test_strike_step() -> None:
    assert fs._strike_step([Decimal("100"), Decimal("110"), Decimal("120")]) == Decimal("10")
    assert fs._strike_step([Decimal("100")]) is None


# ── Orchestration gate (no chain seeding needed) ──────────────────────────────

class TestSuggestGates:
    async def test_empty_when_no_iv_history(self, db: AsyncSession) -> None:
        # No bhavcopy at all → iv_rank None → conservative gate returns nothing.
        assert await fs.suggest_option_sells(db, "NIFTY") == []

    async def test_api_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/fo/suggestions", params={"symbol": "NIFTY"})
        assert resp.status_code == 401

    async def test_api_empty_is_200(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)
        resp = await client.get(
            "/api/v1/fo/suggestions", params={"symbol": "NIFTY"}, headers=headers
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["symbol"] == "NIFTY" and body["candidates"] == []
