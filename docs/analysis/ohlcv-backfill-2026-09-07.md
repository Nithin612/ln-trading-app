# `ohlcv_1d` history backfill (2026-09-07)

Requested **2023-07-03 → 2026-09-05**; 830 weekdays fetched this run.

| outcome | days |
|---|--:|
| ingested | 818 |
| holiday / not published (404) | 12 |
| failed | 0 |

**1,618,965 bars inserted this run.**

## `ohlcv_1d` now

- **2020-03-20 → 2026-09-04** — 792 trading days
- 1,628,241 bars across 3,303 distinct names
- 2,001 inactive stocks (delisted/historical names carrying the point-in-time
  universe — see `_ensure_historical_stocks`)

> **Update 2026-09-08** — a subsequent run extended coverage past this recovery
> snapshot all the way to the archive floor. Live `ohlcv_1d` now spans
> **2019-10-01 → 2026-09-04** — 1,093 trading days, **2,076,769 bars** across
> **3,373 names** (2,070 inactive/historical). The full ~7-year Q5 target is met;
> the pre-COVID regime backtest that consumes it is still sequenced after D1/D5.

## ⚠ Carry these into any study built on this data

- **Prices are UNADJUSTED for corporate actions.** Over 7 years every split and
  bonus reads as a large overnight gap that is not a tradeable move. A multi-year
  backtest must handle this or it will find spectacular fake edges.
- **EQ series only** — consistent with daily ingestion and the T2T ruling, but a
  name that moved to T2T disappears rather than continuing.
- **Symbol churn is unresolved** — a renamed company appears as two unrelated
  symbols. Check `LIKE 'sym-%'` before concluding a symbol vanished.
- **No recorded number changed.** This adds historical bars only.
