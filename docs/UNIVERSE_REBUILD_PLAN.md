# Universe Rebuild Plan — stock master, sector map, index registry

**Status:** DRAFT for review · round 0 written 2026-09-12 · **round-1 adjudication (PART V)
2026-09-12** · **PART VI 2026-09-13 — the user's restore-vs-rebuild question** ·
⭐⭐ **PART VII 2026-09-13 is the round-3 adjudication and SUPERSEDES PART VI's mechanism,
its bar-count rule term, and four of its numbers. Read PART VII before acting on PART VI.**
**Author:** Claude (session 2026-09-12) · **Owner:** Nithin
**Nothing in this document has been executed.** No table was written, no flag flipped,
no migration run. Every number in PARTS I–V is a `SELECT` taken on **2026-09-12** against
the dev database `trading_platform`; every number in **PART VI is a `SELECT` taken on
2026-09-13** against the same database (re-measured, not carried forward).

---

## §0 · How to review this

This document goes to several external reviewers before anything is built. To make
disagreement cheap, it is written so that **every claim is separable from every other
claim**:

- **PART I (§1–§5) is measurement.** Facts with the query that produced them. If a
  reviewer disputes one, they should say which number is wrong and what they think it
  is — not argue about the plan.
- **PART II (§6–§7) is the restoration plan.** Deterministic repair of a known
  regression. This part should be uncontroversial; the review question is "is anything
  *missing*", not "is this right".
- **PART III (§8–§10) is the curation decision.** This is where judgement lives and
  where reviewers should spend their effort. It is deliberately NOT decided here.
- **PART IV (§11–§18) is the review protocol**, and it is two-way. §12 explains the
  window we are in (empty book ⇒ structural change is free right now, and why that does
  **not** lower the evidence bar for selection changes). §13 holds the six questions that
  block this plan; **§14 holds the ten architecture questions we actually want help
  with**; §15 tells you what you may ask *us* and what we cannot answer; §16 is how your
  points get dispositioned — ADOPT / **PARK** / REJECT, where *parked never means wrong*.
  **Appendix B is a five-point orientation for a reviewer new to this system** — read it
  first if you have not seen this project before.
- ⭐ **PART V (§19–§22) is the round-1 adjudication** of five external reviews. Read it
  before re-reading PART I: **§3a corrects §3's root cause**, which round 1 proved wrong,
  and §21 supersedes §7's ordering. §20 carries two findings no reviewer had, both found
  by checking a review against the database rather than against our own documents.
- ⭐⭐ **PART VI (§23–§24) is the live question, and it is upstream of everything above.**
  The user asked why we are repairing the old universe rather than rebuilding a better one
  while the book is empty. §23.1 corrects the premise (**nothing was deleted** — one
  boolean and one empty table broke), §23.3 proves by measurement that **U3 does not depend
  on U2**, and §23.6 proposes **REBUILD-D: derive, don't repair** — collapsing U2 into U13.
  ⚠ **§24 held six questions for round 3; they are answered in PART VII.**
- ⭐⭐ **PART VII (§25–§27) is the round-3 adjudication, and it corrects PART VI.**
  §25a carries the decisive fact of the whole exercise (**every one of the 3,392 `stocks`
  rows was created on 2026-09-07 — the rebuild already happened, improvised, in one night**).
  §25b lists **four errors in PART VI, all ours**. §25c confirms that D2's derived view
  cannot work **while refuting the reason given for it**. §26 is the revised REBUILD-D.
  ⭐ **§27 recommends closing the panel and building.**

⭐ **The one thing to internalise before reviewing:** this project has an explicit,
hard-won rule that a selection rule is never flipped on an argument (CLAUDE.md hard
constraint #8, earned by two promoted-then-reverted gates). A "universe" is a selection
rule. So this plan splits every proposed criterion into **structural** (no evidence bar
— it describes whether we *can* trade the instrument) and **empirical** (needs the
project's `t ≈ 3.6` bar or an explicit user ruling — it claims something about whether
we *should*). Reviewers who recommend a liquidity floor, a price floor, a market-cap
floor or a "top N names" universe are making an **empirical** claim and should say what
evidence would settle it. §9 explains why that particular recommendation has already
been measured here, and lost.

---

# PART I — MEASUREMENT

## §1 · What happened

| When | Event |
|---|---|
| 2026-09-07 | The dev database was destroyed by running `pytest` with `DATABASE_URL` pointed at it (`conftest.py` used `os.environ.setdefault`, and the autouse `clean_tables` fixture `TRUNCATE`d all 52 tables). No backup existed. |
| 2026-09-07 | Recovery: `ohlcv_1d` restored from the NSE bhavcopy archive (2.08 M bars) and `stocks` reseeded from public NSE CSVs via `scripts/seed_stocks.py`. |
| 2026-09-07 → now | **Undetected regression.** The recovery left the stock master in a state where the entire blue-chip universe is flagged `is_active = false`. Daily EOD ingestion writes bars only for active stocks, so those names have received **no daily bar since 2026-09-04** and the hole grows by one session per day. |
| 2026-09-11 | `make live-worker` reported `live-worker up: 0 instruments`. This is the symptom that prompted this document. |

The user's recollection ("the stock master earlier had ~2800 stocks plus some sector,
indices mapping") is accurate and is roughly what NSE publishes today: `EQUITY_L.csv`
currently carries **2,568 rows — 2,292 `EQ`, 249 `BE`, 27 `BZ`**.

## §2 · Measured state of the dev DB (2026-09-12)

### 2a. Row counts

| Table | Rows | Verdict |
|---|--:|---|
| `stocks` | 3,392 | present, but `is_active` is wrong (§3) |
| `stocks` where `is_active` | **1,322** | wrong set — see §2b |
| `kite_instruments` | **0** | ⛔ empty — this is the "0 instruments" |
| `ohlcv_1d` | 2,082,639 | restored, 3,375 distinct names, 2019-10-01 → 2026-09-11 |
| `index_ohlcv_1d` | 54 | ⛔ destroyed, not rebuilt |
| `india_vix_daily` | 18 | ⛔ destroyed, not rebuilt |
| `indices` | 3 | NIFTY50 / BANKNIFTY / FINNIFTY only |
| `index_constituents` | 89 | all `added_on = 2026-09-07`, all `weight_pct` NULL |
| `stocks` with a non-null `sector` | 500 of 3,392 | 20 distinct sectors |
| `strategy_profiles` | **0** | the style engines have nothing to run |
| `watchlists` / `watchlist_items` | 0 / 0 | |
| `signals` | 35 | all `active`, all non-shadow, 09-09 → 09-11 |
| `positions` / `orders` | 0 / 0 | cycle-1 book gone (known) |
| `cas_daily` | 86 | 1 session (known) |
| `nse_holidays` | 48 | 2023-08-15 → 2026-12-25 — **healthy** |
| `fo_bhavcopy` | 594,883 | survived |
| `corporate_filings` | 504 | survived |
| `alembic_version` | `e1f2a3b4c5d6` | **see §2d — a documentation correction** |

### 2b. ⛔ The headline: `is_active` is inverted for the real universe

```
RELIANCE    is_active = false
TCS         is_active = false
HDFCBANK    is_active = false
ABB, ABBOTINDIA, ABCAPITAL, AARTIIND, 3MINDIA … all false
```

| Flag | Active | Inactive |
|---|--:|--:|
| `is_nifty50` | **5** | **45** |
| `is_banknifty` | **0** | **14** |
| `is_finnifty` | 4 | 21 |
| `is_fno` | 45 | 167 |
| has a `sector` | 165 | 335 |

The 1,322 "active" names are dominated by recent listings and micro/small-caps. The top
of the active set by 2026-09-11 turnover is `PINELABS`, `MOLBIO`, `PAYTM`, `ESDS`,
`DHOOTTRANS`, `ATHERENERG` — no Nifty constituent appears, because none is active.

### 2c. The data consequence, measured

| Session | Names receiving a daily bar |
|---|--:|
| 2026-09-02 | 2,646 |
| 2026-09-03 | 2,632 |
| 2026-09-04 | 2,633 |
| **2026-09-07** | **1,182** ← the break |
| 2026-09-08 | 1,179 |
| 2026-09-09 | 1,175 |
| 2026-09-10 | 1,168 |
| 2026-09-11 | 1,166 |

`SELECT count(*) FROM ohlcv_1d o JOIN stocks s ON s.id = o.stock_id WHERE
o.time::date = '2026-09-11' AND NOT s.is_active` → **0**. Not one inactive name has
received a bar since the break.

**Engine readiness of the current active set** (the confluence engine's window canon is
the last 300 completed daily candles):

- active stocks with ≥ 300 bars: **751**
- active stocks with 50–299 bars: 343
- active stocks with < 50 bars: 211
- active stocks with **no bars at all**: 17

So the scorable universe today is ~751 names, weighted toward exactly the illiquid
micro-cap archetype the project has spent months learning to avoid — while 1,683
stocks holding ≥ 300 bars of history sit inactive.

### 2d. ⚠ Documentation correction (working rule W1)

`CLAUDE.md` and `MEMORY.md` both state: *"LEDGER MIGRATION `e1f2a3b4c5d6` NOT APPLIED TO
DEV (dev at `d0e1f2a3b4c5`)"*. **This is stale.** `alembic_version` reads
`e1f2a3b4c5d6` and the `ledger_entries` table exists (0 rows). Per W1 the executable
content wins and the doc gets fixed in the same change — this is queued as item **U0**
so it is not lost.

## §3 · Root cause — exact, and it is a one-line ownership gap

Two pieces of code, each individually correct, compose into the regression.

**(a) The survivorship-safety writer.** `app/services/bhavcopy_service.py:191`
`_ensure_historical_stocks()` creates a `stocks` row for any symbol the bhavcopy names
that we have never seen, deliberately **inactive**:

```sql
-- bhavcopy_service.py:216-218
INSERT INTO stocks (symbol, exchange, company_name, is_active)
SELECT s, 'NSE', s, false FROM unnest(CAST(:syms AS varchar[])) AS s
ON CONFLICT (symbol, exchange) DO NOTHING
```

Its docstring states the invariant it relies on:

> *"`ON CONFLICT DO NOTHING` means an existing ACTIVE row is never touched — this can
> only add, never deactivate."*

⭐ **That invariant holds only if `stocks` is populated first.** On an empty `stocks`
table every symbol is "never seen", so every symbol — RELIANCE included — is created
inactive.

**(b) The reseeder does not own `is_active`.** `scripts/seed_stocks.py` inserts with
`is_active = true` literal, but its conflict branch (`seed_stocks.py:354`,
`ON CONFLICT (symbol, exchange) DO UPDATE SET …`) updates `isin`, `company_name`,
`sector`, `industry`, `lot_size`, the four membership flags, `listed_on` and
`updated_at` — **and never `is_active`**.

**The composition.** On 2026-09-07 the bhavcopy restore ran against an empty `stocks`
table and created ~2,600 names inactive. `seed_stocks.py` then ran, matched them all on
conflict, repaired every column it owns — which is why `ABB` correctly reads
`"ABB India Limited"` — and left `is_active = false` untouched. Only symbols absent
from the bhavcopy-derived set were genuinely INSERTed, with `is_active = true`: new
listings and thin series. That is precisely the junk-weighted active set in §2b.

This is confirmed, not inferred:
- every `stocks` row has `created_at = 2026-09-07`;
- `forensic_stocks_deactivated` holds **15** rows, so `deactivate_dead_stocks.py` —
  the only other writer of `is_active = false` in the codebase — did not do this;
- a repo-wide grep finds exactly two writers of `is_active = false` for stocks
  (`bhavcopy_service.py:217`, `deactivate_dead_stocks.py:100`).

**Recovery-order dependency, stated plainly:** `seed_stocks.py` must run **before** any
bhavcopy ingestion on an empty database. Nothing in the code, the scripts or
`RUNBOOK.md` enforces or documents that today.

### 3a. ⛔⛔ CORRECTION (round 1, 2026-09-12) — the ordering above is WRONG, and the fix changes

⭐ **Credit: Claude's round-1 review (F1) found this by arithmetic, and it is confirmed.**
The review observed that 1,322 active − 17 with no bars = **1,305 active stocks that have
bars**, which under a strictly sequential "bhavcopy first on an empty table, then seed"
is impossible: every stock the backfill touched would have been created inactive.

**Measured, and it is decisive.** 1,303 active stocks hold bars dated *before* 2026-09-05
— `DMART`, `AFFLE`, `NEOGEN` each carry 1,045 bars back to 2019-10-01. Sequential
ordering cannot produce that.

⭐ **The row ids are a forensic fingerprint, because `_ensure_historical_stocks` inserts a
`sorted()` symbol list while `seed_stocks.py` iterates a `set` in hash order.** Grouping
`stocks` by id block:

| id block | rows | active | what created it |
|---|--:|--:|---|
| 1 – ~1,700 | 1,552 | **0** | `_ensure_historical_stocks`, alphabetical — 1,415 of them carry a 2019-10-01 bar, and that session has 1,484 names |
| ~1,700 – 9,276 | 0 | — | ~7,500 sequence values burned by `ON CONFLICT DO NOTHING` |
| 9,277 – 11,823 | 1,322 | **1,322 (100 %)** | `seed_stocks.py`'s INSERT branch |
| 11,750 – 2,157,287 | ~518 | **0** | `_ensure_historical_stocks` again, *after* the seed |

Spot-check: `ABB` id 15, `RELIANCE` id 1,140, `TCS` id 1,383 — all inactive, all in the
first block. `DMART` id 9,424, `NEOGEN` id 9,736, `AFFLE` id 10,063 — all active, all in
the seed block. And the **five active Nifty 50 names are `ETERNAL`, `JIOFIN`,
`MAXHEALTH`, `SHRIRAMFIN`, `TMPV`** — every one a recent listing or rename, i.e. precisely
the names the 2019-era bhavcopy could not have contained.

⇒ **The restore was INTERLEAVED: backfill → seed → backfill.** `is_active` does not encode
any property of the stock. It encodes **which process created the row first**.

⚠ **This changes the remedy, which is why it matters.** Under the original story, "seed
first" was a sufficient fix. Under the true story it is not: any `historical=True`
ingestion run that meets a symbol not yet in `stocks` creates it inactive, and
`seed_stocks.py`'s conflict branch can never repair it — so the hazard recurs on every
future backfill, independent of the 2026-09-07 disaster. ⭐ **The fix is therefore not an
ordering rule but an invariant: the price archive must never consult a trading flag** (see
U6′ in §21).

⚠ **One part of the round-1 finding does NOT survive.** The review stated that *"new
listings are permanently invisible right now."* Checked in code: `_ensure_historical_stocks`
is called **only** under `historical=True` (`bhavcopy_service.py:253`). Daily ingestion never
creates a stock — an unknown symbol is counted in `skipped` — so a genuine new listing is
picked up as ACTIVE by the next `seed_stocks.py` run. The hazard is real but narrower: it
is triggered by *historical backfills*, not by the daily path.

⚠ **Residual unknown, stated rather than guessed:** the exact run sequence that produced
the third block (a backfill re-run after the seed, filling bars for seed-created names) is
not fully reconstructible from the surviving evidence. The *mechanism* above is proven; the
precise operator command history is not.

## §4 · The cascade — what is broken downstream, and why none of it alarmed

| # | Broken | Mechanism |
|---|---|---|
| 1 | **Blue-chip EOD history frozen at 09-04** | `bhavcopy_service.py:255` — `active_only = "" if historical else " AND is_active = true"`. Daily ingestion writes bars for active stocks only. |
| 2 | **Nightly signal generation scans the wrong universe** | `signal_service.py:318` — `select(Stock).where(Stock.is_active.is_(True))`. It scores 1,322 mostly-microcap names, only 751 of which have enough bars to score at all. |
| 3 | **Live worker subscribes to nothing** | `tick_consumer.py:463-467` joins `kite_instruments` → `stocks`. `kite_instruments` is empty ⇒ 0 instruments ⇒ no ticks, no LTP, no depth, no provisional layer, no AlertBell entries. |
| 4 | **`deactivate_dead_stocks.py` is unusable** | Its input is `kite_instruments`. Run today it would see no EQ listing for anything and deactivate the entire master. ⛔ **Do not run it before §7/U1.** |
| 5 | **Every MCE overlay is unevaluable** | `market_regime`, `sector_rs` and `benchmark.py` (`_MARKET = "NIFTY50"`) read `index_ohlcv_1d` (54 rows) and `india_vix_daily` (18 rows). |
| 6 | **The style engines produce nothing** | `strategy_profiles` = 0 rows. |
| 7 | **Circuit-band overlay is dark** | Its market-hours task batches Kite `quote()` over the subscription universe. |

### 4a. ⛔ Why nothing caught it — two alarms, both blind in the same way

The 2026-09-12 daily report reads:

> ✅ **Feeds current as of report generation (≥ 2026-09-11): Equity EOD 2026-09-11** ·
> F&O bhavcopy 2026-09-11 · FII/DII flows 2026-09-11.

**The 6.8.6 silent-feed-outage alarm is green while half the universe is five sessions
stale.** It asserts *recency* (`max(time)`) and never *coverage* (how many names got a
bar, versus how many got one last week). A feed that halves its breadth overnight is
exactly the silent failure the alarm exists to catch, and it is structurally incapable
of seeing it. ⭐ This is the most generalisable defect in this document, and it is an
instance of the project's own `instrument_self_validation` rule: an alarm never run
against the failure it claims to cover has not been validated.

The same report's **worker-liveness alarm (A40) is firing correctly**:

> ⚠️ WORKER LIVENESS ALARM — **celery**: last heartbeat never seen · **live_worker**:
> last heartbeat never seen.

So `make worker` has not been up either. That is a separate, additive reason the
AlertBell is empty and why `cas_daily` is not accruing.

## §5 · What is NOT lost (do not rebuild these)

- **`ohlcv_1d`** — 2.08 M bars, 3,375 names, 2019-10-01 → 2026-09-11. Attribution is
  sound: `stocks` was seeded before the bars were attached, so `stock_id` → symbol
  mapping is internally consistent. ⚠ The bars remain **CA-unadjusted** (the known
  constraint; 49 unadjusted corporate actions sit in the top-250-liquid universe).
  ⚠ **The 922-day hole survived the restore — measured here, not cited:** distinct
  sessions per year are 2019: 61 · 2020: 246 · **2021: 0 · 2022: 0** · 2023: 123 ·
  2024: 248 · 2025: 248 · 2026: 172, for **1,098 sessions total**, and the single gap
  `2020-12-23 → 2023-07-03` is the only break longer than 5 days in the whole table.
  So the modern block (2023-07-03 onward) is session-contiguous, and the only breadth
  defect in it is the per-name hole this document is about.
- **`nse_holidays`** — 48 rows through 2026-12-25; the trading calendar is healthy.
- **`fo_bhavcopy`** (594,883) and **`corporate_filings`** (504).
- **Every free data source used by the recovery is still reachable** (verified live on
  2026-09-12): `EQUITY_L.csv` (2,568 rows), `ind_nifty500list.csv` (501 rows with an
  `Industry` column), and the NSE daily indices CSV (see §7/U8).

⚠ **One reproducibility caveat to carry forward:** every `stocks.id` was reassigned on
2026-09-07. Any artifact written before that date which recorded a raw `stock_id`
(probe JSONL dumps, analysis tables) now points at a different symbol. Re-derive from
symbols, never from a pre-09-07 id.

---

# PART II — RESTORATION (structural; should be uncontroversial)

## §6 · Design principles

1. **Separate restoration from curation.** Repairing `is_active` to mean what it always
   meant is a bug fix. Deciding that we should henceforth trade fewer names is a
   selection decision. They must not ride in the same commit.
2. **Structural vs empirical criteria.** A criterion is *structural* if it describes
   whether we can transact the instrument or compute on it at all (is it listed; is the
   series deliverable; do we have ≥ 300 bars). A criterion is *empirical* if it claims
   the instrument is a worse bet (liquidity floor, price floor, market-cap floor). ⭐
   **Structural criteria need no evidence bar. Empirical criteria need the project's
   `t ≈ 3.6` bar or an explicit user ruling.**
3. **Every repair is reversible and forensic.** Follow the `deactivate_dead_stocks.py`
   precedent: write the before-state to a forensic table in the same statement snapshot,
   and put the reversal SQL in the docstring.
4. **Fix the owner, not just the value.** Each of the three failures below happened
   because a piece of state had no scheduled owner and no startup guard. Restoring the
   value without assigning the owner guarantees a repeat.
5. **The frozen engine is not touched.** Nothing here edits `app/analysis/`,
   `app/backtest/engine.py` or `docs/SIGNAL_ENGINE.md`. A universe change alters which
   panels are scored; it does not alter the scorer.
6. **Back up before the first write.** `make backup` exists (RUNBOOK §9) and this is
   exactly the scenario it was built for.

## §7 · The queue

Conventions follow `docs/BUILD_QUEUE.md`: **WHY · SCOPE · FILES · ACCEPTANCE · DO NOT**.
Ordering is dependency-driven; U1 gates U2, U2 gates U3.

---

### U0 — Doc correction: the ledger migration IS applied *(5 min)*
- **WHY** W1: `CLAUDE.md` + `MEMORY.md` claim `e1f2a3b4c5d6` is unapplied; the DB says
  otherwise. A doc that disagrees with reality has already cost this project real time.
- **SCOPE** Delete the two warnings; note the measured `alembic_version`.
- **ACCEPTANCE** No file claims the ledger migration is pending.
- **DO NOT** Run any migration — nothing is pending.

---

### U1 — Repopulate `kite_instruments` and give it an owner *(P0)* ✅ **DONE 2026-09-13 — see §29**
- **WHY** It is empty; the live path joins through it; four subsystems are dark. It is
  also the *input* to `deactivate_dead_stocks.py`, so nothing else may run first.
- **SCOPE**
  1. Run the existing sync once (`POST /broker/kite/instruments/sync`, admin — or a
     thin script wrapping `kite_client.sync_instruments`). A valid Kite token is
     present (`broker_tokens` id 3, active, expires 06:00 IST).
  2. ⭐ **Add a Celery beat task** that syncs instruments once per trading morning,
     before the live worker starts. Today `sync_instruments` has exactly one caller —
     `app/api/v1/broker.py:118`, an admin HTTP endpoint. **Nothing scheduled has ever
     owned this table.** That is why it stayed empty for five days.
  3. ⭐ **Add a startup guard to `live_worker`:** refuse to start (non-zero exit, loud
     log) when the subscription universe is 0, instead of logging `up: 0 instruments`
     and running dark for a full session. Same for an implausible collapse (e.g. < 50 %
     of the previous session's count) — mirror the `_SWEEP_MIN_FRACTION` tripwire that
     already protects the sweep.
- **FILES** `app/broker/kite_client.py` · `app/tasks/` (new beat entry) ·
  `app/broker/live_worker.py` · `.env.example` if a knob is added (W3).
- **ACCEPTANCE** `kite_instruments` > 50,000 rows; `live-worker up: N instruments` with
  N > 1,000; a test that the guard exits non-zero on an empty universe.
- **DO NOT** Run `deactivate_dead_stocks.py` until this completes and is verified.

---

### U2 — Repair `is_active` from a declared, three-source truth *(P0, gated on U1)*
- **WHY** §3. 1,119 listed, tradeable NSE names are wrongly inactive.
- **SCOPE** A new, idempotent, forensic, dry-run-first script
  (`scripts/repair_stock_universe.py`) that computes the active set as the **agreement
  of three independent sources**, rather than trusting any one:
  1. `EQUITY_L.csv` — present, with `SERIES` recorded (2,292 `EQ`; 249 `BE`; 27 `BZ`);
  2. `kite_instruments` — a plain (non-suffixed) `EQ`-type NSE listing exists;
  3. `ohlcv_1d` — the name traded in the last N sessions.
  Activate on agreement; report every disagreement rather than silently resolving it.
  ⚠ **`BE`/`BZ`/`SM` series stay inactive for live scanning** — that is the existing
  T2T ruling (2026-07-17), not a new decision; they keep receiving EOD bars.
- **Measured effect (today's data):** of 2,289 `EQ` symbols present in `stocks`,
  **1,170 are already active and 1,119 flip to active.** 951 currently-inactive names
  are *correctly* inactive (absent from today's `EQUITY_L.csv` — delisted, renamed, or
  series-moved) and must stay that way: that is the survivorship-safe history.
  ⚠ 152 currently-active names are **not** in the `EQ` list and need review — likely
  `BE`/`SM` series that the reseed activated by the §3 mechanism running in reverse.
- **ACCEPTANCE** `is_nifty50 AND is_active` = 50 · `is_banknifty AND is_active` = 14
  · `RELIANCE`/`TCS`/`HDFCBANK` active · a `forensic_stocks_universe_repair` table
  holding every flip with its reason · reversal SQL in the docstring · dry-run output
  reviewed by the user **before** the write.
- **DO NOT** Apply any liquidity, price or market-cap filter here (§9). Do not touch
  the 951 genuinely-delisted names.

---

### U3 — Backfill the 09-05 → today coverage hole *(P0, ~~gated on U2~~)* ✅ **DONE 2026-09-13 — see §28**
- **WHY** **1,481 names** had a bar on 2026-09-04 and none on 2026-09-11 — each is missing every session since. Left alone this is a permanent
  discontinuity inside the 300-bar window of every blue chip — the same class of defect
  as the 922-day 2020-12→2023-07 hole that invalidated 33 % of a study's panels.
- **SCOPE** Re-run bhavcopy ingestion for 2026-09-05 → today in `historical` mode
  (which bypasses the `is_active` filter) so every repaired name is filled. Idempotent
  (`ON CONFLICT DO NOTHING`).
- **ACCEPTANCE** Every session 09-05 → today shows ≥ 2,500 names; a span-vs-calendar
  gap check (the B4 guard) reports no per-name hole for the active set.
- **DO NOT** ~~Re-run before U2, or the hole is simply refilled at the wrong breadth.~~
  ⛔ **THIS DO-NOT WAS WRONG AND IS NOW DISPROVEN BY EXECUTION (§28).** §23.3 predicted it
  from `bhavcopy_service.py:255`; the run confirmed it — breadth was fully restored with
  `is_active` untouched (1,322 before and after). U3 never depended on U2.

---

### U4 — Make the feed alarm coverage-aware *(P1)*
- **WHY** §4a. The alarm reported ✅ throughout. Recency is not health.
- **SCOPE** Extend the 6.8.6 EOD staleness header to assert **breadth**: names with a
  bar today vs the trailing 5-session median, with an explicit threshold. Alarm on a
  material drop even when `max(time)` is current.
- **ACCEPTANCE** A regression test that replays the 09-04 → 09-07 breadth collapse and
  asserts the alarm fires. ⭐ Per `instrument_self_validation`, the test must first
  reproduce the *silence* against the old code.

---

### U5 — Write down the recovery order, and test the invariant *(P1)*
- **WHY** The composition in §3 is invisible in both files. The next disaster recovery
  will reproduce it exactly.
- **SCOPE** (a) `RUNBOOK.md`: a disaster-recovery section stating the mandatory order —
  `seed_stocks.py` → `kite_instruments` sync → bhavcopy backfill → universe repair →
  index backfill. (b) A test pinning `_ensure_historical_stocks`'s stated invariant:
  seeding an active row first, then ingesting, must leave it active. (c) Consider
  having `_ensure_historical_stocks` **refuse to run** against an empty `stocks` table —
  on an empty master every symbol looks delisted, which is never true.
- **ACCEPTANCE** A failing-then-passing test; a runbook section a stranger can follow.

---

### U6 — ⭐ Split the two meanings of `is_active` *(P1 — the one schema change)*
- **WHY** One boolean currently gates **both** "ingest daily bars for this name"
  (`bhavcopy_service.py:255`) and "scan/score/trade this name"
  (`signal_service.py:318`). That coupling is why a *selection* mistake silently
  destroyed five sessions of *price history* for the most important names we hold.
  Decoupled, the same mistake would have cost nothing but a quiet scanner.
- **SCOPE** Add `is_listed` (data-ingestion eligibility, wide, permissive) alongside
  `is_active` (tradeable-today, narrow); migrate ingestion to `is_listed`; leave
  selection on `is_active`. Reversible migration; backfill `is_listed = true` for every
  name present in any recent bhavcopy.
- **ACCEPTANCE** Ingestion breadth is independent of the tradeable flag, pinned by
  test: flipping every `is_active` to false must not reduce bar ingestion.
- **DO NOT** Bundle this with U2. Repair first, restructure second.
- ⚠ **Reviewers: this is the one item I am least sure about.** It is the correct
  architecture, but it adds a column and a concept to a system that is mid-flight
  toward cycle 2. The alternative — keep one flag, rely on U4's alarm — is cheaper and
  weaker. §13 Q4.

---

### U7 — Sector / industry mapping *(P2)*
- **WHY** 500 of 3,392 names carry a sector; the sector-RS overlay and the screener's
  sector filter both need it. Coverage from the current source is capped at the ~500
  names in `ind_nifty500list.csv`.
- **SCOPE** Declare the source of record and its refresh cadence. `ind_nifty500list.csv`
  is live and carries `Industry` for 501 names. Widening beyond that needs either the
  per-sector index constituent CSVs (free, ~15 files) or a different source — an open
  question (§13 Q2, §14 A7). Record the source and as-of date on the row; do not invent a
  sector for a name we cannot classify (`NULL` beats a plausible guess — UI rule A24).
- **DO NOT** Use a sector map as a gate. It is a *modifier/context* input per the MCE
  principle, never an additive confluence factor.

---

### U8 — ⭐ The index registry and sector-index OHLC *(P2 — the best cost/benefit item here)*
- **WHY** `indices` holds 3 rows; `index_ohlcv_1d` holds 54. Every market-regime and
  sector-RS overlay is unevaluable. `benchmark.py` can only ever return NIFTY50.
- **SCOPE** ⭐ **Verified live on 2026-09-12: the NSE daily indices CSV that
  `vix_service` already downloads carries 165 indices in one free, no-auth file**, with
  columns `Open / High / Low / Closing Index Value / Volume / Turnover (Rs. Cr.) / P/E
  / P/B / Div Yield`. It includes every sector index we would want —
  `Nifty Auto`, `Bank`, `Energy`, `Financial Services`, `FMCG`, `IT`, `Media`, `Metal`,
  `Pharma`, `PSU Bank`, `Private Bank`, `Realty`, `Healthcare`, `Oil & Gas`,
  `Consumer Durables`, `Commodities`, `Infrastructure`, `Services Sector` — plus the
  size ladder (`Next 50`, `100`, `200`, `500`, `Midcap 150`, `Smallcap 250`,
  `Microcap 250`, `Total Market`).
  ⇒ **Sector-index history costs one extra parse of a file we already fetch daily.**
  1. Register the sector + size indices in `indices`.
  2. Widen the ingester to store all registered indices, not just the three.
  3. Run `scripts/backfill_indices.py 2023-07-03 <today>` to seed ~200-DMA and §8 depth,
     rebuilding `india_vix_daily` in the same pass (same CSV, one download per session).
  4. Extend `benchmark.py`'s benchmark picker from the three membership flags to the
     sector map from U7.
- **ACCEPTANCE** `index_ohlcv_1d` ≥ 500 sessions for NIFTY 50; ≥ 200 sessions for each
  registered sector index; `india_vix_daily` ≥ 500 sessions; `market_regime` and
  `sector_rs` return a real verdict instead of failing open.
- **DO NOT** Flip either overlay from shadow to active on the strength of newly
  available data (§9). Data availability is not evidence.

---

### U9 — Index constituents and membership flags *(P2)*
- **WHY** 89 rows, all `weight_pct` NULL, all `added_on` = the reseed date — so the
  table cannot answer "was this a Nifty 50 name on date X", which is what a
  point-in-time backtest needs (the same lesson as A38's mandatory `as_of`).
- **SCOPE** Reseed from the index constituent CSVs; record `added_on` honestly as
  "first observed", not as a fabricated join date; leave `weight_pct` NULL unless a free
  source provides it. Document that pre-2026-09-07 membership history does not exist.
- **DO NOT** Backfill a membership history we cannot source. A fabricated `added_on` is
  worse than a missing one.

---

### U10 — Restore the operational surfaces *(P3)*
- **SCOPE** `strategy_profiles` (0 rows — decide whether these are user-created or want
  a seed script) · a default watchlist · confirm `make worker` is running (the A40 alarm
  is firing now) · re-start CAS accrual, remembering it is real-time-only and cannot be
  back-filled.
- ⚠ **CAS:** every day the worker is down across 15:15–15:33 IST is a session lost
  permanently. If CAS matters, this is the most time-sensitive item in the document —
  it should arguably jump the queue above everything except U1.

---

# PART III — THE CURATION DECISION (not decided here)

## §8 · What should the tradeable universe actually be?

Restoration (U2) returns ~2,290 `EQ` names to active. The user's ask was explicitly to
"plan as new and carefully curate it", so the real question is whether the scanned
universe should be narrower — and if so, on what authority.

**Measured candidate sizes** (dev DB, 2026-09-12; liquidity = median daily traded value
`close × volume` over the trailing ~120 days):

| Candidate universe | Names | Note |
|---|--:|---|
| Everything in `stocks` | 3,392 | includes delisted history — never scan this |
| `EQUITY_L` `EQ` series | 2,292 | the structural answer |
| …present in `stocks` | 2,289 | |
| …with ≥ 300 daily bars (engine window) | **1,801** | structural: below this the engine cannot score |
| …with 200–299 bars | 123 | |
| …with < 200 bars | 365 | |
| ≥ ₹1 cr/day median turnover | 1,470 | **empirical** |
| ≥ ₹5 cr/day | 1,044 | **empirical** |
| ≥ ₹10 cr/day | 819 | **empirical** |
| ≥ ₹50 cr/day | 342 | **empirical** |

⚠ The liquidity tiers are computed over a window in which the wrongly-inactive names
stop at 09-04, so they are slightly stale for those names. Re-measure after U3.

**My recommendation, and I want it attacked:**

> Define the scanned universe **structurally** as: `EQUITY_L` series `EQ` **AND** a
> plain `EQ` listing in `kite_instruments` **AND** ≥ 300 daily bars — ≈ **1,800 names**
> — and apply **no liquidity, price or market-cap floor at the universe layer**.

Two reasons, both from this project's own measurements rather than from principle:

1. **A liquidity floor here is the same instrument as MCE slice 5a, which was measured
   and rejected.** The liquidity gate was built, measured, and the 2026-08-21 deep-dive
   found the illiquid set **net-positive** and the liquid set **net-negative**, robust
   across floors, median and win-rate. The user's ruling was explicit: *keep 5a shadow;
   reframe liquidity later as a position-sizing / slippage MODIFIER, not an entry P&L
   gate.* Moving that same floor upstream to the universe layer would implement the
   rejected decision by another route. ⭐ **If a reviewer recommends a liquidity floor,
   they are asking to overturn a measured, user-ruled decision and should address that
   evidence directly.**
2. **Cost is already priced, not gated.** The A37 participation model charges
   `k × participation²` bps against median daily traded value on both fill paths and
   every mark surface, and A29 levies the flat ₹15.34 DP charge. An illiquid name is
   therefore *expensive*, not *invisible* — which is the correct treatment, and it is
   already shipped.

**The honest counter-argument, which reviewers should weigh:** at ₹1 lakh with 1–2
positions, the flat DP charge makes small tickets structurally expensive (61.6 bps
round-trip on 100 × ₹39 vs 22.4 bps on 400 × ₹2,500), and the project has already
identified the unresolved tension: *cost economics pushes toward concentration while
statistical validation pushes toward breadth, and you cannot have both at this capital.*
A narrower universe is one way to resolve it. I do not think the universe layer is where
that belongs — sizing is — but this is a genuine trade-off, not a settled question.

## §9 · ⛔ Traps this project has already paid for

Reviewers unfamiliar with the history will likely propose several of these. Each has
been tried here and has a recorded outcome:

1. **"Restrict to liquid names."** Measured; illiquid set net-positive. §8.
2. **"Add a market-cap floor."** MCE slice 5b — **dropped** after F1 (2026-09-07) found
   no size signal in the book.
3. **"Filter on confidence / rank by score."** E2 (2026-09-12): unconditional IC at
   h=5d = **−0.0070, 90 % CI [−0.0259, +0.0119]** against a measured break-even of
   0.0310 ⇒ the scorer carries no cross-sectional information; `confidence_pct` is
   flatter still. ⭐ **The ranker is dead.** A universe change cannot be justified by
   "we will pick better within it".
4. **"Turn on the market-regime / sector-RS overlay once the index data is back."**
   The regime gate was promoted on 44 observations and refuted by 88 (it subtracted
   ~8R). The R:R ≥ 1 floor was promoted on an identity argument and refuted within a
   week (it blocked the book's only profitable cohort). **U8 restores the data; it does
   not license a flip.**
5. **"Just widen the universe to everything."** That is how a ₹39 micro-cap × 2,666 qty
   entered on a single indicator. The structural floors in §8 (listed, deliverable
   series, ≥ 300 bars) exist to prevent scoring names the engine cannot evaluate — they
   are not a bet on returns.
6. **"Backfill more history to get more observations."** Measured and dropped: the
   binding lever is **turnover/hold period**, not sample span, and `ohlcv_1d` has a
   922-day hole (2020-12-23 → 2023-07-03) that makes pre-2023 panels unusable anyway.

## §10 · Risk register for the execution

| Risk | Mitigation |
|---|---|
| ⛔ A repair script writes to the live dev DB | `make backup` first (RUNBOOK §9). Dry-run output reviewed before any write. Forensic table + reversal SQL. |
| ⛔ Running `deactivate_dead_stocks.py` before U1 | It would deactivate the entire master. Explicitly blocked in U1's DO NOT. |
| ⛔ Passing `DATABASE_URL` to pytest | The 2026-09-07 cause. `conftest.py` now refuses any DB not named `*_test`; only `JWT_SECRET_KEY` is ever passed inline. |
| Universe change silently alters recorded numbers | Cycle 1's clock is informational, and `positions` is empty, so nothing is restated. **But the governing rule stands: anything that changes a recorded number lands before cycle 2's clock starts.** A universe definition unambiguously qualifies. |
| Kite token expiry mid-repair | Token expires ~06:00 IST daily; U1 needs a fresh one. |
| `pnpm`/venv loss from a snap refresh | Known machine quirk; unrelated but has bitten three times. |

---

# PART IV — THE REVIEW PROTOCOL

This is a **two-way, multi-round exercise**, not a request for a verdict. Reviewers are
expected to ask us questions; we will answer them with measurements. Sections §13–§18
exist to make that loop cheap.

## §11 · What this plan deliberately does NOT do

- It does not touch the frozen engine, `SIGNAL_ENGINE.md`, or any scorer.
- It does not flip any gate from shadow to active.
- It does not restate any historical P&L (`positions` is empty; nothing to restate).
- It does not start cycle 2 or reset any paper clock.
- It does not attempt to recover the destroyed book, CAS history, or signal outcomes.
  Those are gone; the plan is forward-only.

## §12 · ⭐⭐ THE WINDOW — what "no positions, no holdings" licenses right now

This is the most important context a reviewer can have, and it is easy to miss.

```
positions = 0   orders = 0   watchlist_items = 0   signal_outcomes = 0
cycle-1 paper clock = INFORMATIONAL   cycle-2 clock = NOT STARTED
```

The project's governing constraint is: **anything that changes a recorded number must
land BEFORE cycle 2's clock starts** — a rule earned by having to reset one clock already
(the 2026-08-17 spread-aware-fill change made paper P&L non-comparable across that date).

⭐ **Right now there are no recorded numbers to protect.** The book is empty. That makes
this the cheapest moment in the project's life to make structural changes, and the window
closes the day cycle 2 begins. Concretely, all of the following are **free today and
expensive later**:

- redefining the tradeable universe (nothing to restate);
- the `is_active` / `is_listed` split (U6) and any other schema change to `stocks`;
- changing the fill, cost, slippage or mark model;
- rebuilding the index registry and re-basing every benchmark;
- restarting intraday and CAS capture on a new schema.

⚠ **But the window licenses STRUCTURE, not SELECTION — and the distinction is the whole
discipline of this project.** "We have no positions, so we can try it" is a correct
argument about *cost*. It is not an argument about *evidence*, and the two have been
conflated here before, expensively:

| Free today | Still needs evidence |
|---|---|
| Changing **what the system is** — schema, universe definition, data model, cost model, which names we ingest | Changing **what the system believes** — flipping a shadow gate active, adding a selection filter, promoting a ranker |
| Justified by: correctness, reproducibility, maintainability | Justified by: the `t ≈ 3.6` deflated-Sharpe bar, or an explicit user ruling recorded with its reasoning |

Both gates this project promoted were promoted on arguments and refuted by data within
weeks — the regime gate (promoted on 44 observations, refuted by 88, cost ~8R) and the
R:R ≥ 1 floor (promoted on an identity argument, refuted in a week; it had been blocking
the book's only profitable cohort). **An empty book removes the cost of being wrong about
structure. It does not remove the cost of being wrong about edge** — it just defers the
bill to cycle 2, which is the one measurement that is supposed to be trustworthy.

⇒ **Reviewers: propose structural changes freely and aggressively. Propose selection
changes only with the evidence that would settle them, or explicitly as PARKED items
(§16) with their unblocking condition stated.**

## §13 · Decision questions — the six that block this plan

Answer these specifically; each one gates an item in §7.

1. **Q1 — Structural vs empirical.** Is the §6/2 split the right frame? Specifically: is
   "≥ 300 daily bars" structural (the engine's window canon cannot produce a score
   without it) or a disguised survivorship/liquidity filter?
2. **Q2 — Sector coverage.** The free `ind_nifty500list.csv` caps sector coverage at ~500
   of ~2,290 names. Is a ~22 %-covered sector map worth shipping, or does a partial map do
   more harm than none (a sector-RS overlay that silently fails open for 78 % of the
   universe)? What free source would do better?
3. **Q3 — Universe size.** Given §8's table and §9's history, what do you recommend, and
   **what evidence would change your mind**? Answers of the form "top N by liquidity" must
   engage with §9/1.
4. **Q4 — `is_active` split (U6).** Correct architecture, or unnecessary complexity
   mid-flight? Is there a cheaper way to guarantee that a selection error can never again
   stop data ingestion?
5. **Q5 — Ordering.** CAS restart sits at P3 (U10) but is the only item losing data
   permanently every day it waits. Should it jump to P0 alongside U1?
6. **Q6 — What is missing?** The failure mode of this document is an unlisted consumer of
   the stock master that stays broken after U1–U3. §4 lists seven; what is the eighth?

## §14 · ⭐ Architecture questions — building this as a STANDARD system

§13 gets the current fire out. **These are the questions we actually want help with**,
because they decide whether we rebuild the same fragile thing or something durable. We
have no institutional background here; assume we do not know the standard answer.

### A1 — Security identity
We key on `(symbol, exchange)` with a surrogate `stocks.id` that turned out **not to be
stable**: every id was reassigned on 2026-09-07, silently invalidating any artifact that
recorded a raw `stock_id`. Symbols rename, series move (`EQ` → `BE` → `T2T` → `EQ`),
companies merge. `isin` exists, is nullable, has a unique constraint, and already has a
known collision path (`seed_stocks.py` writes `NULL` rather than die on `uq_stocks_isin`).
> **What is the standard identity model for an equity security master?** Permanent
> surrogate ID + an effective-dated symbol/listing history table? Is ISIN the right
> natural key given that it also changes on some schemes of arrangement? **And what is the
> minimum viable version at our scale** (§A8)?

### A2 — Point-in-time / bitemporal universe
The project already made `as_of` mandatory on every trading restriction (A38) so a
backtest can ask *"was this restricted on that date"*. **The universe has the identical
problem and no answer.** `index_constituents.added_on` is uniformly the reseed date and
`weight_pct` is NULL, so *"was X in the Nifty 50 on date D"* is unanswerable. We also just
shipped an append-only ledger (`ledger_entries`, migration `e1f2a3b4c5d6`).
> **Effective-dated rows (`valid_from`/`valid_to`), a daily snapshot table, or an event
> log the universe is folded from?** Which is standard, which is right for a single-box
> Postgres 16 + TimescaleDB holding ~2,300 names × ~1,100 sessions, and **should the
> universe ride the ledger we already have** rather than getting its own mechanism (W2:
> do not add a parallel implementation)?

### A3 — Corporate actions
`corporate_actions` = **0 rows**. `ohlcv_1d` is CA-unadjusted end to end. Measured cost:
**49 unadjusted corporate actions sit in the top-250-liquid universe, 35 of them ≥ 40 %
halvings** (SHRIRAMFIN −81.1 %, ANGELONE −90.1 %, DIACABS +3118.6 %), and dropping just
**4 contaminated trades removed ~+49R of fake profit** from one study — more than that
study's entire original loss. We do have a working ratio-adjuster for *open positions*
(6.8.5, admin-verified ratio), so a detector exists; the **history** does not.
> **Standard architecture: store raw prices + a cumulative adjustment-factor series and
> adjust at read time, or store adjusted with raw kept for audit?** And **is there a free,
> reliable Indian CA source** (NSE corporate-announcements API, BSE, or bhavcopy-derived
> detection of unexplained overnight gaps)? We have no vendor budget.

### A4 — Ingestion invariants
Our staleness alarm asserted **recency** and missed a **56 % breadth collapse** for five
days (§4a).
> **What is the standard invariant set for an EOD reference + price ingestion?** We are
> looking for the minimum set that would have caught *this* failure and the next one —
> candidates: expected row count vs a trailing baseline, per-name presence vs a
> subscription list, price/volume sanity bounds, cross-source reconciliation, monotonic
> session count. Which of these earn their keep at our scale, and which are institutional
> habit?

### A5 — Universe as data or as rule
Today the universe is a mutable boolean on `stocks`, which is why one wrong flag was
invisible.
> **Should the tradeable universe be (a) a flag, (b) a declarative rule evaluated nightly
> whose OUTPUT is snapshotted and immutable, or (c) a hand-curated list?** Reproducibility
> argues for (b). What is actually standard?

### A6 — Multi-source reconciliation
Three sources disagree today: NSE `EQUITY_L.csv` (2,568 rows), the Kite instruments dump,
and the daily bhavcopy. U2 proposes activating on three-way agreement.
> **What is the standard disagreement policy** — intersection (safe, silently loses
> names), union (unsafe), or source-precedence with an exception queue a human clears?
> **Should a disagreement block the pipeline or merely alarm?** Note we are a solo
> operator: an exception queue nobody clears is worse than no exception queue.

### A7 — Sector taxonomy
Our sector map comes from index-membership CSVs, which is **circular**: a name gets a
sector only if it is already in the Nifty 500. That caps coverage at ~22 % and biases it
toward large caps — the opposite of where a sector overlay would be most useful.
> **What free taxonomy covers the full NSE universe?** And a specific idea we would like
> judged rather than assumed: **should sector be derived from return-correlation
> clustering on our own 1,098 sessions of price history** instead of from a published
> taxonomy? That needs no vendor, covers 100 % of names with enough bars, and is arguably
> closer to what a relative-strength overlay actually wants — but it is also a fitted
> object that could overfit, and we would want to hear why it is or is not standard.

### A8 — ⭐ Calibrate to our scale, and tell us what to cut
We are **one person**, personal use first, **₹1 lakh of live capital**, 1–2 concurrent
positions, one dev box (Postgres on :5433, Redis, RAYON ≤ 6 threads), evenings only. The
project's expensive failures have never been infrastructure — they were **unvalidated
claims**. There is a real risk that "standard system" advice imports institutional
machinery we will never need and cannot maintain.
> **What is the minimum professional-grade security master at this scale — and which of
> your own recommendations above would you cut** if told the whole thing must be
> maintainable by one person in evenings, forever?

### A9 — What would you do with the window?
Given §12 — empty book, no recorded numbers to protect, window closes at cycle 2:
> **What is the single highest-value STRUCTURAL change you would make before the window
> closes, that this document has not proposed?**

### A10 — Intraday capture (time-sensitive, like CAS)
`ohlcv_1m`, `ohlcv_5m`, `ohlcv_15m`, `ohlcv_1h` are **all 0 rows** since 2026-09-07.
Intraday data accrues **only in real time and cannot be back-filled** from any free
source, so every opening-range, intraday-timing and execution-microstructure question is
untestable until capture restarts — and each day of delay is permanent.
> **Should intraday capture restart now, before cycle 2?** At what granularity and
> retention for ~2,300 names on one box — and is storing 1-minute bars for the full
> universe sane, or should it be a subscribed subset?

## §15 · What YOU may ask US — and how

⭐ **Please ask.** Several of this project's worst review rounds happened because a
reviewer reasoned from an assumption that one query would have settled. Five separate
review points across previous rounds were refuted by a query the reviewer could have asked
for.

**We can answer, same round:**

| You can ask for | Because |
|---|---|
| Any read-only `SELECT` against the dev DB | 42 application tables, 2.08 M daily bars, 1,098 sessions |
| Any counted distribution, quantile, or cross-tab of the above | |
| The source of any function, model, migration or script | Whole repo available |
| A re-run of any existing probe with different parameters | `backend/scripts/` holds 60 scripts, most of them read-only probes |
| Excerpts of any doc, including the protected `SIGNAL_ENGINE.md` | Protected against *edits*, not reads |
| Exact settings values as a running process sees them | There is a recipe for this (`.env` is unreadable by the agent; a fresh `get_settings()` load is the check) |

**We cannot answer — do not build a recommendation on these:**

| Unavailable | Why |
|---|---|
| Any live-tape P&L, fill, or trade outcome | `positions` = `orders` = `signal_outcomes` = 0. **The entire cycle-1 book was destroyed 2026-09-07 with no backup.** Every live-tape number in our older review docs is currently unreproducible |
| Closing-auction (CAS) behaviour beyond 1 session | `cas_daily` = 86 rows; real-time-only, cannot be back-filled |
| Anything intraday | All intraday tables are empty (§A10) |
| Index or VIX history | `index_ohlcv_1d` = 54 rows, `india_vix_daily` = 18 (U8 fixes this) |
| Anything in `ohlcv_1d` for 2021 or 2022 | The 922-day hole (§5) — **0 sessions** in both years |
| Point-in-time index membership | §A2 — `added_on` is uniformly the reseed date |

**How to ask, so the round stays cheap:**

1. **Name the object.** "What is the distribution of X in table Y" beats "how liquid is
   the universe".
2. **Say whether the answer is BLOCKING.** If your recommendation is the same either way,
   mark it context — we will answer it, but it will not hold up the round.
3. **State your prediction before we run it.** This is an adopted convention here (probe
   convention 5): a published numeric prediction turns our run into a *test* instead of a
   *search*, and it has twice caught an error that a bare result would have hidden.
4. **One question, one estimand.** Compound questions have produced compound answers that
   were half-wrong here before.

## §16 · How we will dispose of your recommendations

Every point gets exactly one of three dispositions, recorded with a reason, following this
project's existing state machine:

```
PARKED ──(evidence it is worth capacity)──> BUILD ──(acceptance test)──> MEASURED ──> ACCEPTED
```

| Disposition | Means | Requires |
|---|---|---|
| **ADOPT** | Enters the §7 queue with an acceptance test | Converged across sources **OR** settled by our own measurement |
| **PARK** | Right, or plausibly right, but not justified to consume capacity **now** | A stated **unblocking condition** — the specific thing that would move it to ADOPT |
| **REJECT** | Contradicted by a measurement we hold | The measurement, cited |

⚠⚠ **"PARKED" NEVER MEANS "WRONG".** This is the user's explicit instruction for this
exercise and it is also existing project policy. A recommendation can be **correct and
still parked** because our system does not yet have the configuration, data, or capital to
support it. ⭐ **A parked item without an unblocking condition is a rejected item wearing a
polite label — so every parked row must state what would unblock it**, and we will raise it
unprompted when that condition is met (the project's review-calendar rule: Claude owns the
calendar and raises due items without being asked).

⭐ **The entry rule, which is the single most expensive lesson of the previous ten rounds:**

> **An item enters the build queue when it is converged across sources OR settled by our
> own measurement — never on consensus alone.**

Unanimous panel agreement has been wrong here repeatedly: all five reviewers once demanded
a factor-level IC study that had already been run and returned nothing; all five
recommended a cross-sectional ranker against a measured prior that it would not work — and
it did not (E2, 2026-09-12: IC = −0.0070, 90 % CI [−0.0259, +0.0119], a null). Meanwhile
**the best items each came from a single source.** ⇒ *Consensus is a good filter for
PRIORITY and a bad one for TRUTH.*

⛔ **Three things are FORBIDDEN rather than parked** — proposing them wastes a round:

1. **Editing the frozen engine.** `backend/app/analysis/`, `app/backtest/engine.py` and
   the swing/window canon are frozen; `docs/SIGNAL_ENGINE.md` is hook-protected. Changing
   a factor, a weight, or the ≥ 70 % gate is a **spec change** requiring explicit user
   instruction, a §8 backtest regression, **and** regenerated Rust oracle fixtures in the
   same commit. Measurements about the engine are findings to record, not licence to edit
   it.
2. **Flipping a shadow gate active without its evidence.** §9/4.
3. **Anything that writes to, truncates, or migrates live data without asking first.**
   The 2026-09-07 loss is why.

## §17 · Review round ledger

Each round appends a row. Keep it honest — including rounds that changed nothing, since
the marginal value of review breadth is itself something this project measures.

| Round | Date | Sources | Points | ADOPT | PARK | REJECT | Notes |
|---|---|---|---|--:|--:|--:|---|
| 0 | 2026-09-12 | Claude (in-repo) | — | — | — | — | This document. Measurement + plan only; nothing executed |
| 1 | 2026-09-12 | ChatGPT · Gemini · Perplexity · DeepSeek · Claude (5) | ~40 | 10 | 6 | 2 | **PART V.** ⭐ One finding (Claude F1) overturned §3's root cause and changed the remedy. **3 claims refuted by measurement**, incl. "no scheduled backup" (cron has run since 09-07) and E2 contamination. ⭐⭐ **Verifying the reviews produced 2 findings no reviewer had** (§20/1 the `load_frames` deadline, §20/2 the dangerous reversal SQL). Gemini added nothing not stated more precisely elsewhere |
| 2 | | | | | | | |

## §18 · The parked register

Live register: **§19d** (round 1 populated it — 6 items, each with its unblocking
condition). Round 0 was empty.

⭐ **The most instructive parked row is one of my own:** the correlation-derived sector
taxonomy I proposed in §A7 was independently objected to by two reviewers on a ground I
could not have tested from inside the system — co-movement clusters are regime artifacts,
not sectors. It is parked with a real instrument attached (a 60/40 session stability
split), which is what PARK is supposed to look like.

---

# PART V — ROUND 1 ADJUDICATION (2026-09-12)

Four reviews received: **ChatGPT**, **Gemini**, **Perplexity**, **DeepSeek**, and a
**Claude** review delivered as a separate 857-line document
(`~/Downloads/UNIVERSE_REBUILD_REVIEW_R1_CLAUDE.md`).

⭐ **Every claim below was adjudicated against the code and the database, not against our
own documents** — which is how two of the reviewers' strongest points were confirmed and
three were refuted.

## §19 · Dispositions

### 19a. ⭐⭐ CONFIRMED BY MEASUREMENT — the single most valuable finding of the round

**Claude F1 — "§3's stated ordering is contradicted by your own counts."** ✅ **CONFIRMED,
and the correction is now §3a.** The reviewer reached it by arithmetic on our published
rows (1,322 − 17 = 1,305 active-with-bars, impossible under sequential ordering). Verified
three ways: 1,303 active stocks hold pre-09-05 bars; the id-block structure separates
cleanly into `_ensure_historical_stocks` and `seed_stocks` regions; and the five active
Nifty 50 names are all post-2019 listings.

⇒ **`is_active` encodes which process created the row, not any property of the stock.**
⇒ **U5's "document the recovery order" is necessary but NOT sufficient** — see U6′.

⚠ **This is the round's lesson about the review process, not just the bug:** the finding
came from *one* reviewer, was derived from numbers we had already published, and needed no
information we had not given. It is the fifth time in this project's review history that a
single source beat the consensus. It also reinforces the probe convention that a reviewer
who *recomputes* outperforms one who only reads.

### 19b. ✅ CONVERGED ACROSS ALL FIVE — adopting

| Point | Sources | Disposition |
|---|---|---|
| **Universe = versioned rule + immutable snapshot**, not a mutable boolean | ChatGPT §6, Perplexity A5, DeepSeek A5, Claude, Gemini | **ADOPT** — and it is *also* settled by our own precedent: A38 already did exactly this for restrictions (declare once, walk the registry, mandatory `as_of`). Converged **and** self-settled, so it clears the entry rule on both counts. |
| **Permanent security identity + effective-dated symbol/listing history** | ChatGPT §4, DeepSeek A1, Perplexity A1, Claude A1 | **ADOPT** — §20/2 below is the concrete proof it is already costing us. |
| **Corporate actions are not P2** | ChatGPT §12, Claude F4, DeepSeek A3, Perplexity A3 | **ADOPT** — raw immutable + adjustment-factor series + a *detector and review queue*, never auto-adjustment. |
| **Coverage-aware ingestion alarm, elevated** | all five | **ADOPT at P0** (was U4/P1). |
| **CAS + intraday restart in capture-only mode** | ChatGPT §10, Perplexity P0-B, DeepSeek Q5, Claude A10 | **ADOPT at P0.** "Capture-only" (store and validate, do not signal or trade) is ChatGPT's framing and is better than my P3 placement. |
| **U2 must not use bhavcopy recency as an activation criterion** | ChatGPT §5, Claude F5, Perplexity A6, DeepSeek A6 | **ADOPT** — OHLCV presence is an *observation*, not an identity authority, and during this very repair it is circular (1,481 names have no bar since 09-04). Replace the three-way intersection with **source precedence** (EQUITY_L → Kite → bhavcopy) + a bounded, noisy disagreement report. |
| **No liquidity / market-cap / top-N floor at the universe layer** | all five | **ADOPT (unchanged)** — unanimous, and consistent with the measured 2026-08-21 finding. |
| **Do not touch the frozen engine; do not flip shadow gates** | all five | **ADOPT (unchanged)**. |
| **Intraday: tiered capture, not 1-minute for the whole universe** | ChatGPT §11, DeepSeek A10, Perplexity A10 | **ADOPT** — 1m for a declared subscribed subset, 5m/15m/1h derived, daily for everything. |

### 19c. ⛔ REFUTED BY MEASUREMENT — do not carry these into round 2

**DeepSeek R4 — "no scheduled backup exists, and `make backup` is not one."**
⛔ **REFUTED.** A cron job has been installed since 2026-09-07 and is running:

```
0 11 * * 1-5  /home/nithin/code/back_ups/trading_platform/bin/backup_db.sh
```
```
trading_platform-20260909-110001.dump   49,745,318 bytes
trading_platform-20260910-110001.dump   58,238,427 bytes
trading_platform-20260911-110001.dump   59,390,111 bytes
```

⚠ **But the review was half-right for reasons it did not state, and those reasons are
real.** (1) **Every existing backup post-dates the breakage**, so all three contain the
inverted universe — restoring one recovers nothing this plan is about. (2) **The dumps sit
on the same box as the database**, so they survive a bad `TRUNCATE` and not a disk
failure. (3) There is a `make backup-verify` target that performs a real restore; whether
it has been *run* since installation is a separate question and is now a queue item.
⇒ The valid residue is adopted as **U0.5′** (off-box copy + a dated restore drill), not as
"there is no backup".

**Claude F2 — "E2 may be contaminated by the regression."**
⛔ **LARGELY REFUTED, and checking it produced something more important.** `e2_score_ic.py`
draws its universe from `swing_dependence_probe.load_frames`, which reads `ohlcv_1d`
**directly and applies no `is_active` filter** — it ranks by median `close × volume` over
the last 180 days with `HAVING count(*) > 100`. Measured today, the frozen blue chips hold
**117 bars** in that window against a threshold of 100. They were in E2's universe. **E2
stands.** → But see §20/1, which is the reason the check was worth running.

**Claude — "new listings are permanently invisible right now."**
⛔ **REFUTED as stated.** `_ensure_historical_stocks` is invoked **only** under
`historical=True` (`bhavcopy_service.py:253`); daily ingestion never creates a stock row.
An unknown symbol on the daily path is counted in `skipped`, and the next `seed_stocks.py`
run INSERTs it **active**. The real hazard is narrower and is stated correctly in §3a:
it is triggered by historical backfills.

**DeepSeek Q2 — "were the 15 `forensic_stocks_deactivated` rows correct?"**
✅ **VERIFIED CORRECT.** `QUINTEGRA`, `VISASTEEL`, `JBCHEPHARM`, `GUJGASLTD` and
`NIFTYNXT50` are all **ABSENT from today's `EQUITY_L.csv`**. `deactivate_dead_stocks.py`'s
July judgements were sound; U2's "951 correctly inactive" figure is not undermined.

**DeepSeek Q1 — "are the 35 signals garbage?"** ✅ **PREDICTION CONFIRMED.** All 35 point
at currently-active stocks, zero orphans, and the sample is the microcap set —
`ALIVUS`, `PNGJL`, `VRAJ`, `BHAGCHEM`, `FABTECH`, `FRONTSP`, `INTLCONV`, `LLOYDSENT`,
`NIRLON`, `AYE`. **Quarantine them before cycle 2** (new queue item U11).

### 19d. ⏸ PARKED, each with its unblocking condition

| item | source | why parked | unblocking condition |
|---|---|---|---|
| Full layered 5-state security model (`security` / `security_listing` / `security_status` / `universe_snapshot` / `data_coverage`) | ChatGPT §4 | Right target, but it is a five-table rewrite competing with a P0 outage. DeepSeek's 4-table and Perplexity's 2-table variants are cheaper and cover the measured failures. | U6′ + U12 ship and a *measured* need appears that the smaller model cannot express |
| Correlation-derived sector taxonomy (my own A7 idea) | mine; ChatGPT §13 and Perplexity both argued against | ⭐ **Both reviewers independently made the same objection I could not have tested: co-movement clusters are regime artifacts, not sectors** (steel + PSU banks + IT can cluster in one regime). DeepSeek's 60/40 stability test is the right instrument. | clustering shows temporal stability on a 60/40 session split **AND** the sector-RS overlay demonstrates it needs coverage beyond the published map |
| Per-sector index constituent CSVs to widen sector coverage 22 % → ~40–50 % | DeepSeek A7 | Good, cheap, but strictly after the P0 outage | U1–U3 complete |
| Full bitemporal model everywhere | ChatGPT, Perplexity (who also cautioned against it) | Over-scope at one operator | a backtest requirement the effective-dated rows cannot serve |
| Separate DEV / TEST / PAPER / PROD databases with startup assertions | ChatGPT P0-A, Perplexity | The specific hole is already closed (`conftest.py` refuses any DB not named `*_test`) | a second near-miss, or live trading (Phase 7) |
| `ingestion_runs` lineage table | Perplexity A9, ChatGPT §15 | ⭐ Genuinely good and I under-weighted it; but it is a cross-cutting change touching every ingester | U1–U4 land; then it is the natural next structural item |

### 19e. ⛔ REJECTED

- **"Declare the ~1,800-name universe only after re-measuring" as a blocker** (ChatGPT §7).
  Half-adopted: re-measuring after U3 is correct and already in §8's caveat. But ChatGPT
  treats the universe size as undecided pending data — it is not. The *structural*
  definition does not depend on the liquidity distribution at all; only an *empirical*
  floor would, and we are not adopting one. Re-measure for the record, do not gate on it.
- **Gemini's review** contributed no point not made more precisely elsewhere, and its
  closing question ("which schema change do you prefer for U6") is answered by U6′ below.
  Recorded for the ledger; no disposition.

## §20 · ⭐ New findings — produced by verifying the reviews, not contained in them

**1. ⭐⭐ THE RESEARCH APPARATUS HAS A DEADLINE, AND IT IS ABOUT THREE WEEKS OUT.**
`load_frames` (the universe loader shared by `swing_dependence_probe.py`, `e2_score_ic.py`
and everything importing them) admits a name only if it has `> 100` bars in the trailing
180 days. The frozen blue chips are at **117 bars — a margin of 17 sessions** — and they
gain none while the window slides forward one session per trading day.

⇒ **On or about 2026-10-06, `RELIANCE`, `TCS`, `HDFCBANK`, `INFY` and `ITC` drop silently
out of every probe built on `load_frames`**, and any study run after that date measures a
microcap universe while appearing to measure the market. Nothing would alarm.

⚠ This converts U2/U3 from "important" into **time-boxed**, and it is a second irreversible
clock alongside CAS and intraday. It was not found by any reviewer; it was found by
checking whether one reviewer's contamination worry was true.

**2. ⭐⭐ A DOCUMENTED REVERSAL PROCEDURE IN THE REPO IS NOW ACTIVELY DANGEROUS.**
`deactivate_dead_stocks.py`'s docstring ships reversal SQL that joins
`forensic_stocks_deactivated` on `stock_id`. **Every one of its 15 stock_ids now resolves
to a different company:**

| `stock_id` | symbol in July 2026 | symbol today |
|--:|---|---|
| 228 | `QUINTEGRA` | `BSE` |
| 544 | `UNIVAFOODS` | `HERCULES` |
| 719 | `NIFTYNXT50` | `JSLHISAR` |
| 853 | `AVAILFC` | `MANAPPURAM` |
| 1,213 | `JBCHEPHARM` | `SCHNEIDER` |
| 1,274 | `MIRCELECTR` | `SKIPPER` |

Running the documented reversal today would reactivate **the wrong companies**. ⭐ This is
the concrete, in-repo cost of unstable `stocks.id` that §5 flagged abstractly — and it is
the strongest argument for the identity work in §19b, stronger than any argument a
reviewer made for it. **Fix the docstring in the same change (W1).**

**3. ⭐ THE ACTIVE SET IS WRONG BY INCLUSION, NOT ONLY BY OMISSION.** `QUINTEGRA` is
`is_active = true` today despite being absent from `EQUITY_L.csv` and having been
*correctly* deactivated in July 2026. The plan so far has framed the damage as "1,119
names wrongly inactive". It is bidirectional, and U2's acceptance test must assert both
directions.

**4. The 35 live signals are artifacts of the broken universe** (§19c) — quarantine, new
item U11.

**5. `_ensure_historical_stocks` runs only under `historical=True`** — narrows the hazard
and kills one reviewer claim (§3a, §19c).

**6. Backups run, but all three post-date the breakage and live on the same box** (§19c).

## §21 · The revised queue

Changes from §7 in bold. Two irreversible clocks (CAS/intraday, and now `load_frames`
at ~2026-10-06) drive the ordering.

| # | item | pri | change |
|---|---|--:|---|
| U0 | doc corrections — ledger migration, **plus §3a and the `deactivate_dead_stocks.py` reversal docstring (§20/2)** | P0 | **widened** |
| **U0.5′** | **off-box backup copy + a dated restore drill** | **P0** | **NEW** (DeepSeek's valid residue) |
| U1 | `kite_instruments` + scheduled owner + startup guard | P0 | unchanged |
| **U10a′** | **restart worker → CAS + tiered intraday, CAPTURE-ONLY** | **P0** | **promoted from P3** |
| U2′ | universe repair by **source precedence, not three-way intersection**; acceptance asserts **both** directions (§20/3) | P0 | **modified** |
| U3 | backfill 09-05 → today | P0 | unchanged |
| U4′ | coverage-aware feed alarm | **P0** | **elevated** |
| **U6′** | **remove the trading flag from the ingestion path** — the price archive must never consult a trading decision. Cheaper than the `is_listed` column and closes the whole class | **P1** | **replaces U6** |
| U5′ | recovery-order runbook + invariant test + `_ensure_historical_stocks` refuses an empty `stocks` | P1 | **necessary, no longer sufficient** |
| **U11** | **quarantine the 35 microcap signals** | P1 | **NEW** |
| **U12** | **permanent `stocks.id` + `symbol_history`; migrate the forensic reversal path** | P1 | **NEW** |
| **U13** | **universe as versioned rule + immutable snapshot** | P1 | **NEW** |
| **U14** | **corporate-action detector + quarantine queue; raw immutable + factor series** | P1 | **NEW** (was implicit in A3) |
| U7/U8/U9 | sector map · index registry · constituents | P2 | unchanged |
| U10b | remaining operational surfaces | P3 | unchanged |

⚠ **Still not decided, and still the user's call:** whether U12/U13/U14 are done *inside*
the window (they change no recorded number, so they are cheap now and dear later) or
deferred so the P0 outage closes first. My recommendation: **U0–U4 first without
exception**, then U12–U14 before cycle 2, because all three get strictly more expensive
once a clock is running.

## §22 · Questions for round 2

The apparatus questions are largely answered. These are what remain open.

1. **[BLOCKING] U6′ vs U6.** Removing `active_only` from the daily path means the archive
   ingests every bhavcopy name, including `BE`/`BZ`/`SM` series that the T2T ruling
   excludes from live coverage. The storage cost is small (the round-1 review estimated
   ~65 MB/year; ~1,100 extra names × ~250 sessions puts it in the same order, and it has
   not been measured here), but it **contradicts the stated rationale of the T2T ruling** ("deactivated names get no EOD bars"). Is the ruling
   about *trading* or about *storage*? If trading only, U6′ is strictly correct and
   cheaper than a new column. If storage too, U6′ needs the user to overturn a prior
   ruling. **This is the one place a reviewer's recommendation collides with an existing
   decision, and I will not resolve it silently.**
2. **[BLOCKING] The `load_frames` clock (§20/1).** Is ~2026-10-06 a hard deadline that
   should reorder everything, or should `load_frames`'s `> 100` threshold simply be made
   coverage-aware so the clock stops mattering? The second is a one-line change to a
   research probe — but it is a change to a *measurement instrument*, and this project has
   a rule about those.
3. **[context] Universe snapshot granularity (U13).** Daily snapshot of ~1,800 rows ≈
   450 k rows/year. Acceptable, or should the snapshot be written only on change?
4. **[context] Given §20/2, should `stocks.id` stability be enforced by *never deleting
   rows* plus `symbol_history`, or by adding a separate immutable `security_id`?** DeepSeek
   and ChatGPT differ here; both work; the cheap one wins unless someone names a case it
   cannot express.
5. **What did this round miss?** Round 0 asked for the eighth broken consumer. Round 1
   produced §20/1 and §20/2, neither of which was on anyone's list — **including mine.**
   The pattern is that the findings come from *running a check*, not from reading. So:
   **name the check, not the concern.**

---

## Appendix A — Reproducing every number here

All measurements are read-only `SELECT`s against `trading_platform` on 2026-09-12, plus
three live HTTP fetches of public NSE CSVs (`EQUITY_L.csv`, `ind_nifty500list.csv`, and
the daily indices CSV via `app.services.vix_service.download_indices_csv`). No script in
this document has been run against the database in write mode.

⚠ Per this project's convention, what is **[ASSUMED]** rather than measured: the liquidity
tiers in §8 use a trailing-120-day window that ends 2026-09-04 for the wrongly-inactive
names, so they understate those names' recent turnover. Everything else in PART I is a
direct count.

## Appendix B — Orientation for a reviewer new to this system

The five facts that make this project unusual, and without which several recommendations
will misfire:

1. **The signal engine is FROZEN and hook-protected.** It is the user's edge, adjudicated
   at a specific commit. It cannot be edited as part of this work.
2. **There is a quantified promotion bar: `t ≈ 3.6` on the trade series**, validated
   against a noise control (it rejects 1.1 % of best-of-20 zero-edge selections and has
   80 % power at a true per-trade Sharpe of 0.52). ⚠ **The hurdle is flat in n** — more
   data never lowers it — so "keep accruing until it passes" is only ever right when the
   point estimate is already ahead.
3. **The measured state of the strategy is honest and poor.** The scorer carries no
   cross-sectional information (E2: IC ≈ 0); gating as a programme is closed (eight
   shadow gates, two promotions, both refuted); exit geometry and the queued generation
   lever were both tested and refuted. **Finding a new source of edge is the open
   problem** — and it is not what this document is about. This document is about the data
   layer being correct enough that the question can be asked at all.
4. **Live trading does not exist.** `place_order` is paper-only. Everything here is
   upstream of an execution path that has not been built (Phase 7).
5. **The operator is one person.** Every recommendation is implicitly a maintenance
   commitment for a solo developer in evenings (§A8).

---

# PART VI — THE RESTORE-vs-REBUILD QUESTION (user, 2026-09-13)

⚠ **This part was written BEFORE the round-2 adjudication.** Three round-2 reviews
(ChatGPT, Gemini, DeepSeek) and one external Claude review (`UNIVERSE_REBUILD_REVIEW_R2`)
have arrived and are **not yet dispositioned** — that is separate work. This part exists
because the user raised a question that none of the ten reviews across two rounds asked,
and it is upstream of all of them.

## §23 · The question

> *"Why are we trying to retrieve the deleted stocks somehow? Why not rebuild this time
> more efficiently — a more future-scoped, more useful system — while we have the
> chance?"* — user, 2026-09-13

⭐ **This is the best question asked of this document so far, and the answer changes the
queue.** Every reviewer so far has argued about *how* to repair `is_active`. Nobody asked
whether repairing it is the right shape of work at all.

### 23.1 · ⛔ First, the premise needs correcting — nothing is being retrieved

There are **no deleted stocks to recover.** Measured 2026-09-13:

| | |
|---|--:|
| `stocks` rows surviving | **3,392** |
| `ohlcv_1d` bars surviving | **2.08 M** |
| `kite_instruments` rows | **0** |

The company records were never lost. What broke is **one boolean column** (`is_active`,
written by the wrong process) and **one empty reference table**. And U2 does not restore
that column from a backup — it re-derives it from the live NSE `EQUITY_L.csv`. ⭐ **We
are already rebuilding from source; the document merely describes it in restoration
language** ("repair `is_active` to mean what it always meant"), which is what makes it
read as recovery. The user's question was a fair reading of our own prose.

So the real question is not *restore vs rebuild*. It is: **do we rebuild into the same
shape, or a better one?**

### 23.2 · Where the plan IS still restoration-shaped, and should not be

U2 writes a repair script that flips a mutable boolean on ~1,000 rows, with a forensic
table and reversal SQL. That restores **the exact data model that produced the failure**:
a single mutable flag, writable by three processes, that simultaneously means

```
listed · tradeable · ingest bars for this · score this ·
subscribe to ticks for this · scan for corporate actions on this
```

Repairing its *value* correctly today does nothing to stop it being written incorrectly
tomorrow. §3a already established that `is_active` partly encodes **which process created
the row first** — that is not a property of a company, and no repair script can make it
one.

⭐⭐ **THE ONE CHANGE THAT MATTERS: collapse U2 into U13.** The plan already contains the
right thing — **U13, "universe as versioned rule + immutable snapshot"** — parked at P1
*behind* the repair. **They are the same work done twice.** Build U13 first and U2 ceases
to exist as an item: the repair becomes **the rule's first evaluation**. Consequences:

- no repair script;
- no forensic table;
- **no reversal SQL** — which matters, because §20/2 proved the documented reversal now
  reactivates the *wrong companies* (`stock_id` 228 was `QUINTEGRA` in July, `BSE` today).
  A derivation has nothing to reverse: you re-evaluate the rule.

⇒ **Derive, don't repair.** This is the round-3 proposal, and it is what the user's
question licenses.

### 23.3 · ⭐ The sequencing unlock — U3 does NOT depend on U2 (measured, not argued)

`app/services/bhavcopy_service.py:255`:

```python
active_only = "" if historical else " AND is_active = true"
```

**Historical-mode ingestion ignores `is_active` entirely.** Therefore **U3 (the 09-05 →
today backfill) has no dependency on U2 whatsoever**, and §7's stated chain
`U1 → U2 → U3` is wrong.

⭐ **This is what makes choosing the better design free.** The urgent data item (close the
coverage hole) and the design decision (what a universe *is*) are independent. We do not
have to ship a fast repair to stop the bleeding and promise to do it properly later —
the promise that never survives contact with a running clock.

It also independently corroborates the external R2 review's G6: historical-mode ingestion
is a **self-healing repair**, so U3 should be **recurring**, not one-off.

### 23.4 · The rebuild is far smaller than it sounds — most of it is already built

Measured 2026-09-13 (read-only `SELECT`s + `grep`):

| Piece | Status | Measured |
|---|---|--:|
| `stocks.isin` — a permanent identity anchor | exists, **UNIQUE, zero duplicates** | 2,547 / 3,392 |
| `stocks.listed_on` | exists | 2,547 |
| ISIN-keyed rename handling | **BUILT** (`seed_stocks.plan_renames`) | — |
| CA detector + quarantine columns | **BUILT** (`ca_detector.py`, `ca_flagged_at`) | 3 flags total |
| `corporate_actions` model | **BUILT** | table 0 rows |
| `universe_service.resolve_universe` | **BUILT** — a single resolver already exists | — |
| `kite_instruments` | empty | 0 |
| `categories` / `stock_categories` | empty | 0 / 0 |
| `indices` / `index_constituents` | thin | 3 / 89 |

⛔ **Consequence for the queue: U14 ("corporate-action detector + quarantine — NEW")
duplicates an existing implementation.** That is a **W1 violation inside our own plan** —
the artifact disagreed with the checkbox and we wrote the checkbox.

⭐ **The pattern across the whole inventory: the components exist. `is_active` is the only
wiring between them, and it is a mutable boolean with no owner.** That is the thing to
rebuild — not the components.

### 23.5 · ⛔ Two defects found while answering this question

Neither is in any review, and both are *worse* than the items they sit next to.

**(1) The CA detector is gated on the broken flag AND is forward-only.**
`ca_detector.py` filters `AND s.is_active AND s.ca_flagged_at IS NULL`, and
`eod_catchup.py:123` calls it **one session date at a time**. So:

- through the entire outage it has been **blind to exactly the names that matter** (the
  wrongly-inactive real universe);
- it has never been run backwards over the 1,098-session archive.

It has produced **3 flags in its lifetime** — `DUCON` (−26.6%, 08-25), `CORDELIA`
(−90.2%, 08-25), `TCC` (−79.7%, 09-04) — against the **49 unadjusted corporate actions
known to sit in the top-250-liquid universe alone** (`[[study-measurement-defects]]`, and
the +49R of fake profit that measurement cost us). ⇒ **The correct U14 is not "build a
detector". It is "the detector exists, remove its `is_active` gate, and run it backwards
once."** Materially cheaper and materially more valuable than what U14 proposed.

**(2) `stocks.tick_size` is a third copy of a value B3 gave an owner.**
`seed_stocks.py` inserts the literal `0.05` and **never updates it on conflict**;
`kite_client.py:144` writes it from the instruments dump; B3's dated schedule lives in
`app/broker/tick_schedule.py` and the paper broker reads `settings.paper_tick_size`.
Three copies, one owner — a **W5** instance. B3 measured that the ₹0.05 grid has been
wrong for sub-₹250 names since June 2024. The rebuild should drop the column or declare
it a cache of the schedule; it must not be reseeded as a literal.

### 23.6 · ⭐ THE PROPOSAL — "REBUILD-D" (derive, don't repair)

Four items. Three are a day or less; one is the real work.

| # | item | size | what it kills |
|---|---|--:|---|
| **D1** | **Identity = ISIN, permanent.** `stocks.id` never deleted, never reused; `symbol_history(stock_id, symbol, series, valid_from, valid_to)`. | ½ day | §20/2's dangerous reversal; symbol-rename ambiguity. 75 % already present. |
| **D2** | ⭐ **`is_active` stops being a decision variable.** Replace with dated **facts** — `series` + listing status (EQUITY_L), `kite_tradable` (instruments dump), bar coverage (computed) — and make the universe a **named, versioned rule** evaluated over them and materialised daily. `resolve_universe` reads the snapshot; `is_active` survives as a **derived view** so the 79 call sites in 45 files need not all change at once. | **2–3 evenings** | the entire failure class. This is U13, promoted to the front. ⛔ **SUPERSEDED — §25b/1 (34 readers, not 79) and §25c (the view cannot work; keep the column, remove the three writers). Revised item = D2′ in §26.** |
| **D3** | **The archive never consults a trading decision** (= U6′). | ½ day | a selection mistake destroying price history. |
| **D4** | **Fix the CA detector** — drop the `is_active` gate; run it backwards over the archive once. | ½ day | §23.5/1; replaces U14. |

⭐ **The derived-view trick in D2 is what makes this affordable for a solo developer.**
The honest cost of "remove `is_active`" is touching 45 files. The honest cost of "make
`is_active` a view over the snapshot" is touching the writers only — and the 79 readers
keep working, unchanged, reading a value that **can no longer be written by the wrong
process**. The migration to explicit universe queries then happens per-caller, at leisure,
with no outage.

⚠ **Where this proposal agrees with round 2, and where it goes further.** ChatGPT's §10
and §13 (universe *definition* vs *snapshot*), DeepSeek's §2.1 (U6′ closes the data-loss
path but **not** the selection-corruption path — `seed_stocks.py`'s conflict branch still
does not own `is_active`, **confirmed by reading it today**) and the external Claude
review's G1 all point the same way. **None of them proposes removing the flag** — all three
propose *repairing it more carefully*. D2 says the flag is the defect.

### 23.7 · ⛔ What I would NOT rebuild — stated because "rebuild" has gravity

1. **`ohlcv_1d`.** 2.08 M bars, attribution internally consistent. The 922-day hole is a
   **fetch** problem, not a design problem. Do not redesign the price archive.
2. **Selection.** A rebuild is precisely the moment a liquidity floor gets slipped in
   "since we are redoing it anyway". §9/1: measured, illiquid set **net-positive**, user
   ruling explicit. **§12's line holds without exception: structure is free today,
   selection still needs `t ≈ 3.6`.**
3. **The 5-table institutional security master** (`security` / `security_listing` /
   `security_status` / `universe_snapshot` / `data_coverage`). Already parked in §19d and
   correctly. ISIN + `symbol_history` + one snapshot table expresses every failure mode
   this project has actually had. If a reviewer wants the fifth table, they must name the
   failure it prevents that D1–D4 cannot express.
4. **`stocks.id` → a separate `security_id`.** Answered in §22/4: never-delete +
   `symbol_history` is cheaper and sufficient. A second identity column is maintenance
   with no named payoff.

### 23.8 · The honest cost, and what it delays

D2 costs ~3 evenings and it **does not delay U1, U3, U4′ or U10a′** — §23.3 proves the
backfill is independent. What it delays is the moment the *scanner* sees the real
universe, which is currently delayed anyway and has no clock on it (the book is empty;
nothing is being traded off the scanner today).

⚠ **The one clock it touches is `load_frames` (§20/1, ~2026-10-06).** That clock is a
consequence of the **coverage hole**, which U3 closes — and U3 is unblocked. So REBUILD-D
does not push that deadline. ⭐ **This also re-answers §22/2 more cleanly than either
option offered there:** the deadline is neither a reason to reorder P0 nor a reason to
weaken a measurement instrument — it is a reason to run U3 in **historical mode now**,
which needs no universe decision at all.

⚠ **What is genuinely lost by choosing REBUILD-D over the fast repair:** if D2 slips or
proves harder than estimated, we will have spent the window and still have a broken flag.
**The mitigation is that D3 + U3 are independently shippable and close the data-loss
paths on day one** — so a D2 slip costs a delayed scanner, never a lost bar.

---

## §24 · Questions for round 3 — put to reviewers, unanswered by us

The user has asked for this to go to the panel before anything is built. **These are the
questions; §23 is our position, not our decision.**

1. **[BLOCKING] Is REBUILD-D right, or is it scope creep dressed as architecture?** A
   solo developer in evenings is proposing to delete a column that 79 call sites read. ⛔ **§25b/1: the number is 34.**
   The derived-view migration (§23.6/D2) is the whole argument for feasibility — **attack
   that specifically.** If the view is unworkable (write paths, `mypy`, SQLAlchemy model
   mapping, the `ON CONFLICT` writers), REBUILD-D collapses back to U2 and we should know
   it now.
2. **[BLOCKING] Does collapsing U2 into U13 lose anything?** Our claim: the repair becomes
   the rule's first evaluation, and the forensic/reversal apparatus becomes unnecessary
   rather than dangerous. **Name what a derivation cannot do that a repair script can.**
3. **[BLOCKING] What is the minimum honest content of a universe rule?** Our draft:
   `series ∈ EQUITY_L` + `plain EQ listing in kite_instruments` + `≥ 300 daily bars`,
   evaluated `as_of` a date, versioned, snapshotted. ⚠ Answers proposing a liquidity /
   price / market-cap term must engage §9 — that is an **empirical** claim under §6/2 and
   needs the `t ≈ 3.6` bar or a user ruling.
4. **Given §23.4 — what ELSE in this system is already built and mis-wired rather than
   missing?** The CA detector was found by grepping for what U14 proposed to build, and it
   already existed, gated on the broken flag. ⭐ **That check generalises: for each queue
   item, grep for its own name before building it.** Round 1 found two items this way
   (§20); §23 found two more. **Name the next one.**
5. **Does the ISIN key hold?** Measured: 2,547 of 3,392 rows carry an ISIN, **zero
   duplicates**; the 842 rows with no ISIN are all inactive and **all have bars** (the ⛔ **§25b/2: it is 845, three are ACTIVE, and they are a test fixture plus two indices — the claim is false. §25d found zero collision casualties.**
   bhavcopy-created archive-only names). Our reading: ISIN is a sound identity key for
   everything tradeable, and the 842 are archive-only by construction — which is the
   archive/trade split stated as data rather than policy. **Is there a case this cannot
   express?** (Renames, series moves `X` → `X-BE` — 13 such symbols exist today —
   delisting-then-relisting, an ISIN reassigned by the depository.)
6. **⚠ The measured false-positive count, which nobody predicted well.** DeepSeek's round-2
   prediction was that after a clean repair, `is_active` names with no recent bar should be
   `< 10`. **Measured today, before any repair: 137** of the 1,322 currently-active names
   have no bar since 2026-09-04. `QUINTEGRA` is not an isolated case. **What does a rule
   do with a name that is listed in `EQUITY_L` and has not traded in a week?** Suspension,
   illiquidity and delisting-in-progress are three different facts and our schema
   currently records none of them.

⭐ **Round-3 entry rule, unchanged (§16):** a point is adopted when it is **converged
across sources OR settled by our own measurement — never on consensus alone.** §23 is
settled by measurement where it cites a number and is **opinion everywhere else**, and the
opinion is what we are asking you to attack.

---

# PART VII — ROUND 3 ADJUDICATION (2026-09-13)

Five responses to PART VI (ChatGPT · Gemini · DeepSeek · Nemotron · an external Claude
session with a 597-line review). **Every claim below was checked against the code or the
database before disposition. Two checks went against this document's own PART VI, and one
went against the reviewer who raised it.**

## §25 · Dispositions

### 25a · ⭐⭐ CONFIRMED, AND IT IS THE DECISIVE FACT OF THE ROUND

> *"The rebuild already happened. On 2026-09-07, at speed, at night, with no design."*
> — external Claude review, §T1

**Measured:**

```sql
SELECT created_at::date, count(*) FROM stocks GROUP BY 1;
--  2026-09-07 | 3392      ← every row. one date. no others.
```

⭐⭐ **There is no pre-existing stock master to restore, and there never was one in this
database.** All 3,392 rows were manufactured in a single day by the emergency recovery.
Every `stocks.id` was minted then. `kite_instruments` was never repopulated at all. The
`is_active` values we have been debating how to "repair" were **produced by that night's
process ordering**, which §3a already proved was `backfill → seed → backfill`.

⇒ **The choice was never restore-vs-rebuild. It is: keep an architecture that was
improvised in a few hours under pressure, or replace it with one that was chosen.** That
reframing settles the cost argument. Three evenings is not an optional refinement bolted
onto a working system — it is the cost of no longer being stuck with an accident that has
already produced a five-day blackout, a documented reversal procedure that reactivates the
wrong companies, and a corporate-action detector blind to the entire real universe.

⭐ **This is the strongest single point produced in four rounds, and it came from a
reviewer reading our own measurements more carefully than we did.**

### 25b · ⛔⛔ FOUR ERRORS IN PART VI, ALL OURS, ALL CORRECTED HERE

**(1) "79 call sites in 45 files" is wrong — the real number is 34.** That grep counted
every occurrence of the string `is_active`, which includes `BrokerToken.is_active`,
`User.is_active`, a `sharpe_decay` local parameter and a screener column reference.
**Actual `Stock.is_active` read sites: 34.** ⚠ This was the load-bearing number in D2's
feasibility argument. It makes D2 *cheaper*, not harder — but it was wrong, it was ours,
and it was the number we asked reviewers to reason about.

**(2) "the 842 rows with no ISIN are all inactive and all have bars — archive-only by
construction" is wrong on every clause.** Measured: **845** rows have no ISIN, and **three
of them are ACTIVE**:

| id | symbol | company_name |
|--:|---|---|
| 1 | `KNOWNCO` | **Test Company Ltd** — a test fixture in the production stock master |
| 9470 | `NIFTYNXT50` | an **index**, carried as a stock row |
| 10151 | `NIFTYFPI` | an **index**, carried as a stock row |

⇒ "no ISIN ⇒ archive-only" is **false**, and the counterexamples are junk rows that a
universe rule would have to exclude on some other ground. §23.4's tidy "the archive/trade
split stated as data rather than policy" does not survive its own measurement.

**(3) "13 series-suffixed symbols" is wrong.** The list is `BAJAJ-AUTO`, `MCDOWELL-N`,
`NAM-INDIA`, `HCL-INSYS`, `MRO-TEK`… — **hyphenated company names**, not series suffixes.
Two (`DUCON-RE1`, `JAYKAY-RE1`) are rights entitlements. The claim was pattern-matching on
a hyphen and calling it a measurement.

**(4) The ISIN evidence was circular, exactly as H2 says.** We offered *"UNIQUE, zero
duplicates"* as proof the key holds. **`seed_stocks.py` writes `NULL` rather than violate
`uq_stocks_isin`** (§A1 says so, in our own document), so zero duplicates is guaranteed
under every possible input. **It measures that the collision handler exists.** ⇒ **H2's
reasoning is ADOPTED in full** — and see 25d for what happened when we went looking for the
casualties it predicted.

⭐ **All four are the same defect: a number was produced, and the question it actually
answered was narrower than the question it was used to settle.** That is H7, and 25f makes
it a convention.

### 25c · ⭐⭐ H1 — VERDICT CONFIRMED, STATED MECHANISM REFUTED

H1 claims D2's derived view is impossible because *"`ON CONFLICT` requires a unique index
to infer against. **A view has no unique index.**"* **Tested directly** (TEMP objects, one
rolled-back transaction, no real table touched):

| test | result |
|---|---|
| `ON CONFLICT` against a **simple auto-updatable** view | ⛔ **SUCCEEDED** — a genuine upsert (1 row, `sym='UPDATED'`) |
| plain `INSERT` into a view **joining** base to snapshot | ✅ **REJECTED** — `cannot insert into view "v_join"` |
| `ON CONFLICT` against that joined view | ✅ **REJECTED** |

⇒ **Postgres infers the conflict target *through* an auto-updatable view against the base
table's index, so the stated reason is false.** But **the view D2 actually needs has a
join**, joined views are not auto-updatable at all, and `INSTEAD OF` triggers do not restore
`ON CONFLICT`. ⭐ **The conclusion stands and the reasoning does not** — recorded so nobody
re-derives the false rule from the true verdict.

⭐⭐ **H1's ALTERNATIVE IS ADOPTED, and it is better than what it replaces.** The 09-07
failure was never that the column existed — it was that three processes could write it and
none owned it. **Keep the column; remove its writers.** Verified by grep: there are
**exactly three writers of `Stock.is_active`**, matching H1's prediction —

```
bhavcopy_service.py:216    _ensure_historical_stocks  (INSERT column list)
seed_stocks.py:345         seed                       (INSERT column list, literal `true`)
deactivate_dead_stocks.py:100  the ONLY UPDATE statement in the repo
```

A column with one writer, refreshed from a versioned rule, **is a materialised view
semantically without being one syntactically** — and the guarantee is enforced by the
database (trigger, or column-level `REVOKE UPDATE (is_active)`) instead of by convention.
**34 readers change by zero lines. The ORM is untouched. `ON CONFLICT` keeps working.**

⭐ **And H1's third check paid off: `resolve_universe` has 4 callers** (`profiles/pipeline`,
`broker/provisional`, `api/v1/strategy`, `backtest/walkforward`) **against 34 direct
queries.** So the remaining work is *routing existing callers through a resolver that
already exists* — a migration, not a build.

### 25d · ⛔ H2's PREDICTED CASUALTIES — REFUTED BY MEASUREMENT

H2 predicted (a) `EQUITY_L.csv` contains ≥ 1 duplicated ISIN, ~65%, and (b) ≥ 1 `stocks`
row has `isin IS NULL` despite the CSV supplying one, ~70%. **Both measured, both zero:**

```
EQUITY_L rows 2,568 · series EQ 2,292 / BE 249 / BZ 27 · duplicate ISINs: 0
stocks rows with NULL isin for which EQUITY_L supplies an ISIN: 0
```

⇒ **No identity has in fact been discarded.** ⭐ The correct disposition is the one this
project keeps having to make: **the reasoning is adopted and the predicted consequence is
absent.** D1's *evidence* must be replaced (25b/4); D1's *premise* survives the search for
its own counterexample. ⚠ And `SM` does not appear in `EQUITY_L` at all — the T2T ruling's
third series is not in the source we would gate on.

**What H2 got right that no measurement was needed for, and which IS adopted:** the unique
constraint sits in the wrong place. `uq_stocks_symbol_exchange` + never-delete + `ON
CONFLICT DO UPDATE` means **an NSE symbol reused after delisting silently merges into the
delisted company's row, and the new company's bars attach to the old company's id.**
Measured surface: **833 symbols in `stocks` are absent from `EQUITY_L`** (H2 said 951;
the hazard is real, the number was not). ⇒ **Move uniqueness onto `symbol_history
(symbol, exchange, valid_from)`.** D1 already builds that table and merely left the
constraint behind.

### 25e · ✅ ADOPTED FROM ROUND 3

1. ⭐⭐ **`≥ 300 bars` comes OUT of the universe rule** (H6). The other two terms are
   *exogenous* facts — what NSE lists, what Kite will route. Bar count is a fact about **our
   own data completeness**, and *a rule that reads its own completeness shrinks when our
   ingestion breaks.* **That is 2026-09-07 rebuilt inside the design meant to prevent it.**
   The engine's 300-bar window becomes a **scoring-time eligibility check** — a name with
   too little history is *unscoreable today*, never *unlisted*. Two layers, two questions.
   ⚠ §8's "1,801 names" therefore stops being a universe definition and becomes a **coverage
   statistic**.
2. ⭐ **The four membership flags are in scope for D2** (DeepSeek §2.2). `is_nifty50`,
   `is_banknifty`, `is_finnifty`, `is_fno` have the same shape: mutable, current-composition
   only, no point-in-time answer. ⭐ **A sharper root cause falls out of checking this:
   `is_active` is the ONLY one of the five missing from `seed_stocks.py`'s `ON CONFLICT DO
   UPDATE SET`.** The other four have the identical ownership defect but **self-heal on every
   reseed** — so they fail as silent *drift* instead of as a stuck value. One class, two
   symptoms; fix all five in one materialiser.
3. ⭐ **Run U3 now** (DeepSeek §7, and it is right that PART VI stated the unlock without
   acting on it). It is independent of every design decision here, it closes the only growing
   hole, and it stops the `load_frames` clock. ⚠ **It writes to the dev DB, so it needs the
   user's go-ahead** — it is the one item in this document that is not read-only.
4. **D2's first act is the rule's first evaluation, inside the same migration** (DeepSeek
   §2.4) — no window in which the writers are gone and the snapshot has not yet run.
5. **`deactivate_dead_stocks.py` is retired by D2, and its July judgements become an
   acceptance test** (DeepSeek §2.5): the rule's first evaluation must reproduce those 15
   deactivations with the same reasons. ⭐ It is also the only `UPDATE` writer, so retiring
   it is what makes the single-writer guarantee true rather than aspirational.
6. **Facts vs policies must be enumerated explicitly** (ChatGPT §8). `series`,
   `kite_tradable`, `listing status` are facts; "we trade only EQ" is a policy. Otherwise the
   rule becomes a new hiding place for assumptions — the thing `is_active` was.
7. **`stocks.id` is the permanent identity; ISIN is a dated attribute** (ChatGPT §6, H2/c).
   D1's title "Identity = ISIN, permanent" is wrong by its own question's standard — ISINs
   change on amalgamations and demergers. **Renamed: `D1′ — permanent internal id, ISIN as
   the strongest dated external attribute.`** No second `security_id` column (unchanged).
8. **A rebuild-from-empty test** (ChatGPT §19): reconstruction is a first-class operation,
   not an emergency sequence of commands. ⭐ **The original failure happened *during* a
   reconstruction** — which is the whole argument for making it testable.
9. **Check a `(stock_id, symbol, isin, first_seen)` seed file into the repo** (H2/2).
   "Never delete" is not enforceable against the `TRUNCATE` that has already happened once.
   ~3,400 rows, and it is what makes §20/2's reversal permanently safe instead of newly
   documented.

### 25f · ⭐ THE ESTIMAND CONVENTION — adopted as a standing rule

H7 names a pattern across three rounds: **E2** (checked *admission* to the universe, used to
settle *universe extent*), **ISIN** (checked *duplicates today*, used to settle *whether
collisions occur*), **the 137 count** (measured *pre-repair*, compared against a prediction
about *post-repair*, then recorded as a refutation it had not earned). 25b adds a fourth.

> ⭐ **STANDING RULE, into `docs/BUILD_QUEUE.md`'s probe conventions: state what the check
> would NOT establish, before running it.** The verification discipline in this project is
> strong; the **estimand** discipline is the weak joint, and every one of these four made a
> conclusion look better supported than it was.

⚠ **The 137 figure stands as a measurement and is withdrawn as a refutation.** It was
measured before any repair; DeepSeek's `< 10` prediction was about after one. It is
evidence that **13 active symbols are absent from `EQUITY_L` entirely** and that the schema
records neither suspension, illiquidity, nor delisting-in-progress — not evidence that
anyone's prediction failed.

### 25g · ⏸ PARKED · ⛔ REJECTED

| item | disposition |
|---|---|
| Lightweight provenance / `source_observation` lineage (ChatGPT §18) | ⏸ **PARK** — unblocks when the rule has >1 version and a snapshot disagrees with expectation. Real, not yet earned. |
| `listing_status` enum on `symbol_history` (DeepSeek §5/6) | ⏸ **PARK** — the right answer to the 13 absentees, but needs a source that publishes suspension. EQUITY_L does not. |
| Bar-coverage hysteresis (DeepSeek §5/6.1) | ⛔ **MOOT** — 25e/1 removes bar coverage from the rule entirely. |
| `isin IS NOT NULL` as a rule term (DeepSeek §24/3) | ⛔ **REJECT as a term, ADOPT as an assertion** — every EQUITY_L row has an ISIN, so it is redundant; a listed name *without* one is a bug to alarm on, not a name to silently drop. |
| `isin_history` table | ⛔ **REJECT** — reassignment is rare; a manual `UPDATE` with an audit row is proportionate. |
| 5-table institutional security master | ⏸ **PARK**, unchanged (§19d). No reviewer named a failure D1′–D4′ cannot express. |
| "Don't rebuild the research apparatus while you're in here" (DeepSeek §4/1) | ✅ **ADOPT into §23.7** as a fifth exclusion. |
| "Don't bundle the CA-adjusted-vs-raw decision into D4" (DeepSeek §4/2) | ✅ **ADOPT into §23.7** as a sixth. That is A3, still open. |

⭐ **Also confirmed, and it is the same pattern as the CA detector:** DeepSeek's §24/4
candidates are real. `categories`/`stock_categories` are **empty but consumed** by
`universe_service` (`kind="category"`), `screener/compiler.py`, `cas_tasks.py` and an API;
`strategy_profiles` is **empty but consumed** by `profiles/pipeline.py`, `daily_report.py`
and `broker/provisional.py`. **Built and starved, exactly like `ca_detector.py`.**

## §26 · REBUILD-D, revised

| # | item | change from §23.6 | est. |
|---|---|---|--:|
| **D0** | **Pin identity: check `(stock_id, symbol, isin, first_seen)` into the repo** | **NEW** (H2/2) — makes a rebuild reproduce the same ids | 1 hr |
| **D1′** | **Permanent internal `stocks.id`; ISIN a dated attribute; `symbol_history` OWNS the symbol uniqueness** | **renamed + constraint moved** (25d) | ½ day |
| **D2′** | **Keep the column, remove the three writers.** Trigger or column-level `REVOKE`; nightly materialiser from a versioned rule → `universe_snapshot`; **extends to all five flags**; first evaluation inside the migration; retires `deactivate_dead_stocks.py` | **mechanism replaced** (25c), **scope widened** (25e/2) | 2–3 evenings |
| **D3** | Archive never consults a trading decision (= U6′) | unchanged | ½ day |
| **D4′** | Ungate `ca_detector.py`; one backward pass over the archive | unchanged | ½ day |

**The rule, revised:** `series ∈ EQUITY_L` **AND** a plain `EQ` listing in
`kite_instruments`. ⛔ **No bar-count term** (25e/1). ⛔ No liquidity, price or market-cap
term (§9, unchanged and not reopened by any round-3 reviewer).

⚠ **Estimate.** §23.6 said 2–3 evenings for D2; H1 says 1–2 with the column kept; DeepSeek
says 4–6 with the widened scope. **We adopt DeepSeek's: 4–6 evenings**, because 25e/2
widened the scope after H1 narrowed the mechanism, and the two roughly cancel. ⭐ **The
honest estimate is the one that accounts for the scope we actually adopted, not the one
that makes the proposal easiest to approve.**

## §27 · What round 4 is for — and it should probably not happen

Round 3 changed decisions: the view mechanism is out, the bar-count term is out, the
membership flags are in, the identity title was wrong, and four of our own numbers were
wrong. That is a high yield. But §13f's rule — **a round only happens if a probe runs with
it** — now cuts the other way: **the remaining open items are build decisions, not review
decisions.** Three questions genuinely remain, and all three are settled by writing code,
not by asking:

1. Does the single-writer guarantee hold under a trigger, or does it need the
   `REVOKE UPDATE (is_active)` + dedicated-role form? **Settled by building it.**
2. Does the rule's first evaluation reproduce the 15 July deactivations? **Settled by
   running it.**
3. Do the 13 EQUITY_L absentees and the 3 junk active rows (`KNOWNCO`, `NIFTYNXT50`,
   `NIFTYFPI`) fall out correctly, or do they need a term the rule does not have?
   **Settled by evaluating it.**

⇒ **Recommendation: close the panel and build.** The single exception, if the user wants
one more pass, is a **narrow** round on D2′'s single-writer mechanism alone — not another
architecture round.

⭐ **And the one action that should not wait for any of it: run U3.** It is independent, it
closes the only hole that grows every day, and it needs nothing in PART VI or PART VII to
be accepted first.


---

# PART VIII — U3 EXECUTED (2026-09-13)

## §28 · The first write this document has made

⭐ **U3 ran. It is the only item in this document that has been executed, and it was run on
the user's explicit instruction.** `make backup` first (`trading_platform-20260913-215611.dump`,
58 MB), per §6/6 and the §10 risk register.

### 28a · What the run actually had to be

⚠ **The scope in §7/U3 was wrong in two ways, both found before running:**

1. **"09-05 → today" is not five sessions plus a weekend — it is exactly five sessions.**
   2026-09-05/06 and 09-12/13 are weekends. **The hole was 09-07 → 09-11.** There was no
   missing session after 09-11, so "today" was never in scope.
2. ⛔ **`scripts/backfill_ohlcv_history.py` would have been a NO-OP, silently.** Its
   `_already_done()` guard skips any date holding `>= _COMPLETE_DAY_ROWS` bars, and
   **`_COMPLETE_DAY_ROWS = 500`** — while the broken sessions each held ~1,170 against a
   normal ~2,630. Every session in the hole would have been classified "already complete"
   and the script would have printed *"nothing to fetch — range already complete."*

⭐ **That is a REAL DEFECT, not a workaround detail** (see §28d). The run therefore reused
that script's own `_fetch_all` loop with an explicit date list — reusing the implementation
rather than writing a second one (**W2**), since the loop is correct and only the
completeness *predicate* is wrong.

### 28b · Result — measured before and after

| session | bars before | bars after |
|---|--:|--:|
| 2026-09-04 (last healthy) | 2,633 | 2,633 |
| 2026-09-07 | 1,182 | **2,652** |
| 2026-09-08 | 1,179 | **2,650** |
| 2026-09-09 | 1,175 | **2,644** |
| 2026-09-10 | 1,168 | **2,638** |
| 2026-09-11 | 1,166 | **2,637** |

- **+7,351 bars** (`ohlcv_1d` 2,082,639 → 2,089,990), matching the reported inserts exactly.
- **Names with a bar on 09-04 and none after: 1,481 → 4.** The four residuals — `RNBDENIMS`,
  `DAICHI` (both `is_active`), `MANAKSTEEL`, `HEG` — stopped appearing in the bhavcopy
  itself. **That is a real trading/listing event, not an ingestion failure**, and it is
  precisely the population §25g parked the `listing_status` enum for.
- `RELIANCE`, `TCS`, `HDFCBANK`, `INFY`, `ICICIBANK` all current to **2026-09-11**.
- **Idempotency confirmed by arithmetic:** the per-day `skipped` counts (1,182 / 1,179 /
  1,175 / 1,168 / 1,166) equal the pre-run row counts exactly. Nothing was double-written.
- **3 new `stocks` rows** created inactive by `_ensure_historical_stocks` — `DEEPA`,
  `CRESTO`, `DOLLEX` (3,392 → 3,395). Designed survivorship-safe behaviour; ⚠ these are
  likely renames, which is the standing symbol-churn caveat.

### 28c · ⭐⭐ §23.3's unlock is now DEMONSTRATED, not merely measured

**`is_active` was 1,322 before the run and 1,322 after.** The universe was not touched, and
the breadth hole closed completely. ⇒ **U3 never depended on U2**, §7's `U1 → U2 → U3` chain
was wrong, and the `load_frames` clock (§20/1, ~2026-10-06) is **stopped** — its cause was
the coverage hole, which no longer exists.

⭐ **The design decision is now entirely unhurried.** Nothing in REBUILD-D is on a clock.

### 28d · ⛔ NEW DEFECT — the backfill can repair a MISSING session, never a THIN one

`_COMPLETE_DAY_ROWS = 500` is a fixed floor standing in for "this day is complete". A day at
45 % of normal breadth passes it. ⭐ **This is the same blindness as the 6.8.6 feed alarm in
§4a — an instrument asserting PRESENCE where the failure mode is COVERAGE** — and it is the
third instance in this document (feed alarm · `load_frames` · this).

⇒ **New queue item, cheap and independent of REBUILD-D:**

> **U15 — make the backfill's completeness predicate breadth-aware.** Compare a session's
> row count against the **trailing median session** (e.g. `< 80 %` ⇒ not complete) instead
> of a fixed 500, and expose it as a CLI override. **ACCEPTANCE:** a session seeded at
> 45 % of trailing median is re-fetched rather than skipped. **DO NOT** raise the constant
> to another fixed number — that reproduces the defect at a different threshold.

### 28e · What U3 did NOT do

- ⛔ **It did not run the corporate-action detector over the new bars.** `ca_detector.py`
  is called from `eod_catchup`, not from `ingest_bhavcopy_date`; CA flags stand at **3**.
  **7,351 bars have entered the archive unscanned** — which is D4′'s job and is now slightly
  more urgent than it was this morning.
- It did not touch `is_active`, `kite_instruments`, or any universe state (U1, U2/D2′ remain
  open).
- It changed no recorded number in the trading sense: `positions` is empty, and bars are
  inputs, not results.


---

# PART IX — U1 EXECUTED (2026-09-13)

## §29 · `kite_instruments` has rows, and now it has an owner

### 29a · ⭐ The finding that shaped the design: the dump is PUBLIC

U1's SCOPE assumed the sync needs a Kite token, and noted one was present. **It was not
— token id 3 expired at 06:00 IST on 09-12**, so the spec was already stale when read.
That turned out not to matter, because **`https://api.kite.trade/instruments` returns
HTTP 200 with 110,290 rows and no `Authorization` header** (measured 2026-09-13).

⭐⭐ **This is not a convenience, it is the whole design.** A Kite access token dies
~06:00 IST daily and is renewable only through an interactive OAuth login. **A beat task
that required one would go dark on exactly the mornings nobody logged in — which is the
failure U1 exists to prevent.** `sync_instruments(db)` now takes `access_token: str | None`
and uses the public transport when none is given; the authenticated SDK path is kept for
the admin endpoint, which already holds a token. A test asserts both paths map a row
identically, so the two cannot drift.

### 29b · ⛔⛔ THE BUG THIS TURNED UP — a success log over a rolled-back transaction

The first real run printed:

```
INFO Kite instruments synced: 57595 rows upserted, 0 stale swept (0 hard)
RESULT synced=57595
```

**and left the table empty.** `sync_instruments` never committed — it relied on its caller,
and its *only* caller was the admin endpoint, whose `get_db` dependency auto-commits. **The
omission was invisible for exactly as long as there was one caller.** `run_db_task` (the
mandatory Celery bridge) does **not** commit, so the beat task added in this same change
would have upserted 57,595 rows and discarded them **every weekday morning, while logging
success.**

⭐ **The class of defect matters more than the instance: a log line that reports work the
transaction did not keep.** It would have been indistinguishable from working, and the
symptom — an empty `kite_instruments` — is the exact symptom U1 was written to fix. The
sync now owns its commit, matching `bhavcopy_service.upsert_bhavcopy_rows` in the same
layer. ⚠ **Found by running it, not by reading it** — the same lesson as §20.

**Both regression tests were stash-proven against the old code**: `assert set() == {601,
602}` and `assert not True`. ⚠ The commit assertion is made from a **separate session** on
purpose — `flush()` makes rows visible to *this* session, so a same-session assertion
passes vacuously (`.claude/rules/python.md`).

### 29c · What shipped

| part | what |
|---|---|
| **U1.1** | `sync_instruments(db, access_token: str \| None = None)` — public dump when token-free; **owns its commit** |
| **U1.2** | beat task `app.tasks.market_data_tasks.sync_kite_instruments`, **02:30 UTC (08:00 IST) weekdays**, before the 09:15 session |
| **U1.3** | `app/broker/universe_guard.py` + `live_worker._preflight` → **`EXIT_NO_UNIVERSE = 5`** |
| knob | `LIVE_UNIVERSE_MIN_FRACTION=0.5` in `.env.example` (**W3**) |
| tests | **28** — 17 guard, 11 sync (incl. the commit regressions) |

**The guard has two arms.** **EMPTY** — a universe of 0 can never be correct, needs no
baseline, and survives a Redis outage. **COLLAPSE** — below `min_fraction` of the previous
session's size, mirroring `_SWEEP_MIN_FRACTION`. ⚠ **Growth is never refused** (the pending
universe repair roughly doubles this number), the first run cannot fire the collapse arm,
and **a refusal does not overwrite the baseline** — otherwise the guard would disarm itself
after one bad morning. It fails **open** on Redis errors: a guard must never be the reason a
healthy worker cannot start.

### 29d · Acceptance — measured

| criterion | required | measured |
|---|---|---|
| `kite_instruments` rows | > 50,000 | **57,595** ✅ |
| subscription universe | > 1,000 | **1,178** ✅ |
| guard exits non-zero on empty | a test | ✅ `_preflight` → `EXIT_NO_UNIVERSE` |

Breakdown: NFO CE 16,901 · NFO PE 16,844 · BSE EQ 12,957 · **NSE EQ 10,246** · NFO FUT 647.

### 29e · ⭐ U1 un-darkens FOUR subsystems, and one of them answers §13/Q6

`kite_instruments` is consumed by more than the tick path:

1. `broker/tick_consumer._build_token_stock_map` — live_worker's subscription universe;
2. `api/v1/ws.py` — the **frontend live-quote WebSocket**, which returned nothing for
   every symbol for five days;
3. `services/chain_recorder.py` — the **F&O option-chain recorder**, whose docstring says
   it *"degrades silently: … NFO instruments not yet synced → status 'skipped'"*.
   ⭐ **So §7 of the daily report was correctly attributing its zero to a reason all along
   — the reason was this table.** That is the §7/§8 design working exactly as intended.
4. the admin sync endpoint itself.

### 29f · ⛔ NEW FINDING — the repaired universe lands near Kite's subscription cap

`live_worker` subscribes in **one call with no chunking**
(`ws.subscribe(list(token_map))`, `live_worker.py:1052`), and Kite caps a single
WebSocket connection at **3,000 instruments**.

- today, on the broken active set: **1,178** — comfortable;
- **joinable ignoring `is_active` (the post-repair ceiling): 2,655 — 88 % of the cap.**

⚠ **So D2′ moves this from 39 % to 88 % of a hard broker limit in one step**, with no
chunking, no second connection and no guard. It does not overflow today, but the headroom
is 345 instruments and the structural universe is the thing about to be redefined.

⇒ **New queue item U16 — chunk the subscription across connections (or cap and log
loudly) BEFORE D2′ lands.** ⭐ This is a direct answer to **§13/Q6** ("the failure mode of
this document is an unlisted consumer that stays broken after U1–U3; §4 lists seven, what
is the eighth?"): **the eighth is not a consumer that stays broken — it is one that breaks
*because* of the repair.**


## §30 · ⭐ The bug-hunter round on U1 — five defects, all in the new code

Run per CLAUDE.md (bug-hunter on broker/pipeline changes). **It found five, every one
verified by execution rather than by reading, and four of them MEDIUM.** All are fixed in
the same commit. ⚠ **This is the second review round in two days where the tests passed and
the code was still wrong** — the tests asserted what was intended.

| # | defect | why it mattered |
|--:|---|---|
| 1 | **`EXIT_NO_UNIVERSE = 5` was added to a comment that says "Exit codes for the supervisor" — and the supervisor was never taught it.** Code 4 gets a 60 s human-action pause; 5 fell into the generic `else` → *"restarting in 5s"*. | On the next outage: refuse → sleep 5 s → **full interpreter restart** → refuse … **~3,000 times a session**, a `log.critical` flood and DB churn, while the screen says the transient word "restarting". ⭐ **The guard would have converted a silent failure into a loud loop — an improvement, but not the one intended.** |
| 2 | **The check ran on `_bootstrap`'s RETURN value, so it fired *after* `startup_gap_fill`.** | A COLLAPSE refusal with `--gap-fill` first spends the throttled Kite REST pass its own docstring budgets at **~35 minutes**, then refuses and discards it. Under defect 1's loop: unbounded repeats against a rate-limited broker API. The EMPTY path escaped only by the accident that `if gap_fill and token_map` short-circuits on `{}`. |
| 3 | ⭐⭐ **The baseline was re-written on every accepted start**, so each morning was compared only against the morning before. | A collapse delivered in sub-threshold steps is accepted at **every** step and becomes the new bar: from 2,655, six 45 % drops run **2655 → 1460 → 803 → 441 → 242 → 133** — **95 % of the universe gone, guard silent.** ⚠ **Not a margin case: the real 09-07 event was 1,182 of 2,646 = 44.7 %, clearing the 50 % bar by 5.3 points.** A slightly milder regression fires nothing *and then becomes the baseline*. |
| 4 | **`if not rows / if not records: return 0` reported SUCCESS.** | A dump host answering **HTTP 200 with a login interstitial** passes `raise_for_status()`, parses to junk-keyed rows, maps to zero records → the beat task logs `refreshed: 0 rows` and finishes SUCCESS **every weekday forever** while the table goes stale. ⭐ **Stale is worse than empty: it is not a step change, so the new COLLAPSE arm never sees it either.** Same class as §29b, one door along. |
| 5 | The COLLAPSE message's only escape hatch was *"delete Redis key …"* — but **`redis-cli` is not installed on this box**. | An instruction the operator cannot run, on the one path where the guard deliberately wedges and the session is ticking away. |

**Fixes.** (1) a `code -eq 5` branch that prints the remedy and **sleeps 300 s**, plus a
CONTRACT comment at the exit codes saying a new code needs its Makefile branch *in the same
commit*. (2) `universe_check` is passed **into** `_bootstrap` and evaluated the moment the
map exists — before gap-fill, before the directory. (3) the baseline **ratchets UP only**
(`expire` refreshes it on an accepted-but-smaller start, so the high-water mark cannot
silently age out) plus a new **absolute floor**, `LIVE_UNIVERSE_MIN_COUNT=500`, because a
ratio has nothing to compare against on a first run. (4) both emptiness checks **raise**;
they sit before every write, so nothing half-applies and the sweep cannot fire. (5) the
message now prints a `uv run python -c …` one-liner that works here.

⚠ **The ratchet's cost, stated rather than discovered later:** a universe that legitimately
shrinks for good needs **one** manual baseline reset. Organic drift cannot reach 50 % (NSE
listings grow), and the refusal carries the command.

⭐ **New file `backend/scripts/sync_instruments.py`** — the manual remedy the supervisor
prints, and what U1's SCOPE originally called "a thin script". Token-free.

**Tests after the round: 41** (27 guard · 14 sync), plus 3 beat-schedule invariants in
`test_schedule_invariants.py`. ⚠ One of *our own* tests also had to be fixed: it opened its
second session on `app.db.session.AsyncSessionFactory` — **the app's module-global engine,
which `run_db_task` disposes inside its own loop** — and killed a *later* test with *"Event
loop is closed"*. **Use conftest's `_SessionFactory`.** Caught only by running the suite in
a different order (111 → 133 → 189 passing as the selection widened).


---

# PART X — D4′ RESCOPED BEFORE BUILDING (2026-09-13)

## §31 · ⛔ "Run the CA detector backwards over the archive" is NOT safe as written

§23.6/D4′ and §25e adopted *"drop the `is_active` gate; run it backwards over the archive
once"* — half a day, uncontroversial. **Measured first (read-only, dev DB, 2026-09-13),
and the second half is wrong.**

`ca_detector.scan_for_discontinuities` flags a stock when
`|open ÷ prev_close − 1| > 20 %`, sets `ca_flagged_at`, and `universe_service.resolve_universe`
then **excludes that stock from every suggestion universe until a human unflags it**. Run
over the whole 1,098-session archive that fires:

| threshold | distinct stocks flagged | events |
|--:|--:|--:|
| **20 % (the shipped default)** | **1,768 of 3,395 (52 %)** | 2,923 |
| 30 % | 1,581 | 2,232 |
| 40 % | 1,385 | 1,765 |
| 50 % | 1,197 | 1,390 |

⛔ **At the shipped threshold the backward pass quarantines 386 of the 1,322 currently
active names — 29 % of the tradeable universe — permanently, in one command**, since the
flag has no expiry and only a human clears it.

⭐ **The premise that fails is written in the detector's own docstring:** *"Genuine
20 %-circuit moves are rarer than splits at this threshold; false positives cost a review,
false negatives cost a poisoned window — the asymmetry favors flagging."* That asymmetry is
sound **at forward cadence**, where the detector fires a few times a day and a review is
cheap. It does not survive a 1,098-session replay, where "a review" means **2,923 of them**.
⚠ **A threshold calibrated for a daily decision was about to be reused for a bulk one.** The
project already has a name for this shape: an instrument validated for one estimand used to
settle another (§25f).

## §32 · D4′, revised — split the safe half from the unsafe one

**D4a — ungate `is_active`. SAFE, ship it.** A corporate action is a fact about a *price
series*, not about whether we currently trade the name, and the quarantine's only consumer
(`resolve_universe`) filters `is_active` separately anyway — so gating *detection* on it is
both redundant and harmful. Its cost is bounded: forward cadence, a few events a day. ⭐ This
is what made the detector blind to the real universe for the whole outage, and it is the
half that mattered.

**D4b — the backward pass is a MEASUREMENT, not a quarantine. Rescoped.** Do not auto-flag.
Write the discontinuities to the (currently empty) **`corporate_actions` table** as a review
queue, and leave `ca_flagged_at` alone. Three things it needs that the forward detector does
not:

1. ⭐ **A discriminator, not just a threshold.** A true split/bonus lands near a simple
   ratio — 1/2, 1/5, 1/10, 2/3 — while a circuit move does not. Ratio proximity is a far
   better separator than magnitude, and it is testable against the four known cases
   (`SHRIRAMFIN` −81.1 %, `COFORGE` −79.7 %, `ANGELONE` −90.1 %, `DIACABS` +3118.6 %).
2. **A per-event record**, not a per-stock flag — the same stock can have several actions
   across seven years, and the current schema records only "flagged, once, for one reason".
3. **A decision about what quarantine even means historically**, which is A3 and still open:
   a 2021 split does not poison a 2026 window. ⚠ **The forward flag is permanent and
   date-less, so it cannot express that** — which is why D4b must not reuse it.

⇒ **D4b is no longer "half a day". It is the front half of A3 (corporate actions), which
§25g explicitly parked.** ⭐ **Recording this rather than running the command is the whole
value of measuring first:** the naive version would have looked like it worked — 1,768 rows
updated, no error — and silently removed a third of the scannable universe.

⚠ **Nothing about D4b is urgent.** The 7,351 bars U3 added are unscanned, but they are
unscanned in the same way the other 2.08 M are, and the archive has been CA-unadjusted
since it was built. ⭐ **D4a closes the regression; D4b was never the regression.**


---

# PART XI — D4a AND U15 SHIPPED (2026-09-13)

## §33 · D4a — the CA detector is no longer gated on the trading flag

One line of SQL removed from `ca_detector.scan_for_discontinuities`: `AND s.is_active`.

⭐ **Why it was wrong, not merely unlucky.** A corporate action is a fact about a **price
series**; `is_active` is a statement about whether we currently *trade* the name. Worse, the
quarantine's only consumer — `universe_service.resolve_universe` — already filters
`is_active` **itself**, so gating *detection* on it was **redundant**. Redundant and
harmful: through the 09-07 → 09-12 outage the real universe was wrongly inactive, so the
detector was blind to exactly the names that mattered. **3 flags in its lifetime**, against
49 unadjusted actions known to sit in the top-250-liquid set alone.

⚠ Forward cost is bounded: the daily ingest path still writes bars only for active names, so
an inactive stock gets no new bars and therefore no new gap to flag. **Three regression
tests**, each failing on the old code.

⛔ **D4b (the backward pass) is NOT shipped — see §32.** It would quarantine 29 % of the
active universe.

## §34 · U15 — the backfill can now repair a THIN session, not just a missing one

`backfill_ohlcv_history` judged a date "already done" by a **fixed floor of 500 rows**
(`_COMPLETE_DAY_ROWS`). The five broken sessions each held ~1,170 against a normal ~2,630 —
**all comfortably over 500** — so running the script across that range would have printed
*"nothing to fetch — range already complete"* and done nothing. §28a caught it before U3 ran;
this fixes it.

**Completeness is now measured against the range's own median session** (`80 %`, via a pure
`complete_day_threshold()` so the rule is testable without a database), with the old 500 kept
only as a backstop for degenerate ranges, plus a `--min-rows` override and a printed line
naming every session it intends to re-fetch.

⚠ **Raising the constant would have reproduced the defect at a new threshold** — no constant
can be right for a quantity that grows with the listed universe. **8 tests**, including a
canary asserting the old floor *would* have passed every thin session.

⭐ **Third instance of one shape, now named in three places:** the 6.8.6 feed alarm asserted
recency, `load_frames` asserted a bar count, this asserted a row floor — **every one an
instrument asserting PRESENCE where the failure mode is COVERAGE.**


## §35 · U16 — the per-connection ceiling, asserted before D2′ can trip it

§29f found that `live_worker` subscribes in **one unchunked call**
(`ws.subscribe(list(token_map))`) against Kite's **3,000-instrument per-connection cap**,
with today's universe at 1,178 (39 %) and the **post-repair ceiling at 2,655 (88 %)**.

⭐ **Checked the SDK rather than assuming: `kiteconnect/ticker.py:567` just serialises the
whole list into one frame and enforces nothing client-side.** So exceeding the cap is a
*server-side* behaviour — the excess is dropped and nothing tells us. That is the same shape
as every other defect in this document: a silent partial that looks like success.

**Shipped as a third arm of the same guard, not a new mechanism** (W2). ⭐ **It REFUSES
rather than truncating, and that is the substantive choice:** subscribing "the first 3,000"
means silently picking which names the system stops watching — **a selection decision, made
by list order, with no evidence.** This project does not make those. The refusal names the
two real fixes: shard across connections, or narrow the universe rule.

⚠ Like EMPTY and FLOOR, the ceiling needs **no baseline and no Redis**, so it fires on a
first run and survives an outage of the store. And an over-cap universe is **not recorded**
as a high-water mark — otherwise a refused start would raise the baseline to a size the
connection cannot carry.

`LIVE_UNIVERSE_MAX_COUNT=3000` (W3). **6 tests.** ⚠ **This does not make a >3,000 universe
work** — it makes it impossible for one to fail quietly. Sharding is the follow-up, and the
headroom before it is needed is **345 instruments**.


## §36 · ⭐ Live verification with a real token (2026-09-13, after the user refreshed it)

U1's design deliberately does not need a Kite token — but having one closed a gap in **our
own testing**: the **public** transport had been verified against the real dump, while the
**authenticated SDK** transport (kept for the admin endpoint) had only ever run against a
stub. A test asserting the two map a row identically is not the same as both actually
working.

| check | result |
|---|---|
| token state | id 4 live, created 16:44 UTC, expires 2026-09-14 00:30 UTC (06:00 IST); id 3 correctly invalidated |
| `sync_instruments(db, access_token)` — **real SDK path** | **57,595 rows** |
| `sync_instruments(db)` — **real public path** | **57,595 rows** |
| `live_worker._preflight` against real state | **OK → 1,178 instruments**; baseline `None` → `1178` |
| knobs read from the live process | `min_fraction=0.5 · min_count=500 · max_count=3000` |

⭐ **The two transports agree on real data, not just in a stubbed test** — which is the claim
§29a actually needed. And the guard's whole path is exercised: first run, no baseline, accept,
record. ⚠ **The recorded baseline is 1,178, and the universe repair will take it to 2,655** —
growth, so accepted and ratcheted up (`test_growth_never_refused` pins exactly that).


---

# PART XII — WHAT THE UNIVERSE MAY AND MAY NOT GATE (2026-09-14)

## §37 · ⛔⛔ The universe is an ENTRY gate — and the tick feed does not know that

**User question:** *what do the downstream processing units — signals, alerts, orders,
positions, holdings — do with `is_active`?* Checked in code rather than reasoned from the
diagram, and it produced a hazard that **D2′ would make substantially worse**.

| stage | reads `is_active`? | where | verdict |
|---|---|---|---|
| bar ingestion | **yes** | `bhavcopy_service.py:255` | ⛔ wrong — this is **D3** |
| signal minting | yes | `universe_service.resolve_universe` | ✅ correct: an ENTRY gate |
| provisional alerts / hot set | **yes** | `provisional.py:428, 442` | ⚠ wrong for HELD names |
| **tick subscription** | **yes** | `tick_consumer.py:469` | ⛔ **the dangerous one** |
| order path · `restrictions.py` · `paper_broker` | no | — | ✅ correct |
| `position_monitor.scan_positions` | no | — | ✅ correct — **but starved** |

### 37a · The chain, and why it fails silently

1. `scan_positions` evaluates **every** open position — correctly NOT universe-filtered.
2. It prices via `get_live_ltp(pos.stock_id)` → Redis `ltp:{stock_id}`.
3. Those keys exist **only for subscribed instruments**.
4. The subscription is `… JOIN stocks s … WHERE s.is_active = true`.

⇒ **A held name that leaves the active set stops receiving ticks, its `ltp:` key expires,
and the monitor skips it — permanently.** Its own docstring states the rule that makes this
silent: *"A position is skipped when no live LTP is available — the monitor never acts on a
stale price."* ⭐ **Correct in isolation, catastrophic in composition:** the position keeps
its SL and TP on paper and **nothing will ever evaluate them again**. No error, no alarm —
the un-exitable-position hazard the circuit guard exists for, arriving through another door.

### 37b · ⭐ Why D2′ escalates it from rare to routine

Today `is_active` changes only when a human runs a script — three writers, all manual.
**After D2′ it is re-evaluated NIGHTLY by a rule.** A delisting, a series move to
`BE`/`BZ`, a tightened definition: any of them can drop a held name overnight, unattended.
**D2′ converts a rare manual hazard into a recurring automatic one**, which is the opposite
of what the rebuild is for.

### 37c · The rule, and the fix

⭐⭐ **THE PRINCIPLE: the universe is an ENTRY gate. Nothing an open position depends on may
be universe-gated.** Entry, minting and display may be gated. **Pricing, monitoring, exits
and P&L must key off the POSITION, not the universe.** The order path and the monitor
already respect this — **the data feeding them does not.**

⇒ **NEW ITEM U17, a PRECONDITION for D2′** (one clause, two call sites):

> **subscription universe = trading universe ∪ { names with an open position or holding }**

and the same union for the alert hot set (`provisional.py`). ⚠ It composes with **U16** by
construction: because the ceiling arm **refuses rather than truncating**, a held name can
never be one of the ones silently dropped.

⚠ **Latent, not live: `positions` is 0 rows today**, which makes this the cheapest moment
to fix it — the §12 window argument applied to the one place it has not yet been applied.

### 37d · D3's real justification, which is not storage

Three rounds have argued D3 on storage (~6 MB/year) versus the T2T ruling's wording.
**Positions settle it better:** if we hold a name and it is deactivated, **its daily bars
stop**, so its own P&L history, exit analysis and R-multiples are computed against a series
that **ends mid-position**. ⭐ *"The archive must never consult a trading decision"* stops
being an architectural preference and becomes a correctness requirement about trades we
actually hold.

**⇒ REVISED ORDER: D3 → U17 → D0 → D1′ → D2′ → (D4b / A3 later).**


---

# PART XIII — D3 SHIPPED (2026-09-14)

## §38 · The downstream trace, which is what decided it

Three rounds argued D3 on storage (~6 MB/year) versus the T2T ruling's wording. **Tracing
the data instead settled it in one query**, and on a completely different ground.

### 38a · ⛔⛔ U3's repair was NOT durable — the hole reopens every day

`eod_catchup.py:102` calls `ingest_bhavcopy_date(db, d)` **without `historical=True`**, so
the daily path took the `AND is_active = true` branch. Measured on the last completed
session:

| 2026-09-11 | names |
|---|--:|
| names that actually traded (in `ohlcv_1d`) | **2,637** |
| what the OLD daily path would write | **1,166** |
| what the NEW daily path writes | **2,637** |
| ⇒ **dropped every single day** | **1,471** |

⭐ **1,471 is the same number U3 repaired per session** (1,469–1,471). So U3 refilled the
hole in `historical` mode on 09-13, and **the very next EOD run would have re-opened it** —
leaving a one-session hole that regrows daily until D2′ lands, weeks away. ⇒ **D3 is not a
philosophical question about a ruling. It is what makes U3 stick.**

### 38b · Every consumer of `ohlcv_1d`, checked

| consumer | affected? | why |
|---|---|---|
| `signal_service` (minting) | **no** | filters `is_active` itself — the ENTRY gate is intact |
| `universe_service.resolve_universe` | **no** | same |
| `provisional` (alerts) · `pair_universe` · `shadow_compare` | **no** | all filter `is_active` |
| `feed_health` (the 6.8.6 alarm) | **no** | measures `max(time)` — recency, not breadth. ⭐ Which is exactly why it read ✅ through the whole outage |
| `deactivate_dead_stocks.py` | **no** | keys on absence from `kite_instruments`, **not** bar recency — so D3 cannot feed back into the flag |
| `corpus_attribution` | **no** | universe is `is_nifty50`, a different flag |
| `benchmark` · `benchmark_curve` · `beta_ir` · `buy_and_hold` | **no** | per-`stock_id` or an explicit universe, never "has bars" |
| `liquidity` | **no** | medians are per-`stock_id`; new rows for other names cannot move them |
| backtest · `walkforward` · `profiles/pipeline` | **no** | universe comes from `resolve_universe` |
| **U15's completeness threshold** | **yes** | the median session rises ~1,170 → ~2,640. **Self-adjusting by construction** — that is why U15 is a median and not a constant |
| **`ca_detector`** | **yes** | post-D4a it scans all stocks, and inactive names now get bars, so new gaps become visible. ⚠ See 38c |
| **`load_frames`** (research) | **yes, and it is a RESTORATION** | the 1,228 wrongly-inactive names already hold bars through 09-11, so D3 keeps them qualifying instead of decaying out. **This is the §20/1 clock, closed permanently** rather than paused |

⭐ **Nothing defines a universe by "has bars"** — that was the one hazard worth checking,
because it would have silently widened a recorded number. It does not exist here.

### 38c · The one interaction worth stating for a future session

**D3 + D4a compose.** D4a ungated CA detection from `is_active`; D3 now gives inactive names
bars to detect on. So archive-only names will start accruing `ca_flagged_at` over time.
⚠ **That is correct** (an unadjusted split poisons a window whoever holds it) **but it has a
delayed consequence: when D2′ repairs the universe, some returning names will already be
quarantined.** That is not a bug — it is the quarantine doing its job on names we were about
to start scoring — but it will look like a surprise on D2′ day if nobody wrote it down.
**Measure the flag count before and after D2′'s first evaluation.**

### 38d · What D3 does NOT do, and the line it does not cross

Ingestion still **skips unknown symbols** in the daily path; creating a stock row remains a
`historical=True` behaviour. ⭐ **Recording a bar is bookkeeping; minting an instrument is a
universe decision** — and this function does not make universe decisions in either
direction now.

### 38e · The T2T ruling is not overturned

It excludes `BE`/`BZ`/`SM` from **live scanning**, and the scanner still enforces exactly
that — `resolve_universe` filters `is_active` on its own. ⭐ **And it was never implementable
as a storage rule anyway: `parse_bhavcopy_csv` keeps `EQ` series only**, so a name that
*moves* to `BE` stops appearing in what we ingest regardless of any flag. The storage reading
of §22/1 was therefore describing a behaviour the code could not produce; U6′/D3 is the first
implementation of the ruling's actual intent, not a reversal of it.

**Test reversed deliberately:** `test_inactive_stock_gets_no_bars` (docstring: *"The T2T
ruling: a deactivated name gets no EOD bars on the live path"*) is now
`test_an_inactive_stock_now_receives_bars`, with the history kept in the class docstring so
the decision stays visible rather than vanishing. **13 tests pass.**


---

# PART XIV — U17 SHIPPED (2026-09-14)

## §39 · The subscription is now `universe ∪ held`, and the scope was decided by tracing

§37 established the principle. This is the build, and **the trace narrowed it** — the
first instinct ("union everything that filters `is_active`") turned out to be wrong in one
place and unnecessary in another.

### 39a · What the exit path actually depends on

```
subscription  →  tick  →  ltp:{stock_id}  →  scan_positions  →  SL / TP / trail / exit
```

`_publish_ltp` writes **from the tick batch**, so a subscribed name gets its price whether
or not anything else knows about it. ⇒ **Only the SUBSCRIPTION gates the exit path.** That
is the one query U17 had to change: `tick_consumer._build_token_stock_map`, now

```sql
WHERE ki.instrument_type = 'EQ'
  AND (s.is_active = true
       OR EXISTS (SELECT 1 FROM positions p
                  WHERE p.stock_id = s.id AND p.closed_at IS NULL))
```

⚠ **Mode-agnostic on purpose** (`closed_at IS NULL`, any mode): a Phase-7 **live** position
needs its feed more than a paper one, and writing `mode = 'paper'` here would have to be
found and removed later, probably after it mattered.

### 39b · ⭐ What the trace talked me OUT of

**The provisional alert hot set (`provisional.py:428, 442`) is deliberately NOT unioned**,
and that is a decision rather than an omission:

1. **Exits do not need it.** It drives near-trigger/provisional computation — ENTRY
   discovery — while `ltp:` comes from the tick batch.
2. ⭐ **Unioning it would be a regression.** The set is capacity-bounded by
   `live_provisional_trigger_market_max`, and its own comment records a past
   quant-verifier finding that a stale row *"silently eats a slot"*. Spending discovery
   slots on names we already hold is precisely that bug, re-introduced deliberately.

⭐ **The general form, worth keeping: a fix aimed at a principle should be applied where the
DATA flows, not everywhere the same predicate appears.** Four call sites mention
`is_active`; exactly one of them was on the path that mattered.

### 39c · The residue the union cannot fix — and why it warns instead of refusing

A held name with **no `EQ` row in `kite_instruments` at all** has no token to subscribe to.
`held_without_instrument()` reports those and `_bootstrap` logs them at ERROR with their
symbols. ⚠ **Reported, never raised:** these positions are genuinely un-exitable through
the live path and need a human (square off at the broker, or repair the instruments table)
— but **one stranded name must not stop the worker serving every other position.** That is
the opposite call from U16's ceiling, and deliberately so: the ceiling means *every*
subscription is wrong, this means *one* is.

### 39d · Verified

| check | result |
|---|--:|
| tests | **9**, two stash-proven to fail on the old query (`assert None == 1`) |
| real data | open positions **0** · subscription universe **1,178** · stranded **0** |
| vs U16's cap | 1,178 ≤ 3,000 ✅ |

⚠ **The union only ever adds INACTIVE held names**, so at cycle-2 scale (1–2 positions) it
is a rounding error against the cap — it cannot be the thing that trips U16.

⭐ **Latent today (`positions` = 0 rows), which is exactly why it was cheap to build now.**
It becomes load-bearing the moment D2′ starts moving `is_active` nightly.


---

# PART XV — D0 SHIPPED (2026-09-14)

## §40 · The identity pin, and what it is honestly worth

### 40a · ⭐ What pinning buys — and the case where it buys nothing

Restoring from a `pg_dump` carries ids with it, so the pin adds **nothing** there.
It matters in **the case that actually happened**: a rebuild **from source** — re-seed
`stocks`, re-attach bars from the bhavcopy archive. Bars re-attach BY SYMBOL so they stay
internally consistent, which is why nobody noticed; but **every artifact keyed on an id from
before silently re-points at a different company.** That is §20/2's reversal SQL, and it is
also every probe JSONL dump, forensic table and analysis output written before 09-07.

⇒ **The pin's job is narrow and worth stating precisely: make a SOURCE rebuild reproduce the
same `id → symbol` mapping.**

### 40b · ⛔ A forensic detail found while building it

`stocks` holds **3,395 rows with ids running 1 … 2,178,609.**

⭐ **A `ON CONFLICT DO UPDATE` still consumes a sequence value on every attempted insert**, so
that gap is a *log* of how many insert attempts the 09-07 reconstruction made — on the order
of 950 backfill days × ~2,300 symbols ≈ 2.18 M. **Independent, third confirmation of §3a's
`backfill → seed → backfill` ordering**, arriving from the sequence rather than the id blocks.
It also settles that the ids are arbitrary: pinning them preserves something with no meaning
beyond *everything else points at it*, which is exactly why it must not move.

### 40c · Shipped

| piece | what |
|---|---|
| `backend/seed/stock_identity.csv` | **3,395 rows, 116 KB** — `stock_id, symbol, isin, first_seen`, sorted by symbol |
| `app/services/stock_identity.py` | pure `serialise` / `parse` / `diff` — no DB, no clock |
| `scripts/stock_identity.py` | `--export` · `--verify` (exit 1 on conflict) |
| tests | **11**, including the negative control |

⚠ **`data/` is gitignored**, which is why the pin lives in `backend/seed/`. A pin file git
never sees is not insurance.

### 40d · ⭐ Only a CONFLICT fails — and that is a design decision

`diff()` returns three lists, deliberately separated:

- **conflicts** — same symbol, different id. **The only failure**; it is the 09-07 defect.
- **missing** — pinned names absent from the DB. Delisting, or an incomplete rebuild.
- **added** — live names not in the pin. New listings.

⭐ **Churn is not drift.** Failing on ordinary listing turnover would make the check noisy
within weeks, and **a noisy guard gets ignored, which is how guards die** — this project has
already watched the 6.8.6 alarm read green through a five-day outage because it asserted the
wrong thing.

⭐ **The first test is a NEGATIVE CONTROL**, not a happy path: it plants the exact 09-07
scenario (`QUINTEGRA` 228 → 900, `BSE` 500 → 228) and asserts both are caught. **A verifier
that cannot detect the failure it exists for is decoration** — the `instrument_self_validation`
discipline applied to a data file.

### 40e · The restore procedure this is insurance for

Written down because insurance nobody can operate is not insurance:

1. load the pin;
2. insert `stocks` with **EXPLICIT ids**;
3. **advance the sequence past the maximum** —
   `SELECT setval(pg_get_serial_sequence('stocks','id'), (SELECT max(id) FROM stocks))`;
4. *then* seed / backfill as normal.

⚠ **Skip step 3 and the next insert collides.** ⚠ And per §28a / the recovery order: run
`seed_stocks.py` before any historical backfill, or `_ensure_historical_stocks` recreates the
master from the wrong end again.


---

# PART XVI — D1′ SHIPPED, DELIBERATELY SMALLER THAN SPECIFIED (2026-09-14)

## §41 · Why the constraint did NOT move, and what shipped instead

§26/D1′ said: *permanent internal `stocks.id`; ISIN a dated attribute; **`symbol_history`
OWNS the symbol uniqueness***. The last clause is the one that changed, and the downstream
trace is why.

### 41a · ⛔ What dropping `uq_stocks_symbol_exchange` would actually cost

**14 call sites assume one row per symbol** — `seed_stocks`' `ON CONFLICT (symbol, exchange)`,
`_ensure_historical_stocks`' `ON CONFLICT … DO NOTHING`, `upsert_bhavcopy_rows`'
`SELECT symbol, id FROM stocks WHERE symbol = ANY(...)`, `_build_token_stock_map`'s
`s.symbol = ki.tradingsymbol`, `ws.py`'s per-symbol lookup, and more. Drop the constraint and
none of them error — **they silently start resolving to an arbitrary row.** The upserts lose
their conflict target outright.

### 41b · ⛔⛔ And the hazard's frequency CANNOT be measured retrospectively

The hazard is **symbol REUSE**: NSE re-issues a delisted ticker, and
`isin = COALESCE(EXCLUDED.isin, stocks.isin)` overwrites the anchor, merging the new company
into the dead one's row — inheriting its id and its entire price history.

I measured it: **0 of 2,547 symbols carry an ISIN differing from EQUITY_L today.**
⚠ **That number is worthless and I am recording it as such.** Our master was rebuilt *from
that very CSV* on 09-07, so agreement is guaranteed; and worse, **the merge overwrites its own
evidence** — after a reuse, the stored ISIN *is* the new company's. ⭐ **This is the fourth
instance of the estimand trap (§25f), caught this time before it was banked** rather than
after.

⇒ **A schema change that breaks an invariant 14 queries rely on, justified by a hazard whose
rate is unmeasurable, is not a trade this project makes.** `uq_stocks_symbol_exchange` stands.

### 41c · What shipped — record and refuse, not restructure

| piece | what |
|---|---|
| migration `f2a3b4c5d6e7` | `symbol_history(stock_id, symbol, exchange, isin, valid_from, valid_to, reason)`; **downgrade round-tripped on dev** |
| `SymbolHistory` model | + exported |
| `app/services/symbol_history.py` | `classify_isin_change` (pure) · `open_interval` · `seed_from_stocks` · `record_rename` · `detect_isin_conflicts` |
| `seed_stocks.py` | records renames · seeds intervals · **reports ISIN conflicts** · ⭐ **`COALESCE(stocks.isin, EXCLUDED.isin)`** — argument order reversed |
| tests | **14** |

⭐⭐ **The one-word fix that matters: `COALESCE(EXCLUDED.isin, stocks.isin)` →
`COALESCE(stocks.isin, EXCLUDED.isin)`.** The anchor is now **filled once and never silently
rewritten.** A differing ISIN on a known symbol is EITHER a reuse OR a data correction, and
**nothing in the feed distinguishes them** — so the old behaviour picked one answer silently,
and the answer it picked was the one that merges two companies. It now keeps what it has and
prints the conflict.

⭐ **Renames stop being invisible.** `plan_renames` already did the right thing (rename in
place, keep the id, keep the bars — AMIRCHAND → AEROPLANE) but left **no trace**, so *"what was
this id called in July?"* was unanswerable. **That is half of why §20/2's reversal SQL is
dangerous**, and it is now answerable.

### 41d · Verified on dev

`3,395` intervals · `3,395` open · **`0` stocks with two open intervals** (the one-open-interval
invariant, which lives in the writer because a partial unique index cannot express "one NULL
per group") · `valid_from` spans 2026-09-07 … 09-13 — ⭐ the later dates being exactly the three
rows U3's backfill created (`DEEPA`, `CRESTO`, `DOLLEX`), so the `first_seen` values are honest
rather than backdated.

### 41e · What is left of D1′, and its unblocking condition

**Moving the uniqueness is PARKED, not dropped.** ⇒ **Unblocks when `symbol_history` has
actually recorded a `reuse` event** — at which point the rate is measured instead of assumed,
and the 14-query migration has a reason. The detector shipped today is what will produce that
evidence; until then, `stocks.id` permanence is maintained by **never deleting rows**, which
costs nothing and is already true.
