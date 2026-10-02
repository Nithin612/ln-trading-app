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
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
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
RUN_OUTPUT = _ROOT / "docs/analysis/pr1-run-output.txt"  # everything the run prints (tee)
RUN_RESULT = _ROOT / "docs/analysis/pr1-run-result.json"  # the decision's numbers
#: The files whose content decides the run, named explicitly. The receipt hashes these PLUS
#: every repo module actually imported and the lockfile (`_hashed_files`), and the run refuses on
#: any uncommitted change under `GUARDED_PATHSPEC` (quant-verifier 2026-10-02, #4 and N4).
GUARDED = (
    Path(__file__).resolve(),
    FROZEN_TEXT,
    _ROOT / "backend/scripts/pr1_design_facts.py",
    _ROOT / "backend/scripts/holdout_seal.py",
    _ROOT / "backend/app/trading/fees.py",
    _ROOT / "backend/app/services/block_bootstrap.py",
    _ROOT / "backend/app/services/deflated_sharpe.py",
)

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
    "I7 (cl. 5, 14): G = P1530_t ÷ C_t − 1 mixes the two tables, so it is computed only for book "
    "slots whose bases agree EXACTLY on t (official open = 09:15-bar open), where both are on "
    "the traded basis; the count of slots used is printed.",
    "I8 (cl. 14 P6): expiry type of session t — 'monthly' = the last nominal expiry weekday of "
    "the month (Thursday before 2025-09-01, Tuesday after), 'weekly' = any other nominal expiry "
    "weekday (Nifty weeklies), 'none' otherwise; a holiday moves it to the previous session.",
    "I9 (cl. 14 P3): a slot's late volume = the volume of the bars stamped 15:15–15:25 ÷ the "
    "session's volume, on t; terciles are cut over all book slots of the chosen branch.",
    "I10 (cl. 14): the long-short intraday variant = the MIS book (5 most negative s) plus a "
    "SHORT of the 5 most positive s, each slot ₹20,000, middle-tercile demeaned, intraday fees "
    "per side; the session value is the mean over all slots entered.",
    "I11 (cl. 14): the beta regression is OLS of the decision series on the equal-weight raw "
    "cohort outcome of the same branch; the alpha's t is the NW t (lag 10) of y − β·x.",
    "I12 (cl. 14): the VIX of session t is `india_vix_daily.close` on t; terciles over the "
    "sessions of the decision series.",
    "I13 (cl. 13): the label's t−1 is the previous session that is neither special NOR one of "
    "the three §10j mismatch sessions (the same neighbour rule as cl. 3's basis test); on "
    "2024-02-06, 2024-05-15 and 2025-01-21 the gap regressor therefore spans two sessions.",
    "I14 (cl. 14 variants): the variant books (executable, P1525, long-short) carry a name with "
    "no outcome at 0 (CNC) or skip it (MIS) instead of the first-bar-open carry — descriptive "
    "only; `--dry` shows no book slot needs a carry in this window.",
    "I15 (cl. 9): an exact tie in the two branches' NW t goes to CNC (the first listed).",
)

#: cl. 14 descriptives still to write. `--run-once` refuses while any is listed, because the study
#: runs ONCE and all of them must come out of that run.
DESCRIPTIVES_PENDING: tuple[str, ...] = ()

#: cl. 14 items that CANNOT be computed from the data the text names, with the reason. They are
#: reported as such; the reviewer rules on each before the run. Never filled with a guess.
DESCRIPTIVES_UNAVAILABLE: tuple[str, ...] = (
    "the index-event-day tag of the concentration panel: no index-event calendar exists in the "
    "data and the text names no source; inventing rebalancing dates would fabricate the tag",
)

#: NSE/FAOP/68747 (the text's §2): stock and Nifty derivatives expire on THURSDAY up to
#: 2025-08-31 and on TUESDAY from 2025-09-01; a holiday moves an expiry to the previous session.
EXPIRY_WEEKDAY_SWITCH = date(2025, 9, 1)


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
    vol: float = 0.0  # the session's total volume (cl. 14 P3)
    vol_late: float = 0.0  # volume of the bars stamped 15:15–15:25 (cl. 14 P3)
    p1505_exact: float | None = None  # close of the bar stamped EXACTLY 15:05 (no carry; I1)


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
    open1_daily: dict[int, Decimal] = field(default_factory=dict)  # official open, t+1 (cl. 14)
    basis_exact: frozenset[int] = frozenset()  # names whose bases agree exactly on t (I7)
    transient: frozenset[int] = frozenset()  # transient/mirror basis-step names (cl. 14 rerun)


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


def _fee_frac(price: Decimal, qty: int, product: str, entry_on: date, exit_on: date,
              side: str = "LONG") -> float:
    """cl. 7: the §5 fee model, both legs priced at C_t, each leg on its own day. The ONE fee
    path of this file — every variant goes through it."""
    total, _ = roundtrip_charges(
        position_side=side, entry_price=price, exit_price=price, quantity=qty,
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
        if b1.p1505_exact is not None:  # I1: a non-book outcome uses its own 15:05 bar only
            r_day[i] = b1.p1505_exact / b1.o915 - 1.0
    return {"cnc": r_on, "mis": r_day}


def _slot(p: PairInput, i: int, branch: str, r: dict[int, float],
          counts: dict[str, int]) -> tuple[float, float] | None:
    """cl. 3, 6, 7 for ONE book slot: (raw outcome, fee fraction), or None if not taken."""
    qty = int(PER_NAME_INR // p.close_t[i])
    if qty == 0:
        counts["qty0"] += branch == "cnc"  # once per SLOT (qty does not depend on the branch)
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
    if b1.p1505_exact is None:  # cl. 3: no 15:05 bar ⇒ the latest earlier bar — a carried slot
        counts["mis_carried_1505"] += 1
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
                            "mis_not_entered", "mis_carried_open", "mis_carried_1505", "cnc_k0",
                            "mis_k0", "cnc_mid_base_empty", "mis_mid_base_empty"), 0)
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
        if not any(i in r for i in mid):
            counts[f"{branch}_mid_base_empty"] = 1  # the base falls back to 0.0 — counted
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


# ── cl. 14: descriptives (reported, never decisive) ──────────────────────────────────────────
def _variant_net(p: PairInput, book: Sequence[int], base_mean: float, r: dict[int, float],
                 product: str, side: str = "LONG", carry_zero: bool = True) -> list[float]:
    """Slot nets of a variant book (h = 2.68). A name with no outcome is carried at 0 (CNC-like)
    or skipped (MIS-like); a SHORT slot earns −(R − base)."""
    out: list[float] = []
    sign = 1.0 if side == "LONG" else -1.0
    for i in book:
        qty = int(PER_NAME_INR // p.close_t[i])
        if qty == 0:
            continue
        if i in r:
            raw = r[i]
        elif carry_zero:
            raw = 0.0
        else:
            continue
        on = (p.t, p.t1) if product == "delivery" else (p.t1, p.t1)
        fee = _fee_frac(p.close_t[i], qty, product, on[0], on[1], side)
        out.append(sign * (raw - base_mean) - fee - 2 * H_PASS_BPS / 1e4)
    return out


@dataclass
class Extras:
    t: date
    exec_net: float | None  # CNC with R_on from C_t within the daily file
    g_bps: list[float]  # G per book slot whose bases agree exactly (I7)
    ls_net: float | None  # the long-short intraday variant (I10)
    p1525_net: float | None  # CNC with s ending at P1525
    cohort_ret: dict[str, float | None]  # equal-weight raw cohort outcome (I11)


def _mean_or_none(xs: Sequence[float]) -> float | None:
    return statistics.fmean(xs) if xs else None


def session_extras(p: PairInput) -> Extras:
    c, s = _late_move(p)
    order = _order(c, s, p.symbol)
    n = len(order)
    mid, book, top = order[n // 3 : 2 * n // 3], order[:BOOK_K], order[-BOOK_K:]
    out = _outcomes(p, c)

    def base(r: dict[int, float], names: Sequence[int]) -> float:
        vals = [r[i] for i in names if i in r]
        return statistics.fmean(vals) if vals else 0.0

    r_exec = {i: float(p.open1_daily[i] / p.close_t[i]) - 1.0 for i in c if i in p.open1_daily}
    exec_net = _mean_or_none(_variant_net(p, book, base(r_exec, mid), r_exec, "delivery"))
    g = [(p.bars_t[i].p1530 / float(p.close_t[i]) - 1.0) * 1e4  # type: ignore[operator]
         for i in book if i in p.basis_exact]
    mis = out["mis"]
    ls = (_variant_net(p, book, base(mis, mid), mis, "intraday", carry_zero=False)
          + _variant_net(p, top, base(mis, mid), mis, "intraday", side="SHORT",
                         carry_zero=False))
    s25_raw = {i: p.bars_t[i].p1525 / p.bars_t[i].p1515 - 1.0  # type: ignore[operator]
               for i in c if p.bars_t[i].p1525}
    m25 = statistics.fmean(s25_raw.values()) if s25_raw else 0.0
    order25 = _order(list(s25_raw), {i: v - m25 for i, v in s25_raw.items()}, p.symbol)
    n25 = len(order25)
    p25 = _variant_net(p, order25[:BOOK_K], base(out["cnc"], order25[n25 // 3 : 2 * n25 // 3]),
                       out["cnc"], "delivery")
    return Extras(p.t, exec_net, g, _mean_or_none(ls), _mean_or_none(p25),
                  {b: _mean_or_none(list(r.values())) for b, r in out.items()})


def expiry_types(cal: Sequence[date]) -> dict[date, str]:
    """I8: 'monthly' / 'weekly' per session of the exchange calendar (others absent)."""
    sessions = sorted(cal)
    have = set(sessions)

    def actual(nominal: date) -> date | None:  # a holiday moves it to the previous session
        d = nominal
        for _ in range(7):
            if d in have:
                return d
            d = date.fromordinal(d.toordinal() - 1)
        return None

    nominals: list[date] = []
    d = sessions[0]
    while d <= sessions[-1]:
        wd = 3 if d < EXPIRY_WEEKDAY_SWITCH else 1  # Thursday, then Tuesday
        if d.weekday() == wd:
            nominals.append(d)
        d = date.fromordinal(d.toordinal() + 1)
    last_of_month: dict[tuple[int, int], date] = {}
    for nd in nominals:
        last_of_month[(nd.year, nd.month)] = nd  # ascending ⇒ the last one wins
    out: dict[date, str] = {}
    for nd in nominals:
        a = actual(nd)
        if a is not None:
            out[a] = "monthly" if last_of_month[(nd.year, nd.month)] == nd else "weekly"
    return out


def _fmt(st_: SeriesStats, scale: float = 1e4, unit: str = "bps", dp: int = 2) -> str:
    t = "—" if st_.t is None else f"{st_.t:+.2f}"
    ci = ("—" if st_.ci is None
          else f"[{st_.ci[0] * scale:+.{dp}f}, {st_.ci[1] * scale:+.{dp}f}]")
    return f"n {st_.n} · mean {st_.mean * scale:+.{dp}f} {unit} · NW t {t} · 90% CI {ci}"


def _as_dict(st_: SeriesStats) -> dict[str, object]:
    return {"n": st_.n, "mean": st_.mean, "t": st_.t, "ci90": st_.ci}


def reported_series(records: Sequence[SessionRecord]) -> dict[str, dict[str, object]]:
    """E1 and the whole-cohort / raw series of both branches — printed AND saved (N1)."""
    out: dict[str, dict[str, object]] = {}
    for b in ("cnc", "mis"):
        out[b] = {
            "e1_ic": _as_dict(series_stats(
                [v for r in records if (v := r.ic_all[b]) is not None])),
            "net_whole_cohort": _as_dict(series_stats(
                [v for r in records if (v := r.net_whole[b]) is not None])),
            "net_raw": _as_dict(series_stats(
                [v for r in records if (v := r.net_raw[b]) is not None])),
        }
    return out


def _tercile_report(label: str, pairs_: Sequence[tuple[float, float]]) -> None:
    """Means by tercile of the first coordinate (cut on its own distribution)."""
    if len(pairs_) < 3:
        print(f"  {label}: too few observations")
        return
    xs = sorted(v for v, _ in pairs_)
    cut1, cut2 = xs[len(xs) // 3], xs[2 * len(xs) // 3]
    for name, lo, hi in (("low", -math.inf, cut1), ("mid", cut1, cut2), ("high", cut2, math.inf)):
        ys = [y for v, y in pairs_ if lo <= v < hi]
        print(f"  {label} {name}: n {len(ys)} · mean net "
              f"{(statistics.fmean(ys) * 1e4 if ys else float('nan')):+.2f} bps")


def describe(pairs: Sequence[PairInput], records: Sequence[SessionRecord], d: Decision,
             vix: dict[date, float], cal: Sequence[date]) -> None:
    """cl. 14 — every descriptive, on the CHOSEN branch unless stated. Never decisive."""
    b = d.branch
    nets = {r.t: v for r in records if (v := r.net[b][H_PASS_BPS]) is not None}
    ext = [session_extras(p) for p in pairs]
    exp = expiry_types(cal)
    print("\n── cl. 14 descriptives (never decisive) ──")
    print("  weekday × expiry type (P6), mean net bps (n):")
    for wd, name in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri")):
        cells = []
        for kind in ("monthly", "weekly", "none"):
            ys = [v for t, v in nets.items() if t.weekday() == wd and exp.get(t, "none") == kind]
            cells.append(f"{kind} {statistics.fmean(ys) * 1e4:+.1f} ({len(ys)})" if ys
                         else f"{kind} — (0)")
        print(f"    {name}: " + " · ".join(cells))
    _tercile_report("VIX tercile (P4)", [(vix[t], v) for t, v in nets.items() if t in vix])
    late = [(p.bars_t[i].vol_late / p.bars_t[i].vol, v)
            for p, r in zip(pairs, records, strict=True) for i, v, _ in r.slot_net[b]
            if p.bars_t[i].vol > 0]
    _tercile_report("late-volume tercile (P3, per slot)", late)
    ls = [e.ls_net for e in ext if e.ls_net is not None]
    print(f"  long-short intraday (I10): {_fmt(series_stats(ls))}")
    print(f"  executable R_on from C_t (daily file): "
          f"{_fmt(series_stats([e.exec_net for e in ext if e.exec_net is not None]))}")
    g = [v for e in ext for v in e.g_bps]
    if g:
        print(f"  G = P1530 ÷ C_t − 1 (I7): {len(g)} slots · mean {statistics.fmean(g):+.2f} bps "
              f"· median {statistics.median(g):+.2f} bps")
    print(f"  CNC with s ending at P1525: "
          f"{_fmt(series_stats([e.p1525_net for e in ext if e.p1525_net is not None]))}")
    vals = sorted(nets.values(), reverse=True)
    total = sum(vals)
    top = vals[: math.ceil(0.05 * len(vals))]
    exp_share = sum(v for t, v in nets.items() if t in exp)
    print(f"  concentration: best-5% sessions carry {sum(top) / total:.1%} of net · expiry "
          f"sessions {exp_share / total:.1%} of net ({sum(t in exp for t in nets)} sessions) · "
          f"index-event days: NOT COMPUTABLE (see DESCRIPTIVES_UNAVAILABLE)" if total else
          "  concentration: total net is 0 — shares undefined")
    present = set.intersection(*(set(p.cohort) for p in pairs)) if pairs else set()
    bal = [evaluate_session(replace(p, cohort=tuple(i for i in p.cohort if i in present)))
           for p in pairs] if len(present) >= 3 * BOOK_K else []
    if bal:
        print(f"  balanced subsample ({len(present)} names in every session): "
              f"{_fmt(series_stats(_vals(bal, b)))}")
    else:
        print(f"  balanced subsample: only {len(present)} names are in every session — too few")
    tr = [evaluate_session(replace(p, cohort=tuple(i for i in p.cohort if i not in p.transient)))
          for p in pairs]
    print(f"  rerun without transient basis-step name-nights "
          f"({sum(len(p.transient & set(p.cohort)) for p in pairs)} dropped): "
          f"{_fmt(series_stats(_vals(tr, b)))}")
    xy = [(e.cohort_ret[b], nets[e.t]) for e in ext
          if e.t in nets and e.cohort_ret[b] is not None]
    if len(xy) > LAG + 3:
        x = np.asarray([v for v, _ in xy])
        y = np.asarray([v for _, v in xy])
        beta = float(np.cov(x, y, ddof=1)[0, 1] / np.var(x, ddof=1))
        alpha = series_stats(list(y - beta * x))
        print(f"  on the equal-weight cohort return (I11): β {beta:+.3f} · alpha {_fmt(alpha)}")
    print(f"  unavailable: {'; '.join(DESCRIPTIVES_UNAVAILABLE)}")


def _vals(records: Sequence[SessionRecord], b: str) -> list[float]:
    return [v for r in records if (v := r.net[b][H_PASS_BPS]) is not None]


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
        vol = rng.lognormal(12, 1, n_names)
        sessions.append({
            i: Bars(75, float(o[i]), float(o[i]), float(p1515[i] * 0.999), float(p1515[i]),
                    float(p1515[i] * math.exp(0.8 * late[i])), float(p1530[i]),
                    float(vol[i]), float(vol[i] * rng.uniform(0.02, 0.12)),
                    float(p1515[i] * 0.999))
            for i in range(n_names)
        })
        closes.append({i: Decimal(str(round(float(p1530[i]), 2))) for i in range(n_names)})
        overnight = rng.normal(0, 0.008, n_names)
        overnight[np.argsort(late - late.mean())[:BOOK_K]] += edge_bps / 1e4
        price = p1530 * np.exp(overnight)
    return [
        PairInput(days[k], days[k + 1], tuple(range(n_names)), syms, closes[k], sessions[k],
                  sessions[k + 1], sessions[k - 1] if k else None,
                  {i: Decimal(str(round(b.o915 or 0.0, 2))) for i, b in sessions[k + 1].items()},
                  frozenset(range(n_names)))
        for k in range(n_pairs)
    ]


def synthetic_context(seed: int, pairs: Sequence[PairInput]) -> Context:
    rng = np.random.default_rng(seed + 1)
    return Context({p.t: float(rng.uniform(10, 30)) for p in pairs},
                   tuple([p.t for p in pairs] + [pairs[-1].t1]))


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
               max(close) FILTER (WHERE (time AT TIME ZONE 'Asia/Kolkata')::time = '15:25'),
               sum(volume),
               sum(volume) FILTER (WHERE (time AT TIME ZONE 'Asia/Kolkata')::time >= '15:15'),
               max(close) FILTER (WHERE (time AT TIME ZONE 'Asia/Kolkata')::time = '15:05')
        FROM ohlcv_5m
        WHERE time >= (CAST(:lo AS date)::timestamp AT TIME ZONE 'Asia/Kolkata')
          AND time <  ((CAST(:hi AS date) + 1)::timestamp AT TIME ZONE 'Asia/Kolkata')
        GROUP BY 1, 2""")
    out: dict[date, dict[int, Bars]] = {}
    async with AsyncSessionFactory() as s:
        await s.execute(text("SET TRANSACTION READ ONLY"))
        for sid, d, nb, o915, fo, p1510, p1515, p1525, p1530, vol, vlate, p1505 in (
                await s.execute(sql, {"lo": lo, "hi": hi})).all():
            def f(v: object) -> float | None:
                return None if v is None else float(v)  # type: ignore[arg-type]
            out.setdefault(d, {})[int(sid)] = Bars(int(nb), f(o915), f(fo), f(p1510), f(p1515),
                                                    f(p1525), f(p1530), f(vol) or 0.0,
                                                    f(vlate) or 0.0, f(p1505))
    return out


async def _load_daily_open_and_vix(lo: date, hi: date) -> tuple[
        dict[date, dict[int, Decimal]], dict[date, float]]:
    """The official open per (session, name) from the daily file, and India VIX closes."""
    from app.db.session import AsyncSessionFactory
    from sqlalchemy import text

    opens: dict[date, dict[int, Decimal]] = {}
    vix: dict[date, float] = {}
    async with AsyncSessionFactory() as s:
        await s.execute(text("SET TRANSACTION READ ONLY"))
        rows = (await s.execute(text("""
            SELECT stock_id, (time AT TIME ZONE 'Asia/Kolkata')::date, open FROM ohlcv_1d
            WHERE time >= (CAST(:lo AS date)::timestamp AT TIME ZONE 'Asia/Kolkata')
              AND time <  ((CAST(:hi AS date) + 1)::timestamp AT TIME ZONE 'Asia/Kolkata')
              AND open IS NOT NULL"""), {"lo": lo, "hi": hi})).all()
        for sid, d, o in rows:
            opens.setdefault(d, {})[int(sid)] = Decimal(o)
        for d, c in (await s.execute(text(
                "SELECT trade_date, close FROM india_vix_daily WHERE trade_date BETWEEN :lo AND :hi"
        ), {"lo": lo, "hi": hi})).all():
            vix[d] = float(c)
    return opens, vix


@dataclass(frozen=True)
class Context:
    """Per-date inputs of the cl. 14 descriptives."""

    vix: dict[date, float]
    calendar: tuple[date, ...]


async def load_real() -> tuple[list[PairInput], dict[str, int], Context]:
    """The cohort machinery of `pr1_design_facts` (W2), plus the 5-minute prices."""
    import pr1_design_facts as df

    _assert_outside_holdouts(WINDOW_LO, WINDOW_HI)
    days, per_day, daily_cal, ex_dates = await df._load(WINDOW_LO, WINDOW_HI)
    qual = {d for d in days if len(per_day[d]) >= df._MIN_NAMES}
    pairs = df._pairs(daily_cal, qual)
    bars = await _load_bars(WINDOW_LO, WINDOW_HI)
    opens, vix = await _load_daily_open_and_vix(WINDOW_LO, WINDOW_HI)
    out: list[PairInput] = []
    drops = strict = split_bonus = transient = 0
    for t, t1 in pairs:
        drop = df._drop(t, t1, ex_dates)
        cohort_ids = {x.stock_id for x in per_day[t]}
        steps, _, kept_set = df._basis_steps(t, t1)
        strict += len(steps & cohort_ids)
        split_bonus += len({sid for sid, exs in ex_dates.items() if t1 in exs} & cohort_ids)
        kept = [x for x in per_day[t] if x.stock_id not in drop]
        transient += len(kept_set & {x.stock_id for x in kept})  # the set the rerun drops (N5)
        drops += len(per_day[t]) - len(kept)
        tm1 = df._prev_session.get(t)
        out.append(PairInput(
            t, t1, tuple(x.stock_id for x in kept), {x.stock_id: x.symbol for x in per_day[t]},
            {x.stock_id: x.close_traded for x in kept}, bars.get(t, {}), bars.get(t1, {}),
            bars.get(tm1) if tm1 is not None and tm1 >= WINDOW_LO else None,
            opens.get(t1, {}),
            frozenset(i for i, a in df.basis.get(t, {}).items() if abs(a - 1.0) < 1e-12),
            frozenset(df._basis_steps(t, t1)[2]),
        ))
    cal = tuple(sorted(set(daily_cal) | {x for x in df._SPECIAL if WINDOW_LO <= x <= WINDOW_HI}))
    meta = {"pairs": len(pairs), "cohort_drops_union": drops, "strict_basis_steps": strict,
            "split_bonus_ex_dates": split_bonus, "transient_or_mirror_steps_kept": transient}
    return out, meta, Context(vix, cal)


def outcome_free_counts(pairs: Sequence[PairInput]) -> dict[str, int]:
    """--dry: what can be counted WITHOUT forming a return. Must match §8 of the text."""
    slots = qty0 = suspended = no915 = no1505 = carry1505 = 0
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
            carry1505 += b1 is not None and b1.p1510 is not None and b1.p1505_exact is None
    return {"book_slots": slots, "qty0": qty0, "suspended_t1": suspended,
            "no_0915_bar_t1": no915, "no_bar_by_1505_t1": no1505,
            "carried_1505_from_earlier_bar_t1": carry1505}


# ── run-once guard ───────────────────────────────────────────────────────────────────────────
def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    """Fail CLOSED: a git error raises, so it can never read as a clean tree (N3)."""
    return subprocess.run(["git", *args], cwd=_ROOT, capture_output=True, text=True,
                          check=True).stdout.strip()


def run_once_preflight() -> list[str]:
    """Every reason the real run must NOT start. Empty ⇒ it may."""
    problems = []
    if _sha(FROZEN_TEXT) != FROZEN_SHA256:
        problems.append("the frozen text's sha256 does not match the freeze")
    try:
        dirty = _git("status", "--porcelain", "--", *GUARDED_PATHSPEC)
        shadows = _shadowing_files()
        on_remote = _git("branch", "-r", "--contains", FREEZE_COMMIT)
    except (subprocess.CalledProcessError, OSError) as exc:
        return [f"git failed ({type(exc).__name__}) — refusing rather than guessing"]
    if dirty:
        problems.append("backend/app, backend/scripts, the lockfile or the frozen text has "
                        "uncommitted changes — the run must be the committed, reviewed code")
    if shadows:
        problems.append(f"git-ignored files could shadow reviewed modules: {shadows[:5]}")
    if not on_remote:
        problems.append("the freeze commit is not on any remote (push it: third-party timestamp)")
    if DESCRIPTIVES_PENDING:
        problems.append(f"{len(DESCRIPTIVES_PENDING)} cl. 14 descriptives are not implemented")
    for f in (RECEIPT, RUN_OUTPUT, RUN_RESULT):
        if f.exists():
            problems.append(f"{f.name} already exists: PR-1 runs ONCE")
    untracked = _untracked_imported_modules()
    if untracked:
        problems.append(f"imported modules not tracked by git: {untracked[:5]}")
    return problems


#: What the clean-tree check covers: all backend code, the lockfile and the pinned deps.
GUARDED_PATHSPEC = ("backend/app", "backend/scripts", "backend/uv.lock",
                    "backend/pyproject.toml",
                    "docs/analysis/pr1-preregistration-v3.1-2026-10-02.md")


def _shadowing_files() -> list[str]:
    """git-IGNORED compiled files under backend/ that Python could import instead of the
    reviewed source: an extension module (*.so) or a stray *.pyc outside __pycache__ (N4)."""
    out = _git("status", "--porcelain", "--ignored", "--", "backend/app", "backend/scripts")
    hits = []
    for line in out.splitlines():
        path = line[3:]
        if line.startswith("!!") and (path.endswith(".so") or (
                path.endswith((".pyc", ".pyo")) and "__pycache__" not in path)):
            hits.append(path)
    return hits


def _untracked_imported_modules() -> list[str]:
    """Every module loaded from inside the repo must be a git-tracked .py file (N4)."""
    tracked = set(_git("ls-files", "backend").splitlines())
    bad = []
    for m in list(sys.modules.values()):
        f = getattr(m, "__file__", None)
        if not f:
            continue
        path = Path(f).resolve()
        if _ROOT in path.parents and ".venv" not in path.parts:
            rel = str(path.relative_to(_ROOT))
            if rel not in tracked:
                bad.append(rel)
    return bad


def _hashed_files() -> list[Path]:
    """GUARDED plus every repo module actually imported, plus the lockfile — so the receipt
    pins exactly the code that ran (N4: the static list missed app/db/session.py and config)."""
    files = {f.resolve() for f in GUARDED}
    files |= {_ROOT / "backend/uv.lock", _ROOT / "backend/pyproject.toml"}
    for m in list(sys.modules.values()):
        f = getattr(m, "__file__", None)
        if f:
            path = Path(f).resolve()
            if _ROOT in path.parents and ".venv" not in path.parts:
                files.add(path)
    return sorted(files)


def _write_receipt() -> None:
    RECEIPT.write_text(json.dumps({
        "started_at": datetime.now(tz=UTC).isoformat(),
        "head": _git("rev-parse", "HEAD"),
        "script_sha256": _sha(Path(__file__)),
        "frozen_text_sha256": FROZEN_SHA256,
        "guarded_sha256": {str(f.relative_to(_ROOT)): _sha(f) for f in _hashed_files()},
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
        print(f"  {b.upper()} E1 (IC): {_fmt(e1, scale=1.0, unit='', dp=4)}")
        print(f"  {b.upper()} whole-cohort-demeaned net: {_fmt(whole)}")
        print(f"  {b.upper()} raw net: {_fmt(raw)}")
    lab = mechanism_label(records, d.branch)
    print(f"  mechanism label ({d.branch.upper()}): {lab['label']} over {lab['sessions']} sessions")
    totals: dict[str, int] = {}
    for r in records:
        for k, v in r.counts.items():
            totals[k] = totals.get(k, 0) + v
    print(f"  counts: {totals}")
    return d


def execute(load: Callable[[], tuple[list[PairInput], dict[str, int], Context]],
            out_path: Path, result_path: Path, write_receipt: Callable[[], None]) -> Decision:
    """The run-once body, separated so tests exercise it end to end on synthetic data (N2).

    Order: the output file is opened, THEN the receipt is written, THEN data is loaded — so a
    crash at any later point still counts as the run and still leaves what it printed. A
    traceback is written into the output file before re-raising (N7)."""
    import contextlib
    import traceback

    with out_path.open("x") as fh:  # "x": never overwrite an existing run output
        write_receipt()
        tee = _Tee(sys.stdout, fh)
        with contextlib.redirect_stdout(tee):
            try:
                pairs, meta, ctx = load()
                print("counts:", meta, outcome_free_counts(pairs))
                recs = [evaluate_session(p) for p in pairs]
                d = report(recs)
                result_path.write_text(json.dumps(
                    {"verdict": d.verdict, "branch": d.branch, "reasons": d.reasons,
                     "stats": d.stats, "reported_series": reported_series(recs),
                     "counts": meta, "interpretations": list(INTERPRETATIONS),
                     "unavailable": list(DESCRIPTIVES_UNAVAILABLE)},
                    indent=2, default=str) + "\n")
                tee.flush()
                describe(pairs, recs, d, *_ctx(ctx))
            except BaseException:
                print("\n⛔ THE RUN RAISED — this still counts as the one run:\n"
                      + traceback.format_exc())
                tee.flush()
                raise
        tee.flush()
    return d


class _Tee:
    """Write to the terminal AND the run's output file."""

    def __init__(self, *streams: object) -> None:
        self._streams = streams

    def write(self, data: str) -> int:
        for st_ in self._streams:
            st_.write(data)  # type: ignore[attr-defined]
        return len(data)

    def flush(self) -> None:
        for st_ in self._streams:
            st_.flush()  # type: ignore[attr-defined]

    def isatty(self) -> bool:
        return False

    encoding = "utf-8"


def _ctx(c: Context) -> tuple[dict[date, float], tuple[date, ...]]:
    return c.vix, c.calendar


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
        pairs = synthetic_pairs(a.seed, edge_bps=a.edge_bps)
        recs = [evaluate_session(p) for p in pairs]
        describe(pairs, recs, report(recs), *_ctx(synthetic_context(a.seed, pairs)))
        return
    if a.dry:
        pairs, meta, _ = asyncio.run(load_real())
        print({**meta, **outcome_free_counts(pairs)})
        print("pending cl. 14 descriptives:", len(DESCRIPTIVES_PENDING),
              "· unavailable (reviewer rules):", len(DESCRIPTIVES_UNAVAILABLE))
        return
    problems = run_once_preflight()
    if problems:
        raise SystemExit("refused:\n  - " + "\n  - ".join(problems))
    execute(lambda: asyncio.run(load_real()), RUN_OUTPUT, RUN_RESULT, _write_receipt)
    print(f"\nwrote {RUN_OUTPUT.name}, {RUN_RESULT.name} and {RECEIPT.name} — commit all three")


if __name__ == "__main__":
    main()
