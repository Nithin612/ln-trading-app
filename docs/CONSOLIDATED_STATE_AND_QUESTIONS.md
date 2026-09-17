# Consolidated state — what is DONE, what is PENDING, and what we are asking

**Combines:** `docs/UNIVERSE_REBUILD_PLAN.md` (3,698 lines, 5 review rounds, the live
infrastructure thread) and `docs/SYSTEM_REVIEW_FOR_QUANT.md` (1,088 lines, the standalone
strategy review) — plus their companions `POSITIONAL_REVIEW_FOR_QUANT.md`,
`quant-panel-adjudication-2026-09-10.md` and `BUILD_QUEUE.md` where they carry the verdict.

**Written:** 2026-09-17 · branch `feature/pre-cycle2-hardening` · **209 commits ahead of
`origin/main`, nothing pushed** `[measured]`.

**Audience:** the next session, and the external reviewers (ChatGPT · Claude · Gemini ·
DeepSeek · Kimi · Perplexity) who have now run five rounds on the universe thread and one
ten-round panel on the strategy thread.

**Not canonical.** Status lives in the top block of `docs/PHASES.md`. This document exists
because the two source docs answer *different halves of one question* — "is the machine
sound?" and "does the machine have an edge?" — and neither one alone tells you what is left.

## Convention for every number below

- `[measured 09-17]` — I ran the query today against the dev DB, read-only.
- `[code]` — read from the file cited, today.
- `[cited]` — taken from a dated report or commit; the date is given because the data behind
  several of them no longer exists (dev DB destroyed 2026-09-07).
- ⚠ A claim with no tag is an opinion. There should be very few.

---

# PART 0 — THE TWO DOCUMENTS' OWN STANDING (read this first)

Both source documents are **behind the code**, in opposite ways. Working rule W1 says the
executable content wins and the doc gets fixed in the same change; this part is that fix,
pointing at the specific lines.

| Document | Last updated | Standing today |
|---|---|---|
| `UNIVERSE_REBUILD_PLAN.md` | round-5 adjudication, 2026-09-14 (PART XXII, §72–§78) | **3 days and 9 commits behind.** Its §77 queue lists V4–V8, U8 and A10 as open; **all of them shipped 09-15 → 09-17.** Everything through §78 is accurate as history. |
| `SYSTEM_REVIEW_FOR_QUANT.md` | generated 2026-09-10 | **Its §2 data-plane table is stale in ALL SEVEN rows** `[measured 09-17]`, and two of its four §13 Tier-3 items are now DONE. Its §3–§12 mechanism findings and §11.3 verdict table are **unaffected** — nothing in the universe work touched the scorer. |

⭐ **The important consequence:** a reviewer reading `SYSTEM_REVIEW_FOR_QUANT.md` today will
conclude that index history, VIX history and intraday bars are missing and that several
hypotheses are untestable. **They are no longer missing.** The blocker moved; the verdicts
did not.

---

# PART 1 — MEASURED STATE, 2026-09-17

One table. Everything else in this document refers back to it.

| Table / fact | `SYSTEM_REVIEW` said (2026-09-10) | **Measured 2026-09-17** | Read |
|---|---|---|---|
| `stocks` | 3,392 · **1,322 active** | **3,395 · 2,299 active** | ✅ repaired (D2′b) |
| …`sector` populated | 500 | **500** | ⛔ unchanged — U7 never ran |
| …`is_nifty50` active | 50 (of which 5 active) | **50 active** | ✅ repaired |
| …`is_fno` active | 212 | **210 active** | ✅ |
| …`ca_flagged_at` | — | **7** (5 of them active) | ⚠ has a clearing path now |
| `ohlcv_1d` | 2,080,305 bars → 2026-09-09 | **2,095,287 bars · 1,100 sessions · 2019-10-01 → 2026-09-16** | ✅ ingesting |
| `ohlcv_5m` | **empty** | **12,625,648 rows · 796 sessions · 2023-07-03 → 2026-09-17** | ✅ **backfilled** |
| `ohlcv_15m` | **empty** | **4,206,475 rows · 796 sessions** | ✅ **backfilled** |
| `ohlcv_1h` | **empty** | **48,065 rows · 3 sessions · 2026-09-15 → 09-17** | ⚠ live-only; backfill path exists, **not run** |
| …intraday breadth | — | **~210 names/session before 09-15; 2,299 from 09-15** | ⚠ the history is a 210-name cohort, not the universe |
| `index_ohlcv_1d` | 48 rows | **21,357 rows · 27 indices · 791 sessions** | ✅ **U8** |
| `indices` registered | 3 | **27** (of 166 in the source CSV; 139 deliberately excluded) | ✅ |
| `india_vix_daily` | 16 | **791** | ✅ |
| `cas_daily` | 43 rows / 1 session | **716 rows / 5 sessions · 2026-09-10 → 09-17** | ⚠ accruing again, cannot be back-filled |
| `fii_dii_daily` | — | **10 rows / 5 sessions of ~790** | ⛔ **unrecoverable by source** |
| `signals` | 30 | **48 · 22 active · 0 shadow** | — |
| `positions` | **0** | **4, all open, all opened 2026-09-16** | ⚠ the trading record still starts from zero |
| `orders` / `signal_outcomes` | 0 / 0 | **4 / 45** | — |
| `ledger_entries` | — | **0 — and no production writer exists** `[code]` | ⛔ **see §3.2** |
| `strategy_profiles` | — | **0** | ⛔ **style engines structurally dead** |
| `categories` / `stock_categories` | — | **0 / 0**, both consumed | ⛔ starved, not in the alarm registry |
| `watchlists` / `saved_screens` / `journal_entries` | — | 0 / 0 / 0 | ⚠ empty-because-unused, not starved |
| `kite_instruments` | 0 (pre-U1) | **58,959** | ✅ U1 |
| `universe_snapshot` | — | **9,196 rows · 4 evaluations · latest 2026-09-17** | ✅ D2′a/b |
| `universe_rule_inputs` | — | **2 days · 2026-09-16 → 09-17** | ✅ §73, recording in production |
| `symbol_history` | — | **3,395** (0 renames — correct and waiting) | ✅ D1′ |
| `ca_flag_events` | — | **7** (backfilled) | ✅ §77 P1 |
| alembic head | — | **`c3d4e5f6a7b8`** (dev at head) | ✅ |

**Processes** `[measured 09-17]`: celery worker+beat **restarted today 08:12** (so it holds
U4′'s 13:40 UTC beat, `record_inputs`, `universe_health` and the V6/V8 beats); uvicorn from
09-15 08:15; the live tick worker ran the 09-17 session (2,299 names of 5m bars) and is not
running post-close, which is expected.

**Gate modes, read out of the live settings object** `[measured 09-17]`:
`entry_diversity` **active** · `sl_atr` · `regime` · `rr` · `circuit` · `chase` · `liquidity`
· `market_regime` · `sector_rs` all **shadow** · `heat_cap` and `position_count_cap` **off**.
Unchanged from the last recorded state — **nothing was flipped by the data restoration**,
which is §9/4's rule working as intended.

---

# PART 2 — DONE, AND AGREED

Inclusion test, applied strictly: **(a)** it is in the code or the data today, **(b)** at
least one external reviewer independently reached the same conclusion or named the query that
settled it, and **(c)** there is a number.

## 2.1 Backend — the data plane and its ownership

| # | Item | What was agreed, and by whom | The proof |
|---|---|---|---|
| 1 | **The universe outage is repaired** (D2′a shadow rule → D2′b apply) | Every round converged on "derive, don't repair" once §25a showed all 3,392 rows were created 2026-09-07 and there was nothing to restore | active **1,322 → 2,299**; Nifty-50 constituents active **5 → 50**; the 152 deactivated were **139 `BE`-series + 13 junk** — reviewed per name before flipping |
| 2 | **`is_active` has ONE writer, enforced by a database trigger** | Unanimous: a flag with three writers and no owner is the root cause | `app.universe_writer` + `SET LOCAL`; `deactivate_dead_stocks.py` retired **with its reversal SQL removed** (it joined on ids reassigned 09-07) |
| 3 | **…and migrations do not bypass it** | DeepSeek W1 asked the question; nobody knew the answer | `universe_writer_probe.py`: plain `UPDATE` **REFUSED**; `session_replication_role='replica'` **did** bypass ⇒ migration `b0c1d2e3f4a5` sets `ENABLE ALWAYS`, re-probed → refused |
| 4 | **Ingestion stopped consulting a trading flag (D3)** | Three rounds argued storage-vs-trading; **the data flow decided it** | `eod_catchup:102` calls the default path ⇒ the old code would have written **1,166 of 2,637** names and dropped **1,471 every day**. U3's repair was not durable |
| 5 | **Subscription = universe ∪ held names (U17)** | Kimi's A4 named the state; the trace found the money path | a held name leaving the universe lost its ticks and the monitor skipped it **permanently**, SL/TP unwatched |
| 6 | **The rule's INPUTS are snapshotted, not hashed (§73)** | **Five of six sources independently**, against my own written spec | `kite_instruments` is upserted in place ("57595 upserted, 0 stale swept") ⇒ yesterday's state is already gone. Now `universe_rule_inputs`: raw gzipped CSV + parsed sets, **recorded BEFORE the decision** |
| 7 | **The collapse rail is two-sided (§74)** | Claude and Kimi converged in one round | growth past `live_universe_max_count` (3,000) makes `universe_guard` refuse the **whole** subscription ⇒ every open position loses its feed at once. Headroom **2,291 of 3,000** |
| 8 | **The download refuses a 200 OK that is not the file (A10)** | Queued as "correct by accident of `raise_for_status`" | measured: **4 of 7** failure bodies parsed to an empty set and reported success |
| 9 | **Index + VIX restored (U8)** | §64/2 flagged the CSV already carried them | `indices` **3 → 27**, `index_ohlcv_1d` **21,357 bars**, VIX **791 sessions**; `market_regime` returns a real verdict (200 closes + VIX 13.17) |
| 10 | **Intraday history restored** | "accrues only in real time" was imprecise — Kite serves deep intraday history | `ohlcv_5m` **12.6M rows**, `ohlcv_15m` **4.2M**, both **2023-07-03 → today**, the same clean block as `ohlcv_1d` |
| 11 | **CAS accrual restarted** | §13/Q5 — the only item losing data permanently every day it waits | `cas_daily` **43 → 716 rows / 5 sessions** |

## 2.2 Backend — the instruments (alarms that assert the right thing)

⭐ **One shape recurred five times and is now the project's most reliable review question:
*is this instrument asserting the thing it is named after?*** In five of five cases it was not.

| # | Instrument | What it used to assert | What it asserts now | Number |
|---|---|---|---|---|
| 12 | **U4′ feed coverage** | recency (`max(time)`) — read ✅ straight through the 09-07 outage | coverage: names today vs a **30-session** median, floor 0.90 | worst benign shortfall **8.17%** over 1,098 sessions, **0 firings**; a 5-session median goes silent on session **4** |
| 13 | **U4″ segment coverage** | — (U4′ is unweighted: ~264 names must vanish) | Nifty-50 · F&O · **names with an open position**, each exact | both segments price **100.0%** every session over 20 — min = median = max ⇒ **any absence is the alarm** |
| 14 | **Session completeness** | nothing — a feed at 16.7% read GREEN on all four alarms | how many of the sessions we should have, do we have | FII/DII **5 of 30 (16.7%)** ⛔ · VIX **30/30** ✅ |
| 15 | **`universe_health`** | that the rule was **evaluated** | evaluation **and apply** (`apply_diverged`) | a refused apply left the snapshot current while `is_active` stayed frozen — "✅ Universe current" over a frozen universe |
| 16 | **V8 report heartbeat** | — | reports present vs the trading calendar | **26 of 30 sessions since 08-01** — four missing, unnoticed, and silence is indistinguishable from a quiet day |
| 17 | **V6 starvation + wiring lint** | — | tables consumed-but-empty; frontend API functions never called | found `strategy_profiles` **empty at head** and a third unwired client function (`watchlistsApi.rename`) |

## 2.3 Frontend — V1 … V8, all shipped

| # | Item | The defect it answered | Evidence |
|---|---|---|---|
| 18 | **V1 scan-scope funnel**, five rungs | a four-rung funnel **manufactures a false attribution** — it forces the whole drop onto the gate (Claude's reframing; DeepSeek and Kimi from the other side) | ⭐ Claude named the query: *"does the live scan path carry its own bar-count gate?"* → `signal_service.py:217` `len(candles) < 50` ⇒ **184 of 2,286 names (8.0%) were being blamed on the confluence gate**. Live: `3,395 → 2,291 → 2,286 → 2,102 → 0` |
| 19 | **V2 price provenance** | the fallback chain is **three** deep, not two, and all three rendered identically | live tick → last 1m close → previous daily close; `stranded` is a **different condition**, not worse staleness |
| 20 | **V3 hold-only** | after D2′b a held name can leave the universe overnight and **nothing stopped you buying more** | shipped as a `Restriction` (`always_on`) ⇒ order-path 409 + `⊘ Blocked` on all five Buy surfaces, **zero new UI** |
| 21 | **V4 search answers absence** | an absence is not askable anywhere else | **1,104 of 3,395 stocks were invisible to search**; excluded names now return ranked below, with the reason and its as-of date |
| 22 | **V5 eligibility panel** | three independent reasons a stock never produces a signal; only one was visible | measured: **5 of 7 quarantined names are ACTIVE** — tradeable on every surface, silently dropped from every suggestion |
| 23 | **V7 CA quarantine queue** | A9 refused the UI until a clearer existed; the mechanism shipped first | the dialog states that clearing **adjusts nothing**, and shows prior-clear counts |
| 24 | **The contrast ratchet** | `tokens.css` recorded contrast in prose comments — that convention failed three times | **8 distinct token pairs below AA, 16 theme instances**, asserted exactly; the list can only shrink |

⭐ **Three of the four ui-reviewer rounds returned FAIL** (13, 21 and 9 findings) on work that
had already passed its own green suite — including **a state rendered backwards in the exact
case the panel exists to explain** (a quarantined stock read "CA quarantine ⊘ no"). The
standing lesson is unchanged and now has four instances: *the tests asserted what was
INTENDED, not what the code did.*

## 2.4 Research — verdicts that are settled and should not be re-litigated

These are `SYSTEM_REVIEW` §11.3 plus the B-queue. **Nothing in the data restoration changes
any of them** — they are statements about the scorer, which was not touched.

| Verdict | Number |
|---|---|
| **The ranker is dead** (E2) | unconditional IC h=5d **−0.0070, 90% [−0.0259, +0.0119]**, upper bound below the measured break-even **0.0310**; `confidence_pct` — what the UI sorts by — flatter still (**+0.0024**) |
| **The ≥70% gate is unproven in BOTH directions** (E2 3b) | point estimate −0.3150% but the upper bound **+0.388%** clears break-even ⇒ INCONCLUSIVE, deliberately not rounded to null |
| **Gating is closed as a programme** | 8 shadow gates, 2 promotions both refuted, best survivor `sl_atr` at **t = 0.41 vs a 3.6 hurdle** |
| **The promotion bar is t ≈ 3.6 and is FLAT IN n** | validated by negative control: 1.10% of best-of-20 zero-edge selections clear; 80% power at a true per-trade Sharpe 0.52 |
| **Exit geometry is not the lever** (D5) | no constant-R:R target 1.0–3.0R beats the frozen absolute-% target on 1,152 signals; every paired ΔR negative, abs(t) ≤ 0.65 |
| **The queued generation lever is refuted** (D1/RVOL) | injecting a graded RVOL factor: **−0.291R at t = −2.91** |
| **Stop-width is a denominator artifact** | closed three times; swing **R −0.386 → raw% −0.262 → excess vs matched basket +0.069** |
| **Positional closes like swing** (E1) | **R −0.4879 → raw% −0.7870 → excess −0.1909 (t −0.29)** — identical shape |
| **Hold-period breadth lever: resolved against** (B7) | MFE over abs(MAE) **0.83 / 1.12**, hazard curve **flat** 0.559 → 0.489 over days 0–5 |
| **88% of the BUY book's gross loss is tape, not alpha** | raw −0.1877% = tape −0.1659% + alpha −0.0218% |
| **Three factors never score** | `DOW_TREND` (weight **20**, the heaviest), `MARUBOZU`, `FII_DII_FLOW` — 0 of 487 panels |

---

# PART 3 — PENDING

Ordered by **what it blocks**, not by size. Every row carries the state measured today.

## 3.1 ⛔ Blocked on the user (nothing proceeds without a decision)

| # | Item | State today | What is actually being asked |
|---|---|---|---|
| U-1 | **The push** | **209 commits ahead of `origin/main`**, no upstream configured `[measured]` | W4 reserves push to the user. Everything in PART 2 exists on one local branch on one machine |
| U-2 | **The palette AA defect** | 8 token pairs / 16 theme instances recorded; **plus two NOT covered by the ratchet** — `--color-accent` on `--color-surface-2` at **2.88 in slate (the default theme)** and `--color-text-muted` at **3.52 slate / 2.34 daybreak** `[code]` | Changing red/green moves **every P&L figure in five themes**. The one-line fixes are measured and ready: dark `--color-loss`/`--color-bear` red-500 → **red-400 `#f87171`** (clears all: 5.84 / 5.38 / 5.68 / 6.66); daybreak `--color-bear` → `#b91c1c`; daybreak green needs a darker value |
| U-3 | **Backfill `ohlcv_1h`** | 3 sessions `[measured]`; the path shipped 09-17 but was **not run** | ~2,300 names × 3 years of REST pulls at ~3 req/s. ⚠ And see §3.4/D-6 — the two producers of this table **disagree by one bar per session, permanently** |
| U-4 | **Universe curation (§8/§13 Q3)** | the rule is `EQ_LISTED ∧ KITE_TRADABLE` ⇒ 2,291 names | Never decided. ⭐ And §75 corrected the evidence for it: **`KITE_TRADABLE` excludes exactly ONE name** ⇒ it is ~99.96% a single-source rule, so "two sources agree" measures consistency, not correctness |
| U-5 | **Cycle-2 start** | caps built and `off`; clock not started | Every dependency in `phase-07-live-trading-plan.md` except Phase 7.1–7.4 is now met |

## 3.2 Backend — open, and three of them are live defects

| # | Item | State `[measured 09-17]` | Severity |
|---|---|---|---|
| B-1 | ⛔ **`strategy_profiles` is empty at head** | **0 rows.** Seeded by migration `o1p2q3r4s5t6`; the 09-07 rebuild restored the schema with alembic already marked applied, so the seed **never re-ran and cannot** — `alembic upgrade` is a no-op on a revision it thinks is done | **HIGH.** Four production call sites read it (`profiles/pipeline`, `broker/provisional`, `api/v1/suggestions`, `daily_report`) ⇒ **the style engines have been structurally unable to produce anything for ten days, at head, with a green suite.** V6 now *detects* it; nothing *fixes* it |
| B-2 | ⛔ **The append-only ledger has no production caller** | `ledger_entries` **0 rows**; `app/services/ledger.py` is imported by **`tests/test_ledger.py` only** `[code]` | **HIGH by consequence.** The external panel called this "the highest-priority engineering item on nobody's tier list" — the trade record that survives the next DB loss. It is built, migrated, tested and **wired to nothing.** ⚠ V6's wiring lint is **frontend-only**, so it is structurally unable to see this |
| B-3 | ⛔ **`categories` / `stock_categories` starved** | **0 / 0**, consumed by `universe_service` (`kind="category"`), `screener/compiler.py`, `cas_tasks.py` and an API `[cited §25g]` | **MEDIUM.** ⚠ And they are **not in the starvation registry**, which today lists only `kite_instruments`, `stocks`, `strategy_profiles` `[code]` — the alarm built for this class of defect does not cover the two tables its own adjudication named |
| B-4 | ⛔ **FII/DII: 5 sessions of ~790, and a frozen consumer states a positive claim from no data** | 10 rows `[measured]` | `get_market_flow_5d` returns `Decimal("0")` when no rows exist, and `app/analysis/structure/institutional.py` (**FROZEN**) turns `(0,0)` into score 0.0 with *"FII/DII flows neutral"*. Contained — a 0.0 score is excluded from the confidence denominator — so it is a **reporting** lie, not a scoring one. Fixing the consumer needs sign-off + an §8 regression |
| B-5 | **U7 — sector map** | **500 of 3,395** `[measured]`, unchanged since the rebuild | Blocks U8 **step 4**: 16 sector indices are ingested daily and **read by nothing**, because `benchmark_symbol_for` still picks on two membership flags and otherwise returns NIFTY50 |
| B-6 | **U9 — membership flags / point-in-time constituents** | `is_nifty50` etc. self-heal on reseed; `index_constituents` cannot answer "was this a Nifty-50 name on date X" | Deferred with reasons (§51). It is the same lesson as A38's mandatory `as_of` |
| B-7 | **U5 — the recovery order** | `RUNBOOK.md` has a "Quick recovery" section; **no disaster-recovery ordering section** `[code]` | The composition that caused 09-07 is still invisible in both files. Cheap |
| B-8 | **D1′ remainder** | `uq_stocks_symbol_exchange` deliberately **not** dropped; 14 queries assume one row per symbol | ⛔ The hazard's rate is **unmeasurable retrospectively** — the merge overwrites its own evidence. Parked with that stated |
| B-9 | **D4b — per-event corporate actions** | 7 flagged / 7 events `[measured]`; the backward pass was never run | §32 projected **1,768 of 3,395** stocks flagged, 386 active ⇒ rescoped as a review queue. A9's verdict stands: fix the mechanism before widening it |
| B-10 | **U0.5′ off-box backup** | backups run `0 11 * * 1-5` to a **local** path | One machine, one disk. The 09-07 loss had no PITR and no backup |
| B-11 | **D0 pin refresh cadence** | `stock_identity.csv` pinned at 3,395 rows | No cadence decided for refreshing it |
| B-12 | **Freshness assertion on the rule's inputs** (§77 P1, last sub-item) | `universe_health` asserts inputs were **captured**; A10 asserts the source is **plausible** | ⚠ Between them the substance is covered; "freshness" as specified (a U15-shaped median check) was never built. **Verify before ticking it** |

## 3.3 Frontend — open

| # | Item | State | Note |
|---|---|---|---|
| F-1 | **`StockDetailPage` is not compliant** | raw `<button>` ×2, **27 raw table elements**, `toFixed`, `toLocaleString`, `--color-text-muted` in 17 places, **an LTP painted `--color-bull` regardless of direction** `[cited, ui-reviewer 09-16]` | The last one is a money-correctness bug, not a style nit: a falling price renders green |
| F-2 | **`UsersPage.CreateUserModal`** | hand-rolled: no Portal, no `role="dialog"`, no Escape | V7 followed this precedent before being forced onto the `Dialog` primitive. ⚠ "Fix the second instance, leave the first" is exactly how the five-Buy-surface problem happened |
| F-3 | **Three unwired API client functions** | `filingsApi.getGuard` · `strategyApi.getRun` · `watchlistsApi.rename` `[code]` | Recorded as named debts in a shrink-only ratchet. `rename` is the purest case: the endpoint and client exist, the UI offers no way to rename, **and the test suite mocks it** |
| F-4 | **Exclusion reasons rendered as-of the last APPLIED snapshot** | reasons are justified from recorded inputs, but a **refused apply** would put a current-looking reason on screen (Kimi §4.2) | Small, and it is the display half of the `apply_diverged` fix already made on the backend |
| F-5 | **The thin ops page (A8)** | `feed_health` / `worker_health` / `calendar_health` / `universe_health` / `report_health` exist as services with **no endpoint** | ⚠ A8's own rule: *if we find ourselves designing new metrics for it, stop.* This is a rendering job, not a monitoring project |
| F-6 | **Decision Trace / Replay (ChatGPT)** | ⏸ parked, **now UNBLOCKED** by §73 | The stated blocker was "the rule's inputs are not snapshotted". They are, as of 09-16 `[measured: 2 days recorded]` |
| F-7 | Universe Explorer · What Changed · Evidence drawer · Command palette · Cockpit · Rule Workbench · AI assistant layer | ⏸ parked, unchanged | ⭐ ChatGPT argued against its own list: *"don't start UI implementation yet"*, and its warning against a Bloomberg clone for a solo operator in evenings is the most valuable paragraph in that response |

## 3.4 Research — the only tier that can change expectancy

`SYSTEM_REVIEW` §13, with today's state written against each one.

| # | Lever | State 09-17 | What changed since 09-10 |
|---|---|---|---|
| R-1 | **Restore trend structure to the scorer** (Tier-1 #1) | **NOT RUN** | The method is settled — the read-only injection that refuted RVOL, no frozen edit needed to get the answer. ⚠ Guarded prior: injection can **dilute** through the confidence normalisation. This is the only item on the list that is a **defect** (a weight-20 factor unreachable by construction) rather than a hypothesis |
| R-2 | **Minervini as a universe filter** (Tier-1 #2) | **NOT RUN** | 0 of 91 entries pass ⇒ disjoint from our selection, so it cannot be tested on this book. Needs a universe-level regeneration |
| R-3 | **12-month price momentum** (Tier-1 #3) | **NOT RUN** | The single untested thread from the reading study. ⚠ It surfaced as the *control that killed* the overhead-supply effect, so the evidence for it is weaker than it looks |
| R-4 | **CAS overnight reversal to ≥30 sessions** (Tier-1 #4) | **accruing: 5 of 30** `[measured]` | ✅ Capture restarted. ~5 weeks of wall-clock left. Best odds on the list — and it is a **different strategy**, not a fix to this one |
| R-5 | **Opening-range / VWAP / intraday timing** | ⭐ **NEWLY TESTABLE** | `SYSTEM_REVIEW` §13 Tier-3 #9 calls these blocked. They are not: **3 years of 5m/15m bars exist for ~210 liquid names** `[measured]`. ⚠ The history is a **210-name cohort**, so any result generalises to F&O/Nifty-50 names only |
| R-6 | **Limit orders** (Tier-2 #5) | Phase 7 | Attacks the only term measured at t ≈ −10 to −13 |
| R-7 | **Cost-relative stop rule** (Tier-2 #6) | **NOT TESTED** | ⚠ It is an identity about arithmetic — and the R:R reversal is the standing warning that **an identity still rests on an empirical premise** |
| R-8 | **Re-run the two studies asserting a false CA-clean window** (Tier-3 #11) | **NOT RUN** | `tp_geometry_study.py` (closed D5) and `rvol_factor_study.py` (closed D1). Both conclusions may well stand — **they are currently uncitable**, and both are load-bearing closures |
| R-9 | **The `_simulate_trade` gap-through-stop defect** | **NOT FIXED** (frozen engine) | Books a gap-through-stop fill as ~**+1R**. Live is immune. **Every study built on it inherits it**, including the 1,975-trade headline; magnitude there unmeasured |
| R-10 | **Directional entry zone** (Tier-3 #8) | **NOT BUILT** — verified in code today | `live_levels._signal_levels` still emits a symmetric `zone` at entry ± `live_entry_zone_pct` (0.5%) while SL/TP touches **are** direction-aware in the same function `[code]`. A correctness fix to an alert, explicitly not a P&L claim |
| R-11 | **Flip the heat + position caps** (Tier-4) | built, `off` `[measured]` | Flips at the cycle-2 reset. Buys survivability, not profitability — and that distinction must be stated whenever it is reported |

## 3.5 Parked, with the unblocking condition (unchanged unless noted)

| Item | Unblocks when |
|---|---|
| 5-table institutional security master | a measured need the current model cannot express |
| Correlation-derived sector taxonomy | clustering shows temporal stability on a 60/40 session split **and** sector-RS demonstrates it needs coverage beyond the published map |
| `ingestion_runs` lineage table | ⭐ genuinely good, under-weighted at the time; cross-cutting |
| `listing_status` on `symbol_history` | a source that publishes suspension — `EQUITY_L` does not |
| Full bitemporal model | a backtest requirement effective-dated rows cannot serve |
| Separate DEV/TEST/PAPER/PROD databases | a second near-miss, or live trading |
| **Decision Trace / Replay** | ✅ **UNBLOCKED 2026-09-16** by §73 |
| **D2** (R2 build-or-drop) | parked to **cycle-2 end** — Claude raises it via the PHASES review calendar |

---

# PART 4 — SOLUTIONS I HAVE NOW

Ordered. Each is scoped by what settles it, because "more review" is not a solution and the
last two rounds measured the marginal value of review breadth as **4 of 37** and **4 of 29**.

## 4.1 Ship this week, no decision needed (all correctness, no P&L claim)

1. ⭐ **Wire the ledger (B-2).** It is the one artifact that makes the next DB loss survivable,
   and it is finished. Proposal: write on every paper fill and every position close, plus a
   nightly off-box export. **Then extend the V6 wiring lint to the backend**, or this class of
   defect stays invisible on the side of the codebase where it costs the most.
2. ⭐ **Re-seed `strategy_profiles` (B-1) with an idempotent script, not a migration.** The
   lesson is structural and should be written down where it will be read: **a migration that
   seeds reference data is invisible to every check we own once it is marked applied.** Any
   reference data that must survive a rebuild belongs in a re-runnable seed script that the
   starvation alarm can point at.
3. **Add `categories`, `stock_categories` and `ledger_entries` to the starvation registry
   (B-3)** with their "what fills this / what consumes this" columns.
4. **Make the entry zone directional (R-10).** The `cross_up`/`cross_down` machinery is
   already in that file for PDH/PDL. It is a correctness fix to an alert and must be shipped
   and reported as exactly that.
5. **U5's runbook section (B-7)** — the ordering that 09-07 had to rediscover:
   `seed_stocks` → `kite_instruments` sync → bhavcopy backfill → universe rule → index backfill.

## 4.2 Close two items that the code has already settled (W1)

6. ⭐ **Close U6 (`is_active` split) as a schema item.** Its stated acceptance criterion —
   *"flipping every `is_active` to false must not reduce bar ingestion"* — **is met today
   without the column**: D3 removed `is_active` from the ingestion path, `resolve_universe`
   keeps it for selection, and `tests/test_ohlcv_history_backfill.py` pins an inactive stock
   being ingested `[code]`. The plan still lists U6 as P1 and as "the item I am least sure
   about". The cheaper alternative won on its own merits — **record that and stop carrying it.**
7. **Retire `SYSTEM_REVIEW` §13 Tier-3 #9 and #10 as done**, and replace #9 with its successor
   question: *the intraday history is a 210-name cohort — is that the right cohort?*

## 4.3 The two research moves I would actually make

8. ⭐⭐ **Run R-1 (trend-structure injection) before anything else in Tier 1.** It is the only
   item that is a *defect* rather than a *hypothesis*: a weight-20 factor described in the spec
   as "the macro context" cannot fire on the timeframe it trades, the swing engine therefore
   carries no trend input, and this is independently corroborated twice (Minervini 0/91; beta
   +0.92, alpha ≈ 0). It costs one read-only corpus pass, needs no frozen edit and no sign-off
   to get the **answer**. ⚠ Only shipping it needs a spec decision — which is §5/Q-3 below.
9. **Re-run R-8's two studies before citing either again.** They close D5 and D1, which is to
   say they close *both* named profitability levers. Two closures resting on a filter that was
   later proven false is not a state to leave standing. Cost: two script re-runs with the CA
   filter, `newey_west_t` and `WINSOR_R` applied — all three already exist.

## 4.4 What I would NOT do

- **Not a ninth gate.** Closed as a programme, with the reasoning: the trades carry no edge to
  partition.
- **Not flip `market_regime` or `sector_rs` because the data now exists.** Data availability is
  not evidence. Two gates promoted on arguments were refuted within weeks.
- **Not run the backward CA pass.** It would quarantine **1,768 of 3,395** names, and the
  clearing path is one human decision per name.
- **Not start cycle 2 before Phase 7.1–7.4.** A 45-day rehearsal through the real
  ExecutionEngine is what gives the plumbing 45 days of runtime hours, and v1 Phase 7's four
  defects were all plumbing.
- **Not build the UI cockpit.** ChatGPT's own warning, and A8's scale rule.

---

# PART 5 — QUESTIONS FOR THE PANEL (round 6)

⭐ **The rule this round inherits, and it is the most productive thing five rounds produced:
name the QUERY, not the concern.** The two best points of round 5 were both a reviewer naming
one query — *"does the live scan path carry its own bar-count gate?"* (it does: 184 names) and
*"which single `EQUITY_L` name fails `KITE_TRADABLE`?"* (exactly one, which demolished a claim
I had called the strongest evidence in the document). Both took one query; both changed
something. A point that cannot be settled by a query, a measurement, or a line of our code is
worth less here than it looks.

## 5.1 Backend / data — three questions

**Q-1 [BLOCKING for the ledger]** — *B-2: the append-only ledger is built, migrated, tested and
called by nothing.* We propose writing on every paper fill and close plus a nightly off-box
export. **What is the smallest set of events that makes a trade ledger actually sufficient for
reconstruction after a total loss?** Concretely: is a fill/close pair enough, or must the
ledger also carry the *decision* (signal id, gate verdicts, the inputs snapshot id) to be worth
its existence? ⚠ We have the inputs snapshot now (§73), so the expensive half is already paid.

**Q-2** — *B-1 names a class, not an incident:* **a migration that seeds reference data is
invisible to every check we own once alembic marks it applied.** `strategy_profiles` has been
empty at head for ten days with a green suite and four live consumers. What is the standard
answer — idempotent seed scripts run separately from schema migration, a `data_version` table,
seed-on-startup with a checksum, or something else? **Name the failure mode of the option you
pick**, because ours failed in the one way we did not check for.

**Q-3** — *B-5/U7, and it is the same question §13/Q2 asked and nobody has answered with a
source:* sector coverage is **500 of 3,395** and has not moved. 16 sector indices are now
ingested daily and **read by nothing** because `benchmark_symbol_for` picks on two membership
flags. Is a ~22%-covered sector map worth shipping — given that `sector_rs` would then silently
fail open for 78% of the universe — or is NULL-honest correct until a fuller free source
exists? ⭐ **The query that would settle it:** on the 500 names we *can* classify, does a
sector-relative benchmark separate outcomes better than NIFTY50 at all? If it does not, the
coverage question is moot and U7 should be dropped rather than queued.

## 5.2 Frontend / UX — two questions

**Q-4** — *U-2, the palette.* Eight token pairs are below AA on copy that carries money, and
the fix is measured and one line each — but it changes the appearance of every P&L figure in
five themes. ⚠ Two further pairs (`--color-accent` 2.88 in the **default** theme,
`--color-text-muted` 2.34 in daybreak) are **outside the ratchet's stated scope** because they
are assembled in components rather than listed. **Is a contrast ratchet that can only see pairs
someone thought to list the right instrument at all**, or should it enumerate *rendered*
combinations? The second is much more work and we would rather be told it is necessary than
discover it.

**Q-5** — *F-6: Decision Trace / Replay is now unblocked.* We can reconstruct, for any past
day we have recorded, exactly why a name was in or out of the universe. **Is that worth
building for a solo operator, or is `scripts/universe_snapshot.py --diff` the right size of
answer?** ⚠ Our own prior is the second — a GUI for a once-a-quarter rule change is inverted
cost — but the input snapshots were justified partly *on* this, so we are asking against our
own preference.

## 5.3 Research — four questions, two of them carried forward unanswered

**Q-6 [the one that matters most]** — *R-1 and `SYSTEM_REVIEW` §14/2, still unanswered.* The
weight-20 `DOW_TREND` factor cannot fire on the daily timeframe by construction
(`lookback=20`, `swing_n=5` admits one pivot per side; the function needs two highs **and**
two lows). **Is restoring it a bug fix — restore the specified intent — or a new hypothesis
that must clear t ≈ 3.6?** ⭐ The governance answer changes the required evidence by an order
of magnitude, and it is the *only* place in the programme where that question has teeth,
because it is the only item that is a defect rather than a proposal.

**Q-7** — *`SYSTEM_REVIEW` §14/1, unanswered.* The confidence denominator normalises by the
weight of factors that **scored**, so abstention is free and three agreeing oscillators are
arithmetically indistinguishable from eleven agreeing inputs. **Is abstention-free defensible,
or should a non-scoring factor count as a zero in the denominator?** ⚠ The adjacent
alternative (sub-factors sharing a group budget) was measured once and was much worse; the
specific question has never been tested. E2 has already shown the composite carries no
cross-sectional information — **so is this worth testing at all, or does E2's null subsume it?**

**Q-8** — *R-5, the newly testable one.* Three years of 5m/15m bars exist for **~210 liquid
names**. Every opening-range and intraday-timing hypothesis is now runnable, and one has
already been half-answered against us (the textbook confirmation trigger loses on two
independent samples, cost t ≈ −7 to −9 against benefit t ≤ 0.4). **Given that, what is the
single intraday question worth one pass — and what result would make you drop it?** Name the
estimand before we write the code; the pre-registration convention here is not decorative,
E2's null was pre-registered in a commit before the code and that is the only reason it is
citable.

**Q-9** — *`SYSTEM_REVIEW` §14/5, the strategic one, still unanswered after ten rounds.* Is the
correct next move to keep searching for edge inside this framework, or to treat what has been
built — the honest execution model, the deflated-Sharpe bar, the outcome recorder, the
overlap-corrected statistics, and now a repaired universe with a versioned rule — as
**evaluation infrastructure** and search for the edge elsewhere? ⚠ Answer it against this
number: **at ₹1 lakh, round-trip friction is 22–62 bps plus spread**, the flat ₹15.34 DP charge
alone is **61.6 bps on a ₹3,900 position**, and cost is the only effect in the programme
measured at |t| > 5.

---

# PART 6 — WHAT THIS DOCUMENT DOES NOT DO

- It does not supersede either source document. `UNIVERSE_REBUILD_PLAN.md` remains the forensic
  record of the infrastructure thread; `SYSTEM_REVIEW_FOR_QUANT.md` remains the standalone
  explanation of the strategy for a reader with no exposure to the codebase.
- It does not change any status. `docs/PHASES.md`'s top block is canonical.
- It does not run anything. Every number here is read; nothing was written to the database, no
  gate mode was changed, and the frozen engine was not touched.
