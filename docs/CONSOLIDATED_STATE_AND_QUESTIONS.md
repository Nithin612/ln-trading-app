# Consolidated state — what is DONE, what is PENDING, and what we are asking

**Combines:** `docs/UNIVERSE_REBUILD_PLAN.md` (3,698 lines, 5 review rounds, the live
infrastructure thread) and `docs/SYSTEM_REVIEW_FOR_QUANT.md` (1,088 lines, the standalone
strategy review) — plus their companions `POSITIONAL_REVIEW_FOR_QUANT.md`,
`quant-panel-adjudication-2026-09-10.md` and `BUILD_QUEUE.md` where they carry the verdict.

**Written:** 2026-09-17 · branch `feature/pre-cycle2-hardening` · **215 commits ahead of
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
- ⭐ **RULE, adopted 2026-09-17 (Claude): every count over time carries its range.** `min → max`,
  a distinct-session count, and a gap flag when the largest gap exceeds five sessions. Stated
  mechanically rather than "where the range is non-obvious", because M2 was invisible precisely
  because the range looked obvious.
- ⭐ **RULE, adopted 2026-09-17 (Kimi SEL-3): every cohort carries its construction date**, and no
  cohort may be ranked on data inside its own measurement window. M31 is why.

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
| `stocks` | 3,392 · **1,322 active** | **3,415 · 2,299 active · 1,116 inactive** | ✅ repaired (D2′b); **+20 historical names from the backfill, active set untouched** (PART 9) |
| …`sector` populated | 500 | **500** | ⛔ unchanged — U7 never ran |
| …`is_nifty50` active | 50 (of which 5 active) | **50 active** | ✅ repaired |
| …`is_fno` active | 212 | **210 active** | ✅ |
| …`ca_flagged_at` | — | **7** (5 of them active) | ⚠ has a clearing path now |
| `ohlcv_1d` | 2,080,305 bars → 2026-09-09 | ✅ **3,166,300 bars · 1,727 sessions · 2019-10-01 → 2026-09-17** | ⭐⭐ **HOLE FILLED + SPECIAL SESSIONS RECOVERED 2026-09-17 (PARTS 9–10).** 1,101 → 1,723 (the 922-day hole) → **1,727** (3 Saturday + **1 Sunday** NSE sessions the enumerator could not reach — M39–M43). ⚠ One known hole remains: **2022-08-08**, where NSE serves an XLSX at the `.csv` URL |
| `ohlcv_5m` | **empty** | **12,625,648 rows · 796 sessions · 2023-07-03 → 2026-09-17** | ✅ **backfilled** |
| `ohlcv_15m` | **empty** | **4,206,475 rows · 796 sessions** | ✅ **backfilled** |
| `ohlcv_1h` | **empty** | **48,065 rows · 3 sessions · 2026-09-15 → 09-17** | ⚠ live-only; backfill path exists, **not run** |
| …intraday breadth | — | **~210 names/session before 09-15; 2,299 from 09-15** | ⚠ the history is a 210-name cohort, not the universe |
| `index_ohlcv_1d` | 48 rows | **21,384 rows · 27 indices · 792 sessions, 2023-07-03 → 2026-09-17** | ✅ **U8** — ⚠ 3.2 years, not 7 (§7.10/4) |
| `indices` registered | 3 | **27** (of 166 in the source CSV; 139 deliberately excluded) | ✅ |
| `india_vix_daily` | 16 | **792, 2023-07-03 → 2026-09-17** | ✅ — ⚠ same 3.2-year scope |
| `cas_daily` | 43 rows / 1 session | **716 rows / 5 sessions · 2026-09-10 → 09-17** | ⚠ accruing again, cannot be back-filled |
| `fii_dii_daily` | — | **10 rows / 5 sessions of ~790** | ⛔ **unrecoverable by source** |
| `signals` | 30 | **50 · 23 active · 0 shadow** (BUY 32 / SELL 18) | ⛔ read **48 · 22** until M56 — stale within the same day, the defect the range rule exists to catch |
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

## 2.4 Research — verdicts as they stand, with their standing marked (revised 2026-09-17)

⚠ **This section previously read "settled and should not be re-litigated" while §7.11 marked E2
re-run-required (M24). Both cannot be binding.** Each row now carries its own standing: **CLOSED**
(cite freely) · **RE-RUN-REQUIRED** (do not cite) · **UNDERPOWERED** (an accepted null, not an
equivalence — ChatGPT Q7, adopted). Nothing here is re-opened by argument; several are re-opened
by a measurement named in §8.10.

These are `SYSTEM_REVIEW` §11.3 plus the B-queue. ⛔ **CORRECTED 2026-09-17 (Claude Q14): the
previous preamble said "nothing in the data restoration changes any of them". That is now false
twice over** — PART 9 added **626 sessions and a zero-drift year**, and M52 shows the retained
block was the mildest available. ⇒ **every row below is a statement about the scorer AS MEASURED
ON THE 794-SESSION POST-HOLE BLOCK**, and none has been re-run on the restored archive.

| Verdict | Number |
|---|---|
| ⚠ **RE-RUN-REQUIRED — "the ranker is dead" (E2)** | IC h=5d **−0.0070, 90% [−0.0259, +0.0119]** vs break-even **0.0310**; `confidence_pct` flatter still (**+0.0024**). ⛔ **Do not cite: M17 — no corporate-action screen.** ✅ Its interval method is sound (M36: non-overlapping `stride=5`). ⛔⛔ **AND A SECOND REASON, M62 (2026-09-18): the cohort is `load_frames`' top-250 ranked on `now() - 180 days` — 34.4% of the cross-section was selected on post-window liquidity, and 29.2% of the names that traded in 2021–22 cannot enter it at all.** The pre-registration named the survivorship half (*"drawn by today's liquidity … recorded, not solved"*) and this document never carried it. **Break-even derivation, carried from the pre-registration (M63): `E[excess|selected] ≈ IC · σ_cs · E[z|sel]` against 25.5 bps** — ⭐ **and its PARAMETERS, which appeared nowhere until round 11 (Kimi F11): `E[z|sel] = 2.267` (identical across both published σ rows, so it is pinned), and break-even 0.0310 therefore implies `σ_cs = 3.63%`.** The one number the programme-kill decision turns on now states its inputs |
| **The ≥70% gate is unproven in BOTH directions** (E2 3b) | point estimate −0.3150% but the upper bound **+0.388%** clears break-even ⇒ INCONCLUSIVE, deliberately not rounded to null |
| **Gating is closed as a programme** | 8 shadow gates, 2 promotions both refuted, best survivor `sl_atr` at **t = 0.41 vs a 3.6 hurdle** |
| **The promotion bar is t ≈ 3.6 and is FLAT IN n** | validated by negative control: 1.10% of best-of-20 zero-edge selections clear; 80% power at a true per-trade Sharpe 0.52 |
| **Exit geometry is not the lever** (D5) | no constant-R:R target 1.0–3.0R beats the frozen absolute-% target on 1,152 signals; every paired ΔR negative, abs(t) ≤ 0.65 |
| **The queued generation lever is refuted** (D1/RVOL) | injecting a graded RVOL factor: **−0.291R at t = −2.91** |
| **Stop-width is a denominator artifact** | closed three times; swing **R −0.386 → raw% −0.262 → excess vs the cohort basket paired in time +0.069** (⛔ renamed 2026-09-18: "matched" was a misnomer — `basket_series` is an equal-weight mean of the same `load_frames` cohort over each trade's own window, **matched on nothing**) |
| ⚠ **UNDERPOWERED — positional vs swing (E1)** | **R −0.4879 → raw% −0.7870 → excess −0.1909 (t −0.29)**. ⛔ **Relabelled 2026-09-17 (ChatGPT Q7): t = −0.29 is an ACCEPTED NULL, not a demonstrated equivalence.** "Identical shape" is withdrawn; an equivalence claim needs a TOST with a pre-declared margin |
| **Hold-period breadth lever: resolved against** (B7) | MFE over abs(MAE) **0.83 / 1.12**, hazard curve **flat** 0.559 → 0.489 over days 0–5 |
| **88% of the BUY book's gross loss is tape, not alpha** | raw −0.1877% = tape −0.1659% + alpha −0.0218% |
| ⚠ **CORRECTED — three factors effectively never score** | `DOW_TREND` (weight **20**), `MARUBOZU`, `FII_DII_FLOW`. ⛔ **"0 of 487 panels" is withdrawn twice over:** M9 refuted its mechanism, and at M10's measured **0.026%** the expected count in 487 panels is **0.127** — the sample could never distinguish "never" from "rare". Standing figure: **5 of 19,100 (M10)** |

---

# PART 3 — PENDING

Ordered by **what it blocks**, not by size. Every row carries the state measured today.

## 3.1 ⛔ Blocked on the user (nothing proceeds without a decision)

| # | Item | State today | What is actually being asked |
|---|---|---|---|
| U-1 | **The push** | **215 commits ahead of `origin/main`** (⛔ restated 2026-09-18 — read 209 here and 210 in §8.10 simultaneously, Kimi F2), no upstream configured `[measured]` | W4 reserves push to the user. Everything in PART 2 exists on one local branch on one machine |
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
| R-2 | **Minervini as a DIFFERENT STRATEGY, not a filter** (Tier-1 #2) | **NOT RUN, REFRAMED 2026-09-17** | ⭐ **Grok F11, adopted:** importing it is a new strategy needing its own null — and it **will look like edge in a bull tape**, which is all we have (M32). Test it against a **time-paired cohort basket** (⛔ renamed 2026-09-18, round 11 — this said "a matched basket" and it is matched on nothing; §12.10/6 claimed the rename was complete and missed this one, which is the only instance that is a FORWARD INSTRUCTION), never against this book. 0 of 91 entries pass ⇒ disjoint from our selection. Needs a universe-level regeneration |
| R-3 | **12-month price momentum** (Tier-1 #3) | **NOT RUN** | The single untested thread from the reading study. ⚠ It surfaced as the *control that killed* the overhead-supply effect, so the evidence for it is weaker than it looks |
| R-4 | **CAS overnight reversal to ≥30 sessions** (Tier-1 #4) | **accruing: 5 of 30** `[measured]` | ✅ Capture restarted. ~5 weeks of wall-clock left. Best odds on the list — and it is a **different strategy**, not a fix to this one |
| R-5 | **Opening-range / VWAP / intraday timing** | ⭐ **NEWLY TESTABLE** | `SYSTEM_REVIEW` §13 Tier-3 #9 calls these blocked. They are not: **3 years of 5m/15m bars exist for ~210 liquid names** `[measured]`. ⚠ The history is a **210-name cohort**, so any result generalises to F&O/Nifty-50 names only |
| R-6 | **Limit orders** (Tier-2 #5) | Phase 7 | Attacks the only term measured at t ≈ −10 to −13. ⛔ **But they cannot go under the floor (Grok E4, confirmed by M28): 20.0 of the 22.22 bps delivery floor is statutory STT.** Limits attack spread and impact *on top of* it |
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
   +0.92, alpha ≈ 0 `[cited — engine_selectivity_probe, 2026-09-10; sample and method not
   independently verified — Kimi, round 6]`). It costs one read-only corpus pass, needs no frozen edit and no sign-off
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
| **M7** | How often is a trade exposed to M5? | Overnight gap distribution, 183,556 stock-days, top-250 liquid, 2023-07-03→now: gap ≤ **−0.65%** (p10 stop) **9.25%** · ≤ **−2%** **2.08%** · ≤ **−5%** (median stop) **0.34%**. Mean gap **+0.1835%**. ⛔ **SUPERSEDED — the cohort was ranked on 2026 liquidity (look-ahead, M31); point-in-time figures are 8.51% / 1.60% / 0.26%. And it measured only the LONG tail (M30).** |
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
best-of-**20**; the programme has run far more than 20 hypotheses. **ADOPTED as an open item** — now
**§8.10 row Q-B** (it was a null pointer until 2026-09-17; M21).

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

- **Q1's "predefine the live estimand and run to power"** — cannot be scoped until **§8.10 row Q-A**
  (the intended capital and account type) is answered — a null pointer until 2026-09-17 (M21), because position size sets both n and cost.
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

---

# PART 8 — THE ROUND-7 PANEL, ANSWERED ONE BY ONE (2026-09-17)

Seven responses: **ChatGPT · Gemini · DeepSeek · Grok · Nemotron 3.5 lightning · Claude · Kimi K3.**
(Perplexity did not respond this round.) Adjudicated separately again, for the same reason as
round 6 — and it paid again: **the single most consequential finding came from one source, as a
question nobody had thought to ask.**

## §8.0 · What I checked first, and why the order matters

Round 6's rule was *send the numbers and ask for a recomputation*. This round the panel did
exactly that, and **most of the strongest points were aimed at my own document rather than at the
system.** Those are the cheapest to verify, so I verified them first — six were true.

⭐⭐ **And one reviewer question did something no critique has done in eight rounds: it dissolved
a constraint the programme had been planning around for a month.** See **M38**.

⚠ **One near-miss worth recording before the table.** Working through Kimi's STAT-8 I computed
an overlap-inflation factor for E2's confidence interval and was one step from publishing *"E2
flips from NULL to INCONCLUSIVE"*. Then I read the sampling parameter. **`--stride` defaults to
`HORIZON` = 5, so the decision grid is non-overlapping by construction and no correction
applies** (M36). I would have shipped a false correction of a false correction.

## §8.1 · The round-7 measurement round

| ID | Question | Result `[measured 2026-09-17]` |
|---|---|---|
| **M21** | Do `§7.11/Q-A` and `Q-B` exist? | ⛔ **No.** They appear only as forward references at lines 487 and 506. §7.11 is a 12-row numbered table. **Two adoptions point at null addresses.** |
| **M22** | Does §2.4 still carry the refuted "0 of 487"? | ⛔ **Yes**, line 166, uncorrected. ⭐ And M10 makes it worse than stale: at **0.026%** the expected count in 487 panels is **0.127** — so "0 of 487" was **never evidence** of "never scores". It is what a working factor produces. |
| **M23** | Is `beta +0.92, alpha ≈ 0` tagged, as §7.9 said it would be? | ⛔ **No.** Untagged at **line 286**, exactly where the reviewer said. §7.10 lists five corrections and this is not among them. |
| **M24** | Does §2.4 still read "settled and should not be re-litigated"? | ⛔ **Yes**, line 149 — while §7.11 item 4 marks E2 **re-run-required**. Both cannot be binding. |
| **M25** | Queue rows with an empty falsifier? | ⛔ **3 of 12** — items 8, 9 and 11, in a table whose stated purpose is a falsifier per item. |
| **M26** | How many round-6 ADOPTIONS reached the queue? | ⛔ **2 of 8.** Landed: Kimi's freeze argument (item 6), Gemini's U7 kill-rule (item 10). Did not: E1's relabel, MDE-beside-nulls, bps-with-CI, price-staleness, the t≈3.6 trial count, and **R-2's Minervini reframe — its row at line 220 is unchanged**. |
| **M27** | Does the cost table fit a fixed + linear model? | ✅ **Exactly.** `charges = ₹15.34 + 22.225 bps × notional`, residual **≤ ₹0.01 on all 11 points**. The ₹15.34 **is** the DP charge. |
| **M28** | What is the floor made of, and is it product-specific? | ⭐⭐ **Delivery floor 22.22 bps, of which STT (0.1% × 2 legs) is 20.00 = 90.0%** (stamp 1.50, exchange 0.60, GST 0.12, SEBI 0.02, DP 0.15 at ₹10L). **Intraday floor is 3.52 bps — 6.3× lower.** At ₹1L: delivery **23.8** vs intraday **8.2** bps. ⚠ **F&O is not modelled at all** (`fees.py:10` — "F&O charges are Phase 4"). |
| **M29** | Four tables, one window, four session counts — why? | `ohlcv_1d` 794 · `5m` 796 · index 792 · VIX 792. **6 dates are not in all four**, and all six are **special sessions**: Saturday budget/DR-site sessions (2024-01-20, 2024-03-02, 2024-05-18, 2025-02-01, 2026-02-01) and **Muhurat 2024-11-01** (index+VIX+daily, no 5m). Explainable — and a study that inner-joins to the index table silently drops them. |
| **M30** | The gap tail for **shorts** (the stop is *above* entry) | ⭐ **Short-side exposure is 2.1× the long side at the tight stop**: gap ≥ +0.65% = **19.83%** vs ≤ −0.65% = **9.25%**; ≥ +2% = 3.28% vs 2.08%; ≥ +5% = 0.331% vs 0.343% (**equal at the median stop**). |
| **M31** | Was my M7 cohort point-in-time? | ⛔ **No — it was ranked on 2026 liquidity and applied to 2023-2026.** Re-run with a cohort ranked **only on pre-window data** (2020-01 → 2023-07): long tail **9.248% → 8.508%**, short tail **19.830% → 16.822%**. **My M7 overstated exposure by 8% and 18% relative — ⚠ **restated 2026-09-18 (Kimi F3): those two figures use DIFFERENT BASES.** Long tail 8.0% of the old value; short tail 17.9% of the *corrected* value (15.2% of the old). On one base consistently: **8.0% and 15.2%** of the old.** |
| **M32** | Is the post-hole block representative? | ⛔ **No.** Same PIT cohort on the **pre-hole block (2019-10 → 2020-12, includes COVID)**: long tail **12.63%**, short tail **28.67%** — **~1.5–1.7× the post-hole figures.** The 3.2-year window is a benign-regime sample. |
| **M33** | Did the operator take the top of the ranking? | ⛔⛔ **No.** The four acted-on signals rank **76, 76, 75, 74** in confidence. **All 14 higher-confidence signals (78–90) were NOT acted on**, including five SELLs at 80–90. Mean confidence **SELL 77.7 > BUY 74.6**. |
| **M34** | Of the funnel's live signals, how many can a delivery account hold? | ⛔⛔ **4 of 15.** The live book is **11 SELL / 4 BUY**. **The real tradeable last rung is 4, not 15** — 73% of the live list is untradeable overnight on CNC. |
| **M35** | Does any restriction refuse a short? | ⛔ **No.** 13 registry entries (withdrawal · universe · off-market · regime · circuit · entry-quality · R:R · sector-RS · market-regime · liquidity · chase · through-stop) — **none is directional or settlement-aware.** |
| **M36** | Is E2's naive `mean ± 1.645·se` interval anti-conservative? | ✅ **No — REFUTED.** `--stride` defaults to `HORIZON` = 5 (`e2_score_ic.py:335`), so the decision grid is `sessions[::5]` and the 5-day forward windows **do not overlap**. The naive SE is the right estimator here, and the design is deliberate (the per-name loop was rejected in a comment for exactly this reason). |
| **M37** | Is `ohlcv_1d` back-adjusted for corporate actions? | ⛔ **No.** `bhavcopy_service` has no adjustment logic, and `ca_adjust.py` adjusts **open paper positions only** ("Corporate-action adjustment of OPEN paper positions — Phase 6.8.5"). **Drop-the-window is the only policy**, and it is applied inconsistently across scripts. |
| **M38** | ⭐⭐⭐ Is the 922-day hole actually permanent? | ⛔⛔ **NO. NSE SERVES THE MISSING FILES TODAY.** One probe each: `sec_bhavdata_full_15062021.csv` → **HTTP 200, 233,986 bytes**; `..._15032022.csv` → **HTTP 200, 246,024 bytes**; today's → HTTP 200, 393,799 bytes. **Identical header schema.** Same URL template as `bhavcopy_service.py:45`. |

---

## §8.2 · ChatGPT — correctly re-sequenced, and one challenge I concede

**✅ AGREED** — its re-ordering is right and I am adopting it: account correctness → simulator →
clean E2 → clean D5/RVOL → `entry_diversity` → portfolio → *then* new alpha. Its P0 (the four
shorts) matches Grok's and mine.

⭐ **H4 — "the ~1% prevalence threshold is not established" — CONCEDED.** I wrote that falsifier
and never justified 1%. **Grok supplied the better instrument in the same round** (§8.5): the bias
is `exposure × 2R`, so the criterion should be stated in **R of mean contamination**, not in
percent of trades. Item 6's falsifier is rewritten accordingly.

⭐ **Its Q4 (dependency map for E2) is adopted** — with M36 and Kimi's M17 together, E2 now has one
confirmed contamination (no CA screen) and one *refuted* one (interval method), and the list of
conclusions resting on it has never been written down.

⭐ **E4 — price-provenance prevalence — is the right elevation**, and it is still unmeasured. I
adopted the mechanism from Perplexity in round 6 and did not queue the counter. That is an M26
instance.

**⛔ NOT AGREED**

- **"The ranker is dead → downgrade to 'requires clean E2 rerun'".** Half right. The CA gap (M17)
  justifies the downgrade; the interval concern does **not** (M36). Say *one* reason, not two.
- **Q1's "1,975-trade prevalence" as the first number.** M30/M31/M32 show the exposure rate is not
  one number: it depends on direction (2.1× for shorts), on cohort construction (my own was
  look-ahead), and on regime (1.5–1.7× pre-hole). Ask for the **stop-width distribution of the
  corpus** first, then prevalence.

**❓ QUESTIONS BACK TO CHATGPT**

1. Given **M28** — delivery floor 22.2 bps of which 90% is statutory STT, intraday floor 3.5 bps —
   is your P7 ("only then test new alpha") still the right sequence, or does the *product* choice
   (swing-on-delivery vs intraday) dominate every alpha question at ₹1 lakh?
2. **M38**: the 922-day hole is fillable. Does that change your Q3 (E2 three ways) into "re-run
   E2 on a 1,714-session sample" — i.e. does a 56% larger sample outrank a cleaner one?

---

## §8.3 · Gemini — accurate again, and again nothing new

**✅ AGREED** — all nine findings reproduce and every quote is correct. Its PART 2 items 1–5
likewise.

**⛔ NOT AGREED — nothing to disagree with, which is the problem.** Every item is a restatement of
a finding already in the document, including the five corrections I had already made in §7.10.
Its item 3 ("market_regime was claimed to return a validated regime state") quotes **my own
correction** back to me as if it were a new finding.

⭐ **Its one durable contribution remains round 6's U7 kill-rule**, which is queue item 10 and the
only reviewer artifact from either round that converted an open item into a falsifiable test.

**❓ QUESTION BACK TO GEMINI** — you have now twice produced a faithful restatement. Round 6 asked
you to re-issue the sector query against the real schema and it did not come back. **M2** now
bounds that test at 792 sessions and ~500 classifiable names: is it still worth running, and what
separation would you accept as a pass? A kill-rule without a threshold cannot kill anything.

---

## §8.4 · DeepSeek — the best index of the document, and now mostly an echo of it

**✅ AGREED** — its A1–A9, Q1–Q12, D1–D13, B1–B11, S1–S10, E1–E7, H1–H11, F1–F13 and L1–L12 are
accurate and correctly keyed. As a navigable index of the current state it is the best of the
seven.

**⛔ NOT AGREED — the request list has inverted.** Round 6's P0 list named five things I had not
measured. Round 7's Priority-A list asks me to **re-show M13, M17, M5/M6/M7, M9/M10 and M1/M2** —
all of which are already in the document with their queries attached. Its items 6–20 are the same.
⭐ The one genuinely new ask is **"show the account type configuration"** (its item 1), which
matters: it is the falsifier for queue item 1 and it is not in the database — it is a broker
account property, so it is the user's to state.

**❓ QUESTION BACK TO DEEPSEEK** — your format's value is that every row carries a test. **M31**
shows one of my own rows failed its own test (the cohort was not point-in-time). Would you add a
column for *"whose data constructed this, and was that construction point-in-time?"* — it is the
one check your table cannot currently express, and it caught a real defect this round.

---

## §8.5 · Grok — answered its own homework, and supplied the instrument ChatGPT asked for

⭐⭐ **The 2R bias identity is the best methodological contribution of the round.** You restated
the gap-defect falsifier as `exposure × 2R` and gave the numbers: 0.34% ⇒ **+0.0068R**, 9.25% ⇒
**+0.185R**, against a headline of −0.386R. ⇒ **"invalid as cited if |bias| > 0.05R; adjust in
place if |bias| < 0.02R."** That is a falsifier in the unit of the claim, and it replaces my
unjustified 1%. **ADOPTED into item 6.**

⭐ **Your answer to my question 1 (shorts) is now settled in your favour and then some.**
**M35: no restriction anywhere refuses a short** — the registry has 13 entries and not one is
directional. So your "(c) + (a)" is not merely preferable; there is no 409 to rely on. Your own
falsifier fires the other way.

⭐⭐ **Your question 2 is ANSWERED, and the answer is neither branch you offered.** You predicted:
*"4/4 actives were SELL ⇒ machine; mixed actives + only SELL taken ⇒ operator/UI."* **M33/M34:**
the live book is **11 SELL / 4 BUY** (mixed), **the four taken rank 76/76/75/74**, and **all 14
higher-confidence signals — five of them SELL at 80–90 — were not taken.** So it is not the
scorer picking, and it is not "the operator took the top of the list" either. Both mechanisms are
partly implicated: the scorer **over-produces and over-scores shorts** (SELL mean 77.7 vs BUY
74.6; 73% of the live list), and the operator **took four mid-ranked names and skipped every
better-scored one**. ⇒ a third hypothesis is now on the table: selection by *what was clickable*
— entry-zone proximity, or eligibility, or screen position — none of which is recorded.

⭐ **E4 — "limit orders do not remove STT; do not sell them as a way under 22 bps" — CONFIRMED by
M28.** STT is 20.0 of the 22.22 bps delivery floor. Limits attack spread and impact **on top of**
a statutory floor they cannot touch. That correction belongs in R-6's description and is now made.

⭐ **C1 — CONFIRMED (M24).** §2.4's "should not be re-litigated" and §7.11's "re-run-required"
were both live in the same document. Fixed in §8.9.

**⛔ NOT AGREED**

- **Q-CC-31's premise that the last rung is "how many of the 15 are CNC-holdable longs".**
  Measured (**M34**) it is **4** — but note that makes the funnel end *lower* than the 0 you
  originally attacked, not higher. The system produces 15 live signals and 4 tradeable ones.
- **"F&O STT is a different schedule and would change S2"** — correct in principle and
  **unanswerable here: F&O is not modelled at all** (M28). I cannot price the 210-name cohort as
  F&O without building that schedule.

**❓ QUESTIONS BACK TO GROK**

1. **M33** puts a third hypothesis on the table — selection by clickability rather than by rank or
   by direction. Is that worth instrumenting (log which surface and which rank each order came
   from), or does the answer not change what we do, given item 1 blocks the direction anyway?
2. Your 0.05R threshold assumes each affected trade flips −1R → +1R. **M30** shows short-side
   exposure is 2.1× the long side at tight stops. Should the threshold be computed **per
   direction** and weighted by the corpus's BUY/SELL mix, or is a single blended number enough?
3. **M28**: intraday's floor is 3.52 bps against delivery's 22.22. Does that make your Q-8 ruling
   ("do not run an opening-range study until Q-9 is answered") *softer* — since the intraday
   product has 6× more room — or harder, because it is a different strategy on a cohort the
   delivery account cannot hold?

---

## §8.6 · Nemotron 3.5 lightning — second failure, partially recovered

Round 6 produced planning text with no findings. Round 7 produced **tables** — A1–A6, Q1–Q9,
D1–D7, B1–B5, U1–U5, E1–E4, H1–H8, F1–F7, I1–I10 — and then **broke mid-output**: *"I need to stop
here and refocus on the actual request from the user"*, followed by a restatement of the prompt,
a restart, and truncation mid-row at *"Q1 | **922-day data hole** … 2019, 2020, **2023, 2024, 202"*.

**Assessment, factually:** the tables it did produce are accurate and correctly quoted — every one
is a restatement of a finding already in PART 7, including the five §7.10 corrections. **Findings
not already in the document: 0.** The mid-output collapse and self-address are the same failure
mode as round 6, caught later in the pipeline.

⭐ **Its one distinct contribution is a list of five items I had marked "should be queued" and had
not queued** (its I-series overlaps M26). That it surfaced by mechanical enumeration rather than
by analysis is the point: **a checklist beat my own follow-through.**

**❓ QUESTION BACK:** none. As in round 6, the most useful thing it could return is one
independent recomputation of a number in PART 1 or the M-tables.

---

## §8.7 · Claude — recomputed four things, was right about all four, and found six document defects

**✅ AGREED — CONFIRMED BY MEASUREMENT**

| Their recomputation | Verdict |
|---|---|
| *"charges = ₹15.33 + 22.225 bps × notional, residual ≤ ₹0.02"* | ✅ **M27 — exact.** Fitted independently: **₹15.34 + 22.225 bps**, residual ≤ ₹0.01 on 11 points. |
| *"delivery STT is 90% of the floor"* | ✅ **M28 — 20.00 of 22.22 bps = 90.0%.** And the intraday floor is **3.52 bps**, a 6.3× difference — **larger than your "roughly a quarter" estimate.** |
| *"922 days ≈ 620 sessions; 307 + 794 = 1,101"* | ✅ **M1.** |
| *"P(4 of 4 SHORT) = 0.0168, 1 in 60"* | ✅ with your stated model (with replacement). **Without replacement it is 0.0133, 1 in 75.** Either way the draw is unlikely — and **M33 shows the mechanism is not a draw at all.** |
| A7 (8 adopted, 2 queued) · A8 (Q-A/Q-B missing) · A9 (§2.4 uncorrected; beta untagged at line 286) · EX8 (3 empty falsifiers) | ✅ **M26 · M21 · M22/M23 · M25 — all four confirmed, including the exact line number.** |

⭐⭐ **A9's sharpest half is the one I would have missed: at 0.026%, the expected count in 487
panels is 0.127, so "0 of 487" was never evidence of "never scores."** That is a second,
independent refutation of the same claim — the original probe's *sample* was too small to
distinguish "never" from "rare" even before its mechanism was wrong.

⭐⭐ **BT7 — the correction is DELETION, not re-fill — is the most important structural point of
the round.** M8 (live raises) and M5 (backtest enters and books +4.211%) together mean the corpus
contains trades **that could not exist in any executable book**. So: removing them takes out
booked winners in one direction regardless of prevalence, **and** shrinks n. A prevalence
threshold is the right instrument for a magnitude error and the wrong one for a **population**
error. **ADOPTED**, and it is why item 6 now demands both treatments reported.

⭐ **BT8 — CONFIRMED and quantified (M30).** Short-side exposure is **19.83% vs 9.25%** at the
0.65% stop, 2.1× fatter — and **100% of the live book and 36% of minted signals are shorts.**
⚠ One refinement your reasoning did not predict: at the **median 5% stop the two tails are equal**
(0.331% vs 0.343%). The asymmetry is concentrated exactly where the defect bites hardest.

⭐ **Q8 — CONFIRMED with a magnitude (M32).** The pre-hole block carries **12.63% / 28.67%**
exposure against the post-hole **8.51% / 16.82%**. The 3.2-year window understates gap risk by
**~1.5–1.7×**. Your "+18.35 bps compounds to 3.84×" arithmetic is right as stated (it is the mean
overnight gap compounded, not a total return — worth saying so when it is quoted).

⭐ **EX6 — item 6 must precede item 5.** Correct: D5/D1 are trade-level and carry the fill defect;
E2 is panel-level and does not. The queue is reordered. ⭐ **EX7 — B7's MFE/MAE also inherits it**
and was in no re-run list. Both adopted.

**⛔ NOT AGREED**

- **D7's implication that the session counts indicate corruption.** **M29**: the six differing
  dates are all **special sessions** — Saturday budget/DR-site sessions and Muhurat. The counts
  differ for legitimate reasons. Your *consequence* stands (an inner join to the index table
  silently drops them) but the cause is benign.
- **D8's "M15 answers a different question".** Correct as stated, and I am adopting the
  distinction — but note your proposed test is now **superseded by M38**: rather than diffing a
  2020 bhavcopy against `stocks` to *measure* the survivorship hole, we can **fill the underlying
  gap**, which changes the question.

**❓ QUESTIONS BACK TO CLAUDE**

1. **M38 — NSE still serves 2021 and 2022 bhavcopy files (HTTP 200, correct schema).** The hole is
   not permanent. Does that make a final untouched holdout feasible again (your H4 said it was
   not, with one contiguous block), and if so would you take the holdout from **2021–22** (a
   different regime, newly available) or from the most recent sessions?
2. **M31 shows my own M7 cohort was ranked on 2026 liquidity** — Kimi caught it, you did not, and
   you recomputed four other things in the same document. Is there a general rule that would have
   surfaced it, beyond "check the cohort construction"? I ask because it is the class of defect
   your A7/A8/A9 are also instances of: the document asserting a property it never verified.
3. Your answer 3 proposed a mechanical rule — every count over time carries `min→max`, a distinct
   session count, and a gap flag above five sessions. **Adopted.** Should the flag threshold be
   sessions or calendar days? **M29** suggests sessions alone would miss the Muhurat/Saturday
   asymmetry between tables.

---

## §8.8 · Kimi K3 — asked the question that dissolved a month-old constraint

⭐⭐⭐ **DATA-1 IS THE FINDING OF THE ROUND, AND IT IS A QUESTION, NOT A CRITIQUE.** You wrote:
*"Can 2021–2022 daily bars be backfilled from NSE bhavcopy? If not, why not — and if it was never
attempted, why is the hole treated as permanent?"*

**M38: NSE serves them right now.** `sec_bhavdata_full_15062021.csv` → **HTTP 200, 233,986 bytes**;
`..._15032022.csv` → **HTTP 200, 246,024 bytes** — same header schema as today's file, same URL
template the ingestion service already uses (`bhavcopy_service.py:45`).

⚠ **CORRECTING MY OWN FRAMING BEFORE CREDITING YOURS.** It is not true that nobody considered
this. `CLAUDE.md` names the remedy explicitly — *"the blocker was never the CA source but 615
missing sessions (bhavcopy back-fill)"* — and round 8 then **DROPPED the 2021–23 back-fill on a
stated argument**: *"the 2021–23 back-fill is DROPPED, the lever is TURNOVER."* So it was a
decision, not an oversight, and I will not award a point for a question that was already answered.

⭐⭐ **What your question actually establishes is better than that: the constraint is REVERSIBLE,
and every reason for dropping it has since changed.** The drop was argued on *breadth* — that
more history buys fewer effective observations than faster turnover. Since then: **M32** shows the
retained 3.2-year block is a benign-regime sample (gap exposure **1.5–1.7× higher** in the
pre-hole block that contains COVID); **Claude's H4** argues a final untouched holdout is
impossible with one contiguous block; and every verdict in §2.4 is now scoped to that block. None
of those is a breadth argument. ⇒ **the back-fill should be re-decided on regime coverage and
holdout feasibility, which are not what it was rejected on** — and **M38 proves the option is
still open**, which nobody had verified. Filling it takes the sample from **1,101 → ~1,714
sessions (+56%)**.

⭐⭐ **SEL-3 is the second-best point of the round and it refutes my own method.** You wrote that
*"top-250 liquid" / "200 liquid names" have no stated point-in-time definition — a look-ahead
channel no reviewer named.* **Correct. M31:** my M7 cohort was ranked on `time >= '2026-01-01'`
liquidity and applied to 2023–2026. Re-run with a pre-window-only ranking, the long tail falls
**9.248% → 8.508%** and the short tail **19.830% → 16.822%**. **My own measurement carried the
defect class the document exists to hunt**, and eight reviewers across two rounds did not catch it.

⭐ **DATA-5 — CONFIRMED (M37).** `ohlcv_1d` is **not** back-adjusted anywhere; `ca_adjust.py` is
scoped to *open paper positions*. Drop-the-window is the only policy and it is applied
inconsistently. Your framing — that the document treats CA as a filter problem and never states
the adjust-vs-drop policy — is right, and the policy is now owed in writing.

⭐ **ARCH-2's census point** — *"how many other seed-bearing migrations are in this state"* — was
conceded in round 6 as un-enumerated and is **still** un-enumerated. An M26 instance.

**⛔ NOT AGREED, with the measurement**

- **STAT-8 — "with h=5d overlapping forward windows, naive intervals would be anti-conservative".**
  **REFUTED — M36.** `--stride` defaults to `HORIZON` = 5, so the grid is `sessions[::5]` and the
  windows **do not overlap**; the naive SE is correct. ⚠ **I nearly published your correction as
  fact** before reading the parameter — recorded in §8.0, because it is the exact failure this
  document keeps finding in others.
- **"The document's own evidence says Q-9 is item 1, not item 7."** The evidence is strong and
  **M28 strengthens it further** (the floor is statutory, so no execution work can go under it) —
  but Q-9 is a decision about whether to abandon a thesis, and that is the user's, not a queue
  item I can promote on my own authority. Recorded as the standing recommendation, at the top.

**❓ QUESTIONS BACK TO KIMI**

1. **M38 changes the shape of your STAT-1.** With 2021–22 fillable, should the CA-screened E2
   re-run wait for the larger sample (one run, 1,714 sessions, clean) or run twice (now on 794,
   again after the backfill)? Running now risks a third pass; waiting delays the only test that
   can settle the ranker.
2. Your SEL-3 generalises: **every cohort in this document may be look-ahead-constructed.** Is the
   right response a rule ("no cohort may be ranked on data inside its own measurement window") or
   an instrument (a helper that takes an as-of date and refuses otherwise)? I lean instrument,
   because M31 shows the rule alone did not survive contact with my own query.
3. **M37**: given the archive is unadjusted and drop-the-window is inconsistent, would you adopt
   **adjust** (back-adjust the archive from a CA table) or **drop** (screen every study) as the
   standing policy? Adjusting fixes every consumer at once and rewrites history; dropping is
   reversible and must be remembered every time.

---

## §8.9 · ⛔⛔ WHAT ROUND 7 COST ME — six defects in my own document, and one in my own method

Round 6 cost me five corrections. Round 7 cost seven, and **six of them are the same defect**:
the document decided something and then did not do it.

**1. ⛔⛔ Two of eight round-6 ADOPTIONS reached the queue (M26).** E1's relabel, MDE-beside-nulls,
bps-with-CI, the price-staleness counter, the t≈3.6 trial count and R-2's Minervini reframe were
all marked ADOPTED and none of them changed a line outside the section that adopted them.
⭐⭐ **This is `strategy_profiles` — marked applied, never ran — inside the document that diagnoses
it.** Three reviewers found it independently (Claude A7, Nemotron's I-series, Grok's C1 in part).

**2. ⛔ `§7.11/Q-A` and `Q-B` do not exist (M21).** Two adoptions point at null addresses. Both
are now real rows.

**3. ⛔ §2.4 still carried "0 of 487 panels" for `DOW_TREND` (M22)** — the claim §7.10 corrected
everywhere else. ⭐ And the sharper half, which I missed and Claude did not: **at 0.026% the
expected count in 487 panels is 0.127**, so that row was never evidence for "never scores" even
before its mechanism was refuted. **A sample that cannot distinguish "never" from "rare" was cited
as proof of "never" for eight days.**

**4. ⛔ §2.4's heading said "settled and should not be re-litigated" while §7.11 marked E2
re-run-required (M24, Grok C1).** Both were live in one document. The heading is now scoped.

**5. ⛔ `beta +0.92, alpha ≈ 0` is still untagged at line 286 (M23)** — §7.9 said it was tagged in
§7.10. It was not. Kimi flagged it in round 6, I agreed, and then did not do it.

**6. ⛔ Three of twelve queue rows had an empty falsifier (M25)** in a table whose stated purpose
is a falsifier per item — the contrast-ratchet shape again: *an instrument that only sees what
someone thought to list.*

**7. ⛔⛔ AND ONE THAT IS NOT A DOCUMENT DEFECT BUT A METHOD DEFECT — MINE (M31, Kimi SEL-3).**
My M7 cohort was *"top-250 liquid"* ranked on `time >= '2026-01-01'` and then applied to
2023-2026. **That is look-ahead inside a measurement I used to bound a defect's blast radius.**
Re-run point-in-time, the numbers move 8% and 18% relative. ⭐ **Eight reviewers over two rounds
read that query's description and none questioned the cohort; the one who did had not seen the
query at all.** Every M-number computed on a "liquid" cohort now carries its construction date.

⚠ **And the near-miss, recorded because it is the same class:** I computed an overlap-inflation
factor for E2's interval and was one step from publishing *"E2 flips to INCONCLUSIVE"* before
reading `--stride` (M36). **I would have corrected a correct thing.**

---

## §8.10 · THE QUEUE, REVISED AGAIN — reordered, re-falsified, and with the two null rows filled

⭐ Two structural changes this round: **item 6 moves above item 5** (Claude EX6 — re-running
trade-level studies on an unfixed engine guarantees a third pass), and **every falsifier that was
a prevalence percentage is now stated in R** (Grok's `exposure × 2R` identity).

| # | Item | Why now | FALSIFIER |
|--:|---|---|---|
| **1** | **The four SHORT positions — close them AND ship a directional restriction** | ⛔ **M35: no restriction anywhere refuses a short.** 13 registry entries, none directional. ⛔ **M34: only 4 of 15 live signals are CNC-holdable.** | If delivery shorts are representable in the intended account. ⚠ Needs the **account type**, which is not in the database — it is the user's to state (DeepSeek) |
| **2** | **Wire the ledger (M20)** + a backend wiring lint | Unchanged | A reconstruction drill succeeding from `positions`+`orders` alone |
| **3** | **Re-seed `strategy_profiles` idempotently** + **enumerate every other seed-bearing migration** (Kimi ARCH-2, still un-done) | 0 rows at head, ten days, four consumers | Consumers degrade safely *and* that is the spec |
| **4** | ⓘ **Fix `_simulate_trade`'s entry-bar gap — MOVED UP** (Claude EX6) | Trade-level studies must not be re-run on an unfixed engine | ⭐ **Grok's identity, not a prevalence %:** report the corpus's **stop-width distribution** first, then bias = `exposure × 2R`. **abs(bias) > 0.05R ⇒ headline invalid as cited; < 0.02R ⇒ footnote.** ⚠ Report **both treatments** — delete (Claude BT7: live would refuse these trades, so they are a *population* error) and re-fill-at-open. ⚠ Compute **per direction** (M30: shorts 2.1× at tight stops) |
| **5** | **Re-run E2 with a CA screen (M17)** ⚠ and only for that reason (M36 refutes the interval concern) | The central null's one confirmed contamination | Filtered 90% interval still excludes break-even ⇒ null hardens |
| **6** | **Re-run D5 + D1 + B7 with the CA screen, after item 4** | ⭐ **B7 added (Claude EX7): MFE/MAE is the statistic most corrupted by an entry booked below its own stop** | Signs and t hold ⇒ citable and closed |
| **7** | ✅ **DONE 2026-09-17 (PART 9)** — backfilled 2021–2022 from bhavcopy | ✅ **RAN: 1,101 → 1,723 sessions, +1,063,351 bars, largest gap now 5 days.** ⭐⭐ It bought **a zero-drift regime the archive did not contain (2022: −0.1%/yr, 42.7% down-days)** and **a genuinely untouched 620-session holdout**. ⚠ It did NOT buy a bear market — 2021 is +34.7%/yr | A sampled month fails to parse or returns EQ=0 under the A10 plausibility guard |
| **8** | ⓘ **Answer capital AND product from M27/M28** | Delivery floor **22.22 bps, 90% statutory STT**; intraday floor **3.52 bps**. ⚠ **Limit orders cannot go under a statutory floor** (Grok E4) | A gross edge estimate clearing ~24 bps on delivery, or ~5 bps intraday. ⚠ **F&O unpriceable — not modelled** |
| **9** | **Starvation registry + `categories`/`ledger_entries` (M19)** | Unchanged | A table in the registry that is empty-and-fine, showing the registry over-fires |
| **10** | **Directional entry zone** | Correctness, not P&L | ⭐ Replay the 45 `signal_outcomes` against a direction-aware zone: **0 differences ⇒ pure hygiene**, drop below item 12 |
| **11** | **U7 sector map — GATED on Gemini's kill test** | ⚠ **M2 bounds it**: 792 sessions, ~500 names | Sector-relative does not clear NIFTY50 ⇒ **drop U7** |
| **12** | **U5 runbook DR ordering; off-box backup; push** | One machine, one disk, 210 commits | ⭐ A restore drill on a second host reproducing PART 1's row counts |
| **Q-A** | ⓘ **NEW ROW (was a null pointer)** — **state the intended capital and account type** | Gates item 1's falsifier, item 8's arithmetic, and every power calculation | — it is a statement, not a test |
| **Q-B** | ⓘ **NEW ROW (was a null pointer)** — **build the experiment registry; recompute the t≈3.6 bar at the true trial count** | The bar was calibrated best-of-20; nobody knows k | True k ≈ 20 ⇒ the bar stands unchanged |
| **Q-C** | ⓘ **NEW — the six unqueued round-6 adoptions** (M26): relabel E1 · MDE beside every null · bps+CI beside every t · the price-provenance counter · R-2's reframe · **and adopt "every count carries its range"** (Claude) | They were decided and not done | — |

**Not doing, unchanged:** a ninth gate · flipping `market_regime`/`sector_rs` on restored data ·
the backward CA pass · a UI cockpit · the 1h backfill before a producer-of-record · **starting
cycle 2**, now blocked by item 1.

---

## §8.11 · What round 7 returned

**Decision-changing points: 8.** Kimi's M38 (the hole is fillable — ⚠ and my first write-up of it overclaimed; the back-fill was dropped deliberately in round 8, so what M38 establishes is that the option is still open and was never re-judged on regime coverage) and M31 (my cohort was
look-ahead) · Claude's M26/M21/M22/M25 (the document did not do what it decided), M28 (the floor
is statutory and product-specific), BT7 (deletion not re-fill), EX6 (reorder) · Grok's 2R identity
and M35/M33 (no directional restriction; the operator did not take the top) · ChatGPT's H4 (my
1% threshold was unjustified).

⭐⭐ **The two biggest came from a question and from a method audit, not from a critique of a
conclusion.** Kimi asked whether the source still had the data — the remedy was on record but its
availability had never been tested, and the reasons for dropping it had all expired. Kimi asked how
a cohort was built; it was built wrong, by me, in the measurement round that was supposed to be the
corrective.

⭐ **The round-6 rule needs amending.** It said: *send the numbers and ask for a recomputation.*
Round 7 shows the sharper version: **⛔ send the numbers, the QUERIES THAT PRODUCED THEM, and ask
what the query assumed.** M31 was invisible to everyone who saw only the number, and obvious to
the one reviewer who asked how the population was defined.

⚠ **And the standing warning is now about this document, not the system:** two rounds running, its
largest defect class has been *deciding something and not doing it.* §8.10's Q-C row exists so
that is measurable next round — if those six are still open, the adjudication process is
generating conclusions faster than the codebase absorbs them, and the correct response is to stop
running rounds.

---

# PART 9 — THE BACKFILL, EXECUTED (2026-09-17)

Queue item 7, run on the user's instruction. **This is the first action in this document that
wrote to the database**; everything before it was read-only.

## §9.1 · What ran, and what it produced

`scripts/backfill_ohlcv_history.py --start 2020-12-24 --end 2023-07-02 --sleep 1.0` — the
purpose-built script, which already existed and was **idempotent, resumable and
`ON CONFLICT DO NOTHING`**. 654 weekdays requested, ~30 minutes, 1s between requests. **652 ingested · 1 holiday (404) ·
**1 FAILED — 2022-08-08**, and the failure is a finding in its own right (§9.5).

⭐ **The 307 pre-2021 sessions turned out to be an interrupted earlier run, not a boundary.** The
script's defaults are `--start 2019-10-01 --end 2023-07-02`; something stopped it at 2020-12-23
and the resulting edge was later reasoned about as though it were a property of the archive.

| | before | **after** |
|---|---|---|
| sessions | 1,101 | **1,723** |
| span | 2019-10-01 → 2026-09-17 | 2019-10-01 → 2026-09-17 |
| **largest gap** | **922 days** (2020-12-23 → 2023-07-03) | **5 days** ×2 — 2022-04-13 (Ambedkar Jayanti + Good Friday + weekend, legitimate) and 2022-08-05, which is the **gap's START**; the failed session is **2022-08-08** (§9.5 — mislabelled here until M61) |
| bars | 2,095,287 | **3,158,638** (+1,063,351) |
| distinct names with bars | 3,387 | **3,402** |
| `stocks` total | 3,395 | **3,415** |
| `stocks` **active** | 2,299 | **2,299 — unchanged** |
| `stocks` inactive | 1,096 | **1,116** (+20 historical names) |

**Sessions per year** ⛔ **RESTATED 2026-09-17 (M61): this table summed to 1,723 and the archive is
1,727** — it predated the four weekend sessions PART 10 recovered. Current `[measured 2026-09-17]`: 2019 **61** (Oct start) ·
2020 **252** · 2021 **248** · 2022 **247** · 2023 **245** · 2024 **249** · 2025 **249** · 2026 **176**
— **total 1,727**, reconciling to M44. ⚠ A per-year table is exactly the artifact §9.6 says must
reconcile to its total, and this one did not for a day.

⭐ **Survivorship was the point, not a side effect.** The run used `historical=True`, so a symbol
the bhavcopy names but today's master has never heard of is **created as an inactive historical
stock**. Twenty such names were created; **the active set was not touched**, which also confirms
the `is_active` single-writer trigger held (it is `BEFORE UPDATE`; these are `INSERT … ON CONFLICT
DO NOTHING`).

## §9.2 · ⭐⭐ What it bought: a zero-drift regime, which the archive did not previously contain

Measured with a cohort ranked **only on 2019-10 → 2020-10** and applied forward — the
point-in-time construction M31 forced on us, so this number does not repeat that defect.

**Equal-weight daily return of the PIT cohort — "the tape":**

⛔ **SUPERSEDED BY M52 (Claude A12).** The cohort below was ranked on 2019-10 → 2020-10 and applied
to blocks *including* that window, so the COVID row is hindsight-constructed. The strictly-prior
re-run is **M52**: 2021 **+35.5%/yr** · **2022 −3.7%/yr, 43.5% down-days** · 2023-07→now
**+12.8%/yr**; long-side gap exposure **2022 14.36% vs 8.58% retained = 1.67×**. ⚠ The COVID block
is **not PIT-computable** — the archive starts 2019-10-01. The conclusion survives; this table does
not.

| block | sessions | mean/day | sd | down-days | worst day | annualised |
|---|--:|--:|--:|--:|--:|--:|
| 2019-10 → 2021-01 (COVID) | 311 | **+0.1303%** | 1.702 | 38.3% | **−12.61%** | **+38.1%** |
| 2021-01 → 2022-01 | 247 | **+0.1202%** | 1.071 | 39.3% | −5.08% | **+34.7%** |
| ⭐ **2022-01 → 2023-01** | **246** | **−0.0006%** | 1.219 | **42.7%** | −6.00% | **−0.1%** |
| 2023-01 → 2023-07 | 121 | +0.0626% | 0.684 | 43.0% | −1.87% | +16.8% |
| 2023-07 → 2026-09 (**the old sample**) | 793 | +0.0526% | 1.021 | 42.0% | −6.87% | **+13.9%** |

⭐⭐ **2022 is a flat-to-bear year — 246 sessions at −0.1% annualised with 42.7% down-days — and
the archive did not contain one.** Every previous verdict was measured on samples running at
+13.9% to +38.1% annualised. This is the sample that was missing.

⇒ **Grok's F5 is now answerable.** Its warning was that an imported filter (Minervini, 12-month
momentum) *"will look like edge in a bull tape, and with only 3.2 contiguous years there is no
bear-regime sample to falsify against."* There is now: **2022**.

⇒ ⭐⭐ **And a genuinely untouched holdout exists for the first time.** Claude's H4 and ChatGPT's
Q8 both argued a final holdout was infeasible with one contiguous block. **2021-01 → 2023-07 (620
sessions) has never been seen by any study, script, or reviewer in this programme** — not because
it was reserved, but because it did not exist in the database until today. That is the strongest
form of untouched a holdout can have.

## §9.3 · What the backfill also changes, measured

**Overnight-gap exposure, same PIT cohort, by block** — the input to queue item 4's falsifier:

⛔ **REPLACED IN PLACE 2026-09-18 by M69** (Claude A27: the old rows were superseded by
cross-reference while this section still said "the input to queue item 4's falsifier").
**Estimator, named: strictly-PIT annual top-250 cohort — year Y ranks on calendar year Y−1 only —
with a GLOBAL `lag()` so no per-block seam artifact can arise. 1,727 sessions.**

| block | n | long stop-side ≤−0.65% | ≤−5% | short stop-side ≥+0.65% | ≥+5% |
|---|--:|--:|--:|--:|--:|
| **WHOLE archive** | **405,426** | **10.07%** | **0.470%** | **21.76%** | 0.322% |
| COVID block (2019-10→2020-12) | 61,959 | 13.94% | **1.625%** | 31.91% | 0.884% |
| holdout 2021-01→2023-07-02 | 149,811 | 10.20% | 0.216% | 22.79% | 0.204% |
| test 2023-07-03→ | 193,656 | **8.72%** | **0.297%** | **17.70%** | 0.233% |

✅ **Blocks tile exactly (difference 0)** ⇒ M58's 479 confirmed as a seam artifact by an independent
construction. ⚠ The COVID row excludes 2019-Q4, which has no prior year to rank on.
⭐ **And a cohort effect nobody asked about: on ALL names with a prior close** (3,162,898 name-days)
the whole-archive tails are **13.15% / 34.49%** — so the top-250 cohort **understates the live
2,291-name universe's exposure by 1.31× long and 1.59× short.**

⛔ Superseded rows, kept so the change is auditable: FULL 403,979 / 9.84% / 0.469% / 21.20% ·
COVID 77,277 / 12.45% / 1.470% · restored 147,824 / 10.03% / 0.193% · old sample 178,399 / 8.57%.

⛔ **The retained sample was the mildest of the three on every measure.** Against the full archive
it understates the long stop-side tail by **1.15×**, the short by **1.25×**, and the extreme
(≤−5%) tail by **1.77×**. ⇒ **item 4's exposure figures must be recomputed on the full archive**,
and any risk number sourced from the 3.2-year block is a benign-regime number.

⚠ **What it did NOT buy, stated so nobody claims it later:** the restored block is *also* a rising
tape overall (2021 at +34.7%). The archive gained **one flat year and 626 sessions** (⛔ restated 2026-09-18 — this line said **620**, a second instance of the staleness M61 corrected at "622" one paragraph later), not a bear
market. The only crash regime remains COVID, which was already there.

## §9.4 · Consequences that are now owed

1. ⛔ **FIVE study scripts hardcode `_CLEAN_SINCE = 2023-07-03`** (⛔ restated 2026-09-18, M71 — this line said *four*; `confirmation_base_rate.py` was missed) — `tp_geometry_study.py`,
   `squeeze_study.py`, `confirmation_base_rate.py`, `rvol_factor_study.py`. That constant *was*
   the data boundary; it is now an **undeclared deliberate truncation** discarding **626** sessions (1,727 − 1,101; the figure was
   622 before the weekend recovery — M61).
   ⚠ **Deliberately not changed here:** two of them are already queued for a CA-screened re-run,
   and the window is a separate decision from the screen. **Whoever re-runs them must decide the
   window explicitly.** ⭐ And the name is doubly wrong — the "CA-clean" claim was already refuted.
2. ✅ **The gap guard self-heals.** `observed_session_index` runs `SELECT DISTINCT time::date FROM
   ohlcv_1d` with no cache, so every consumer of the session calendar picked up 2021–22
   immediately. Windows that were dropped for straddling the hole will now be admitted — correct,
   and it means **study output produced before today is not comparable with output produced
   after**.
3. ⚠ **`nse_holidays` holds 49 rows, 2023-08-15 → 2026-12-25 — no coverage for 2021–22.**
   Historical studies use the observed-session calendar rather than that table, so the exposure is
   limited, but any calendar arithmetic over the new years is unguarded.
4. ⚠ **`gen_walkforward_goldens.py` reads the dev DB** and its comment reasons from "the dev corpus
   starts 2023-07-03". The committed goldens are unaffected (the test DB is separate and was not
   touched), but **regenerating them now would produce different fixtures**. Not a break; a trap.
5. ⚠ **Prices remain CA-UNADJUSTED**, and over 7 years there are far more splits and bonuses than
   over 3.2. M37 established there is no back-adjustment anywhere and drop-the-window is the only
   policy. **The CA screen is now more load-bearing, not less.**

## §9.5 · ⛔ The one failed session, and what it exposes

**2022-08-08 failed, deterministically**, with `Error: new-line character seen in unquoted field`.
Retried alone: **fails identically.** Diagnosed:

```
GET .../sec_bhavdata_full_08082022.csv  ->  HTTP 200, 233,582 bytes
first bytes: PK\x03\x04          # ZIP magic
zip entries: [Content_Types].xml, xl/workbook.xml, xl/worksheets/sheet1.xml, ...
```

⇒ **NSE published that date's bhavcopy as an XLSX workbook at the `.csv` URL, with HTTP 200.** It
is not a transient fetch error; the archive has served the wrong file type for that date since
2022 and will keep doing so.

⭐ **This is A10's defect class, on a path A10 never covered.** A10 hardened the *universe* CSV
download against "a 200 OK that is not the file" after measuring that 4 of 7 failure bodies parsed
to an empty set and reported success. **The bhavcopy downloader has no equivalent check** — no
content-type assertion, no magic-byte test, no row-count floor.

✅ **It failed loudly here only by accident of the CSV parser raising.** A ZIP whose bytes happened
to parse as degenerate CSV would have ingested **zero rows and reported success** — the exact
shape of the `EQ=0` header bug and the `sync_instruments` login interstitial, both of which this
project has already been bitten by. ⇒ **queue: give `bhavcopy_service` the A10 treatment.**

⛔ **The session is NOT recovered, deliberately.** Extracting it means a bespoke XLSX path inside
an otherwise clean CSV pipeline, for **one session in 1,724 (0.06%)**, existing for exactly one
date in history — a parallel implementation (W2) with a permanent maintenance cost and no
generalisable benefit. **Recorded as a known one-session hole at 2022-08-08**, which is one of the
two 5-day gaps measured above; the other (2022-04-13) is legitimate holidays.

⚠ **And it corrects my own first report of this run**, which said "zero failures" — it was 652
ingested, 1 holiday, **1 failed**. The script's report file said so and I read the console summary
instead. Corrected in all four documents.

## §9.6 · ⭐ A false claim found in the earlier run's own report

`docs/analysis/ohlcv-backfill-2026-09-07.md` carries an update dated 2026-09-08:

> *"a subsequent run extended coverage past this recovery snapshot all the way to the archive
> floor. Live `ohlcv_1d` now spans **2019-10-01 → 2026-09-04** — 1,093 trading days … **The full
> ~7-year Q5 target is met**."*

⛔ **It was not met, and the report contains its own refutation.** A 2019-10 → 2026-09 span is
~1,730 sessions; the same sentence reports **1,093**. The 637-session shortfall — the 922-day hole
— is visible in the two numbers printed side by side, and it stood unexamined for nine days while
the hole was reasoned about as a property of the archive.

⭐⭐ **That is precisely the defect Claude found in PART 1 of this document a week later** (M1: a
span quoted without a reconciling session count), and it had already happened once, in the report
of the run that created the gap. ⇒ **the "every count carries its range" rule adopted in §8.9 must
also mean: a span and a count that disagree is an alarm, not a pair of facts.**

---

# PART 10 — THE ROUND-8 PANEL (2026-09-17)

Seven responses: **ChatGPT · Gemini · DeepSeek · Grok · Nemotron 3.5 lightning · Claude · Kimi K3.**

⚠ **A timing problem that shapes everything below: these were written against the document as it
stood BEFORE the backfill.** Three of them (ChatGPT P5, Claude S12, Grok's holdout protocol) argue
*do not ingest 2021–22 until the holdout is sealed*. The user instructed the backfill and it ran.
§10.10 deals with that squarely rather than around it.

## §10.1 · The round-8 measurement round

| ID | Question | Result `[measured 2026-09-17]` |
|---|---|---|
| **M39** | Claude's D11 — is `ohlcv_1d` missing 3 of the 6 special sessions? | ⭐⭐ **YES, exactly.** Missing **2024-03-02, 2025-02-01, 2026-02-01** — and these are **real sessions**: `ohlcv_5m` holds **4,242 / 15,600 / 15,675** rows on them. **He derived this from three published session counts (792/794/796) and "exactly 6 dates", without seeing the data.** My round-7 "explainable, benign" verdict was wrong. |
| **M40** | Root cause? | ⛔ **`_weekdays()` filtered `d.weekday() < 5`** — Mon–Fri. NSE's Saturday special sessions were **structurally unreachable: the request was never made**, so the 404-handling the function relies on never ran. NSE serves all three (**1,783 / 2,007 / 2,411** EQ rows). |
| **M41** | Is the defect only in the backfill? | ⛔⛔ **No — it is live and system-wide.** Every Celery beat is `day_of_week="1-5"`, so a Saturday session is invisible to EOD ingestion, nightly generation and every health probe **as they run**. |
| **M42** | Fixed? | ✅ Enumerator corrected, **3 regression tests**, 16 green. Re-run over the full span recovered **2020-02-01 (+1,461)**, **2024-03-02 (+1,783)**, **2025-02-01 (+2,007)** — including a Saturday that was not in the original six. |
| **M43** | ⛔⛔ And then my own fix was wrong. | **2026-02-01 is a SUNDAY on which NSE traded** (Budget day): `ohlcv_5m` holds **15,675 rows**, the archive serves it. My fix asserted *"Sunday stays excluded: NSE has never held one"* **and pinned it in a test** — reproducing the defect being fixed, one weekday over. The enumerator now **asserts nothing**: every calendar day is offered and the 404 decides. **+2,411 bars.** |
| **M44** | Archive now | **1,727 sessions · 3,166,300 bars · 2019-10-01 → 2026-09-17.** (1,101 before any of this.) |
| **M45** | Kimi A2.2 — is E2's SE blind to cross-sectional dependence? | ✅ **REFUTED by construction.** `e2_score_ic.py` computes `_spearman` **per session** (`for v in by_day.values()`), collects into `ics`, then `_mean_se(ics)` = mean ± sd/√n_sessions. **That is Fama–MacBeth** — each date contributes one observation, so same-date dependence is fully absorbed. Kimi even named the correct remedy; the code already does it. |
| **M46** | Kimi A2.3 — is the IC on the absolute score, hiding a signed relationship? | ✅ **REFUTED — and the error that produced it is MINE.** The IC loop runs on `key="score"`, labelled **"signed normalized_score ← PRE-REGISTERED"**. The *absolute* score appears only in the `E[z-selected]` constant, with a comment explaining why. **My round-7 answer to Grok mis-described my own script**, and Kimi built a finding on my error. |
| **M47** | Claude Q18 — do M33 and M34 share a population? | ⛔ **No, and he derived it from 4 + 14 = 18 > 15.** M33 ranked **all 50 signals**; the four positions came from the **2026-09-15 cohort of 12** (3 BUY / 9 SELL). Only **2** signals that day scored above the best acted-on — **both BUY**. |
| **M48** | The corrected probability | ⛔⛔ **P(4 of 4 SELL, given the 09-15 cohort) = 0.2545 = 1 in 3.9 — unremarkable.** My round-7 "1 in 60 / 1 in 75" used the wrong population. **The inference is WITHDRAWN.** |
| **M49** | So what did the operator do? | Within the 12: skipped **both** higher-scoring BUYs (78, 77); took 4 SELLs but **not the top 4** — among **five tied at 76 took two, skipped three**; among two at 75 took one; among two at 74 took one. ⇒ **not rank, not strictly direction.** Arbitrary-among-ties survives, on a population of **12, not 50**. |
| **M50** | Claude BT12 — is "6.3× lower" the right number at ₹1 lakh? | ⛔ **No — 2.88×** (he predicted 2.90×). 6.3× is the asymptotic ratio. ⭐ **And a result neither of us predicted: intraday is FLAT at 10.6 bps from 2 positions onward** (percentage brokerage below the ₹20 cap, no fixed charge), while delivery rises 23.8 → 60.5. ⛔ **CORRECTED (M59): the ratio is U-SHAPED, not widening — 2.88 → 2.39 → 2.53 → 2.67 → 2.82 → 3.54 → 5.71.** The minimum is at **two** positions, and at the 3–4 names S2 called viable the advantage is ~2.5×, not 5.71× |
| **M51** | Kimi A2.7 — is the gap bias 2R? | ⛔⛔ **WITHDRAWN 2026-09-18 by M64 — this is the bias in NO unit any study computed.** D1/D5/positional all divide by the **fill**-referenced risk and the fill *is* the gap open, so an affected trade books **exactly +1.0000R at every gap size**. Below is the superseded statement. ~~CONFIRMED. bias = gap ÷ stop_distance~~; Grok's 2R is the special case gap = 2 × stop. The M5 repro (gap 5%, stop 1%) is **5R**, not 2R. At the p10 0.65% stop, a 2% gap is **3.08R** and a 5% gap is **7.69R**. |
| **M52** | Claude A12 — did M32 reintroduce the look-ahead M31 removed? | ⛔ **YES.** M32 ranked on 2020-01 → 2023-07 and applied it to 2019-10 → 2020-12 — a window that **overlaps and post-dates** the measurement. ⭐ **Redone with strictly-prior expanding cohorts, and the conclusion survives on better ground:** 2021 **+35.5%/yr**, **2022 −3.7%/yr with 43.5% down-days**, 2023-07→now **+12.8%/yr**; long-side gap exposure **2022 14.36% vs retained 8.58% = 1.67×**. ⚠ The COVID block is **not PIT-computable** — the archive starts 2019-10-01, so there is no prior data to rank on. |

---

## §10.2 · ChatGPT — right about the sequence, and it caught a date error

**✅ AGREED** — its re-ordering (account correctness → simulator → clean E2 → D5/D1/B7 → data →
economics) matches where the queue already moved, and its **P4 (point-in-time cohort helper as an
executable API, not a documentation rule)** is the correct escalation of Kimi's SEL-3. **M52 is the
proof**: I adopted the rule in writing and violated it in the next row of the same table.

⭐ **The date error is real and now fixed.** Nine instances of `2026-09-18` in a document whose
convention is that every measurement carries its date. Corrected across four files.

⭐ **Q6 — "the 3.2-year sample is a benign-regime sample" is stronger than the supplied evidence.**
Conceded and now repaired: M32's support was hindsight-constructed (M52). The claim survives on
2022 with a strictly-prior cohort, and I have added the down-day and drift figures it asked for.

**⛔ NOT AGREED**

- **"P5 — backfill, but re-decide rather than automatically doing it."** Overtaken: the user
  instructed it. ⚠ Your *reason* was sound and is answered in §10.10.
- **Q1's "do not use the 1% threshold"** — already replaced by Grok's R-based identity in round 7,
  and now superseded again by **M51**: the bias is `gap ÷ stop`, so even Grok's 2R is a special
  case. Your instinct was right twice over; the instrument is now on its third revision.

**❓ QUESTIONS BACK TO CHATGPT**

1. **M50**: intraday's cost advantage is **2.88× at one position and 5.71× at twenty-five**,
   because intraday has no fixed charge. Delivery's cost argument pushes toward concentration;
   intraday's removes the penalty for breadth entirely. Does that change your P6 ("establish actual
   portfolio economics") from one question into two — *how much capital* and *which product* —
   answered in that order?
2. Your A4 proposes CI-checking that every ADOPTED item has a code/doc change or a `BLOCKED`
   status. **M52 shows a rule can be adopted and violated in the same document by its author.**
   Would your CI check have caught that, or does it only catch un-actioned adoptions rather than
   mis-applied ones?

---

## §10.3 · Gemini — a third faithful restatement, and the pattern is now the finding

**✅ AGREED** — every quote is accurate; the 14 sections reproduce the document correctly.

**⛔ NOT AGREED — nothing, for the third round running.** Every item restates a finding already in
the document, including several of my own corrections quoted back as discoveries (its §12 items are
§7.10/5 and §7.10/1 verbatim). **Findings not already in the document: 0**, across rounds 6, 7 and 8.

⚠ **Stated without complaint, because it is informative:** three rounds of faithful restatement is
evidence the document is *readable and internally consistent* — a real property, and one no other
source tests. But it is not review, and I will stop asking this source for findings and start
asking it for the one thing it demonstrably does well: **checking whether the document says what I
think it says.**

**❓ QUESTION BACK TO GEMINI** — the U7 kill-rule you supplied in round 6 is still the only reviewer
artifact from any round that converted an open item into a falsifiable test, and it still has **no
threshold** (Grok flagged this: "a kill-rule without a threshold cannot kill"). One number, please:
what sector-vs-NIFTY50 IC separation would you accept as a pass, on 792 sessions and ~500 names?

---

## §10.4 · DeepSeek — the index is now complete, and that is its ceiling

**✅ AGREED** — A1–A10, Q1–Q12, D1–D15, B1–B10, S1–S10, E1–E7, H1–H12, F1–F15, L1–L14 are accurate
and correctly keyed to the M-numbers. As a navigable index of a 1,600-line document it is the best
of the seven and it improved this round (it now keys to M-IDs rather than prose).

**⛔ NOT AGREED — the request list is now entirely retrospective.** All twenty items ask me to
re-show measurements already in the document with their queries attached. Round 6's list named five
things I had not measured; round 8's names zero. ⭐ Its one live item remains **"show the account
type configuration"** — which is Q-A, is not in the database, and is the user's to state.

**❓ QUESTION BACK TO DEEPSEEK** — you asked in round 7 whether I would add a *"whose data
constructed this, and was that construction point-in-time?"* column. **M52 says yes and proves why:
I violated my own new cohort rule one row after adopting it.** Would you put that column on the
M-table (per measurement) or on the queue (per item)? I lean M-table, because the defect is always
in the measurement, never in the intention.

---

## §10.5 · Grok — the 2R identity it supplied is superseded by a sharper one

**✅ AGREED** — its answers to my three round-7 questions are all adopted: clickability logged as
**fields on the ledger write** rather than a third writer; per-direction reporting for the gap
bias; and Q-8 hardened rather than softened until Q-A is answered.

⭐ **Its holdout protocol (E2 on the 794 first, *then* fill, then 2021–22 as holdout, no retune) is
the right sequence and I ran the fill first.** §10.10.

⭐ **"Limit orders cannot go under a statutory floor"** stands and is reinforced: **M50** shows the
floor is a *product* property, and no execution technique moves it.

**⛔ NOT AGREED, with the measurement**

- **The `exposure × 2R` identity you supplied — which I adopted into the queue — is a special
  case.** **M51**: bias = `gap ÷ stop_distance`, and 2R holds only when the gap is exactly twice
  the stop. The M5 repro is **5R**. Your instrument was a large improvement on my unjustified 1%
  and is still not the right one; the threshold must be computed from the **joint** distribution of
  gap depth and stop width, which is what item 4 already asks for and then does not use.
- **Your reading of M33 ("the operator took 4 mid-ranked and skipped every better-scored one")**
  inherits my denominator error. **M47/M48**: the pool was **12**, not 50; 4-of-4 SELL is **1 in
  3.9**. Your "clickability" hypothesis survives — **M49** shows two of five signals *tied at 76*
  were taken — but the evidence for it is much weaker than either of us stated.

**❓ QUESTIONS BACK TO GROK**

1. **M49**: among five signals tied at confidence 76, two were taken. There is no rank information
   in a tie, so *something* broke the tie. Is a ledger-attached `surface` + `displayed_rank` still
   sufficient, or does a tie mean you also need the **sort key's tiebreaker** (which today is
   `id`, i.e. mint order) recorded?
2. **M50**: at one position intraday is 2.88× cheaper; at twenty-five it is 5.71×. Your Q-8 ruling
   was "hard until Q-A". Does the *shape* of that curve change the ruling — since delivery makes
   concentration mandatory and intraday makes it optional?

---

## §10.6 · Nemotron 3.5 lightning — third consecutive output failure

Round 6 produced planning text; round 7 produced tables and then broke mid-output; round 8 is
planning text again — a restatement of the prompt, a list of sections it intends to fill, an
inventory of quotes it might use, and an internal note (*"Actually, this is going to be extremely
long. Let me think about how to approach this efficiently"*), terminating mid-sentence inside the
architectural section.

**Findings produced: 0. Verdicts: 0. Tests proposed: 0.** Nothing to agree or disagree with.

⚠ Three attempts, three failures of the same kind, is now a measurement rather than an accident:
**this source cannot complete a task of this length.** Recorded so it is not re-tried a fourth time
expecting a different result, and so its silence is never counted as agreement.

---

## §10.7 · Claude — three independent recomputations, all three landed, and one inverted my conclusion

⭐⭐ **D11 is the most impressive single deduction of any round.** From three published session
counts (792 / 794 / 796) and the statement that exactly 6 dates differed, it derived that
**`ohlcv_1d` must be missing 3 of them** — without the data. **M39 confirms it exactly**, and
**M40/M41** found the cause: a Mon–Fri enumerator, and the same filter on every Celery beat. My
round-7 verdict that the discrepancy was "benign" was wrong, and this defect is now fixed, tested
and back-filled (M42).

⭐⭐ **A12 is confirmed and it is the sharpest methodological catch so far: M32 reintroduced the
look-ahead M31 had just removed, one row later in the same table.** The ranking window
(2020-01 → 2023-07) overlapped *and post-dated* the block it was applied to (2019-10 → 2020-12).
**M52** redoes it with strictly-prior expanding cohorts — and the conclusion **survives on better
ground**: 2022 is **−3.7%/yr with 43.5% down-days**, and its long-side gap exposure is **1.67×**
the retained sample's. ⚠ Its other half is also right: the COVID block is **not PIT-computable at
all**, because the archive starts 2019-10-01.

⭐⭐ **Q18's denominator catch (4 + 14 = 18 > 15) inverts one of my conclusions.** **M47/M48**: the
population was the 09-15 cohort of 12, not all 50 signals, and P(4-of-4 SELL) is **1 in 3.9** —
unremarkable. **My "1 in 60" and the inference built on it are withdrawn.**

⭐ **BT12 confirmed at 2.88%** (predicted 2.90×), with **M50**'s addition that intraday is flat in
breadth.

⭐ **Q14 (§2.4's preamble still says "nothing in the data restoration changes any of them")** —
conceded and now false in a second way: the restoration this round added 626 sessions and a
zero-drift year. Rewritten to scope the table explicitly.

**⛔ NOT AGREED**

- **M28's component list "sums to 22.39, not 22.22".** The components were each rounded to 2 dp;
  summed unrounded they give **22.225**, matching M27's fit exactly, and the DP term belongs to the
  fixed ₹15.34, not the linear coefficient. The presentation was sloppy; the number was not.
- **"M29's benign verdict"** — you are right that it was wrong, but note the failure was *mine*,
  not the instrument's: the four-table join **did** surface the six dates. I stopped at "special
  sessions" instead of asking which table lacked them.

**❓ QUESTIONS BACK TO CLAUDE**

1. **M43 is the finding I most want your read on.** Fixing D11 I asserted *"Sunday stays excluded:
   NSE has never held one"* and pinned it in a test — and 2026-02-01 is a Sunday session already
   sitting in our own `ohlcv_5m`. **I reproduced the exact defect I was fixing, one weekday over,
   inside the fix.** The enumerator now asserts nothing and lets the 404 decide. Is
   "assert nothing about a calendar you do not own" the general form, or is there a stronger rule —
   something like *a filter over a domain owned by an external authority is always a bug*?
2. Your adjective rule ("liquid", "top-250", "active" are unverified claims standing in for dated
   rules) predicts M52. **It did not predict M43**, where the suspect word was a *weekday name*.
   Does the rule extend to calendar predicates, or is that a second class?
3. **M50**: does intraday being flat in breadth while delivery is not change your S2 conclusion —
   which said the cost floor "fixes the concentration" — into something stronger, i.e. that the
   product choice *determines whether breadth is available at all*?

---

## §10.8 · Kimi K3 — one confirmed, two refuted, and one of the refutations is of my own error

⭐⭐ **A2.7 is CONFIRMED and it is the round's best quantitative correction.** The per-event bias is
`gap ÷ stop_distance`, not a flat 2R; the M5 repro books **5R**. At the p10 stop a 2% gap is
**3.08R**. ⇒ **the 0.05R invalidation threshold trips earlier than the adopted identity implies**,
and item 4's falsifier is now on its third revision (my 1% → Grok's 2R → your ratio).

⭐ **The epistemic preamble is fair and correct:** everything here is self-attested by one operator,
and M52 is this round's proof that the operator's own measurements carry the defects they hunt.

**⛔ NOT AGREED, with the code**

- **A2.2 — "stride fixes time overlap; it does nothing for same-date cross-sectional dependence".**
  **REFUTED — M45.** The script computes the IC **per session** and then takes mean ± sd/√n over
  sessions. That *is* the Fama–MacBeth estimator you recommend; each date contributes exactly one
  observation, so same-date dependence is absorbed by construction.
- **A2.3 — "the IC is on the absolute score, so a signed relationship is invisible".**
  **REFUTED — M46, and the error is mine.** The IC runs on the **signed** score, labelled
  `← PRE-REGISTERED`; the absolute score appears only in `E[z|selected]`. **I mis-described my own
  script in a round-7 answer and you built a finding on it.** The finding is void; the underlying
  concern — that nobody had stated the estimand precisely — was legitimate and is now answered.

**⚠ NEEDS PROOF** — A4.7 (the 1,975-trade corpus's construction is unspecified) is correct and
unanswered. Given M16 and M37, your prior (membership-repainted and CA-contaminated until shown
otherwise) is the right default.

**❓ QUESTIONS BACK TO KIMI**

1. **M51 makes your formula the falsifier.** To use it I need the **joint** distribution of gap
   depth and stop width in the 1,975-trade corpus, not the marginals. Is `E[gap/stop | gap > stop]`
   the right summary, or would you want the full bivariate because the tail is where it bites?
2. Two of your three new statistical points were refuted by the code, and **one of them only
   because I had described my own script wrongly to a reviewer**. Does that change your view on the
   packet problem — i.e. is the fix "attach the scripts", or is it that any claim I make *about*
   the code should be quoted from it rather than paraphrased?

---

## §10.9 · ⛔⛔ WHAT ROUND 8 COST ME

**1. ⛔⛔ I reproduced the defect I was fixing, inside the fix (M43).** Correcting a Mon–Fri filter,
I asserted *"Sunday stays excluded: NSE has never held one"* — and pinned it in a **test**.
2026-02-01 is a Sunday NSE session whose bars were **already in our own `ohlcv_5m`**. ⭐ The general
form now in the code: **a filter over a calendar owned by an external authority is a claim you
cannot verify — offer every day and let the 404 decide.**

**2. ⛔⛔ M32 reintroduced the look-ahead M31 removed, one row later (M52, Claude A12).** The
cohort rule was adopted in §8.9 and violated in §8.1 of the same document.

**3. ⛔⛔ My "1 in 60" short-book inference is WITHDRAWN (M47/M48, Claude Q18).** Wrong population;
the correct figure is **1 in 3.9**.

**4. ⛔ I mis-described my own script to a reviewer (M46)** — said the IC was on the absolute score
when it is on the signed score — and a reviewer built a finding on it.

**5. ⛔ "Benign" was the wrong verdict on M29 (M39).** The join surfaced the six dates; I stopped
one question short of asking which table lacked them.

**6. ⛔ Nine wrong dates (ChatGPT)**, in a document whose central convention is that every
measurement carries its date.

⭐ **The pattern across rounds 6–8 is now stable and worth stating plainly: the reviewers'
highest-value output is not finding defects in the system — it is finding defects in my
measurements of the system.** Every round, the largest correction has been to my own work.

## §10.10 · The holdout, and a sequencing criticism that landed after the action

Claude's S12, Grok's protocol and ChatGPT's P5 all say: **decide and seal the holdout before
ingesting.** The user instructed the backfill; it ran; then I measured 2021–22.

**What was actually done to the new data:** descriptive regime statistics only — mean daily return,
down-day share, overnight-gap tail frequencies (§9.2, M52). **No scorer, no signal, no strategy,
no parameter, and no model has touched 2021–22.**

⚠ **What that costs, stated honestly:** I now know 2022 was a down year with fatter gaps, and I
used that to argue the backfill was worthwhile. A later "discovery" that something works in 2022
would be mildly contaminated by my having chosen to highlight it. That is real, and it is smaller
than a strategy evaluation would have been.

⇒ **SEALING RULE, pre-registered now, before any strategy evaluation touches it:**

1. **2021-01-01 → 2023-07-02 is the REGIME HOLDOUT — 617 sessions** (⛔ stated as 620 until M54;
   248 + 247 + 122). ⚠ **313 further sessions (2019-10 → 2020-12, the only crash regime) are in
   NEITHER the holdout nor the test block** — unsealed and unused (M55). No scorer run, no gate
   evaluation, no parameter fit, no study may read it until a result on the 794-session post-hole
   block has been **committed first**.
2. **E2's CA-screened re-run happens on the 794 block and is committed before the holdout is
   opened** — Grok's protocol, adopted late but intact.
3. **Opening the holdout is a one-way door**: it is read once, for a pre-registered question, with
   no retune afterwards.
4. **Descriptive statistics already taken are recorded** (§9.2, M52) so nobody later mistakes the
   holdout for pristine.

## §10.11 · Queue changes from round 8

| # | Change | Why |
|---|---|---|
| **4** | ⓘ **Falsifier revised a third time**: bias = `gap ÷ stop_distance` (M51), computed from the **joint** distribution of gap depth and stop width, **per direction**. Report `E[gap/stop]` conditional on gap > stop, alongside the marginals | My 1% → Grok's 2R → Kimi's ratio |
| **5** | ⓘ **Must complete and be committed BEFORE the holdout is opened** (§10.10) | Grok's protocol |
| **7** | ✅ **DONE** — and extended: 3 Saturday + 1 Sunday special sessions recovered (M42/M43) | |
| **NEW 13** | **Change the Celery beats from `day_of_week="1-5"`** so a Saturday/Sunday session is ingested live | **M41** — the backfill is fixed; the live path is not. ⚠ A scheduling change on a running system: the user's call |
| **NEW 14** | **A point-in-time cohort helper** — `liquid_as_of(date)` that refuses an `as_of` inside its own measurement window | **M52**. ChatGPT P4, Kimi, Grok all converged; and a prose rule demonstrably failed within one document |
| **Q-C** | ⓘ **Widened** to every concession in PARTS 7–8, not just the six round-6 adoptions, and **given a falsifier**: the same greps that produced M26 return zero | Claude A13/A14 |

## §10.12 · What round 8 returned

**Decision-changing points: 6.** Claude's D11 (a live ingestion defect, derived from arithmetic),
A12/Q18 (two of my measurements refuted), BT12 · Kimi's A2.7 (the falsifier, again) · ChatGPT's
date catch and Q6 · plus **M43**, which is mine and is the one I would keep if I could keep only one.

⚠ **Three of the six are corrections to my own measurements, and a fourth (M43) is a defect I
introduced while fixing a defect.** The system's defect rate is not what these rounds are measuring
any more.

---

# PART 11 — THE ROUND-9 PANEL (2026-09-17)

Six responses: **ChatGPT · Gemini · DeepSeek · Grok · Claude · Kimi K3.** (Nemotron did not respond.)

⭐ **Two sources did independent arithmetic on PARTS 9–10 and found seven errors in them. All
seven are mine.** That is now the third consecutive round in which the panel's highest-value output
was a defect in my measurements rather than in the system.

## §11.1 · The round-9 measurement round

| ID | Question | Result `[measured 2026-09-17]` |
|---|---|---|
| **M53** | Claude A17 — the range holds 657 weekdays; the run reported 654. Were 3 never requested? | ✅ **Explained, benignly.** The 3 are **2021-06-14/15/16**, my own `--limit 3` smoke run, already complete when the full run started (`_already_done` excluded them). They hold 1,540 / 1,539 / 1,538 bars. **Not a second instance of M40.** ⛔ But Claude's deeper point stands: **the report printed 654 against a 657-weekday range and reconciled neither** — the §9.6 alarm shape, in the run that fixed §9.6's cause. |
| **M54** | The holdout's exact size, before sealing | ⛔ **617 sessions, not 620.** 2021 = **248** · 2022 = **247** · 2023-01→07-03 = **122**. My 620 was an estimate in a quantity about to be pre-registered. |
| **M55** | Claude Q20 — what is in neither the holdout nor the test block? | **313 sessions** (2019-10-01 → 2020-12-31). Blocks tile exactly: **313 + 617 + 797 = 1,727** ✅. ⇒ **the only crash regime in the archive is in neither block — unsealed and unused**, while item 5 is specified on the 797-session post-hole block. |
| **M56** | Kimi 9.5 — PART 1 says 48 signals / 22 active; M12 says 50 / 23 | ⛔ **50 / 23 is current.** PART 1's row was measured earlier the same day and never restamped — the exact defect the "every count carries its range" rule exists to catch, in the table that adopted it. |
| **M57** | ⭐⭐ Kimi 3.8 — the backfill was validated by **counts**, never by **values**. Are the 1.06M bars right? | ⭐⭐ **VALIDATED: 4,974 of 4,974 stored closes match exactly (100.00%, 1bp tolerance).** Method: the bhavcopy publishes `PREV_CLOSE`, a column **we never ingest**, on the *following* session's file. Compared our stored close for session N−1 against it for 2021-06-16 (1,533), 2022-03-16 (1,648), 2022-11-10 (1,793). ⛔⛔ **RESTATED 2026-09-18 by M66: this check is not merely untested for corporate actions, it is INCAPABLE of seeing one.** `PREV_CLOSE` is the same unadjusted series — measured on 8 boundary events incl. IRCTC −77.9%, BAJAJFINSV −89.6%, PEL −44.8%, it matched our stored close on **8 of 8**. ✅ **Superseded as the validation of record by M65**, which compares all five fields against the SAME day's own file: **4,981 of 4,981 name-days, 100.00%, 0 rows absent** — including `open`, the field the entire gap analysis is built on. |
| **M58** | Claude D15 — the three blocks sum to 479 less than the archive | ✅ **A `lead()` boundary artifact, reproduced exactly.** Re-run: full archive 404,903 vs blocks 77,527 + 147,824 + 179,073 = 404,424 — **difference 479 again**. Each block's `lead()` cannot see across its own boundary, so the last session of each loses its gap observation: 2 internal seams × ~240 names. **Not missing data.** |
| **M59** | Claude BT16 — is M50's ratio monotonic in breadth? | ⛔ **No — it is U-shaped with a minimum at 2 positions.** Measured: **2.88 → 2.39 → 2.53 → 2.67 → 2.82 → 3.54 → 5.71** at 1/2/3/4/5/10/25. **My "the ratio widens with breadth" is wrong**, and it is wrong in the range S2 identified as viable: at 3–4 positions the advantage is ~2.5×, near the minimum. |
| **M60** | Claude Q21 — how many R definitions are live? | ⛔ **Three.** In the M5 repro the engine books (99−95)/95 = **+4.211%**. Referenced to the **actual entry** (abs(95−99)) that is **+1R**; to the **signal-referenced stop distance** (100−99 = 1) it is **+4R**; and M51's `gap ÷ stop` = **5R** is the *swing* from an intended −1R, not the booked value. **Item 4's falsifier is stated in R and R is not defined.** |
| **M61** | Document staleness Claude found by arithmetic | ⛔ All three confirmed: §9.1's per-year table sums to **1,723** when M44 says **1,727** (stale by the four sessions the same document recovered); "**622 sessions**" should be **626** (1,727 − 1,101); and the gap label calls **2022-08-05** "the one failed session" when the failure is **2022-08-08** (08-05 is the gap's *start*). |

---

## §11.2 · ChatGPT — right that the process is now the bottleneck

**✅ AGREED.** Its framing is the sharpest statement of where this stands: *"the trading system itself is
getting cleaner faster than the evidence supporting its trading edge."* And its five-field
requirement — **population query + as-of date + measurement window + raw input snapshot + code
version** — is the correct generalisation of M31, M43, M46 and M48, which it correctly identifies as
one defect rather than four: *"the research system records results more reliably than it records the
exact semantics of how those results were produced."*

⭐ **Q5 (its holdout reclassification) is adopted.** "Strategy-blind, descriptively-seen" is more
honest than "untouched", and **M55 sharpens it further**: the seal covers 617 sessions while 313
sessions of the only crash regime sit in neither block.

**⛔ NOT AGREED** — its **P0 ordering (account/product first)** conflicts with Grok's
**product-then-capital**, and Grok has the better argument: at ₹10 lakh a CNC book still cannot beat
~22 bps of STT, so product decides whether the question is economic at all and capital only sizes it.
**M59** supports Grok: the product gap is narrowest (~2.4–2.7×) exactly in the 3–4 position range.

**❓ QUESTIONS BACK** — (1) Given **M55**, should item 5's E2 re-run use 797 sessions or 1,110
(797 + 313)? Your Q3 asks for the dependency map but not the window. (2) Your five-field requirement
implies a schema. Should it live on the M-row, as DeepSeek suggested, or in a sidecar the scripts
write themselves?

## §11.3 · Gemini — fourth faithful restatement, zero new findings

**✅ AGREED** — every quote accurate across 14 sections. **⛔ Findings not already in the document:
0**, for the fourth consecutive round. Its §12 again quotes my own corrections back as discoveries.

⚠ As stated in round 8, I will stop asking this source for findings. **The U7 kill-rule threshold has
now been owed for four rounds** and both Grok and I have flagged that a kill-rule without one cannot
kill. **Grok supplied a candidate in this round** — *"sector IC 90% CI entirely above NIFTY50 IC"* —
so unless Gemini objects, that becomes the threshold by default.

## §11.4 · DeepSeek — complete, accurate, and now purely retrospective

**✅ AGREED** — A1–A10, Q1–Q10, D1–D12, B1–B10, S1–S8, H1–H12, F1–F15, L1–L12 all key correctly to
the M-numbers. **⛔ All twenty requests ask me to re-show measurements already in the document.**

⭐ Its one live contribution is the **"whose data constructed this, and was it point-in-time?" column**
— which **M54 and M56 now argue should be two columns**: construction *and* as-of. Adopted into the
five-field requirement above.

## §11.5 · Grok — withdrew its own instrument, and its product-first ruling is now measured

⭐⭐ **It withdrew the 2R identity it supplied in round 7** — *"2R is withdrawn. M51 is right."* Two
rounds running, Grok has supplied an instrument and then retired it on evidence. That is the
behaviour the panel is for.

⭐ **Product-then-capital is adopted over ChatGPT's capital-then-product**, and **M59 strengthens it
while correcting its arithmetic**: the CNC/intraday ratio is **U-shaped**, minimum **2.39× at two
positions**, so at the 3–4 names S2 identified the advantage is ~2.5×, not the 5.71× the tail implies.

⭐ **Its Q-CC-35 (index/VIX for 2021–22) is the right unanswered question** and I have not run it.
M38 answered it for *equity* bhavcopy only; the index/VIX path is a different file and a different
service. **Queued.**

**⛔ NOT AGREED** — its **H2** says 2022 "cannot kill a 'works except crashes' story". Correct, and
**M55 makes it sharper than Grok had it**: the crash regime exists (313 sessions) and is in neither
the holdout nor the test block, so it *can* be used — nothing forbids it.

**❓ QUESTION BACK** — given M55, does the 313-session COVID block become (a) part of item 5's test
set, (b) a second holdout, or (c) left unsealed and unused? My lean is (b): it is the only crash
sample, and spending it on a CA-screen re-run wastes it.

## §11.6 · Claude — seven arithmetic findings, all correct, all mine

⭐⭐ **The strongest single contribution of any round.** Every one of A17, Q23, D15, BT16, Q21, and
the three staleness items was derived from published numbers, and **all seven are confirmed**
(M53–M61). Two deserve special note:

- **BT16 (M59)** — I wrote "the ratio widens with breadth" and it **narrows first**. Claude
  reconstructed the whole curve from two of my numbers and found the minimum at two positions.
- **Q21 (M60)** — **three R definitions are live and item 4's falsifier is denominated in R.** A bias
  of 0.04R under one definition is 0.2R under another, against a 0.05R threshold. The instrument has
  a sharper formula and a *less determinate unit* than when it started. **This blocks item 4.**

⭐ **Its answer to my M43 question is better than my own rule.** I wrote "assert nothing about a
calendar you do not own"; Claude's version generalises and keeps the necessary envelope:
**"a predicate that encodes an external authority's behaviour must be a cache of that authority's
answers, not a rule you evaluate — if the authority changed its mind tomorrow, would this code find
out?"** ⭐⭐ And it dissolves my adjective rule into the same law: *"the predicate is evaluated here
and the truth lives there."* That covers M31, M52 **and** M43, and predicts the next three:
`EQ_LISTED`, the F&O flags, and `nse_holidays` with its 2023-08 floor. **Adopted as the standing rule.**

**⛔ NOT AGREED** — **A17 has a benign explanation** (M53): the three weekdays were my own smoke run.
The reporting defect it identifies is real; the second-instance-of-M40 hypothesis is not.

**❓ QUESTIONS BACK** — (1) **M55**: 313 unsealed crash sessions. Second holdout, or test set?
(2) You say define R once in code. Should R be **entry-referenced** (what the trade actually risked)
or **signal-referenced** (what the plan risked)? They differ by exactly the chase, which is a
measured effect here. (3) Your envelope clause bounds the request space "by something cheap and
defensible". For `EQ_LISTED` the envelope is the whole listed universe — is the cache-not-rule law
still tractable there, or does it need a staleness budget instead?

## §11.7 · Kimi K3 — the value-validation question, and the sharpest single new finding

⭐⭐⭐ **3.8 is the most valuable question of the round and its answer is good news.** Kimi observed
that every verification in §9.1–9.3 was a count and that, given the source demonstrably serves wrong
file types, count-level validation is insufficient. **M57: 4,974 of 4,974 stored closes match the
independently-published `PREV_CLOSE` exactly.** The backfill is value-validated, not just
count-validated. ⚠ With the caveat Kimi would want stated: no CA boundary fell in the sample, so the
check's CA-detection arm is untested.

⭐⭐ **7.6 is the sharpest new finding in the round: "pre-registration" rests on local, unpushed,
mutable git timestamps.** E2's null is citable *because* it was pre-registered in a commit — and with
nothing pushed, that reduces to my word. **This is the strongest argument yet for the push**, and it
reframes item 12 from disaster-recovery to **evidentiary integrity**.

⭐ **2.7 — the "88% tape, not alpha" framing is contradicted by its own decomposition.** Gross alpha
is **−0.0218%**, so the book loses *before any cost*. ⇒ **cost reduction (R-6, limit orders) cannot
rescue it; it can only reduce the loss.** Adopted, and R-6 is reclassified.

⭐ **2.5 (per-direction IC), 3.2 (dividend contamination below the 25% screen), 4.3 (no spread/impact
model anywhere), 10.4 (the live phase cannot validate the strategy, only the plumbing)** — four new
items, all cheap, none previously named. ⭐ **10.1 is the one I would act on first: the programme has
a falsifier for every item and none for itself.**

**⛔ NOT AGREED — 2.5 should not be run now.** Splitting E2's IC by direction is one line, but running
any E2 variant before the CA screen is pre-registered is exactly the sequencing error the sealing
rule exists to prevent. **It becomes a pre-registered arm of item 5**, not an ad-hoc run.

**❓ QUESTIONS BACK** — (1) Your 2.1 power note derives that the re-run can only resurrect the ranker
if the cleaned IC reaches **~0.050**, seven times the current estimate. Should that be pre-registered
as item 5's *interpretation* bar, so the result is read against it rather than after it? (2) **3.2**:
should the dividend screen be a second threshold (say 0.5%) on the same `|move|` test, or a join to
an ex-date table we do not have?

---

## §11.8 · ⛔⛔ WHAT ROUND 9 COST ME — seven errors, all arithmetic, all in PARTS 9–10

**1. The holdout is 617 sessions, not 620** (M54) — in a quantity about to be pre-registered.
**2. "The ratio widens with breadth" is wrong** (M59) — it narrows first, minimum at two positions,
and the error is in the range S2 called viable.
**3. Item 4's falsifier is denominated in an undefined unit** (M60) — three R definitions live.
**4. §9.1's per-year table is stale by four sessions** (M61) — the four the same document recovered.
**5. "622 sessions" should be 626** (M61).
**6. The gap label names the wrong date** (M61) — 2022-08-05 for a failure on 2022-08-08, in a
document that had just corrected nine date errors.
**7. PART 1's signal row was stale within the same day** (M56) — 48/22 against 50/23.
**8. ⚠ And while writing correction #4 I stated the repaired per-year figures BEFORE measuring
them.** They turned out right — the four recovered sessions fall in 2020, 2024, 2025 and 2026, so
the derivation was sound — but the rule is measure-then-state, and I inverted it inside the
correction of a staleness defect. Now `[measured]`: 61 · 252 · 248 · 247 · 245 · 249 · 249 · 176 =
**1,727**.

⭐ **And two things I got right that are worth recording because they were challenged:** the backfill's
**values** are correct (M57, 100% against an independent field), and the three-block partition is
**complete** (M58, the 479 is a `lead()` artifact, not missing data).

⭐⭐ **The generalisable rule, from Claude, replacing two of mine:**
**a predicate that encodes an external authority's behaviour must be a CACHE of that authority's
answers, not a RULE you evaluate.** Test: *if the authority changed its mind tomorrow, would this
code find out?* This covers the cohort rule (M31/M52), the calendar rule (M43), and predicts
`EQ_LISTED`, the F&O flags and `nse_holidays`.

⭐ **And from ChatGPT, the instrument that would have caught four of this round's seven:** every
measurement records **population query · as-of date · measurement window · input snapshot · code
version**. M31 passed because the number looked reasonable and the population was future-aware; M60
passes today because the number looks reasonable and the unit is undefined.

## §11.9 · Queue changes from round 9

| # | Change | Why |
|---|---|---|
| **4** | ⛔ **BLOCKED until R is defined once, in code** (M60) | The falsifier is in R and three R definitions are live |
| **5** | ⓘ **Window must be stated: 797 or 1,110?** (M55) | 313 crash sessions are in neither block, unsealed and unused |
| **5b** | ⓘ **NEW ARM — per-direction IC** (Kimi 2.5), pre-registered, not run separately | One line; never run; bears on the account problem |
| **5c** | ⓘ **NEW — pre-register the interpretation bar** (Kimi 2.1): the cleaned IC must reach **~0.050** to resurrect the ranker | So the result is read against a bar set before it |
| **10** | ⓘ **Holdout restated: 617 sessions**, and the seal is a **whitelist** (Claude S14) — permitted: row/session counts, integrity checks. Everything else forbidden | M54; and §9.3's gap tabulation already read it under a blacklist |
| **NEW 15** | **Give `bhavcopy_service` the A10 treatment** — named in §9.5, never queued (Claude D17, DeepSeek L3) | It guards the daily path |
| **NEW 16** | **Adopt a CA policy: adjust or drop**, and make every study declare which (Claude A20, Kimi 3.1) | Items 5 and 6 both depend on it; the backfill made it more load-bearing |
| **NEW 17** | **Measure spread and impact** (Kimi 4.3) | Named twice, measured never; plausibly larger than the 22 bps statutory floor on the illiquid half |
| **NEW 18** | **Index/VIX for 2021–22** (Grok Q-CC-35) | M38 answered equity only; `market_regime` stays a 792-session object until this is run |
| **NEW 19** | **A project-level kill criterion** (Kimi 10.1) | Every item has a falsifier; the programme has none |
| **R-6** | ⓘ **Reclassified**: limit orders reduce loss, they do not create edge (Kimi 2.7) | Gross alpha is **−0.0218%** — negative before any cost |
| **12** | ⓘ **Re-scoped**: the push is **evidentiary**, not just disaster recovery (Kimi 7.6) | "Pre-registered in a commit" is worth only the operator's word while nothing is pushed |

---

# PART 12 — THE ROUND-10 PANEL (2026-09-18)

## §12.1 · What arrived, and what was stale

Seven responses. **Five are current. Two were written against an older copy of this document and
must be read as such** — that is not a criticism of the reviewer, it is a fact about which artifact
they were given, and it changes what their findings are worth.

| source | standing | new, decision-changing |
|---|--:|---|
| **Claude** | current; recomputed PART 11 independently — **7 checks, all reproduce** (M58 with a noted total drift) | **5** (A22, A23, D20, Q28, H23) |
| **Kimi** | current | **3** (E2's panel construction, the cost model fitted to itself, tax) |
| **Grok** | current | **2** (delete-first unblocks item 4; PREV_CLOSE is the same unadjusted series) |
| **ChatGPT** | current | 1 (softened-wording table) |
| **DeepSeek** | current; high-fidelity restatement | 1 (the 0.5%–25% band request) |
| **Gemini** | ⛔ **round-8 vintage** — asks whether to backfill before re-running E2; the backfill ran 2026-09-17 | 1 (the 30 bps position cap — and it reproduces) |
| **Nemotron** | ⛔ **round-6/7 vintage** — quotes `ohlcv_1d` at 1,101 sessions and restates M33, **withdrawn by M47/M48** | 0 |

⚠ Kimi's and Nemotron's replies each arrived **twice** in the paste (Nemotron's truncated both
times). Treated as one each.

## §12.2 · What I measured before answering anybody

| # | Question | Result |
|---|---|---|
| **M62** | Kimi 2.4 — what universe does `e2_score_ic.py` score, and as of when? | ⛔⛔ **`load_frames` ranks the top 250 by median `close*volume` over `now() - 180 days`** — i.e. **2026-03 → 2026-09** — and applies it to panels from 2023-07-03. A PIT cohort as of 2023-07-03 shares **164 of 250 (65.6%)**; as of 2021-01-01, **135 (54.0%)**. **61 of the 250 (24.4%) have no bar before 2021-01-01.** |
| **M63** | Kimi 2.3 — where is break-even IC = 0.0310 derived? | ✅ **It is derived, in the pre-registration**: `E[excess\|selected] ≈ IC · σ_cs · E[z\|sel]` against 25.5 bps, with a σ_cs table (5% → 0.0225, 7% → 0.0161). ⛔ **It appears nowhere in THIS document** — Kimi is right about the artifact they were given. |
| **M64** | Grok Q-CC-37 / Claude q8 — which R do the closed studies compute? | ⭐⭐ **All of them compute FILL-referenced R.** `tp_geometry_study:155`, `rvol_factor_study:99`, `positional_probe:167` all divide by `abs(entry_price − stop)/entry_price`, and `_simulate_trade:212` sets `entry_price = fill_candle["open"]`. **Executed: the entry-bar gap books exactly +1.0000R at every gap size** — 2%, 5%, 10%, 20% ⇒ +1.0000, +1.0000, +1.0000, +1.0000. |
| **M65** | Claude D20 — validate `open`, not just `close` | ✅ **All five fields, 4,981 name-days, 100.00%.** 2021-06-15 (1,539) · 2022-03-15 (1,648) · 2022-11-09 (1,794); open/high/low/close/volume each matched the same day's own bhavcopy; **0 rows absent from the file**. |
| **M66** | Claude D21 vs Grok D1 — is `PREV_CLOSE` CA-adjusted? | ⛔ **Grok is right.** 8 boundary events incl. IRCTC −77.9%, BAJAJFINSV −89.6%, PEL −44.8%: **`PREV_CLOSE` matched our unadjusted stored close on all 8.** It is the same unadjusted series ⇒ **M57's check is not "untested" for CAs, it is structurally INCAPABLE of seeing one.** |
| **M67** | Claude H25 — is the special-session class closed? | ✅ **Yes, by a second instrument.** Over the overlapping window: **1** date in `ohlcv_5m` not in `ohlcv_1d` (**2026-09-18 — today**, mid-session) and **1** the other way (**2024-11-01 Muhurat**, already documented in M29). |
| **M68** | Claude A24 — smoke-run provenance | ⛔ **Refuted.** **7 of the 20** backfill-created historical names have bars on 2021-06-14/15/16, and the distinct-symbol counts sit exactly on the local trend: 1541 · 1540 · 1540 · **1540 · 1539 · 1538** · 1485. No deficit. |
| **M69** | Claude D19 — §9.3 on the 1,727-session archive | See §12.3. PIT top-250: whole archive **405,426** name-days, long ≤−0.65% **10.07%**, ≤−5% **0.470%**, short ≥+0.65% **21.76%**. **Blocks tile exactly (difference 0)** under a global `lag()` ⇒ M58's 479 confirmed as a seam artifact by an independent construction. |
| **M70** | Claude Q27 / Kimi 3.2 / DeepSeek 16 — the move distribution | Of 3,162,898 name-days: **>5% = 6.78%**, >10% = 1.12%, **>25% = 0.068%**, and **76.24% fall in the 0.5–25% band the screen never touches**. |
| **M71** | Claude q9 — `_CLEAN_SINCE` consumers | ⛔ **FIVE, not four** (§9.4 said four): `tp_geometry_study` · `squeeze_study` · `confirmation_base_rate` · `overhead_supply_study` · `entry_confirmation_study`. |
| **M72** | Claude H23 / q7 — is the E2 pre-registration commit signed? | ⛔ **No.** `git log --format=%G?` on `fe5d508` returns **`N`** — no signature, no third-party timestamp. |
| **M73** | Kimi — is tax anywhere? | ⛔ **Nowhere.** No hit for STCG / capital gains / `tax` in `app/`, `scripts/`, or this document. |
| **M74** | Kimi 4.2 — has `fees.py` been reconciled to a contract note? | ⛔ **No.** One aspiration line in the 09-10 adjudication ("Reconcile the fee model to contract notes, daily"). M27 fitted a line to `fees.py`'s **own output**. |
| **M76** | Claude D22 — `nse_holidays` as a cache | ⓘ **Half-refuted, and the correct statement is sharper.** A36 `calendar_health.py` alarms on the **forward** horizon (`coverage_end`) via a daily beat. There is **no backward floor**. And `market_calendar.py:166` already records the table is **wrong**, not merely absent, for 2019–20: **7 rows against ≥17 holidays**. |
| **M77** | Gemini — cap positions to keep friction under 30 bps | ✅ **Confirmed, boundary located.** Delivery bps at ₹1L: 1→**23.76**, 2→25.29, 3→26.88, 4→28.36, 5→**29.89**, 6→**31.52**, 25→**60.55**. **Crosses 30 bps between 5 and 6.** 1→25 = **+36.79 bps** (Gemini said 36.7). |
| **M78** | Claude A23 — are the three standing concessions in any queue section? | ⛔ **Zero, zero, zero.** *portfolio* · *entry_diversity* · *modelled/calibration* appear **0 times** across §7.11, §8.10, §10.11, §11.9. |
| **M79** | Claude Q28 — yield vs document growth | Lines written / corrections to my own numbers: round 6 **630 / 5**, round 7 **437 / 7**, round 8 **328 / 6**, round 9 **201 / 8** ⇒ **0.79 → 1.60 → 1.83 → 3.98 self-corrections per 100 lines.** |
| **M80** | Kimi 1.4 — is gate configuration versioned? | ⛔ **No table exists** matching `%config%`/`%setting%`/`%gate%`. A past signal cannot be attributed to a configuration. |
| **M81** | Kimi q8 — overlap correction in the closed studies? | ⛔ **None.** Neither `tp_geometry_study` (D5), `rvol_factor_study` (D1) nor `b7_hazard` imports `newey_west_t` or `block_bootstrap`. |
| **M83** | Kimi 3.6 — historical-name completeness | 0 orphan `stock_id`s. **2,107 distinct names traded in 2021–22; 1,492 (70.8%) are active today** ⇒ **615 (29.2%) cannot enter E2's cohort at all.** |
| **M84** | Nemotron E5's proposed test | ⛔ **Unrunnable.** `signal_outcomes` has neither `acted_on` nor `confidence`. |

## §12.3 · Claude — adjudicated

**Recomputation.** 6 of 6 arithmetic checks reproduce exactly, including the three-block tile and
the M59 curve. M53's explanation is accepted and the second-instance hypothesis correctly withdrawn.

| point | verdict |
|---|---|
| **A22** — no single current queue; it is a base table plus three patch sets | ✅ **Taken.** ~24 items across four sections. §12.12 publishes **one table**; the delta sections become history. |
| **A23** — three concessions in no queue section | ⛔⛔ **CONFIRMED by M78: 0, 0, 0.** Q-C was widened to "every concession in PARTS 7–8" and its falsifier never enumerated them. Now enumerated. |
| **A24** — smoke-run provenance unchecked | ⛔ **REFUTED by M68.** 7 of 20 historical names have bars on those dates; symbol counts sit on the local trend. A well-posed question with a clean negative answer. |
| **Q25** — 5c pre-registers one bar for three arms whose bars differ | ✅ **Taken, and it is the right order of operations.** The bar is `break-even + 1.645·SE`, and SE depends on the window and the split. **Register the FORMULA, not the number.** |
| **Q26** — item 8's falsifier needs a positive gross edge; the only estimate is −2.18 bps | ✅ **Taken.** Item 8 is now explicitly **downstream of items 4, 5, 6**. |
| **Q27** — dividend contamination is directional and sits where the analysis is most sensitive | ⓘ **Half-confirmed, and M66 makes it worse than stated.** The screen touches **0.068%** of name-days while **76.24%** sit in the untouched 0.5–25% band. But the ex-date count needs a CA source we do not have — see §12.7. |
| **Q28** — the panel's yield tracks document growth, not defect rate | ⛔⛔ **WITHDRAWN 2026-09-18 (round 11, Claude Q29): M79 REFUTES this, it does not confirm it.** corr(lines, corrections) = **−0.837**; proportionality predicts 5 → 3.5 → 2.6 → 1.6, observed **5 → 7 → 6 → 8** while volume fell 3.1× ⇒ the absolute defect count is flat-to-rising and the yield is NOT a volume artifact. Superseded statement follows. ~~CONFIRMED with M79's number~~ — 0.79 → 1.60 → 1.83 → **3.98** self-corrections per 100 lines. ⭐ **And round 10 breaks it**: M62 is a defect in a script, found because one reviewer asked *"show me the population query"* rather than *"recompute the table"*. **That question shape is the finding.** |
| **D19** — §9.3 is stale and feeds item 4 | ✅ **Taken; recomputed as M69.** ⚠ My re-run is **not** the same estimator (annual PIT cohort, global `lag()`), so the +924 Claude computed is against M58, not against M69. |
| **D20** — M57 validated `close`; the gap analysis uses `open` | ⭐⭐ **The best request of the round, and it passed: M65, all five fields, 4,981/4,981.** Cheaper than M57 and it covers everything. |
| **D21** — re-run M57 at a CA boundary | ⛔ **Test design refuted by M66.** The premise ("if `PREV_CLOSE` is adjusted and our close is not") is false — both are unadjusted. |
| **D22** — `nse_holidays` is a cache with no as-of | ⓘ **Sharpened by M76:** it has a **forward** horizon alarm (A36) and **no backward floor**, and is measured **wrong** for 2019–20 (7 rows vs ≥17 holidays). |
| **BT19** — item 4's block has no owner or definition of done | ✅ **Taken and RESOLVED** — see §12.7/M64. |
| **BT20** — §9.3's restored row reads holdout data under the old blacklist | ✅ **CONFIRMED, and I did it again this round**: M66's CA census queried 2021-01→2023-07. Recorded, per §10.10, as a permitted integrity read. |
| **BT21** — NEW 17 has no falsifier | ✅ **Taken**, with Claude's own threshold: *median half-spread on the tradability-screened subset below 5 bps ⇒ spread is not binding.* |
| **S17** — 797 is a default nobody chose | ✅ **Taken and DECIDED this round** (§12.7). And M71 says the constant is in **five** scripts. |
| **S18** — the cohorts in current use are still unrederived | ⭐⭐ **CONFIRMED far beyond what was claimed — M62.** |
| **EX15 / EX16** | ✅ Both taken. Execution items are loss-reduction; stated once in §12.12. |
| **H23** — pushing secures the NEXT pre-registration, not E2's | ⛔⛔ **CONFIRMED by M72: `fe5d508` is UNSIGNED.** E2's null is **operator-attested** and will remain so. Label changed. |
| **H25** — are the four recovered sessions the whole class? | ✅ **CONFIRMED CLOSED by M67**, via a second instrument. |
| **H26** — the holdout has no opening condition | ✅ **Taken; the condition is written in §12.12.** |

## §12.4 · ChatGPT — adjudicated

Correctly identifies that the research machine is now the dominant risk, and its five-field
manifest remains the single most reusable proposal any reviewer has made. Specifics:

- ✅ **The softened-wording table is adopted almost entirely** — it is the cheapest correctness
  work available. "Ranker is dead" → **"not supported on the current measured block; CA-clean **and
  PIT-cohort** re-run required"** (M62 adds the second clause ChatGPT could not know about);
  "holdout untouched" → **"strategy-blind, descriptively-seen"**; "backfill validated" → now
  **"all five fields validated on 4,981 name-days; CA boundaries structurally unseeable (M66)"**.
- ✅ **E1's TOST** — accepted; an accepted null is not equivalence.
- ⛔ **"Define CA policy: `CA_POLICY = DROP | ADJUST`"** — taken, but M66 shows the choice is not
  binary in the way stated: **a drop rule keyed on `|move|` is not a CA detector.** See §12.7.
- ⓘ **"Push establishes the pre-registration boundary"** — **M72 refutes the retrospective half**
  exactly as Claude's H23 did. It establishes future ones.
- ✅ **Entry-price provenance by rung** — still unmeasured, still queued; ChatGPT is right that it
  is a research-validity question and not only a UI one.
- ⛔ **"Do not turn on `market_regime` or `sector_rs` merely because the data exists"** — agreed,
  and note the data does **not** exist: index/VIX remain a 792-session object (NEW 18).

## §12.5 · Gemini — adjudicated (round-8 vintage)

Its framing question — *"should the full bhavcopy backfill be executed before re-running the
CA-filtered E2?"* — **was executed on 2026-09-17**, before this reply was written. Its M38/M13/M34/
M17/M28 restatements are correct but superseded. Its "1,714 sessions" is now **1,727**.

⭐ **What survives, and it is its best contribution in five rounds:** *"moving from 1 to 25 positions
dilutes net expectancy by 36.7 bps in friction alone. Position count should be capped at 3–5 to keep
friction under 30 bps."* **M77 reproduces both numbers**: +36.79 bps, and the 30 bps line falls
**between 5 and 6 positions**. ⭐ It independently supports a decision already taken on unrelated
grounds — D4's **max-concurrent-position cap of 3** (26.88 bps), built 2026-09-08 for concentration
reasons. Cost and risk agree.

⛔ **The U7 kill threshold Gemini has owed for four rounds did not arrive again.** Grok's candidate
becomes the default by forfeit (§12.7).

## §12.6 · DeepSeek — adjudicated

The most faithful restatement yet — A1–A10, Q1–Q12, D1–D11, B1–B10, S1–S10, E1–E7, H1–H14, F1–F16
with verbatim quotes, each falsifiable and each with a test. **Its accuracy is high and its novelty
is near zero**: I can find no row that is not already in PARTS 7–11. Two exceptions and one error:

- ✅ **Request 16 — the `|move|` distribution 0.5%–25%** — run as **M70**, and it is the sharpest
  number behind the CA-policy decision: **76.24% of name-days sit in the band the screen never
  touches, and the screen itself fires on 0.068%.**
- ✅ **Request 20 — a programme falsifier** — answered in §12.12 (NEW 19).
- ⛔ **Q10 is a misreading.** *"The '88% tape, not alpha' framing is contradicted by its own
  decomposition."* It is not contradicted — it **is** the decomposition: raw −0.1877% = tape
  −0.1659% + alpha −0.0218%. Both statements are true simultaneously; 88% of the loss is tape **and**
  alpha is negative. No contradiction exists.
- ⚠ "209 commits ahead" is stale — **215**.

## §12.7 · Grok — adjudicated

The round's most decision-dense reply, and **it wins both of its head-to-head disagreements.**

**⭐⭐ 1. The 313-session block: Grok (Holdout-2) vs Claude (test set). GROK WINS, and the
adjudication is arithmetic, not taste.**
Claude's strongest argument is variance reduction where the bar is tightest: 797 → 1,110 sessions
takes the half-width **0.0189 → 0.0160**. Grok's is that mixing a crash regime into a re-run changes
the estimand and destroys comparability with −0.0070.
Measured: the interval improves by **0.0029**. The move required to reach the resurrection bar is
**0.050 − (−0.0070) = 0.0570**. The 313 sessions buy **5.1% of the required move — 19.6× short.**
⇒ **They cannot change the decision, and they are the only crash regime we will ever have.**
**DECIDED: 313 = Holdout-2, sealed. Item 5 runs on 797.**
⚠ Grok's constraint is adopted with it: no `liquid_as_of` inside 2019-10→2020-12 — there is no
prior ranking window.

**⭐⭐ 2. "Unblock item 4 without waiting on a theology of R" — RIGHT, and M64 makes it stronger
than Grok claimed.** Grok's point is that the **delete** treatment needs no R. M64 shows the
**magnitude** arm needs none either: because D1/D5/positional all divide by the **fill**-referenced
risk, and the fill *is* the gap open, **every affected trade books exactly +1.0000R regardless of
gap size**. So:
- the per-trade contamination is a **constant, +1.000R**, not a distribution;
- ⛔ **my M51 is WITHDRAWN as stated.** "bias = gap ÷ stop_distance … the M5 repro is 5R" is the
  gap expressed in *planned-risk* units — **it is the bias in no unit any study computed**;
- ⛔ affected trades are **invisible in the R distribution** — they look exactly like genuine +1R
  winners. They can only be found by re-deriving `open` vs `stop` at the fill bar;
- ⚠ and when the gap lands *exactly* on the stop, fill-referenced R is **undefined** (÷0) and every
  study's `risk_pct <= 0` guard silently **drops the row**.
⇒ **Item 4 is UNBLOCKED.** Falsifier, in the studies' own published unit: *delete the affected
trades; if any D1/D5/B7 headline changes sign or crosses |t| = 1.96, that headline is invalid.*

**3. Which R to canonicalise.** Grok says three names, never mixed; Claude says signal-referenced
with chase reported separately. ⭐ **M64 decides it for Claude's side on evidence, not argument:**
fill-referenced R returned **+1.0000 at every gap size** — the metric is blind to the defect *by
construction*. A reported R must be able to show the failure it is reporting on.
⇒ **`R_signal = |signal_price − planned_stop|` is canonical for REPORTING**, fixed at mint;
`R_entry` is retained as the realised-economics figure; **chase is its own term**, never absorbed
into a denominator; **never mixed inside one threshold**.

**4. Grok's D1 — "`PREV_CLOSE` is the same vendor's unadjusted series."** ⭐ **CONFIRMED by M66 on
8 of 8 boundaries.** This is the correct reading and Claude's D21 rests on the opposite premise.

**5. ⭐ The CA screen is not a CA detector — a new finding that falls out of M66.** Of the 8
flagged `|move| > 25%` events, **3 are corporate actions** (IRCTC 1:5 split · BAJAJFINSV 1:1 bonus
+ 1:5 split · PEL demerger) and **5 are genuine price moves** (ZEEL ×2 on the Sony/Invesco news,
IDEA on the telecom relief package, ADANIENT ×2 on Hindenburg) `[cited — classified by hand from
public corporate-action records; we ingest no CA table]`. ⇒ **a drop-the-window rule at 25% would
delete the single most informative week in the block and keep every dividend.** Grok's "drop at 25%
and declare it; don't invent 0.5% without an ex-date table" is directionally right, but the
measurement says the rule is **62.5% false-positive on this sample**. **NEW 16 is rescoped: the CA
policy needs the external source D3 already found** (the free NSE `/api/` path), not a threshold.

**6. U7's kill threshold** — adopted by forfeit: *sector-relative IC 90% CI entirely above the
NIFTY50 IC on 792 sessions / ~500 names, else drop U7.*

**7. Grok's C3, C6** — both already applied. Its "no round 11 unless a probe runs with it" is the
same rule §13f set in round 8 and is restated in §12.12.

## §12.8 · Kimi — adjudicated

**⭐⭐⭐ Its 2.4 is the finding of the round, and the answer is worse than the question.**
*"E2's panel construction is never stated — the same defect class the document burned on twice."*
**M62: `load_frames` ranks on `now() - 180 days` and the run is applied to 2023-07-03 onward.**
- **86 of 250 names (34.4%)** entered E2's cross-section on liquidity information from **after**
  the measurement window;
- extended to the holdout it would be **46%**, and **61 names (24.4%) have no bar before 2021**;
- **615 of the 2,107 names that actually traded in 2021–22 (29.2%) are structurally ineligible**,
  because the filter requires >100 bars in the **last 180 days**.

⚠ **But Kimi's charge must be split, because the pre-registration is better than the document.**
`E2-PREREGISTRATION-2026-09-12.md` line 36 **does** fix the eligible universe (≥300 prior bars,
close > ₹1, span guard) and line 38 **names the bias**: *"⛔ This inherits the known 0a.3
survivorship bias — the name set is drawn by today's liquidity — and that bias is not fixed by this
test. It is recorded, not solved."* ⇒
- ⛔ **REFUTED against the pre-registration** — it is stated, and the script matches it exactly;
- ⛔⛔ **CONFIRMED against THIS document and against CLAUDE.md, MEMORY.md and PHASES.md**, which
  all carry **"THE RANKER IS DEAD"** with **none** of that caveat. That is a W1 doc-sync failure and
  it is mine;
- ⛔ **and the pre-registration named only SURVIVORSHIP, not LOOK-AHEAD.** They are different
  defects. Its direction argument — *"it should if anything help the scorer, so a null is
  conservative"* — is plausible for survivorship and **unmeasured for look-ahead liquidity
  selection**, where names that *became* liquid by 2026 were a growth cohort in 2023. That sentence
  is now tagged `[ASSUMED]`.

| other | verdict |
|---|---|
| **2.3** — break-even 0.0310 has no published derivation | ⛔ **REFUTED (M63)** — it is derived in the pre-registration, and **✅ CONFIRMED for this document**, which never carried the formula. Now carried. |
| **4.2** — the cost model was only ever fitted to itself | ⭐ **CONFIRMED (M74), and conceded.** M27 regressed `fees.py` against **`fees.py`**. That validates arithmetic, not accuracy, and the 22.22 bps floor is the programme's most decision-load-bearing number. **NEW 21.** |
| **Missing — taxation** | ⭐⭐ **CONFIRMED (M73): STCG appears NOWHERE.** It cannot rescue a negative gross edge, but it raises the hurdle a positive one must clear and it is absent from every break-even in the programme. **NEW 20.** |
| **1.4** — gate config unversioned | ✅ **CONFIRMED (M80)** — no config/setting/gate table exists. Conceded in round 6, never queued; **now queued (NEW 22)**. |
| **q8** — overlap handling in the closed studies | ⛔ **CONFIRMED (M81): none of D5, D1 or B7 applies `newey_west_t`.** ⚠ **Consequence Kimi did not draw: D1 was DECLINED on `t = −2.91` with a naive SE.** Under the correction the 09-10 methods audit mandates, that refutation is weaker than published — **R1/RVOL is "not refuted", not "refuted"**, until item 6 re-runs it. |
| **6.4** — the matched basket's construction is undocumented | ⛔ **REFUTED in code** — `swing_dependence_probe.basket_series` is an **equal-weight mean of the same `load_frames` cohort over each trade's own window**, and its docstring says it inherits that cohort's bias. ⚠ "Matched" is a misnomer; it is *paired in time*, not matched on characteristics. Renamed in §12.10. |
| **7.5** — the gating closure depends on the contaminated E2 | ✅ **Taken.** "The trades carry no edge to partition" inherits every defect E2 has. Recorded as a dependency. |
| **3.6** — historical-name completeness asserted, not checked | ⓘ **Partly measured (M83):** 0 orphans, and 20 names created by the backfill. The external cross-check against NSE delisting circulars remains undone. |
| **1.1–1.3, 2.1, 2.5–2.9, 3.x, 5.x, 7.x** | Faithful restatements of PARTS 7–11. |
| **Meta — "the next reviewer should be an independent recomputation of the M-table"** | ⭐ **Agreed, with one amendment M79 supports: recomputation is what rounds 6–9 already were.** The round-10 yield came from *"show me the population query"*. **That is the question shape to repeat.** |

## §12.9 · Nemotron — adjudicated (round-6/7 vintage)

Working from an old copy, and it shows in ways that matter:

- ⛔ **Q3/H1 quote `ohlcv_1d` at "1,101 distinct sessions … 2021 and 2022 do not exist."** The hole
  was filled 2026-09-17; the archive is **1,727 sessions**.
- ⛔ **D1 "attempt the backfill"** and **Finding 28 "fill the 922-day data hole"** — done.
- ⛔⛔ **E5 restates M33** — *"all 14 higher-confidence signals were NOT acted on"* — **withdrawn in
  round 8 by M47/M48**: the population was 12, not 50, and P(4 of 4 SELL) = 0.2545 = **1 in 3.9**.
  Re-citing a withdrawn claim as current is the one failure mode a reviewer of a versioned document
  must avoid.
- ⛔ **Its proposed test is unrunnable (M84)**: `signal_outcomes` has neither `acted_on` nor
  `confidence`.
- ⚠ Its B-5 quote gives the sector map as **both** "500 of 3,397" and "500 of 3,395" in one reply.
- ⚠ Its Q6 asks to "re-run D5 using actual stop distances from entry rather than fixed percentage" —
  **M64 shows D5 already divides by the actual fill-referenced distance.**
- ✅ Correct and current: A1–A5 (empty `strategy_profiles`, unwired ledger, starved categories, the
  FII/DII false neutral, the sector map), B2 (live immune by explicit rejection), S5 (the
  universe-size guard as a systemic outage).

**Net: 0 decision-changing points.** Both stale replies produced findings the current document had
already recorded, which is the expected outcome and the reason vintage is now tracked in §12.1.

## §12.10 · ⛔ What round 10 cost me — corrections to my own document

1. ⛔⛔ **E2's cohort caveat never left the pre-registration.** Four documents carry "THE RANKER IS
   DEAD"; the pre-registration carries "the name set is drawn by today's liquidity … recorded, not
   solved". **W1 failure, mine.** Fixed in all four.
2. ⛔⛔ **M51 WITHDRAWN.** "bias = gap ÷ stop_distance … the M5 repro is 5R" is the bias in **no
   unit any study computed**. In the studies' own unit it is **exactly +1.000R, always** (M64).
3. ⛔ **§9.4 said four scripts hardcode `_CLEAN_SINCE`. There are five** (M71).
4. ⛔ **§9.3 still says the archive gained "620 sessions".** It gained **626** — the same defect M61
   corrected at "622" one paragraph later, in a second instance I did not look for.
5. ⛔ **M57's CA caveat was too weak.** I wrote "this check's CA-detection capability is untested".
   M66 shows it is **incapable** — `PREV_CLOSE` is the same unadjusted series, on 8 of 8 boundaries.
6. ⛔ **"Matched basket" is a misnomer** — it is an equal-weight cohort basket **paired in time**,
   matched on nothing. Renamed wherever it appears.
7. ⛔ **The break-even formula was never carried into this document** from the pre-registration
   (M63), so a reader of this document alone could not check the one number the E2 verdict turns on.
8. ⚠ **I read the holdout again** (M66's CA census, 2021-01→2023-07). Permitted as an integrity read
   under §10.10's whitelist, and recorded here rather than left implicit — BT20's warning, live.

## §12.11 · Two standing rules earned this round

⭐⭐ **A metric may not be blind to the failure it is meant to report.** Fill-referenced R returns
**+1.0000 for every gap size** — the quantity that should have screamed is mathematically incapable
of varying. Test, before adopting any metric: *construct the failure it is supposed to catch and
check the number MOVES.*

⭐⭐ **Ask for the population query, not the recomputation.** M79 measures four rounds of
recomputation converging on my own arithmetic (0.79 → 3.98 self-corrections per 100 lines) while
system-defect yield fell to zero. The round that broke the trend asked *"what universe does this
script score, and as of when?"* — **one question against one function, and it reopened the
programme's central null.**

## §12.12 · ⭐ THE QUEUE — one table, current (A22). §7.11, §8.10, §10.11 and §11.9 are now history.

| # | Item | State |
|---|---|---|
| **1** | Decide the four SHORT positions + ship a directional/settlement restriction | ⛔ **Blocked on Q-A** (account type — the user's to state) |
| **2** | Wire the ledger + a backend wiring lint | Ready |
| **3** | Re-seed `strategy_profiles` idempotently + census every seed-bearing migration | Ready |
| **4** | Fix `_simulate_trade`'s entry-bar gap | ✅ **UNBLOCKED (M64).** Delete treatment; falsifier: *any D1/D5/B7 headline that changes sign or crosses \|t\|=1.96 is invalid.* Affected rows are invisible in the R distribution — find them by `open` vs `stop` at the fill bar |
| **5** | Re-run E2 | ⛔ **Now needs THREE repairs, not one**: CA policy (16) · **PIT cohort (14) — M62** · window = **797, DECIDED**. Arms 5b (per-direction) and 5c (bar as a **formula**, `break-even + 1.645·SE`, per arm) pre-registered |
| **6** | Re-run D5 + D1 + B7 after item 4 | ⚠ **and with the overlap correction (M81)** — D1's `t = −2.91` is naive |
| **7–9** | Ledger `surface`/`displayed_rank`; the five-field manifest; experiment registry (Q-B) | Ready |
| **10** | Directional entry zone | Ready — **loss-reduction, not edge (EX16)** |
| **11** | Holdout seal: **617 sessions**, whitelist = row/session counts + integrity checks | ✅ **Opening condition, written (H26): the holdout opens once, after item 5 returns on 797, and only if item 5 clears 5c's bar** |
| **12** | Push | ⓘ **Evidentiary for FUTURE pre-registrations only — `fe5d508` is UNSIGNED (M72).** E2's label is now *"pre-registered, operator-attested"* |
| **13** | Celery beats off `day_of_week="1-5"` | Ready |
| **14** | **PIT cohort helper `liquid_as_of(date)`** | ⭐⭐ **PROMOTED to a precondition of item 5** (M62) |
| **15** | A10 treatment for `bhavcopy_service` | Ready |
| **16** | CA policy | ⭐ **RESCOPED (M66): a `\|move\|` threshold is not a CA detector — 62.5% false-positive on the measured sample.** Needs D3's external NSE source |
| **17** | Measure spread and impact | Falsifier (Claude BT21): *median half-spread on the tradability-screened subset < 5 bps ⇒ not binding* |
| **18** | Index/VIX for 2021–22 | Ready — integrity ingest, whitelist-class |
| **19** | Project-level kill criterion | **Written**: *if item 5 on 797, CA-screened and PIT-cohorted, returns a 90% upper bound below break-even, this daily-swing scorer is retired. The crash block is not spent trying to save it.* |
| **20** | ⭐ **NEW — put tax in the cost model** (Kimi) | **M73: absent everywhere.** Raises every break-even |
| **21** | ⭐ **NEW — reconcile `fees.py` to one real contract note** (Kimi 4.2) | **M74: never done.** The 22.22 bps floor is the programme's most load-bearing number and is self-fitted |
| **22** | ⭐ **NEW — version the gate configuration** (Kimi 1.4) | **M80: no table exists**; conceded round 6, never queued |
| **23** | ⭐ **NEW — enumerate the three standing concessions** (Claude A23) | **M78: 0/0/0.** Portfolio-level evaluation · `entry_diversity`'s incremental effect · live-vs-modelled fill calibration |
| **24** | Position-count cap | ⓘ **D4's cap of 3 independently supported by cost (M77)**: 30 bps falls between 5 and 6 |
| **Q-A** | Account type + capital | ⛔ **The user's. Blocks item 1 and every cost conclusion** |

⛔ **No round 11 unless a probe runs with it.** M79 is the evidence: four rounds of recomputation,
yield converging on my own arithmetic. The one question that paid this round was aimed at a
function, not a table.

---

# PART 13 — THE ROUND-11 PANEL (2026-09-18), AND THE ANSWER: BUILD

## §13.1 · The round in one line

**Six responses. All six say the same thing: stop reviewing, work the queue.** §12.12's own rule
said it first. This round therefore ships **with a probe (M85)** and is the last adjudication until
code lands. ⚠ Two responses were stale again — **Gemini for the third consecutive round** (it
proposes filling the 922-day hole, done 2026-09-17) and **Nemotron for the third** (it restates
§12.12 back verbatim and asks which row to start on). Both: **0 new points.**

⭐⭐ **The round's yield was almost entirely defects in THIS DOCUMENT, and one of them is a verdict
I got backwards.** Ten corrections, listed in §13.7. That is the density finding arriving on
schedule, and it is the argument for building rather than the argument against it.

## §13.2 · ⭐⭐ THE PROBE — M85: item 4's contamination is a function of stop width

Claude's BT23 said the affected trades are findable without re-deriving the fill bar. Generalised:
because **every affected trade books exactly +1.000R (M64)**, the shift the delete treatment
produces is arithmetic — `f · (1 − μ_clean)/(1 − f)` — and `f` is just the archive's gap exposure
at that stop width. Measured on 405,426 name-days, strictly-PIT annual top-250, 1,727 sessions:

| stop width `w` | P(entry-bar gap through) | bias on mean R | vs item 4's 0.05R bar |
|---|--:|--:|---|
| p10 **0.65%** | **10.068%** | **+0.1231** | ⛔ **2.5× OVER** |
| order-path floor **2%** | 2.499% | +0.0282 | under |
| 3% | 1.314% | +0.0146 | under |
| median **5%** | 0.470% | +0.0052 | under |
| swing cap **8%** | 0.191% | +0.0021 | under |

⭐⭐⭐ **THE ANSWER: item 4's falsifier cannot fire on the book the order path will take.** The
contamination clears 0.05R **only below a 2% stop** — and the notional cap is already a 2%
minimum-stop-width rule in disguise. At the order-path floor it is **+0.028R**; at the median stop
**+0.005R**, 10× under.

⇒ **Item 4 is reclassified: a CORRECTNESS fix, not a headline-moving one** — *except* for D1, D5,
B7 and the 1,975-trade corpus, which all include the sub-2% cohort the order path refuses. That is
now a stated, measured expectation the re-run must match, not an open question.
⚠ Long side only. The short tail is ~2× larger at every width, but a cash-delivery book cannot hold
one. ⚠ `μ_clean = −0.10` is the corpus's own order of magnitude; the ranking is insensitive to it.
⭐ **Grok predicted this curve** (≈0.0026R at the median, ≈0.085R at p10) — right shape, ~2× low.

## §13.3 · Claude — adjudicated

Recomputed PART 12 independently before answering, for the second round running.

| point | verdict |
|---|---|
| **Q29** — M79 *refutes* Q28, it does not confirm it | ⛔⛔ **CORRECT, AND MY §12.3 VERDICT IS WITHDRAWN.** Measured: corr(lines, corrections) = **−0.837**. Proportionality predicts 5 → 3.5 → 2.6 → 1.6; observed **5 → 7 → 6 → 8** while volume fell 3.1×. **The absolute defect count is flat-to-rising as output shrinks** ⇒ the yield is not a volume artifact, and the case for stopping is stronger than I stated it. |
| **A25** — Holdout-2 was decided in §12.7 and never reached §12.12 | ⛔⛔ **CONFIRMED: zero mentions of 313 or Holdout-2 in §12.12** — in the round that published the one-table queue to prevent exactly this. |
| **A26** — "renamed wherever it appears" is false | ⛔ **CONFIRMED.** Line 235 (R-2) still reads *"Test it against a matched basket"* — and it is a **forward instruction for an unrun test**, the one place the stale label can still produce a wrong study. |
| **A27** — §9.3 superseded by cross-reference, not replaced | ⛔ **CONFIRMED**, and it still says "the input to queue item 4's falsifier". Replaced in place this round. |
| **Q30** — the decision rule has an undefined middle | ⛔⛔ **CONFIRMED and it is exactly two half-widths wide.** Item 19 fires when the point estimate < **0.0121**; 5c resurrects at ≥ **0.0499**. The band **[0.0121, 0.0499]** triggers neither, and it is the modal outcome of a repaired re-run. Third branch written in §13.8. |
| **Q31** — `liquid_as_of` turns a hidden lookback into a free parameter | ✅ **Taken.** 180 days is pinned in the signature with no caller override. |
| **BT22** — tax does not move break-even | ⭐⭐ **CORRECT, and it fixes my own item 20.** Break-even is where profit is zero; tax is levied on profit; at break-even tax is zero. Tax raises every **target**, not the hurdle. ⇒ **item 5's cost dependency is item 21 alone**, one fewer blocker than §12.12 implied. |
| **BT23** — a free detector exists | ⭐⭐ **Taken and generalised into M85** (§13.2), which answers the magnitude question with no re-run at all. |
| **H27** — the push must precede item 5 | ⭐ **CORRECT and adopted.** Item 5 is the next pre-registered run and the first that *can* be attested. Pushed below item 5, it inherits E2's operator-attested status permanently. **Item 12 moves above item 5.** |
| M77 recomputation (26.83 / 29.90 / 31.43 / 60.58) | ⓘ Both right. Claude divides ₹1L exactly; I size integer shares at ₹500. Immaterial, and the 30 bps crossing is unchanged. |
| M70 arithmetic: 3,166,300 − 3,162,898 = **3,402** = one dropped bar per name | ⭐ A neat independent confirmation of M69's `lag()` construction — 3,402 is exactly the distinct-name count. |

## §13.4 · ChatGPT — adjudicated

| point | verdict |
|---|---|
| **1.2** — a cohort fixed at study start and a cohort rebuilt per measurement date are **different estimands** | ⭐⭐ **CORRECT, and §12.12 item 14 did not say which.** E2's stated question — *does the score rank forward returns among eligible names on each date* — is the **dynamic** one. Pre-registered in §13.8. This is the sharpest point in the reply. |
| **2.3** — "use Newey-West" is too simplistic; characterise the dependence first | ✅ **CORRECT, and I over-specified.** D1's dependence is per-date (a market-wide regressor), D5's is paired-by-signal, B7's is per-trade with overlapping windows. Item 6 now says *choose the estimator after inspecting the structure*, not "apply Newey-West". |
| **3.1** — M65 validates ingestion fidelity, not source truth | ✅ **Taken.** The wording is now "our stored bars match the vendor's own file", not "independently published". An independent second vendor remains untested. |
| **7.3** — parameterise tax, do not add a flat bps | ✅ **Taken** (and see BT22 — it does not enter break-even at all). |
| **7.2** — the 3-position cap is conditional on ₹1L | ✅ **Taken**; item 24 now carries the condition. |
| **1.3 / 11** — configuration is a fourth provenance dimension | ✅ Folded into items 8 and 22. |

## §13.5 · Grok — adjudicated

| point | verdict |
|---|---|
| **Do not block item 5 on a full CA ingest** — exclude the 3 named events by dated list; item 16 proceeds in parallel | ⭐⭐ **ADOPTED.** A three-row dated exclusion **is** a cache of the authority's answers, which is exactly what the standing law asks for; a `\|move\|` threshold is not. **Item 5 is no longer blocked on item 16.** |
| **"A null is conservative" is FALSE for look-ahead** | ⭐⭐ **CORRECT and sharper than my `[ASSUMED]` tag.** Names that *became* liquid by 2026 were a growth cohort in 2023, so the filter can **manufacture** IC. The current null is not conservative — it is **uninterpretable**. Restated. |
| The stop-width contamination curve | ⭐ **Predicted and measured** — see §13.2. |
| Slice ordering (14 → 4 → 2 → 3 → 15) | ✅ Adopted, with item 12 hoisted per H27. |

## §13.6 · DeepSeek · Gemini · Kimi · Nemotron — adjudicated

**DeepSeek.** A faithful restatement of PART 12 in table form, plus a correct execution answer and a
sensible order. Its one mischaracterisation: §12.3's note about M69's estimator is called "Claude's
own recomputation drifting from the archive" — it is not drift, the two are different estimators and
the document says so. **New points: 0; correct call: yes, build.**

**Gemini.** ⛔ **Round-8/9 vintage for the third consecutive round.** Its work queue proposes
"Fetch missing 2020–2023 daily bhavcopy CSVs" (done 2026-09-17, 654 sessions) and "Fill Daily
Archive Hole (M38)" as step 4 of 5. **0 new points.** ⛔ **Its U7 kill threshold has now been owed
five rounds**; Grok's stands by forfeit.

**Kimi.** The most productive reply after Claude's, and **three of its findings are refuted by
measurement** — which is the right outcome to report:

| # | claim | verdict |
|---|---|---|
| **F1** | §12.12 does not subsume what it declares history | ⛔⛔ **CONFIRMED in all three parts.** Measured on §12.12: *runbook* 0 · *off-box* 0 · *Q-C* 0 · *provenance* 0 · *MDE* 0 · *FII* 0 · *LTP* 0 · *palette* 0. §8.10's item 12 was **"U5 runbook DR ordering; off-box backup; push"**; §12.12 kept only "Push". **The one-table queue is not one table.** Rebuilt in §13.8. |
| **F2** | The commit count is carried three ways | ⛔ **CONFIRMED: 209** (header, U-1, §7.11) · **210** (§8.10) · **215** (§12.6), all live. |
| **F3** | M31's "8% and 18%" use different bases | ⛔ **CONFIRMED.** Long tail 8.0% of the OLD base; short tail 17.9% of the NEW base (15.2% on the old). |
| **F4** | {8.2, 2.88, 2.90} cannot all be right | ⛔ **REFUTED (M88).** Measured to four places: intraday **8.2440** bps, delivery **23.7580**, ratio **2.8819**. Both published figures round correctly; only the *reconstruction from rounded components* fails. ⭐ Real lesson kept: **publish a ratio or its components at reproducing precision, never rounded halves of both.** |
| **F5** | 20 names created, only 15 gained bars | ⛔ **REFUTED (M86): 20 created, 20 with bars.** The +15 was measured before the weekend recovery added the rest. |
| **F6** | §9.2's block table no longer tiles | ✅ **CONFIRMED and fully reconciled (M89):** 311+247+246+121+793 = **1,718**, nine short of 1,727 — **5 sessions lost to the per-block return lag (one per block, a return series over N sessions has N−1 returns) + the 4 weekend sessions recovered after §9.2 was written.** Not missing data; a stale table with a structural artifact inside it. |
| **F8** | "largest gap 5 days ×2" — one of them is 4 | ⛔ **REFUTED (M87).** The sessions run **2022-08-05 → 2022-08-10**: 08-08 is the XLSX failure and **08-09 was Muharram**. The gap is 5 days. "×2" is correct. |
| **F9** | Item 4's falsifier names a t but not its SE | ✅ **Taken** — named in §13.8. |
| **F10 / F11** | The kill criterion fires on current numbers; "retired" is undefined; break-even 0.0310's σ_cs is unstated | ✅ **Both taken.** Measured: with `E[z\|sel] = 2.267`, **0.0310 implies σ_cs = 3.63%** — a number that appears nowhere. Now carried. "Retired" is defined in §13.8. |
| **F12** | The four shorts' gross | ✅ **Measured: ₹1,19,569 = 1.196× a ₹1 lakh book.** Belongs in Q-A's answer. |

**Nemotron.** ⛔ Reproduces §12.12 back verbatim and asks which row to start on. **0 new points, third
consecutive round.** Its one substantive line — that the queue is the deliverable, not a new round —
is correct and is the document's own.

## §13.7 · ⛔ What round 11 cost me — ten corrections

1. ⛔⛔ **§12.3's Q28 verdict is WITHDRAWN.** I wrote "✅ CONFIRMED"; the data refutes the
   hypothesis (r = −0.837) and the true reading is worse for the document.
2. ⛔⛔ **§12.12 lost Holdout-2** — decided in §12.7, never written into the queue.
3. ⛔⛔ **§12.12 lost the runbook-DR and off-box-backup rows** that §8.10 item 12 carried.
4. ⛔⛔ **§12.12 never folded in PART 3** — B-4, B-12, F-1 (the LTP painted bull regardless of
   direction, a money-correctness bug), F-2, F-3, F-4, U-2 have no row. **A22 was half-fixed.**
5. ⛔ **Q-C vanished**, and §12.4 then pointed at it — *"still queued"* with no row to queue it in.
6. ⛔ **Item 20's "raises every break-even" is wrong** (BT22). Tax raises targets, not the hurdle.
7. ⛔ **§9.3 was superseded by cross-reference, not replaced in place.**
8. ⛔ **"Renamed wherever it appears" was false** — the surviving instance is a forward instruction.
9. ⛔ **The commit count is carried three ways** (209 / 210 / 215).
10. ⛔ **M31's two percentages use different bases**; **break-even 0.0310's σ_cs (3.63%) is stated
    nowhere**; **item 4's falsifier names a t without its SE**; **item 14 never said which estimand.**

⭐ **The pattern, stated plainly: eight of ten are maintenance defects in a 313-line section written
in one sitting, and six are the SAME class the section was written to close.** A document this size
cannot be kept true by writing more of it. §13.8 is the last queue revision; after it, changes land
as commits.

## §13.8 · ⭐⭐ THE QUEUE — complete this time. PARTS 3 and 7–12 are history.

⚠ **Completeness rule, so this cannot silently shrink again: every row that ever appeared in §7.11,
§8.10, §10.11, §11.9, §12.12 or PART 3 appears below or is explicitly marked DROPPED with a reason.**

### Blocked on the user — one sentence unblocks four rows

| # | Item | Note |
|---|---|---|
| **Q-A** | **Account type + capital** | ⛔ Blocks 1, 24, and every cost conclusion. ⚠ **The live book's gross is ₹1,19,569 = 1.196× a ₹1 lakh book** (M89/F12) — whatever the answer, the current book already exceeds it |
| **1** | The four SHORT positions + a directional/settlement restriction | ⛔ On Q-A. If CNC: close + `always_on` overnight-SELL restriction. If MIS: the restriction is the wrong patch |
| **13** | Celery beats off `day_of_week="1-5"` | ⛔ A scheduling change on a running system — your call |
| **21** | Reconcile `fees.py` to one real contract note | ⛔ Needs one actual note. ⭐ **This is item 5's ONLY cost blocker** (BT22) |

### The chain that decides whether the scorer lives

| # | Item | State |
|---|---|---|
| **12** | **Push** | ⭐ **MOVED ABOVE ITEM 5 (H27).** `fe5d508` is unsigned and stays operator-attested; item 5 is the first run that *can* be attested, and only if the push precedes it. **Sign the pre-registration commit** |
| **14** | `liquid_as_of(date)` | ✅ **BUILT 2026-09-18** — `app/services/pit_cohort.py` + 6 tests. **DYNAMIC estimand** (ChatGPT 1.2): `liquid_over` rebuilds eligibility per measurement date; `liquid_as_of` is its primitive, window `[as_of − 180d, as_of)` half-open. **180 days pinned as a module constant, absent from the signature** (Q31 — asserted by a test that introspects the signature). `PitViolationError` on `as_of >= applied_to`; `InsufficientHistoryError` rather than an empty cohort. ⭐ **Mutation-tested: the M62 canary was VACUOUS on first write** (median ranking ignores a minority of look-ahead bars) and now fails under both a widened ranking window and a today-anchored one |
| **4** | `_simulate_trade`'s entry-bar gap | ✅ **BUILT 2026-09-18** — `app/backtest/entry_gap.py` + 13 tests. `is_unfillable` delegates to **`restrictions.through_stop_reason`**, the predicate `place_paper_order` uses, so the backtest corpus is exactly the set live would accept (W2 — not re-derived). `partition` / `apply_delete_treatment` report the shift. ⭐ A test CALLS the frozen engine and pins M64: **+1.0000R at 2/5/10/20% gaps**. Mutation-tested both ways (always-fillable and always-refused each kill tests). ⚠ **The FROZEN engine is deliberately NOT changed** — repairing it would move every walk-forward golden and the Rust oracle, needing sign-off + an §8 regression; the filter gives every study the delete treatment today at no such cost. **Falsifier, SE named (F9): any D1/D5/B7 headline that changes sign, or crosses \|t\| = 1.96 *under the same estimator the re-run uses*, is invalid.** ⭐ **Expected magnitude measured (M85): +0.028R at a 2% stop, +0.005R at the median — it can only clear 0.05R below a 2% stop** |
| **5** | Re-run E2 | Needs **14** and **21**. ⭐ **No longer blocked on 16 (Grok):** exclude the three named corporate actions by dated list — IRCTC 1:5, BAJAJFINSV 1:1 bonus + 1:5, PEL demerger. Window **797, DECIDED**. Arms 5b (per-direction) and 5c (bar as the formula `break-even + 1.645·SE`, per arm) |
| **6** | Re-run D5 + D1 + B7 | After 4. ⚠ **Characterise the dependence first, then choose the estimator** (ChatGPT 2.3) — D1 is per-date, D5 paired-by-signal, B7 overlapping-per-trade. Not "apply Newey-West" |
| **19** | Project kill criterion | ⭐ **THIRD BRANCH WRITTEN (Q30).** Point estimate **< 0.0121** ⇒ retire. **≥ 0.0499** ⇒ resurrection candidate. **In between ⇒ a second null: item 19 fires, the scorer is retired, and the holdout is NOT opened to break the tie.** ⭐ **"Retired" means: the scorer stops being a candidate, `entry_diversity` stays as the one hard rule, the 617- and 313-session blocks are preserved unopened for a successor generator, and the harness stays** |
| **11** | Holdout seal — **617 sessions**, whitelist = row/session counts + integrity checks | Opens once, after item 5 on 797, **only** on the ≥0.0499 branch |
| **11b** | ⭐ **NEW — Holdout-2 seal: 313 sessions (2019-10-01 → 2020-12-31)**, same whitelist | ⛔ **The row §12.7 decided and §12.12 lost (A25).** The only crash regime in the archive. ⚠ No `liquid_as_of` inside it — there is no prior ranking window |

### Ready now — no decision, no research risk

| # | Item | Note |
|---|---|---|
| **2** | Wire the ledger + a backend wiring lint | The one artifact that survives the next DB loss |
| **3** | Re-seed `strategy_profiles` idempotently + census every seed-bearing migration | ✅ **BUILT 2026-09-18** — `scripts/seed_strategy_profiles.py` + 9 tests. ⭐⭐ **TEN profiles, not eight: TWO migrations seed this table** and only `o1p2q3r4s5t6` was ever named. `d2e3f4a5b6c7` seeds `retune_base` + `retune_momentum_x15` — **restoring only the eight would have left the momentum-retune shadow arm dead**, a forward-evidence loop PHASES still lists as open. ⭐ **Census measured: 4 of 46 migrations seed rows.** `indices` (27) and `ca_flag_events` (7) are populated; only `strategy_profiles` is empty. `tests/test_seed_migrations.py` is a **ratchet** — a new seeding migration fails the suite until `SEED_BEARING` records what re-seeds it. The script loads each migration **by path** and reuses its own `SEEDS` and `_INSERT` (W2 — nothing restated), adding `ON CONFLICT DO NOTHING`. ⏳ **Dry run on dev confirms all 10 missing; the write itself awaits the user** (CLAUDE.md: ask before writing live data) |
| **7** | Ledger `surface` + client `displayed_rank` | Selection is otherwise unattributable |
| **8** | The five-field manifest | ⭐ **Widened (ChatGPT 11): + configuration snapshot + dependency lock.** A study fails closed when one is missing |
| **9** | Experiment registry (Q-B) | The t ≈ 3.6 bar's trial count is unknown |
| **10** | Directional entry zone | Loss-reduction, not edge |
| **15** | A10 treatment for `bhavcopy_service` | ✅ **BUILT 2026-09-18** — `_assert_plausible_bhavcopy` (magic bytes · HTML · SYMBOL+SERIES header · line floor 1,000) + 11 tests, mirroring `universe_materialiser._assert_plausible_equity_l`. ⭐⭐ **M91 measured why BOTH checks are needed: 2022-08-08 still returns HTTP 200 with `PK\x03\x04` and 233,582 bytes containing 858 NEWLINE BYTES — a line floor alone would have passed it.** Real files carry 2,059 / 2,628 / 3,484 lines. ⭐ A corrupt source is now `status="failed"`, never "holiday": `download_bhavcopy` raises `BhavcopySourceError`, `ingest_bhavcopy_date` converts it (so `eod_catchup`, which aborts on any non-`HTTPError`, does not forfeit the run) and the backfill counts it as **failed**, not holiday. 2022-08-08 stays a hole — deliberately (W2, no XLSX parser) |
| **16** | CA policy — the external NSE source (D3's free `/api/` path) | ⭐ No longer blocks item 5; runs in parallel |
| **17** | Measure spread and impact | Falsifier: median half-spread on the tradability-screened subset < 5 bps ⇒ not binding |
| **18** | Index/VIX for 2021–22 | Integrity ingest, whitelist-class |
| **20** | Tax in the cost model | ⛔ **CORRECTED (BT22): raises every TARGET, not the break-even.** Parameterise by product and holding period; do not add a flat bps |
| **22** | Version the gate configuration | No table exists; a past signal cannot be attributed to a config |
| **23** | The three standing concessions, enumerated | Portfolio-level evaluation · `entry_diversity`'s incremental effect · live-vs-modelled fill calibration |
| **24** | Position-count cap | ⓘ **Conditional wording (ChatGPT 7.2): at ₹1 lakh under the current modelled costs, 3 positions keeps delivery friction below 30 bps** (29.89 at 5, 31.52 at 6). Not a universal cap |

### Restored from §8.10 and PART 3 — dropped by the last consolidation (F1)

| # | Item | Note |
|---|---|---|
| **25** | **U5 — the disaster-recovery ordering section in `RUNBOOK.md`** | ⛔ Carried by §8.10 item 12, lost in §12.12. The composition that caused 09-07 is still undocumented |
| **26** | **Off-box backup** | ⛔ Same row, same loss. Backups run to a **local** path |
| **27** | **F-1 — `StockDetailPage` paints the LTP `--color-bull` regardless of direction** | ⛔ A falling price renders green. **Money-correctness, not a style nit**, and it had no queue row |
| **28** | **B-4 — the FII/DII consumer states "flows neutral" from zero rows** | A positive claim from absent data |
| **29** | **Q-C's three unclosed adoptions** | **MDE beside every null · effects in bps with a CI beside the t · the price-provenance rung counter.** §12.4 called the last "still queued" with nothing to queue it in |
| **30** | **B-12 · F-2 · F-3 · F-4 · U-2** | Freshness assertion · CreateUserModal · unwired API functions · exclusion reasons as-of · the palette (yours) |

**DROPPED, with reasons:** the 1h backfill (two producers disagree permanently) · a ninth gate
(gating closed as a programme) · the XLSX parser for 2022-08-08 (W2) · regenerating goldens from the
current dev DB · a 1,110-session E2 (decided: 797) · **round 12.**

## §13.9 · The answer to "shall we work on the agreed items"

**Yes.** Six of six reviewers, and the document's own rule. The order, with the chain first because
it is the only sequence that decides whether the scorer lives:

**You:** one sentence — **Q-A** (account type + capital), and **the push** (W4 reserves it).

**Then, in order:** **12** (push + sign) → **14** (`liquid_as_of`, dynamic estimand) → **4** (delete
treatment) → **21** (one contract note) → **5** (the re-run) → **6** → **19 fires or does not.**

**In parallel, needing nothing:** 2, 3, 27 (the LTP colour bug), 15, 22, 10, 7–9, 16, 18, 23.

⛔ **No round 12.** The next artifact from this programme is a commit.
