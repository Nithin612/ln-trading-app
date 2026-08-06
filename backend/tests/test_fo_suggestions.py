"""Tests for the F&O option-selling suggestion engine — Phase 4 slice 4.3.

Pure payoff/probability/expectancy math is hand-computed; the orchestration is
exercised end-to-end on a seeded INDEX chain (IV history + full chain) so the
gate → price → build → rank pipeline is covered, not just the units.
"""

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest
from app.models.fo_data import FoBhavcopy, IndiaVixDaily
from app.services import fo_suggestions as fs
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, get_auth_headers

_EXPIRY = date(2026, 9, 25)


def _leg(action: str, opt: str, strike: str, premium: str) -> fs.OptionLeg:
    return fs.OptionLeg(action=action, option_type=opt, strike=Decimal(strike),
                        premium=Decimal(premium))


# ── Payoff / expectancy / exit math (hand-computed) ───────────────────────────

class TestBullPut:
    def test_economics(self) -> None:
        c = fs.bull_put(
            sell=_leg("sell", "PE", "95", "2.0"), buy=_leg("buy", "PE", "90", "0.8"),
            short_delta=0.18, dte=30, expiry=_EXPIRY,
        )
        assert c is not None
        assert c.structure == "bull_put"
        assert c.net_credit == Decimal("1.2") and c.width == Decimal("5")
        assert c.max_loss == Decimal("3.8")            # width − credit
        assert c.breakevens == (Decimal("93.8"),)      # short − credit
        assert abs(c.pop - 0.82) < 1e-9                # delta proxy default
        assert abs(float(c.expectancy) - (0.82 * 1.2 - 0.18 * 3.8)) < 1e-9
        assert c.exit_plan.take_profit_credit == Decimal("0.60")     # 50% of credit
        assert c.exit_plan.stop_loss_amount == Decimal("2.4")        # min(2×credit, max_loss)
        assert c.exit_plan.time_stop_dte == 21

    def test_pop_override_used(self) -> None:
        c = fs.bull_put(
            sell=_leg("sell", "PE", "95", "2.0"), buy=_leg("buy", "PE", "90", "0.8"),
            short_delta=0.18, dte=30, expiry=_EXPIRY, pop_override=0.70,
        )
        assert c is not None and abs(c.pop - 0.70) < 1e-9

    def test_rejects_non_credit_and_wrong_legs(self) -> None:
        assert fs.bull_put(  # buy strike above sell → not a bull put
            sell=_leg("sell", "PE", "90", "2.0"), buy=_leg("buy", "PE", "95", "0.8"),
            short_delta=0.2, dte=30, expiry=_EXPIRY,
        ) is None
        assert fs.bull_put(  # no credit
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
        assert c.net_credit == Decimal("1.2") and c.max_loss == Decimal("3.8")
        assert c.breakevens == (Decimal("106.2"),)     # short + credit


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
        assert ic.structure == "iron_condor" and len(ic.legs) == 4
        assert ic.net_credit == Decimal("2.4")          # 1.2 + 1.2
        assert ic.max_loss == Decimal("2.6")            # max(5,5) − 2.4
        assert ic.breakevens == (Decimal("92.6"), Decimal("107.4"))


# ── Breakeven-exact POP (Black-76) ────────────────────────────────────────────

class TestBreakevenPop:
    def test_prob_above_atm_is_near_half(self) -> None:
        p = fs._prob_above(100.0, 100.0, 0.20, 0.25)
        assert 0.47 < p < 0.50

    def test_prob_above_monotone_in_strike(self) -> None:
        assert fs._prob_above(100.0, 95.0, 0.2, 0.25) > fs._prob_above(100.0, 110.0, 0.2, 0.25)

    def test_structure_directions(self) -> None:
        bp = fs.breakeven_pop("bull_put", fwd=100.0, breakevens=(Decimal("90"),), iv=0.2, t=0.25)
        bc = fs.breakeven_pop("bear_call", fwd=100.0, breakevens=(Decimal("110"),), iv=0.2, t=0.25)
        ic = fs.breakeven_pop(
            "iron_condor", fwd=100.0, breakevens=(Decimal("90"), Decimal("110")), iv=0.2, t=0.25
        )
        assert bp is not None and bp > 0.8
        assert bc is not None and bc > 0.8
        assert ic is not None and 0.0 <= ic <= 1.0 and ic < min(bp, bc)

    def test_degenerate_returns_none(self) -> None:
        be = (Decimal("90"),)
        assert fs.breakeven_pop("bull_put", fwd=0.0, breakevens=be, iv=0.2, t=0.25) is None    # fwd
        assert fs.breakeven_pop("bull_put", fwd=100.0, breakevens=be, iv=0.0, t=0.25) is None  # iv


# ── Gates / ranking ───────────────────────────────────────────────────────────

def _bull(credit: str, delta: float) -> fs.SpreadCandidate:
    c = fs.bull_put(
        sell=_leg("sell", "PE", "95", credit), buy=_leg("buy", "PE", "90", "0.0"),
        short_delta=delta, dte=30, expiry=_EXPIRY,
    )
    assert c is not None
    return c


class TestGatesAndRank:
    def test_reward_floor_rejects_thin_credit(self) -> None:
        thin = _bull("1.0", 0.10)                       # 1.0/5 = 0.20 < 0.30 floor
        assert not fs.passes_gates(thin, fs.DEFAULT_SELL_RULES)

    def test_expectancy_reported_correctly(self) -> None:
        c = fs.bull_put(
            sell=_leg("sell", "PE", "95", "2.0"), buy=_leg("buy", "PE", "90", "0.0"),
            short_delta=0.10, dte=30, expiry=_EXPIRY, pop_override=0.70,
        )
        assert c is not None
        # credit 2, width 5, max_loss 3 → 0.70·2 − 0.30·3 = 0.5
        assert abs(float(c.expectancy) - 0.5) < 1e-9

    def test_expectancy_is_not_a_gate(self) -> None:
        # A risk-neutral-negative-expectancy spread still passes when reward +
        # POP clear — the edge is the vol risk premium (IV-rank), not a positive
        # risk-neutral expectancy (which is ~0 by construction).
        c = fs.bull_put(
            sell=_leg("sell", "PE", "95", "1.5"), buy=_leg("buy", "PE", "90", "0.0"),
            short_delta=0.10, dte=30, expiry=_EXPIRY, pop_override=0.65,
        )
        assert c is not None
        assert c.expectancy < 0                          # 0.65·1.5 − 0.35·3.5 = −0.25
        assert fs.passes_gates(c, fs.DEFAULT_SELL_RULES)  # reward 0.30 + POP 0.65 clear

    def test_pop_floor(self) -> None:
        low = replace(_bull("2.0", 0.10), pop=0.50)     # < 0.65 floor
        assert not fs.passes_gates(low, fs.DEFAULT_SELL_RULES)

    def test_passes_when_all_clear(self) -> None:
        ok = replace(_bull("2.0", 0.10), pop=0.80)      # 2/5=0.40 floor ok, pop ok, exp>0
        assert fs.passes_gates(ok, fs.DEFAULT_SELL_RULES)

    def test_rank_orders_by_rom_times_pop(self) -> None:
        a = replace(_bull("2.0", 0.10), pop=0.82)
        b = replace(_bull("1.0", 0.10), pop=0.70)
        assert fs.rank_candidates([b, a])[0] is a


def test_strike_step() -> None:
    assert fs._strike_step([Decimal("100"), Decimal("110"), Decimal("120")]) == Decimal("10")
    assert fs._strike_step([Decimal("100")]) is None


# ── Orchestration gates (cheap, no chain) ─────────────────────────────────────

class TestSuggestGates:
    async def test_non_index_universe_rejected(self, db: AsyncSession) -> None:
        assert await fs.suggest_option_sells(db, "RELIANCE") == []    # not cash-settled index

    async def test_empty_when_no_iv_history(self, db: AsyncSession) -> None:
        assert await fs.suggest_option_sells(db, "NIFTY") == []        # index, but no data

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
        assert resp.json() == {"symbol": "NIFTY", "candidates": []}


# ── Real-chain happy path (seed IV history + full chain, run the pipeline) ─────

_LAST = date(2026, 8, 3)
_SUG_EXPIRY = date(2026, 9, 7)    # 35 DTE from _LAST — inside the 20–45 window
_FWD = 50000.0
_RATE = 0.065


# A calm VIX series (last = min → "low" band) so the fail-closed veto lets the
# happy path through; other cases pass their own series (or [] for no data).
_CALM_VIX = [(date(2026, 7, 30), "20"), (date(2026, 7, 31), "19"),
             (date(2026, 8, 1), "18"), (date(2026, 8, 3), "14")]


async def _seed_index_chain(
    db: AsyncSession, tc: object, *, vix: list[tuple[date, str]] | None = None
) -> None:
    """7-session ascending-IV history (ATM CE) so IV-rank is high, plus the full
    CE/PE chain on the last day priced at a rich IV — all cash-settled index.
    `vix` seeds India-VIX for the regime gate (default calm; [] = none)."""
    hist = [(date(2026, 7, 27), 0.15), (date(2026, 7, 28), 0.16), (date(2026, 7, 29), 0.17),
            (date(2026, 7, 30), 0.18), (date(2026, 7, 31), 0.19), (date(2026, 8, 1), 0.20),
            (date(2026, 8, 2), 0.21)]
    for d, iv in hist:
        t = (_SUG_EXPIRY - d).days / 365.0
        px = tc.option_price("call", [(_FWD, _FWD, t, _RATE, 0.0, iv)])[0]  # type: ignore[attr-defined]
        db.add(FoBhavcopy(trade_date=d, symbol="BANKNIFTY", instrument="FUT",
                          expiry_date=_SUG_EXPIRY, strike=Decimal("0"), close=Decimal(str(_FWD)),
                          underlying_close=Decimal(str(_FWD)), open_interest=1000))
        db.add(FoBhavcopy(trade_date=d, symbol="BANKNIFTY", instrument="CE",
                          expiry_date=_SUG_EXPIRY, strike=Decimal(str(int(_FWD))),
                          close=Decimal(str(round(px, 2))), open_interest=1000))

    t = (_SUG_EXPIRY - _LAST).days / 365.0
    strikes = [float(k) for k in range(44000, 56001, 100)]
    calls = tc.option_price("call", [(_FWD, k, t, _RATE, 0.0, 0.30) for k in strikes])  # type: ignore[attr-defined]
    puts = tc.option_price("put", [(_FWD, k, t, _RATE, 0.0, 0.30) for k in strikes])  # type: ignore[attr-defined]
    db.add(FoBhavcopy(trade_date=_LAST, symbol="BANKNIFTY", instrument="FUT",
                      expiry_date=_SUG_EXPIRY, strike=Decimal("0"), close=Decimal(str(_FWD)),
                      underlying_close=Decimal(str(_FWD)), open_interest=1000))
    for k, cp, pp in zip(strikes, calls, puts, strict=True):
        db.add(FoBhavcopy(trade_date=_LAST, symbol="BANKNIFTY", instrument="CE",
                          expiry_date=_SUG_EXPIRY, strike=Decimal(str(int(k))),
                          close=Decimal(str(round(cp, 2))), open_interest=1000))
        db.add(FoBhavcopy(trade_date=_LAST, symbol="BANKNIFTY", instrument="PE",
                          expiry_date=_SUG_EXPIRY, strike=Decimal(str(int(k))),
                          close=Decimal(str(round(pp, 2))), open_interest=1000))
    for d, v in (_CALM_VIX if vix is None else vix):
        db.add(IndiaVixDaily(trade_date=d, close=Decimal(v)))
    await db.commit()


class TestSuggestHappyPath:
    async def test_pipeline_returns_gated_candidates(self, db: AsyncSession) -> None:
        tc = pytest.importorskip("tradecore")
        await _seed_index_chain(db, tc)
        # NOTE: the DEFAULT 0.16Δ + 0.30 reward-floor combo is intentionally very
        # selective (far-OTM 1-strike spreads rarely clear a 30% credit/width) —
        # a safe "often no trade" stance. To exercise the pipeline we sell nearer
        # (~0.30Δ) with an achievable floor; the strict gates are unit-tested above.
        rules = replace(
            fs.DEFAULT_SELL_RULES, short_delta_target=0.30, short_delta_band=0.15,
            min_credit_to_width=0.10, min_pop=0.50,
        )
        cands = await fs.suggest_option_sells(db, "BANKNIFTY", rate=_RATE, as_of=_LAST, rules=rules)
        assert cands, "expected at least one candidate on a rich-IV index chain"
        assert {c.structure for c in cands} <= {"bull_put", "bear_call", "iron_condor"}
        for c in cands:
            assert c.max_loss > 0 and c.net_credit > 0 and c.breakevens
            assert fs.passes_gates(c, rules)                            # gates actually applied
            assert c.exit_plan.time_stop_dte == 21
            assert all(leg.premium > 0 for leg in c.legs)

    async def test_high_vix_vetoes(self, db: AsyncSession) -> None:
        tc = pytest.importorskip("tradecore")
        # Risk-off regime: last VIX is the max of its window → band "high" → hard veto.
        hi = [(date(2026, 7, 29), "10"), (date(2026, 7, 30), "11"), (date(2026, 7, 31), "12"),
              (date(2026, 8, 1), "13"), (_LAST, "40")]
        await _seed_index_chain(db, tc, vix=hi)
        assert await fs.suggest_option_sells(db, "BANKNIFTY", rate=_RATE, as_of=_LAST) == []

    async def test_no_vix_data_fails_closed(self, db: AsyncSession) -> None:
        # Regime unknown (no VIX) → the safety veto must fail CLOSED, not proceed.
        tc = pytest.importorskip("tradecore")
        await _seed_index_chain(db, tc, vix=[])
        assert await fs.suggest_option_sells(db, "BANKNIFTY", rate=_RATE, as_of=_LAST) == []
