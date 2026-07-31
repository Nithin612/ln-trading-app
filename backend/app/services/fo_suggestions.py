"""F&O option-selling suggestion engine — Phase 4 slice 4.3 (STRAWMAN).

DRAFT per docs/phases/phase-04-fo-suggestions.md (option B, 2026-07-30). The
payoff math and structures here are settled; the **rules** in `SellRules` are
conservative PLACEHOLDERS to be replaced by the user's masterclass option rules
(see the doc's §7 open questions). Suggestions only — never auto-trades.

Defined-risk credit structures only in v1: bull put spread, bear call spread,
iron condor. Money = Decimal; probabilities/ratios = float.
"""

from __future__ import annotations

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
    premium: Decimal


@dataclass(frozen=True)
class SpreadCandidate:
    structure: str                       # "bull_put" | "bear_call" | "iron_condor"
    legs: tuple[OptionLeg, ...]
    net_credit: Decimal
    max_profit: Decimal
    max_loss: Decimal
    width: Decimal
    breakevens: tuple[Decimal, ...]
    pop: float                           # probability of profit (delta proxy, v1)
    margin_est: Decimal                  # defined-risk → max loss
    return_on_margin: float
    short_delta: float                   # |Δ| of the (dominant) short leg
    dte: int
    expiry: date
    rationale: str


# ── Calibration surface — CONSERVATIVE PLACEHOLDERS (⚠ calibrate) ───────────────

@dataclass(frozen=True)
class SellRules:
    """The knobs to calibrate with the user. Defaults are defensible starting
    points ONLY (doc §4) — none are the user's actual rules yet."""

    iv_rank_min: float = 50.0            # sell only when IV is rich
    short_delta_target: float = 0.16     # ≈1 SD OTM short strike
    short_delta_band: float = 0.06       # accept |Δ| within target ± band
    width_strikes: int = 1               # protection this many strikes further OTM
    dte_min: int = 14
    dte_max: int = 45
    min_oi: int = 500                    # per-leg liquidity floor
    skip_high_vix: bool = True           # stand down in a risk-off vol regime
    min_pop: float = 0.70


DEFAULT_SELL_RULES = SellRules()


# ── Payoff math (settled — calibration-independent) ─────────────────────────────

def _pop_from_delta(*short_deltas: float) -> float:
    """Delta-proxy POP: 1 − Σ|Δ(short legs)|, clamped to [0, 1]. Each short
    delta approximates that leg's probability of finishing ITM."""
    tail = sum(abs(d) for d in short_deltas)
    return max(0.0, min(1.0, 1.0 - tail))


def _vertical(
    structure: str,
    *,
    sell: OptionLeg,
    buy: OptionLeg,
    short_delta: float,
    dte: int,
    expiry: date,
    rationale: str,
) -> SpreadCandidate | None:
    """Bull-put / bear-call credit vertical. Returns None if the legs don't form
    a positive-credit, positive-max-loss defined-risk spread (bad/stale data)."""
    credit = sell.premium - buy.premium
    width = abs(sell.strike - buy.strike)
    if credit <= 0 or width <= 0 or credit >= width:
        return None
    max_loss = width - credit
    if structure == "bull_put":
        breakevens = (sell.strike - credit,)
    else:  # bear_call
        breakevens = (sell.strike + credit,)
    return SpreadCandidate(
        structure=structure,
        legs=(sell, buy),
        net_credit=credit,
        max_profit=credit,
        max_loss=max_loss,
        width=width,
        breakevens=breakevens,
        pop=_pop_from_delta(short_delta),
        margin_est=max_loss,
        return_on_margin=float(credit / max_loss),
        short_delta=abs(short_delta),
        dte=dte,
        expiry=expiry,
        rationale=rationale,
    )


def bull_put(
    *,
    sell: OptionLeg,
    buy: OptionLeg,
    short_delta: float,
    dte: int,
    expiry: date,
    rationale: str = "",
) -> SpreadCandidate | None:
    """Sell put `sell` (higher strike), buy put `buy` (lower strike). Mildly
    bullish/neutral: profits while the underlying holds above `sell.strike − C`."""
    if not (sell.option_type == "PE" and buy.option_type == "PE" and buy.strike < sell.strike):
        return None
    return _vertical(
        "bull_put", sell=sell, buy=buy, short_delta=short_delta, dte=dte, expiry=expiry,
        rationale=rationale,
    )


def bear_call(
    *,
    sell: OptionLeg,
    buy: OptionLeg,
    short_delta: float,
    dte: int,
    expiry: date,
    rationale: str = "",
) -> SpreadCandidate | None:
    """Sell call `sell` (lower strike), buy call `buy` (higher strike). Mildly
    bearish/neutral: profits while the underlying holds below `sell.strike + C`."""
    if not (sell.option_type == "CE" and buy.option_type == "CE" and buy.strike > sell.strike):
        return None
    return _vertical(
        "bear_call", sell=sell, buy=buy, short_delta=short_delta, dte=dte, expiry=expiry,
        rationale=rationale,
    )


def iron_condor(
    *,
    put: SpreadCandidate,
    call: SpreadCandidate,
    dte: int,
    expiry: date,
    rationale: str = "",
) -> SpreadCandidate | None:
    """Combine a bull-put and a bear-call into a neutral, defined-risk condor.
    Only one side can be breached, so max loss = wider wing − total credit."""
    if put.structure != "bull_put" or call.structure != "bear_call":
        return None
    credit = put.net_credit + call.net_credit
    max_loss = max(put.width, call.width) - credit
    if max_loss <= 0:
        return None
    put_short = next(leg for leg in put.legs if leg.action == "sell")
    call_short = next(leg for leg in call.legs if leg.action == "sell")
    breakevens = (put_short.strike - credit, call_short.strike + credit)
    pop = _pop_from_delta(put.short_delta, call.short_delta)
    return SpreadCandidate(
        structure="iron_condor",
        legs=put.legs + call.legs,
        net_credit=credit,
        max_profit=credit,
        max_loss=max_loss,
        width=max(put.width, call.width),
        breakevens=breakevens,
        pop=pop,
        margin_est=max_loss,
        return_on_margin=float(credit / max_loss),
        short_delta=max(put.short_delta, call.short_delta),
        dte=dte,
        expiry=expiry,
        rationale=rationale,
    )


def rank_candidates(candidates: list[SpreadCandidate]) -> list[SpreadCandidate]:
    """Best-first by return-on-margin × POP (the placeholder ranker, doc §4)."""
    return sorted(candidates, key=lambda c: c.return_on_margin * c.pop, reverse=True)


# ── Orchestration (DRAFT wiring — the calibration-shaped part, doc §4/§7) ───────
#
# This composes the settled math above with the 4.1/4.2 analytics and tradecore.
# It runs end-to-end, but the SellRules thresholds and the strike-selection logic
# are placeholders — the happy-path chain test is deferred until the rules are
# calibrated (the gate short-circuits are covered now). Do NOT treat its output
# as a recommendation until §7 is answered.

async def _pick_expiry(
    db: AsyncSession, symbol: str, *, as_of: date, rules: SellRules
) -> tuple[date, date] | None:
    """(trade_date, expiry) — the latest bhavcopy day, and the nearest expiry
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
    ).scalars().all()
    for e in expiries:
        dte = (e - day).days
        if rules.dte_min <= dte <= rules.dte_max:
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
    """Ranked defined-risk credit candidates for `symbol`. Empty when the vol
    regime / IV rank / liquidity gates reject (a valid answer). DRAFT — see the
    module and doc headers."""
    ref = as_of or date.today()

    # Gate 1 — only sell when implied vol is rich (needs an IV-rank history).
    ivr = await fa.iv_rank(db, symbol, rate=rate, as_of=ref)
    if ivr is None or ivr.rank < rules.iv_rank_min:
        return []

    # Gate 2 — stand down in a risk-off vol regime.
    vix = await fa.vix_regime(db, as_of=datetime(ref.year, ref.month, ref.day))
    if rules.skip_high_vix and vix is not None and vix.band == "high":
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
    legs = _select_and_build(chain, fwd=fwd, t=t, rate=rate, dte=dte, expiry=expiry, ivr=ivr.rank,
                             rules=rules)
    return rank_candidates(legs)


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
    """Pure-ish: from a chain, price IV+delta per strike (tradecore), pick short
    strikes near the target delta, and build the three defined-risk structures
    that clear the OI/POP gates. tradecore is the only side effect (compute)."""
    import tradecore  # deferred: parity-gated wheel (idiom: signal_service)

    ce = {r.strike: r for r in chain if r.option_type == "CE" and r.ltp and r.ltp > 0}
    pe = {r.strike: r for r in chain if r.option_type == "PE" and r.ltp and r.ltp > 0}
    if not ce or not pe:
        return []

    def deltas(rows: dict[Decimal, fa.ChainRow], kind: str) -> dict[Decimal, float]:
        strikes = sorted(rows)
        iv_in = [(float(rows[k].ltp), fwd, float(k), t, rate, 0.0) for k in strikes]  # type: ignore[arg-type]
        ivs = tradecore.implied_vol(kind, iv_in)
        g_in = [
            (fwd, float(k), t, rate, 0.0, iv)
            for k, iv in zip(strikes, ivs, strict=True)
            if iv is not None
        ]
        g_strikes = [k for k, iv in zip(strikes, ivs, strict=True) if iv is not None]
        greeks = tradecore.option_greeks(kind, g_in)
        return {
            k: g[0] for k, g in zip(g_strikes, greeks, strict=True) if g is not None
        }  # g[0] = delta

    ce_delta = deltas(ce, "call")
    pe_delta = deltas(pe, "put")

    lo, hi = rules.short_delta_target - rules.short_delta_band, (
        rules.short_delta_target + rules.short_delta_band
    )
    strikes_sorted = sorted({*ce, *pe})

    def nearest_short(delta_map: dict[Decimal, float]) -> Decimal | None:
        band = [k for k, d in delta_map.items() if lo <= abs(d) <= hi]
        if not band:
            return None
        return min(band, key=lambda k: abs(abs(delta_map[k]) - rules.short_delta_target))

    def leg(rows: dict[Decimal, fa.ChainRow], k: Decimal, action: str, kind: str) -> OptionLeg:
        return OptionLeg(action=action, option_type=kind, strike=k, premium=rows[k].ltp)  # type: ignore[arg-type]

    def liquid(rows: dict[Decimal, fa.ChainRow], *ks: Decimal) -> bool:
        return all(rows[k].oi >= rules.min_oi for k in ks)

    out: list[SpreadCandidate] = []
    step = _strike_step(strikes_sorted)

    # Bull put: short OTM put, long `width` strikes lower.
    ps = nearest_short(pe_delta)
    if ps is not None and step is not None:
        pl = ps - step * rules.width_strikes
        if pl in pe and liquid(pe, ps, pl):
            c = bull_put(sell=leg(pe, ps, "sell", "PE"), buy=leg(pe, pl, "buy", "PE"),
                         short_delta=pe_delta[ps], dte=dte, expiry=expiry,
                         rationale=f"IV-rank {ivr:.0f}, {abs(pe_delta[ps]):.2f}Δ short put")
            if c and c.pop >= rules.min_pop:
                out.append(c)

    # Bear call: short OTM call, long `width` strikes higher.
    cs = nearest_short(ce_delta)
    if cs is not None and step is not None:
        ch = cs + step * rules.width_strikes
        if ch in ce and liquid(ce, cs, ch):
            c = bear_call(sell=leg(ce, cs, "sell", "CE"), buy=leg(ce, ch, "buy", "CE"),
                          short_delta=ce_delta[cs], dte=dte, expiry=expiry,
                          rationale=f"IV-rank {ivr:.0f}, {abs(ce_delta[cs]):.2f}Δ short call")
            if c and c.pop >= rules.min_pop:
                out.append(c)

    # Iron condor: both wings, if both verticals formed.
    bp = next((c for c in out if c.structure == "bull_put"), None)
    bc = next((c for c in out if c.structure == "bear_call"), None)
    if bp is not None and bc is not None:
        ic = iron_condor(put=bp, call=bc, dte=dte, expiry=expiry,
                         rationale=f"IV-rank {ivr:.0f}, neutral condor")
        if ic and ic.pop >= rules.min_pop:
            out.append(ic)
    return out


def _strike_step(strikes: list[Decimal]) -> Decimal | None:
    """Smallest gap between adjacent strikes (the strike interval). None if <2."""
    if len(strikes) < 2:
        return None
    gaps = [b - a for a, b in zip(strikes, strikes[1:], strict=False) if b > a]
    return min(gaps) if gaps else None
