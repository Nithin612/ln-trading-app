# Universe Rebuild Plan — stock master, sector map, index registry

**Status:** DRAFT for review · round 0 written 2026-09-12 · **round-1 adjudication (PART V)
2026-09-12** · ⭐ **PART VI added 2026-09-13 — the user's restore-vs-rebuild question, which
changes the queue and is the live question for round 3**
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
  ⚠ **The three round-2 reviews are NOT yet dispositioned**; PART VI was written before
  that adjudication and does not pre-empt it. **§24 holds the six round-3 questions.**

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

### U1 — Repopulate `kite_instruments` and give it an owner *(P0)*
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

### U3 — Backfill the 09-05 → today coverage hole *(P0, gated on U2)*
- **WHY** **1,481 names** had a bar on 2026-09-04 and none on 2026-09-11 — each is missing every session since. Left alone this is a permanent
  discontinuity inside the 300-bar window of every blue chip — the same class of defect
  as the 922-day 2020-12→2023-07 hole that invalidated 33 % of a study's panels.
- **SCOPE** Re-run bhavcopy ingestion for 2026-09-05 → today in `historical` mode
  (which bypasses the `is_active` filter) so every repaired name is filled. Idempotent
  (`ON CONFLICT DO NOTHING`).
- **ACCEPTANCE** Every session 09-05 → today shows ≥ 2,500 names; a span-vs-calendar
  gap check (the B4 guard) reports no per-name hole for the active set.
- **DO NOT** Re-run before U2, or the hole is simply refilled at the wrong breadth.

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
| **D2** | ⭐ **`is_active` stops being a decision variable.** Replace with dated **facts** — `series` + listing status (EQUITY_L), `kite_tradable` (instruments dump), bar coverage (computed) — and make the universe a **named, versioned rule** evaluated over them and materialised daily. `resolve_universe` reads the snapshot; `is_active` survives as a **derived view** so the 79 call sites in 45 files need not all change at once. | **2–3 evenings** | the entire failure class. This is U13, promoted to the front. |
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
   solo developer in evenings is proposing to delete a column that 79 call sites read.
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
   duplicates**; the 842 rows with no ISIN are all inactive and **all have bars** (the
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
