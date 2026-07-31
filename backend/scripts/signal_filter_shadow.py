"""Signal-filter shadow report — would a regime (ER) / R:R / age gate have
improved trade selection?

Read-only. For every paper trade, compute the three filter signals AS OF ENTRY
(no look-ahead) — Kaufman efficiency ratio of the daily tape (trend vs chop),
the signal's reward:risk, and near-expiry (≥80% of validity elapsed) — and the
RELIABLE outcome (open = mark-to-market at the latest 1m close; closed =
realised, with off-tape/pre-open-bug corrupt trades flagged and excluded from
totals). Then show, for candidate gates, what would be KEPT vs KILLED and the
P&L / win-rate of each bucket. Measure before gating.

    uv run python scripts/signal_filter_shadow.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from app.models.market_data import Ohlcv1m, OhlcvDaily  # noqa: E402
from app.models.signal import Signal  # noqa: E402
from app.models.stock import Stock  # noqa: E402
from app.models.trading import Position  # noqa: E402
from sqlalchemy import select  # noqa: E402

_MARKET_END = datetime(2026, 7, 31, 10, 0, tzinfo=UTC)  # 15:30 IST 07-31 (session cutoff)


@dataclass
class Trade:
    symbol: str
    side: str
    classification: str
    conf: int
    rr: float
    er10: float | None
    near_expiry: bool
    aligned: bool | None      # trade direction with the 20d daily trend?
    outcome: Decimal | None   # gross ₹ (None = corrupt/insufficient → excluded)
    flag: str


def _kaufman_er(closes: list[float], n: int = 10) -> float | None:
    if len(closes) < n + 1:
        return None
    seg = closes[-(n + 1):]
    net = abs(seg[-1] - seg[0])
    path = sum(abs(seg[i] - seg[i - 1]) for i in range(1, len(seg)))
    return (net / path) if path else 0.0


async def _load() -> list[Trade]:  # noqa: C901 — linear per-trade collection
    trades: list[Trade] = []
    async with AsyncSessionFactory() as db:
        rows = (
            await db.execute(
                select(Position).where(Position.mode == "paper").order_by(Position.opened_at)
            )
        ).scalars().all()

        for p in rows:
            stock = await db.get(Stock, p.stock_id)
            symbol = stock.symbol if stock else str(p.stock_id)
            sig = await db.get(Signal, p.signal_id) if p.signal_id else None
            classification = sig.classification if sig else "?"
            conf = sig.confidence_pct if sig else 0
            entry = Decimal(str(p.avg_entry_price))

            # reward:risk from the signal
            rr = 0.0
            near_expiry = False
            if sig is not None:
                s_entry = Decimal(str(sig.entry_price))
                risk = abs(s_entry - Decimal(str(sig.stop_loss)))
                if risk > 0:
                    rr = float(abs(Decimal(str(sig.take_profit)) - s_entry) / risk)
                span = (sig.validity_until - sig.created_at).total_seconds()
                if span > 0:
                    near_expiry = (p.opened_at - sig.created_at).total_seconds() / span >= 0.8

            # ER (as of entry) + 20d trend, from daily closes strictly before entry
            dclose = (
                await db.execute(
                    select(OhlcvDaily.close)
                    .where(
                        OhlcvDaily.stock_id == p.stock_id,
                        OhlcvDaily.is_complete.is_(True),
                        OhlcvDaily.time < p.opened_at,
                    )
                    .order_by(OhlcvDaily.time.desc())
                    .limit(25)
                )
            ).scalars().all()
            closes = [float(c) for c in reversed(dclose)]
            er10 = _kaufman_er(closes, 10)
            aligned: bool | None = None
            if len(closes) >= 21:
                chg20 = closes[-1] / closes[-21] - 1
                trend_up = chg20 > 0.02
                trend_dn = chg20 < -0.02
                if trend_up or trend_dn:
                    aligned = (p.side == "LONG") == trend_up

            # reliable outcome (gross ₹)
            outcome: Decimal | None = None
            flag = ""
            if p.closed_at is None:
                latest = (
                    await db.execute(
                        select(Ohlcv1m.close)
                        .where(Ohlcv1m.stock_id == p.stock_id, Ohlcv1m.is_complete.is_(True))
                        .order_by(Ohlcv1m.time.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if latest is not None:
                    px = Decimal(str(latest))
                    outcome = (entry - px if p.side == "SHORT" else px - entry) * p.quantity
                    flag = "open(MTM)"
                else:
                    flag = "open(no price)"
            else:
                # off-tape check: exit better than anything that traded in the window
                ext = (
                    await db.execute(
                        select(Ohlcv1m.high, Ohlcv1m.low).where(
                            Ohlcv1m.stock_id == p.stock_id,
                            Ohlcv1m.is_complete.is_(True),
                            Ohlcv1m.time >= p.opened_at,
                            Ohlcv1m.time <= (p.closed_at or _MARKET_END),
                        )
                    )
                ).all()
                off_tape = False
                if ext and p.exit_price is not None:
                    hi = max(Decimal(str(r.high)) for r in ext)
                    lo = min(Decimal(str(r.low)) for r in ext)
                    xp = Decimal(str(p.exit_price))
                    off_tape = (p.side == "SHORT" and xp < lo) or (p.side == "LONG" and xp > hi)
                if off_tape:
                    flag = "CORRUPT(off-tape)"        # excluded from totals
                else:
                    outcome = p.realized_pnl + (p.charges or Decimal("0"))  # gross realised
                    flag = "closed"

            trades.append(Trade(symbol, p.side, classification, conf, rr, er10,
                                near_expiry, aligned, outcome, flag))
    return trades


def _bucket(name: str, kept: list[Trade], killed: list[Trade]) -> str:
    def stat(ts: list[Trade]) -> str:
        vals = [float(t.outcome) for t in ts if t.outcome is not None]
        if not vals:
            return f"{len(ts):>2} trades   —"
        wins = sum(1 for v in vals if v > 0)
        return (f"{len(ts):>2} trades  P&L {sum(vals):>+8.0f}  "
                f"win {wins}/{len(vals)} ({100*wins//max(1,len(vals)):>3}%)")
    return f"  {name:<26} KEEP: {stat(kept)}\n  {'':<26} KILL: {stat(killed)}"


async def run() -> int:
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    trades = await _load()
    usable = [t for t in trades if t.outcome is not None]

    print(f"\n{len(trades)} paper trades  ({len(usable)} with a reliable outcome; "
          f"{len(trades)-len(usable)} corrupt/no-price excluded)\n")
    print(f"{'stock':<11}{'side':<6}{'class':<11}{'conf':>4}{'R:R':>5}{'ER10':>6}"
          f"{'nearExp':>8}{'align':>7}{'outcome':>10}  flag")
    for t in sorted(trades, key=lambda x: (x.outcome or Decimal('-99999'))):
        er = f"{t.er10:.2f}" if t.er10 is not None else "  —"
        al = "—" if t.aligned is None else ("WITH" if t.aligned else "vs")
        oc = f"{float(t.outcome):>+10.0f}" if t.outcome is not None else f"{'—':>10}"
        print(f"{t.symbol:<11}{t.side:<6}{t.classification:<11}{t.conf:>4}{t.rr:>5.1f}"
              f"{er:>6}{('yes' if t.near_expiry else 'no'):>8}{al:>7}{oc}  {t.flag}")

    print("\n── would-a-gate-have-helped (on the reliable-outcome trades) ──")
    def split(pred):  # noqa: ANN001
        keep = [t for t in usable if pred(t)]
        kill = [t for t in usable if not pred(t)]
        return keep, kill
    print(_bucket("drop near-expiry", *split(lambda t: not t.near_expiry)))
    print(_bucket("regime ER10 >= 0.30", *split(lambda t: (t.er10 or 0) >= 0.30)))
    print(_bucket("R:R >= 1.5", *split(lambda t: t.rr >= 1.5)))
    print(_bucket("with-trend only", *split(lambda t: t.aligned is True)))
    print(_bucket("ALL: fresh + ER>=.3 + R:R>=1.5",
                  *split(lambda t: (not t.near_expiry) and (t.er10 or 0) >= 0.30 and t.rr >= 1.5)))
    print("\noutcome = gross ₹ (open = MTM @ latest 1m close; closed = realised+charges).")
    print("A gate HELPS if its KILL bucket is more negative / lower win-rate than KEEP.")
    print(f"Small sample ({len(usable)}) — directional only; confirm on the Mon/Tue forward run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
