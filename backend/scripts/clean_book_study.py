"""What does the book look like without the trades that were never really chosen?

    uv run python scripts/clean_book_study.py

## The question

*"Some positions were entered wildly without looking at the signal, and a few were
mis-clicks. Omit those and the rest will show the real P&L."*

## ⚠ First finding: none of that is recorded anywhere

Nothing in `CHANGELOG.md`, `docs/`, the phase docs or the memory files marks any position
as a mis-click. There is no `entered_by`, no intent flag, no annotation. So the exclusion
below is a **forensic reconstruction from execution signatures**, not a record of what was
meant. It can be wrong about any individual trade.

## ⚠ Second finding: the "wrong button" class does not exist in this book

Checked explicitly:

- **side mismatch** (a LONG opened on a SELL signal, or the reverse) — **0 of 106**
- **entered through its own stop** — **1** (SPARC, the side-blind `size_for_fill` bug,
  fixed forward-only)
- **weekend entries** — 0 · **off-market entries** — 3

So nobody bought a sell signal. Whatever went wrong was not a click on the wrong button.

## What IS detectable: entering far from the signal's own entry

If a trade was taken without looking at the price, the fill sits a long way past the entry
the signal specified. That displacement has a name here and an owner: `chase_guard.py`
blocks it at `settings.chase_max_r`, and the threshold is READ from settings rather than
copied (working rule W5) so this study cannot silently disagree with the gate.

## ⚠⚠ Third finding — and it is about the instrument, not the book

**Displacement is measured in units of the stop distance, so a tight stop mechanically
inflates it.** A stock that ran ₹1 past its entry is "0.1R chased" on a ₹10 stop and "1.0R
chased" on a ₹1 stop — same price action, different verdict. And the numbers show exactly
that entanglement: the chased trades average a **2.13%** stop against **5.33%** for the
rest, with 8 of 12 in the already-known tight-stop leak (CLAUDE.md: *"14 trades with stops
<2% of price lost ₹25,951 at 29% win"*).

So "chased" is substantially a **proxy for "tight stop"** — the same partition-is-a-proxy
trap the market-regime gate (proxy for *side*) and the profit-lock ratchet (proxy for
*went into profit*) already sprang here. The cross-tab is printed below and the cells are
too small to separate the two effects. **Do not read this as a clean measurement of
chasing.**

## What it is legitimate for

Removing the worst 12% of any book improves it, so a cleaned P&L proves nothing on its
own. The reason this particular cut is not hindsight is that **displacement is knowable
BEFORE the order** — `chase_guard` computes it from the live LTP at order time. It is an
implementable policy, not a filter fitted after the fact.

That still does not make it promotable: n is 12. The bar is t ≈ 3.6, flat in n.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.db.session import AsyncSessionFactory  # noqa: E402
from sqlalchemy import text  # noqa: E402

_IST = ZoneInfo("Asia/Kolkata")
_OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "analysis"

_SQL = text(
    """
    SELECT s.symbol, sg.classification AS cls, p.side, p.quantity,
           p.avg_entry_price AS fill, sg.entry_price AS sig_entry,
           sg.stop_loss AS commit_sl, p.peak_pnl, p.realized_pnl, sg.direction
    FROM positions p
    JOIN signals sg ON sg.id = p.signal_id
    JOIN stocks s ON s.id = p.stock_id
    WHERE p.mode = 'paper' AND p.closed_at IS NOT NULL
    """
)

_BUCKETS: tuple[tuple[float, float, str], ...] = (
    # ⚠ The floor is -inf, not 0. `peak_pnl` is genuinely NEGATIVE for a trade whose best
    # mark never cleared its own entry — 10 of 86 here — and a 0.0 floor silently dropped
    # every one of them from the table while still counting them in the summary, so the
    # rows added to 76 against a stated 86. A bucket table must partition its input.
    (float("-inf"), 0.25, "<0.25R (incl. never above entry)"),
    (0.25, 0.5, "0.25-0.5R"),
    (0.5, 1.0, "0.5-1R"),
    (1.0, 2.0, "1-2R"),
    (2.0, float("inf"), ">=2R"),
)


@dataclass
class T:
    """One closed position, with every quantity needed to judge how it was entered."""

    symbol: str
    cls: str
    pnl: float
    risk_inr: float
    peak_r: float | None
    chase_r: float | None
    stop_pct: float
    wrong_side: bool

    @property
    def real_r(self) -> float:
        return self.pnl / self.risk_inr


def classify(t: T, max_chase: float) -> str:
    """`broken` (R not computable) → `chased` → `clean`, in that order.

    Order matters: a wrong-side row has a meaningless chase figure too, so it must be
    caught first rather than landing in whichever bucket its garbage arithmetic implies.
    """
    if t.risk_inr <= 0 or t.wrong_side:
        return "broken"
    if t.chase_r is not None and t.chase_r > max_chase:
        return "chased"
    return "clean"


def build(rows: list) -> list[T]:  # type: ignore[type-arg]
    trades: list[T] = []
    for r in rows:
        long = r.side == "LONG"
        # Risk from the ACTUAL fill (what was really at stake), displacement against the
        # SIGNAL's entry (what was intended) — two different reference prices on purpose.
        risk_sh = float(r.fill - r.commit_sl) if long else float(r.commit_sl - r.fill)
        sig_risk = abs(float(r.sig_entry - r.commit_sl))
        disp = float(r.fill - r.sig_entry) if long else float(r.sig_entry - r.fill)
        risk_inr = risk_sh * r.quantity
        trades.append(
            T(
                symbol=r.symbol,
                cls=r.cls,
                pnl=float(r.realized_pnl),
                risk_inr=risk_inr,
                peak_r=(float(r.peak_pnl) / risk_inr)
                if (r.peak_pnl is not None and risk_inr > 0)
                else None,
                chase_r=(disp / sig_risk) if sig_risk > 0 else None,
                stop_pct=100 * sig_risk / float(r.fill) if r.fill else 0.0,
                wrong_side=(long and r.direction != "BUY")
                or (not long and r.direction != "SELL"),
            )
        )
    return trades


def _exit_section(clean: list[T]) -> list[str]:
    """The exit picture on the clean set — a DIFFERENT question from the entry audit.

    Split out so the two cannot be read as one argument: excluding badly-entered trades
    is about P&L attribution, while this asks whether doing so moves where the loss is
    made. It does not, and that is the point of printing it here.
    """
    ok = [t for t in clean if t.peak_r is not None]
    if not ok:
        return []
    out = [
        "",
        "## Does excluding them change the EXIT verdict? No.",
        "",
        "| peak bucket | n | peak R | realised R | capture |",
        "|---|--:|--:|--:|--:|",
    ]
    placed = 0
    for lo, hi, label in _BUCKETS:
        g = [t for t in ok if lo <= (t.peak_r or 0.0) < hi]
        placed += len(g)
        if not g:
            continue
        sp = sum(t.peak_r or 0.0 for t in g)
        sr = sum(t.real_r for t in g)
        # Capture against a peak that never existed is undefined, not a large negative.
        cap = f"{100 * sr / sp:.0f}%" if sp >= 0.5 * len(g) else "— (no peak)"
        out.append(f"| {label} | {len(g)} | {sp:.1f}R | {sr:+.1f}R | {cap} |")

    # The rows MUST account for every trade in the summary line below, or the two
    # disagree and the reader has no way to tell which is wrong. They did once.
    assert placed == len(ok), f"bucket table dropped {len(ok) - placed} trade(s)"

    worked = [t for t in ok if (t.peak_r or 0.0) >= 0.5]
    never = [t for t in ok if (t.peak_r or 0.0) < 0.5]
    wp = sum(t.peak_r or 0.0 for t in worked)
    if wp <= 0:
        return out
    wr = sum(t.real_r for t in worked)
    out += [
        "",
        f"⭐ On the clean set the exits still keep **{100 * wr / wp:.0f}%** of peak on the "
        f"{len(worked)} trades that reached 0.5R, and **{len(never)} of {len(ok)}** still "
        f"never got there (₹{sum(t.pnl for t in never):,.0f}).",
        "",
        "**⇒ The exit conclusion is robust to the exclusion.** Removing the badly-entered",
        "trades does not turn this into an exit problem; it makes the entry problem smaller",
        "without moving where it lives.",
    ]
    return out


def render(trades: list[T], max_chase: float, today: str) -> str:
    groups: dict[str, list[T]] = {"clean": [], "chased": [], "broken": []}
    for t in trades:
        groups[classify(t, max_chase)].append(t)

    out: list[str] = [
        f"# The book without the trades that were never really chosen ({today})",
        "",
        f"**{len(trades)} closed paper positions.** Exclusion threshold "
        f"`settings.chase_max_r = {max_chase}` — read from the same setting "
        "`chase_guard.py` enforces, never copied (W5).",
        "",
        "## ⚠ No mis-click is recorded anywhere",
        "",
        "Nothing in `CHANGELOG.md`, `docs/`, the phase docs or the memory files marks a",
        "position as unintended, and there is no intent field on `positions`. What follows",
        "is a **forensic reconstruction from execution signatures** and can be wrong about",
        "any individual trade.",
        "",
        "## ⚠ The 'wrong button' class is empty",
        "",
        f"- LONG opened on a SELL signal (or the reverse): "
        f"**{sum(1 for t in trades if t.wrong_side)} of {len(trades)}**",
        f"- entered through its own stop: "
        f"**{sum(1 for t in trades if t.risk_inr <= 0 and not t.wrong_side)}** "
        "(the side-blind `size_for_fill` bug, fixed forward-only)",
        "",
        "Nobody bought a sell signal. Whatever went wrong was not a mis-click.",
        "",
        "## The book, split",
        "",
        "| set | n | realised ₹ | total R | win% |",
        "|---|--:|--:|--:|--:|",
    ]
    for name, label in (
        ("clean", "**KEEP** — entered at or near the signal"),
        ("chased", f"EXCLUDE — filled >{max_chase}R past the signal entry"),
        ("broken", "EXCLUDE — R not computable (stop on the wrong side of the fill)"),
    ):
        g = groups[name]
        if not g:
            continue
        wins = sum(1 for t in g if t.pnl > 0)
        tot_r = sum(t.real_r for t in g if t.risk_inr > 0)
        out.append(
            f"| {label} | {len(g)} | ₹{sum(t.pnl for t in g):,.0f} | {tot_r:+.1f}R | "
            f"{100 * wins / len(g):.0f}% |"
        )

    book = sum(t.pnl for t in trades)
    clean_pnl = sum(t.pnl for t in groups["clean"])
    dropped = len(trades) - len(groups["clean"])
    out += [
        "",
        f"⭐ **The book as recorded is ₹{book:,.0f}. Without those {dropped} trades it is "
        f"₹{clean_pnl:,.0f}** — a swing of ₹{clean_pnl - book:,.0f} across "
        f"{100 * dropped / len(trades):.0f}% of the positions.",
        "",
        "## ⚠⚠ But 'chased' is largely a proxy for 'tight stop'",
        "",
        "Displacement is measured in units of the **stop distance**, so a tight stop",
        "mechanically inflates it: a stock that ran ₹1 past its entry is 0.1R chased on a",
        "₹10 stop and 1.0R chased on a ₹1 stop. Same price action, opposite verdict.",
        "",
        "| set | n | avg stop width | tight stops (<2%) |",
        "|---|--:|--:|--:|",
    ]
    for name in ("clean", "chased"):
        g = groups[name]
        if g:
            out.append(
                f"| {name} | {len(g)} | {sum(t.stop_pct for t in g) / len(g):.2f}% | "
                f"{sum(1 for t in g if t.stop_pct < 2)} |"
            )
    out += [
        "",
        "CLAUDE.md already records the tight-stop leak independently — *14 trades with",
        "stops <2% of price lost ₹25,951 at 29% win*. The two partitions overlap heavily.",
        "",
        "| stop | entry | n | ₹ | avg R | win% |",
        "|---|---|--:|--:|--:|--:|",
    ]
    for wide in (False, True):
        for name in ("chased", "clean"):
            sub = [t for t in groups[name] if (t.stop_pct >= 2) is wide]
            if not sub:
                continue
            out.append(
                f"| {'wide (>=2%)' if wide else 'tight (<2%)'} | {name} | {len(sub)} | "
                f"₹{sum(t.pnl for t in sub):,.0f} | "
                f"{sum(t.real_r for t in sub) / len(sub):+.2f} | "
                f"{100 * sum(1 for t in sub if t.pnl > 0) / len(sub):.0f}% |"
            )
    out += [
        "",
        "**The cells are too small to separate the two effects.** Chasing survives inside",
        "the wide-stop group, which is the cleanest look available — but on a handful of",
        "trades. Read this as *two entangled defects*, not a measurement of chasing.",
    ]
    out += _exit_section(groups["clean"])
    out += [
        "",
        "## ⚠ What this does NOT license",
        "",
        f"- **Flipping `chase_gate_mode` active.** n = {len(groups['chased'])}. The bar is",
        "  t ≈ 3.6 and it is flat in n — more data will not lower it.",
        f"- **Treating ₹{clean_pnl:,.0f} as a P&L we could have had.** Removing the worst",
        f"  {100 * dropped / len(trades):.0f}% of any book improves it. The only reason this",
        "  cut is not hindsight is that displacement is knowable BEFORE the order.",
    ]
    return "\n".join(out)


async def _run() -> int:
    max_chase = float(settings.chase_max_r)
    async with AsyncSessionFactory() as db:
        rows = list((await db.execute(_SQL)).all())
    if not rows:
        print("no closed paper positions")
        return 1

    now = datetime.now(UTC).astimezone(_IST)
    report = render(build(rows), max_chase, now.date().isoformat())
    print(report, flush=True)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = _OUT_DIR / f"clean-book-{now.date().isoformat()}.md"
    target.write_text(report + "\n", encoding="utf-8")
    print(f"\nwritten: {target}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
