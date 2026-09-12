# Universe Rebuild Plan — stock master, sector map, index registry

**Status:** DRAFT for review · round 0 · written 2026-09-12
**Author:** Claude (session 2026-09-12) · **Owner:** Nithin
**Nothing in this document has been executed.** No table was written, no flag flipped,
no migration run. Every number below is a `SELECT` taken on 2026-09-12 against the dev
database `trading_platform`.

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
- **PART IV (§11–§12)** is the trap list and the questions we actually want answered.

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
  weaker. §12 Q4.

---

### U7 — Sector / industry mapping *(P2)*
- **WHY** 500 of 3,392 names carry a sector; the sector-RS overlay and the screener's
  sector filter both need it. Coverage from the current source is capped at the ~500
  names in `ind_nifty500list.csv`.
- **SCOPE** Declare the source of record and its refresh cadence. `ind_nifty500list.csv`
  is live and carries `Industry` for 501 names. Widening beyond that needs either the
  per-sector index constituent CSVs (free, ~15 files) or a different source — an open
  question (§12 Q2). Record the source and as-of date on the row; do not invent a
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

# PART IV — WHAT WE WANT FROM REVIEW

## §11 · What this plan deliberately does NOT do

- It does not touch the frozen engine, `SIGNAL_ENGINE.md`, or any scorer.
- It does not flip any gate from shadow to active.
- It does not restate any historical P&L (`positions` is empty; nothing to restate).
- It does not start cycle 2 or reset any paper clock.
- It does not attempt to recover the destroyed book, CAS history, or signal outcomes.
  Those are gone; the plan is forward-only.

## §12 · Open questions — please answer these specifically

1. **Q1 — Structural vs empirical.** Is the §6/2 split the right frame? Specifically:
   is "≥ 300 daily bars" structural (the engine's window canon cannot produce a score
   without it) or is it a disguised survivorship/liquidity filter?
2. **Q2 — Sector coverage.** The free `ind_nifty500list.csv` caps sector coverage at
   ~500 of ~2,290 names. Is a ~22 %-covered sector map worth shipping, or does a
   partial map do more harm than none (a sector-RS overlay that silently fails open for
   78 % of the universe)? What free source would do better?
3. **Q3 — Universe size.** Given §8's table and §9's history, what do you recommend, and
   **what evidence would change your mind**? Answers of the form "top N by liquidity"
   must engage with §9/1.
4. **Q4 — `is_active` split (U6).** Correct architecture, or unnecessary complexity
   mid-flight? Is there a cheaper way to guarantee that a selection error can never
   again stop data ingestion?
5. **Q5 — Ordering.** I have CAS restart at P3 (U10) but it is the only item losing
   data permanently every day it waits. Should it jump to P0 alongside U1?
6. **Q6 — What is missing?** The failure mode of this document is an unlisted consumer
   of the stock master that stays broken after U1–U3. §4 lists seven; what is the
   eighth?

---

## Appendix A — Reproducing every number here

All measurements are read-only `SELECT`s against `trading_platform` on 2026-09-12, plus
three live HTTP fetches of public NSE CSVs (`EQUITY_L.csv`, `ind_nifty500list.csv`, the
daily indices CSV via `app.services.vix_service.download_indices_csv`). No script in
this document has been run against the database in write mode.

⚠ Per the project's own convention, note what is **[ASSUMED]** rather than measured:
the liquidity tiers in §8 use a trailing-120-day window that ends 09-04 for the
wrongly-inactive names, so they understate those names' recent turnover. Everything else
in PART I is a direct count.
