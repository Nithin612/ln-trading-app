"""PR-1 design-level facts — measured from SESSION-t DATA ONLY, before the pre-registration.

    uv run python scripts/pr1_design_facts.py [--lo 2023-07-03] [--hi 2026-07-31]

**Read-only** (`SET TRANSACTION READ ONLY`) and **outcome-free**: no return, IC or signal-vs-
outcome statistic is computed. It reads, per session, the 5-minute bars and the exchange's daily
bar of THAT session, plus session DATES (the calendar) and corporate-action dates. The one
cross-session read is the basis check below. It compares two sources' prices for the SAME
session and never differences prices across sessions. It exists because the reviewers asked
for coverage, concentration and cost facts, and because two kills had to be calibrated on the
real book (`docs/analysis/pr1-outside-pass-2026-09-30.md`).

## ⛔ The two price tables are on DIFFERENT BASES (quant-verifier, 2026-09-30; re-measured here)

- `ohlcv_5m` (the Kite historical backfill) is **back-adjusted** for splits, bonuses, demergers,
  rights and some dividends.
- `ohlcv_1d` (the NSE bhavcopy) holds the **traded** prices.
- The same-session ratio A = official open ÷ open of the 09:15 bar is ≠ 1 on about 22% of
  name-days. It steps exactly at corporate-action dates (KOTAKBANK 5.0 until its split, NESTLEIND
  20 → 2 → 1). Where the bases agree, the two opens are EXACTLY equal on 98.7% of name-days.
- ⇒ **A return must be computed inside ONE table.** PR-1 draft v3 takes every return from the
  5-minute table, whose 09:15 open is the official open. The daily file is used only for sizing
  and fees, which need the traded price. This script therefore prices qty and fees from the
  official close C_t, not from the adjusted 5-minute print.

What it prints (§2 and §8 of `docs/analysis/pr1-preregistration-extract-v3-2026-09-30.md`):
- the basis check;
- the two calendars and the pairs a muhurat session silently spans;
- coverage;
- the book: concentration, late move, traded price, qty-0 share, delivery fee per slot;
- the Abdi–Ranaldo half-spread of book slots vs every name-window, as unconditional quantiles,
  plus the book's own bracket top by the SAME construction as the cohort's 2.28 (the median of
  the non-clamped windows).

The window is PINNED by date: the tables grow, so an unpinned re-run measures a different sample.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import statistics
import sys
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from app.trading.fees import roundtrip_charges  # noqa: E402
from sqlalchemy import text  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent.parent
_AR_CSV = _ROOT / "docs/analysis/item17-name-windows-2026-09-20.csv"
_BARS_PER_SESSION = 75  # 09:15 … 15:25, start-stamped
_MIN_NAMES = 150
_BOOK_K = 5
_PER_NAME_INR = Decimal("20000")
#: Exchange-announced short sessions (DR drills, muhurat). 2023-11-12 is in NEITHER table, so a
#: calendar built from the data cannot see it; it is listed from the exchange's announcement.
#: §10j: sessions on which 13–26 names have a 09:15-bar open 0.3–2% off the official open,
#: reverting the next session — a one-day SOURCE mismatch, not a basis step. v3.1 cl. 3 excludes
#: them as WHOLE sessions (both adjoining pairs), by this dated list fixed before any outcome is
#: read (quant-verifier 2026-10-02: a name-level drop on these nights selects on how far the
#: outcome's endpoint is mis-measured).
_MISMATCH = frozenset({date(2024, 2, 5), date(2024, 5, 14), date(2025, 1, 20)})
#: The rule that produces `_MISMATCH`: ≥ this many names with a one-day basis outlier.
_OUTLIER_SESSION = 10
#: The next / previous exchange session that is neither special nor §10j — set by `_pairs` from
#: the exchange calendar. The persistence test judges A against these, never against a DR drill,
#: a muhurat or a mismatch session (quant-verifier 2026-10-02, #5).
_next_session: dict[date, date] = {}
_prev_session: dict[date, date] = {}
#: cl. 12 K4: the dated halves split here (the first half ends 2025-01-31).
_K4_SPLIT = date(2025, 2, 1)
_SPECIAL = frozenset(
    {date(2023, 11, 12), date(2024, 3, 2), date(2024, 5, 18), date(2024, 11, 1), date(2025, 10, 21)}
)


@dataclass(frozen=True)
class NameSession:
    stock_id: int
    symbol: str  # the pre-registered tie-break at the fifth place
    s: float  # raw late move; demeaned per session below (a within-table ratio: basis-free)
    close_traded: Decimal  # official close C_t, the TRADED basis — used for qty and fees only
    open_basis: float  # official open ÷ open of the 09:15 bar, same session


#: Same-session basis ratio A = official open ÷ 09:15-bar open, for every (stock_id, session)
#: with both. Filled by `_load`. Read only as a RATIO OF TWO MEASUREMENTS OF ONE PRICE — it says
#: whether the 5-minute table's adjustment factor changed overnight, never what the price did.
basis: dict[date, dict[int, float]] = defaultdict(dict)

#: v3.1 cl. 3: a name-night (t, t+1) whose basis steps by more than this is dropped. Measured
#: 2026-09-30 (round 2): 554 such name-nights on the 754 pairs, 18 of them book slots. RELIANCE's
#: demerger factor 1.0491 = 1/0.9532 is the company's tax cost-apportionment ratio, so the
#: adjusted return across that night is WRONG, not merely unrealizable.
BASIS_STEP = 0.003


def _stepped(a: float | None, b: float | None) -> bool:
    return a is not None and b is not None and abs(b / a - 1.0) > BASIS_STEP


def _basis_steps(t: date, t1: date) -> tuple[set[int], int, set[int]]:
    """Names whose adjustment factor changes overnight from t to t+1: a STRICT step.

    All three must hold (A = official open ÷ 09:15-bar open; t−1 / t+2 = the neighbouring
    sessions that are neither special nor §10j):
      - A steps from t to t+1;
      - it STAYS stepped on t+2 (otherwise the t+1 open is a one-day outlier — transient);
      - A_t is clean against A_{t−1} (otherwise the "step" is A_t's own one-day outlier
        reverting — a mirror, and the night's R_on is clean; quant-verifier 2026-10-02, #4).
    A missing A on t+2 or t−1, or a t+2 / t−1 outside the window, counts as "no evidence of an
    outlier" (the step is kept as strict); nothing beyond the window is read. Also returns the
    names not checkable (no 09:15 bar on t or t+1; kept) and the transient + mirror SET (kept;
    the PR-1 study's cl. 14 rerun drops them)."""
    steps: set[int] = set()
    unknown = 0
    kept: set[int] = set()
    nxt = basis.get(t1, {})
    t2, tm1 = _next_session.get(t1), _prev_session.get(t)
    after = basis.get(t2, {}) if t2 is not None else {}
    before = basis.get(tm1, {}) if tm1 is not None else {}
    for sid, a_t in basis.get(t, {}).items():
        a_t1 = nxt.get(sid)
        if a_t1 is None:
            unknown += 1
        elif _stepped(a_t, a_t1):
            if _stepped(a_t1, after.get(sid)) or _stepped(before.get(sid), a_t):
                kept.add(sid)
            else:
                steps.add(sid)
    return steps, unknown, kept


def _drop(t: date, t1: date, ex_dates: dict[int, set[date]]) -> set[int]:
    """cl. 3's exclusions for the pair: t+1 is a split/bonus ex-date, or the basis steps."""
    return {sid for sid, exs in ex_dates.items() if t1 in exs} | _basis_steps(t, t1)[0]


def _q(xs: list[float], p: float) -> float:
    """Order statistic at quantile p of an already-sorted list."""
    return xs[int(p * (len(xs) - 1))]


async def _load(
    lo: date, hi: date
) -> tuple[list[date], dict[date, list[NameSession]], list[date], dict[int, set[date]]]:
    bounds = {"lo": lo, "hi": hi}
    sql = text(
        """
        WITH b AS (
          SELECT stock_id, (time AT TIME ZONE 'Asia/Kolkata')::date AS d,
                 count(*) AS nb,
                 max(open) FILTER (
                   WHERE (time AT TIME ZONE 'Asia/Kolkata')::time = '09:15') AS o915,
                 max(close) FILTER (
                   WHERE (time AT TIME ZONE 'Asia/Kolkata')::time = '15:10') AS p1515,
                 max(close) FILTER (
                   WHERE (time AT TIME ZONE 'Asia/Kolkata')::time = '15:25') AS p1530
          FROM ohlcv_5m
          WHERE time >= (CAST(:lo AS date)::timestamp AT TIME ZONE 'Asia/Kolkata')
            AND time <  ((CAST(:hi AS date) + 1)::timestamp AT TIME ZONE 'Asia/Kolkata')
          GROUP BY 1, 2)
        SELECT b.stock_id, st.symbol, b.d, b.nb, b.o915, b.p1515, b.p1530, dd.open, dd.close
        FROM b
        JOIN ohlcv_1d dd ON dd.stock_id = b.stock_id
                        AND dd.time >= (CAST(:lo AS date)::timestamp AT TIME ZONE 'Asia/Kolkata')
                        AND dd.time <  ((CAST(:hi AS date) + 1)::timestamp
                                        AT TIME ZONE 'Asia/Kolkata')
                        AND (dd.time AT TIME ZONE 'Asia/Kolkata')::date = b.d
        JOIN stocks st ON st.id = b.stock_id
        """
    )
    cal_sql = text(
        """
        SELECT DISTINCT (time AT TIME ZONE 'Asia/Kolkata')::date FROM ohlcv_1d
        WHERE time >= (CAST(:lo AS date)::timestamp AT TIME ZONE 'Asia/Kolkata')
          AND time <  ((CAST(:hi AS date) + 1)::timestamp AT TIME ZONE 'Asia/Kolkata')
        ORDER BY 1
        """
    )
    ca_sql = text(
        "SELECT stock_id, ex_date FROM corporate_actions WHERE ex_date >= :lo AND ex_date <= :hi"
    )
    async with AsyncSessionFactory() as s:
        await s.execute(text("SET TRANSACTION READ ONLY"))
        rows = (await s.execute(sql, bounds)).all()
        daily_cal = [r[0] for r in (await s.execute(cal_sql, bounds)).all()]
        ca_rows = (await s.execute(ca_sql, bounds)).all()
    per_day: dict[date, list[NameSession]] = defaultdict(list)
    days: set[date] = set()
    basis.clear()
    for sid, sym, d, nb, o915, p15, p30, ob, cb in rows:
        days.add(d)
        if o915 is not None and ob is not None and o915 > 0:
            basis[d][int(sid)] = float(ob) / float(o915)
        if nb != _BARS_PER_SESSION or None in (o915, p15, p30, ob, cb) or p15 <= 0 or o915 <= 0:
            continue
        per_day[d].append(
            NameSession(int(sid), str(sym), float(p30) / float(p15) - 1.0, Decimal(cb),
                        float(ob) / float(o915))
        )
    ex_dates: dict[int, set[date]] = defaultdict(set)
    for sid, exd in ca_rows:
        ex_dates[int(sid)].add(exd)
    return sorted(days), per_day, daily_cal, ex_dates


def _pairs(daily_cal: list[date], qual: set[date]) -> list[tuple[date, date]]:
    """(t, t+1) consecutive in the EXCHANGE calendar (the daily file + the listed specials),
    neither special nor a §10j mismatch session, t qualifying — so a pair never silently spans a
    session."""
    cal = sorted(set(daily_cal) | {d for d in _SPECIAL if daily_cal[0] <= d <= daily_cal[-1]})
    skip = _SPECIAL | _MISMATCH
    ordinary = [d for d in cal if d not in skip]
    _next_session.clear()
    _next_session.update(zip(ordinary, ordinary[1:], strict=False))
    _prev_session.clear()
    _prev_session.update(zip(ordinary[1:], ordinary, strict=False))
    return [(a, b) for a, b in zip(cal, cal[1:], strict=False)
            if a not in skip and b not in skip and a in qual]


def _book(xs: list[NameSession], drop: set[int]) -> list[tuple[float, NameSession]]:
    """The 5 most negative demeaned s; a name whose t+1 is a split/bonus ex-date is dropped."""
    kept = [x for x in xs if x.stock_id not in drop]
    m = statistics.fmean(x.s for x in kept)
    ranked = sorted(kept, key=lambda x: (x.s - m, x.symbol))  # ties: ascending symbol
    return [(x.s - m, x) for x in ranked[:_BOOK_K]]


def _print_basis(per_day: dict[date, list[NameSession]]) -> None:
    dev = sorted(abs(x.open_basis - 1.0) for xs in per_day.values() for x in xs)
    agree = [v for v in dev if v < 0.02]
    exact = sum(v == 0 for v in agree) / len(agree)
    print(f"\nbasis check, official open ÷ 09:15-bar open (same session), {len(dev):,} name-days:")
    print(f"  |A−1| > 2%: {sum(v > 0.02 for v in dev) / len(dev):.1%} · where the bases agree "
          f"(|A−1| < 2%) the opens are exactly equal on {exact:.1%}"
          f" · deviations of 0.3–2%: {sum(0.003 < v < 0.02 for v in dev):,} (dividend-adjustment "
          "offsets and one-day source mismatches)")


def _print_outlier_sessions(daily_cal: list[date]) -> None:
    """The §10j RULE, not just its list: a session is excluded whole when ≥ _OUTLIER_SESSION
    names have a ONE-DAY basis outlier on it (A steps in from the previous session and back
    out to the next, which agree). Neighbours are the raw exchange calendar's. Ratios only."""
    cal = sorted(d for d in daily_cal if d in basis)
    per: dict[date, int] = {}
    for prev, d, nxt in zip(cal, cal[1:], cal[2:], strict=False):
        n = sum(
            1 for sid, a in basis[d].items()
            if _stepped(basis[prev].get(sid), a) and _stepped(a, basis[nxt].get(sid))
            and not _stepped(basis[prev].get(sid), basis[nxt].get(sid))
        )
        if n:
            per[d] = n
    hit = sorted(d for d, n in per.items() if n >= _OUTLIER_SESSION)
    print(f"one-day basis outliers: {sum(per.values())} name-days on {len(per)} sessions · "
          f"sessions with ≥ {_OUTLIER_SESSION}: {[(str(d), per[d]) for d in hit]} · "
          f"largest below the rule: {max((n for d, n in per.items() if d not in hit), default=0)}"
          f" · rule reproduces the §10j list: {set(hit) == set(_MISMATCH)}")


def _print_basis_steps(
    pairs: list[tuple[date, date]], per_day: dict[date, list[NameSession]],
    ex_dates: dict[int, set[date]],
) -> None:
    """How many cohort name-nights cl. 3's basis-step rule drops, and how many would have been
    BOOK slots under the split/bonus-only rule (v3). Counts only — no price is printed."""
    nights = book_hit = unknown = kept = 0
    for t, t1 in pairs:
        steps, _, k = _basis_steps(t, t1)
        cohort = {x.stock_id for x in per_day[t]}
        nights += len(steps & cohort)
        kept += len(k)
        nxt, cur = basis.get(t1, {}), basis.get(t, {})
        unknown += sum(1 for sid in cohort if sid not in nxt or sid not in cur)
        split_only = {sid for sid, exs in ex_dates.items() if t1 in exs}
        book_hit += sum(1 for _, x in _book(per_day[t], split_only) if x.stock_id in steps)
    print(f"STRICT basis steps overnight (|A_t+1 / A_t − 1| > {BASIS_STEP:.1%}, still stepped "
          f"on t+2, A_t clean against t−1): {nights} cohort name-nights dropped · {book_hit} of "
          f"them were v3 book slots · transient or mirror steps (kept): {kept} · cohort "
          f"name-nights not checkable (no 09:15 bar on one side; kept): {unknown}")


def _print_book(
    pairs: list[tuple[date, date]], per_day: dict[date, list[NameSession]],
    ex_dates: dict[int, set[date]],
) -> list[int]:
    """Concentration, late move, traded price and per-slot delivery fee of the k = 5 book."""
    slots: Counter[int] = Counter()
    book_s: list[float] = []
    prices: list[float] = []
    fee_bps: list[float] = []
    unbuyable = 0
    for t, t1 in pairs:
        drop = _drop(t, t1, ex_dates)
        for v, x in _book(per_day[t], drop):
            slots[x.stock_id] += 1
            book_s.append(v)
            prices.append(float(x.close_traded))
            qty = int(_PER_NAME_INR // x.close_traded)
            if qty == 0:
                unbuyable += 1
                continue
            total, _ = roundtrip_charges(
                position_side="LONG", entry_price=x.close_traded, exit_price=x.close_traded,
                quantity=qty, product="delivery", entry_on=t, exit_on=t1,
            )
            fee_bps.append(float(total) / float(x.close_traded * qty) * 1e4)
    n_slots = sum(slots.values())
    ranked = [c for _, c in slots.most_common()]
    hhi = sum((c / n_slots) ** 2 for c in ranked)
    cohort_px = sorted(float(x.close_traded) for t, _ in pairs for x in per_day[t])
    print(f"\nbook: {n_slots} slots over {len(pairs)} pairs · {len(slots)} distinct names · "
          f"effective names (1/HHI) {1 / hhi:.1f}")
    for k in (1, 3, 10, 20):
        print(f"  top-{k} names' share of slots: {sum(ranked[:k]) / n_slots:.1%}")
    book_s.sort()
    prices.sort()
    fee_bps.sort()
    print(f"book late move s (demeaned): median {_q(book_s, .5) * 1e4:.0f} bps · "
          f"p10 {_q(book_s, .1) * 1e4:.0f} · p90 {_q(book_s, .9) * 1e4:.0f}")
    print(f"traded price (official close): book median ₹{_q(prices, .5):,.0f} · p90 "
          f"₹{_q(prices, .9):,.0f} · max ₹{prices[-1]:,.0f} | cohort median "
          f"₹{_q(cohort_px, .5):,.0f} · book slots above ₹20,000: {unbuyable} "
          f"({unbuyable / n_slots:.2%})")
    print(f"delivery fee at ₹20,000/name, whole shares, traded prices: median "
          f"{_q(fee_bps, .5):.2f} · mean {statistics.fmean(fee_bps):.2f} · p90 "
          f"{_q(fee_bps, .9):.2f} · max {fee_bps[-1]:.2f} bps")
    return ranked


def _ar_by_window() -> tuple[dict[tuple[int, str], float], list[tuple[str, str]], list[float]]:
    by_key: dict[tuple[int, str], float] = {}
    windows: set[tuple[str, str]] = set()
    with _AR_CSV.open() as f:
        for row in csv.DictReader(f):
            by_key[(int(row["stock_id"]), row["first_session"])] = float(row["ar_half_bps"])
            windows.add((row["first_session"], row["last_session"]))
    return by_key, sorted(windows), sorted(by_key.values())


def _cluster_mean_ci(groups: dict[str, list[float]]) -> tuple[float, float, float]:
    """Pooled mean with a CLUSTER-robust (CR1) 90% CI, clusters = the 21-session windows (one
    window's slots share one spread estimate per name, so they are not independent). The
    quantile is t with G − 1 degrees of freedom, not z: with 37 clusters z understates it."""
    from scipy.stats import t as student_t

    xs = [v for g in groups.values() for v in g]
    n, mean = len(xs), statistics.fmean(xs)
    g = len(groups)
    var = sum(sum(v - mean for v in grp) ** 2 for grp in groups.values()) / (n * n)
    se = (var * g / (g - 1)) ** 0.5
    q = float(student_t.ppf(0.95, g - 1))
    return mean, mean - q * se, mean + q * se


def _print_spread(
    pairs: list[tuple[date, date]], per_day: dict[date, list[NameSession]],
    ex_dates: dict[int, set[date]],
) -> None:
    """Book-slot half-spreads vs every name-window. ⚠ The windows span t … t+20: a SPREAD
    input measured on the capture set, not an outcome of this study."""
    ar, windows, all_ar = _ar_by_window()
    starts = [w[0] for w in windows]
    book_ar: list[float] = []
    book_by_window: dict[str, list[float]] = defaultdict(list)
    for t, t1 in pairs:
        i = bisect_right(starts, t.isoformat()) - 1
        if i < 0 or t.isoformat() > windows[i][1]:
            continue
        drop = _drop(t, t1, ex_dates)
        w = windows[i][0]
        got = [max(ar[(x.stock_id, w)], 0.0) for _, x in _book(per_day[t], drop)
               if (x.stock_id, w) in ar]
        book_ar.extend(got)
        book_by_window[w].extend(got)
    book_ar.sort()

    def clamp(xs: list[float]) -> float:
        return sum(1 for v in xs if v <= 0) / len(xs)

    print(f"\nAbdi–Ranaldo half-spread, book slots matched {len(book_ar)}: q50 "
          f"{_q(book_ar, .5):.2f} bps (clamped {clamp(book_ar):.1%}) vs all name-windows q50 "
          f"{_q(all_ar, .5):.2f} (clamped {clamp(all_ar):.1%})")
    for p in (.6, .7, .8, .9):
        print(f"  q{int(p * 100)}: book {_q(book_ar, p):.2f} vs all {_q(all_ar, p):.2f}")
    mean, lo, hi = _cluster_mean_ci(book_by_window)
    print(f"  book-slot MEAN half-spread (clamped windows as 0): {mean:.2f} bps · "
          f"window-cluster 90% CI [{lo:.2f}, {hi:.2f}] (t, {len(book_by_window) - 1} df) over "
          f"{len(book_by_window)} windows · coverage {len(book_ar):,} of the book's slots")
    top_book = statistics.median(v for v in book_ar if v > 0)
    top_all = statistics.median(v for v in all_ar if v > 0)
    print(f"  bracket top by one construction (median of the non-clamped windows): "
          f"book {top_book:.2f} · all {top_all:.2f}")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lo", type=date.fromisoformat, default=date(2023, 7, 3))
    ap.add_argument("--hi", type=date.fromisoformat, default=date(2026, 7, 31))
    a = ap.parse_args()
    days, per_day, daily_cal, ex_dates = await _load(a.lo, a.hi)
    qual = {d for d in days if len(per_day[d]) >= _MIN_NAMES}
    counts = [len(per_day[d]) for d in sorted(qual)]
    print(f"window {a.lo} → {a.hi}: sessions with 5-minute bars {len(days)} · daily-file "
          f"sessions {len(daily_cal)} · only in the daily file: "
          f"{sorted(set(daily_cal) - set(days))} · qualifying (≥{_MIN_NAMES} names complete) "
          f"{len(qual)}")
    print(f"names/session: min {min(counts)} · median {statistics.median(counts)} · "
          f"max {max(counts)}")
    pairs = _pairs(daily_cal, qual)
    naive = sum(1 for x, y in zip(sorted(days), sorted(days)[1:], strict=False)
                if x in qual and y in qual)
    print(f"pairs: {len(pairs)} on the exchange calendar (a 5-minute-only calendar gives "
          f"{naive}, silently spanning the muhurat sessions)")
    _print_basis(per_day)
    _print_outlier_sessions(daily_cal)
    _print_basis_steps(pairs, per_day, ex_dates)
    first = sum(1 for t, _ in pairs if t < _K4_SPLIT)
    print(f"K4 dated halves: {first} pairs with t < {_K4_SPLIT} · {len(pairs) - first} after")
    ranked = _print_book(pairs, per_day, ex_dates)
    _print_spread(pairs, per_day, ex_dates)
    print("\nslot counts (for the K6 calibration):", " ".join(str(c) for c in ranked))


if __name__ == "__main__":
    asyncio.run(main())
