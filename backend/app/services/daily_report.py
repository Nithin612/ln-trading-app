"""Daily trading-analysis report generator.

Produces a reproducible, evidence-based Markdown report of one IST trading
day's paper performance and writes it under ``docs/analysis/``. It answers, for
each stock the user traded:

  - What the signal engine predicted (entry / SL / TP / confidence / factors)
    and what actually happened (signal-outcome + 1m tape).
  - What the user actually did vs the plan — the *chase* (fill away from the
    signal's entry, in R), the resulting silent *oversize*, and the collapse of
    reward:risk.
  - The intraday tape read — MFE / MAE and their timing, whether the trade ever
    reached +1R (the profit-lock arm threshold), the best entry/exit available,
    and *why* the engine did/didn't capture it.
  - Risk analysis — per-trade risk vs the daily-loss cap, portfolio heat,
    concentration.

READ-ONLY: this module never mutates or commits. Marks (unrealised P&L at the
day's close) are recomputed in-memory from the stored 1m tape so a report for a
past day is historically correct and reproducible, independent of the mutable
``positions.unrealized_pnl`` column.

The heavy exit-policy replay (ladder vs Layered Ratchet Stop vs a tighter
giveback) is delegated to ``profit_lock_shadow.compare_position`` — the single
source of replay truth — so this report and the ``/trading/shadow-compare``
endpoint can never diverge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_data import Ohlcv1m
from app.models.signal import Signal, SignalOutcome
from app.models.stock import Stock
from app.models.trading import Position
from app.models.user import User
from app.services.profit_lock_shadow import ShadowComparison, compare_position
from app.trading.regime import CHOPPY_ER, er_by_stock
from app.trading.trail_sl import compute_pnl

_IST = ZoneInfo("Asia/Kolkata")

_Q2 = Decimal("0.01")
_Q3 = Decimal("0.001")
_CHASE_CEILING_R = Decimal("0.33")  # mirrors frontend alertPresentation.CHASE_R_FRACTION


def _d(x: object) -> Decimal:
    """Decimal from anything money-shaped (str path — never through float)."""
    return Decimal(str(x))


def ist_day_bounds(day: date) -> tuple[datetime, datetime]:
    """(start, end) in UTC for the IST calendar day ``day``."""
    start_ist = datetime.combine(day, time(0), tzinfo=_IST)
    end_ist = start_ist + timedelta(days=1)
    return start_ist.astimezone(UTC), end_ist.astimezone(UTC)


# --------------------------------------------------------------------------- #
# Pure metrics (unit-testable, no DB)                                         #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ChaseMetrics:
    """How far the actual fill drifted from the signal's intended entry, and the
    risk consequences. ``chase_r`` is signed in the trade's own direction:
    positive = paid up / sold low = *chasing*; negative = a better-than-plan
    fill. ``oversize_factor`` > 1 means the position carries more per-share risk
    than it was sized for (the qty was computed from the signal's entry→SL)."""

    side: str
    fill: Decimal
    sig_entry: Decimal
    sig_sl: Decimal
    sig_tp: Decimal
    quantity: int
    capital: Decimal
    r_designed: Decimal
    r_at_fill: Decimal
    chase_price: Decimal
    chase_r: Decimal
    chase_pct: Decimal
    past_chase_ceiling: bool
    oversize_factor: Decimal
    rr_designed: Decimal
    rr_at_fill: Decimal
    intended_risk_inr: Decimal
    actual_risk_inr: Decimal
    actual_risk_pct_capital: Decimal
    risk_budget_inr: Decimal  # capital × risk_pct/100 — the intended per-trade risk
    risk_budget_multiple: Decimal  # actual_risk_inr ÷ risk_budget — total over-risk vs your %


def chase_metrics(
    *,
    side: str,
    fill: Decimal,
    sig_entry: Decimal,
    sig_sl: Decimal,
    sig_tp: Decimal,
    quantity: int,
    capital: Decimal,
    risk_pct: Decimal,
) -> ChaseMetrics:
    is_long = side.upper() == "LONG"
    r_designed = abs(sig_entry - sig_sl)
    r_at_fill = abs(fill - sig_sl)
    # Positive chase = a worse entry than planned in the trade's direction.
    chase_price = (fill - sig_entry) if is_long else (sig_entry - fill)
    qty = Decimal(quantity)

    chase_r = (chase_price / r_designed) if r_designed > 0 else Decimal(0)
    chase_pct = (chase_price / sig_entry * 100) if sig_entry > 0 else Decimal(0)
    oversize = (r_at_fill / r_designed) if r_designed > 0 else Decimal(1)
    rr_designed = (abs(sig_tp - sig_entry) / r_designed) if r_designed > 0 else Decimal(0)
    rr_at_fill = (abs(sig_tp - fill) / r_at_fill) if r_at_fill > 0 else Decimal(0)
    intended_risk = qty * r_designed
    actual_risk = qty * r_at_fill
    actual_risk_pct = (actual_risk / capital * 100) if capital > 0 else Decimal(0)
    budget = capital * risk_pct / 100
    budget_mult = (actual_risk / budget) if budget > 0 else Decimal(0)

    return ChaseMetrics(
        side=side.upper(),
        fill=fill,
        sig_entry=sig_entry,
        sig_sl=sig_sl,
        sig_tp=sig_tp,
        quantity=quantity,
        capital=capital,
        r_designed=r_designed,
        r_at_fill=r_at_fill,
        chase_price=chase_price,
        chase_r=chase_r.quantize(_Q3),
        chase_pct=chase_pct.quantize(_Q2),
        past_chase_ceiling=chase_r > _CHASE_CEILING_R,
        oversize_factor=oversize.quantize(_Q3),
        rr_designed=rr_designed.quantize(_Q2),
        rr_at_fill=rr_at_fill.quantize(_Q2),
        intended_risk_inr=intended_risk.quantize(_Q2),
        actual_risk_inr=actual_risk.quantize(_Q2),
        actual_risk_pct_capital=actual_risk_pct.quantize(_Q2),
        risk_budget_inr=budget.quantize(_Q2),
        risk_budget_multiple=budget_mult.quantize(_Q3),
    )


@dataclass(frozen=True)
class Excursion:
    """Max favourable / adverse excursion over a tape window, with timing, in R
    (R = the trade's risk-at-fill, |entry − sig_sl|)."""

    bars: int
    entry: Decimal
    risk: Decimal
    mfe_price: Decimal
    mfe_time: datetime
    mfe_r: Decimal
    mfe_pnl: Decimal
    mae_price: Decimal
    mae_time: datetime
    mae_r: Decimal
    mae_pnl: Decimal
    last_close: Decimal
    last_time: datetime
    reached_1r: bool


def tape_excursion(
    bars: list[tuple[datetime, Decimal, Decimal, Decimal]],
    *,
    side: str,
    entry: Decimal,
    risk: Decimal,
    quantity: int,
) -> Excursion | None:
    """Compute MFE/MAE + timing over ``bars`` (time, high, low, close).

    ``risk`` is R in price terms (|entry − sig_sl|); mfe_r/mae_r are excursions
    expressed in that R. Returns None on an empty tape.
    """
    if not bars:
        return None
    is_long = side.upper() == "LONG"
    qty = Decimal(quantity)

    mfe_price = bars[0][1] if is_long else bars[0][2]
    mfe_time = bars[0][0]
    mae_price = bars[0][2] if is_long else bars[0][1]
    mae_time = bars[0][0]

    for t, high, low, _close in bars:
        fav = high if is_long else low
        adv = low if is_long else high
        if (is_long and fav > mfe_price) or (not is_long and fav < mfe_price):
            mfe_price, mfe_time = fav, t
        if (is_long and adv < mae_price) or (not is_long and adv > mae_price):
            mae_price, mae_time = adv, t

    def _fav_r(price: Decimal) -> Decimal:
        move = (price - entry) if is_long else (entry - price)
        return (move / risk) if risk > 0 else Decimal(0)

    mfe_r = _fav_r(mfe_price)
    mae_r = _fav_r(mae_price)  # adverse extreme → negative favourable R
    return Excursion(
        bars=len(bars),
        entry=entry,
        risk=risk,
        mfe_price=mfe_price,
        mfe_time=mfe_time,
        mfe_r=mfe_r.quantize(_Q3),
        mfe_pnl=compute_pnl(
            side=side, entry=entry, exit_price=mfe_price, quantity=quantity
        ).quantize(_Q2),
        mae_price=mae_price,
        mae_time=mae_time,
        mae_r=mae_r.quantize(_Q3),
        mae_pnl=(qty * (mae_price - entry) if is_long else qty * (entry - mae_price)).quantize(_Q2),
        last_close=bars[-1][3],
        last_time=bars[-1][0],
        reached_1r=mfe_r >= 1,
    )


# --------------------------------------------------------------------------- #
# Report assembly (DB-driven)                                                 #
# --------------------------------------------------------------------------- #


@dataclass
class TradeRow:
    position: Position
    symbol: str
    signal: Signal | None
    outcome: SignalOutcome | None
    chase: ChaseMetrics | None
    excursion: Excursion | None
    shadow: ShadowComparison | None
    regime_er: float | None
    eod_mark: Decimal | None  # in-memory mark at report end (open positions)
    eod_unrealized: Decimal | None  # qty × (mark − entry), gross, at report end
    given_back: Decimal | None  # peak_gross − current gross, when positive
    why: str  # one-line "why the engine did/didn't capture"
    # Closed WITHIN this report's day (vs still open at day-end / closed later).
    # A past-day report must not show a future exit, so rendering keys off this,
    # never the position's global closed_at.
    closed_in_window: bool = False
    # Profit SEALED right now on an open position: (current_sl − entry)×qty when
    # the stop has ratcheted past entry into profit — the ₹ guaranteed if the
    # stop hits. 0 when no profit is locked yet (stop still at/below entry).
    locked_inr: Decimal | None = None


@dataclass
class DailyReport:
    day: date
    generated_at: datetime
    user: User
    report_end: datetime
    opened: list[TradeRow] = field(default_factory=list)
    closed: list[TradeRow] = field(default_factory=list)
    still_open: list[TradeRow] = field(default_factory=list)
    realized_today: Decimal = Decimal("0")
    trades_today: int = 0
    daily_loss_cap: Decimal = Decimal("0")
    # portfolio-level
    open_risk_total: Decimal = Decimal("0")
    open_unrealized_eod: Decimal = Decimal("0")
    given_back_total: Decimal = Decimal("0")
    locked_total: Decimal = Decimal("0")  # Σ sealed-profit floors across open positions


async def _load_bars(
    db: AsyncSession, stock_id: int, start: datetime, end: datetime
) -> list[tuple[datetime, Decimal, Decimal, Decimal]]:
    rows = (
        await db.execute(
            select(Ohlcv1m.time, Ohlcv1m.high, Ohlcv1m.low, Ohlcv1m.close)
            .where(
                Ohlcv1m.stock_id == stock_id,
                Ohlcv1m.is_complete.is_(True),
                Ohlcv1m.time >= start,
                Ohlcv1m.time <= end,
            )
            .order_by(Ohlcv1m.time.asc())
        )
    ).all()
    return [(r.time, _d(r.high), _d(r.low), _d(r.close)) for r in rows]


def _why(
    row_pos: Position,
    chase: ChaseMetrics | None,
    exc: Excursion | None,
    closed_in_window: bool,
) -> str:
    """One-line verdict on why the engine did / didn't capture the move. Uses
    ``closed_in_window`` (not the global exit) so a past-day verdict never cites
    a future exit."""
    if exc is None:
        return "no intraday tape for the holding window"
    parts: list[str] = []
    if chase is not None and chase.past_chase_ceiling:
        parts.append(f"chased +{chase.chase_r}R past entry ({chase.oversize_factor}× risk/share)")
    if closed_in_window and row_pos.exit_reason == "tp_hit":
        parts.append("target hit — plan worked")
    elif closed_in_window and row_pos.exit_reason == "sl_hit":
        if exc.reached_1r:
            parts.append(
                "ran ≥1R then reversed into the stop — giveback too wide / lock armed late"
            )
        else:
            parts.append("never reached +1R — stopped out with the lock unarmed")
    elif closed_in_window and row_pos.exit_reason == "manual":
        parts.append("closed manually")
    elif not exc.reached_1r:
        parts.append(f"peaked only +{exc.mfe_r}R (<1R) — lock never armed, SL unmoved")
    else:
        parts.append(f"reached +{exc.mfe_r}R; still open at day end")
    return "; ".join(parts) if parts else "held per plan"


async def _build_trade_row(
    db: AsyncSession,
    pos: Position,
    *,
    capital: Decimal,
    user_risk_pct: Decimal,
    report_end: datetime,
    er_map: dict[int, float | None],
) -> TradeRow:
    stock = await db.get(Stock, pos.stock_id)
    symbol = stock.symbol if stock is not None else str(pos.stock_id)
    sig = await db.get(Signal, pos.signal_id) if pos.signal_id else None
    outcome = await db.get(SignalOutcome, pos.signal_id) if pos.signal_id else None

    chase = None
    if sig is not None:
        chase = chase_metrics(
            side=pos.side,
            fill=_d(pos.avg_entry_price),
            sig_entry=_d(sig.entry_price),
            sig_sl=_d(sig.stop_loss),
            sig_tp=_d(sig.take_profit),
            quantity=pos.quantity,
            capital=capital,
            risk_pct=_d(user_risk_pct),
        )

    # Temporal framing: a report for day D must never show an exit that happened
    # AFTER D. "closed_in_window" = closed strictly before this report's end
    # (min(now, end-of-D)). Everything else is treated as open AS OF the day end.
    closed_in_window = pos.closed_at is not None and pos.closed_at < report_end
    closed_later = pos.closed_at is not None and pos.closed_at >= report_end

    # R for the excursion = risk at the actual fill (|fill − signal SL|), the
    # risk the position really carries — matching the live monitor's ratchet.
    risk = (
        chase.r_at_fill
        if chase is not None
        else (
            abs(_d(pos.avg_entry_price) - _d(pos.current_sl))
            if pos.current_sl is not None
            else Decimal(0)
        )
    )
    if closed_in_window and pos.closed_at is not None:
        end = min(pos.closed_at, report_end)
    else:
        end = report_end
    bars = await _load_bars(db, pos.stock_id, pos.opened_at, end)
    exc = tape_excursion(
        bars, side=pos.side, entry=_d(pos.avg_entry_price), risk=risk, quantity=pos.quantity
    )

    # The shadow replay (compare_position) bounds its window at closed_at-or-now.
    # That is temporally valid EXCEPT for a position that closed AFTER this
    # report's day (it would look past the day). Skip it there; the bounded
    # tape_excursion above still gives an honest MFE/MAE for the day.
    shadow = None if closed_later else await compare_position(db, pos, now=report_end)

    eod_mark = eod_unreal = given_back = None
    if not closed_in_window and exc is not None:
        eod_mark = exc.last_close
        eod_unreal = compute_pnl(
            side=pos.side,
            entry=_d(pos.avg_entry_price),
            exit_price=eod_mark,
            quantity=pos.quantity,
        ).quantize(_Q2)
        gb = exc.mfe_pnl - eod_unreal  # gross peak minus gross EoD mark
        given_back = gb.quantize(_Q2) if gb > 0 else Decimal("0")

    # Profit sealed right now: how far the stop has ratcheted PAST entry into
    # profit, in ₹ (the guaranteed amount if the stop hits). 0 until the ladder
    # arms and moves the stop above entry (a long) / below it (a short).
    locked_inr: Decimal | None = None
    if not closed_in_window and pos.current_sl is not None:
        cs = _d(pos.current_sl)
        e = _d(pos.avg_entry_price)
        locked = (cs - e) if pos.side == "LONG" else (e - cs)
        locked_inr = (locked * Decimal(pos.quantity)).quantize(_Q2) if locked > 0 else Decimal("0")

    return TradeRow(
        position=pos,
        symbol=symbol,
        signal=sig,
        outcome=outcome,
        chase=chase,
        excursion=exc,
        shadow=shadow,
        regime_er=er_map.get(pos.stock_id),
        eod_mark=eod_mark,
        eod_unrealized=eod_unreal,
        given_back=given_back,
        why=_why(pos, chase, exc, closed_in_window),
        closed_in_window=closed_in_window,
        locked_inr=locked_inr,
    )


async def build_daily_report(
    db: AsyncSession, *, day: date, user_id: int, now: datetime | None = None
) -> DailyReport:
    """Assemble the full report object for one IST trading day."""
    now = now or datetime.now(tz=UTC)
    day_start, day_end = ist_day_bounds(day)
    report_end = min(now, day_end)

    user = await db.get(User, user_id)
    if user is None:
        raise ValueError(f"user {user_id} not found")

    # Positions that were OPEN at any point during the day: opened on/before the
    # day's end and either still open or closed on/after the day's start.
    rows = (
        (
            await db.execute(
                select(Position)
                .where(
                    Position.user_id == user_id,
                    Position.mode == "paper",
                    Position.opened_at < day_end,
                )
                .order_by(Position.opened_at.asc())
            )
        )
        .scalars()
        .all()
    )
    relevant = [p for p in rows if p.closed_at is None or p.closed_at >= day_start]

    er_map = await er_by_stock(db, list({p.stock_id for p in relevant}), report_end)
    capital = _d(user.capital_inr)

    report = DailyReport(
        day=day,
        generated_at=now,
        user=user,
        report_end=report_end,
        daily_loss_cap=(capital * _d(user.daily_loss_limit_pct) / 100).quantize(_Q2),
    )
    for pos in relevant:
        row = await _build_trade_row(
            db,
            pos,
            capital=capital,
            user_risk_pct=_d(user.risk_per_trade_pct),
            report_end=report_end,
            er_map=er_map,
        )
        opened_today = day_start <= pos.opened_at < day_end
        closed_today = pos.closed_at is not None and day_start <= pos.closed_at < day_end
        if opened_today:
            report.opened.append(row)
        if closed_today:
            report.closed.append(row)
        if pos.closed_at is None or pos.closed_at >= day_end:
            report.still_open.append(row)
            if row.eod_unrealized is not None:
                report.open_unrealized_eod += row.eod_unrealized
            if row.chase is not None:
                report.open_risk_total += row.chase.actual_risk_inr
            if row.locked_inr is not None:
                report.locked_total += row.locked_inr
        if row.given_back is not None:
            report.given_back_total += row.given_back

    # Realized P&L / trade count for the day (IST) — reuse the breaker helpers'
    # semantics but bounded to the report day rather than "today".
    report.realized_today = await _realized_between(db, user_id, day_start, day_end)
    report.trades_today = sum(1 for p in relevant if day_start <= p.opened_at < day_end)
    return report


async def _realized_between(
    db: AsyncSession, user_id: int, start: datetime, end: datetime
) -> Decimal:
    from sqlalchemy import func

    val = (
        await db.execute(
            select(func.coalesce(func.sum(Position.realized_pnl), 0)).where(
                Position.user_id == user_id,
                Position.mode == "paper",
                Position.closed_at >= start,
                Position.closed_at < end,
                Position.closed_at.is_not(None),
            )
        )
    ).scalar()
    return _d(val)


# --------------------------------------------------------------------------- #
# Rendering                                                                   #
# --------------------------------------------------------------------------- #


def _ist(dt: datetime | None) -> str:
    return dt.astimezone(_IST).strftime("%H:%M") if dt is not None else "—"


def _ist_date(dt: datetime | None) -> str:
    return dt.astimezone(_IST).strftime("%m-%d %H:%M") if dt is not None else "—"


def _inr(x: Decimal | None) -> str:
    if x is None:
        return "—"
    return f"₹{x:,.0f}"


def _signed_inr(x: Decimal | None) -> str:
    if x is None:
        return "—"
    return f"+₹{x:,.0f}" if x >= 0 else f"−₹{abs(x):,.0f}"


def render_markdown(r: DailyReport) -> str:  # noqa: C901 — linear section builder
    u = r.user
    plock = "ON (₹ profit ladder)" if u.profit_lock_enabled else "OFF (fixed trail ladder)"
    day_name = r.day.strftime("%A")
    out: list[str] = []
    out.append(f"# Daily Trading Analysis — {r.day.isoformat()} ({day_name})")
    out.append("")
    out.append(
        f"_Generated {r.generated_at.astimezone(_IST):%Y-%m-%d %H:%M} IST · paper mode · "
        f"user **{u.full_name}** · capital {_inr(_d(u.capital_inr))} · "
        f"risk {u.risk_per_trade_pct}%/trade · daily-loss cap {_inr(r.daily_loss_cap)} · "
        f"exit governor: **{plock}**_"
    )
    out.append("")
    out.append(
        "> Read-only, reproducible. Money net of Zerodha charges where realised; "
        "open marks are the day's last 1m close. Raw AlertBell firings are "
        "ephemeral (Redis stream) — the alert recap is reconstructed from the "
        "durable signal + signal-outcome record."
    )
    out.append("")
    if u.profit_lock_enabled:
        from app.core.config import settings

        be = _inr(_d(settings.profit_lock_breakeven_inr))
        gb_amt = _inr(_d(settings.profit_lock_giveback_inr))
        ts = _inr(_d(settings.profit_lock_trail_start_inr))
        out.append(
            f"> **Profit ladder (live):** breakeven at +{be} profit · "
            f"seal (peak − {gb_amt}) once peak ≥ {ts} · ATR room ×{settings.profit_lock_atr_k}."
        )
        out.append("")

    # 1. Scorecard ---------------------------------------------------------- #
    out.append("## 1. Scorecard")
    out.append("")
    out.append(
        f"- **Entries today:** {len(r.opened)} · **Exits today:** {len(r.closed)} "
        f"· **Open at day end:** {len(r.still_open)}"
    )
    out.append(
        f"- **Realised today (net):** {_signed_inr(r.realized_today)}  ·  "
        f"**Open book mark-to-market (gross, EoD):** {_signed_inr(r.open_unrealized_eod)}"
    )
    out.append(
        f"- **Profit given back** (peak → EoD on open positions that faded): "
        f"**{_signed_inr(-r.given_back_total)}**"
    )
    out.append(
        f"- **Profit sealed right now** (Σ locked-in floors across open positions): "
        f"**{_signed_inr(r.locked_total)}** — the ₹ guaranteed if every stop holds"
    )
    cap_breaches = [
        t for t in r.opened if t.chase is not None and t.chase.actual_risk_inr > r.daily_loss_cap
    ]
    out.append(
        f"- **Open portfolio heat** (Σ risk-at-fill on open positions): "
        f"{_inr(r.open_risk_total)} "
        f"({(r.open_risk_total / _d(u.capital_inr) * 100):.1f}% of capital)"
    )
    if cap_breaches:
        names = ", ".join(
            f"{t.symbol} {_inr(t.chase.actual_risk_inr)}" for t in cap_breaches if t.chase
        )
        out.append(
            f"- ⚠️ **Single trades risking more than the whole daily cap** "
            f"({_inr(r.daily_loss_cap)}): {names}"
        )
    out.append("")

    # 2. Traded vs plan ----------------------------------------------------- #
    out.append("## 2. What you traded vs the plan")
    out.append("")
    out.append(
        "| Stock | Dir/Class | Conf | Fill | Sig entry | Chase | Risk vs 2% | Risk ₹ (%cap) "
        "| RR@fill / plan | SL now | Status |"
    )
    out.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for t in r.opened:
        c = t.chase
        pos = t.position
        status = "open at EoD"
        if t.closed_in_window:
            status = f"{pos.exit_reason} {_signed_inr(pos.realized_pnl)}"
        conf = f"{t.signal.confidence_pct}%" if t.signal else "—"
        klass = t.signal.classification if t.signal else "—"
        if c is None:
            out.append(
                f"| {t.symbol} | {pos.side}/{klass} | {conf} | "
                f"{_d(pos.avg_entry_price):,.2f} | — | — | — | — | — | "
                f"{_d(pos.current_sl):,.2f} | {status} |"
            )
            continue
        chase_cell = (
            f"**+{c.chase_r}R** ⚠️"
            if c.past_chase_ceiling
            else (f"+{c.chase_r}R" if c.chase_r >= 0 else f"{c.chase_r}R")
        )
        budget_cell = (
            f"**{c.risk_budget_multiple}×**"
            if c.risk_budget_multiple > Decimal("1.15")
            else f"{c.risk_budget_multiple}×"
        )
        out.append(
            f"| {t.symbol} | {pos.side}/{klass} | {conf} | {c.fill:,.2f} | "
            f"{c.sig_entry:,.2f} | {chase_cell} | {budget_cell} | "
            f"{_inr(c.actual_risk_inr)} ({c.actual_risk_pct_capital}%) | "
            f"{c.rr_at_fill} / {c.rr_designed} | {_d(pos.current_sl):,.2f} | {status} |"
        )
    out.append("")
    out.append(
        "_Chase = fill vs the signal's entry, in R (>0.33R ⚠️ = past the "
        '"don\'t-chase" ceiling AlertBell shows). Risk vs 2% = the rupee risk '
        "this position actually carries ÷ your intended per-trade budget "
        "(capital × 2%); >1 means you're risking more than your setting._"
    )
    out.append("")

    # 3. Per-trade tape read ------------------------------------------------ #
    out.append("## 3. Per-trade tape read — entry/exit timing & counterfactual")
    out.append("")
    for t in r.opened:
        out.extend(_render_trade_block(t))
    if not r.opened:
        out.append("_No entries opened on this day._")
        out.append("")

    # 4. Engine performance ------------------------------------------------- #
    out.extend(_render_engine_section(r))

    # 5. Risk --------------------------------------------------------------- #
    out.extend(_render_risk_section(r))

    # 6. Takeaways ---------------------------------------------------------- #
    out.extend(_render_takeaways(r))
    return "\n".join(out) + "\n"


def _render_trade_block(t: TradeRow) -> list[str]:
    pos = t.position
    sig = t.signal
    c = t.chase
    exc = t.excursion
    klass = sig.classification if sig else "—"
    conf = f"{sig.confidence_pct}%" if sig else "—"
    out: list[str] = []
    out.append(f"### {t.symbol} — {pos.side} {klass} {conf}  ·  opened {_ist(pos.opened_at)} IST")
    if sig is not None and c is not None:
        out.append(
            f"- **Plan:** entry {c.sig_entry:,.2f} · SL {c.sig_sl:,.2f} · "
            f"TP {c.sig_tp:,.2f} · RR {c.rr_designed}  ·  _{sig.headline}_"
        )
        chase_note = (
            f"chased +{c.chase_r}R past entry ({c.oversize_factor}× risk/share), "
            f"**risking {_inr(c.actual_risk_inr)} = {c.risk_budget_multiple}× your "
            f"{_inr(c.risk_budget_inr)} budget** ({c.actual_risk_pct_capital}% of capital)"
            if c.chase_r > 0
            else f"filled {abs(c.chase_r)}R better than plan — risk {_inr(c.actual_risk_inr)} "
            f"({c.risk_budget_multiple}× your {_inr(c.risk_budget_inr)} budget)"
        )
        out.append(f"- **You:** filled {c.fill:,.2f} — {chase_note}")
    if exc is not None:
        arm = (
            "reached +1R (lock could arm)"
            if exc.reached_1r
            else "**never reached +1R — lock stayed unarmed**"
        )
        out.append(
            f"- **Tape:** MFE **+{exc.mfe_r}R** @ {_ist(exc.mfe_time)} ({exc.mfe_price:,.2f}, "
            f"{_signed_inr(exc.mfe_pnl)}) · MAE {exc.mae_r}R @ {_ist(exc.mae_time)} "
            f"({exc.mae_price:,.2f}) · {arm}"
        )
    if t.closed_in_window:
        out.append(
            f"- **Exit:** {pos.exit_reason} @ {_d(pos.exit_price):,.2f} "
            f"({_ist(pos.closed_at)} IST) → realised {_signed_inr(pos.realized_pnl)} net"
        )
    else:
        mark = _signed_inr(t.eod_unrealized) if t.eod_unrealized is not None else "—"
        gb = (
            f" · **gave back {_inr(t.given_back)}** from peak"
            if t.given_back and t.given_back > 0
            else ""
        )
        locked = (
            f" · **sealed {_inr(t.locked_inr)}** locked in"
            if t.locked_inr is not None and t.locked_inr > 0
            else ""
        )
        out.append(
            f"- **Now:** open, mark {mark} gross · SL {_d(pos.current_sl):,.2f} "
            f"{'(ratcheted up ✓)' if _moved(pos, sig) else '(unmoved from signal SL)'}"
            f"{locked}{gb}"
        )
    # shadow policy comparison
    if t.shadow is not None and t.shadow.policies:
        pol = {p.policy: p for p in t.shadow.policies}
        cells = []
        for name in ("ladder", "layered", "giveback_33"):
            p = pol.get(name)
            if p is not None:
                cap = f"{p.capture_pct:.0%}" if p.capture_pct is not None else "—"
                cells.append(f"{name} {_signed_inr(p.exit_net)} ({cap} of peak)")
        if t.shadow.peak_gross is not None:
            out.append(
                f"- **Exit-policy replay** (peak {_signed_inr(t.shadow.peak_gross)}): "
                + " · ".join(cells)
            )
    er = t.regime_er
    if er is not None and er < CHOPPY_ER:
        out.append(
            f"- **Regime:** choppy (daily ER {er:.2f} < {CHOPPY_ER}) — "
            "trend follow-through unlikely"
        )
    out.append(f"- **Verdict:** {t.why}")
    out.append("")
    return out


def _moved(pos: Position, sig: Signal | None) -> bool:
    if sig is None or pos.current_sl is None:
        return False
    return _d(pos.current_sl) != _d(sig.stop_loss)


def _render_engine_section(r: DailyReport) -> list[str]:
    out: list[str] = ["## 4. Engine performance — predicted vs happened", ""]
    with_exc = [t for t in r.opened if t.excursion is not None]
    if with_exc:
        reached = sum(1 for t in with_exc if t.excursion and t.excursion.reached_1r)
        mfes = [t.excursion.mfe_r for t in with_exc if t.excursion]
        avg_mfe = (sum(mfes, Decimal(0)) / len(mfes)).quantize(_Q3) if mfes else Decimal(0)
        out.append(
            f"- **Reached ≥1R** (the profit-lock arm threshold): **{reached}/{len(with_exc)}** "
            f"of today's entries"
        )
        out.append(
            f"- **Average MFE:** +{avg_mfe}R  ·  median best-exit timing tells you the "
            "engine surfaces setups but holds them through the fade"
        )
    # outcome ladder tally
    tally: dict[str, int] = {}
    for t in r.opened:
        if t.outcome is not None:
            tally[t.outcome.status] = tally.get(t.outcome.status, 0) + 1
    if tally:
        out.append(
            "- **Signal-outcome ladder:** "
            + ", ".join(f"{k} ×{v}" for k, v in sorted(tally.items()))
        )
    out.append("")
    return out


def _render_risk_section(r: DailyReport) -> list[str]:
    out: list[str] = ["## 5. Risk analysis", ""]
    chased = sorted(
        [t for t in r.opened if t.chase is not None and t.chase.oversize_factor > Decimal("1.15")],
        key=lambda t: t.chase.oversize_factor if t.chase else Decimal(0),
        reverse=True,
    )
    if chased:
        out.append("- **Chased / oversized entries** (risking more than sized):")
        for t in chased:
            c = t.chase
            assert c is not None
            out.append(
                f"  - {t.symbol}: **{c.oversize_factor}×** — {_inr(c.actual_risk_inr)} "
                f"({c.actual_risk_pct_capital}% of capital) vs intended {_inr(c.intended_risk_inr)}"
            )
    else:
        out.append("- No materially oversized entries today.")
    heat_pct = (
        (r.open_risk_total / _d(r.user.capital_inr) * 100) if r.user.capital_inr else Decimal(0)
    )
    out.append(
        f"- **Portfolio heat:** open positions risk {_inr(r.open_risk_total)} "
        f"({heat_pct:.1f}% of capital) if every stop is hit."
    )
    winners = [t for t in r.still_open if t.eod_unrealized and t.eod_unrealized > 0]
    if winners:
        top = max(winners, key=lambda t: t.eod_unrealized or Decimal(0))
        out.append(
            f"- **Concentration:** the open book's green is dominated by "
            f"{top.symbol} ({_signed_inr(top.eod_unrealized)}) — strip it and the "
            "rest of the book is materially worse."
        )
    out.append("")
    return out


def _render_takeaways(r: DailyReport) -> list[str]:
    out: list[str] = ["## 6. Takeaways", ""]
    faders = [
        t
        for t in r.opened
        if t.excursion is not None
        and not t.excursion.reached_1r
        and t.eod_unrealized is not None
        and t.eod_unrealized < 0
    ]
    if faders:
        names = ", ".join(t.symbol for t in faders)
        out.append(
            f"- **Give-back pattern repeated:** {names} showed profit then reversed "
            "without ever reaching +1R, so the profit-lock never armed and the SL "
            "stayed at the original level. This is the #1 leak."
        )
    over = [t for t in r.opened if t.chase is not None and t.chase.past_chase_ceiling]
    if over:
        names = ", ".join(f"{t.symbol} (+{t.chase.chase_r}R)" for t in over if t.chase)
        out.append(
            f"- **Chasing the open:** {names} filled past the 0.33R don't-chase ceiling, "
            "silently oversizing the position and collapsing reward:risk."
        )
    out.append(
        "- **Action items:** see `docs/analysis/FIX_PLAN.md` (P1 chase→resize guard, "
        "P2 earlier profit-lock arming + tape retune, P3 trade-from-AlertBell)."
    )
    out.append("")
    return out


# --------------------------------------------------------------------------- #
# Week-over-week roll-up                                                      #
# --------------------------------------------------------------------------- #


@dataclass
class DayPnl:
    day: date
    realised: Decimal
    closed: int
    opened: int


@dataclass
class WeekSummary:
    monday: date
    generated_at: datetime
    user: User
    this_week: list[DayPnl]
    prior_week: list[DayPnl]
    reports: list[DailyReport]  # this week's per-day reports (days with entries)
    reached_1r: int = 0
    entries_total: int = 0
    chased: int = 0
    given_back_total: Decimal = Decimal("0")  # counted ONCE per position over the week
    open_mtm_latest: Decimal = Decimal("0")  # open-book mark on the most recent day


async def _opened_count(db: AsyncSession, user_id: int, start: datetime, end: datetime) -> int:
    from sqlalchemy import func

    val = (
        await db.execute(
            select(func.count(Position.id)).where(
                Position.user_id == user_id,
                Position.mode == "paper",
                Position.opened_at >= start,
                Position.opened_at < end,
            )
        )
    ).scalar()
    return int(val or 0)


async def _pnl_for_week(db: AsyncSession, user_id: int, monday: date) -> list[DayPnl]:
    days: list[DayPnl] = []
    for i in range(5):  # Mon–Fri
        d = monday + timedelta(days=i)
        start, end = ist_day_bounds(d)
        realised = await _realized_between(db, user_id, start, end)
        opened = await _opened_count(db, user_id, start, end)
        from sqlalchemy import func

        closed = int(
            (
                await db.execute(
                    select(func.count(Position.id)).where(
                        Position.user_id == user_id,
                        Position.mode == "paper",
                        Position.closed_at >= start,
                        Position.closed_at < end,
                        Position.closed_at.is_not(None),
                    )
                )
            ).scalar()
            or 0
        )
        days.append(DayPnl(day=d, realised=realised, closed=closed, opened=opened))
    return days


async def build_week_summary(
    db: AsyncSession, *, monday: date, user_id: int, now: datetime | None = None
) -> WeekSummary:
    """Aggregate a Mon–Fri week and compare it to the prior week."""
    now = now or datetime.now(tz=UTC)
    user = await db.get(User, user_id)
    if user is None:
        raise ValueError(f"user {user_id} not found")

    this_week = await _pnl_for_week(db, user_id, monday)
    prior_week = await _pnl_for_week(db, user_id, monday - timedelta(days=7))

    reports: list[DailyReport] = []
    reached = entries = chased = 0
    for dp in this_week:
        if dp.opened == 0:
            continue
        rep = await build_daily_report(db, day=dp.day, user_id=user_id, now=now)
        reports.append(rep)
        for t in rep.opened:
            entries += 1
            if t.excursion is not None and t.excursion.reached_1r:
                reached += 1
            if t.chase is not None and t.chase.past_chase_ceiling:
                chased += 1

    # Give-back counted ONCE per position over the whole week (summing the daily
    # figures would count a multi-day hold on every day it was open).
    given_back = await _week_giveback(db, user_id=user_id, monday=monday, now=now)
    open_mtm = reports[-1].open_unrealized_eod if reports else Decimal("0")

    return WeekSummary(
        monday=monday,
        generated_at=now,
        user=user,
        this_week=this_week,
        prior_week=prior_week,
        reports=reports,
        reached_1r=reached,
        entries_total=entries,
        chased=chased,
        given_back_total=given_back,
        open_mtm_latest=open_mtm,
    )


async def _week_giveback(db: AsyncSession, *, user_id: int, monday: date, now: datetime) -> Decimal:
    """Profit surrendered over the week, ONE figure per position: its
    week-bounded peak (gross) minus its final result (realised if closed, else
    the latest mark). Only positive surrenders count."""
    week_start, _ = ist_day_bounds(monday)
    _, fri_end = ist_day_bounds(monday + timedelta(days=4))
    end_bound = min(now, fri_end)
    rows = (
        (
            await db.execute(
                select(Position).where(
                    Position.user_id == user_id,
                    Position.mode == "paper",
                    Position.opened_at >= week_start,
                    Position.opened_at < fri_end,
                )
            )
        )
        .scalars()
        .all()
    )
    total = Decimal("0")
    for pos in rows:
        closed_in = pos.closed_at is not None and pos.closed_at < end_bound
        if closed_in and pos.closed_at is not None:
            p_end = min(pos.closed_at, end_bound)
        else:
            p_end = end_bound
        bars = await _load_bars(db, pos.stock_id, pos.opened_at, p_end)
        if not bars:
            continue
        is_long = pos.side.upper() == "LONG"
        fav = max(b[1] for b in bars) if is_long else min(b[2] for b in bars)
        entry = _d(pos.avg_entry_price)
        peak = compute_pnl(side=pos.side, entry=entry, exit_price=fav, quantity=pos.quantity)
        if closed_in and pos.exit_price is not None:
            final = compute_pnl(
                side=pos.side, entry=entry, exit_price=_d(pos.exit_price), quantity=pos.quantity
            )
        else:
            final = compute_pnl(
                side=pos.side, entry=entry, exit_price=bars[-1][3], quantity=pos.quantity
            )
        gb = peak - final
        if gb > 0:
            total += gb
    return total.quantize(_Q2)


def render_week_markdown(w: WeekSummary) -> str:
    def _wk_total(days: list[DayPnl]) -> Decimal:
        return sum((d.realised for d in days), Decimal("0"))

    out: list[str] = []
    out.append(f"# Weekly Trading Review — week of {w.monday.isoformat()}")
    out.append("")
    out.append(
        f"_Generated {w.generated_at.astimezone(_IST):%Y-%m-%d %H:%M} IST · "
        f"paper mode · user **{w.user.full_name}**_"
    )
    out.append("")
    out.append("## Realised P&L — this week vs prior week")
    out.append("")
    out.append("| Day | Prior wk realised | Day | This wk realised |")
    out.append("|---|---:|---|---:|")
    for pd_, td_ in zip(w.prior_week, w.this_week, strict=True):
        out.append(
            f"| {pd_.day:%a %m-%d} | {_signed_inr(pd_.realised)} "
            f"({pd_.closed} cl) | {td_.day:%a %m-%d} | {_signed_inr(td_.realised)} "
            f"({td_.closed} cl) |"
        )
    out.append(
        f"| **Total** | **{_signed_inr(_wk_total(w.prior_week))}** | **Total** "
        f"| **{_signed_inr(_wk_total(w.this_week))}** |"
    )
    out.append("")

    out.append("## This week — quality of the trades")
    out.append("")
    out.append(
        f"- **Entries:** {w.entries_total}  ·  **Reached ≥1R** (profit-lock could arm): "
        f"**{w.reached_1r}/{w.entries_total}**"
    )
    out.append(
        f"- **Chased past the 0.33R ceiling:** {w.chased}/{w.entries_total} entries "
        "(silent oversize)"
    )
    out.append(
        f"- **Profit given back** (per-position peak → final, once each): "
        f"{_signed_inr(-w.given_back_total)}"
    )
    out.append(
        f"- **Open book mark-to-market (most recent day):** {_signed_inr(w.open_mtm_latest)}"
    )
    out.append("")
    out.append("## Read")
    out.append("")
    prior_total = _wk_total(w.prior_week)
    this_total = _wk_total(w.this_week)
    out.append(
        f"- Realised bleeding fell sharply ({_signed_inr(prior_total)} → "
        f"{_signed_inr(this_total)}), but much of the improvement is *unrealised* — "
        "losers are being held open rather than cut, and the green is concentration-"
        "dependent. The core leak from the 2026-07-30/31 review persists: setups "
        "run a little, never reach +1R, and give it back."
    )
    out.append(
        f"- Only **{w.reached_1r}/{w.entries_total}** entries reached +1R, so the "
        "profit-lock had nothing to arm on for the rest — the exit governor can't "
        "protect a profit the trade never makes. That points at *entry timing / "
        "setup selection*, not just the stop logic."
    )
    out.append(
        "- Full per-day detail: the dated files in this folder. Fix plan: "
        "`docs/analysis/FIX_PLAN.md`."
    )
    out.append("")
    return "\n".join(out) + "\n"
