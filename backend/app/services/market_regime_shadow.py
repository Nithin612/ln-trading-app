"""Market-regime shadow measurement — MCE slice 4.

The forward-evidence half of the market-regime overlay (`app/signals/market_regime.py`),
mirroring `sector_rs_shadow` / `entry_quality_shadow`: recompute the regime verdict over
the LIVE tradeable signal cohort and report what it WOULD suppress, with a flip-readiness
banner + a per-entry context table. Read-only; never suppresses anything.

Each signal is judged on the broad-market trend as of ITS OWN `created_at` (no look-ahead).
Partition (among the cohort): **would-block** = market regime against the signal's side
(long into a market below its N-DMA, short into one above); **eligible** = regime with the
side; **no data** = fewer than `dma_period` market sessions (fails open live — the state
until the deep index backfill lands). VIX is reported per entry but never gates. Flip
readiness compares would-block vs eligible and speaks to the shadow→active flip (§8 +
sign-off).
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
from app.services.benchmark import MarketRegimeContext, load_market_regime_context
from app.services.signal_outcomes import OUTCOME_EPOCH
from app.signals import market_regime

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
class SignalRegime:
    created_at: datetime
    symbol: str
    side: str
    gap_pct: Decimal | None  # market close vs its N-DMA, %
    vix: Decimal | None
    blocked: bool
    realized: Decimal | None


@dataclass(frozen=True)
class MarketRegimeShadow:
    since: datetime
    n_signals: int
    market_symbol: str
    dma_period: int
    blocked: Bucket
    eligible: Bucket
    no_data: Bucket
    detail: list[SignalRegime] = field(default_factory=list)


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


async def compute_market_regime_shadow(
    db: AsyncSession, *, since: datetime = OUTCOME_EPOCH
) -> MarketRegimeShadow:
    """Recompute the market-regime overlay over the tradeable cohort (is_shadow FALSE)
    since `since`, partitioned by would-block / eligible / no-market-data, with outcomes."""
    sigs = (
        await db.execute(
            select(Signal).where(Signal.is_shadow.is_(False), Signal.created_at >= since)
        )
    ).scalars().all()
    realized = await _realized_by_signal(db, [s.id for s in sigs])
    symbols = await _symbols(db, [s.stock_id for s in sigs])

    symbol = settings.market_regime_market_symbol
    dma_period = settings.market_regime_dma_period
    buffer_pct = Decimal(str(settings.market_regime_dma_buffer_pct))
    vix_threshold = Decimal(str(settings.market_regime_vix_threshold))

    blocked, eligible, no_data = Bucket(), Bucket(), Bucket()
    detail: list[SignalRegime] = []
    # The market-regime context is stock-independent — it varies only by the as-of DATE
    # (the SQL filters `trade_date <= as_of.date()`). Memoize per date so a cohort of N
    # signals across D distinct days costs D loads, not N (identical results).
    ctx_cache: dict[date, MarketRegimeContext] = {}

    for s in sigs:
        key = s.created_at.date()
        ctx = ctx_cache.get(key)
        if ctx is None:
            ctx = await load_market_regime_context(
                db, market_symbol=symbol, dma_period=dma_period, as_of=s.created_at
            )
            ctx_cache[key] = ctx
        v = market_regime.evaluate(
            side=s.direction,
            market_closes=ctx.market_closes,
            dma_period=dma_period,
            buffer_pct=buffer_pct,
            vix=ctx.vix,
            vix_threshold=vix_threshold,
            market_symbol=symbol,
        )
        r = realized.get(s.id)
        if not v.has_data:
            no_data.add(r)
        elif v.blocked:
            blocked.add(r)
        else:
            eligible.add(r)
        if v.has_data:
            detail.append(
                SignalRegime(
                    created_at=s.created_at,
                    symbol=symbols.get(s.stock_id, str(s.stock_id)),
                    side=v.side,
                    gap_pct=v.gap_pct,
                    vix=v.vix,
                    blocked=v.blocked,
                    realized=r,
                )
            )

    detail.sort(key=lambda d: d.created_at, reverse=True)
    return MarketRegimeShadow(
        since=since,
        n_signals=len(sigs),
        market_symbol=symbol,
        dma_period=dma_period,
        blocked=blocked,
        eligible=eligible,
        no_data=no_data,
        detail=detail,
    )


def regime_flip_ready(r: MarketRegimeShadow) -> tuple[bool, str]:
    # SHARED VETO FIRST. A gate-specific count/sign test is meaningless if the partition
    # itself cannot certify anything — this is what let the market-regime banner print
    # ✅ READY on a side proxy whose negative mean was 94% one trade. See
    # `app/services/flip_readiness.py` for the three guards and why each exists.
    _veto = fr.veto(
        [fr.Row(side=d.side, blocked=d.blocked, realized=d.realized) for d in r.detail]
    )
    if _veto is not None:
        return False, f"VETOED by a shared readiness guard — {_veto}"

    """Forward evidence to flip the market-regime gate ACTIVE? ≥ N resolved would-block
    trades, that set net-losing, AND worse than the eligible set. Advice only — never
    flips anything (mirrors sector_rs_shadow.rs_flip_ready)."""
    b, p = r.blocked, r.eligible
    if b.resolved < FORWARD_EVIDENCE_TARGET_N:
        return False, (
            f"{b.resolved}/{FORWARD_EVIDENCE_TARGET_N} resolved would-block trades — keep accruing"
        )
    if b.avg is None or b.avg >= 0:
        return False, f"would-block set is not net-negative ({b.avg}) — do NOT flip"
    if p.avg is not None and b.avg >= p.avg:
        return False, f"would-block ({b.avg}) not worse than eligible ({p.avg}) — do NOT flip"
    return True, (
        f"would-block net-negative ({b.avg}), worse than eligible ({p.avg}) — READY for sign-off"
    )


def readiness_line(r: MarketRegimeShadow) -> str:
    ready, reason = regime_flip_ready(r)
    tag = "✅ READY" if ready else "⏳ NOT READY"
    return f"[market-regime forward evidence] {tag} — {reason}"


def _row(name: str, b: Bucket) -> str:
    avg = f"₹{b.avg:,.0f}" if b.avg is not None else "—"
    win = f"{b.win_pct}%" if b.win_pct is not None else "—"
    net = f"₹{b.net:,.0f}" if b.resolved else "—"
    return f"| {name} | {b.n} | {b.resolved} | {net} | {avg} | {win} |"


def _detail_row(d: SignalRegime) -> str:
    gap = f"{d.gap_pct:+.2f}%" if d.gap_pct is not None else "—"
    vix = f"{d.vix:.2f}" if d.vix is not None else "—"
    outcome = f"₹{d.realized:,.0f}" if d.realized is not None else "open/none"
    flag = "🚫 would-block" if d.blocked else "✅ with-regime"
    return f"| {d.created_at.date()} | {d.symbol} | {d.side} | {gap} | {vix} | {flag} | {outcome} |"


def render_markdown(r: MarketRegimeShadow, *, day: date) -> str:
    mode = settings.market_regime_gate_mode
    out = [
        f"# Market-regime shadow (live signals) — {day}",
        "",
        f"_Read-only. The market-regime overlay recomputed over the tradeable signal cohort "
        f"since {r.since.date()} ({r.n_signals} signals), broad-market ({r.market_symbol}) "
        f"trend + VIX aligned to each signal's decision time (no look-ahead). Gate mode: "
        f"**{mode}**. A signal is 'would-block' when the market regime is AGAINST its side — a "
        f"long while {r.market_symbol} is below its {r.dma_period}-DMA, a short while above. "
        f"'no market data' = fewer than {r.dma_period} index sessions yet (fails open live; "
        "needs the deep index backfill). VIX is reported per entry but never gates. A "
        "would-block set net-negative AND worse than the with-regime set is the evidence to "
        "flip the gate active._",
        "",
        "| set | signals | resolved | net ₹ | avg ₹ | win% |",
        "|---|--:|--:|--:|--:|--:|",
        _row("would-BLOCK (regime against the side)", r.blocked),
        _row("with-regime (eligible)", r.eligible),
        _row(f"no market data (< {r.dma_period}-DMA history)", r.no_data),
        "",
    ]
    ready, reason = regime_flip_ready(r)
    tag = "✅ READY" if ready else "⏳ NOT READY"
    out += [
        f"**market-regime flip readiness:** {tag} — {reason}. Flipping the gate active is "
        "behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user "
        "sign-off (reversible via `market_regime_gate_mode=shadow`).",
        "",
    ]
    if r.detail:
        shown = r.detail[:_DETAIL_MAX]
        out += [
            *fr.evidence_lines(
                [fr.Row(side=d.side, blocked=d.blocked, realized=d.realized) for d in r.detail],
                label="market-regime gate",
            ),
            "## Per-entry context (each committed signal's market regime)",
            "",
            "| date | stock | side | mkt vs DMA | VIX | regime verdict | outcome |",
            "|---|---|---|--:|--:|---|--:|",
            *[_detail_row(d) for d in shown],
            "",
        ]
        if len(r.detail) > _DETAIL_MAX:
            out.append(f"_… {len(r.detail) - _DETAIL_MAX} more assessable signals not shown._")
            out.append("")
    else:
        out += [
            "_No signals had ≥ DMA-period market history yet — index OHLC still backfilling._",
            "",
        ]
    return "\n".join(out) + "\n"
