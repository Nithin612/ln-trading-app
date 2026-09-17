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
| `ohlcv_1d` | 2,080,305 bars → 2026-09-09 | **2,095,287 bars · 1,101 sessions · 2019-10-01 → 2026-09-17** ⛔ **with a 922-day hole: 2020-12-23 → 2023-07-03. 2021 and 2022 do not exist** (307 sessions pre-2021 + 794 from 2023-07-03) | ✅ ingesting, ⛔ not contiguous — §7.10/3 |
| `ohlcv_5m` | **empty** | **12,625,648 rows · 796 sessions · 2023-07-03 → 2026-09-17** | ✅ **backfilled** |
| `ohlcv_15m` | **empty** | **4,206,475 rows · 796 sessions** | ✅ **backfilled** |
| `ohlcv_1h` | **empty** | **48,065 rows · 3 sessions · 2026-09-15 → 09-17** | ⚠ live-only; backfill path exists, **not run** |
| …intraday breadth | — | **~210 names/session before 09-15; 2,299 from 09-15** | ⚠ the history is a 210-name cohort, not the universe |
| `index_ohlcv_1d` | 48 rows | **21,384 rows · 27 indices · 792 sessions, 2023-07-03 → 2026-09-17** | ✅ **U8** — ⚠ 3.2 years, not 7 (§7.10/4) |
| `indices` registered | 3 | **27** (of 166 in the source CSV; 139 deliberately excluded) | ✅ |
| `india_vix_daily` | 16 | **792, 2023-07-03 → 2026-09-17** | ✅ — ⚠ same 3.2-year scope |
| `cas_daily` | 43 rows / 1 session | **716 rows / 5 sessions · 2026-09-10 → 09-17** | ⚠ accruing again, cannot be back-filled |
| `fii_dii_daily` | — | **10 rows / 5 sessions of ~790** | ⛔ **unrecoverable by source** |
| `signals` | 30 | **48 · 22 active · 0 shadow** | — |
| `positions` | **0** | **4, all open, opened 2026-09-16 — ⛔⛔ ALL FOUR ARE `SHORT`** (M13) | ⛔ a cash-delivery account cannot hold an overnight short — §7.11/1 |
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
| 9 | **Index + VIX restored (U8)** | §64/2 flagged the CSV already carried them | `indices` **3 → 27**, `index_ohlcv_1d` **21,357 bars**, VIX **792 sessions, all 2023-07-03 → 2026-09-17**; `load_market_regime_context` returns a populated context (200 closes + VIX 13.17) — ⚠ *the function returned a number*, not a validated verdict (§7.10/5) |
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
| R-1 | **Retune the trend factor's parameters** (Tier-1 #1) | **NOT RUN, RECLASSIFIED 2026-09-17** | ⛔ **NOT a defect — M9 refutes "unreachable by construction": it fires (+0.70) at the shipped `lookback=20, swing_n=5`.** True statement is M10: **5 of 19,100 panels = 0.026%**. ⇒ a **parameter proposal** that must clear `t ≈ 3.6`. Method unchanged (read-only injection); guarded prior: injection can **dilute** through the confidence normalisation |
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

8. ⭐⭐ **Run R-1 (trend-structure injection) — RECLASSIFIED.** ⛔ **CORRECTED 2026-09-17 (§7.10/1): it is NOT a defect.** M9 shows it fires at the shipped parameters; M10 measures **0.026%** of real panels. It is a parameter proposal at the `t ≈ 3.6` bar. The observation that motivated it survives — a weight-20 factor described in the spec
   as "the macro context" effectively never fires on the timeframe it trades, the swing engine therefore
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

**Q-6 [ANSWERED BY MEASUREMENT 2026-09-17 — my premise was false]** — I asked whether restoring
`DOW_TREND` was a bug fix or a new hypothesis, on the stated ground that it *cannot* fire by
construction. ⛔ **M9 refutes that: it fires (+0.70) at `lookback=20, swing_n=5`**; M10 measures
**0.026%** of 19,100 real panels. ⇒ **the fork collapses — the code implements the spec
correctly, so changing the parameters is a NEW HYPOTHESIS at `t ≈ 3.6`.** ⭐ The governance answer changes the required evidence by an order
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
number: **at ₹1 lakh, round-trip friction is 22–62 bps plus spread**, **total** round-trip charges are
**61.6 bps on a ₹3,900 position** (the flat ₹15.34 DP charge is **39.3** of them — corrected in
§7.10/2), the floor is **~22 bps at any size**, and cost is the only effect measured at |t| > 5 —
⚠ which §7.8/Q3 correctly notes is partly an artifact of its near-zero variance.

---

# PART 6 — WHAT THIS DOCUMENT DOES NOT DO

- It does not supersede either source document. `UNIVERSE_REBUILD_PLAN.md` remains the forensic
  record of the infrastructure thread; `SYSTEM_REVIEW_FOR_QUANT.md` remains the standalone
  explanation of the strategy for a reader with no exposure to the codebase.
- It does not change any status. `docs/PHASES.md`'s top block is canonical.
- It does not run anything. Every number here is read; nothing was written to the database, no
  gate mode was changed, and the frozen engine was not touched.

---

# PART 7 — THE ROUND-6 PANEL, ANSWERED ONE BY ONE (2026-09-17)

Eight responses came back: **ChatGPT · Gemini · Perplexity · DeepSeek · Grok · Nemotron 3.5
lightning · Claude · Kimi K3.** Each is adjudicated separately below, deliberately **not**
merged into a consensus table — three of the most valuable points in this round were made by
exactly one source, and a merge would have averaged them away.

## §7.0 · How I judged them, and the rule I broke last time

Every verdict below is settled by a query, a code read, or an execution — never by which
reviewers agreed. That matters because **this round refuted two claims that every source
accepted, and both of them were mine.** Reviewer unanimity measured my document's persuasiveness,
not its correctness.

⭐ **I tested my own load-bearing claims first, and two failed.** That is the single most
useful thing in this part; a review round that only audits the reviewers has the burden of proof
backwards.

## §7.1 · The measurement round — everything settled today

Each row is one query, code read, or execution. Sections §7.2–§7.9 cite these by ID.

| ID | Question | Result `[measured 2026-09-17]` |
|---|---|---|
| **M1** | Does `ohlcv_1d` really hold 1,100 sessions over 2019-10→2026-09? | **1,101 distinct sessions** — and the years present are 2019, 2020, **2023, 2024, 2025, 2026**. ⛔ **2021 and 2022 do not exist.** Largest gap: **2020-12-23 → 2023-07-03 = 922 days**. 307 sessions before 2021 + 794 from 2023-07-03. |
| **M2** | What period do the "restored" index and VIX histories actually cover? | `index_ohlcv_1d` **2023-07-03 → 2026-09-17, 792 sessions, 21,384 rows**; `india_vix_daily` **2023-07-03 → 2026-09-17, 792 rows**. **3.2 years, not 7.** |
| **M3** | Is the flat ₹15.34 DP charge 61.6 bps on a ₹3,900 position? | **No. 39.3 bps.** The **total** round trip on ₹3,900 is **₹24.01 = 61.6 bps**. Measured through `fees.roundtrip_charges`: ₹3,900 → 61.6 bps · ₹38,965 → 26.2 · ₹1,00,000 → 23.8 · ₹10,00,000 → **22.4**. DP alone reaches 61.6 bps at a **₹2,490** position. |
| **M4** | Is STT in the cost model? | **Yes** — ₹3.90 per leg on ₹3,900 (0.1% delivery, both legs), alongside stamp duty, exchange txn, SEBI, GST and DP. Full breakdown printed. |
| **M5** | Does `_simulate_trade` book a gap-through-stop as a win? | **Yes, and ONLY at the entry bar.** Executed: signal close 100 / stop 99 / next open 95 ⇒ entry 95, exit **99**, `hit_sl=True`, **+4.211%**. Short mirror **+3.810%**. |
| **M6** | Does it mishandle gaps generally? | **No — the controls pass.** A gap through the stop on a *later* bar exits at the **open** (−5.000%), and an ordinary intrabar stop exits at the stop (−1.000%). The defect is strictly the **fill bar**. |
| **M7** | How often is a trade exposed to M5? | Overnight gap distribution, 183,556 stock-days, top-250 liquid, 2023-07-03→now: gap ≤ **−0.65%** (p10 stop) **9.25%** · ≤ **−2%** **2.08%** · ≤ **−5%** (median stop) **0.34%**. Mean gap **+0.1835%**. |
| **M8** | Is "live is immune" true, and why? | **True, by an explicit rejection.** `paper_broker.place_paper_order` computes the fill, then calls `eligibility.through_stop_reason(side, price=fill_price, stop_loss)` and **raises `PaperOrderError`**. Tests exist: `tests/test_restrictions.py:224-244`, `tests/test_eligibility_preview.py:245,341`. |
| **M9** | Can `DOW_TREND` fire on the daily timeframe? | ⛔⛔ **YES. The "impossible by construction" claim is REFUTED.** A constructed 20-bar daily window with pivots at window indices 5/14 (highs) and 6/13 (lows) returns **+0.70 "Confirmed uptrend"**; the mirror returns **−0.70**. |
| **M10** | Then how often does it fire on real bars? | **5 of 19,100 panels = 0.026%** (2 positive, 3 negative) — 200 liquid names, 2023-07-03→now, through the frozen function. Independently reproduces the prior 3-of-4,511 rarity on a 4× larger sample. |
| **M11** | Does the live funnel still end at 0? | **No — 15.** Today: `3,395 known → 2,299 in universe → 2,291 priced → 2,108 admitted → 15 live signals`; breadth median 2,251. 183 names refused before scoring. |
| **M12** | Is the engine long-only? | **No.** `signals`: **BUY 32 / SELL 18**; swing 40 / positional 10; 23 active / 27 expired. |
| **M13** | What are the four open positions? | ⛔⛔ **All four are `SHORT`**, `mode='paper'`, each carrying a `signal_id`, opened 2026-09-16: 207@₹138.24 · 33@₹855.55 · 72@₹423.55 · 143@₹225.35. |
| **M14** | What is the 210-name intraday cohort? | **Exactly 210 names, 210 of 210 are `is_fno`, 50 are `is_nifty50`.** The cohort *is* the F&O universe. |
| **M15** | Is the archive survivorship-pruned? | **No, not at bar level.** **1,081 inactive stocks carry bars**, and **389 names have no bar since 2025-01-01** — dead names are retained. |
| **M16** | Can we answer "was X in Nifty-50 on date D"? | **No.** `index_constituents`: **89 rows, 3 indices, 0 with `weight_pct`, every `added_on` = 2026-09-07**. |
| **M17** | Does the E2 IC study filter corporate actions? | ⛔ **NO.** `scripts/e2_score_ic.py` skips panels for *window holes* (`skipped_gap`) but carries **no abs(move) > 25% CA screen** — unlike `swing_dependence_probe.py`, which has `CA_JUMP = 0.25` and reports its drop count. |
| **M18** | Does a subscription-ceiling trip kill held names too? | **Yes.** `live_worker` bootstrap: `check_and_record_universe(...)` returning a refusal ⇒ `return EXIT_NO_UNIVERSE` — the worker **refuses to start**, so U17's held-name union never gets subscribed. |
| **M19** | Does the starvation registry cover the named tables? | **No** — it lists `kite_instruments`, `stocks`, `strategy_profiles` only. `categories`/`stock_categories` (**0/0, consumed**) and `ledger_entries` (**0**) are absent. |
| **M20** | Does the trade ledger have a production caller? | **No.** Precise grep for `from app.services.ledger import` / `from app.services import ledger` / `import app.services.ledger` across `app/`, `scripts/`, `tests/` returns exactly one hit: `tests/test_ledger.py:17`. No call site for `record_entry`/`amend_entry`/`chain` anywhere in `app/` or `scripts/`. |

⭐ **M9 + M10 together are the most consequential result of this round**, and §7.10 records what
they cost.

---

## §7.2 · ChatGPT — the most complete taxonomy, and the one statistical point nobody else made

**✅ AGREED, settled by measurement**

| Their finding | Verdict |
|---|---|
| A2 reference-data seeding is not lifecycle-safe | **CONFIRMED** — `strategy_profiles` 0 at head; the seed migration cannot re-run |
| A3 ledger is architecturally incomplete | **CONFIRMED — M20.** One importer, and it is the test |
| A4 backend wiring verification is weaker than frontend | **CONFIRMED** — the lint is frontend-only by construction |
| A5 starvation monitoring does not cover all consumed state | **CONFIRMED — M19** |
| A6 recovery architecture is single-box | **CONFIRMED** — local path, 209 unpushed commits |
| A7 a universe-size guard becomes a systemic outage | **CONFIRMED — M18**, and worse than stated: the worker **refuses to start**, so U17's held-name union is never subscribed at all |
| BKT1 stop-gap fill contaminates research | **CONFIRMED — M5**, with M6/M7 scoping it |
| BKT3 costs may overwhelm the signal | **CONFIRMED — M3**, 61.6 bps round trip at ₹3,900 falling to 22.4 at ₹10L |
| D1 FII/DII incomplete + missing rendered as neutral | **CONFIRMED** |
| D5 1h internally inconsistent | **CONFIRMED** — 6 bars (Kite) vs 7 (worker) |
| D7 a 200 OK is not the file | **CONFIRMED** — 4 of 7 failure bodies parsed to empty and reported success |

⭐ **Q7 — "near-zero t is not equivalence" — is the best statistical point in the round, and it
is right.** E1's positional-vs-swing verdict rests on `excess −0.1909 (t −0.29)`, which is an
**accepted null**, not a demonstrated equivalence. No other source said this so precisely.
**ADOPTED:** E1 is relabelled *not separable at this n*, and any future equivalence claim ships
a TOST with a pre-declared margin.

⭐ **Q4 — the t ≈ 3.6 bar's universality is not established.** Correct. The negative control was
best-of-**20**; the programme has run far more than 20 hypotheses. **ADOPTED as an open item**
(see §7.11/Q-B).

**⛔ NOT AGREED, or narrower than claimed**

- **BKT1's framing is too broad.** "gap-through-stop" is handled **correctly** on every bar
  except the entry bar (**M6**: later-bar gap exits at the open, −5.000%). The defect is
  *entry-bar-only*, and its blast radius is therefore the overnight gap distribution, not the
  intraday one — **M7**: 0.34% of trades at the median 5% stop, 9.25% at the p10 0.65% stop.
  Your "Priority 1, highest" ranking survives this; the *description* does not.
- **BKT6 "no-repaint evidence incomplete"** — agreed in substance, but the framing ("universe
  inputs snapshotted ≠ every feature") understates it: the snapshots are **2 days deep**, so the
  correct statement is that no-repaint is established for **nothing historical at all**, not that
  it is partial.
- **Q2/Q8 "no complete multiplicity-adjusted family" and "no final untouched holdout"** —
  agreed, and both were already true; but note the **922-day hole (M1)** makes a clean holdout
  *period* much harder than you assume. The only contiguous modern block is 2023-07-03 → today.

**⚠ NEEDS PROOF — I could not settle these**

- **Q1's "predefine the live estimand and run to power"** — cannot be scoped until §7.11/Q-A
  (what the intended capital is) is answered, because position size sets both n and cost.
- **BKT4 "honest execution model asserted more strongly than demonstrated"** — fair, and I cannot
  refute it: there is **no live-vs-modelled fill calibration** anywhere. Sample today is 4 orders.

**✋ NOT ADOPTING, with the reason**

- **The 21-question round-2 brief as specified.** Roughly half of it (Q2 dependency map, Q5
  time-travel replay, Q15 full experiment registry, Q17 holdout identification) is a multi-week
  research-infrastructure programme, and this project has one operator working evenings. §A8's
  scale rule applies: *if we find ourselves designing new metrics for it, stop.* I have answered
  the subset that changes a decision and left the rest named.
- **"Repair `DOW_TREND` before inventing another gate" (Priority 5)** — see **M9/M10**: the
  premise you were given was wrong, and the item is now a *parameter* question, not a repair.

**❓ QUESTIONS BACK TO CHATGPT**

1. Given **M7** — exposure 0.34% at the median stop, 9.25% at the p10 stop — and that the
   affected trades book roughly +1R instead of −1R, what is the *threshold* prevalence at which
   you would consider the 1,975-trade headline invalidated rather than merely adjusted? Name the
   number before I re-run it.
2. Your Q7 equivalence point applies to E1. Does it also apply to **E2 3b**, where I already
   report INCONCLUSIVE — or is reporting the interval sufficient there?
3. **M1**: the corpus has no 2021 and no 2022. Does your "final untouched holdout" recommendation
   survive a sample whose only contiguous block is 3.2 years, or does it become an argument for
   not making the claim at all?

---

## §7.3 · Gemini — correct on every item, and every item was already in the document

**✅ AGREED** — all nine findings reproduce: ledger unwired (**M20**), IC below break-even, 1h
producer disagreement, gap-through-stop (**M5**), `KITE_TRADABLE` single-source, symmetric entry
zone, abstention-free denominator, DP charge crushing small positions (**M3**), local-only backups.

**⛔ NOT AGREED — one factual problem, stated plainly because it is checkable**

Your Priority-2 SQL is **not runnable against this schema.** It selects `so.symbol`,
`so.forward_5d_return`, `so.signal_score` from `signal_outcomes` and joins `sec`/`nix` tables.
Measured columns of `signal_outcomes`: `signal_id, stock_id, direction, classification, timeframe,
validity_until, status, entry_touched_at, entry_touch_price, sl_touched_at, sl_touch_price,
tp_touched_at, tp_touch_price, resolved_at, created_at, updated_at, mfe_price, mfe_at, mfe_r,
mae_price, mae_at, mae_r, excursion_computed_at`. There is no symbol column, no forward-return
column, no score column, and no `sec`/`nix` relations. The query was written against an imagined
schema.

⭐ **But the DECISION RULE inside it is the most useful thing you sent, and I am adopting it
verbatim:** *"If `sector_ic` does not meaningfully clear `nifty_ic`, drop U7 sector backfilling
entirely instead of spending effort populating the remaining 2,895 names."* That converts an open
queue item into a falsifiable test with a pre-declared kill condition, which is exactly the shape
this programme has been short of. **U7 is now gated on that test** (§7.11).

**⚠ NEEDS PROOF** — your Q-8 ORB/VWAP proposal is runnable (**M14** confirms the cohort exists),
but it needs a pre-registered estimand first; see the question below.

**✋ NOT ADOPTING** — nothing else, because nothing else was new. Said without complaint: a short
response that reproduces the document faithfully is a useful *control* on whether the document is
readable, and it passed.

**❓ QUESTIONS BACK TO GEMINI**

1. Will you re-issue the sector query against the real schema above? The relation you need is
   `signal_outcomes` joined to `signals` (for the score) and to `index_ohlcv_1d` (for the
   benchmark) — and note **M2**: index history only starts 2023-07-03, so the test window is 792
   sessions, not seven years.
2. Your ORB/VWAP proposal asks for "expectancy (bps per trade) and trade frequency". Against
   **M3**, what net bps would make you call it viable rather than interesting?

---

## §7.4 · Perplexity — the most complete false-edge inventory, and one genuinely new mechanism

**✅ AGREED, settled by measurement** — 1.3 reference data (`strategy_profiles`), 1.4 ledger
(**M20**), 1.5 wiring lint, 1.6 total feed loss (**M18**), 1.7 no DR ordering, 3.2/3.3 FII/DII
and its false neutral, 3.4 sector coverage, 3.5 point-in-time membership (**M16**), 3.6 upsert-
in-place, 4.1/4.2 the fill defect (**M5**, scoped by **M6/M7**), 4.3/4.4 cost magnitude and its
non-linearity in size (**M3** — measured 22.4 → 61.6 bps across the size range), 5.1 single-source
universe, 6.1 entry zone, 6.5 caps off.

⭐ **8.9 — "entry timing and price staleness" as a FALSE-EDGE source — is new and nobody else
made it.** You connected V2's three-deep price fallback (live tick → last 1m close → previous
daily close) to *research validity*, not just display honesty. That is the right connection:
if a signal's decision price can silently be yesterday's close, then the modelled entry and the
executable entry are different objects. **ADOPTED** — see the question below, because I cannot
yet tell you how often the third rung wins.

⭐ **1.1 — "the document is not canonical" as a governance risk.** Conceded. Six reviewers have
no other view of this system, so for them it is canonical whatever its header says.

**⛔ NOT AGREED, with the measurement**

- **5.2 / 8.1 survivorship.** *"Using current membership flags or a current curated stock list in
  historical tests can exclude delisted, suspended, merged securities."* **Refuted at the bar
  level — M15: 1,081 inactive stocks carry bars and 389 names have had no bar since 2025-01-01.**
  Dead names are retained in the archive. What is *not* retained is **point-in-time index
  membership** (M16) and point-in-time listing status. So the survivorship exposure is real but
  narrow: it bites any study that conditions on `is_nifty50`/`is_fno`, not the price archive.
- **8.4 "bar-boundary and timestamp look-ahead"** — the quote you attach (`t ≈ −10 to −13`) is the
  *fill-cost* term, which is not evidence for a timestamp defect. The no-look-ahead rule (compute
  on candle N, valid from N+1) is enforced in the frozen engine and pinned by parity fixtures.
  If you want to attack it, attack the **`is_complete`** boundary, not the cost t.
- **2.1's implied remedy ("re-run the IC on an independently reconstructed dataset")** — there is
  no independent dataset to reconstruct it from. **M1**: 2021 and 2022 do not exist in this
  database, and the bhavcopy archive is the same source.

**⚠ NEEDS PROOF** — 4.5 (fill specification) and 4.8 (backtest/live engine equivalence) are both
fair and both unanswerable today. **M8** proves the two engines *diverge by design* on exactly one
case; it does not establish they agree everywhere else.

**✋ NOT ADOPTING**

- **Priority 2, "create a reproducible point-in-time dataset", as a prerequisite to any new edge
  claim.** Directionally right, but as a gate it is unsatisfiable here: point-in-time membership
  before 2026-09-07 **cannot be reconstructed** — the rows were all created that night (M16).
  Adopting it as a precondition would mean never making another claim. I am adopting the weaker,
  achievable version: *label* every study that conditions on membership as membership-repainted.

**❓ QUESTIONS BACK TO PERPLEXITY**

1. Your 8.9: to price that mechanism I need to know how often the **third** fallback rung wins.
   If it turns out the daily-close rung is used on, say, <1% of decisions, does 8.9 stay a
   false-edge source or become a rendering issue?
2. Given **M15/M16** — bars retained, membership not — do you still rank survivorship at #2, or
   does it drop below the CA contamination in **M17**?

---

## §7.5 · DeepSeek — the most operationally usable format, and it chose its five correctly

**✅ AGREED, settled by measurement** — A1 (seed migration), A2 (**M20**), A3 (frontend-only lint),
A4 (**M19**), A5 (local backups, no DR ordering), A6 (**M5**), A8 (LTP painted `--color-bull`
regardless of direction), A9 (209 unpushed); D1/D2 FII/DII; D3 (1h); D4 (**M14** — exactly 210,
all F&O); D5 sector; D6 categories; D9 (rule inputs 2 days); S1 single-source; S3 (**M16**);
S5 (held-name feed loss); S7 (U6 closable); B3, B4, E1–E7.

⭐ **Your P0 list of five is the best-chosen subset any source proposed**, and four of the five are
now answered: #1 ledger (**M20**), #2 `strategy_profiles`, #3 `_simulate_trade` (**M5/M6/M7**),
#5 FII/DII. Only #4 changed its answer — see below.

**⛔ NOT AGREED — and it is your #4, which is also the one I got wrong**

*"Q4. Can `DOW_TREND` ever fire on the daily timeframe? … expected from the doc: 0/487."*

**Answer: YES, it can — M9.** A constructed 20-bar daily window with two swing highs at window
indices 5 and 14 and two swing lows at 6 and 13 returns **+0.70, "Confirmed uptrend"**. The
mechanism my document gave you — *"any two pivots differ by ≤9 < 11 so their windows overlap"* —
is **wrong**: pivots 9 apart do not sit inside each other's ±5 windows, so both can be strict
maxima. What is true is **M10**: it fires on **5 of 19,100 real panels (0.026%)**.

Also narrower than you have it: **A6/B3** — the gap defect is entry-bar-only (**M6**).

**⚠ NEEDS PROOF** — Q2 in your list ("why did no check catch it") is answered mechanically (a
migration alembic believes applied), but the *class* question — how many other seeded tables are
in this state — I have not enumerated.

**✋ NOT ADOPTING**

- **L12 "decide universe curation with an independent source."** There is no second free source
  with materially different failure modes for NSE cash equity; `KITE_TRADABLE` was supposed to be
  it and excludes one name. Adopting this would queue an item with no supplier. The achievable
  version is Claude's **S2** (§7.8): derive the universe size from cost arithmetic instead of from
  source agreement.

**❓ QUESTIONS BACK TO DEEPSEEK**

1. Given **M9/M10** — reachable but 0.026% — does your L4 (*"run R-1 trend-structure injection
   before any other Tier-1 hypothesis"*) still rank first? It is no longer a defect repair; it is a
   proposal to change a spec parameter, which under this project's rules needs `t ≈ 3.6`.
2. Your Q7 asked for per-session distinct counts on `ohlcv_5m`. Answered: **~209–210 before
   2026-09-15, 2,299 after**, and **M14** shows the cohort is exactly the F&O list. Does that make
   the intraday work more attractive (a clean, definable population) or less (a population we
   cannot trade on delivery)?

---

## §7.6 · Grok — the most independent reading, and the only one that attacked the live book

**✅ AGREED, settled by measurement** — A1 ledger (**M20**), A5 single-box, A6 collapse rail
(**M18**), A8 starvation registry (**M19**), D1/D5 FII-DII and CA sparsity, D3 the 1h producers,
D6 point-in-time membership (**M16**), BT1 the fill defect (**M5**), U1 single-source universe,
EX1 the entry zone, EX5 caps off.

⭐ **F10 is the sharpest thing anyone wrote about the live book, and the measurement makes it
worse than you stated.** You wrote: *"Four positions on 09-16 is not a sample; it is a narrative."*
**M13: all four positions are `SHORT`.** On a cash-delivery account — the account this system is
being built for, and the constraint behind the documented "57% of generator output is
untradeable" — an overnight short **cannot be held at all**. So the entire current live book sits
in the one direction the intended account cannot take. Neither my document nor any reviewer could
have seen that; it took a query. **This is the single most actionable finding of the round.**

⭐ **F11 — importing Minervini is a NEW strategy, and it will look like edge in a bull tape**
(*"the 91 are simply long-only momentum"*). Correct, unmeasurable here, and it reframes R-2 from
"a filter we haven't tried" to "a different strategy needing its own null". **ADOPTED into R-2's
description.**

⭐ **C6 — conceded in full.** *"`market_regime` 'returns a real verdict (200 closes + VIX 13.17)'
is 'the function returned a number', not 'the verdict is the specified regime'."* That is exactly
what it was, and I wrote it as validation. Corrected in §7.10.

⭐ **C5 answered rather than conceded — M8.** "Live is immune" now has its mechanism:
`place_paper_order` computes the fill, calls `eligibility.through_stop_reason`, and **raises**.
Tests at `tests/test_restrictions.py:224-244`. It is not an assertion from order type.

**⛔ NOT AGREED, with the measurement**

- **E1 / "the machine that would express an edge is not the machine that is running" / "the live
  funnel produced 0 candidates".** **Refuted today — M11: `3,395 → 2,299 → 2,291 → 2,108 → 15`.**
  You reasoned correctly from the number in my document; the number was one day old. The system
  is generating signals. ⚠ But your *conclusion* survives in a different form via M13: it is
  generating them, and the ones acted on were all shorts.
- **H7 — "restoring Dow on daily is restoring an impossible intent, i.e. a timeframe change".**
  **Refuted — M9.** It is reachable at `lookback=20, swing_n=5`; it fires on 0.026% of real panels
  (**M10**). Your governance conclusion (*"must clear t ≈ 3.6"*) nonetheless **strengthens**: a
  parameter change to a reachable factor is unambiguously a new hypothesis.
- **H2 — "if tape is just long-beta, the strategy IS a beta bet".** Partly refuted: **M12** shows
  the generator is **not** long-only (BUY 32 / SELL 18). The book that can be *traded on delivery*
  is long-only, which is a different statement and the one that should be made.
- **Q-CC-21 "is the engine long-only?"** — answered: no (**M12**), and `_simulate_trade` branches
  on `direction == "BUY"` with a mirrored short path, so the 1,975-trade corpus blends both.

**⚠ NEEDS PROOF**

- **C1 — "E2 numbers without n, IC flavour, residual definition or cost treatment in this
  document".** Fair. Partially answerable now: the script is `scripts/e2_score_ic.py`; `HORIZON = 5`
  is pre-registered in a comment marked ⛔; the break-even `0.255%` is the explicit round-trip
  charge stack; the IC is computed on the **absolute** score because the gate is a magnitude
  threshold. What I could **not** confirm and now consider a defect is **M17** (no CA filter) —
  which is Kimi's finding, not yours, but it lands in your C1's gap.
- **Q-CC-20 `entry_diversity`'s incremental effect** — not measured. It is the only ACTIVE gate and
  nobody has tabled what it drops.

**✋ NOT ADOPTING**

- **"Stop generating candidates from this confluence scorer" as an immediate instruction (your #1).**
  Directionally I think you are right and §7.11 moves toward it — but it is the user's decision,
  not a reviewer's and not mine, and it is exactly the kind of large irreversible call this
  project's rules reserve. Recorded as the standing recommendation, not executed.
- **The full 25-item Q-CC brief.** I answered the six you named as the smallest useful subset,
  plus five others. The rest are named in §7.11 rather than run.

**❓ QUESTIONS BACK TO GROK**

1. **M13 — all four open positions are shorts on a cash-delivery account.** Is the right response
   (a) close them and treat it as a plumbing rehearsal finding, (b) leave them and record the book
   as untradeable-by-construction, or (c) add a restriction that refuses overnight shorts outright?
   My lean is (c) plus (a), because a restriction is the only one of the three that cannot recur.
2. Your F10 says four positions is a narrative. With **M12** (BUY 32 / SELL 18 minted) and M13
   (4 of 4 acted-on are shorts), is the selection mechanism you'd suspect the *scorer* or the
   *operator*? I can measure the first; I cannot measure the second.
3. You proposed the `FALSIFIER:` field per answer. I have adopted it for §7.11. Is a falsifier
   that names a *threshold* (e.g. "prevalence > 3% invalidates") strictly better than one that
   names a *direction*, in your view?

---

## §7.7 · Nemotron 3.5 lightning — no findings were produced

Stated factually, because the user asked for an assessment of each response.

**What arrived is planning text, not an analysis.** It restates the prompt, enumerates section
headings it intends to fill, lists quotes it might use, and then repeats one paragraph — the
"claims made without sufficient support" enumeration — approximately ten times with no variation,
ending mid-sentence at *"…based on the document content."*

**Findings produced: 0. Verdicts: 0. Tests proposed: 0. Quotes verified: 0.** There is nothing to
agree or disagree with, and nothing to adopt. The one substantive line — *"we need to be careful:
The document includes many items"* — is a note to itself.

⚠ **This is worth recording rather than discarding**, for one reason: it is the control case for
§7.0's rule. Seven responses agreed on the ledger, `strategy_profiles` and the fill defect. If
agreement were evidence, this eighth response's silence would be evidence too. It is not — it is
an output failure, and the correct treatment is to exclude it rather than to read consensus into
the remaining seven.

**❓ QUESTION BACK:** none. If it is re-run, the single most useful thing it could return is the
one thing no other source attempted — an independent recomputation of a number in PART 1.

---

## §7.8 · Claude — the only response that did arithmetic on my numbers, and it found three errors

This response checked three figures before writing anything else. **All three checks were correct
and all three found a defect in my document.** No other source did this.

**✅ AGREED — CONFIRMED BY MEASUREMENT, all three**

| Their check | Verdict |
|---|---|
| *"1,100 sessions is wrong for the stated date range… ~1,713 NSE sessions"* | **CONFIRMED — M1.** 1,101 actual; the missing ~613 are the **922-day hole, 2020-12-23 → 2023-07-03**. Your estimate was accurate to about one session. ⚠ The *cause* is not a new defect — the hole is long documented — but **my document gave the span without the hole**, which is a real reporting defect and yours to claim. |
| *"791 sessions is exactly right for the intraday range… neither row states a date range"* | **CONFIRMED EXACTLY — M2.** `index_ohlcv_1d` and `india_vix_daily` both run **2023-07-03 → 2026-09-17, 792 sessions**. Your inference from an unstated range was right. |
| *"₹15.34 on ₹3,900 is 39.3 bps, not 61.6… implies either a ₹24.02 charge or a ₹2,490 position"* | **CONFIRMED, and both alternatives are exactly right — M3.** DP alone = **39.3 bps**; the **total** round trip on ₹3,900 = **₹24.01 = 61.6 bps**; and DP alone reaches 61.6 bps at a **₹2,490** position. You reverse-engineered the correct figure to the paisa from the discrepancy alone. |

⭐⭐ **S2 is the best strategic reframe anyone offered, and it is now measured.** You wrote:
*"solve for the position size at which round-trip friction falls under a chosen fraction of the
target edge, divide capital by it… that number — probably 3 to 6 — is how many names the selector
needs to produce."* Measured at ₹1,00,000 capital `[measured]`:

| concurrent positions | notional each | round-trip charges | bps |
|---:|---:|---:|---:|
| 1 | ₹1,00,000 | ₹237.58 | **23.8** |
| 2 | ₹50,000 | ₹126.46 | 25.3 |
| 3 | ₹33,000 | ₹88.69 | 26.9 |
| **4** | **₹25,000** | ₹70.91 | **28.4** |
| 5 | ₹20,000 | ₹59.78 | 29.9 |
| 10 | ₹10,000 | ₹37.56 | 37.6 |
| 25 | ₹4,000 | ₹24.22 | **60.5** |

⇒ **the percentage floor is ~22 bps and breadth costs ~6 bps per extra position up to 4, then
accelerates.** Going from 4 concurrent positions to 25 costs **32 bps of round-trip friction** —
which is larger than most effects the programme has measured. **Your "3 to 6" was right.** This
converts U-4 (universe curation, "never decided") from a taxonomy question into an arithmetic one,
and it is adopted as such in §7.11.

⭐ **Q1 — publish MDE beside every null and relabel underpowered ones.** ADOPTED. Several §2.4
verdicts should read UNDERPOWERED rather than REFUTED, and the document applied that distinction
to E2 3b while not applying it symmetrically elsewhere. That asymmetry is exactly your point.

⭐ **Q3 — |t| favours deterministic quantities.** ADOPTED, and **M3 demonstrates it**: the cost
term is a near-deterministic function of notional, so its standard error is tiny by construction
and |t| > 5 is arithmetic, not evidence of dominance. Effects will be reported in **bps with a CI**
beside the t from here.

⭐ **A3 (gate config unversioned), P2 (mark verdicts whose data is gone), H6 (no stated economic
mechanism), S3 (label the four positions).** All conceded; S3 is answered and sharpened by **M13**.

**⛔ NOT AGREED**

- **Q6/H7's premise** — you accepted *"lookback=20, swing_n=5 … needs two highs AND two lows …
  cannot fire"* and built a governance fork on it. **M9 refutes the premise** (it fires, +0.70) and
  **M10** replaces it with 0.026%. My document handed you the bad premise; your reasoning on top of
  it was sound, and your conclusion survives — *more* strongly, since a parameter change to a
  reachable factor is unambiguously a new hypothesis.
- **D6's inference from bar counts** (*"daily history is thinner per session than the present…
  each step is an ingestion event"*) — measured: names/session by year run 1,479 (2019) · 1,494
  (2020) · 1,752 (2023) · 1,877 (2024) · 2,136 (2025) · 2,453 (2026). It is a **step at the hole
  and a drift after it**, consistent with genuine listings growth plus the D2′b repair, not a
  series of ingestion events. Your remedy (cohort-stable statistics) stands regardless.

**⚠ NEEDS PROOF** — Q6's reviewer-independence test (seed a false premise and measure catch rate).
I cannot run it; it needs the user to seed the next round. ⭐ Noting one data point in its favour:
**this round, six of eight sources repeated a false premise I supplied** (the Dow "impossible by
construction" claim) and **none caught it** — consistent with your prior that panel independence is
lower than "five of six" implies.

**❓ QUESTIONS BACK TO CLAUDE**

1. Your S2 table above has a floor of ~22 bps that no position size can beat, because it is
   percentage-based (STT 0.1% × 2 legs dominates). If a strategy's gross edge must clear ~24 bps
   round trip at its *best* configuration of one position, does that end the daily-swing question
   at ₹1 lakh outright — or is your view that it merely fixes the concentration?
2. **M7** bounds the fill defect's exposure at 0.34% (median stop) to 9.25% (p10 stop). Your
   Priority 2 says fix and re-run. At which of those two ends would you still call the re-run
   mandatory before citing the 1,975-trade headline?
3. You flagged that PART 1 rows lack date ranges. **M2** shows why that mattered. Should every
   count in a state table carry a range as a *rule*, or only those whose range is not obvious?

---

## §7.9 · Kimi K3 — attacked the null instead of the claims, and found a real defect

Kimi was the only source to aim at the programme's **negative** result rather than its positive
ones, on the grounds that a null built on a contaminated sample is not a null.

⭐⭐ **H2 is CONFIRMED IN CODE, and it is the most valuable single finding from any reviewer this
round.** You wrote: *"Pre-registration guards against specification searching; it does not guard
against a contaminated sample. The document proves a CA-clean window was false for two other
studies but never states whether E2's IC sample excluded CA-affected names."*

**M17: it does not.** `scripts/e2_score_ic.py` skips panels for **window holes** (the 922-day gap)
and carries **no corporate-action screen** — while the sibling `swing_dependence_probe.py` defines
`CA_JUMP = 0.25` and prints its drop count. With 49 unadjusted corporate actions in the top-250
liquid universe, 35 of them ≥40% halvings `[cited]`, a 5-day forward return window straddling one
of those contributes a ±40–80% observation to the return series the IC is computed against.

⚠ **Direction unknown, and I will not guess it.** CA noise plausibly *widens* the estimate's
interval, in which case a filtered re-run could make the null **stronger**, not weaker. It could
also move the point estimate if contaminated names correlate with score. **E2 is now
RE-RUN-REQUIRED before citing**, and it joins R-8's two studies rather than sitting above them.

⭐ **Your "apply the document's own convention against it" catch is correct and I concede it.**
*"beta +0.92, alpha ≈ 0 — untagged, no source, no sample; yet it is the single most
decision-relevant number."* It is untagged in my document, and it is load-bearing in two places.
Tagged `[cited]` in §7.10, with its provenance named.

⭐ **A7 — the freeze converts a correctness defect into permanent contamination, and the freeze was
argued for strategy changes, not measurement fixes.** This is the sharpest governance point of the
round. The freeze exists so the scorer cannot drift without sign-off and a parity-fixture
regeneration; `_simulate_trade` is a **measurement instrument**, not a scoring rule, and nothing in
the freeze's rationale covers it. **ADOPTED** as the argument for the one exception in §7.11.

⭐ **"No portfolio-level evaluation anywhere"** — conceded, and it is a real hole: every statistic
in the programme is per-signal or per-trade. There is no equity curve, no portfolio Sharpe, no
drawdown of the book as actually constructed. Claude's S2 arithmetic above is the first thing in
this document that is portfolio-level at all.

**✅ ALSO AGREED** — Finding 0 (only one document was attached; second-hand verdicts cannot be
verified from the packet — correct and fairly stated), A1–A6, Q1–Q4, D1–D7, B1, B3, S1–S5, E1–E5.

**⛔ NOT AGREED, with the measurement**

- **B2 — "'Live is immune' is asserted with zero supporting evidence… no such test is cited."**
  **Answered — M8.** The mechanism is an explicit pre-fill rejection in `place_paper_order`, and
  tests exist at `tests/test_restrictions.py:224-244` and `tests/test_eligibility_preview.py:245,341`.
  Your scepticism was correctly placed — the document gave you three words — but the code does not
  share the document's weakness.
- **D4's standard, applied to the 1h claim** (*"the claim is asserted, not demonstrated, here"*) —
  correct about the document; the measurement exists in the commit that shipped it (Kite
  `60minute` returns 6 bars, the worker mints 7, verified against the live API). The defect is that
  I carried the conclusion without its evidence.
- **B3's framing that the cohort is "already liquid" names** — precise version, **M14**: the cohort
  is **exactly the 210 `is_fno` names**, 50 of which are Nifty-50. It is not a liquidity screen that
  happened to select them; it is a membership list.

**⚠ NEEDS PROOF** — your Q4 (*"is there a registry of every study run, or only pre-registered
ones?"*). There is no such registry. That is the honest answer and it feeds ChatGPT's Q4 and
Claude's Q1 directly: without it, the t ≈ 3.6 bar's trial count is unknown.

**✋ NOT ADOPTING**

- **"Answer Q-9 with the capital number on the table" as a gate on everything else.** Adopting the
  reasoning, not the sequencing: Claude's S2 arithmetic (above) answers most of the capital
  question already, and the remaining items (ledger, seed, CA re-runs) are worth doing whatever
  that answer is.

**❓ QUESTIONS BACK TO KIMI**

1. **M17 confirms your H2.** Before I re-run E2 with a `|move| > 25%` screen: do you want the
   filter applied to the **forward return window only**, to the **scoring window only**, or to
   both? They answer different questions and I would rather pre-register your choice than pick
   after seeing the result.
2. Given **M15** (1,081 inactive names carry bars; 389 have no bar since 2025) — does your
   survivorship concern reduce to the membership flags alone (**M16**), or do you see a second
   channel I have not measured?
3. You called for portfolio-level evaluation. With **M13** (the only live book is four shorts an
   equity-delivery account cannot hold), is a portfolio evaluation of *this* book meaningful at
   all, or does it have to wait for a book that could exist?

---

## §7.10 · ⛔⛔ WHAT THIS ROUND COST ME — five corrections to my own document

Every one of these was in PART 0–6 above and is corrected in place. Four were found by a
reviewer; **the fifth I found by testing my own claim, and it is the worst of them.**

**1. ⛔⛔ "The weight-20 `DOW_TREND` factor is unreachable by construction" — WRONG, and it
propagated to six of eight reviewers.**
**M9**: it fires, +0.70, on a constructed daily panel at the shipped parameters. The stated
mechanism — *"any two pivots differ by ≤9 < 11 so their windows overlap"* — is simply false:
pivots 9 apart do not lie inside each other's ±5 windows. The prior synthetic probe that
"returned 0.0" had placed its pivots **outside the admissible index range [5, 14]** — the same
mistake I made twice today before getting it right. ⭐ **The true statement is empirical, not
mathematical: 5 of 19,100 real panels = 0.026% (M10).** The conclusion — the swing engine
carries effectively no trend-structure input — **stands**. The reason it stands changed
completely, and with it the governance answer: R-1 is a **parameter proposal requiring t ≈ 3.6**,
not a defect repair that could ship on correctness grounds.
⚠ **This claim also sits in `CLAUDE.md` and `docs/SYSTEM_REVIEW_FOR_QUANT.md` §4.2 and in the
`dow-trend-dead-on-daily` memory.** All are corrected. **A claim asserted as structural, never
executed, survived in four documents for seven days and was repeated back to me by six
reviewers as established fact.**

**2. ⛔ "The flat ₹15.34 DP charge alone is 61.6 bps on a ₹3,900 position" — WRONG (Claude).**
**M3**: DP alone is **39.3 bps**; **₹24.01 total = 61.6 bps**. `CLAUDE.md` states it correctly
("100 × ₹39 pays 61.6 bps of **round-trip charges**"); I mis-attributed the total to one
component while condensing. The strategic point is unchanged and now better supported by the
breadth table in §7.8.

**3. ⛔ PART 1 gave `ohlcv_1d` as "1,100 sessions · 2019-10-01 → 2026-09-16" and omitted the
922-day hole (Claude).** **M1**: 2021 and 2022 do not exist. A reader computes ~1,713 sessions
from that span and is misled by ~613. The hole is long documented elsewhere; **omitting it from
a state table addressed to reviewers with no other view of the system is the defect.**

**4. ⛔ PART 1 gave `index_ohlcv_1d` and `india_vix_daily` as row counts with no date range
(Claude).** **M2**: both are **2023-07-03 → 2026-09-17**. "Restored" is true for 3.2 years, not
for the seven the daily table's span implies. Every market-regime and sector-RS evaluation is
therefore scoped to the post-gap block.

**5. ⛔ "`market_regime` returns a real verdict (200 closes + VIX 13.17)" was written as
validation (Grok).** It is not. It is *the function returned a number*. Corrected to say so.

⭐ **And one correction to the reviewers that is really a correction to me:** seven of eight
responses lead with the trade ledger, `strategy_profiles` and the fill defect — the three things
my own document already flagged. **Agreement concentrated exactly where I had pre-labelled the
answer.** The findings that changed anything (Kimi's M17, Claude's M1–M3, Grok's C6) all came
from attacking something the document asserted rather than something it flagged.

---

## §7.11 · THE REVISED QUEUE — with a falsifier per item (Grok's format)

Reordered by what this round settled. Items marked ⓘ changed position because of a measurement.

| # | Item | Why now | FALSIFIER — what would reverse it |
|---|---|---|---|
| **1** | ⓘ **Decide the four SHORT positions (M13)** | The only live book is in a direction a cash-delivery account cannot hold overnight | If delivery shorts *are* representable in the intended account, this is a non-issue and the restriction is wrong |
| **2** | **Wire the ledger (M20)** + a backend wiring lint | Unchanged: the record that survives the next loss | A reconstruction drill that succeeds from `positions`+`orders` alone would make it optional |
| **3** | **Re-seed `strategy_profiles` via an idempotent script** | 0 rows at head; four consumers dead | Finding the four consumers degrade safely to "no style engines" rather than silently |
| **4** | ⓘ **Re-run E2 with a CA screen (M17, Kimi)** | The programme's central null has no corporate-action filter | If the filtered IC's 90% interval still excludes break-even, the null hardens and this closes |
| **5** | **Re-run D5 + D1 with the CA screen (R-8)** | Both closures cite a CA-clean window that does not exist | If both signs and both t's hold, they become citable and stay closed |
| **6** | ⓘ **Fix `_simulate_trade`'s entry-bar gap and quantify (M5/M6/M7)** | Scoped now: entry-bar only, exposure 0.34%→9.25% by stop width. **Kimi's A7 is the governance argument** — the freeze covers the *scorer*, not the *measurement instrument* | Prevalence in the actual 1,975-trade corpus below ~1% **and** no sign change in D1/D5 ⇒ adjust the headline, do not re-open the closures |
| **7** | ⓘ **Answer the capital/breadth question from §7.8's table** | 23.8 bps at 1 position → 60.5 at 25; the floor is ~22 bps and cannot be beaten | A gross edge estimate that clears ~24 bps at *any* configuration keeps the strategy class alive |
| **8** | **Add `categories`, `stock_categories`, `ledger_entries` to the starvation registry (M19)** | The alarm misses the tables its own adjudication named | — |
| **9** | **Make the entry zone directional** | Correctness, not P&L | — |
| **10** | ⓘ **U7 sector map — GATED on Gemini's test** | Run sector-relative vs NIFTY50 separation on the 500 classified names first | ⭐ **Pre-declared kill: if sector-relative does not clear NIFTY50, DROP U7** rather than backfill 2,895 names |
| **11** | **U5 runbook DR ordering; off-box backup; push** | One machine, one disk, 209 commits | — |
| **12** | ⓘ **R-1 trend injection — RECLASSIFIED** | No longer a defect repair (M9). A parameter proposal at `t ≈ 3.6` | A read-only injection returning paired ΔR at abs(t) ≥ 3.6 would promote it; anything less closes it |

**Not doing, with the reason** — a ninth gate · flipping `market_regime`/`sector_rs` on restored
data · the backward CA pass on 1,768 names · a UI cockpit · the 1h backfill before a
producer-of-record is named · **and not starting cycle 2**, which now has a new blocker: item 1.

---

## §7.12 · What the round returned, measured against the bar I set for it

My pre-registered rule was ChatGPT's and my own: **a point counts if it changes a decision AND is
settleable by a query.**

**Points that changed a decision: 7.**
Kimi's M17 (E2 has no CA filter) · Claude's M1, M2, M3 (three arithmetic defects) · Grok's C6
(validation overclaim) and F10→M13 (the short book) · Gemini's U7 kill-rule · ChatGPT's Q7
(equivalence ≠ small t) · plus **my own M9/M10**, which is not a reviewer point but was produced
by the discipline the round imposed.

**Compare:** §13f measured review breadth at 4-of-37 and §78 at 4-of-29. This round is the highest
yield so far — and the reason is visible: **five of the seven came from a reviewer recomputing or
interrogating a number I asserted, rather than proposing new work.** The three responses that
mostly restated the document (Gemini, most of Perplexity, most of DeepSeek) contributed one
adoptable item between them, and the response that produced nothing (Nemotron) is the control
showing that agreement counts are not evidence.

⭐ **The rule for round 7, if there is one: send reviewers the numbers and ask them to recompute,
not the plan and ask them to critique.** Every high-yield point this round came from the former.
