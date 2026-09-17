# `ohlcv_1d` history backfill (2026-09-17)

Requested **2026-02-01 → 2026-02-01**; 1 candidate days fetched this run.

| outcome | days |
|---|--:|
| ingested | 1 |
| holiday / not published (404) | 0 |
| failed | 0 |

**2,411 bars inserted this run.**

## `ohlcv_1d` now

- **2019-10-01 → 2026-09-17** — 1,727 trading days
- 3,166,300 bars across 3,402 distinct names
- 1,116 inactive stocks (delisted/historical names carrying the point-in-time
  universe — see `_ensure_historical_stocks`)

## ⚠ Carry these into any study built on this data

- **Prices are UNADJUSTED for corporate actions.** Over 7 years every split and
  bonus reads as a large overnight gap that is not a tradeable move. A multi-year
  backtest must handle this or it will find spectacular fake edges.
- **EQ series only** — consistent with daily ingestion and the T2T ruling, but a
  name that moved to T2T disappears rather than continuing.
- **Symbol churn is unresolved** — a renamed company appears as two unrelated
  symbols. Check `LIKE 'sym-%'` before concluding a symbol vanished.
- **No recorded number changed.** This adds historical bars only.
