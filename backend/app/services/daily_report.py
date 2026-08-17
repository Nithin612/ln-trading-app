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

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_data import Ohlcv1m
from app.models.signal import Signal, SignalOutcome
from app.models.stock import Stock
from app.models.trading import Order, Position
from app.models.user import User
from app.services import fo_analytics as fa
from app.services import fo_suggestions as fs
from app.services.excursion import Excursion, load_1m_bars, tape_excursion
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


# `Excursion` moved to `app/services/excursion.py` (shared with the signal-outcome
# excursion recorder, Phase 6 slice 6.1) — imported above.


# `tape_excursion` moved to `app/services/excursion.py` (Phase 6 slice 6.1) —
# imported above; one definition now serves both the report and the recorder.


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
class FillRealismRow:
    """One paper fill, as priced by the 6.8.2 spread-aware model.

    ``excess_inr`` is the honesty delta: what this fill cost ABOVE the old flat
    `paper_slippage_bps` baseline. Summed over a day it is the amount by which
    the pre-6.8.2 paper record was overstating the edge.
    """

    symbol: str
    kind: str  # "entry" | "exit"
    side: str  # BUY | SELL
    quantity: int
    model: str  # "spread" (live book) | "flat" (no book — fell open)
    reference: Decimal  # mark before the haircut
    fill: Decimal
    slippage_bps: Decimal
    baseline_bps: Decimal
    excess_bps: Decimal
    half_spread_bps: Decimal
    impact_bps: Decimal
    excess_inr: Decimal
    filled_at: datetime | None


@dataclass
class DailyReport:
    day: date
    generated_at: datetime
    user: User
    report_end: datetime
    opened: list[TradeRow] = field(default_factory=list)
    closed: list[TradeRow] = field(default_factory=list)
    still_open: list[TradeRow] = field(default_factory=list)
    # Carried = still open at day-end AND opened on a PRIOR day (6.8.4). A subset of
    # `still_open`, surfaced separately so a multi-day hold quietly bleeding toward
    # its stop gets the rolling MFE/MAE narrative, not just an EoD heat line.
    carried: list[TradeRow] = field(default_factory=list)
    realized_today: Decimal = Decimal("0")
    trades_today: int = 0
    daily_loss_cap: Decimal = Decimal("0")
    # portfolio-level
    open_risk_total: Decimal = Decimal("0")
    open_unrealized_eod: Decimal = Decimal("0")
    given_back_total: Decimal = Decimal("0")
    locked_total: Decimal = Decimal("0")  # Σ sealed-profit floors across open positions
    # F&O option-selling engine attribution — see build_fo_health for why.
    fo_health: list[FoUnderlyingHealth] = field(default_factory=list)
    # Intraday shadow layer — see build_shadow_health for why a silent day matters.
    shadow_health: list[ShadowProfileHealth] = field(default_factory=list)
    # Spread-aware fill model (6.8.2) — what the honest book charged vs flat bps.
    fill_realism: list[FillRealismRow] = field(default_factory=list)


# `load_1m_bars` (was `_load_bars`) moved to `app/services/excursion.py`
# (Phase 6 slice 6.1) — imported above.


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
    bars = await load_1m_bars(db, pos.stock_id, pos.opened_at, end)
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


def _place_row(
    report: DailyReport, row: TradeRow, *, day_start: datetime, day_end: datetime
) -> None:
    """Classify one trade row into the report's buckets (opened/closed/still-open/
    carried) and fold its open-book contributions into the portfolio totals."""
    pos = row.position
    if day_start <= pos.opened_at < day_end:
        report.opened.append(row)
    if pos.closed_at is not None and day_start <= pos.closed_at < day_end:
        report.closed.append(row)
    if pos.closed_at is None or pos.closed_at >= day_end:
        report.still_open.append(row)
        if pos.opened_at < day_start:  # opened on a prior day → carried (6.8.4)
            report.carried.append(row)
        if row.eod_unrealized is not None:
            report.open_unrealized_eod += row.eod_unrealized
        if row.chase is not None:
            report.open_risk_total += row.chase.actual_risk_inr
        if row.locked_inr is not None:
            report.locked_total += row.locked_inr
    if row.given_back is not None:
        report.given_back_total += row.given_back


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
        _place_row(report, row, day_start=day_start, day_end=day_end)

    # Realized P&L / trade count for the day (IST) — reuse the breaker helpers'
    # semantics but bounded to the report day rather than "today".
    report.realized_today = await _realized_between(db, user_id, day_start, day_end)
    report.trades_today = sum(1 for p in relevant if day_start <= p.opened_at < day_end)
    # Independent of the equity book — the F&O engine emits suggestions whether
    # or not anything was traded, and a dark day is exactly what needs recording.
    report.fo_health = await build_fo_health(db, day=day)
    report.shadow_health = await build_shadow_health(db, day=day)
    report.fill_realism = await build_fill_realism(
        db, user_id=user_id, start=day_start, end=day_end
    )
    return report


async def build_fill_realism(
    db: AsyncSession, *, user_id: int, start: datetime, end: datetime
) -> list[FillRealismRow]:
    """Read the 6.8.2 fill-model telemetry off the day's paper orders.

    Purely a read of what was recorded at fill time (`broker_payload["fill"]`),
    never a re-derivation — the book that priced a fill is long gone by report
    time, so a recomputation would be fiction. Orders written before 6.8.2 have
    no `fill` block and are simply skipped.
    """
    orders = (
        (
            await db.execute(
                select(Order)
                .where(
                    Order.user_id == user_id,
                    Order.mode == "paper",
                    Order.status == "filled",
                    Order.filled_at >= start,
                    Order.filled_at < end,
                )
                .order_by(Order.filled_at.asc())
            )
        )
        .scalars()
        .all()
    )
    if not orders:
        return []
    symbols = {
        s.id: s.symbol
        for s in (
            await db.execute(
                select(Stock).where(Stock.id.in_({o.stock_id for o in orders}))
            )
        )
        .scalars()
        .all()
    }
    rows: list[FillRealismRow] = []
    for o in orders:
        payload = o.broker_payload if isinstance(o.broker_payload, dict) else {}
        fill = payload.get("fill")
        if not isinstance(fill, dict):
            continue  # pre-6.8.2 order — no telemetry to report
        try:
            reference = _d(fill["reference"])
            excess_bps = _d(fill["excess_bps"])
            qty = int(o.filled_qty or o.quantity or 0)
            rows.append(
                FillRealismRow(
                    symbol=symbols.get(o.stock_id, str(o.stock_id)),
                    kind="entry" if "chase" in payload else "exit",
                    side=o.side,
                    quantity=qty,
                    model=str(fill["model"]),
                    reference=reference,
                    fill=_d(fill["fill"]),
                    slippage_bps=_d(fill["slippage_bps"]),
                    baseline_bps=_d(fill["baseline_bps"]),
                    excess_bps=excess_bps,
                    half_spread_bps=_d(fill["half_spread_bps"]),
                    impact_bps=_d(fill["impact_bps"]),
                    excess_inr=(
                        Decimal(qty) * reference * excess_bps / Decimal("10000")
                    ).quantize(_Q2),
                    filled_at=o.filled_at,
                )
            )
        except (KeyError, TypeError, ValueError, ArithmeticError):
            continue  # a malformed telemetry blob must never break the report
    return rows


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

    # Carried positions (6.8.4) — the rolling MFE/MAE narrative for holds opened on
    # a PRIOR day, marked to THIS day's cutoff (no look-ahead). Without this a swing
    # bleeding toward its stop over several days is never narrated until it closes.
    if r.carried:
        out.append("### Carried positions (opened earlier) — rolling tape to this day's cutoff")
        out.append("")
        for t in r.carried:
            out.extend(_render_trade_block(t, show_date=True))

    # 4. Engine performance ------------------------------------------------- #
    out.extend(_render_engine_section(r))

    # 5. Risk --------------------------------------------------------------- #
    out.extend(_render_risk_section(r))

    # 6. Takeaways ---------------------------------------------------------- #
    out.extend(_render_takeaways(r))

    # 7. F&O engine --------------------------------------------------------- #
    out.extend(_render_fo_section(r.fo_health))

    # 8. Intraday shadow layer ---------------------------------------------- #
    out.extend(_render_shadow_section(r.shadow_health))

    # 9. Fill realism -------------------------------------------------------- #
    out.extend(_render_fill_realism_section(r.fill_realism))
    return "\n".join(out) + "\n"


def _render_fill_realism_section(rows: list[FillRealismRow]) -> list[str]:
    """§9 — what the spread-aware fill model (6.8.2) actually charged.

    The number that matters is the **excess over the flat baseline**: it is the
    amount by which the old flat-2bps paper record was overstating the edge, and
    that record is what gates live trading.
    """
    out: list[str] = ["## 9. Fill realism — spread-aware slippage (6.8.2)", ""]
    if not rows:
        out.append(
            "_No paper fills carrying fill-model telemetry on this day._ "
            "(Orders placed before 6.8.2 have none; a day with no trades has none.)"
        )
        out.append("")
        return out

    priced = [r for r in rows if r.model == "spread"]
    total_excess = sum((r.excess_inr for r in rows), Decimal(0))
    out.append(
        f"- **{len(priced)} of {len(rows)}** fills were priced off a live order book; "
        f"the rest fell open to the flat {rows[0].baseline_bps} bps (no fresh depth — "
        "off-market, thin name, or a cold cache)."
    )
    out.append(
        f"- **Extra cost the honest model charged: {_inr(total_excess)}** — this is how "
        "much the flat-bps record was overstating the day's edge, not a new loss."
    )
    out.append("")
    out.append(
        "| Fill | Symbol | Side | Qty | Model | Ref | Fill | ½-spread | Impact | "
        "Total bps | vs flat | Excess ₹ |"
    )
    out.append("|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        out.append(
            f"| {r.kind} | {r.symbol} | {r.side} | {r.quantity:,} | {r.model} | "
            f"{r.reference:,.2f} | {r.fill:,.2f} | {r.half_spread_bps} | "
            f"{r.impact_bps} | {r.slippage_bps} | +{r.excess_bps} | "
            f"{_inr(r.excess_inr)} |"
        )
    out.append("")
    out.append(
        "_Read: `½-spread` is the real half-spread from the book at fill time; "
        "`Impact` is the size-vs-top-of-book term; the flat bps is a FLOOR, so a "
        "`spread` fill is never cheaper than a `flat` one. Backtests are unaffected "
        "— they run on candle data and never read depth._"
    )
    out.append("")
    return out


def _render_trade_block(t: TradeRow, *, show_date: bool = False) -> list[str]:
    pos = t.position
    sig = t.signal
    c = t.chase
    exc = t.excursion
    klass = sig.classification if sig else "—"
    conf = f"{sig.confidence_pct}%" if sig else "—"
    # Carried positions (opened a prior day) show the open DATE, not just the time.
    opened = _ist_date(pos.opened_at) if show_date else _ist(pos.opened_at)
    out: list[str] = []
    out.append(f"### {t.symbol} — {pos.side} {klass} {conf}  ·  opened {opened} IST")
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
    # Open-book mark-to-market per trading day (6.8.4): (day, gross unrealized of all
    # positions open at that day's cutoff). A day-by-day series, not latest-only, so a
    # carried book's heat is visible as it evolves across the week.
    open_mtm_series: list[tuple[date, Decimal]] = field(default_factory=list)


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


async def _last_1m_close_at(
    db: AsyncSession, stock_id: int, cutoff: datetime
) -> Decimal | None:
    """The mark: last COMPLETE 1m close at or before `cutoff`. Temporally bounded
    (`time <= cutoff`) so no future bar leaks in — the same discipline as
    `load_1m_bars`. ``None`` when the tape has no bar for the stock yet."""
    close = (
        await db.execute(
            select(Ohlcv1m.close)
            .where(
                Ohlcv1m.stock_id == stock_id,
                Ohlcv1m.is_complete.is_(True),
                Ohlcv1m.time <= cutoff,
            )
            .order_by(Ohlcv1m.time.desc())
            .limit(1)
        )
    ).scalars().first()
    return _d(close) if close is not None else None


async def _open_book_mtm(db: AsyncSession, user_id: int, cutoff: datetime) -> Decimal:
    """Gross unrealized P&L of every paper position OPEN at `cutoff`, each marked to
    the last 1m close ≤ cutoff. 0 when the book is flat. Read-only, no look-ahead —
    a position that closed after `cutoff` is still treated as open as of `cutoff`."""
    rows = (
        await db.execute(
            select(Position).where(
                Position.user_id == user_id,
                Position.mode == "paper",
                Position.opened_at <= cutoff,
                or_(Position.closed_at.is_(None), Position.closed_at > cutoff),
            )
        )
    ).scalars().all()
    total = Decimal("0")
    for pos in rows:
        mark = await _last_1m_close_at(db, pos.stock_id, cutoff)
        if mark is None:
            continue
        total += compute_pnl(
            side=pos.side,
            entry=_d(pos.avg_entry_price),
            exit_price=mark,
            quantity=pos.quantity,
        )
    return total.quantize(_Q2)


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

    # Open-book MTM series (6.8.4): one point per TRADING day in the week — the
    # carried book's heat as it evolves, not just the latest day. Each day is marked
    # to min(day-end, now), so a partial current day marks to now and never past it.
    from app.services.market_calendar import is_trading_day

    open_mtm_series: list[tuple[date, Decimal]] = []
    for dp in this_week:
        day_start, day_end = ist_day_bounds(dp.day)
        cutoff = min(day_end, now)
        if cutoff <= day_start:  # a future day in the current week — nothing yet
            continue
        if not await is_trading_day(db, dp.day):
            continue
        open_mtm_series.append((dp.day, await _open_book_mtm(db, user_id, cutoff)))
    open_mtm = open_mtm_series[-1][1] if open_mtm_series else Decimal("0")

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
        open_mtm_series=open_mtm_series,
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
        bars = await load_1m_bars(db, pos.stock_id, pos.opened_at, p_end)
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
    if w.open_mtm_series:
        series = " · ".join(
            f"{d.strftime('%a %m-%d')} {_signed_inr(v)}" for d, v in w.open_mtm_series
        )
        out.append(f"- **Open book mark-to-market (per trading day):** {series}")
    else:
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


# --------------------------------------------------------------------------- #
# F&O option-selling engine health                                             #
# --------------------------------------------------------------------------- #
#
# WHY THIS SECTION EXISTS. Two calibration decisions were taken on 2026-08-07
# (phase-04-fo-suggestions.md §9.3 / §9.7) on the strength of an argument, not a
# measurement, and both were explicitly left open for review:
#
#   1. `require_exact_expiry_future=True` — weeklies excluded. Costs ~9 of every
#      42 weekdays; the bet is that a weekly's ~1%-of-monthly OI makes those days
#      not worth having.
#   2. Stale vol gates warn instead of rejecting.
#
# Reviewing either needs a record of what the engine actually did, day by day.
# The engine returning `[]` was ALREADY the ambiguity that hid a month-long
# outage, so "no suggestions today" must never again be the only artifact.


@dataclass
class FoUnderlyingHealth:
    """One allowed underlying's engine outcome for the report day."""

    symbol: str
    data_day: date | None            # latest F&O bhavcopy at or before the day
    data_lag_days: int | None        # report day − data day (0 = fresh)
    candidates: int
    verdict: str                     # "produced" | "dark" | "no data"
    reason: str                      # plain-language attribution
    expiry: date | None = None
    dte: int | None = None
    forward_source: str | None = None
    in_window: list[date] = field(default_factory=list)
    iv_rank: float | None = None
    iv_rank_as_of: date | None = None
    vix_band: str | None = None

    @property
    def gate_stale_days(self) -> int | None:
        """How far the vol gate's evidence lags the day being priced."""
        if self.iv_rank_as_of is None or self.data_day is None:
            return None
        return (self.data_day - self.iv_rank_as_of).days


async def build_fo_health(
    db: AsyncSession, *, day: date, rules: fs.SellRules | None = None
) -> list[FoUnderlyingHealth]:
    """Per-underlying attribution of what the option-selling engine did.

    Deliberately re-walks the SAME gates in the SAME order as
    `fs.suggest_option_sells`, calling the engine's own helpers rather than
    reimplementing them, so this can only report what the engine would do. The
    candidate count comes from the real entry point.
    """
    rules = rules or fs.DEFAULT_SELL_RULES
    out: list[FoUnderlyingHealth] = []

    for symbol in sorted(rules.allowed_underlyings):
        found = await fs.in_window_expiries(db, symbol, as_of=day, rules=rules)
        if found is None:
            out.append(
                FoUnderlyingHealth(
                    symbol=symbol, data_day=None, data_lag_days=None, candidates=0,
                    verdict="no data", reason="no F&O bhavcopy recorded at or before this day",
                )
            )
            continue
        data_day, in_window = found
        h = FoUnderlyingHealth(
            symbol=symbol,
            data_day=data_day,
            data_lag_days=(day - data_day).days,
            candidates=0,
            verdict="dark",
            reason="",
            in_window=list(in_window),
        )

        ivr = await fa.iv_rank(db, symbol, as_of=day)
        if ivr is not None:
            h.iv_rank, h.iv_rank_as_of = ivr.rank, ivr.as_of
        vix = await fa.vix_regime(db, as_of=datetime.combine(day, time.max, tzinfo=UTC))
        if vix is not None:
            h.vix_band = vix.band

        picked = await fs._pick_expiry(db, symbol, as_of=day, rules=rules)
        if picked is not None:
            _, h.expiry, fwd = picked
            h.dte = (h.expiry - data_day).days
            h.forward_source = fwd.source

        blocked = _fo_blocked_reason(
            rules, ivr=ivr, vix=vix, in_window=in_window, picked=picked is not None
        )
        if blocked is not None:
            h.reason = blocked
        else:
            cands = await fs.suggest_option_sells(db, symbol, as_of=day, rules=rules)
            h.candidates = len(cands)
            if cands:
                h.verdict = "produced"
                h.reason = f"{len(cands)} candidate(s) cleared every gate"
            else:
                h.reason = (
                    f"priced {h.expiry} (DTE {h.dte}) but no structure cleared the "
                    f"reward floor ({rules.min_credit_to_width:.0%} credit/width) "
                    f"or POP floor ({rules.min_pop:.0%}) — a genuine no-trade"
                )
        out.append(h)
    return out


def _fo_blocked_reason(
    rules: fs.SellRules,
    *,
    ivr: fa.IvRank | None,
    vix: fa.VixRegime | None,
    in_window: list[date],
    picked: bool,
) -> str | None:
    """Which gate stopped the engine, or None if none did.

    Evaluated in `suggest_option_sells`' OWN order, which matters: the VIX veto
    fires BEFORE expiry selection, so a vetoed day can still have a perfectly
    pickable expiry. Attributing off "did we pick an expiry" alone would report
    a risk-off stand-down as "nothing qualified" — the exact class of
    misattribution this section exists to prevent.
    """
    if ivr is None:
        return "no IV-rank history — the vol gate cannot be evaluated"
    if ivr.rank < rules.iv_rank_min:
        return f"IV-rank {ivr.rank:.0f} below the {rules.iv_rank_min:.0f} sell gate"
    if rules.skip_high_vix and vix is None:
        return "VIX regime unknown — hard veto fails CLOSED"
    if rules.skip_high_vix and vix is not None and vix.band == "high":
        return "VIX regime HIGH — risk-off veto"
    if picked:
        return None
    if not in_window:
        return f"no option expiry in the {rules.dte_min}–{rules.dte_max} DTE window"
    which = ", ".join(e.isoformat() for e in in_window)
    if rules.require_exact_expiry_future:
        return (
            f"no ELIGIBLE expiry — in-window ({which}) but none has a same-expiry "
            "future, and weeklies are excluded (SellRules.require_exact_expiry_future)"
        )
    return f"no in-window expiry could be priced ({which})"


# ── §8 Intraday shadow layer ────────────────────────────────────────────────
# Same reasoning as §7, one step earlier in the funnel. The three intraday
# profiles run in SHADOW: they execute on the real schedule and their
# suggestions are measured to outcome, but they are never tradeable, because
# walk-forward returned negative risk-adjusted returns for all three. The whole
# point is to replace that backtest verdict with forward evidence.
#
# Which means a silent layer is a FAILED layer. If the profiles mint nothing —
# worker down, Kite token not refreshed, decision bars stale, confidence gate
# never cleared — nobody would notice, and weeks later the "no evidence yet"
# would be indistinguishable from "evidence says no". A dark day is only
# meaningful with its reason.


@dataclass
class ShadowProfileHealth:
    """One shadow profile's outcome for the report day."""

    key: str
    style: str
    timeframe: str
    schedule: str
    status: str
    minted: int                      # shadow signals created on the day
    resolved: int                    # of those, outcomes already terminal
    wins: int
    losses: int
    reason: str | None = None        # why nothing was minted, when minted == 0


async def build_shadow_health(
    db: AsyncSession, *, day: date
) -> list[ShadowProfileHealth]:
    """Per-profile shadow activity for `day`, with attribution when it is zero.

    Reads only — this reports what the scheduler did, it never runs a profile.
    """
    rows = (
        await db.execute(
            text(
                "SELECT key, style, timeframe, schedule, status"
                " FROM strategy_profiles"
                " WHERE status = 'shadow' ORDER BY key"
            )
        )
    ).all()
    if not rows:
        return []

    start = datetime.combine(day, time.min, tzinfo=_IST).astimezone(UTC)
    end = start + timedelta(days=1)

    out: list[ShadowProfileHealth] = []
    for key, style, timeframe, schedule, status in rows:
        stats = (
            await db.execute(
                text(
                    "SELECT count(*) AS minted,"
                    "       count(o.signal_id) FILTER ("
                    "           WHERE o.status IN ('tp_first','sl_first')) AS resolved,"
                    "       count(*) FILTER (WHERE o.status = 'tp_first') AS wins,"
                    "       count(*) FILTER (WHERE o.status = 'sl_first') AS losses"
                    " FROM signals s"
                    " LEFT JOIN signal_outcomes o ON o.signal_id = s.id"
                    " WHERE s.profile_key = :k AND s.is_shadow IS TRUE"
                    "   AND s.created_at >= :start AND s.created_at < :end"
                ),
                {"k": key, "start": start, "end": end},
            )
        ).one()
        minted = int(stats.minted or 0)
        out.append(
            ShadowProfileHealth(
                key=key,
                style=style,
                timeframe=timeframe,
                schedule=schedule,
                status=status,
                minted=minted,
                resolved=int(stats.resolved or 0),
                wins=int(stats.wins or 0),
                losses=int(stats.losses or 0),
                reason=await _shadow_zero_reason(db, timeframe, day) if minted == 0 else None,
            )
        )
    return out


async def _shadow_zero_reason(db: AsyncSession, timeframe: str, day: date) -> str:
    """Why a shadow profile minted nothing — checked in the order it fails.

    Ordering matters for the same reason it did in §7: attributing off the wrong
    gate turns "the data never arrived" into "nothing qualified", which is the
    misreading this section exists to prevent.
    """
    from app.profiles.pipeline import _TIMEFRAME_TABLE
    from app.services.market_calendar import is_trading_day

    if not await is_trading_day(db, day):
        return "not a trading day"

    # Whitelist-sourced identifier, per the raw-SQL rule — never a caller string.
    table = _TIMEFRAME_TABLE.get(timeframe)
    if table is None:
        return f"no bar table for timeframe {timeframe}"
    start = datetime.combine(day, time.min, tzinfo=_IST).astimezone(UTC)
    end = start + timedelta(days=1)
    bars = int(
        (
            await db.execute(
                text(
                    f"SELECT count(*) FROM {table}"  # noqa: S608 - whitelisted name
                    " WHERE time >= :start AND time < :end AND is_complete"
                ),
                {"start": start, "end": end},
            )
        ).scalar_one()
    )
    if bars == 0:
        return (
            f"NO {timeframe} bars for the day — the live worker produced nothing"
            " (check the Kite token ritual and the worker process)"
        )
    return (
        f"ran on {bars} {timeframe} bars but nothing cleared the confidence gate"
        " — the setups did not trigger"
    )


def _render_shadow_section(rows: list[ShadowProfileHealth]) -> list[str]:
    out: list[str] = ["## 8. Intraday shadow layer", ""]
    if not rows:
        out.append("_No profiles are running in shadow._")
        out.append("")
        return out

    out.append(
        "> Shadow profiles run on the real schedule and are measured to outcome, "
        "but are **never tradeable** — the order path rejects them. They exist to "
        "replace a negative backtest verdict with forward evidence, so a silent "
        "day is a failure, not a non-event."
    )
    out.append("")
    out.append("| Profile | TF | Minted | Resolved | W/L | Note |")
    out.append("|---|---|---|---|---|---|")
    for r in rows:
        wl = f"{r.wins}/{r.losses}" if r.resolved else "—"
        note = r.reason or "—"
        out.append(
            f"| `{r.key}` | {r.timeframe} | {r.minted} | {r.resolved} | {wl} | {note} |"
        )
    out.append("")
    total = sum(r.minted for r in rows)
    if total == 0:
        out.append(
            "- **Nothing minted today.** Zero is only meaningful with its reason — "
            "read the Note column before concluding the strategies are dead."
        )
        out.append("")
    return out


def _render_fo_section(rows: list[FoUnderlyingHealth]) -> list[str]:
    out: list[str] = ["## 7. F&O option-selling engine", ""]
    if not rows:
        out.append("_No allowed underlyings configured._")
        out.append("")
        return out

    out.append(
        "> Suggestions only — there is no F&O order path (live trading is Phase 7). "
        "This section exists to review two open calibration decisions "
        "(`phase-04-fo-suggestions.md` §9.3 / §9.7); **a dark day is only "
        "meaningful with its reason.**"
    )
    out.append("")
    out.append("| Underlying | Verdict | Expiry (DTE) | Why |")
    out.append("|---|---|---|---|")
    for h in rows:
        exp = f"{h.expiry} ({h.dte}d)" if h.expiry else "—"
        mark = {"produced": "✅", "dark": "⚫", "no data": "—"}.get(h.verdict, "?")
        out.append(f"| {h.symbol} | {mark} {h.verdict} | {exp} | {h.reason} |")
    out.append("")

    # The two decisions under review, called out explicitly.
    policy_dark = [
        h for h in rows if h.verdict == "dark" and "require_exact_expiry_future" in h.reason
    ]
    if policy_dark:
        names = ", ".join(h.symbol for h in policy_dark)
        out.append(
            f"- **Monthly-only policy cost you today:** {names} had in-window expiries but "
            "all were weeklies. This is the §9.3 decision working as designed — "
            "track how often it lands before deciding whether the flag should flip."
        )
    stale = [h for h in rows if (h.gate_stale_days or 0) > 0]
    if stale:
        worst = max(stale, key=lambda h: h.gate_stale_days or 0)
        out.append(
            f"- **⚠ Vol gate ran on stale evidence:** {worst.symbol}'s IV-rank is from "
            f"{worst.iv_rank_as_of} against a {worst.data_day} chain "
            f"({worst.gate_stale_days}d behind). Per §9.7 this warns rather than rejects — "
            "if it keeps happening, that decision needs revisiting."
        )
    lagging = [h for h in rows if (h.data_lag_days or 0) > 0]
    if lagging:
        worst = max(lagging, key=lambda h: h.data_lag_days or 0)
        out.append(
            f"- **F&O data is {worst.data_lag_days} day(s) behind** (latest bhavcopy "
            f"{worst.data_day}) — check the EOD beats ran."
        )
    if not policy_dark and not stale and not lagging:
        out.append("- No policy or data-freshness flags today.")
    out.append("")
    return out
