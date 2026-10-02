"""PR-1 — the study, written to the FROZEN pre-registration.

    uv run python scripts/pr1_study.py --synthetic [--seed 7]   # the full path on generated data
    uv run python scripts/pr1_study.py --dry                    # real data, outcome-FREE counts
    uv run python scripts/pr1_study.py --run-once               # THE run (guarded; see below)

**The text this implements is `docs/analysis/pr1-preregistration-v3.1-2026-10-02.md`, frozen at
commit `6f61c9e`** (sha256 below). Every clause number in this file (cl. N) refers to §4 of that
text. Where the text needed an interpretation to become code, the interpretation is written next
to the code AND listed in `INTERPRETATIONS`, so the reviewer can check each against the text
before the run (cl. 15: committed → code → **review** → run once → report).

## Why the three modes

- `--synthetic` runs the exact decision path on a generated panel (a planted reversal in the
  book, or none) — the way to see the code work without reading the test window.
- `--dry` reads the real window but prints only OUTCOME-FREE counts (pairs, cohort sizes, drops,
  slots, qty-0 and carried slots). They must reproduce §8 of the text (748 pairs, 3,740 slots,
  187 strict basis-step drops); a mismatch is a bug in this file, found before the run.
- `--run-once` is the single real run. It refuses unless: the frozen text's hash matches; this
  file and the text are committed with no local edits; the freeze commit is on a remote (a
  third-party timestamp); every cl. 14 descriptive is implemented; and no run receipt exists.
  It writes the receipt BEFORE reading any outcome, so a crash mid-run still counts as the run.

## Reuse (W2)

The calendar, the pair rule, the mismatch-session list and the cl. 3 drops (split/bonus +
strict basis steps) are imported from `pr1_design_facts.py`, where they were verified against §8
by three quant-verifier passes. This file adds the outcomes and the decision, nothing parallel.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import statistics
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.block_bootstrap import newey_west_t  # noqa: E402
from app.services.deflated_sharpe import deflated_sharpe  # noqa: E402
from app.trading.fees import roundtrip_charges  # noqa: E402

_ROOT = Path(__file__).resolve().parents[2]
FROZEN_TEXT = _ROOT / "docs/analysis/pr1-preregistration-v3.1-2026-10-02.md"
FROZEN_SHA256 = "9a47dac0ac457c32d5708660e2bae4ad3e6f8946895e93772dd73f78573f258a"
FREEZE_COMMIT = "6f61c9ec757a9c922eab44674f7be3f4de1ac3e5"
RECEIPT = _ROOT / "docs/analysis/pr1-run-receipt.json"

# ── cl. 2, 6, 7, 9–12: the frozen numbers ────────────────────────────────────────────────────
WINDOW_LO, WINDOW_HI = date(2023, 7, 3), date(2026, 7, 31)
BOOK_K = 5
PER_NAME_INR = Decimal("20000")
H_PASS_BPS, H_KILL_BPS = 2.68, 1.76  # cl. 7 bracket: top decides PASS, bottom the cost KILL
LAG = 10  # cl. 10: ⌈748^(1/3)⌉
TRIALS = 22  # cl. 9–10
BAR_T = 3.5954  # cl. 11
DSR_MIN = 0.95
Z90 = 1.6448536269514722
K3_DROP = 15  # cl. 12
K4_SPLIT = date(2025, 2, 1)
K6_TOP, K6_SHARE = 3, 0.5

#: Every place the text needed a reading to become code. The reviewer checks each one against
#: the frozen text BEFORE the run; changing one after the run is a new trial.
INTERPRETATIONS: tuple[str, ...] = (
    "I1 (cl. 3, 5): a NON-book cohort name's outcome is 'defined' only when its own prices exist "
    "(R_on: a 09:15 bar on t+1; R_day: a 09:15 and a 15:05 bar on t+1). The carry rules are "
    "applied to BOOK slots only, as cl. 3 states them ('a book name with missing t+1 data').",
    "I2 (cl. 3, 7): an MIS book slot with bars on t+1 but none at or before 15:05 has no "
    "'latest earlier bar'; it is treated as never entered (counted), like a suspended slot.",
    "I3 (cl. 6): a session where no book slot is bought or entered (k_t = 0) has no session "
    "return; it is left out of that branch's series and counted (PR-1's text is silent; §9a a5 "
    "states the same rule for PR-2).",
    "I4 (cl. 8, 12): Spearman IC with average ranks for ties, over names with a defined outcome; "
    "a session with fewer than 3 such names contributes no IC (counted).",
    "I5 (cl. 10–11): the 90% CI is mean ± 1.645·SE with SE = |mean| ÷ |NW t| (the house "
    "Newey–West at lag 10), so the CI and the t share one variance estimate.",
    "I6 (cl. 13): the label's per-session OLS has an intercept, over cohort names with a defined "
    "chosen outcome and all three regressors; with an intercept, 'all demeaned' does not move "
    "the slopes. CI(β_s − β_pre) is the cl.-10 CI of the per-session difference series.",
)

#: cl. 14 descriptives. `--run-once` refuses until every one is implemented, because the study
#: runs ONCE and all of them must come out of that run.
DESCRIPTIVES_PENDING: tuple[str, ...] = (
    "weekday × expiry type (P6)",
    "VIX terciles (P4)",
    "late-volume terciles (P3)",
    "the long-short intraday variant",
    "the executable R_on from C_t (daily file) and G = P1530_t ÷ C_t − 1",
    "a concentration panel (best-5% share; tagged expiry and index-event days)",
    "a balanced-subsample rerun (names present in every session)",
    "a rerun that also drops the transient basis-step name-nights",
    "the CNC branch with s ending at P1525",
    "the decision series regressed on the equal-weight cohort return",
)


# ── data ─────────────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Bars:
    """One (name, session) of the 5-minute table (bars stamped by START time, IST)."""

    nb: int
    o915: float | None  # open of the bar stamped 09:15 = the official open where bases agree
    first_open: float | None  # open of the session's first bar (cl. 3 carry)
    p1510: float | None  # close of the bar stamped 15:05, else of the latest earlier bar (cl. 3)
    p1515: float | None  # close of the bar stamped 15:10
    p1525: float | None  # close of the bar stamped 15:20 (cl. 14 variant)
    p1530: float | None  # close of the bar stamped 15:25


@dataclass(frozen=True)
class PairInput:
    """Everything one (t, t+1) pair needs. The cohort is AFTER the cl. 3 drops."""

    t: date
    t1: date
    cohort: tuple[int, ...]
    symbol: dict[int, str]
    close_t: dict[int, Decimal]  # C_t, the official close (daily file, traded basis)
    bars_t: dict[int, Bars]
    bars_t1: dict[int, Bars]  # every name with ANY bar on t+1
    bars_tm1: dict[int, Bars] | None  # the previous non-special session; None for the first


@dataclass
class SessionRecord:
    t: date
    n_cohort: int
    net: dict[str, dict[float, float | None]]  # branch → h → session net (None: k_t = 0)
    net_whole: dict[str, float | None]  # whole-cohort-demeaned, h = H_PASS (cl. 14)
    net_raw: dict[str, float | None]  # raw outcome, h = H_PASS (cl. 14)
    ic_all: dict[str, float | None]  # cl. 8, whole cohort
    ic_quint: dict[str, float | None]  # cl. 12 K2, bottom quintile
    label: dict[str, tuple[float, float, float] | None]  # β_s, β_pre, β_gap per branch
    slot_net: dict[str, list[tuple[int, float, int]]]  # (name, net_i at H_PASS, k_t)
    counts: dict[str, int] = field(default_factory=dict)


# ── cl. 3–7: one session ─────────────────────────────────────────────────────────────────────
def _order(cohort: Sequence[int], s: dict[int, float], symbol: dict[int, str]) -> list[int]:
    """Ranks of s, ascending, ties broken by ascending symbol (cl. 3, 6)."""
    return sorted(cohort, key=lambda i: (s[i], symbol[i]))


def _spearman(x: Sequence[float], y: Sequence[float]) -> float | None:
    if len(x) < 3:
        return None
    import warnings

    from scipy.stats import spearmanr  # deferred: heavy, and only needed on the decision path

    with warnings.catch_warnings():  # a constant input is undefined → None below (I4)
        warnings.simplefilter("ignore")
        rho = float(spearmanr(x, y).statistic)
    return None if math.isnan(rho) else rho


def _ols_slopes(y: list[float], xs: list[list[float]]) -> tuple[float, ...] | None:
    if len(y) < len(xs) + 3:
        return None
    a = np.column_stack([np.ones(len(y)), *[np.asarray(c) for c in xs]])
    beta, *_ = np.linalg.lstsq(a, np.asarray(y), rcond=None)
    return tuple(float(b) for b in beta[1:])


def _fee_frac(price: Decimal, qty: int, product: str, entry_on: date, exit_on: date) -> float:
    """cl. 7: the §5 fee model, both legs priced at C_t, each leg on its own day."""
    total, _ = roundtrip_charges(
        position_side="LONG", entry_price=price, exit_price=price, quantity=qty,
        product=product, entry_on=entry_on, exit_on=exit_on,
    )
    return float(total) / float(price * qty)


def _outcomes(p: PairInput, c: Sequence[int]) -> dict[str, dict[int, float]]:
    """cl. 5, for names whose own prices exist (I1)."""
    r_on: dict[int, float] = {}
    r_day: dict[int, float] = {}
    for i in c:
        b1 = p.bars_t1.get(i)
        p1530 = p.bars_t[i].p1530
        if b1 is None or b1.o915 is None or p1530 is None:
            continue
        r_on[i] = b1.o915 / p1530 - 1.0
        if b1.p1510 is not None:
            r_day[i] = b1.p1510 / b1.o915 - 1.0
    return {"cnc": r_on, "mis": r_day}


def _slot(p: PairInput, i: int, branch: str, r: dict[int, float],
          counts: dict[str, int]) -> tuple[float, float] | None:
    """cl. 3, 6, 7 for ONE book slot: (raw outcome, fee fraction), or None if not taken."""
    qty = int(PER_NAME_INR // p.close_t[i])
    if qty == 0:
        counts["qty0"] += 1
        return None
    b1 = p.bars_t1.get(i)
    p1530 = p.bars_t[i].p1530
    assert p1530 is not None  # cohort names have it (cl. 3: all 75 bars on t)
    if branch == "cnc":
        if b1 is None:  # cl. 3: suspended ⇒ R_on = 0, carried, pays the round trip
            counts["cnc_carried_suspended"] += 1
            raw = 0.0
        elif i in r:
            raw = r[i]
        elif b1.first_open is not None:  # no 09:15 bar ⇒ the open of the first bar of t+1
            counts["cnc_carried_open"] += 1
            raw = b1.first_open / p1530 - 1.0
        else:
            counts["cnc_carried_suspended"] += 1
            raw = 0.0
        return raw, _fee_frac(p.close_t[i], qty, "delivery", p.t, p.t1)
    if b1 is None or b1.p1510 is None:  # cl. 3/7 never entered; I2
        counts["mis_not_entered"] += 1
        return None
    o = b1.o915 if b1.o915 is not None else b1.first_open
    if o is None:
        counts["mis_not_entered"] += 1
        return None
    if b1.o915 is None:
        counts["mis_carried_open"] += 1
    return b1.p1510 / o - 1.0, _fee_frac(p.close_t[i], qty, "intraday", p.t1, p.t1)


def _label_slopes(p: PairInput, c: Sequence[int], s: dict[int, float],
                  r: dict[int, float]) -> tuple[float, float, float] | None:
    """cl. 13 for one session: OLS slopes of the outcome on s, r_pre and gap (I6)."""
    if p.bars_tm1 is None:  # the first session is skipped
        return None
    y: list[float] = []
    x_s: list[float] = []
    x_pre: list[float] = []
    x_gap: list[float] = []
    for i in c:
        prev = p.bars_tm1.get(i)
        bt = p.bars_t[i]
        if (i not in r or prev is None or prev.p1530 is None or bt.o915 is None
                or bt.p1515 is None):
            continue
        y.append(r[i])
        x_s.append(s[i])
        x_pre.append(bt.p1515 / bt.o915 - 1.0)
        x_gap.append(bt.o915 / prev.p1530 - 1.0)
    sl = _ols_slopes(y, [x_s, x_pre, x_gap])
    return None if sl is None else (sl[0], sl[1], sl[2])


def _late_move(p: PairInput) -> tuple[list[int], dict[int, float]]:
    """cl. 4: s = (P1530 − P1515) ÷ P1515, demeaned across the cohort."""
    c = [i for i in p.cohort if p.bars_t[i].p1515 and p.bars_t[i].p1530]
    raw = {i: p.bars_t[i].p1530 / p.bars_t[i].p1515 - 1.0  # type: ignore[operator]
           for i in c}
    m = statistics.fmean(raw.values())
    return c, {i: v - m for i, v in raw.items()}


def evaluate_session(p: PairInput) -> SessionRecord:
    c, s = _late_move(p)
    order = _order(c, s, p.symbol)
    n = len(order)
    quint, mid, book = order[: n // 5], order[n // 3 : 2 * n // 3], order[:BOOK_K]
    counts = dict.fromkeys(("qty0", "cnc_carried_suspended", "cnc_carried_open",
                            "mis_not_entered", "mis_carried_open", "cnc_k0", "mis_k0"), 0)
    outcome = _outcomes(p, c)

    def base(r: dict[int, float], names: Sequence[int]) -> float:
        vals = [r[i] for i in names if i in r]
        return statistics.fmean(vals) if vals else 0.0

    net: dict[str, dict[float, float | None]] = {}
    net_whole: dict[str, float | None] = {}
    net_raw: dict[str, float | None] = {}
    slot_net: dict[str, list[tuple[int, float, int]]] = {}
    for branch, r in outcome.items():
        mid_mean, whole_mean = base(r, mid), base(r, c)  # cl. 5 decision base / cl. 14
        slots = [(i, *x) for i in book if (x := _slot(p, i, branch, r, counts)) is not None]
        k = len(slots)
        if k == 0:  # I3
            net[branch] = {H_PASS_BPS: None, H_KILL_BPS: None}
            net_whole[branch] = net_raw[branch] = None
            slot_net[branch] = []
            counts[f"{branch}_k0"] = 1
            continue

        def mean_net(shift: float, h: float, sl: list[tuple[int, float, float]] = slots) -> float:
            return statistics.fmean(raw - shift - fee - 2 * h / 1e4 for _, raw, fee in sl)

        net[branch] = {h: mean_net(mid_mean, h) for h in (H_PASS_BPS, H_KILL_BPS)}
        net_whole[branch] = mean_net(whole_mean, H_PASS_BPS)
        net_raw[branch] = mean_net(0.0, H_PASS_BPS)
        slot_net[branch] = [(i, raw - mid_mean - fee - 2 * H_PASS_BPS / 1e4, k)
                            for i, raw, fee in slots]

    def ic(names: Sequence[int], r: dict[int, float]) -> float | None:
        kept = [i for i in names if i in r]
        return _spearman([s[i] for i in kept], [r[i] for i in kept])

    return SessionRecord(
        p.t, n, net, net_whole, net_raw,
        {b: ic(c, r) for b, r in outcome.items()},
        {b: ic(quint, r) for b, r in outcome.items()},
        {b: _label_slopes(p, c, s, r) for b, r in outcome.items()},
        slot_net, counts,
    )


# ── cl. 9–13: the decision ───────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class SeriesStats:
    n: int
    mean: float
    t: float | None
    ci: tuple[float, float] | None


def series_stats(x: Sequence[float]) -> SeriesStats:
    """cl. 10: NW t at lag 10; 90% CI = mean ± 1.645·SE, SE from the same NW variance (I5)."""
    n = len(x)
    m = statistics.fmean(x) if n else float("nan")
    t = newey_west_t(list(x), lag=LAG) if n > LAG + 2 else None
    ci = None
    if t is not None and t != 0:
        se = abs(m) / abs(t)
        ci = (m - Z90 * se, m + Z90 * se)
    return SeriesStats(n, m, t, ci)


@dataclass
class Decision:
    branch: str
    verdict: str  # PASS / KILL / NULL
    reasons: list[str]
    stats: dict[str, object]


def _series(records: Sequence[SessionRecord], b: str, h: float) -> list[tuple[date, float]]:
    return [(r.t, v) for r in records if (v := r.net[b][h]) is not None]


def _robustness_kills(records: Sequence[SessionRecord], branch: str,
                      xs: list[tuple[date, float]]) -> tuple[bool, bool, bool]:
    """cl. 12 K3, K4, K6 — checked only on a would-be PASS."""
    x = [v for _, v in xs]
    # sorted ascending, so dropping the last K3_DROP removes the largest sessions
    k3 = statistics.fmean(sorted(x)[: len(x) - K3_DROP]) <= 0 if len(x) > K3_DROP else True
    first = [v for d, v in xs if d < K4_SPLIT]
    second = [v for d, v in xs if d >= K4_SPLIT]
    k4 = bool(first and second) and (
        math.copysign(1, statistics.fmean(first)) != math.copysign(1, statistics.fmean(second)))
    contrib: dict[int, float] = {}
    for r in records:
        for i, v, k in r.slot_net[branch]:
            contrib[i] = contrib.get(i, 0.0) + v / k
    total = sum(contrib.values())
    k6 = sum(sorted(contrib.values(), reverse=True)[:K6_TOP]) > K6_SHARE * total
    return k3, k4, k6


def decide(records: Sequence[SessionRecord]) -> Decision:
    t_of = {b: series_stats([v for _, v in _series(records, b, H_PASS_BPS)]).t
            for b in ("cnc", "mis")}
    # cl. 9: the higher NW t of the NET series at h = 2.68 decides
    branch = max(("cnc", "mis"), key=lambda b: -math.inf if (v := t_of[b]) is None else v)
    xs = _series(records, branch, H_PASS_BPS)
    x = [v for _, v in xs]
    st = series_stats(x)
    st_kill = series_stats([v for _, v in _series(records, branch, H_KILL_BPS)])
    dsr = deflated_sharpe(x, trials=TRIALS)
    ic_q = [v for r in records if (v := r.ic_quint[branch]) is not None]
    mean_ic = statistics.fmean(ic_q) if ic_q else None
    k2 = mean_ic is not None and mean_ic >= 0
    cost_kill = st_kill.ci is not None and st_kill.ci[1] < 0
    would_pass = (st.t is not None and st.t >= BAR_T and dsr is not None
                  and dsr.dsr >= DSR_MIN)
    k3, k4, k6 = _robustness_kills(records, branch, xs) if would_pass else (False, False, False)
    fired = [("K2: bottom-quintile IC ≥ 0", k2),
             ("cost KILL: 90% CI upper bound of net(h = 1.76) < 0", cost_kill),
             ("K3 on a would-be PASS", k3), ("K4 on a would-be PASS", k4),
             ("K6 on a would-be PASS", k6)]
    reasons = [name for name, f in fired if f]
    verdict = "KILL" if reasons else "PASS" if would_pass else "NULL"
    return Decision(branch, verdict, reasons, {
        "t_by_branch": t_of, "n": st.n, "mean": st.mean, "t": st.t, "ci90": st.ci,
        "ci90_h176": st_kill.ci, "dsr": None if dsr is None else dsr.dsr,
        "skew": None if dsr is None else dsr.moments.skew,
        "kurtosis": None if dsr is None else dsr.moments.kurtosis,
        "k2_mean_ic_quintile": mean_ic, "would_pass": would_pass,
        "k3": k3, "k4": k4, "k6": k6,
    })


def mechanism_label(records: Sequence[SessionRecord], branch: str) -> dict[str, object]:
    """cl. 13 — reported with the decision, never changes it."""
    rows = [r.label[branch] for r in records if r.label[branch] is not None]
    b_s = series_stats([v[0] for v in rows])  # type: ignore[index]
    diff = series_stats([v[0] - v[1] for v in rows])  # type: ignore[index]
    neg = b_s.ci is not None and b_s.ci[1] < 0
    label = ("close-specific" if neg and diff.ci is not None and diff.ci[1] < 0
             else "generic reversal" if neg else "none")
    return {"label": label, "beta_s": b_s, "beta_s_minus_pre": diff, "sessions": len(rows)}


# ── synthetic panel (no market data) ─────────────────────────────────────────────────────────
def synthetic_pairs(seed: int, n_pairs: int = 748, n_names: int = 204,
                    edge_bps: float = 0.0) -> list[PairInput]:
    """A generated window with the real shapes — no market data. Each session: an open, a
    15:10 price, a late move to 15:25, a 15:05 price; the next open follows an overnight return
    in which the 5 most negative late moves get `edge_bps` of reversal planted."""
    rng = np.random.default_rng(seed)
    syms = {i: f"S{i:03d}" for i in range(n_names)}
    days = [date.fromordinal(WINDOW_LO.toordinal() + k) for k in range(n_pairs + 1)]
    sessions: list[dict[int, Bars]] = []
    closes: list[dict[int, Decimal]] = []
    price = rng.uniform(100, 3000, n_names)
    for _ in days:
        o = price
        p1515 = o * np.exp(rng.normal(0, 0.012, n_names))
        late = rng.normal(0, 0.006, n_names)
        p1530 = p1515 * np.exp(late)
        sessions.append({
            i: Bars(75, float(o[i]), float(o[i]), float(p1515[i] * 0.999), float(p1515[i]),
                    float(p1515[i] * math.exp(0.8 * late[i])), float(p1530[i]))
            for i in range(n_names)
        })
        closes.append({i: Decimal(str(round(float(p1530[i]), 2))) for i in range(n_names)})
        overnight = rng.normal(0, 0.008, n_names)
        overnight[np.argsort(late - late.mean())[:BOOK_K]] += edge_bps / 1e4
        price = p1530 * np.exp(overnight)
    return [
        PairInput(days[k], days[k + 1], tuple(range(n_names)), syms, closes[k], sessions[k],
                  sessions[k + 1], sessions[k - 1] if k else None)
        for k in range(n_pairs)
    ]


# ── real data ────────────────────────────────────────────────────────────────────────────────
def _assert_outside_holdouts(lo: date, hi: date) -> None:
    """The loader refuses any window touching a sealed block — the guard M93 lacked."""
    from holdout_seal import BLOCKS

    # Only the HOLDOUT blocks are sealed; `test` is the working block this study lives in.
    for b in (b for b in BLOCKS if str(b["name"]).startswith("holdout")):
        if lo <= b["hi"] and b["lo"] <= hi:
            raise SystemExit(f"refused: {lo}→{hi} overlaps the sealed block {b['name']}")


async def _load_bars(lo: date, hi: date) -> dict[date, dict[int, Bars]]:
    from app.db.session import AsyncSessionFactory
    from sqlalchemy import text

    sql = text("""
        SELECT stock_id, (time AT TIME ZONE 'Asia/Kolkata')::date AS d, count(*) AS nb,
               max(open)  FILTER (WHERE (time AT TIME ZONE 'Asia/Kolkata')::time = '09:15'),
               (array_agg(open ORDER BY time))[1],
               (array_agg(close ORDER BY time DESC)
                  FILTER (WHERE (time AT TIME ZONE 'Asia/Kolkata')::time <= '15:05'))[1],
               max(close) FILTER (WHERE (time AT TIME ZONE 'Asia/Kolkata')::time = '15:10'),
               max(close) FILTER (WHERE (time AT TIME ZONE 'Asia/Kolkata')::time = '15:20'),
               max(close) FILTER (WHERE (time AT TIME ZONE 'Asia/Kolkata')::time = '15:25')
        FROM ohlcv_5m
        WHERE time >= (CAST(:lo AS date)::timestamp AT TIME ZONE 'Asia/Kolkata')
          AND time <  ((CAST(:hi AS date) + 1)::timestamp AT TIME ZONE 'Asia/Kolkata')
        GROUP BY 1, 2""")
    out: dict[date, dict[int, Bars]] = {}
    async with AsyncSessionFactory() as s:
        await s.execute(text("SET TRANSACTION READ ONLY"))
        for sid, d, nb, o915, fo, p1510, p1515, p1525, p1530 in (
                await s.execute(sql, {"lo": lo, "hi": hi})).all():
            def f(v: object) -> float | None:
                return None if v is None else float(v)  # type: ignore[arg-type]
            out.setdefault(d, {})[int(sid)] = Bars(int(nb), f(o915), f(fo), f(p1510), f(p1515),
                                                    f(p1525), f(p1530))
    return out


async def load_real() -> tuple[list[PairInput], dict[str, int]]:
    """The cohort machinery of `pr1_design_facts` (W2), plus the 5-minute prices."""
    import pr1_design_facts as df

    _assert_outside_holdouts(WINDOW_LO, WINDOW_HI)
    days, per_day, daily_cal, ex_dates = await df._load(WINDOW_LO, WINDOW_HI)
    qual = {d for d in days if len(per_day[d]) >= df._MIN_NAMES}
    pairs = df._pairs(daily_cal, qual)
    bars = await _load_bars(WINDOW_LO, WINDOW_HI)
    out: list[PairInput] = []
    drops = 0
    for t, t1 in pairs:
        drop = df._drop(t, t1, ex_dates)
        kept = [x for x in per_day[t] if x.stock_id not in drop]
        drops += len(per_day[t]) - len(kept)
        tm1 = df._prev_session.get(t)
        out.append(PairInput(
            t, t1, tuple(x.stock_id for x in kept), {x.stock_id: x.symbol for x in per_day[t]},
            {x.stock_id: x.close_traded for x in kept}, bars.get(t, {}), bars.get(t1, {}),
            bars.get(tm1) if tm1 is not None and tm1 >= WINDOW_LO else None,
        ))
    return out, {"pairs": len(pairs), "cohort_drops": drops}


def outcome_free_counts(pairs: Sequence[PairInput]) -> dict[str, int]:
    """--dry: what can be counted WITHOUT forming a return. Must match §8 of the text."""
    slots = qty0 = suspended = no915 = no1505 = 0
    for p in pairs:
        c = [i for i in p.cohort if p.bars_t[i].p1515 and p.bars_t[i].p1530]
        raw = {i: p.bars_t[i].p1530 / p.bars_t[i].p1515 - 1.0 for i in c}  # type: ignore[operator]
        m = statistics.fmean(raw.values())
        for i in _order(c, {i: v - m for i, v in raw.items()}, p.symbol)[:BOOK_K]:
            slots += 1
            qty0 += int(PER_NAME_INR // p.close_t[i]) == 0
            b1 = p.bars_t1.get(i)
            suspended += b1 is None
            no915 += b1 is not None and b1.o915 is None
            no1505 += b1 is not None and b1.p1510 is None
    return {"book_slots": slots, "qty0": qty0, "suspended_t1": suspended,
            "no_0915_bar_t1": no915, "no_bar_by_1505_t1": no1505}


# ── run-once guard ───────────────────────────────────────────────────────────────────────────
def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=_ROOT, capture_output=True, text=True,
                          check=False).stdout.strip()


def run_once_preflight() -> list[str]:
    """Every reason the real run must NOT start. Empty ⇒ it may."""
    problems = []
    if _sha(FROZEN_TEXT) != FROZEN_SHA256:
        problems.append("the frozen text's sha256 does not match the freeze")
    if _git("status", "--porcelain", "--", str(FROZEN_TEXT), __file__):
        problems.append("this script or the frozen text has uncommitted changes")
    if not _git("branch", "-r", "--contains", FREEZE_COMMIT):
        problems.append("the freeze commit is not on any remote (push it: third-party timestamp)")
    if DESCRIPTIVES_PENDING:
        problems.append(f"{len(DESCRIPTIVES_PENDING)} cl. 14 descriptives are not implemented")
    if RECEIPT.exists():
        problems.append(f"a run receipt already exists ({RECEIPT.name}): PR-1 runs ONCE")
    return problems


def _write_receipt() -> None:
    RECEIPT.write_text(json.dumps({
        "started_at": datetime.now(tz=UTC).isoformat(),
        "head": _git("rev-parse", "HEAD"),
        "script_sha256": _sha(Path(__file__)),
        "frozen_text_sha256": FROZEN_SHA256,
        "freeze_commit": FREEZE_COMMIT,
    }, indent=2) + "\n")


# ── report ───────────────────────────────────────────────────────────────────────────────────
def report(records: Sequence[SessionRecord]) -> Decision:
    d = decide(records)
    print(f"\nsessions {len(records)} · chosen branch {d.branch.upper()} "
          f"(NW t: CNC {d.stats['t_by_branch']['cnc']}, MIS {d.stats['t_by_branch']['mis']})")  # type: ignore[index]
    print(f"VERDICT: {d.verdict}" + (f" — {'; '.join(d.reasons)}" if d.reasons else ""))
    for k, v in d.stats.items():
        if k != "t_by_branch":
            print(f"  {k}: {v}")
    for b in ("cnc", "mis"):
        e1 = series_stats([r.ic_all[b] for r in records if r.ic_all[b] is not None])  # type: ignore[misc]
        whole = series_stats([r.net_whole[b] for r in records if r.net_whole[b] is not None])  # type: ignore[misc]
        raw = series_stats([r.net_raw[b] for r in records if r.net_raw[b] is not None])  # type: ignore[misc]
        print(f"  {b.upper()}: E1 mean IC {e1.mean:+.4f} (t {e1.t}) · whole-cohort-demeaned net "
              f"t {whole.t} · raw net t {raw.t}")
    lab = mechanism_label(records, d.branch)
    print(f"  mechanism label ({d.branch.upper()}): {lab['label']} over {lab['sessions']} sessions")
    totals: dict[str, int] = {}
    for r in records:
        for k, v in r.counts.items():
            totals[k] = totals.get(k, 0) + v
    print(f"  counts: {totals}")
    return d


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--synthetic", action="store_true")
    g.add_argument("--dry", action="store_true")
    g.add_argument("--run-once", action="store_true")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--edge-bps", type=float, default=0.0, help="synthetic: planted reversal")
    a = ap.parse_args()
    if a.synthetic:
        recs = [evaluate_session(p) for p in synthetic_pairs(a.seed, edge_bps=a.edge_bps)]
        report(recs)
        return
    if a.dry:
        pairs, meta = asyncio.run(load_real())
        print({**meta, **outcome_free_counts(pairs)})
        print("pending cl. 14 descriptives:", len(DESCRIPTIVES_PENDING))
        return
    problems = run_once_preflight()
    if problems:
        raise SystemExit("refused:\n  - " + "\n  - ".join(problems))
    _write_receipt()  # BEFORE any outcome is read: a crash still counts as the run
    pairs, _ = asyncio.run(load_real())
    report([evaluate_session(p) for p in pairs])


if __name__ == "__main__":
    main()
