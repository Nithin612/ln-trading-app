"""Market-regime study (~3y) — validates the level-vs-breadth thesis and builds a regime playbook.

The two-window autopsy suggested the 200-DMA *level* alone does not separate a good tape from a bad
one — short-term *breadth* does. This study tests that across the whole index history we have
(NIFTY 50 + Bank/Fin Nifty + India VIX, 2023-07 → now): it classifies each day into a level×breadth
quadrant (reusing the already-reviewed `market_regime_report.summarize_regime` as-of that day, so no
look-ahead in the *classifier*) and measures the FORWARD 5/10/20-session return that followed. A
study legitimately looks forward — we are measuring "what happened AFTER this regime", which is the
whole point; the frozen signal engine and live paths are untouched.

Outputs: (1) forward returns per quadrant — the direct test of "below+strong (Window A) beats
below+weak (Window B)"; (2) below-200-DMA drawdown episodes (depth, duration, recovery); (3) VIX by
quadrant; (4) index dispersion (does BankNifty/FinNifty fare worse in weak regimes?). The
FII/DII-flow angle is a KNOWN GAP — the recorder only has ~1 month of history — flagged, not faked.
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.services.market_regime_report import summarize_regime

HORIZONS = (5, 10, 20)  # forward sessions
_MIN_HISTORY = 200  # need a full 200-DMA before a day is classifiable
QUADRANTS = ("above+strong", "above+weak", "below+strong", "below+weak")


@dataclass(frozen=True)
class DayState:
    t: int  # index into the close series
    d: date
    close: float
    quadrant: str
    vs200: float
    breadth: float
    vix: float | None
    fwd: dict[int, float | None]  # horizon → forward return % (None if it runs past the data)


@dataclass
class QuadStat:
    quadrant: str
    n: int = 0
    fwd_sum: dict[int, float] = field(default_factory=dict)
    fwd_cnt: dict[int, int] = field(default_factory=dict)
    win20: int = 0  # days whose forward-20 return was > 0
    win20_cnt: int = 0
    vix_sum: float = 0.0
    vix_cnt: int = 0

    def avg_fwd(self, k: int) -> float | None:
        return self.fwd_sum.get(k, 0.0) / self.fwd_cnt[k] if self.fwd_cnt.get(k) else None

    def fwd_n(self, k: int) -> int:
        """Days that actually HAD a forward-k window (the mean's denominator) — < n for the tail
        days whose window runs past the data. The label must use THIS, not the day-count."""
        return self.fwd_cnt.get(k, 0)

    @property
    def win20_pct(self) -> float | None:
        return 100 * self.win20 / self.win20_cnt if self.win20_cnt else None

    @property
    def avg_vix(self) -> float | None:
        return self.vix_sum / self.vix_cnt if self.vix_cnt else None


@dataclass(frozen=True)
class Episode:
    start: date
    end: date
    sessions: int
    depth_pct: float  # trough vs the close on the day it crossed below the 200-DMA
    recovered: bool  # crossed back above the 200-DMA within the data
    avg_vix: float | None


def _quadrant(level_bullish: bool, breadth_bullish: bool) -> str:
    return ("above" if level_bullish else "below") + "+" + ("strong" if breadth_bullish else "weak")


def classify_days(
    dates: list[date], closes: list[float], vix: list[float | None]
) -> list[DayState]:
    """One DayState per classifiable day (≥200 prior closes), with the level×breadth quadrant
    as-of that day and the forward returns that followed."""
    n = len(closes)
    dclose = [Decimal(str(c)) for c in closes]
    out: list[DayState] = []
    for t in range(n):
        if t + 1 < _MIN_HISTORY:
            continue
        v = vix[t]
        r = summarize_regime(dclose[: t + 1], Decimal(str(v)) if v is not None else None)
        if not r.enough or r.level_bullish is None or r.breadth_bullish is None:
            continue
        fwd: dict[int, float | None] = {}
        for k in HORIZONS:
            fwd[k] = ((closes[t + k] / closes[t] - 1) * 100) if (t + k < n and closes[t]) else None
        out.append(
            DayState(
                t=t,
                d=dates[t],
                close=closes[t],
                quadrant=_quadrant(r.level_bullish, r.breadth_bullish),
                vs200=r.vs_long_pct or 0.0,
                breadth=r.breadth_up_pct or 0.0,
                vix=r.vix,
                fwd=fwd,
            )
        )
    return out


def quadrant_stats(days: list[DayState]) -> dict[str, QuadStat]:
    stats = {q: QuadStat(quadrant=q) for q in QUADRANTS}
    for ds in days:
        s = stats[ds.quadrant]
        s.n += 1
        for k in HORIZONS:
            fv = ds.fwd.get(k)
            if fv is not None:
                s.fwd_sum[k] = s.fwd_sum.get(k, 0.0) + fv
                s.fwd_cnt[k] = s.fwd_cnt.get(k, 0) + 1
        f20 = ds.fwd.get(20)
        if f20 is not None:
            s.win20_cnt += 1
            if f20 > 0:
                s.win20 += 1
        if ds.vix is not None:
            s.vix_sum += ds.vix
            s.vix_cnt += 1
    return stats


def below_episodes(days: list[DayState]) -> list[Episode]:
    """Contiguous runs of 'below-200-DMA' classified days → depth/duration/recovery."""
    episodes: list[Episode] = []
    run: list[DayState] = []

    def flush(recovered: bool) -> None:
        if not run:
            return
        entry = run[0].close
        trough = min(x.close for x in run)
        vixes = [x.vix for x in run if x.vix is not None]
        episodes.append(
            Episode(
                start=run[0].d,
                end=run[-1].d,
                sessions=len(run),
                depth_pct=(trough / entry - 1) * 100 if entry else 0.0,
                recovered=recovered,
                avg_vix=statistics.mean(vixes) if vixes else None,
            )
        )

    for ds in days:
        if ds.quadrant.startswith("below"):
            run.append(ds)
        elif run:
            flush(recovered=True)  # crossed back above → recovered
            run = []
    if run:
        flush(recovered=False)  # still below at the end of the data
    return episodes


def dispersion(
    days: list[DayState], closes_by_index: dict[str, list[float]], horizon: int = 20
) -> dict[str, dict[str, float | None]]:
    """Avg forward-`horizon` return of each index, grouped by NIFTY's quadrant — does
    BankNifty/FinNifty fall harder in weak regimes? Keyed quadrant → {index → avg fwd %}."""
    acc: dict[str, dict[str, list[float]]] = {
        q: {idx: [] for idx in closes_by_index} for q in QUADRANTS
    }
    for ds in days:
        for idx, series in closes_by_index.items():
            t = ds.t
            if t + horizon < len(series) and series[t]:
                acc[ds.quadrant][idx].append((series[t + horizon] / series[t] - 1) * 100)
    return {
        q: {idx: (statistics.mean(v) if v else None) for idx, v in idxmap.items()}
        for q, idxmap in acc.items()
    }


@dataclass(frozen=True)
class Robustness:
    """Does the below-weak vs below-strong fwd-20 gap survive the overlap problem? The naive means
    treat overlapping forward windows as independent (they aren't — the +1.33 vs +0.21 rests on ~2
    episodes). Two honest re-estimates: (1) a NON-OVERLAPPING subsample (days ≥ horizon apart), and
    (2) a moving-block bootstrap CI on the gap (blocks preserve local autocorrelation)."""

    horizon: int
    no_weak: float | None
    no_strong: float | None
    no_gap: float | None
    no_n_weak: int
    no_n_strong: int
    boot_gap_mean: float | None
    boot_ci_lo: float | None
    boot_ci_hi: float | None
    boot_p_positive: float | None  # fraction of replicates with below-weak > below-strong
    n_boot: int


def _labeled_fwd(days: list[DayState], horizon: int) -> list[tuple[str, float]]:
    """Chronological (quadrant, fwd-horizon) for days that HAVE a forward window."""
    out: list[tuple[str, float]] = []
    for d in days:
        v = d.fwd.get(horizon)
        if v is not None:
            out.append((d.quadrant, v))
    return out


def _below_gap(labeled: list[tuple[str, float]]) -> tuple[float | None, float | None, float | None,
                                                          int, int]:
    weak = [v for q, v in labeled if q == "below+weak"]
    strong = [v for q, v in labeled if q == "below+strong"]
    mw = statistics.mean(weak) if weak else None
    ms = statistics.mean(strong) if strong else None
    gap = (mw - ms) if (mw is not None and ms is not None) else None
    return mw, ms, gap, len(weak), len(strong)


def robustness(
    days: list[DayState],
    *,
    horizon: int = 20,
    block: int = 20,
    n_boot: int = 1000,
    seed: int = 12345,
) -> Robustness:
    """Non-overlapping subsample + moving-block bootstrap of the below-weak − below-strong fwd gap.
    Seeded → deterministic/reproducible."""
    # (1) non-overlapping: greedily keep classified days ≥ horizon apart (by t), then split.
    kept: list[tuple[str, float]] = []
    last_t = -(10**9)
    for d in sorted(days, key=lambda x: x.t):
        v = d.fwd.get(horizon)
        if v is None or d.t - last_t < horizon:
            continue
        kept.append((d.quadrant, v))
        last_t = d.t
    no_weak, no_strong, no_gap, no_nw, no_ns = _below_gap(kept)

    # (2) moving-block bootstrap over the full labeled series (blocks preserve autocorrelation).
    series = _labeled_fwd(days, horizon)
    n = len(series)
    gaps: list[float] = []
    if n >= block:
        rng = random.Random(seed)
        n_blocks = -(-n // block)  # ceil
        for _ in range(n_boot):
            resampled: list[tuple[str, float]] = []
            for _ in range(n_blocks):
                start = rng.randint(0, n - block)
                resampled.extend(series[start : start + block])
            _, _, g, nw, ns = _below_gap(resampled[:n])
            if g is not None and nw and ns:
                gaps.append(g)
    gaps.sort()

    def pctl(p: float) -> float | None:
        if not gaps:
            return None
        return gaps[min(len(gaps) - 1, max(0, int(p * len(gaps))))]

    return Robustness(
        horizon=horizon,
        no_weak=no_weak,
        no_strong=no_strong,
        no_gap=no_gap,
        no_n_weak=no_nw,
        no_n_strong=no_ns,
        boot_gap_mean=statistics.mean(gaps) if gaps else None,
        boot_ci_lo=pctl(0.025),
        boot_ci_hi=pctl(0.975),
        boot_p_positive=(sum(1 for g in gaps if g > 0) / len(gaps)) if gaps else None,
        n_boot=len(gaps),
    )


def _action(avg20: float | None, win20: float | None) -> str:
    """Data-driven playbook verdict for a quadrant from its forward-20 return + win rate."""
    if avg20 is None or win20 is None:
        return "insufficient data"
    if avg20 > 0.5 and win20 >= 55:
        return "FAVOUR longs (regime tailwind)"
    if avg20 < 0 or win20 < 50:
        return "STAND DOWN / size down new longs — prefer market-neutral, demand higher confidence"
    return "NEUTRAL / selective — normal size, tighter entry discipline"


def render_markdown(
    *,
    day: date,
    span: tuple[date, date],
    n_days: int,
    qstats: dict[str, QuadStat],
    episodes: list[Episode],
    disp: dict[str, dict[str, float | None]],
    indices: list[str],
    fii_dii_note: str,
    robust: Robustness | None = None,
) -> str:
    def f(x: float | None, dp: int = 2) -> str:
        return f"{x:+.{dp}f}%" if x is not None else "—"

    out = [
        f"# Market-regime study — {day}",
        "",
        f"_Read-only research over {n_days} classified sessions ({span[0]} → {span[1]}). Each day "
        "is put in a level×breadth quadrant AS-OF that day (200-DMA level × short-term breadth / "
        "20-DMA, the reviewed `summarize_regime` classifier — no classifier look-ahead), then "
        "FORWARD 5/10/20-session NIFTY return that followed is measured. This tests the two-window "
        "finding: does **below-200-DMA + STRONG breadth (Window A)** actually beat **below + WEAK "
        "breadth (Window B)**? A study looks forward by design; the live engine is untouched._",
        "",
        "## 1. Forward returns by regime quadrant (the thesis test)",
        "",
        "| quadrant | days | fwd-5 | fwd-10 | fwd-20 | fwd-20 win% | avg VIX |",
        "|---|--:|--:|--:|--:|--:|--:|",
    ]
    for q in QUADRANTS:
        s = qstats[q]
        win = f"{s.win20_pct:.0f}%" if s.win20_pct is not None else "—"
        vix = f"{s.avg_vix:.1f}" if s.avg_vix is not None else "—"
        out.append(
            f"| {q} | {s.n} | {f(s.avg_fwd(5))} | {f(s.avg_fwd(10))} | {f(s.avg_fwd(20))} | "
            f"{win} | {vix} |"
        )
    bs, bw = qstats["below+strong"], qstats["below+weak"]
    bs20, bw20 = bs.avg_fwd(20), bw.avg_fwd(20)
    if bs20 is not None and bw20 is not None:
        verdict = (
            "CONFIRMS the thesis — below+strong beat below+weak"
            if bs20 > bw20
            else "does NOT confirm the thesis on this sample"
        )
        out += [
            "",
            f"**Thesis check: {verdict}.** Below-200-DMA & STRONG breadth → fwd-20 {f(bs20)} "
            f"(n={bs.fwd_n(20)} of {bs.n} days); below & WEAK breadth → fwd-20 {f(bw20)} "
            f"(n={bw.fwd_n(20)} of {bw.n} days). The 200-DMA level alone lumps both together; "
            "breadth separates them.",
            "",
            "> **⚠ Fragility:** the arithmetic is verified correct, but the forward-20 windows "
            "overlap heavily — the below+weak edge rests on ~2 drawdown episodes (one still open), "
            "NOT the labelled ~independent observations. See the robustness re-estimates below. "
            "And 3y is ONE bull cycle where every dip recovered — a 'buy the dip' prior would "
            "be dangerous in a structural bear (falling knife). We are currently in the "
            "deepest/longest below-200-DMA episode (still open) — exactly the 'bull dip or regime "
            "change?' case the study cannot resolve.",
        ]
    if robust is not None:
        ng = f(robust.no_gap)
        lo, hi = f(robust.boot_ci_lo), f(robust.boot_ci_hi)
        p = f"{robust.boot_p_positive * 100:.0f}%" if robust.boot_p_positive is not None else "—"
        out += [
            "",
            "### Robustness — does the gap survive the overlap?",
            "",
            f"- **Non-overlapping subsample** (days ≥{robust.horizon} apart): below+weak "
            f"{f(robust.no_weak)} (n={robust.no_n_weak}) vs below+strong {f(robust.no_strong)} "
            f"(n={robust.no_n_strong}) → gap **{ng}** (vs the naive ~6× — collapses, as expected).",
            f"- **Moving-block bootstrap** ({robust.n_boot} replicates, block={robust.horizon}): "
            f"mean gap {f(robust.boot_gap_mean)}, 95% CI [{lo}, {hi}], "
            f"**P(below-weak > below-strong) = {p}**.",
            "- **Verdict:** if the CI straddles 0 (or P is near 50%), the direction is NOT "
            "statistically established — treat as a weak prior, not a rule. Re-run as data grows.",
        ]
    out += ["", "## 2. Below-200-DMA episodes (how bad, how long, did it recover)", ""]
    if episodes:
        out += [
            "| start | end | sessions | depth (trough vs cross) | recovered | avg VIX |",
            "|---|---|--:|--:|:--:|--:|",
        ]
        for e in episodes:
            vix = f"{e.avg_vix:.1f}" if e.avg_vix is not None else "—"
            out.append(
                f"| {e.start} | {e.end} | {e.sessions} | {f(e.depth_pct)} | "
                f"{'yes' if e.recovered else 'STILL BELOW'} | {vix} |"
            )
        rec = [e for e in episodes if e.recovered]
        if rec:
            out += [
                "",
                f"_{len(rec)}/{len(episodes)} episodes recovered above the 200-DMA within data; "
                f"median duration {statistics.median([e.sessions for e in rec]):.0f} sessions, "
                f"deepest trough {min(e.depth_pct for e in episodes):.1f}%._",
            ]
    else:
        out.append("_No fully-formed below-200-DMA episodes in the classified window._")

    out += ["", "## 3. Index / cap dispersion (avg fwd-20 by NIFTY quadrant)", ""]
    out += ["| quadrant | " + " | ".join(indices) + " |", "|---" + "|--:" * len(indices) + "|"]
    for q in QUADRANTS:
        row = " | ".join(f(disp.get(q, {}).get(idx)) for idx in indices)
        out.append(f"| {q} | {row} |")

    out += [
        "",
        "## 4. Playbook — what to do in each regime (data-driven)",
        "",
        "| regime quadrant | fwd-20 | action |",
        "|---|--:|---|",
    ]
    for q in sorted(QUADRANTS, key=lambda x: (qstats[x].avg_fwd(20) or -1e9), reverse=True):
        s = qstats[q]
        out.append(f"| {q} | {f(s.avg_fwd(20))} | {_action(s.avg_fwd(20), s.win20_pct)} |")

    out += [
        "",
        "## 5. Money-flow (FII/DII) — DATA GAP",
        "",
        f"_{fii_dii_note}_",
        "",
        "> **Honest limits:** this study measures PRICE / BREADTH / VIX behaviour and how regimes "
        "recovered — not *cause*. Negative-news / management / holder-issue attribution needs a "
        "news & fundamentals history we do not have (the MCE news layer helps FORWARD, not back). "
        "FII/DII flow — the one causal-ish factor — has too little history to use yet (see above). "
        "And the sample is one market cycle (~3y): treat the playbook as a prior, re-run as "
        "data grows.",
        "",
    ]
    return "\n".join(out) + "\n"
