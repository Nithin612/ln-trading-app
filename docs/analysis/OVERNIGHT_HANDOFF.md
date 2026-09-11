# Overnight build handoff — B-queue

**Started 2026-09-11 evening; 4 of 7 items done by ~01:00. Branch `feature/pre-cycle2-hardening`, MAIN checkout (never a worktree).** ⭐ A scheduled continuation is set for **03:31** when the token quota refreshes — but cron jobs here are SESSION-ONLY, so if the terminal closed it did not fire and this file is the resume point.
Queue and acceptance criteria: `docs/BUILD_QUEUE.md`. Update this file after EVERY item.

## Order (round-10: money-at-risk first)

| # | item | status | commit |
|---|---|---|---|
| **B2** | `Σ notional ≤ available cash` rail | ✅ **DONE** | `e170d2b` |
| **B3** | dated tick SCHEDULE table | ✅ **DONE** | (see log) |
| **B1** | delete `_near_expiry` / `_choppy` | ✅ **DONE** | (see log) |
| **B4** | span-based gap guard | ✅ **DONE** (1 part blocked) | (see log) |
| **B5** | E1 positional in four units | ✅ **DONE** | `90000c1` `1dd38d4` |
| **B6+B7** | E2 three estimands + MFE/MAE | ✅ **DONE** | (see log) |
| **B8** | append-only ledger (ONE table, ONE day) | ⏳ NEXT — the last item | — |

## Standing rules for this run

- Every item ships with tests and meets its BUILD_QUEUE acceptance criteria.
- One commit per item. **Commit freely; NEVER push, never merge, never touch `main`.**
- `mypy` + targeted `pytest` per change. ⛔ **Never pass `DATABASE_URL` to pytest.**
  ⛔ Do not run full `make check` (starves under RAM pressure).
- ⛔ **Do not apply any Alembic migration to the DEV database** — write it, verify against the test
  DB, leave the dev apply for the user.
- ⛔ **Do not edit `app/analysis/`, `app/backtest/engine.py`, or `docs/SIGNAL_ENGINE.md`** — frozen /
  hook-protected.
- One long task at a time; wait for it.
- If blocked: write why here, skip, move on.

## Where to resume

⭐ **NEXT: B8 — the LAST item.** ⚠ **TIMEBOXED TO ONE DAY: ONE append-only table with the five
node types as a discriminated column** (`DecisionSnapshot · OrderIntent · Execution ·
PositionLifecycle · PerformanceRecord`), every row carrying `code_commit · spec_version ·
experiment_id · data_version · created_at`, plus a nightly off-box export. ⛔ **NOT the five-table
schema** — the base rate is one item shipped as code in fifty days and that version is the one
that does not ship. ⛔ **Write the migration but do NOT apply it to the DEV database** — verify
against the test DB and leave the dev apply for the user.

⚠ **QUEUED, found during B6/B7, not fixed:** `swing_dependence_probe.py` has **no through-stop
exclusion** while `positional_probe.py` and the live path both do. The swing corpus admits fills
the order path would refuse; the positional corpus does not. Bounded (defect #4 is 2 of 185) but
the two corpora have never measured the same population.

⚠ **Before quoting any `probe-147` number, re-run it** — B4 changed the gap-clean cohort to
`probe-145`, and `clean × BUY` is now **n = 60**, not 61 (§16.1d).

## Log

- **B2 DONE** (`e170d2b`). `cash_cap_reason` + `RULE_CASH_CAP` in `SIZING_RULES`;
  `OpenHeat.notional` from the same read; `cash_cap_mode`/`cash_cap_leverage` default **off**;
  `.env.example` documented. 9 tests inc. the acceptance criterion (3 slots at the median 5% stop
  refused at exactly 120% of capital). ruff + mypy clean, `tests/test_risk_engine.py` **50 passed**.
  ⭐ A bug was caught by its own test before shipping: the first draft netted the
  position-being-topped-up out of the held notional, but `qty` is the INCREMENT at every call
  site, so it double-discounted. Regression test built so only the aggregate rail can refuse.
  ⚠ `check_sizing` was refactored into a rail table (ruff C901 forced it) — same order, same
  stamps, same behaviour.

- **B3 DONE.** `app/broker/tick_schedule.py` — the grid as a dated price-band TABLE, each row
  carrying its own source. `paper_tick_size` default `0.05` → **`0.0` = use the schedule**;
  positive forces a flat grid. 15 tests + the acceptance criterion. **Money-path regression
  520 passed.**
  ⭐ **Measured from `ohlcv_1d`, not guessed:** sub-₹250 closes on the ₹0.05 grid ran 96–98%
  through 2020, 84–88% to 2024-05, **38.98% in 2024-06**, then 20.8–23.3% (= the 1-in-5 chance
  rate) from 2024-07. **≥₹250 never moved.** ⇒ the change took effect **June 2024**.
  ⭐⭐ **The boundary is a ZONE, not a cliff** — ₹225–250 is 39% on ₹0.05, ₹250–275 is 67%,
  ₹275–300 is 84%. The tick is a property of the INSTRUMENT (set at a review, sticky), not of
  the current price. **So the cut is at ₹225, the low end** — that can over-charge a ₹0.01 name
  but never under-charge a ₹0.05 one, which is the module contract. A ₹250 cut would have been
  wrong for ~a third of that zone.
  ⚠ **Also fixed en route:** my own round-10 PHASES edit broke the `(updated YYYY-MM-DD)` stamp
  and `tests/test_doc_sync.py` caught it. The ritual works.

- **B1 DONE.** Both undeclared display filters **removed** (not declared) — the choppy one was
  measured at **t = −0.00, p = 0.999** on 185 trades while hiding **67%** of the offered set.
  Acceptance test added: a signal that trips BOTH rules is still offered, and the registry is
  asserted to declare neither.
  ⚠ **Scope grew by one honest step:** the Dashboard had real user-facing toggles wired to the
  deleted params, so they were about to become DEAD CONTROLS. Converted to **client-side focus
  filters with the opposite sense** ("Hide near-expiry" / "Hide choppy", default off) — the data
  (`near_expiry`, `choppy`, `regime_er`) is already on every row, and toggling now costs no
  refetch. Backend 67 tests green; **frontend 428 green**, tsc + eslint clean.

- **B4 DONE — and it shipped a defect that the verification run caught.** `market_calendar`
  gained `observed_session_index` / `session_span` / `window_has_holes`; the two hardcoded
  `GAP_LO`/`GAP_HI` constants are **deleted**.
  ⛔⛔ **The first version tested observed SESSIONS only and flagged 3 trades where the old
  guard flagged 38.** During the 922-day hole NOBODY has bars, so those dates are absent from
  the observed calendar and a straddling window reads as ~300 sessions for 300 rows —
  contiguous. **Only the wall clock sees it** (~1,340 days vs ~440). ⭐ **A hole is invisible
  to exactly the instrument that defines "normal" using the same data the hole is missing
  from.** Now runs BOTH tests OR-ed, with a regression test.
  ✅ **Re-verified full corpus: 40 straddling / 145 clean** vs the old 38 / 147 — catches
  everything the endpoint test did **plus 2 per-name holes**. Contrast t +0.88, so no
  conclusion moves. ⚠ **`probe-147` → `probe-145`; `clean × BUY` is now n = 60, not 61**
  (recorded as §16.1d).
  ⚠ **BLOCKED, not skipped:** B4's third target, `run_single_stock`'s bar-50 walk, is inside
  the **FROZEN** `app/backtest/engine.py`. Needs sign-off + §8 regression + regenerated Rust
  fixtures. `positional_probe.py` has no guard to replace — it gets one with B5.

- **B5 DONE — and it ANSWERED E1.** `positional_probe.py` gained `T`/`bench`/`excess`/`ret_atr`/
  `cash`/`atr_pct` + the gap flag (all helpers **imported** from the swing probe, W2), B4's span
  guard (which it never had), a four-unit bucket report with **contrasts + SEs + MDEs**, and
  `--dump-trades`. **1,585 trade records; 390 on the live rule.**
  ⭐⭐ **THE VERDICT: positional closes the same way swing did.** The contrast decays
  **R −0.4879 (t −1.89) → raw % −0.7870 (t −1.18) → excess vs basket −0.1909 (t −0.29)**.
  ⛔ **§12.27's "opposite signs ⇒ different mechanism" is WITHDRAWN against itself:** `E[1/w]`
  jumps **110×** at the first bucket (43.4 vs 0.352, i.e. ~0.026% stops) and net ₹ there is
  **−25,808/trade**. A leverage point, on a cohort the order path refuses.
  ⭐ `drift × T` confirmed a second time on a different class: mean `T` 6.4 → 32.9 sessions.
  ⇒ **§4.4, §12.1, §12.2, the cap sweep and the σ_R objective all close with it.**
  ⚠ The RELABEL question is untouched. New fact: positional mean `T` is 6–33 sessions vs swing's
  **3.59**, so the classes DO differ in realised hold even though their rule sets are not
  separable by outcome.

- **B6 + B7 DONE — and E2 is ANSWERED.** Pre-registration committed at `fe5d508` **before** the
  code, with 2 timestamped amendments (signed score; global session grid + `E[z]` on the absolute
  score — both found by smoke-running, both pre-result).
  ⭐⭐ **3a unconditional IC at h=5d = −0.0070, 90% [−0.0259, +0.0119] ⇒ NULL** on the
  pre-registered band (upper bound below the measured break-even 0.0310). **The scorer carries no
  measurable cross-sectional information; `confidence_pct` is flatter still (+0.0024).**
  ⚠ **3b is INCONCLUSIVE, reported as such** — point estimate −0.3150% (passers UNDERPERFORM) but
  the upper bound +0.388% clears the +0.255% break-even. ⇒ **the RANKER is dead, the GATE is
  unproven in both directions. The clean-closure branch does NOT fire cleanly.**
  ⭐ **Two assumed constants retired:** `sd(IC_t)` 0.10 → **0.1126**; **`E[z|selected]` 2.268 →
  1.8506** ⇒ every break-even-IC figure rises ~23%; break-even IC is **0.0310**.
  ⭐⭐ **B7: MFE/|MAE| = 0.83 / 1.12 — symmetric, so no geometry repair.** And **the hazard curve is
  FLAT** (0.559 → 0.489 over days 0–5, unchanged to day 20) ⇒ **§13.11's hold-period lever is
  RESOLVED AGAINST IT.** The **T=0 cohort** contrast is **t = −4.16** — first past 3.6 in eleven
  rounds — but it is the tight-stop cohort again and the order path already refuses it.
  ⚠ **Prediction scorecard 4 of 7.** The two misses are the useful ones: 3b underpowered rather
  than null, and the hazard FLAT rather than front-loaded (a stronger result than predicted).
