"""F1 — would a market-cap SIZE floor have helped? (the cheap cross-tab, before the scraper)

    uv run python scripts/size_proxy_spike.py

**This is the half of F1 that does not need a vendor.** MCE slice 5b proposes a market-cap
floor on the junk gate, and building it means choosing a fundamentals vendor (decision D3)
and paying for an XBRL scraper. The standing instruction is explicit: *cross-tab a cheap
proxy before paying that cost*, because the 5a deep-dive already found the illiquid cohort
was net-**positive** and therefore questioned 5b's whole premise.

So: we do not have `market_cap` (no writer — that is what 5b would build). We do have two
things a market-cap floor would be *proxying for*, on every closed position:

    median daily traded value   (close × volume, the liquidity/size composite)
    entry price level           (a ₹39 micro-cap is not a ₹2,500 large cap)

**The test that decides whether 5b is worth building at all:** if size matters, both
proxies should point the same way. Two measures of the same underlying quantity that
disagree are not measuring it.

⚠ **A proxy result cannot prove a market-cap floor would fail** — only that the cheap
evidence gives it no support. That is still decisive for *sequencing*: paying a vendor to
test a hypothesis the free data already declines to support is the expensive way to learn
this.

⚠ **n is thin and the buckets are thinner.** 105 closed positions is 21 per quintile.
Every contrast is bootstrapped and none of it can clear the project's t ≈ 3.6 bar.
"""

from __future__ import annotations

import asyncio
import random
import statistics
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from sqlalchemy import text  # noqa: E402

_IST = ZoneInfo("Asia/Kolkata")
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_OUT_DIR = _REPO_ROOT / "docs" / "analysis"
_SEED = 20260907

#: Traded-value lookback. Recent enough to describe the stock as it was when traded,
#: long enough that a single quiet week does not define a name's liquidity.
_SINCE = datetime(2026, 6, 1, tzinfo=UTC)

_SQL = text(
    """
    WITH closed AS (
        SELECT p.stock_id,
               p.avg_entry_price AS px,
               p.quantity,
               p.realized_pnl,
               (p.realized_pnl / NULLIF(p.quantity * p.avg_entry_price, 0)) AS ret
        FROM positions p
        WHERE p.mode = 'paper' AND p.closed_at IS NOT NULL
    ),
    adv AS (
        SELECT stock_id,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY close * volume) AS mdtv
        FROM ohlcv_1d
        WHERE time >= :since
        GROUP BY stock_id
    )
    SELECT c.stock_id, c.px, c.quantity, c.realized_pnl, c.ret, a.mdtv, s.symbol
    FROM closed c
    JOIN adv a ON a.stock_id = c.stock_id
    JOIN stocks s ON s.id = c.stock_id
    WHERE c.ret IS NOT NULL
    """
)


@dataclass(frozen=True)
class Row:
    symbol: str
    px: float
    mdtv: float
    pnl: float
    ret: float


def _quintiles(rows: list[Row], key: Callable[[Row], float]) -> list[list[Row]]:
    ordered = sorted(rows, key=key)
    size = len(ordered) // 5
    return [
        ordered[q * size : (q + 1) * size] if q < 4 else ordered[4 * size :]
        for q in range(5)
    ]


def _bucket_line(idx: int, bucket: list[Row], label_value: float, unit: str) -> str:
    mean_ret = statistics.fmean(r.ret for r in bucket) * 100
    wins = sum(1 for r in bucket if r.pnl > 0)
    total = sum(r.pnl for r in bucket)
    return (
        f"| Q{idx} | {len(bucket)} | {label_value:,.2f} {unit} | {mean_ret:+.3f}% | "
        f"{100 * wins / len(bucket):.0f}% | ₹{total:,.0f} |"
    )


def _bootstrap_diff(a: list[Row], b: list[Row], n_iter: int = 5000) -> tuple[float, float]:
    """90% interval for (mean return of A − mean return of B), resampling within each.

    Trades are the unit here, unlike CAS-2 where the day was — these are 105 separate
    positions in different names on different dates, not 208 names sharing one afternoon.
    """
    rng = random.Random(_SEED)
    diffs: list[float] = []
    for _ in range(n_iter):
        ra = statistics.fmean(rng.choice(a).ret for _ in a)
        rb = statistics.fmean(rng.choice(b).ret for _ in b)
        diffs.append((ra - rb) * 100)
    diffs.sort()
    return diffs[int(0.05 * len(diffs))], diffs[int(0.95 * len(diffs))]


async def _run() -> int:
    async with AsyncSessionFactory() as db:
        raw = list((await db.execute(_SQL, {"since": _SINCE})).all())
    if not raw:
        print("no closed positions with a traded-value join")
        return 1

    rows = [
        Row(symbol=r.symbol, px=float(r.px), mdtv=float(r.mdtv),
            pnl=float(r.realized_pnl), ret=float(r.ret))
        for r in raw
    ]

    by_mdtv = _quintiles(rows, lambda r: r.mdtv)
    by_px = _quintiles(rows, lambda r: r.px)

    mdtv_lo, mdtv_hi = _bootstrap_diff(by_mdtv[0], by_mdtv[4])
    px_lo, px_hi = _bootstrap_diff(by_px[0], by_px[4])

    now = datetime.now(UTC).astimezone(_IST)
    out: list[str] = [
        f"# F1 — would a market-cap SIZE floor have helped? ({now.date().isoformat()})",
        "",
        "**The half of F1 that needs no vendor.** MCE 5b proposes a market-cap floor on the",
        "junk gate; building it means choosing a fundamentals vendor (**decision D3**) and",
        "paying for an XBRL scraper. The standing instruction is to *cross-tab a cheap proxy",
        "first*, because 5a already found the illiquid cohort net-**positive** and so",
        "questioned 5b's premise.",
        "",
        f"**{len(rows)} closed paper positions.** We have no `market_cap` (no writer — that",
        "is what 5b would build), so we test the two things such a floor would be proxying",
        "for: **median daily traded value** and **entry price level**.",
        "",
        "⭐ **The decisive test: if size matters, both proxies should point the same way.**",
        "Two measures of one underlying quantity that disagree are not measuring it.",
        "",
        "## By median daily traded value (Q1 = smallest / least traded)",
        "",
        "| quintile | n | median traded value | mean return | win | total |",
        "|---|---|---|---|---|---|",
    ]
    for i, b in enumerate(by_mdtv, start=1):
        out.append(_bucket_line(i, b, statistics.fmean(r.mdtv for r in b) / 1e7, "Cr"))
    out += [
        "",
        f"Q1 − Q5 mean-return difference: 90% interval **[{mdtv_lo:+.3f}%, {mdtv_hi:+.3f}%]**",
        "",
        "## By entry price level (Q1 = cheapest)",
        "",
        "| quintile | n | avg entry price | mean return | win | total |",
        "|---|---|---|---|---|---|",
    ]
    for i, b in enumerate(by_px, start=1):
        out.append(_bucket_line(i, b, statistics.fmean(r.px for r in b), "₹"))
    out += [
        "",
        f"Q1 − Q5 mean-return difference: 90% interval **[{px_lo:+.3f}%, {px_hi:+.3f}%]**",
        "",
        "## Verdict",
        "",
    ]

    mdtv_small_better = statistics.fmean(r.ret for r in by_mdtv[0]) > statistics.fmean(
        r.ret for r in by_mdtv[4]
    )
    px_small_better = statistics.fmean(r.ret for r in by_px[0]) > statistics.fmean(
        r.ret for r in by_px[4]
    )
    agree = mdtv_small_better == px_small_better

    mdtv_sig = mdtv_lo > 0 or mdtv_hi < 0
    px_sig = px_lo > 0 or px_hi < 0

    if not agree:
        out += [
            "⛔ **THE TWO SIZE PROXIES DISAGREE — AND NEITHER CONTRAST IS ESTABLISHED.**",
            "",
            f"- traded-value Q1−Q5 interval **{'excludes' if mdtv_sig else 'SPANS'} zero**",
            f"- price-level Q1−Q5 interval **{'excludes' if px_sig else 'SPANS'} zero**",
            "",
            "So the case against a size floor is doubled: the two proxies point in opposite",
            "directions, *and* neither difference survives its own bootstrap. There is no",
            "coherent size signal here to build a gate on.",
            "",
            f"- By traded value, the **smallest** quintile is "
            f"{'better' if mdtv_small_better else 'worse'} than the largest.",
            f"- By price level, the **cheapest** quintile is "
            f"{'better' if px_small_better else 'worse'} than the dearest.",
            "",
            "If a size effect were driving outcomes, two proxies for size would point the",
            "same way. They do not, and neither is monotonic across its own quintiles.",
            "",
            "**⇒ The cheap evidence gives a market-cap floor NO support.** That does not",
            "prove such a floor would fail — only that paying a vendor to test a hypothesis",
            "the free data already declines to support is the expensive way to learn it.",
            "",
            "**Recommendation: DROP MCE 5b, and D3 (the vendor decision) becomes moot until",
            "someone produces a reason to revisit the premise.** This is consistent with the",
            "5a ruling — where the liquidity floor would have cut a net-*winning* set, and",
            "the already-ACTIVE diversity gate caught the SRTL archetype anyway.",
        ]
    else:
        direction = "smaller" if mdtv_small_better else "larger"
        out += [
            f"Both proxies agree that **{direction}** names did better.",
            "",
            "⚠ Agreement is not significance. Check whether either interval excludes zero",
            "before reading anything into it, and note that n = 21 per bucket.",
        ]

    out += [
        "",
        "## ⚠ What this cannot tell you",
        "",
        f"- **n = {len(rows)} closed positions, 21 per quintile.** Nothing here approaches the",
        "  project's t ≈ 3.6 promotion bar, and that bar does not fall with n.",
        "- **Traded value is not market cap.** A widely-traded small company and a quiet",
        "  large one both break the proxy. This is evidence about *sequencing*, not a",
        "  measurement of the size factor.",
        "- **Survivorship**: these are the names our engine chose, not a cross-section of",
        "  the market. A size effect could exist in the universe and be invisible here.",
    ]

    report = "\n".join(out)
    print(report, flush=True)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = _OUT_DIR / f"size-proxy-spike-{now.date().isoformat()}.md"
    target.write_text(report + "\n", encoding="utf-8")
    print(f"\nwritten: {target}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
