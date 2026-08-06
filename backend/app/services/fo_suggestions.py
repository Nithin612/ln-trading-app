"""F&O option-selling suggestion engine — Phase 4 slice 4.3.

Defined-risk credit structures (bull put, bear call, iron condor) with the v1
rules calibrated 2026-08-06 (docs/phases/phase-04-fo-suggestions.md): sell only
rich IV, ~1-SD-OTM short strikes, a reward floor, positive expectancy, hard
VIX/liquidity gates, and mechanical exits. Suggestions only — never auto-trades;
paper/human-confirmed behind the go-live gate.

Design invariants (finance-safety):
  - Defined-risk only — max loss = width − credit, always known.
  - Cash-settled INDEX underlyings only in v1 (no physical-settlement/assignment).
  - Conservative fills — sold legs haircut down, bought legs up (never optimistic).
  - Reward floor + positive expectancy — reject high-POP/low-reward "pennies".
  - Hard vetoes (risk-off VIX regime, illiquid legs) — non-negotiable.

Money = Decimal; probabilities / ratios = float.

Follow-ups (flagged, not v1): confluence-engine directional tilt (Q8), the full
event calendar / F&O-ban veto (the deferred Market Context Engine, Q9), and Kite
SPAN-margin refinement (we use defined-risk max-loss as the margin proxy).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fo_data import FoBhavcopy
from app.services import fo_analytics as fa

# ── Structures ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class OptionLeg:
    action: str          # "sell" | "buy"
    option_type: str     # "CE" | "PE"
    strike: Decimal
    premium: Decimal     # the conservative fill (haircut applied by the caller)


@dataclass(frozen=True)
class ExitPlan:
    """Mechanical exits (metadata; execution lands in Phase-6/live)."""

    take_profit_credit: Decimal   # close when this much of the credit is captured
    stop_loss_amount: Decimal     # cut when the loss reaches this (≤ max loss)
    time_stop_dte: int            # close by this many days to expiry (gamma zone)


@dataclass(frozen=True)
class SpreadCandidate:
    structure: str                       # "bull_put" | "bear_call" | "iron_condor"
    legs: tuple[OptionLeg, ...]
    net_credit: Decimal
    max_profit: Decimal
    max_loss: Decimal
    width: Decimal
    breakevens: tuple[Decimal, ...]
    pop: float                           # probability of profit (breakeven-exact when priced)
    expectancy: Decimal                  # POP·credit − (1−POP)·max_loss; risk-neutral ≈0 (info)
    margin_est: Decimal                  # defined-risk → max loss
    return_on_margin: float
    short_delta: float                   # |Δ| of the (dominant) short leg
    dte: int
    expiry: date
    exit_plan: ExitPlan
    rationale: str


# ── Calibration surface — v1 defaults (user-approved 2026-08-06) ────────────────

@dataclass(frozen=True)
class SellRules:
    """v1 conservative defaults. Still forward-tested on paper before live; the
    user's masterclass numbers drop straight in here."""

    # Universe: cash-settled index only (no physical settlement / assignment).
    allowed_underlyings: frozenset[str] = frozenset({"NIFTY", "BANKNIFTY", "FINNIFTY"})
    iv_rank_min: float = 50.0            # sell only when IV is rich (upper half)
    short_delta_target: float = 0.16     # ≈1 SD OTM short strike
    short_delta_band: float = 0.06       # accept |Δ| within target ± band
    width_strikes: int = 1               # protection this many strikes further OTM
    dte_min: int = 20                    # theta window, away from the gamma zone
    dte_max: int = 45
    min_oi: int = 500                    # per-leg liquidity floor
    skip_high_vix: bool = True           # hard veto: stand down in risk-off vol
    min_pop: float = 0.65                # breakeven-exact (risk-neutral) POP floor
    min_credit_to_width: float = 0.30    # reward floor — no high-POP "pennies"
    # Conservative per-leg fill haircut ≈ each leg's half bid-ask: the LARGER of
    # a % of premium and a floor in points (so cheap far-OTM legs aren't
    # under-slipped and narrow spreads aren't over-slipped). Real per-leg bid/ask
    # from intraday snapshots is the calibration refinement.
    slippage_frac: float = 0.005         # 0.5% of premium …
    min_slippage: Decimal = Decimal("1.0")  # … but at least 1 point per leg
    # NOTE: there is deliberately NO "expectancy > 0" gate. Under fair
    # (risk-neutral) pricing a credit spread's expectancy is ~0 by construction,
    # so such a gate would reject everything. The edge is the volatility risk
    # premium — proxied by the IV-rank gate (sell only rich IV) and validated by
    # forward-testing, NOT provable from prices. `expectancy` is REPORTED (below)
    # for transparency; note the two-point estimator (POP·credit − (1−POP)·max_loss)
    # is a CONSERVATIVE, slightly negative-biased proxy of the true risk-neutral
    # zero — a mildly negative reported value is expected for a fair spread, not a
    # red flag.
    # Mechanical exits (metadata):
    take_profit_pct: float = 0.50        # bank 50% of the credit
    stop_loss_mult: float = 2.0          # cut at 2× credit lost
    time_stop_dte: int = 21              # exit before the gamma zone


DEFAULT_SELL_RULES = SellRules()


# ── Probability / expectancy (calibration-independent) ──────────────────────────

def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _prob_above(fwd: float, strike: float, iv: float, t: float) -> float:
    """Risk-neutral P(S_T > strike) under Black-76 (forward, carry 0)."""
    d2 = (math.log(fwd / strike) - 0.5 * iv * iv * t) / (iv * math.sqrt(t))
    return _norm_cdf(d2)


def breakeven_pop(
    structure: str, *, fwd: float, breakevens: tuple[Decimal, ...], iv: float, t: float
) -> float | None:
    """Exact probability of profit = P(finish on the profitable side of the
    breakeven), Black-76 on the future. None when inputs are degenerate."""
    if fwd <= 0 or iv <= 0 or t <= 0 or any(b <= 0 for b in breakevens):
        return None
    if structure == "bull_put":
        return _prob_above(fwd, float(breakevens[0]), iv, t)          # P(S ≥ be)
    if structure == "bear_call":
        return 1.0 - _prob_above(fwd, float(breakevens[0]), iv, t)    # P(S ≤ be)
    if structure == "iron_condor":
        lo, up = float(breakevens[0]), float(breakevens[1])
        p = _prob_above(fwd, lo, iv, t) - _prob_above(fwd, up, iv, t)  # P(lo ≤ S ≤ up)
        return max(0.0, min(1.0, p))
    return None


def _pop_from_delta(*short_deltas: float) -> float:
    """Delta-proxy POP fallback: 1 − Σ|Δ(short legs)|, clamped to [0, 1]."""
    return max(0.0, min(1.0, 1.0 - sum(abs(d) for d in short_deltas)))


# ── Payoff math (settled) ───────────────────────────────────────────────────────

def _make_candidate(
    *,
    structure: str,
    legs: tuple[OptionLeg, ...],
    net_credit: Decimal,
    max_loss: Decimal,
    width: Decimal,
    breakevens: tuple[Decimal, ...],
    pop: float,
    short_delta: float,
    dte: int,
    expiry: date,
    rationale: str,
    take_profit_pct: float,
    stop_loss_mult: float,
    time_stop_dte: int,
) -> SpreadCandidate:
    pop_d = Decimal(str(pop))
    expectancy = pop_d * net_credit - (Decimal(1) - pop_d) * max_loss
    exit_plan = ExitPlan(
        take_profit_credit=net_credit * Decimal(str(take_profit_pct)),
        stop_loss_amount=min(net_credit * Decimal(str(stop_loss_mult)), max_loss),
        time_stop_dte=time_stop_dte,
    )
    return SpreadCandidate(
        structure=structure,
        legs=legs,
        net_credit=net_credit,
        max_profit=net_credit,
        max_loss=max_loss,
        width=width,
        breakevens=breakevens,
        pop=pop,
        expectancy=expectancy,
        margin_est=max_loss,
        return_on_margin=float(net_credit / max_loss),
        short_delta=short_delta,
        dte=dte,
        expiry=expiry,
        exit_plan=exit_plan,
        rationale=rationale,
    )


def _vertical(
    structure: str,
    *,
    sell: OptionLeg,
    buy: OptionLeg,
    short_delta: float,
    dte: int,
    expiry: date,
    rationale: str,
    pop_override: float | None = None,
    take_profit_pct: float = 0.50,
    stop_loss_mult: float = 2.0,
    time_stop_dte: int = 21,
) -> SpreadCandidate | None:
    credit = sell.premium - buy.premium
    width = abs(sell.strike - buy.strike)
    if credit <= 0 or width <= 0 or credit >= width:
        return None
    max_loss = width - credit
    breakevens = (
        (sell.strike - credit,) if structure == "bull_put" else (sell.strike + credit,)
    )
    pop = pop_override if pop_override is not None else _pop_from_delta(short_delta)
    return _make_candidate(
        structure=structure, legs=(sell, buy), net_credit=credit, max_loss=max_loss,
        width=width, breakevens=breakevens, pop=pop, short_delta=abs(short_delta),
        dte=dte, expiry=expiry, rationale=rationale, take_profit_pct=take_profit_pct,
        stop_loss_mult=stop_loss_mult, time_stop_dte=time_stop_dte,
    )


def bull_put(
    *,
    sell: OptionLeg,
    buy: OptionLeg,
    short_delta: float,
    dte: int,
    expiry: date,
    rationale: str = "",
    pop_override: float | None = None,
) -> SpreadCandidate | None:
    """Sell put `sell` (higher strike), buy put `buy` (lower strike)."""
    if not (sell.option_type == "PE" and buy.option_type == "PE" and buy.strike < sell.strike):
        return None
    return _vertical(
        "bull_put", sell=sell, buy=buy, short_delta=short_delta, dte=dte, expiry=expiry,
        rationale=rationale, pop_override=pop_override,
    )


def bear_call(
    *,
    sell: OptionLeg,
    buy: OptionLeg,
    short_delta: float,
    dte: int,
    expiry: date,
    rationale: str = "",
    pop_override: float | None = None,
) -> SpreadCandidate | None:
    """Sell call `sell` (lower strike), buy call `buy` (higher strike)."""
    if not (sell.option_type == "CE" and buy.option_type == "CE" and buy.strike > sell.strike):
        return None
    return _vertical(
        "bear_call", sell=sell, buy=buy, short_delta=short_delta, dte=dte, expiry=expiry,
        rationale=rationale, pop_override=pop_override,
    )


def iron_condor(
    *,
    put: SpreadCandidate,
    call: SpreadCandidate,
    dte: int,
    expiry: date,
    rationale: str = "",
    pop_override: float | None = None,
) -> SpreadCandidate | None:
    """Combine a bull-put and a bear-call into a neutral, defined-risk condor.
    Only one side can be breached, so max loss = wider wing − total credit."""
    if put.structure != "bull_put" or call.structure != "bear_call":
        return None
    put_short = next(leg for leg in put.legs if leg.action == "sell")
    call_short = next(leg for leg in call.legs if leg.action == "sell")
    if put_short.strike >= call_short.strike:
        return None  # overlapping/inverted shorts → the one-side-breachable math breaks
    credit = put.net_credit + call.net_credit
    max_loss = max(put.width, call.width) - credit
    if max_loss <= 0:
        return None
    breakevens = (put_short.strike - credit, call_short.strike + credit)
    pop = (
        pop_override
        if pop_override is not None
        else _pop_from_delta(put.short_delta, call.short_delta)
    )
    return _make_candidate(
        structure="iron_condor", legs=put.legs + call.legs, net_credit=credit,
        max_loss=max_loss, width=max(put.width, call.width), breakevens=breakevens, pop=pop,
        short_delta=max(put.short_delta, call.short_delta), dte=dte, expiry=expiry,
        rationale=rationale, take_profit_pct=0.50, stop_loss_mult=2.0, time_stop_dte=21,
    )


def rank_candidates(candidates: list[SpreadCandidate]) -> list[SpreadCandidate]:
    """Best-first by return-on-margin × POP."""
    return sorted(candidates, key=lambda c: c.return_on_margin * c.pop, reverse=True)


def passes_gates(c: SpreadCandidate, rules: SellRules) -> bool:
    """Reward floor + POP floor (the risk controls). Expectancy is reported, not
    gated — see the SellRules note on why a risk-neutral expectancy gate is wrong."""
    reward_floor = Decimal(str(rules.min_credit_to_width)) * c.width
    return c.net_credit >= reward_floor and c.pop >= rules.min_pop


# ── Orchestration ───────────────────────────────────────────────────────────────

async def _pick_expiry(
    db: AsyncSession, symbol: str, *, as_of: date, rules: SellRules
) -> tuple[date, date] | None:
    """(trade_date, expiry) — the latest bhavcopy day and the nearest expiry
    whose days-to-expiry fall in the rules' DTE window."""
    day = (
        await db.execute(
            select(FoBhavcopy.trade_date)
            .where(FoBhavcopy.symbol == symbol, FoBhavcopy.trade_date <= as_of)
            .order_by(FoBhavcopy.trade_date.desc())
            .limit(1)
        )
    ).scalar()
    if day is None:
        return None
    expiries = (
        (
            await db.execute(
                select(FoBhavcopy.expiry_date)
                .where(
                    FoBhavcopy.symbol == symbol,
                    FoBhavcopy.trade_date == day,
                    FoBhavcopy.instrument.in_(("CE", "PE")),
                )
                .distinct()
                .order_by(FoBhavcopy.expiry_date.asc())
            )
        )
        .scalars()
        .all()
    )
    for e in expiries:
        if rules.dte_min <= (e - day).days <= rules.dte_max:
            return day, e
    return None


async def suggest_option_sells(
    db: AsyncSession,
    symbol: str,
    *,
    rules: SellRules = DEFAULT_SELL_RULES,
    as_of: date | None = None,
    rate: float = 0.065,
) -> list[SpreadCandidate]:
    """Ranked defined-risk credit candidates for `symbol`. Empty when the
    universe / IV-rank / vol-regime / expiry / liquidity gates reject — a valid
    answer. Suggestions only; never an order."""
    ref = as_of or date.today()

    # Gate 0 — cash-settled index universe only (no physical settlement).
    if symbol not in rules.allowed_underlyings:
        return []

    # Gate 1 — only sell when implied vol is rich (needs an IV-rank history).
    ivr = await fa.iv_rank(db, symbol, rate=rate, as_of=ref)
    if ivr is None or ivr.rank < rules.iv_rank_min:
        return []

    # Gate 2 — HARD veto (fail-CLOSED): stand down in a risk-off vol regime AND
    # when the regime can't be assessed (no VIX data). A blind safety gate must
    # not pass — a vol spike lifts IV-rank (Gate 1 passes), so this is the backstop.
    vix = await fa.vix_regime(db, as_of=datetime(ref.year, ref.month, ref.day))
    if rules.skip_high_vix and (vix is None or vix.band == "high"):
        return []

    picked = await _pick_expiry(db, symbol, as_of=ref, rules=rules)
    if picked is None:
        return []
    day, expiry = picked
    dte = (expiry - day).days

    basis = await fa.futures_basis(db, symbol, expiry, as_of=datetime(day.year, day.month, day.day))
    if basis is None:
        return []
    fwd = float(basis.fut_close)  # Black-76 forward
    t = dte / 365.0

    chain = await fa.load_chain(db, symbol, expiry, source="eod")
    candidates = _select_and_build(
        chain, fwd=fwd, t=t, rate=rate, dte=dte, expiry=expiry, ivr=ivr.rank, rules=rules
    )
    return rank_candidates([c for c in candidates if passes_gates(c, rules)])


@dataclass(frozen=True)
class _StrikeInfo:
    premium: Decimal      # raw LTP (haircut applied at leg construction)
    delta: float
    iv: float
    oi: int


def _select_and_build(  # noqa: C901 — linear strike-selection + three structures
    chain: list[fa.ChainRow],
    *,
    fwd: float,
    t: float,
    rate: float,
    dte: int,
    expiry: date,
    ivr: float,
    rules: SellRules,
) -> list[SpreadCandidate]:
    """From a chain: price IV+delta per strike (tradecore), pick short strikes
    near the target delta, and build the defined-risk structures with
    conservative fills and breakeven-exact POP. tradecore is the only compute."""
    import tradecore  # deferred: parity-gated wheel (idiom: signal_service)

    def build_side(kind: str) -> dict[Decimal, _StrikeInfo]:
        rows = {r.strike: r for r in chain if r.option_type == kind and r.ltp and r.ltp > 0}
        strikes = sorted(rows)
        if not strikes:
            return {}
        iv_in = [(float(rows[k].ltp), fwd, float(k), t, rate, 0.0) for k in strikes]  # type: ignore[arg-type]
        ivs = tradecore.implied_vol(kind, iv_in)
        info: dict[Decimal, _StrikeInfo] = {}
        g_rows = [
            (k, iv) for k, iv in zip(strikes, ivs, strict=True) if iv is not None and iv > 0
        ]
        greeks = tradecore.option_greeks(
            kind, [(fwd, float(k), t, rate, 0.0, iv) for k, iv in g_rows]
        )
        for (k, iv), g in zip(g_rows, greeks, strict=True):
            if g is None:
                continue
            r = rows[k]
            info[k] = _StrikeInfo(premium=r.ltp, delta=g[0], iv=iv, oi=r.oi)  # type: ignore[arg-type]
        return info

    ce = build_side("CE")   # chain option_type is "CE"/"PE"; tradecore accepts both
    pe = build_side("PE")
    if not ce or not pe:
        return []

    step = _strike_step(sorted({*ce, *pe}))
    if step is None:
        return []
    lo, hi = (
        rules.short_delta_target - rules.short_delta_band,
        rules.short_delta_target + rules.short_delta_band,
    )

    def nearest_short(info: dict[Decimal, _StrikeInfo]) -> Decimal | None:
        band = [k for k, v in info.items() if lo <= abs(v.delta) <= hi]
        return (
            min(band, key=lambda k: abs(abs(info[k].delta) - rules.short_delta_target))
            if band
            else None
        )

    frac = Decimal(str(rules.slippage_frac))

    def _haircut(prem: Decimal) -> Decimal:
        return max(prem * frac, rules.min_slippage)  # ≈ one leg's half bid-ask

    def sell_leg(info: dict[Decimal, _StrikeInfo], k: Decimal, kind: str) -> OptionLeg:
        prem = info[k].premium
        fill = max(Decimal(0), prem - _haircut(prem))  # sold → receive less (floored at 0)
        return OptionLeg(action="sell", option_type=kind, strike=k, premium=fill)

    def buy_leg(info: dict[Decimal, _StrikeInfo], k: Decimal, kind: str) -> OptionLeg:
        prem = info[k].premium
        fill = prem + _haircut(prem)  # bought → pay more
        return OptionLeg(action="buy", option_type=kind, strike=k, premium=fill)

    out: list[SpreadCandidate] = []

    # Bull put: short OTM put, long `width` strikes lower.
    ps = nearest_short(pe)
    bp: SpreadCandidate | None = None
    if ps is not None:
        pl = ps - step * rules.width_strikes
        if pl in pe and pe[ps].oi >= rules.min_oi and pe[pl].oi >= rules.min_oi:
            draft = bull_put(
                sell=sell_leg(pe, ps, "PE"), buy=buy_leg(pe, pl, "PE"),
                short_delta=pe[ps].delta, dte=dte, expiry=expiry,
                rationale=f"IV-rank {ivr:.0f}, {abs(pe[ps].delta):.2f}Δ short put",
            )
            if draft is not None:
                pop = breakeven_pop(
                    "bull_put", fwd=fwd, breakevens=draft.breakevens, iv=pe[ps].iv, t=t
                )
                bp = bull_put(
                    sell=sell_leg(pe, ps, "PE"), buy=buy_leg(pe, pl, "PE"),
                    short_delta=pe[ps].delta, dte=dte, expiry=expiry,
                    rationale=draft.rationale, pop_override=pop,
                )
                if bp is not None:
                    out.append(bp)

    # Bear call: short OTM call, long `width` strikes higher.
    cs = nearest_short(ce)
    bc: SpreadCandidate | None = None
    if cs is not None:
        ch = cs + step * rules.width_strikes
        if ch in ce and ce[cs].oi >= rules.min_oi and ce[ch].oi >= rules.min_oi:
            draft = bear_call(
                sell=sell_leg(ce, cs, "CE"), buy=buy_leg(ce, ch, "CE"),
                short_delta=ce[cs].delta, dte=dte, expiry=expiry,
                rationale=f"IV-rank {ivr:.0f}, {abs(ce[cs].delta):.2f}Δ short call",
            )
            if draft is not None:
                pop = breakeven_pop(
                    "bear_call", fwd=fwd, breakevens=draft.breakevens, iv=ce[cs].iv, t=t
                )
                bc = bear_call(
                    sell=sell_leg(ce, cs, "CE"), buy=buy_leg(ce, ch, "CE"),
                    short_delta=ce[cs].delta, dte=dte, expiry=expiry,
                    rationale=draft.rationale, pop_override=pop,
                )
                if bc is not None:
                    out.append(bc)

    # Iron condor: both wings (neutral default), if both verticals formed.
    if bp is not None and bc is not None and ps is not None and cs is not None:
        draft = iron_condor(put=bp, call=bc, dte=dte, expiry=expiry)
        if draft is not None:
            mid_iv = (pe[ps].iv + ce[cs].iv) / 2.0
            pop = breakeven_pop(
                "iron_condor", fwd=fwd, breakevens=draft.breakevens, iv=mid_iv, t=t
            )
            ic = iron_condor(
                put=bp, call=bc, dte=dte, expiry=expiry,
                rationale=f"IV-rank {ivr:.0f}, neutral condor", pop_override=pop,
            )
            if ic is not None:
                out.append(ic)
    return out


def _strike_step(strikes: list[Decimal]) -> Decimal | None:
    """Smallest gap between adjacent strikes (the strike interval). None if <2."""
    if len(strikes) < 2:
        return None
    gaps = [b - a for a, b in zip(strikes, strikes[1:], strict=False) if b > a]
    return min(gaps) if gaps else None
