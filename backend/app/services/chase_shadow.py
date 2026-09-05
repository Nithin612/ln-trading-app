"""Anti-chase shadow measurement — the forward-evidence half of `app/signals/chase_guard.py`.

Mirrors `liquidity_shadow` / `market_regime_shadow`: report what the anti-chase gate WOULD
suppress over the LIVE tradeable signal cohort, with a flip-readiness banner + a per-entry table.
Read-only; never suppresses.

**Evidence source.** The gate acts pre-fill on the live LTP, but the honest realized signal is how
far past entry each order ACTUALLY filled — recorded on every order's `broker_payload`. So per
signal the chase_r is read from the order: the gate's own `chase_gate.chase_r` stamp when present
(shadow/active orders), else the broker's post-fill `chase.chase_r` telemetry as the historical
proxy (the two differ only by the fill haircut). Partition (among the cohort): **chased**
(chase_r > `chase_max_r` — would-block), **near entry** (eligible), **no data** (no chase stamp).
Flip readiness compares chased vs near-entry and speaks to the shadow→active flip (§8 + sign-off).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.signal import Signal
from app.models.stock import Stock
from app.models.trading import Order, Position
from app.services import flip_readiness as fr
from app.services.signal_outcomes import OUTCOME_EPOCH

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
class SignalChase:
    created_at: datetime
    symbol: str
    side: str
    chase_r: Decimal
    would_block: bool
    realized: Decimal | None


@dataclass(frozen=True)
class ChaseShadow:
    since: datetime
    n_signals: int
    max_chase_r: Decimal
    chased: Bucket
    near_entry: Bucket
    no_data: Bucket
    detail: list[SignalChase] = field(default_factory=list)


def _chase_r_from_payload(payload: dict[str, object] | None) -> Decimal | None:
    """The realized chase_r for an order: the gate's own stamp first (what it would act on),
    else the broker's post-fill telemetry. None when neither is present/parseable."""
    if not isinstance(payload, dict):
        return None
    for key, field_name in (("chase_gate", "chase_r"), ("chase", "chase_r")):
        block = payload.get(key)
        if isinstance(block, dict) and block.get(field_name) is not None:
            try:
                return Decimal(str(block[field_name]))
            except (InvalidOperation, ValueError):
                continue
    return None


async def _chase_by_signal(db: AsyncSession, signal_ids: list[str]) -> dict[str, Decimal]:
    """signal_id → recorded chase_r, from the entry order's broker_payload."""
    out: dict[str, Decimal] = {}
    if not signal_ids:
        return out
    for sig_id, payload in (
        await db.execute(
            select(Order.signal_id, Order.broker_payload)
            .where(Order.signal_id.in_(signal_ids), Order.mode == "paper")
            # Earliest entry order wins deterministically — the INITIAL entry's chase, not a
            # later average-in (bug-hunter LOW #2; without this the "first parseable" row is
            # non-deterministic when a signal has >1 entry order).
            .order_by(Order.placed_at.asc())
        )
    ).all():
        if sig_id is None or sig_id in out:
            continue
        cr = _chase_r_from_payload(payload)
        if cr is not None:
            out[sig_id] = cr
    return out


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


async def compute_chase_shadow(db: AsyncSession, *, since: datetime = OUTCOME_EPOCH) -> ChaseShadow:
    """Recompute the anti-chase partition over the tradeable cohort (is_shadow FALSE) since
    `since`, partitioned by chased / near-entry / no-data, with resolved outcomes."""
    sigs = (
        await db.execute(
            select(Signal).where(Signal.is_shadow.is_(False), Signal.created_at >= since)
        )
    ).scalars().all()
    ids = [s.id for s in sigs]
    chase = await _chase_by_signal(db, ids)
    realized = await _realized_by_signal(db, ids)
    symbols = await _symbols(db, [s.stock_id for s in sigs])

    max_chase_r = Decimal(str(settings.chase_max_r))
    chased, near_entry, no_data = Bucket(), Bucket(), Bucket()
    detail: list[SignalChase] = []

    for s in sigs:
        cr = chase.get(s.id)
        r = realized.get(s.id)
        if cr is None:
            no_data.add(r)
            continue
        would_block = cr > max_chase_r
        (chased if would_block else near_entry).add(r)
        detail.append(
            SignalChase(
                created_at=s.created_at,
                symbol=symbols.get(s.stock_id, str(s.stock_id)),
                side="LONG" if s.direction.upper() in ("BUY", "LONG") else "SHORT",
                chase_r=cr,
                would_block=would_block,
                realized=r,
            )
        )

    detail.sort(key=lambda d: d.created_at, reverse=True)
    return ChaseShadow(
        since=since,
        n_signals=len(sigs),
        max_chase_r=max_chase_r,
        chased=chased,
        near_entry=near_entry,
        no_data=no_data,
        detail=detail,
    )


def chase_flip_ready(r: ChaseShadow) -> tuple[bool, str]:
    # SHARED VETO FIRST. A gate-specific count/sign test is meaningless if the partition
    # itself cannot certify anything — this is what let the market-regime banner print
    # ✅ READY on a side proxy whose negative mean was 94% one trade. See
    # `app/services/flip_readiness.py` for the three guards and why each exists.
    _veto = fr.veto(
        [
            fr.Row(side=d.side, blocked=d.would_block, realized=d.realized, at=d.created_at)
            for d in r.detail
        ]
    )
    if _veto is not None:
        return False, f"VETOED by a shared readiness guard — {_veto}"

    """Forward evidence to flip the anti-chase gate ACTIVE? ≥ N resolved chased trades, that set
    net-losing, AND worse than the near-entry set. Advice only — never flips."""
    b, p = r.chased, r.near_entry
    if b.resolved < FORWARD_EVIDENCE_TARGET_N:
        return False, (
            f"{b.resolved}/{FORWARD_EVIDENCE_TARGET_N} resolved chased trades "
            f"(> {r.max_chase_r}R past entry) — keep accruing"
        )
    if b.avg is None or b.avg >= 0:
        return False, f"chased set is not net-negative ({b.avg}) — do NOT flip"
    if p.avg is not None and b.avg >= p.avg:
        return False, f"chased ({b.avg}) not worse than near-entry ({p.avg}) — do NOT flip"
    return True, (
        f"chased net-negative ({b.avg}), worse than near-entry ({p.avg}) — READY for sign-off"
    )


def readiness_line(r: ChaseShadow) -> str:
    ready, reason = chase_flip_ready(r)
    tag = "✅ READY" if ready else "⏳ NOT READY"
    return f"[anti-chase forward evidence] {tag} — {reason}"


def _row(name: str, b: Bucket) -> str:
    avg = f"₹{b.avg:,.0f}" if b.avg is not None else "—"
    win = f"{b.win_pct}%" if b.win_pct is not None else "—"
    net = f"₹{b.net:,.0f}" if b.resolved else "—"
    return f"| {name} | {b.n} | {b.resolved} | {net} | {avg} | {win} |"


def _detail_row(d: SignalChase) -> str:
    outcome = f"₹{d.realized:,.0f}" if d.realized is not None else "open/none"
    flag = "🚫 chased" if d.would_block else "✅ near entry"
    cr = f"{d.chase_r:+.3f}R"
    cells = f"{d.created_at.date()} | {d.symbol} | {d.side} | {cr} | {flag} | {outcome}"
    return f"| {cells} |"


def render_markdown(r: ChaseShadow, *, day: date) -> str:
    mode = settings.chase_gate_mode
    out = [
        f"# Anti-chase shadow (live signals) — {day}",
        "",
        f"_Read-only. The anti-chase overlay recomputed over the tradeable signal cohort since "
        f"{r.since.date()} ({r.n_signals} signals), each judged on how far past its entry the "
        f"order actually filled (chase_r = R past entry; the gate's own stamp when present, else "
        f"the broker's post-fill telemetry). Gate mode: **{mode}**. 'chased' = chase_r above the "
        f"{r.max_chase_r}R ceiling — the reward:risk you were shown is materially gone. A "
        "would-block set net-negative AND worse than the near-entry set is the evidence to flip "
        "the gate active._",
        "",
        "| set | signals | resolved | net ₹ | avg ₹ | win% |",
        "|---|--:|--:|--:|--:|--:|",
        _row(f"CHASED (> {r.max_chase_r}R past entry, would-block)", r.chased),
        _row("near entry (eligible)", r.near_entry),
        _row("no data (no chase stamp)", r.no_data),
        "",
    ]
    ready, reason = chase_flip_ready(r)
    tag = "✅ READY" if ready else "⏳ NOT READY"
    out += [
        f"**anti-chase flip readiness:** {tag} — {reason}. Flipping the gate active is "
        "behaviour-changing → needs forward evidence + explicit user sign-off (reversible via "
        "`chase_gate_mode=shadow`).",
        "",
    ]
    if r.detail:
        shown = r.detail[:_DETAIL_MAX]
        out += [
            *fr.evidence_lines(
                [
                    fr.Row(
                        side=d.side, blocked=d.would_block, realized=d.realized, at=d.created_at
                    )
                    for d in r.detail
                ],
                label="anti-chase gate",
            ),
            "## Per-entry context (each committed signal's chase)",
            "",
            "| date | stock | side | chase_r | verdict | outcome |",
            "|---|---|---|--:|---|--:|",
            *[_detail_row(d) for d in shown],
            "",
        ]
        if len(r.detail) > _DETAIL_MAX:
            out.append(f"_… {len(r.detail) - _DETAIL_MAX} more assessable signals not shown._")
            out.append("")
    else:
        out += ["_No tradeable signals carried a chase stamp yet._", ""]
    return "\n".join(out) + "\n"
