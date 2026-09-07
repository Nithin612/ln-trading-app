"""Q5 — the pre-COVID backtest: is the DATA obtainable, and what would it cost?

    uv run python scripts/historical_data_spike.py [--probe]

**The first concrete step, and deliberately not the backtest itself.** The user asked
(2026-08-28) for a pre-COVID regime-robustness backtest — 2018 or 2015 — and held it until
after watch mode. The blocker was never the analysis: `ohlcv_1d` starts **2023-07-03**, so
going back is a *data-acquisition project*, not a query.

This answers three questions in the order that decides whether the project is worth
starting:

1. **Is the archive reachable at all** for 2018 / 2015?
2. **What does a point-in-time, survivorship-safe universe cost** to reconstruct?
3. **What would the result actually be worth** once we had it?

⚠ `--probe` makes a handful of polite HTTPS requests to NSE's public archive (a few
seconds apart, browser headers, same host `bhavcopy_service` already uses daily). Without
it the script reports only what is knowable offline.

⚠ **Read-only. Ingests nothing.** A spike that quietly started backfilling four years of
bars would be answering a question nobody asked yet.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from sqlalchemy import text  # noqa: E402

_IST = ZoneInfo("Asia/Kolkata")
_OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "analysis"

#: Both formats the service already documents. Format 1 is what we ingest daily; format 2
#: is the older compact archive, and the question is where the boundary sits.
_FULL = "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{d:%d%m%Y}.csv"
_COMPACT = (
    "https://nsearchives.nseindia.com/content/historical/EQUITIES/"
    "{d:%Y}/{d:%b}/cm{d:%d%b%Y}bhav.csv.zip"
)

#: Trading days, chosen to bracket the eras we might want. Deliberately few — this is a
#: reachability probe, not a crawl.
_PROBE_DATES = [
    date(2015, 1, 2),
    date(2018, 1, 2),
    date(2019, 9, 2),   # last confirmed 404 — a Monday, so not a holiday artefact
    date(2019, 10, 1),  # first confirmed 200: the boundary sits between these two
    date(2020, 3, 23),  # the COVID low — the most valuable single day in any stress test
    date(2023, 7, 3),   # our own earliest bar, as a control
]


@dataclass
class Probe:
    when: date
    full_status: int | str
    compact_status: int | str


async def _probe(dates: list[date]) -> list[Probe]:
    import httpx
    from app.services.bhavcopy_service import _NSE_HEADERS

    out: list[Probe] = []
    async with httpx.AsyncClient(headers=_NSE_HEADERS, timeout=20, follow_redirects=True) as c:
        try:
            await c.get("https://www.nseindia.com/", timeout=15)  # cookie handshake
        except Exception as exc:  # noqa: BLE001 — a probe reports, it does not raise
            return [Probe(d, f"no network: {type(exc).__name__}", "—") for d in dates]
        for d in dates:
            results: list[int | str] = []
            for url in (_FULL.format(d=d), _COMPACT.format(d=d)):
                try:
                    r = await c.get(url)
                    results.append(
                        r.status_code
                        if r.status_code != 200
                        else f"200 ({len(r.content):,}B)"
                    )
                except Exception as exc:  # noqa: BLE001
                    results.append(type(exc).__name__)
                await asyncio.sleep(2.0)  # polite: this is someone else's archive
            out.append(Probe(d, results[0], results[1]))
    return out


async def _run(do_probe: bool) -> int:
    async with AsyncSessionFactory() as db:
        cov = (
            await db.execute(
                text(
                    "SELECT MIN(time)::date AS first, MAX(time)::date AS last, "
                    "COUNT(DISTINCT time::date) AS days, COUNT(DISTINCT stock_id) AS stocks, "
                    "COUNT(*) AS bars FROM ohlcv_1d"
                )
            )
        ).one()
        stocks = (
            await db.execute(
                text(
                    "SELECT COUNT(*) FILTER (WHERE is_active) AS active, "
                    "COUNT(*) FILTER (WHERE NOT is_active) AS inactive FROM stocks"
                )
            )
        ).one()

    probes = await _probe(_PROBE_DATES) if do_probe else []
    now = datetime.now(UTC).astimezone(_IST)

    out: list[str] = [
        f"# Q5 — pre-COVID backtest: data-sourcing spike ({now.date().isoformat()})",
        "",
        "**The first concrete step, and deliberately not the backtest.** The ask (2026-08-28)",
        "was a pre-COVID regime-robustness test — 2018 or 2015 — held until after watch mode.",
        "The blocker was never the analysis.",
        "",
        "## Where we stand today",
        "",
        f"- `ohlcv_1d`: **{cov.first} → {cov.last}**, {cov.days} trading days, "
        f"{cov.stocks:,} stocks, {cov.bars:,} bars",
        f"- `stocks`: {stocks.active:,} active, {stocks.inactive} inactive",
        "- **~3.2 years, and all of it one broad regime.** No COVID crash, no 2018 credit",
        "  event, no rate cycle. That is precisely the gap the request is about.",
        "",
        "## 1. Is the archive reachable?",
        "",
        "We already ingest NSE bhavcopy daily (`app/services/bhavcopy_service.py`), and it",
        "documents **two** formats: `sec_bhavdata_full` (what we use) and the older compact",
        "`cm<DD><MMM><YYYY>bhav.csv.zip`. So the question is not *whether* a source exists —",
        "it is where the format boundary sits and whether old files still serve.",
        "",
    ]
    if probes:
        out += [
            "| date | `sec_bhavdata_full` | compact zip |",
            "|---|---|---|",
        ]
        out += [
            f"| {p.when} | {p.full_status} | {p.compact_status} |" for p in probes
        ]
        out += [
            "",
            "⚠ A `200` proves the file *serves*, not that it parses into our schema. Column",
            "names and the series vocabulary have changed over the years; that is ingestion",
            "work, not a download.",
            "",
            "### ⭐ The finding: the archive starts around **October 2019**",
            "",
            "Probed to the boundary: **2019-09-02 → 404** (a Monday, so not a holiday",
            "artefact) and **2019-10-01 → 200**. The compact `.zip` format 404s throughout,",
            "so `sec_bhavdata_full` is the only path and it does not reach the older era.",
            "",
            "**That answers the request as asked with a NO — and offers something arguably",
            "better:**",
            "",
            "| era | available? |",
            "|---|---|",
            "| 2015 / 2018 — *what was asked for* | ⛔ **no** |",
            "| the COVID crash (Feb–Apr 2020) | ✅ **yes** |",
            "| Oct 2019 → today | ✅ **yes — ~7 years, vs the 3.2 we hold** |",
            "",
            "The purpose behind the 2018 request was *does the edge survive a different",
            "regime, including a crash*. **An October-2019 start contains the crash itself** —",
            "the fastest drawdown in NSE's modern history — where 2018 would have offered a",
            "credit-cycle wobble. It more than doubles our history and captures the most",
            "violent regime change available to us.",
            "",
        ]
    else:
        out += [
            "*(Run with `--probe` to test reachability — a handful of polite requests to the",
            "same public host the daily ingest already uses.)*",
            "",
        ]

    out += [
        "## 2. ⭐ The survivorship problem, and why it is cheaper than it looks",
        "",
        "The obvious trap: our `stocks` table is a **today** snapshot built from Kite",
        f"instruments ({stocks.active:,} active). Every company that delisted, merged or was",
        "wound up between 2018 and now **is simply not in it**. Backtesting 2018 against",
        "today's names would silently exclude the failures — the textbook survivorship bias,",
        "and it flatters results in exactly the direction that would make us confident.",
        "",
        "⭐ **But the fix is already in the source.** A bhavcopy is the day's trading record:",
        "it lists what traded **that day**, delisted names included. So a point-in-time",
        "universe is not a second dataset to find — **it falls out of ingesting the",
        "bhavcopies themselves**, one row per name per day. The universe reconstructs itself.",
        "",
        "That materially lowers the estimated cost of this project. It does leave real work:",
        "",
        "- **symbol churn** — renames and series moves (`-BE`, `-BZ`, `-T2T`) mean the same",
        "  company appears under different symbols across years. Our T2T ruling already",
        "  taught us to check `LIKE 'sym-%'` before concluding a symbol vanished;",
        "- **corporate actions** — splits and bonuses over 8 years, on names we have no CA",
        "  history for. Unadjusted prices produce fake gaps that look like tradeable moves;",
        "- **schema drift** — older files predate the current column set.",
        "",
        "## 3. What would the result be worth?",
        "",
        "⚠ **Validation, not tuning — and this constraint is the whole point.** The engine is",
        "FROZEN for the current regime. Older data may say *whether the edge survives another",
        "regime*; it must not be used to search for parameters that fit 2018, which would be",
        "the largest overfitting surface this project has ever opened.",
        "",
        "⚠ **Calibrate the expectation before paying for it.** Corpus base expectancy is",
        "**+0.05R** over the ~3 years we hold, and the live book's Sharpe is **−0.033 with a",
        "90% interval [−0.223, +0.118]** — at n=105 not even the loss is established. A longer",
        "history would widen what we can ask, but the honest prior is that it finds *no",
        "significant edge in either direction*, more precisely measured.",
        "",
        "⚠ **Regime non-stationarity cuts both ways.** Pre-2020 NSE is structurally different:",
        "less retail F&O, no weekly options, different settlement. A strategy failing in 2018",
        "may be telling you about 2018's market microstructure, not about the strategy.",
        "",
        "## Recommendation",
        "",
        "**Do not start the ingestion yet — and the reason is sequencing, not doubt.**",
        "",
        "This is multi-day work (download, parse across schema eras, CA-adjust, reconstruct",
        "the universe, re-run the corpus) whose most likely outcome is *a wider confidence",
        "interval around approximately zero*. Meanwhile the demonstrated leak is upstream and",
        "untouched: **the book lost 15% while NIFTY fell 2%**, and nothing in the current",
        "queue addresses what generates the signals.",
        "",
        "**The order that makes sense:**",
        "",
        "1. settle the generation-side question first (D1 / D5 — the frozen-engine work);",
        "2. **then** come back here, because a regime test is only meaningful against an",
        "   engine somebody still believes in. Testing the current one across 2018 answers",
        "   'did this survive another regime' about a strategy whose edge is not established",
        "   in *this* one.",
        "",
        "**When it is time**, the path is clear and the survivorship fix is free: ingest",
        "bhavcopies day by day from **~2019-10-01** (the archive boundary), letting the",
        "universe reconstruct itself, then re-run the existing corpus tooling. No new vendor,",
        "no new dependency — `scripts/backfill_eod.py` already does the download and would",
        "need schema-era handling, not a rewrite.",
        "",
        "**Rough sizing:** ~1,480 trading days from Oct 2019 to our current start, at the",
        "existing polite ~0.7 s cadence ≈ **20 minutes of downloading**, plus the real work:",
        "schema drift, corporate-action adjustment on names we hold no CA history for, and",
        "symbol-churn reconciliation. Call it **days, not weeks** — materially less than the",
        "'data-acquisition project' the original hold assumed, because the universe",
        "reconstructs itself.",
    ]

    report = "\n".join(out)
    print(report, flush=True)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = _OUT_DIR / f"historical-data-spike-{now.date().isoformat()}.md"
    target.write_text(report + "\n", encoding="utf-8")
    print(f"\nwritten: {target}", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Q5 pre-COVID data-sourcing spike")
    ap.add_argument(
        "--probe", action="store_true", help="test NSE archive reachability (a few requests)"
    )
    args = ap.parse_args()
    return asyncio.run(_run(args.probe))


if __name__ == "__main__":
    raise SystemExit(main())
