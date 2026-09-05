"""Shared guards that stop a shadow sidecar printing ✅ READY on bad evidence.

Two gates were promoted on favourable-looking banners in one week, and both had to be
reverted:

  - **regime (ADX 20–25)** — promoted on 44 resolved observations, refuted by 88. Cost
    ~8R and three weeks of a contaminated population.
  - **R:R ≥ 1** — promoted on an "it enforces an identity, so no evidence bar is needed"
    argument, refuted within a week: it blocked the book's only profitable cohort
    (24 trades, +₹10,585, 63% win).

Meanwhile the **market-regime** sidecar has been printing ✅ READY on evidence that cannot
support it at all, and nothing in the readiness logic could tell:

  - NIFTY50 sat below its 200-DMA on **33 of 33 days**, so the gate never varied — every
    LONG was blocked and every SHORT kept (39/11, zero exceptions). "Would-block is
    net-negative" was just *our longs lost and our shorts broke even* over one directional
    window: a **side proxy**, not a regime finding.
  - It would block the cohort with the **better median (+₹156) and better win rate (54%)**,
    on a mean where **one trade (NDRAUTO −₹14,970) is 94% of the loss**. Dropping the
    worst 3 of 65 longs flips that cohort from −₹15,986 to **+₹10,861**.

Each sidecar keeps its own count/sign criteria (those are gate-specific). These guards are
the shared *veto*: they answer "can this evidence certify ANY gate?", and any failure
refuses READY regardless of how good the headline looks.

**What a failing guard does and does not mean.** It is a refusal to CERTIFY, not a verdict
that the gate is bad — it says this evidence cannot distinguish the gate from something
simpler, or rests on too few observations to be trusted. A gate that trips `side_proxy` in
a one-directional window might genuinely discriminate in a two-sided one; the honest
response is to keep measuring, not to conclude.

Pure: rows in, verdicts out. No I/O, no settings.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services import block_bootstrap as bb

#: Blocked/eligible purity above which the partition is treated as a proxy for side.
SIDE_PURITY = 0.95
#: Fraction of the worst outcomes trimmed when testing whether the sign is tail-driven.
TAIL_TRIM_FRAC = 0.10


@dataclass(frozen=True)
class Row:
    """The minimal per-entry record every sidecar already carries."""

    side: str
    blocked: bool
    realized: Decimal | None  # None = not resolved (no P&L yet)
    # When the entry happened. Optional only for backwards compatibility: the block
    # bootstrap (H1) resamples CONSECUTIVE runs of trades, so it is meaningless unless the
    # series is in time order — and sidecars sort their rows for DISPLAY (market_regime
    # sorts newest-first). Rather than trust a convention nothing can check, the bootstrap
    # sorts by this and REFUSES when any row lacks it.
    at: datetime | None = None


@dataclass(frozen=True)
class Guard:
    name: str
    ok: bool
    reason: str


def _resolved(rows: Sequence[Row], *, blocked: bool) -> list[Decimal]:
    return [r.realized for r in rows if r.blocked is blocked and r.realized is not None]


def _chronological(rows: Sequence[Row], *, blocked: bool) -> bb.BootstrapResult | None:
    """Resolved outcomes for one side of the partition, in TIME order.

    Returns the bootstrap result, or None when the order cannot be established because a
    row carries no timestamp — blocks drawn from an arbitrarily-ordered series are not
    blocks, and an interval computed from them would look authoritative while measuring
    nothing. Fail closed.
    """
    from app.services import block_bootstrap as bb

    picked = [r for r in rows if r.blocked is blocked and r.realized is not None]
    if not picked or any(r.at is None for r in picked):
        return None
    ordered = sorted(picked, key=lambda r: r.at)  # type: ignore[arg-type,return-value]
    return bb.moving_block_bootstrap([float(r.realized) for r in ordered])  # type: ignore[arg-type]


def _median(xs: Sequence[Decimal]) -> Decimal:
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return Decimal(0)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def _win_pct(xs: Sequence[Decimal]) -> float | None:
    return (sum(1 for x in xs if x > 0) / len(xs)) if xs else None


def side_proxy_guard(rows: Sequence[Row]) -> Guard:
    """FAIL when the blocked/eligible split is ~perfectly predicted by trade SIDE.

    If every blocked entry is one side and every eligible entry the other, the sidecar is
    measuring long-vs-short performance over the window, not the gate. That is exactly how
    the market-regime banner reached ✅ READY: NIFTY never crossed its 200-DMA, so the gate
    reduced to "block longs" for 33 of 33 days.
    """
    blocked = [r.side.upper() for r in rows if r.blocked]
    eligible = [r.side.upper() for r in rows if not r.blocked]
    if not blocked or not eligible:
        return Guard("side_proxy", True, "one side of the partition is empty — not assessable")
    b_top = max(set(blocked), key=blocked.count)
    e_top = max(set(eligible), key=eligible.count)
    b_purity = blocked.count(b_top) / len(blocked)
    e_purity = eligible.count(e_top) / len(eligible)
    if b_top != e_top and b_purity >= SIDE_PURITY and e_purity >= SIDE_PURITY:
        return Guard(
            "side_proxy",
            False,
            f"the partition is a PROXY FOR SIDE — {b_purity:.0%} of would-block entries are "
            f"{b_top} and {e_purity:.0%} of eligible are {e_top}. This evidence measures "
            "long-vs-short performance over the window, not the gate, so it cannot certify "
            "a flip however good the headline looks",
        )
    return Guard("side_proxy", True, "the partition is not explained by side alone")


def tail_guard(rows: Sequence[Row]) -> Guard:
    """FAIL when the would-block set's negative mean is carried by a few outliers.

    Two independent reads, both must hold:
      - the **median** must be ≤ 0 (a positive median with a negative mean IS a tail);
      - the mean must stay negative after dropping the worst `TAIL_TRIM_FRAC` of outcomes.
    """
    b = _resolved(rows, blocked=True)
    if len(b) < 3:
        return Guard("tail", True, f"only {len(b)} resolved would-block trades — not assessable")
    med = _median(b)
    mean = sum(b) / len(b)
    if med > 0:
        # The message must branch on the MEAN's sign. Saying "the negative mean is carried
        # by losses" when the mean is POSITIVE is simply false — and the liquidity sidecar
        # produced exactly that sentence on first run (median ₹515, mean ₹326). A guard
        # built to stop misleading banners must not emit one itself.
        detail = (
            f"while its mean is ₹{mean:,.0f} — the negative mean is carried by a few large "
            "losses, so the gate would suppress a cohort that is TYPICALLY profitable"
            if mean < 0
            else f"and its mean is ₹{mean:,.0f} too — the would-block set is net-POSITIVE, "
            "so the gate would suppress a profitable cohort outright"
        )
        return Guard("tail", False, f"would-block MEDIAN is ₹{med:,.0f} (positive) {detail}")
    k = max(1, math.ceil(len(b) * TAIL_TRIM_FRAC))
    trimmed = sorted(b)[k:]
    if trimmed and sum(trimmed) / len(trimmed) >= 0:
        return Guard(
            "tail",
            False,
            f"dropping the worst {k} of {len(b)} would-block trades moves its mean from "
            f"₹{mean:,.0f} to ₹{sum(trimmed) / len(trimmed):,.0f} — the negative sign is "
            "tail-driven, not a property of the cohort",
        )
    return Guard("tail", True, "the would-block set stays net-negative after trimming the tail")


def win_rate_guard(rows: Sequence[Row]) -> Guard:
    """FAIL when the would-block set WINS MORE OFTEN than the eligible set.

    A gate that suppresses the higher-win-rate cohort is choosing on magnitude alone. That
    can be legitimate (cutting fat-tailed losers), but it is not something a ✅ READY banner
    should assert without the tail guard also passing — so it is called out explicitly.
    """
    bw = _win_pct(_resolved(rows, blocked=True))
    ew = _win_pct(_resolved(rows, blocked=False))
    if bw is None or ew is None:
        return Guard("win_rate", True, "a side of the partition has no resolved trades")
    if bw > ew:
        return Guard(
            "win_rate",
            False,
            f"would-block wins MORE often than eligible ({bw:.0%} vs {ew:.0%}) — the gate is "
            "suppressing the higher-win-rate cohort",
        )
    return Guard("win_rate", True, f"would-block win rate {bw:.0%} ≤ eligible {ew:.0%}")


def guards(rows: Sequence[Row]) -> list[Guard]:
    """All shared guards, in the order a reader should consider them."""
    return [side_proxy_guard(rows), tail_guard(rows), win_rate_guard(rows)]


def veto(rows: Sequence[Row]) -> str | None:
    """The reason READY must be refused, or None if every shared guard passes.

    Call this FIRST in a sidecar's own readiness function: a gate-specific count/sign test
    is meaningless if the partition itself cannot certify anything.
    """
    failed = [g for g in guards(rows) if not g.ok]
    if not failed:
        return None
    return "; ".join(f"[{g.name}] {g.reason}" for g in failed)


# ── The RECORD, not just the verdict ─────────────────────────────────────────
# User request 2026-09-03: "along with ✅ READY or sign-off it is best to have the data or
# record of the captured one — it helps better." A verdict without its numbers cannot be
# re-judged months later, and both gates we reverted were reverted precisely because
# someone went back to the numbers. So every readiness banner now ships its evidence.


def _fmt(x: Decimal | float | None, money: bool = True) -> str:
    if x is None:
        return "—"
    return f"₹{x:,.0f}" if money else f"{x:.2f}"


def evidence_lines(rows: Sequence[Row], *, label: str, trials: int | None = None) -> list[str]:
    """Markdown recording WHAT was measured, beside the verdict.

    Includes the deflated-Sharpe bar on the ELIGIBLE set — the book you would actually
    hold if the gate were flipped — because that is the thing whose risk-adjusted return
    has to survive the multiple-testing correction.
    """
    from app.services import block_bootstrap as bb  # local: keeps this module dependency-light
    from app.services import deflated_sharpe as ds

    b = _resolved(rows, blocked=True)
    e = _resolved(rows, blocked=False)
    n_b = sum(1 for r in rows if r.blocked)
    n_e = len(rows) - n_b

    def row(name: str, xs: list[Decimal], n: int) -> str:
        if not xs:
            return f"| {name} | {n} | 0 | — | — | — | — |"
        k = max(1, math.ceil(len(xs) * TAIL_TRIM_FRAC))
        trimmed = sorted(xs)[k:]
        tmean = (sum(trimmed) / len(trimmed)) if trimmed else None
        wp = _win_pct(xs)
        return (
            f"| {name} | {n} | {len(xs)} | {_fmt(sum(xs) / len(xs))} | {_fmt(_median(xs))} "
            f"| {_fmt(tmean)} | {wp:.0%} |" if wp is not None else ""
        )

    out = [
        "",
        f"### Evidence of record — {label}",
        "",
        "_The numbers behind the verdict, so it can be re-judged later. `trimmed mean` drops "
        f"the worst {TAIL_TRIM_FRAC:.0%} of outcomes: if the sign changes there, the signal is "
        "tail-driven._",
        "",
        "| set | signals | resolved | mean | median | trimmed mean | win% |",
        "|---|--:|--:|--:|--:|--:|--:|",
        row("would-BLOCK", b, n_b),
        row("eligible (kept)", e, n_e),
        "",
        "**Shared guards:**",
    ]
    for g in guards(rows):
        out.append(f"- {'✅' if g.ok else '🚫'} `{g.name}` — {g.reason}")
    out.append("")
    if e:
        dsr = (
            ds.deflated_sharpe([float(x) for x in e], trials=trials)
            if trials is not None
            else ds.deflated_sharpe([float(x) for x in e])
        )
        out += ds.render_lines(
            dsr, label="eligible set (the book a flip would leave you holding)"
        )
        # H1 — the non-parametric complement, on the same set. DSR asks "better than
        # luck given N trials"; this asks "if the same process ran again, would the sign
        # hold". Read them together: DSR's weakness is the independence assumption, and
        # blocks are what price that in.
        out += bb.render_lines(
            _chronological(rows, blocked=False),
            label="eligible set",
        )
    else:
        out.append("- **deflated Sharpe:** no resolved eligible trades yet")
    out.append("")
    return out
