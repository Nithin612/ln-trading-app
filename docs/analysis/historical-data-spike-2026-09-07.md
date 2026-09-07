# Q5 — pre-COVID backtest: data-sourcing spike (2026-09-07)

**The first concrete step, and deliberately not the backtest.** The ask (2026-08-28)
was a pre-COVID regime-robustness test — 2018 or 2015 — held until after watch mode.
The blocker was never the analysis.

## Where we stand today

- `ohlcv_1d`: **2023-07-03 → 2026-09-04**, 786 trading days, 2,361 stocks, 1,384,699 bars
- `stocks`: 2,365 active, 15 inactive
- **~3.2 years, and all of it one broad regime.** No COVID crash, no 2018 credit
  event, no rate cycle. That is precisely the gap the request is about.

## 1. Is the archive reachable?

We already ingest NSE bhavcopy daily (`app/services/bhavcopy_service.py`), and it
documents **two** formats: `sec_bhavdata_full` (what we use) and the older compact
`cm<DD><MMM><YYYY>bhav.csv.zip`. So the question is not *whether* a source exists —
it is where the format boundary sits and whether old files still serve.

| date | `sec_bhavdata_full` | compact zip |
|---|---|---|
| 2015-01-02 | 404 | 404 |
| 2018-01-02 | 404 | 404 |
| 2019-09-02 | 404 | 404 |
| 2019-10-01 | 200 (213,174B) | 404 |
| 2020-03-23 | 200 (213,692B) | 404 |
| 2023-07-03 | 200 (276,637B) | 404 |

⚠ A `200` proves the file *serves*, not that it parses into our schema. Column
names and the series vocabulary have changed over the years; that is ingestion
work, not a download.

### ⭐ The finding: the archive starts around **October 2019**

Probed to the boundary: **2019-09-02 → 404** (a Monday, so not a holiday
artefact) and **2019-10-01 → 200**. The compact `.zip` format 404s throughout,
so `sec_bhavdata_full` is the only path and it does not reach the older era.

**That answers the request as asked with a NO — and offers something arguably
better:**

| era | available? |
|---|---|
| 2015 / 2018 — *what was asked for* | ⛔ **no** |
| the COVID crash (Feb–Apr 2020) | ✅ **yes** |
| Oct 2019 → today | ✅ **yes — ~7 years, vs the 3.2 we hold** |

The purpose behind the 2018 request was *does the edge survive a different
regime, including a crash*. **An October-2019 start contains the crash itself** —
the fastest drawdown in NSE's modern history — where 2018 would have offered a
credit-cycle wobble. It more than doubles our history and captures the most
violent regime change available to us.

## 2. ⭐ The survivorship problem, and why it is cheaper than it looks

The obvious trap: our `stocks` table is a **today** snapshot built from Kite
instruments (2,365 active). Every company that delisted, merged or was
wound up between 2018 and now **is simply not in it**. Backtesting 2018 against
today's names would silently exclude the failures — the textbook survivorship bias,
and it flatters results in exactly the direction that would make us confident.

⭐ **But the fix is already in the source.** A bhavcopy is the day's trading record:
it lists what traded **that day**, delisted names included. So a point-in-time
universe is not a second dataset to find — **it falls out of ingesting the
bhavcopies themselves**, one row per name per day. The universe reconstructs itself.

That materially lowers the estimated cost of this project. It does leave real work:

- **symbol churn** — renames and series moves (`-BE`, `-BZ`, `-T2T`) mean the same
  company appears under different symbols across years. Our T2T ruling already
  taught us to check `LIKE 'sym-%'` before concluding a symbol vanished;
- **corporate actions** — splits and bonuses over 8 years, on names we have no CA
  history for. Unadjusted prices produce fake gaps that look like tradeable moves;
- **schema drift** — older files predate the current column set.

## 3. What would the result be worth?

⚠ **Validation, not tuning — and this constraint is the whole point.** The engine is
FROZEN for the current regime. Older data may say *whether the edge survives another
regime*; it must not be used to search for parameters that fit 2018, which would be
the largest overfitting surface this project has ever opened.

⚠ **Calibrate the expectation before paying for it.** Corpus base expectancy is
**+0.05R** over the ~3 years we hold, and the live book's Sharpe is **−0.033 with a
90% interval [−0.223, +0.118]** — at n=105 not even the loss is established. A longer
history would widen what we can ask, but the honest prior is that it finds *no
significant edge in either direction*, more precisely measured.

⚠ **Regime non-stationarity cuts both ways.** Pre-2020 NSE is structurally different:
less retail F&O, no weekly options, different settlement. A strategy failing in 2018
may be telling you about 2018's market microstructure, not about the strategy.

## Recommendation

**Do not start the ingestion yet — and the reason is sequencing, not doubt.**

This is multi-day work (download, parse across schema eras, CA-adjust, reconstruct
the universe, re-run the corpus) whose most likely outcome is *a wider confidence
interval around approximately zero*. Meanwhile the demonstrated leak is upstream and
untouched: **the book lost 15% while NIFTY fell 2%**, and nothing in the current
queue addresses what generates the signals.

**The order that makes sense:**

1. settle the generation-side question first (D1 / D5 — the frozen-engine work);
2. **then** come back here, because a regime test is only meaningful against an
   engine somebody still believes in. Testing the current one across 2018 answers
   'did this survive another regime' about a strategy whose edge is not established
   in *this* one.

**When it is time**, the path is clear and the survivorship fix is free: ingest
bhavcopies day by day from **~2019-10-01** (the archive boundary), letting the
universe reconstruct itself, then re-run the existing corpus tooling. No new vendor,
no new dependency — `scripts/backfill_eod.py` already does the download and would
need schema-era handling, not a rewrite.

**Rough sizing:** ~1,480 trading days from Oct 2019 to our current start, at the
existing polite ~0.7 s cadence ≈ **20 minutes of downloading**, plus the real work:
schema drift, corporate-action adjustment on names we hold no CA history for, and
symbol-churn reconciliation. Call it **days, not weeks** — materially less than the
'data-acquisition project' the original hold assumed, because the universe
reconstructs itself.
