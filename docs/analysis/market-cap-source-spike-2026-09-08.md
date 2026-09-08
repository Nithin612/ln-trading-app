# D3 — free market-cap source spike (2026-09-08)

**Question (D3):** the MCE roadmap needs `market_cap_cr`, which has no writer — the standing
"keystone blocker" that was assumed to require a **paid vendor** or the heavy XBRL scraper
(MCE 5b). The user chose a **free-source spike** before committing to any vendor: is there a
free, official source that can populate market cap?

`market_cap = price × shares_outstanding`. We already store price (OHLCV). The missing
quantity is **shares outstanding**, and it has no free path in our *current* feeds — which is
what made this a "vendor decision" at all.

## What was checked

| source | reachable here? | carries market cap / shares? |
|---|---|---|
| `sec_bhavdata_full` (daily equity bhavcopy) | ✅ | ❌ OHLCV + delivery only |
| `ind_close_all_<date>.csv` (the vix/index file) | ✅ | ❌ per-**index** (Index Name, O/H/L/C, P/E, P/B) — no per-stock row |
| NSE equity lists (EQUITY_L / index constituents) | ✅ | ❌ symbol/ISIN/face-value, no mcap |
| **NSE `/api/quote-equity` (+ `section=trade_info`)** | ⚠ **403 from here** | ✅ **`securityInfo.issuedSize` (shares outstanding) + `trade_info.totalMarketCap` + `ffmc`** |

## Verdict — ⭐ NO VENDOR IS NEEDED; a free official path exists

- **No free BULK file** carries per-stock market cap (confirmed against the reachable archives).
- **A free per-symbol path exists on the NSE `/api/` surface the app ALREADY uses in production.**
  `app/services/fii_dii_service.py` fetches `api/fiidiiTradeReact` and
  `app/ingestion/filings_consumer.py` fetches `api/corporate-announcements` with the same cookie
  warm-up (`_NSE_HEADERS` + a prior GET to `nseindia.com`). `api/quote-equity?symbol=X` returns
  **`issuedSize`** (shares outstanding) and `&section=trade_info` returns **`totalMarketCap`** and
  **`ffmc`** (free-float mcap). So `market_cap = issuedSize × price` is computable **daily from the
  OHLCV we already store**, after only an occasional shares-outstanding fetch.
- **Shares outstanding changes rarely** — only on splits/bonuses/issuance — so this is a **one-time
  backfill + a corporate-action-triggered refresh**, not a daily 2,000-symbol scrape. Far lighter
  than the XBRL scraper MCE 5b proposed, and $0.

## ⚠ The verification gap (be honest)

NSE `/api/` returned **HTTP 403 Access Denied** from this environment's datacenter IP, so the exact
`quote-equity` field names and the practical rate limit could **not be confirmed live here**. But the
identical auth pattern already powers the app's working FII/DII and filings fetches, so the path is
viable **from the app's own IP** — confirm the field names and a polite cadence there before building.

## ⇒ D3 resolution

**The vendor question is answered: no vendor.** The "market_cap has no writer → pick a vendor"
keystone framing is **retired** — there is a free, official, low-maintenance path (issuedSize × price
via the NSE `/api/` the app already speaks), and MCE 5b's heavy XBRL scraper is unnecessary.

**But do NOT build it yet.** Nothing needs `market_cap_cr` today: F1 (`size-proxy-spike-2026-09-07.md`)
killed the entry-gate size floor (MCE 5b dropped), and cycle 2 does not use it. The only inert
consumer is the screener's `market_cap_cr` filter. Build the writer when a real consumer appears
(a fundamentals/quality feature, or reviving the screener filter) — starting from this free path, not
a vendor purchase. Step 0 at that point: verify the `quote-equity` fields from the app's IP.
