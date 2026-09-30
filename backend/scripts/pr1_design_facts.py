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
    for sid, sym, d, nb, o915, p15, p30, ob, cb in rows:
        days.add(d)
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
    neither special, t qualifying — so a pair never silently spans a session."""
    cal = sorted(set(daily_cal) | {d for d in _SPECIAL if daily_cal[0] <= d <= daily_cal[-1]})
    return [(a, b) for a, b in zip(cal, cal[1:], strict=False)
            if a not in _SPECIAL and b not in _SPECIAL and a in qual]


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
          f" · one-day mismatches (0.3–2%): {sum(0.003 < v < 0.02 for v in dev):,}")


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
        drop = {sid for sid, exs in ex_dates.items() if t1 in exs}
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


def _print_spread(
    pairs: list[tuple[date, date]], per_day: dict[date, list[NameSession]],
    ex_dates: dict[int, set[date]],
) -> None:
    """Book-slot half-spreads vs every name-window. ⚠ The windows span t … t+20: a SPREAD
    input measured on the capture set, not an outcome of this study."""
    ar, windows, all_ar = _ar_by_window()
    starts = [w[0] for w in windows]
    book_ar: list[float] = []
    for t, t1 in pairs:
        i = bisect_right(starts, t.isoformat()) - 1
        if i < 0 or t.isoformat() > windows[i][1]:
            continue
        drop = {sid for sid, exs in ex_dates.items() if t1 in exs}
        w = windows[i][0]
        book_ar.extend(ar[(x.stock_id, w)] for _, x in _book(per_day[t], drop)
                       if (x.stock_id, w) in ar)
    book_ar.sort()

    def clamp(xs: list[float]) -> float:
        return sum(1 for v in xs if v <= 0) / len(xs)

    print(f"\nAbdi–Ranaldo half-spread, book slots matched {len(book_ar)}: q50 "
          f"{_q(book_ar, .5):.2f} bps (clamped {clamp(book_ar):.1%}) vs all name-windows q50 "
          f"{_q(all_ar, .5):.2f} (clamped {clamp(all_ar):.1%})")
    for p in (.6, .7, .8, .9):
        print(f"  q{int(p * 100)}: book {_q(book_ar, p):.2f} vs all {_q(all_ar, p):.2f}")
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
    ranked = _print_book(pairs, per_day, ex_dates)
    _print_spread(pairs, per_day, ex_dates)
    print("\nslot counts (for the K6 calibration):", " ".join(str(c) for c in ranked))


if __name__ == "__main__":
    asyncio.run(main())
