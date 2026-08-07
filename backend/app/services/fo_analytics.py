"""F&O analytics — Phase 4 slice 4.1 (arithmetic-only, offline).

Computes option-chain analytics from the Phase-0 recorders (`fo_bhavcopy`,
`option_chain_snapshots`, `india_vix_daily`). Read-only: no writes, no
migration — it only reads already-recorded history.

Scope boundary: the options MATH itself — Black-Scholes/Black-76 pricing,
implied-vol inversion, Greeks — is Rust-only (`engine/`, Phase 4 slice 4.2,
validated against goldens) and is never reimplemented here. What lives here is
(a) the pure-arithmetic layer that needs no solver — put/call ratio, max pain,
futures basis, India VIX regime — and (b) the orchestration that assembles
inputs, makes ONE batched `tradecore` call, and shapes the result: `iv_rank`
(4.2b) and `price_chain_greeks` (per-leg IV + Greeks for the chain ladder, 5.2).

Money = Decimal. Ratios / percentiles = float (analytical, never money).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fo_data import FoBhavcopy, IndiaVixDaily, OptionChainSnapshot

_ZERO = Decimal(0)
_IST = ZoneInfo("Asia/Kolkata")
# How many futures expiries past the option to consider when the nearest one has
# no settlement price. Indian index futures list 3 serial months, so 4 covers the
# whole board with room to spare while staying an indexed, bounded lookup.
_FUT_FALLBACK_DEPTH = 4


# ── Value types ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ChainRow:
    """One option leg (a single strike + type) at a point in time."""

    strike: Decimal
    option_type: str          # "CE" | "PE"
    oi: int
    volume: int
    ltp: Decimal | None


@dataclass(frozen=True)
class PutCallRatio:
    pcr_oi: float | None       # None when there is no call OI (undefined ratio)
    pcr_volume: float | None
    total_ce_oi: int
    total_pe_oi: int


@dataclass(frozen=True)
class Basis:
    fut_close: Decimal
    underlying_close: Decimal
    basis: Decimal             # fut − underlying (carry; +ve = contango)
    basis_pct: float


@dataclass(frozen=True)
class VixRegime:
    current: Decimal
    percentile: float          # 0–100, share of the lookback strictly below current
    band: str                  # "low" | "normal" | "high"
    sample: int                # sessions counted in the lookback (incl. current)


@dataclass(frozen=True)
class ChainForward:
    """The Black-76 forward to price ONE option expiry against.

    Index options are weekly; index futures are monthly — so most option
    expiries have NO future of their own and a same-expiry lookup returns
    nothing (on a real NIFTY day, 3 of 12 option expiries have a FUT row).
    `source` records how the forward was obtained so the UI can never imply a
    same-expiry future that doesn't exist.
    """

    price: Decimal
    source: str          # "fut_exact" | "fut_carry_implied"
    trade_date: date     # the bhavcopy day the inputs came from
    fut_expiry: date     # which future was used


@dataclass(frozen=True)
class LegGreeks:
    """Implied vol + Greeks for ONE chain leg, priced off the future (Black-76).

    Per-contract values as `tradecore` returns them: `theta` is per year and
    `vega` per 1.00 (100 vol points) of implied vol — the display layer scales
    them, so nothing here is pre-divided.
    """

    iv: float                  # annualized implied vol, inverted from the quote
    delta: float
    gamma: float
    vega: float
    theta: float


@dataclass(frozen=True)
class IvRank:
    as_of: date                # the latest trading day with a computable IV
    current_iv: float          # ATM front-month implied vol (annualized) on as_of
    rank: float                # (current − min)/(max − min)·100 over the window
    percentile: float          # % of the window strictly below current
    min_iv: float
    max_iv: float
    sample: int                # days with a computable IV in the window


# ── Pure analytics (no I/O — hand-testable) ─────────────────────────────────────

def put_call_ratio(rows: Sequence[ChainRow]) -> PutCallRatio:
    """PCR by OI and by volume. Ratio is None when the denominator (call side)
    is zero — an undefined ratio is reported as None, never 0 or infinity."""
    ce_oi = sum(r.oi for r in rows if r.option_type == "CE")
    pe_oi = sum(r.oi for r in rows if r.option_type == "PE")
    ce_vol = sum(r.volume for r in rows if r.option_type == "CE")
    pe_vol = sum(r.volume for r in rows if r.option_type == "PE")
    return PutCallRatio(
        pcr_oi=(pe_oi / ce_oi) if ce_oi > 0 else None,
        pcr_volume=(pe_vol / ce_vol) if ce_vol > 0 else None,
        total_ce_oi=ce_oi,
        total_pe_oi=pe_oi,
    )


def max_pain(rows: Sequence[ChainRow]) -> Decimal | None:
    """The strike that minimises total option-writer payout at expiry — i.e.
    where the most option value expires worthless (the "pin").

    For a candidate expiry price E:
        call payout = Σ (E − K)·CE_OI for strikes K < E
        put  payout = Σ (K − E)·PE_OI for strikes K > E
    Max pain = argmin over the traded strikes of (call + put) payout.
    Ties resolve to the LOWER strike (strikes iterated ascending, strict `<`).
    Returns None on an empty chain.
    """
    ce_oi: dict[Decimal, int] = {}
    pe_oi: dict[Decimal, int] = {}
    for r in rows:
        if r.option_type == "CE":
            ce_oi[r.strike] = ce_oi.get(r.strike, 0) + r.oi
        elif r.option_type == "PE":
            pe_oi[r.strike] = pe_oi.get(r.strike, 0) + r.oi

    strikes = sorted(set(ce_oi) | set(pe_oi))
    if not strikes:
        return None

    best_strike: Decimal | None = None
    best_pain: Decimal | None = None
    for expiry_px in strikes:
        call_pain = sum(
            ((expiry_px - k) * oi for k, oi in ce_oi.items() if k < expiry_px), _ZERO
        )
        put_pain = sum(
            ((k - expiry_px) * oi for k, oi in pe_oi.items() if k > expiry_px), _ZERO
        )
        total = call_pain + put_pain
        if best_pain is None or total < best_pain:
            best_pain = total
            best_strike = expiry_px
    return best_strike


def atm_strike(rows: Sequence[ChainRow], spot: Decimal) -> Decimal | None:
    """The traded strike closest to spot. Ties resolve to the lower strike."""
    strikes = sorted({r.strike for r in rows})
    if not strikes:
        return None
    return min(strikes, key=lambda k: (abs(k - spot), k))


def near_atm(rows: Sequence[ChainRow], spot: Decimal, n: int) -> list[ChainRow]:
    """Keep only rows within ±n strikes of ATM (both CE and PE at each kept
    strike). n <= 0 or no ATM → return rows unchanged."""
    atm = atm_strike(rows, spot)
    if atm is None or n <= 0:
        return list(rows)
    strikes = sorted({r.strike for r in rows})
    idx = strikes.index(atm)
    keep = set(strikes[max(0, idx - n): idx + n + 1])
    return [r for r in rows if r.strike in keep]


# ── Async loaders (read the recorders) ──────────────────────────────────────────

def price_chain_greeks(
    rows: Sequence[ChainRow], *, fwd: float, t: float, rate: float
) -> dict[tuple[Decimal, str], LegGreeks]:
    """Invert every quoted leg to an implied vol, then price its Greeks.

    Black-76 on the FUTURE (carry = 0) — the same convention `iv_rank` uses, so
    a strike's IV here is directly comparable to the IV-rank history rather than
    being a second, subtly different number for the same thing.

    Keyed by `(strike, option_type)`. Legs without a positive quote, or whose
    premium won't invert (deep-ITM at intrinsic, negligible vega), are simply
    ABSENT from the result — never zero-filled, because a 0.0 delta or IV reads
    as a real, tradeable value on screen. Two batched `tradecore` calls per
    side; the Rust wheel remains the only options-math implementation.
    """
    if t <= 0 or fwd <= 0:
        return {}

    import tradecore  # deferred: parity-gated wheel (idiom: signal_service)

    out: dict[tuple[Decimal, str], LegGreeks] = {}
    for kind in ("CE", "PE"):
        quoted: list[tuple[ChainRow, float]] = []
        for r in rows:
            if r.option_type != kind or r.ltp is None or r.ltp <= _ZERO:
                continue
            quoted.append((r, float(r.ltp)))
        if not quoted:
            continue

        ivs = tradecore.implied_vol(
            kind, [(prem, fwd, float(r.strike), t, rate, 0.0) for r, prem in quoted]
        )
        priced = [
            (r, iv)
            for (r, _prem), iv in zip(quoted, ivs, strict=True)
            if iv is not None and iv > 0
        ]
        if not priced:
            continue

        greeks = tradecore.option_greeks(
            kind, [(fwd, float(r.strike), t, rate, 0.0, iv) for r, iv in priced]
        )
        for (r, iv), g in zip(priced, greeks, strict=True):
            if g is None:
                continue
            delta, gamma, vega, theta, _rho = g  # tradecore order, NOT alphabetical
            out[(r.strike, kind)] = LegGreeks(
                iv=iv, delta=delta, gamma=gamma, vega=vega, theta=theta
            )
    return out


async def spot_on_day(db: AsyncSession, symbol: str, day: date) -> Decimal | None:
    """Underlying spot for `symbol` on `day`, from ANY contract's recorded
    `underlying_close`.

    `latest_spot` reads it off the FUT row for a specific expiry, which is
    empty for every weekly option expiry. Every CE/PE row carries the same
    underlying price, so the chain day always has a spot even when its expiry
    has no future — without one there is no ATM strike and the ±N strike
    window silently degrades to the whole chain.
    """
    return (
        await db.execute(
            select(FoBhavcopy.underlying_close)
            .where(
                FoBhavcopy.symbol == symbol,
                FoBhavcopy.trade_date == day,
                FoBhavcopy.underlying_close.is_not(None),
            )
            .limit(1)
        )
    ).scalar()


async def forward_for_expiry(
    db: AsyncSession, symbol: str, expiry: date, *, on_day: date
) -> ChainForward | None:
    """Black-76 forward for `expiry`, using futures recorded on `on_day`.

    - Exact-expiry future (monthly option expiries) → use its close directly.
    - Otherwise (every weekly expiry) → imply the market's own cost of carry
      from the NEAREST future expiring on/after the option, and grow spot by it:
      `b = ln(F_fut / S) / T_fut`, `F_opt = S · e^(b · T_opt)`. This uses the
      traded curve rather than assuming a rate or a dividend yield.
    - No usable future on that day → None, and the caller reports Greeks as
      unknown rather than pricing against a guessed forward.

    Deliberately pinned to `on_day`: reading "the latest FUT row at or before"
    would price an INTRADAY chain against yesterday's futures close (EOD
    bhavcopy lands ~18:45 IST), silently skewing every IV and delta.
    """
    # Take the NEAREST future on/after the option that actually has a settlement
    # price. Looking at only the nearest row meant one unpriced recorder row
    # killed the forward — and so every Greek — for the whole front chain, even
    # with a perfectly good future one expiry further out.
    candidates = (
        await db.execute(
            select(FoBhavcopy.close, FoBhavcopy.underlying_close, FoBhavcopy.expiry_date)
            .where(
                FoBhavcopy.symbol == symbol,
                FoBhavcopy.instrument == "FUT",
                FoBhavcopy.trade_date == on_day,
                FoBhavcopy.expiry_date >= expiry,
            )
            .order_by(FoBhavcopy.expiry_date.asc())
            .limit(_FUT_FALLBACK_DEPTH)
        )
    ).all()
    row = next((r for r in candidates if r.close is not None and r.close > _ZERO), None)
    if row is None:
        return None
    # Spot is the same underlying for every contract, so prefer the NEAREST row
    # that carries it rather than whichever row happened to supply the price.
    spot = next((r.underlying_close for r in candidates if r.underlying_close is not None), None)

    if row.expiry_date == expiry:
        return ChainForward(
            price=row.close, source="fut_exact", trade_date=on_day, fut_expiry=expiry
        )

    if spot is None or spot <= _ZERO:
        return None
    t_fut = (row.expiry_date - on_day).days / 365.0
    t_opt = (expiry - on_day).days / 365.0
    if t_fut <= 0 or t_opt <= 0:
        return None

    carry = math.log(float(row.close) / float(spot)) / t_fut
    fwd = float(spot) * math.exp(carry * t_opt)
    if not math.isfinite(fwd) or fwd <= 0:
        return None
    return ChainForward(
        # float-tainted → build the Decimal from a string, never from the float.
        price=Decimal(str(fwd)).quantize(Decimal("0.0001")),
        source="fut_carry_implied",
        trade_date=on_day,
        fut_expiry=row.expiry_date,
    )


async def chain_day(
    db: AsyncSession,
    symbol: str,
    expiry: date,
    *,
    as_of: datetime | None = None,
    source: str = "eod",
) -> date | None:
    """The trading day the chain `load_chain` would return actually belongs to.

    Greeks need a time-to-expiry, and dating them off `today` would silently
    misprice a chain loaded on a Monday from Friday's close (and every holiday).
    Returns None when nothing is recorded.
    """
    if source == "intraday":
        stmt = select(OptionChainSnapshot.time).where(
            OptionChainSnapshot.symbol == symbol,
            OptionChainSnapshot.expiry_date == expiry,
            OptionChainSnapshot.option_type.in_(("CE", "PE")),
        )
        if as_of is not None:
            stmt = stmt.where(OptionChainSnapshot.time <= as_of)
        snap = (await db.execute(stmt.order_by(OptionChainSnapshot.time.desc()).limit(1))).scalar()
        # Snapshot times are stored UTC; the TRADING day is an IST calendar day.
        # `.date()` on the UTC instant lands a day early for anything after
        # 18:30 UTC (= 00:00 IST next day) — a whole day of error in dte.
        return snap.astimezone(_IST).date() if snap is not None else None
    if source == "eod":
        day_stmt = select(FoBhavcopy.trade_date).where(
            FoBhavcopy.symbol == symbol,
            FoBhavcopy.expiry_date == expiry,
            FoBhavcopy.instrument.in_(("CE", "PE")),
        )
        if as_of is not None:
            day_stmt = day_stmt.where(FoBhavcopy.trade_date <= as_of.date())
        return (
            await db.execute(day_stmt.order_by(FoBhavcopy.trade_date.desc()).limit(1))
        ).scalar()
    raise ValueError(f"unknown chain source: {source!r} (expected 'eod' | 'intraday')")


async def available_underlyings(
    db: AsyncSession, *, as_of: datetime | None = None
) -> tuple[date | None, list[str]]:
    """`(day, symbols)` — F&O underlyings with option rows on the most recent
    recorded day.

    Scoped to the latest day rather than all history so the picker offers what
    is currently tradeable (contracts get delisted) and stays index-fast
    instead of DISTINCT-scanning years of bhavcopy. The day is returned so
    callers can state what the list is as-of.
    """
    day_stmt = select(func.max(FoBhavcopy.trade_date)).where(
        FoBhavcopy.instrument.in_(("CE", "PE"))
    )
    if as_of is not None:
        day_stmt = day_stmt.where(FoBhavcopy.trade_date <= as_of.date())
    day = (await db.execute(day_stmt)).scalar()
    if day is None:
        return None, []
    rows = (
        await db.execute(
            select(FoBhavcopy.symbol)
            .where(FoBhavcopy.trade_date == day, FoBhavcopy.instrument.in_(("CE", "PE")))
            .distinct()
            .order_by(FoBhavcopy.symbol)
        )
    ).scalars()
    return day, list(rows)


async def available_expiries(
    db: AsyncSession, symbol: str, *, as_of: datetime | None = None
) -> tuple[date | None, list[date]]:
    """`(chain_day, expiries)` — expiries still open on the latest recorded day.

    Expiries strictly BEFORE that day are dropped: a settled contract has no
    tradeable chain, and offering one would produce a ladder with no Greeks
    (t <= 0). Ascending, so the nearest expiry is the natural default.
    """
    day_stmt = select(func.max(FoBhavcopy.trade_date)).where(
        FoBhavcopy.symbol == symbol, FoBhavcopy.instrument.in_(("CE", "PE"))
    )
    if as_of is not None:
        day_stmt = day_stmt.where(FoBhavcopy.trade_date <= as_of.date())
    day = (await db.execute(day_stmt)).scalar()
    if day is None:
        return None, []
    rows = (
        await db.execute(
            select(FoBhavcopy.expiry_date)
            .where(
                FoBhavcopy.symbol == symbol,
                FoBhavcopy.trade_date == day,
                FoBhavcopy.instrument.in_(("CE", "PE")),
                FoBhavcopy.expiry_date >= day,
            )
            .distinct()
            .order_by(FoBhavcopy.expiry_date)
        )
    ).scalars()
    return day, list(rows)


async def load_chain(
    db: AsyncSession,
    symbol: str,
    expiry: date,
    *,
    as_of: datetime | None = None,
    source: str = "eod",
) -> list[ChainRow]:
    """Load the option chain (CE+PE legs) for one underlying + expiry.

    source="eod": the latest `fo_bhavcopy` trading day at or before `as_of`.
    source="intraday": the latest `option_chain_snapshots` timestamp at or
    before `as_of`. Returns [] when nothing has been recorded.
    """
    if source == "intraday":
        return await _chain_from_snapshots(db, symbol, expiry, as_of)
    if source == "eod":
        return await _chain_from_bhavcopy(db, symbol, expiry, as_of)
    raise ValueError(f"unknown chain source: {source!r} (expected 'eod' | 'intraday')")


async def _chain_from_bhavcopy(
    db: AsyncSession, symbol: str, expiry: date, as_of: datetime | None
) -> list[ChainRow]:
    day_stmt = select(FoBhavcopy.trade_date).where(
        FoBhavcopy.symbol == symbol,
        FoBhavcopy.expiry_date == expiry,
        FoBhavcopy.instrument.in_(("CE", "PE")),
    )
    if as_of is not None:
        day_stmt = day_stmt.where(FoBhavcopy.trade_date <= as_of.date())
    day = (await db.execute(day_stmt.order_by(FoBhavcopy.trade_date.desc()).limit(1))).scalar()
    if day is None:
        return []

    rows = (
        await db.execute(
            select(
                FoBhavcopy.strike,
                FoBhavcopy.instrument,
                FoBhavcopy.open_interest,
                FoBhavcopy.volume_contracts,
                FoBhavcopy.close,
            ).where(
                FoBhavcopy.symbol == symbol,
                FoBhavcopy.expiry_date == expiry,
                FoBhavcopy.trade_date == day,
                FoBhavcopy.instrument.in_(("CE", "PE")),
            )
        )
    ).all()
    return [
        ChainRow(
            strike=r.strike,
            option_type=r.instrument,
            oi=r.open_interest or 0,
            volume=r.volume_contracts or 0,
            ltp=r.close,
        )
        for r in rows
    ]


async def _chain_from_snapshots(
    db: AsyncSession, symbol: str, expiry: date, as_of: datetime | None
) -> list[ChainRow]:
    time_stmt = select(OptionChainSnapshot.time).where(
        OptionChainSnapshot.symbol == symbol,
        OptionChainSnapshot.expiry_date == expiry,
        OptionChainSnapshot.option_type.in_(("CE", "PE")),
    )
    if as_of is not None:
        time_stmt = time_stmt.where(OptionChainSnapshot.time <= as_of)
    snap = (
        await db.execute(time_stmt.order_by(OptionChainSnapshot.time.desc()).limit(1))
    ).scalar()
    if snap is None:
        return []

    rows = (
        await db.execute(
            select(
                OptionChainSnapshot.strike,
                OptionChainSnapshot.option_type,
                OptionChainSnapshot.oi,
                OptionChainSnapshot.volume,
                OptionChainSnapshot.ltp,
            ).where(
                OptionChainSnapshot.symbol == symbol,
                OptionChainSnapshot.expiry_date == expiry,
                OptionChainSnapshot.time == snap,
                OptionChainSnapshot.option_type.in_(("CE", "PE")),
            )
        )
    ).all()
    return [
        ChainRow(
            strike=r.strike,
            option_type=r.option_type,
            oi=r.oi or 0,
            volume=r.volume or 0,
            ltp=r.ltp,
        )
        for r in rows
    ]


async def latest_spot(
    db: AsyncSession, symbol: str, expiry: date, *, as_of: datetime | None = None
) -> Decimal | None:
    """Underlying spot from the futures row's `underlying_close` (bhavcopy)."""
    stmt = select(FoBhavcopy.underlying_close).where(
        FoBhavcopy.symbol == symbol,
        FoBhavcopy.expiry_date == expiry,
        FoBhavcopy.instrument == "FUT",
    )
    if as_of is not None:
        stmt = stmt.where(FoBhavcopy.trade_date <= as_of.date())
    return (await db.execute(stmt.order_by(FoBhavcopy.trade_date.desc()).limit(1))).scalar()


async def futures_basis(
    db: AsyncSession, symbol: str, expiry: date, *, as_of: datetime | None = None
) -> Basis | None:
    """Futures basis = FUT close − underlying spot for one expiry, from the
    latest bhavcopy day at or before `as_of`. None if no FUT row or no spot."""
    stmt = select(
        FoBhavcopy.close, FoBhavcopy.underlying_close, FoBhavcopy.trade_date
    ).where(
        FoBhavcopy.symbol == symbol,
        FoBhavcopy.expiry_date == expiry,
        FoBhavcopy.instrument == "FUT",
    )
    if as_of is not None:
        stmt = stmt.where(FoBhavcopy.trade_date <= as_of.date())
    row = (await db.execute(stmt.order_by(FoBhavcopy.trade_date.desc()).limit(1))).first()
    if row is None or row.close is None or row.underlying_close is None:
        return None
    if row.underlying_close == 0:
        return None  # avoid division by zero in the percentage
    diff = row.close - row.underlying_close
    return Basis(
        fut_close=row.close,
        underlying_close=row.underlying_close,
        basis=diff,
        basis_pct=float(diff / row.underlying_close * 100),
    )


async def vix_regime(
    db: AsyncSession, *, as_of: datetime | None = None, lookback: int = 252
) -> VixRegime | None:
    """India VIX regime: the current close's percentile within the trailing
    `lookback` sessions, bucketed low (<25) / normal / high (>75). None if no
    VIX has been recorded."""
    stmt = select(IndiaVixDaily.close)
    if as_of is not None:
        stmt = stmt.where(IndiaVixDaily.trade_date <= as_of.date())
    closes = list(
        (await db.execute(stmt.order_by(IndiaVixDaily.trade_date.desc()).limit(lookback))).scalars()
    )
    if not closes:
        return None
    current = closes[0]
    below = sum(1 for c in closes if c < current)
    percentile = below / len(closes) * 100
    band = "low" if percentile < 25 else ("high" if percentile > 75 else "normal")
    return VixRegime(current=current, percentile=percentile, band=band, sample=len(closes))


# ── Implied-vol rank (Black-76 on the front-month future) ───────────────────────
#
# IV itself needs Black-Scholes, which is Rust-only (engine-core/options.rs via
# `tradecore`). Here we assemble the per-day ATM inputs from bhavcopy and invert
# them in ONE batched FFI call, then rank the latest against the window. Using
# the FUTURE as the underlying (carry=0, Black-76) keeps it dividend-free.

_DEFAULT_RATE = 0.065  # continuously-compounded proxy; IV is weakly rate-sensitive


async def _front_month_days(
    db: AsyncSession, symbol: str, *, as_of: date | None, lookback: int
) -> list[tuple[date, date]]:
    """(trade_date, front-month expiry) for the latest `lookback` futures trading
    days at or before `as_of`. Front month = nearest expiry ≥ the trade date."""
    stmt = select(FoBhavcopy.trade_date, func.min(FoBhavcopy.expiry_date)).where(
        FoBhavcopy.symbol == symbol,
        FoBhavcopy.instrument == "FUT",
        FoBhavcopy.expiry_date >= FoBhavcopy.trade_date,
    )
    if as_of is not None:
        stmt = stmt.where(FoBhavcopy.trade_date <= as_of)
    stmt = (
        stmt.group_by(FoBhavcopy.trade_date)
        .order_by(FoBhavcopy.trade_date.desc())
        .limit(lookback)
    )
    rows = (await db.execute(stmt)).all()
    return [(r[0], r[1]) for r in reversed(rows)]  # ascending by date


async def _atm_iv_by_day(
    db: AsyncSession, symbol: str, pairs: list[tuple[date, date]], *, rate: float
) -> dict[date, float]:
    """Invert the ATM front-month call to an implied vol for each (day, expiry).
    Three queries + one batched `tradecore.implied_vol` call. Days lacking a
    future close, an ATM call, or positive time-to-expiry drop out."""
    if not pairs:
        return {}
    front = dict(pairs)
    days = [d for d, _ in pairs]
    exps = list({e for _, e in pairs})

    fut_rows = (
        await db.execute(
            select(FoBhavcopy.trade_date, FoBhavcopy.expiry_date, FoBhavcopy.close).where(
                FoBhavcopy.symbol == symbol,
                FoBhavcopy.instrument == "FUT",
                FoBhavcopy.trade_date.in_(days),
                FoBhavcopy.expiry_date.in_(exps),
            )
        )
    ).all()
    fut = {(r.trade_date, r.expiry_date): r.close for r in fut_rows if r.close is not None}

    ce_rows = (
        await db.execute(
            select(
                FoBhavcopy.trade_date,
                FoBhavcopy.expiry_date,
                FoBhavcopy.strike,
                FoBhavcopy.close,
            ).where(
                FoBhavcopy.symbol == symbol,
                FoBhavcopy.instrument == "CE",
                FoBhavcopy.trade_date.in_(days),
                FoBhavcopy.expiry_date.in_(exps),
            )
        )
    ).all()
    ce: dict[tuple[date, date], list[tuple[Decimal, Decimal]]] = {}
    for r in ce_rows:
        if r.close is not None:
            ce.setdefault((r.trade_date, r.expiry_date), []).append((r.strike, r.close))

    ordered_days: list[date] = []
    inputs: list[tuple[float, float, float, float, float, float]] = []
    for d in days:
        exp = front[d]
        fwd = fut.get((d, exp))
        legs = ce.get((d, exp))
        if fwd is None or not legs:
            continue
        t = (exp - d).days / 365.0
        if t <= 0:
            continue
        strike, ce_close = min(legs, key=lambda sc: (abs(sc[0] - fwd), sc[0]))  # ATM (tie → lower)
        inputs.append((float(ce_close), float(fwd), float(strike), t, rate, 0.0))
        ordered_days.append(d)

    if not inputs:
        return {}
    import tradecore  # deferred: parity-gated wheel (idiom: signal_service, walkforward)

    ivs = tradecore.implied_vol("call", inputs)
    return {d: iv for d, iv in zip(ordered_days, ivs, strict=True) if iv is not None}


async def iv_rank(
    db: AsyncSession,
    symbol: str,
    *,
    rate: float = _DEFAULT_RATE,
    lookback: int = 252,
    as_of: date | None = None,
) -> IvRank | None:
    """ATM front-month IV rank/percentile over the trailing `lookback` futures
    sessions. `None` when no day in the window yields a computable IV."""
    pairs = await _front_month_days(db, symbol, as_of=as_of, lookback=lookback)
    series = await _atm_iv_by_day(db, symbol, pairs, rate=rate)
    if not series:
        return None
    as_of_day = max(series)
    current = series[as_of_day]
    vals = list(series.values())
    lo, hi = min(vals), max(vals)
    rank = 0.0 if hi == lo else (current - lo) / (hi - lo) * 100.0
    below = sum(1 for v in vals if v < current)
    percentile = below / len(vals) * 100.0
    return IvRank(
        as_of=as_of_day,
        current_iv=current,
        rank=rank,
        percentile=percentile,
        min_iv=lo,
        max_iv=hi,
        sample=len(vals),
    )
