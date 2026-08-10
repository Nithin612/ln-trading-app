# Interstitial slice — Intraday activation + v1 surface uplift

**2026-08-07 → 08-10 · merged to main and pushed · commits `4d4554d`,
`ec5ae30`, `e3003b9`, `b795326`.**

Not a numbered phase. Agreed as the work to do *before* Phase 6, so that its
noise wouldn't land inside the phase. Origin: an audit on 2026-08-07 asking a
plain question — "does the Intraday menu work like F&O, Swing and Investment,
and do the supporting menus work like a pro?" The answer was no, for reasons
that were not visible from the docs.

---

## 1. The audit finding that started it

**Intraday had never produced a single signal.** Verified against the live DB,
not the docs: the `signals` table contained only `swing` (168) and `positional`
(68) rows, all `timeframe='1d'`, for all time. Two independent causes, and only
the first was known:

1. The three intraday profiles (`pdh_pdl`, `orb_15m`, `gainer_925`) were
   `status='inactive'`.
2. **Nothing scheduled them either way.** `nightly_suggestions` ran only the
   `'eod'` schedule; `on_close_suggestions` was still a Phase-3 stub returning
   `{"status": "stub"}`. The `intraday_15m` and `time_0925` schedules had *no
   caller anywhere in the codebase*. The menu was structurally unable to
   populate regardless of profile status.

Data was never the blocker — `ohlcv_15m` held 4.95M rows and `ohlcv_5m` 14.5M.
Nothing consumed them.

## 2. What shipped

### 2.1 Stock master repaired (`4d4554d`)

Went in to widen sector coverage; found two larger defects underneath.

- **No stock had a correct company name.** `EQUITY_L.csv` carries a
  `NAME OF COMPANY` column that `fetch_equity_universe` never read, so
  `company_name` was the ticker itself for **2,274 of 2,333** active stocks —
  and for the 59 index members it was the **sector**, because the caller indexed
  a `{symbol: industry}` map as if it held names. ADANIENT was named
  "Metals & Mining". That string was rendering in the screener, watchlist
  search, stock detail and CSV export. `company_name` was also missing from the
  upsert's `DO UPDATE SET`, so a reseed could never repair a name once written.
- **The reseed had silently stopped working.** The upsert conflicts on
  `(symbol, exchange)`, but `uq_stocks_isin` must hold too — so an NSE ticker
  rename arrives as a NEW symbol carrying the OLD row's ISIN, dies on the ISIN
  constraint, and rolls the entire run back. Six real renames were blocking it:
  AMIRCHAND→AEROPLANE, ASHIKA→ASHIKAG, LYPSAGEMS→AURUS, GUJGASLTD→GUJENERGY,
  MIRCELECTR→ONIDA, VISASTEEL→VISACHROME.
- `plan_renames()` resolves a rename **in place** — same company, so the row
  keeps its id and with it every OHLCV bar, signal and position pointing at it
  (GUJENERGY kept 738 daily bars, ONIDA 376). A fresh row would strand that
  history under a ticker NSE no longer publishes. When BOTH tickers already
  exist, choosing the canonical history is not a seed script's call: reported as
  a collision, incoming row written without its ISIN, nothing merged.
- Sector source widened to Nifty 500: coverage **59 → 500**. Market cap stays
  unpopulated — NSE publishes no free shares-outstanding source — so the
  screener reports it honestly rather than offering a filter that cannot work.
- Measured after reseed: `company_name` = ticker **2,274 → 2**; = sector
  **59 → 0**; inactive rows **15 → 15**, so the 2026-07-17 T2T deactivation
  ruling survived untouched (`is_active` is deliberately absent from the update
  list).

### 2.2 v1 surface uplift (`ec5ae30`)

- **Watchlists had no prices.** The page rendered symbol + company name and
  nothing else — the only live surface in the app without quotes, while the
  backend had been fanning ticks out *per watchlist* since Phase 3. Now a real
  table with live LTP, change % and previous close. `prev_close` is the last
  **completed** daily close: today's daily bar does not exist until EOD
  ingestion (~18:40 IST), so during a session this correctly resolves to
  yesterday. Comparing a live LTP against the bar the same tick is building
  would report every stock as flat.
- **The screener silently returned nothing on sparse columns.** A filter on a
  mostly-null field matches almost no rows, which reads as "no stocks match"
  when the truth is "this data isn't loaded" — sector sat at 59 of 2,333 for
  months behind exactly that ambiguity. New `GET /screener/fields` returns each
  field with a **counted** `populated`, and a filter row now says "Only 500 of
  2,365 stocks have a sector". Counted per request, never hardcoded: the number
  moves on every reseed.
- **The Intraday page blamed the clock.** Every style showed "generated nightly
  after EOD" — true for the EOD-scheduled styles, false for intraday. It now
  states the real reason.

### 2.3 The intraday shadow layer (`e3003b9`, fixed in `b795326`)

**`status='shadow'` is a third profile state:** the profile runs on its real
schedule and its suggestions are measured to outcome, but they are never
tradeable.

Why not simply activate? Walk-forward says not to — all three are negative
risk-adjusted (pdh_pdl −1.06 Sharpe, orb_15m −0.60, gainer_925 −0.86 at 32% max
drawdown; gainer_925's headline +56.2% is **+0.004% per trade** over 12,935
trades, i.e. noise before costs, and it was already flattered ~2× by a
look-ahead fixed in 8c-4). But leaving them off produced no evidence, so that
backtest verdict was never going to be revisited. Shadow replaces it with
forward evidence.

**Untradeability is enforced by code that already existed**: the order path
admits `status == "active"` only, so a shadow signal is rejected there (409)
without a new flag anyone must remember.

Scheduler: `intraday_suggestions` on a beat at `:01/:16/:31/:46` — one minute
after each 15m bar closes, so the scored bar is complete. The stub's design (one
task per stock per candle-close event) was dropped deliberately: the profiles
score completed bars and bar boundaries are known in advance, so a beat is the
same computation without depending on the tick pipeline being healthy.

## 3. The review round (`b795326`) — read this part

**quant-verifier returned FAIL on the first cut and was right.** Recorded in
full because the CRITICAL is a design lesson, not a typo.

- **CRITICAL — shadow results were counted as real performance.**
  `/analytics/outcomes` grouped by style with no shadow filter, so every shadow
  outcome landed in the intraday hit-rate/expectancy that StylePage renders as
  "Tracked outcomes". Shadow profiles are *precisely* the ones that have not
  earned activation, so this dragged the headline numbers toward a strategy
  nobody trades — corrupting the evidence the layer exists to produce.
- **The deeper half: `status` cannot carry provenance.** It is a LIFECYCLE
  field — the sweeper overwrites it with `'expired'`, and expiry is exactly when
  an outcome finalises. Filtering `status <> 'shadow'` would have excluded the
  handful still live and counted the entire finalised history. Hence an
  immutable **`signals.is_shadow`**, written once at mint. `strategy_profiles.status`
  was no substitute either — it is mutable, so activating a profile later would
  retroactively relabel its whole shadow history as tradeable evidence.
  **Every tradeable statistic must filter `is_shadow IS FALSE`.**
- **HIGH — the 09:16 IST beat scored the previous session.** It passes the
  session guard but precedes the day's first 15m close (09:30 IST), so
  `_load_window` returned yesterday's 15:15 bar; the setups pass on it (a stale
  close sits far above yesterday's PDH) and the resulting signal took the
  one-per-(stock, profile) dedup slot, suppressing every genuine run that day.
  Window narrowed to 09:31–15:16 IST, plus `stale_decision_bar_day()` rejecting
  any decision bar not from today's session — which also covers a day when the
  live worker never started because the Kite token wasn't refreshed.
- **HIGH — the 15:16 IST beat minted 24-hour "intraday" signals.**
  `compute_validity_until` rolls the deadline forward past 09:45 UTC (correct
  for the nightly EOD caller), so a late beat produced a signal spanning the
  overnight gap — on a Friday, expiring on a **Saturday**.
  `past_intraday_cutoff()` refuses it, leaving `expiry.py` untouched.
- **MEDIUM** — the alert shadow stamp failed *open* (a missing key drew a Buy
  button); positional `r[8]` row access would silently re-map that same flag if
  a column were ever inserted.

**A note on how one of these fixes was nearly wrong.** The first freshness guard
used a minutes-based age threshold and passed — but only because it was 3am. The
same tests would have failed at 10am, since the fixtures stamp bars with today's
date. It was replaced with an IST *trading-date* comparison, which is the actual
invariant. A test that passes at night and fails in the morning is worse than
the bug it guards.

## 4. §8 of the daily report

The layer exists to replace a negative backtest verdict with forward evidence,
so **a silent layer is a failed layer** — "no evidence yet" and "evidence says
no" must never look the same. `make analysis` now reports per shadow profile:
minted / resolved / W-L, and when the count is zero, **why** — distinguishing
"not a trading day" from "NO bars for the day, the live worker produced nothing
(check the Kite token ritual)" from "ran but nothing cleared the confidence
gate". Attribution is checked in failure order, because blaming the wrong gate
turns a dead worker into an apparent strategy failure. Same reasoning as §7 F&O
engine health, one step earlier in the funnel.

## 5. First live session — Monday 2026-08-10

**Every scheduled beat fired.** From Celery's own result records (Redis db 2):

```
09:26:13  SUCCESS  time_0925     {'gainer_925': 0}
09:31:25  SUCCESS  intraday_15m  {'pdh_pdl': 0, 'orb_15m': 0}
09:46:25  SUCCESS  intraday_15m  {'pdh_pdl': 0, 'orb_15m': 0}
10:01:26  SUCCESS  intraday_15m  {'pdh_pdl': 0, 'orb_15m': 0}
10:16:29  SUCCESS  intraday_15m  {'pdh_pdl': 0, 'orb_15m': 0}
```

Data was healthy throughout — 6,197 fresh 15m bars, live worker writing 1m bars
current to 10:01 IST — and invoking the task body directly at 10:05 reproduced
the same result. So the runner works end to end, on schedule, and **the zeros
come from "nothing cleared the confidence gate", not from a broken pipeline.**

The stack was stopped ~09:32 and restarted ~09:46. That window fell entirely
between two 15m slots (09:31 and 09:46), so nothing was lost — but a restart
straddling a slot would silently skip it, and beat does not backfill.

**A method correction worth carrying forward.** The first read of this session
claimed the 09:26 and 09:31 beats had been *missed*, inferred from the Celery
process's uptime (~1,066 s at 10:02, implying a 09:44 start). That was the
**restarted** process; the beats had already run before the restart. Process
uptime is not evidence of when a beat fired. The authoritative record is the
result backend — and two things make it awkward to read: results carry **no task
name** unless `result_extended` is enabled, and they live in **Redis db 2**
(`celery_result_backend`), not db 0. Identify a task by the shape of its return
payload instead. Beat's own `celerybeat-schedule.db` shelve was no help: it held
only `__version__`, having been reset on restart.

## 6. What is still unknown

Signal **production** across a full session remains unmeasured — one 10:05 IST
sample of zero is not a verdict. Read §8 in `docs/analysis/` over the coming
sessions. If it shows zeros for several days running, the honest question is
whether `min_confidence: 70` is simply unreachable for these setups. That would
be a real finding about the profiles, and it is exactly what the shadow layer
was built to surface — **do not "fix" it by lowering the gate without
evidence.**

## 7. Also fixed en route

- Journal and Portfolio 401'd on **every** request (`7bcaaf9`, merged earlier):
  neither API module ever took a token, so no request from either carried an
  `Authorization` header. Both features were entirely unusable against a live
  backend while their page tests stayed green — the mocks sit at the API-module
  boundary, so the seam was never exercised. Fixed in the client, with
  `src/test/apiClient.test.ts` now covering that seam.
- `GET /filings/recent` 422'd on the Filings page's own default view (a 7-day
  range spans 8 calendar days → `hours=192` over a `le=168` cap), and the same
  request silently discarded the end date.
- `kite_instruments` was 15 days stale; re-synced 2026-08-10 (61,427 → 56,318
  rows, 5,109 carcasses swept). Active stocks with no instrument-token match:
  308 → **281**, of which 271 are the known T2T/-BE cohort that also receives no
  EOD bars. **Zero F&O stocks unmatched**, so the intraday shadow universe is
  fully mapped.
