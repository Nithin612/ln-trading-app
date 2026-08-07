"""Tests for the F&O option-selling suggestion engine — Phase 4 slice 4.3.

Pure payoff/probability/expectancy math is hand-computed; the orchestration is
exercised end-to-end on a seeded INDEX chain (IV history + full chain) so the
gate → price → build → rank pipeline is covered, not just the units.
"""

import math
from dataclasses import replace
from datetime import UTC, date, datetime
from datetime import time as dtime
from decimal import Decimal

import pytest
from app.models.fo_data import FoBhavcopy, IndiaVixDaily
from app.services import fo_analytics as fa
from app.services import fo_suggestions as fs
from httpx import AsyncClient
from sqlalchemy import select
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




# ── Expiry selection: walk the window, don't dead-end on its first entry ──────
#
# Index options expire WEEKLY; index futures only MONTHLY. `_pick_expiry` took
# the first in-window expiry unconditionally and `suggest_option_sells` priced
# it with `futures_basis`, which needs an EXACT expiry match — so a weekly
# sitting in FRONT of an in-window monthly killed the whole run, returning `[]`,
# INDISTINGUISHABLE from "no candidate cleared the gates". On the real NIFTY
# calendar that dead-end cost 26 of the 33 trading days between 2026-08-06 and
# 10-02 that should have produced candidates.
#
# The v1 ruling (phase-04 §7.6) is monthly-only, and index futures are monthly,
# so `require_exact_expiry_future` (default True) IS the monthly test. The walk
# is what fixes the bug; the flag is what keeps the calibration honest.

_WEEKLY = date(2026, 8, 25)       # 22 DTE from _LAST — in window, NO future
_MONTHLY = date(2026, 9, 28)      # 56 DTE — owns the only FUT row
_SPOT = 50000.0
_FUT_PX = 50250.0                 # +0.5% over 56d → a real, NON-ZERO carry


async def _seed_weekly_ahead_of_monthly(
    db: AsyncSession, tc: object, *, fut_close: str | None = str(_FUT_PX)
) -> None:
    """The real NSE topology: a tradeable WEEKLY chain sitting in front of a
    MONTHLY that owns the only futures row. Both expiries carry a full chain, so
    either could be selected — which one gets picked is the behaviour on test.
    `fut_close=None` seeds a settlement-less future (the data-quality case).

    The carry is deliberately non-zero (`underlying_close` 50000 vs FUT 50250):
    with a zero-carry fixture the exact-expiry and carry-implied branches return
    the SAME number, and a calibration guard asserting only equality would pass
    even with the exact-expiry short-circuit deleted.
    """
    # IV history for `iv_rank`: the ATM front-month call, one row per prior day.
    # The strike MUST sit on the same 100-point grid as the chain below — an
    # off-grid row (e.g. 50250) makes `_strike_step` collapse to 50 and no
    # 1-strike-wide spread can be built at all. `_LAST` is deliberately absent
    # here: its ATM call comes from the full chain, so adding one would collide
    # on the primary key.
    hist_strike = 50300              # on-grid, nearest the 50250 future
    hist = [(date(2026, 7, 27), 0.15), (date(2026, 7, 28), 0.16), (date(2026, 7, 29), 0.17),
            (date(2026, 7, 30), 0.18), (date(2026, 7, 31), 0.19), (date(2026, 8, 1), 0.20),
            (date(2026, 8, 2), 0.21)]
    for d, iv in hist:
        t_fut = (_MONTHLY - d).days / 365.0
        px = tc.option_price("call", [(_FUT_PX, float(hist_strike), t_fut, _RATE, 0.0, iv)])[0]  # type: ignore[attr-defined]
        db.add(FoBhavcopy(
            trade_date=d, symbol="BANKNIFTY", instrument="FUT", expiry_date=_MONTHLY,
            strike=Decimal("0"),
            close=None if fut_close is None else Decimal(fut_close),
            underlying_close=Decimal(str(_SPOT)), open_interest=1000,
        ))
        db.add(FoBhavcopy(trade_date=d, symbol="BANKNIFTY", instrument="CE",
                          expiry_date=_MONTHLY, strike=Decimal(str(hist_strike)),
                          close=Decimal(str(round(px, 2))), open_interest=1000))
    # `_LAST`'s own futures row (the history loop no longer covers it).
    db.add(FoBhavcopy(
        trade_date=_LAST, symbol="BANKNIFTY", instrument="FUT", expiry_date=_MONTHLY,
        strike=Decimal("0"),
        close=None if fut_close is None else Decimal(fut_close),
        underlying_close=Decimal(str(_SPOT)), open_interest=1000,
    ))

    carry = math.log(_FUT_PX / _SPOT) / ((_MONTHLY - _LAST).days / 365.0)
    strikes = [float(k) for k in range(44000, 56001, 100)]
    for e in (_WEEKLY, _MONTHLY):
        t = (e - _LAST).days / 365.0
        f = _FUT_PX if e == _MONTHLY else _SPOT * math.exp(carry * t)
        calls = tc.option_price("call", [(f, k, t, _RATE, 0.0, 0.30) for k in strikes])  # type: ignore[attr-defined]
        puts = tc.option_price("put", [(f, k, t, _RATE, 0.0, 0.30) for k in strikes])  # type: ignore[attr-defined]
        for k, cp, pp in zip(strikes, calls, puts, strict=True):
            db.add(FoBhavcopy(trade_date=_LAST, symbol="BANKNIFTY", instrument="CE",
                              expiry_date=e, strike=Decimal(str(int(k))),
                              close=Decimal(str(round(cp, 2))), open_interest=1000))
            db.add(FoBhavcopy(trade_date=_LAST, symbol="BANKNIFTY", instrument="PE",
                              expiry_date=e, strike=Decimal(str(int(k))),
                              close=Decimal(str(round(pp, 2))), open_interest=1000))
    for d, v in _CALM_VIX:
        db.add(IndiaVixDaily(trade_date=d, close=Decimal(v)))
    await db.commit()


# A DTE window wide enough to hold BOTH the weekly (22) and the monthly (56).
_BOTH_IN_WINDOW = replace(fs.DEFAULT_SELL_RULES, dte_min=20, dte_max=60)
_LOOSE = replace(
    _BOTH_IN_WINDOW, short_delta_target=0.30, short_delta_band=0.15,
    min_credit_to_width=0.10, min_pop=0.50,
)


def _shape(cands: list[fs.SpreadCandidate]) -> list[tuple[str, tuple[Decimal, ...], Decimal]]:
    """Identity of a candidate set — structure, strikes, credit."""
    return sorted(
        (c.structure, tuple(leg.strike for leg in c.legs), c.net_credit) for c in cands
    )


class TestExpiryWalk:
    async def test_canary_old_path_cannot_price_the_weekly(self, db: AsyncSession) -> None:
        """The topology really is the broken one: `futures_basis` — what the
        engine used to price with — finds nothing for the leading weekly."""
        tc = pytest.importorskip("tradecore")
        await _seed_weekly_ahead_of_monthly(db, tc)
        assert await fa.futures_basis(db, "BANKNIFTY", _WEEKLY) is None
        assert await fa.futures_basis(db, "BANKNIFTY", _MONTHLY) is not None

    async def test_walks_past_the_weekly_to_the_monthly(self, db: AsyncSession) -> None:
        """THE REGRESSION. Old code stopped at the weekly, could not price it and
        returned [] even though an in-window monthly sat right behind it."""
        tc = pytest.importorskip("tradecore")
        await _seed_weekly_ahead_of_monthly(db, tc)
        picked = await fs._pick_expiry(db, "BANKNIFTY", as_of=_LAST, rules=_BOTH_IN_WINDOW)
        assert picked is not None
        day, expiry, fwd = picked
        assert (day, expiry) == (_LAST, _MONTHLY), "must skip the weekly, not stop on it"
        assert fwd.source == "fut_exact"

    async def test_produces_candidates_where_it_used_to_return_empty(
        self, db: AsyncSession
    ) -> None:
        tc = pytest.importorskip("tradecore")
        await _seed_weekly_ahead_of_monthly(db, tc)
        cands = await fs.suggest_option_sells(
            db, "BANKNIFTY", rate=_RATE, as_of=_LAST, rules=_LOOSE
        )
        assert cands, "an in-window monthly behind a weekly must still produce"
        assert {c.expiry for c in cands} == {_MONTHLY}
        for c in cands:
            assert c.max_loss > 0 and c.net_credit > 0 and c.breakevens
            assert fs.passes_gates(c, _LOOSE)

    async def test_weeklies_excluded_by_default(self, db: AsyncSession) -> None:
        """phase-04 §7.6 — "weeklies excluded in v1". With ONLY the weekly in
        window there is no eligible expiry: an honest no-trade, not a weekly."""
        tc = pytest.importorskip("tradecore")
        await _seed_weekly_ahead_of_monthly(db, tc)
        assert fs.DEFAULT_SELL_RULES.require_exact_expiry_future is True
        weekly_only = replace(fs.DEFAULT_SELL_RULES, dte_min=20, dte_max=30)  # 22 in, 56 out
        assert await fs._pick_expiry(db, "BANKNIFTY", as_of=_LAST, rules=weekly_only) is None
        loose_weekly_only = replace(
            weekly_only, short_delta_target=0.30, short_delta_band=0.15,
            min_credit_to_width=0.10, min_pop=0.50,
        )
        assert await fs.suggest_option_sells(
            db, "BANKNIFTY", rate=_RATE, as_of=_LAST, rules=loose_weekly_only
        ) == []

    async def test_weeklies_selectable_only_when_the_flag_is_flipped(
        self, db: AsyncSession
    ) -> None:
        """The escape hatch is a deliberate, named knob — not an emergent
        property of which expiry happens to own a futures row."""
        tc = pytest.importorskip("tradecore")
        await _seed_weekly_ahead_of_monthly(db, tc)
        allow = replace(_BOTH_IN_WINDOW, require_exact_expiry_future=False)
        picked = await fs._pick_expiry(db, "BANKNIFTY", as_of=_LAST, rules=allow)
        assert picked is not None
        _, expiry, fwd = picked
        assert expiry == _WEEKLY                       # now the nearest wins
        assert fwd.source == "fut_carry_implied"
        # Log-space interpolation between (0, spot) and (T_fut, F_fut) — never
        # extrapolation — so the forward is strictly inside those bounds.
        # Hand-check: b = ln(50250/50000)/(56/365) = 0.032508,
        # F = 50000·e^(0.032508·22/365) = 50098.0656.
        assert _SPOT < float(fwd.price) < _FUT_PX
        assert float(fwd.price) == pytest.approx(50098.07, abs=0.05)

    async def test_carry_implied_forward_is_disclosed_in_the_rationale(
        self, db: AsyncSession
    ) -> None:
        """A carry-implied forward carries a measured, CONSISTENTLY positive
        ~0.12% bias worth ~1.1pp of POP — enough to cross the hard `min_pop`
        gate. It must never read as though it came from a traded future."""
        tc = pytest.importorskip("tradecore")
        await _seed_weekly_ahead_of_monthly(db, tc)
        allow = replace(_LOOSE, require_exact_expiry_future=False)
        cands = await fs.suggest_option_sells(
            db, "BANKNIFTY", rate=_RATE, as_of=_LAST, rules=allow
        )
        assert cands and {c.expiry for c in cands} == {_WEEKLY}
        assert all("fut_carry_implied" in c.rationale for c in cands)
        exact = await fs.suggest_option_sells(
            db, "BANKNIFTY", rate=_RATE, as_of=_LAST, rules=_LOOSE
        )
        assert exact and all("carry" not in c.rationale for c in exact)

    async def test_unpriced_nearest_future_falls_through_to_a_priced_one(
        self, db: AsyncSession
    ) -> None:
        """One settlement-less recorder row must not kill the forward for the
        whole front chain when a priced future sits an expiry further out."""
        tc = pytest.importorskip("tradecore")
        await _seed_weekly_ahead_of_monthly(db, tc)
        far = date(2026, 12, 28)
        db.add(FoBhavcopy(trade_date=_LAST, symbol="BANKNIFTY", instrument="FUT",
                          expiry_date=far, strike=Decimal("0"), close=Decimal("51000.0"),
                          underlying_close=Decimal(str(_SPOT)), open_interest=1000))
        row = (await db.execute(
            select(FoBhavcopy).where(
                FoBhavcopy.trade_date == _LAST, FoBhavcopy.symbol == "BANKNIFTY",
                FoBhavcopy.instrument == "FUT", FoBhavcopy.expiry_date == _MONTHLY,
            )
        )).scalars().first()
        assert row is not None
        row.close = None                      # blank the nearest future's settlement
        await db.commit()
        fwd = await fa.forward_for_expiry(db, "BANKNIFTY", _MONTHLY, on_day=_LAST)
        assert fwd is not None, "should fall through to the priced December future"
        assert fwd.source == "fut_carry_implied" and fwd.fut_expiry == far

    async def test_no_usable_future_at_all_returns_none(self, db: AsyncSession) -> None:
        """No priced future anywhere → no forward, never a guessed one."""
        tc = pytest.importorskip("tradecore")
        await _seed_weekly_ahead_of_monthly(db, tc, fut_close=None)
        assert await fa.forward_for_expiry(db, "BANKNIFTY", _WEEKLY, on_day=_LAST) is None
        assert await fs._pick_expiry(db, "BANKNIFTY", as_of=_LAST, rules=_BOTH_IN_WINDOW) is None


class TestExactExpiryForwardIsUnchanged:
    """Calibration guard. `SellRules` were calibrated against an exact-expiry
    future, so on that path the forward must be bit-for-bit what `futures_basis`
    used to hand the engine."""

    async def test_picked_forward_equals_the_future_close_exactly(
        self, db: AsyncSession
    ) -> None:
        tc = pytest.importorskip("tradecore")
        await _seed_weekly_ahead_of_monthly(db, tc)
        picked = await fs._pick_expiry(db, "BANKNIFTY", as_of=_LAST, rules=_BOTH_IN_WINDOW)
        assert picked is not None
        day, expiry, fwd = picked
        assert (day, expiry) == (_LAST, _MONTHLY)
        # Assert the BRANCH, not the number — and note WHY the number alone can
        # never do it. For a SAME-expiry future `t_fut == t_opt`, so the carry
        # formula collapses to an identity: S·e^((ln(F/S)/t)·t) == F. The carry
        # branch would return 50249.99999999999, which quantizes to the same
        # Decimal("50250.0000"). `source` is the only thing that distinguishes
        # them, so the equality below is a genuine-but-insufficient check.
        # (The corollary is reassuring: the exact-expiry invariance is stronger
        # than "the branch is taken" — even bypassed it is accurate to ~5e-11,
        # which quantization to 1e-4 absorbs.)
        assert fwd.source == "fut_exact"
        basis = await fa.futures_basis(db, "BANKNIFTY", _MONTHLY)
        assert basis is not None
        assert fwd.price == basis.fut_close      # Decimal equality — no drift


class TestNoLookAheadInTheChain:
    """`load_chain` without `as_of` takes the LATEST recorded day for the expiry,
    unbounded — so a historical `as_of` priced a LATER chain against an EARLIER
    forward. Inert on the live endpoint (which never passes `as_of`), but the
    Phase-6 realized-vs-POP dashboard is precisely a historical-`as_of` consumer.
    """

    async def test_chain_is_bound_to_the_forward_s_own_day(self, db: AsyncSession) -> None:
        tc = pytest.importorskip("tradecore")
        await _seed_weekly_ahead_of_monthly(db, tc)
        # A LATER day on a violently different tape (spot gapped +5%, IV halved).
        later = date(2026, 8, 4)
        t_later = (_MONTHLY - later).days / 365.0
        gapped = 52500.0
        strikes = [float(k) for k in range(44000, 56001, 100)]
        calls = tc.option_price("call", [(gapped, k, t_later, _RATE, 0.0, 0.10) for k in strikes])  # type: ignore[attr-defined]
        puts = tc.option_price("put", [(gapped, k, t_later, _RATE, 0.0, 0.10) for k in strikes])  # type: ignore[attr-defined]
        db.add(FoBhavcopy(trade_date=later, symbol="BANKNIFTY", instrument="FUT",
                          expiry_date=_MONTHLY, strike=Decimal("0"),
                          close=Decimal(str(gapped)),
                          underlying_close=Decimal(str(gapped)), open_interest=1000))
        for k, cp, pp in zip(strikes, calls, puts, strict=True):
            db.add(FoBhavcopy(trade_date=later, symbol="BANKNIFTY", instrument="CE",
                              expiry_date=_MONTHLY, strike=Decimal(str(int(k))),
                              close=Decimal(str(round(cp, 2))), open_interest=1000))
            db.add(FoBhavcopy(trade_date=later, symbol="BANKNIFTY", instrument="PE",
                              expiry_date=_MONTHLY, strike=Decimal(str(int(k))),
                              close=Decimal(str(round(pp, 2))), open_interest=1000))
        await db.commit()

        # The forward still comes from _LAST …
        picked = await fs._pick_expiry(db, "BANKNIFTY", as_of=_LAST, rules=_BOTH_IN_WINDOW)
        assert picked is not None and picked[0] == _LAST

        dte = (_MONTHLY - _LAST).days
        bounded = await fa.load_chain(
            db, "BANKNIFTY", _MONTHLY,
            as_of=datetime.combine(_LAST, dtime.max, tzinfo=UTC), source="eod",
        )
        unbounded = await fa.load_chain(db, "BANKNIFTY", _MONTHLY, source="eod")
        kw = dict(fwd=_FUT_PX, t=dte / 365.0, rate=_RATE, dte=dte,
                  expiry=_MONTHLY, ivr=100.0, rules=_LOOSE, forward_source="fut_exact")
        def gated(chain: list[fa.ChainRow]) -> list[tuple[str, tuple[Decimal, ...], Decimal]]:
            built = fs._select_and_build(chain, **kw)                 # type: ignore[arg-type]
            return _shape([c for c in built if fs.passes_gates(c, _LOOSE)])

        from_last, from_later = gated(bounded), gated(unbounded)
        assert from_last, "fixture must produce candidates on _LAST's chain"
        assert from_last != from_later, "the two days must actually differ"

        # … and so must the chain the engine actually priced.
        cands = await fs.suggest_option_sells(
            db, "BANKNIFTY", rate=_RATE, as_of=_LAST, rules=_LOOSE
        )
        assert _shape(cands) == from_last
        assert _shape(cands) != from_later      # the canary: fails on the old code
