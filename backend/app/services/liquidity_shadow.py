"""Liquidity shadow measurement — MCE slice 5a.

Forward-evidence half of the liquidity overlay (`app/signals/liquidity_guard.py`), mirroring
`sector_rs_shadow` / `market_regime_shadow`: recompute the liquidity verdict over the LIVE
tradeable signal cohort and report what it WOULD suppress, with a flip-readiness banner + a
per-entry table. Read-only; never suppresses.

Each signal is judged on the stock's traded-value history as of ITS OWN `created_at` (no
look-ahead). Partition (among the cohort): **illiquid** (median daily traded value below the
floor), **liquid** (eligible), **no data** (fewer than `lookback` sessions — fails open live).
Flip readiness compares illiquid vs liquid and speaks to the shadow→active flip (§8 + sign-off).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.signal import Signal
from app.models.stock import Stock
from app.models.trading import Position
from app.services import flip_readiness as fr
from app.services.liquidity import load_traded_values
from app.services.signal_outcomes import OUTCOME_EPOCH
from app.signals import liquidity_guard

FORWARD_EVIDENCE_TARGET_N = 20
_DETAIL_MAX = 50


@dataclass
class Bucket:
    n: int = 0
    resolved: int = 0
    net: Decimal = field(default_factory=lambda: Decimal("0"))
    wins: int = 0

    def add(self, realized: Decimal | None) -> None:
        self.n += 1
        if realized is not None:
            self.resolved += 1
            self.net += realized
            if realized > 0:
                self.wins += 1

    @property
    def avg(self) -> Decimal | None:
        return (self.net / self.resolved) if self.resolved else None

    @property
    def win_pct(self) -> int | None:
        return round(100 * self.wins / self.resolved) if self.resolved else None


@dataclass(frozen=True)
class SignalLiquidity:
    created_at: datetime
    symbol: str
    side: str
    median_traded_value: Decimal | None
    blocked: bool
    realized: Decimal | None


@dataclass(frozen=True)
class LiquidityShadow:
    since: datetime
    n_signals: int
    lookback: int
    floor: Decimal
    illiquid: Bucket
    liquid: Bucket
    no_data: Bucket
    detail: list[SignalLiquidity] = field(default_factory=list)


async def _realized_by_signal(db: AsyncSession, signal_ids: list[str]) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    if not signal_ids:
        return out
    for sig_id, realized, closed_at in (
        await db.execute(
            select(Position.signal_id, Position.realized_pnl, Position.closed_at).where(
                Position.signal_id.in_(signal_ids), Position.mode == "paper"
            )
        )
    ).all():
        if closed_at is not None and sig_id is not None:
            out[sig_id] = out.get(sig_id, Decimal("0")) + realized
    return out


async def _symbols(db: AsyncSession, stock_ids: list[int]) -> dict[int, str]:
    if not stock_ids:
        return {}
    rows = (await db.execute(select(Stock.id, Stock.symbol).where(Stock.id.in_(stock_ids)))).all()
    return {sid: sym for sid, sym in rows}


async def compute_liquidity_shadow(
    db: AsyncSession, *, since: datetime = OUTCOME_EPOCH
) -> LiquidityShadow:
    """Recompute the liquidity overlay over the tradeable cohort (is_shadow FALSE) since
    `since`, partitioned by illiquid / liquid / no-data, with resolved outcomes."""
    sigs = (
        await db.execute(
            select(Signal).where(Signal.is_shadow.is_(False), Signal.created_at >= since)
        )
    ).scalars().all()
    realized = await _realized_by_signal(db, [s.id for s in sigs])
    symbols = await _symbols(db, [s.stock_id for s in sigs])

    lookback = settings.liquidity_lookback
    floor = Decimal(str(settings.liquidity_min_traded_value_inr))
    illiquid, liquid, no_data = Bucket(), Bucket(), Bucket()
    detail: list[SignalLiquidity] = []

    for s in sigs:
        values = await load_traded_values(db, s.stock_id, lookback=lookback, as_of=s.created_at)
        v = liquidity_guard.evaluate(
            traded_values=values, side=s.direction, lookback=lookback, min_traded_value=floor
        )
        r = realized.get(s.id)
        if not v.has_data:
            no_data.add(r)
        elif v.blocked:
            illiquid.add(r)
        else:
            liquid.add(r)
        if v.has_data:
            detail.append(
                SignalLiquidity(
                    created_at=s.created_at,
                    symbol=symbols.get(s.stock_id, str(s.stock_id)),
                    side=v.side,
                    median_traded_value=v.median_traded_value,
                    blocked=v.blocked,
                    realized=r,
                )
            )

    detail.sort(key=lambda d: d.created_at, reverse=True)
    return LiquidityShadow(
        since=since,
        n_signals=len(sigs),
        lookback=lookback,
        floor=floor,
        illiquid=illiquid,
        liquid=liquid,
        no_data=no_data,
        detail=detail,
    )


def liquidity_flip_ready(r: LiquidityShadow) -> tuple[bool, str]:
    # SHARED VETO FIRST. A gate-specific count/sign test is meaningless if the partition
    # itself cannot certify anything — this is what let the market-regime banner print
    # ✅ READY on a side proxy whose negative mean was 94% one trade. See
    # `app/services/flip_readiness.py` for the three guards and why each exists.
    _veto = fr.veto(
        [
            fr.Row(side=d.side, blocked=d.blocked, realized=d.realized, at=d.created_at)
            for d in r.detail
        ]
    )
    if _veto is not None:
        return False, f"VETOED by a shared readiness guard — {_veto}"

    """Forward evidence to flip the liquidity gate ACTIVE? ≥ N resolved illiquid trades,
    that set net-losing, AND worse than the liquid set. Advice only — never flips (mirrors
    sector_rs_shadow.rs_flip_ready)."""
    b, p = r.illiquid, r.liquid
    if b.resolved < FORWARD_EVIDENCE_TARGET_N:
        return False, (
            f"{b.resolved}/{FORWARD_EVIDENCE_TARGET_N} resolved illiquid trades — keep accruing"
        )
    if b.avg is None or b.avg >= 0:
        return False, f"illiquid set is not net-negative ({b.avg}) — do NOT flip"
    if p.avg is not None and b.avg >= p.avg:
        return False, f"illiquid ({b.avg}) not worse than liquid ({p.avg}) — do NOT flip"
    return True, (
        f"illiquid net-negative ({b.avg}), worse than liquid ({p.avg}) — READY for sign-off"
    )


def readiness_line(r: LiquidityShadow) -> str:
    ready, reason = liquidity_flip_ready(r)
    tag = "✅ READY" if ready else "⏳ NOT READY"
    return f"[liquidity forward evidence] {tag} — {reason}"


def _row(name: str, b: Bucket) -> str:
    avg = f"₹{b.avg:,.0f}" if b.avg is not None else "—"
    win = f"{b.win_pct}%" if b.win_pct is not None else "—"
    net = f"₹{b.net:,.0f}" if b.resolved else "—"
    return f"| {name} | {b.n} | {b.resolved} | {net} | {avg} | {win} |"


def _detail_row(d: SignalLiquidity) -> str:
    mtv = f"₹{d.median_traded_value:,.0f}" if d.median_traded_value is not None else "—"
    outcome = f"₹{d.realized:,.0f}" if d.realized is not None else "open/none"
    flag = "🚫 illiquid" if d.blocked else "✅ liquid"
    return f"| {d.created_at.date()} | {d.symbol} | {d.side} | {mtv} | {flag} | {outcome} |"


def render_markdown(r: LiquidityShadow, *, day: date) -> str:
    mode = settings.liquidity_gate_mode
    out = [
        f"# Liquidity shadow (live signals) — {day}",
        "",
        f"_Read-only. The liquidity overlay recomputed over the tradeable signal cohort since "
        f"{r.since.date()} ({r.n_signals} signals), each judged on its stock's median daily traded "
        f"value (₹ = close × volume) over {r.lookback} sessions as of its decision time (no "
        f"look-ahead). Gate mode: **{mode}**. 'illiquid' = median below the ₹{r.floor:,.0f} "
        "floor — too thin to exit safely, either side (the SRTL archetype). A would-block set "
        "net-negative AND worse than the liquid set is the evidence to flip the gate active._",
        "",
        "| set | signals | resolved | net ₹ | avg ₹ | win% |",
        "|---|--:|--:|--:|--:|--:|",
        _row(f"ILLIQUID (< ₹{r.floor:,.0f}/day, would-block)", r.illiquid),
        _row("liquid (eligible)", r.liquid),
        _row(f"no data (< {r.lookback} sessions)", r.no_data),
        "",
    ]
    ready, reason = liquidity_flip_ready(r)
    tag = "✅ READY" if ready else "⏳ NOT READY"
    out += [
        f"**liquidity flip readiness:** {tag} — {reason}. Flipping the gate active is "
        "behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user "
        "sign-off (reversible via `liquidity_gate_mode=shadow`).",
        "",
    ]
    if r.detail:
        shown = r.detail[:_DETAIL_MAX]
        out += [
            *fr.evidence_lines(
                [
                    fr.Row(
                        side=d.side, blocked=d.blocked, realized=d.realized, at=d.created_at
                    )
                    for d in r.detail
                ],
                label="liquidity gate",
            ),
            "## Per-entry context (each committed signal's liquidity)",
            "",
            "| date | stock | side | median ₹/day | liquidity | outcome |",
            "|---|---|---|--:|---|--:|",
            *[_detail_row(d) for d in shown],
            "",
        ]
        if len(r.detail) > _DETAIL_MAX:
            out.append(f"_… {len(r.detail) - _DETAIL_MAX} more assessable signals not shown._")
            out.append("")
    else:
        out += ["_No signals had ≥ lookback sessions of history yet._", ""]
    return "\n".join(out) + "\n"
