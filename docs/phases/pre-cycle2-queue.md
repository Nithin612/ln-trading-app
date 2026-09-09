# Pre-cycle-2 queue — branch `feature/pre-cycle2-hardening`

**Created 2026-09-06.** Base: `feature/phase6-overlay-walkforward-retune` @ `518b84f`
(69 commits ahead of `main`, 0 behind). This branch carries the remaining work that must
land **before cycle 2's clock starts**.

> **The rule that orders everything** (`docs/quant-agent-findings.md`):
> *anything that changes a recorded number must land BEFORE cycle 2's clock starts.*
> We have already paid this once — paper P&L before and after 2026-08-17 is not comparable
> because the spread-aware fill model landed mid-window, and the 30-day clock had to reset.

---

## 1. Entry check — what is already done

Verified 2026-09-06 against the **artifacts**, not the checkboxes (working rule W1).

### ✅ Bucket A — freeze the numbers — **COMPLETE** (8 items; A30/A31 subsumed by A38)

| item | artifact verified |
|---|---|
| A38 point-in-time `Restrictions` | `app/signals/restrictions.py` (640 ln) · `tests/test_restrictions.py` |
| A21 mark-to-exit | `paper_broker.exit_mark` / `exit_side_for` |
| A37+T3 participation cap | `paper_broker.participation_bps` + `load_median_traded_values_safe` |
| A29 flat DP charge | `fees.dp_charge_per_sell = 15.34` · `tests/test_fees.py` |
| A23 effective-dated fees | `fees.SCHEDULE_HISTORY` + `schedule_for(on)` |
| A26 hot-set refusal | `provisional.apply_hotset_cap` |
| A25 tick-mode assert | `app/broker/tick_mode.py` (270 ln) · `tests/test_tick_mode.py` |
| H6 degenerate-ratio hygiene | `app/core/ratios.py` (140 ln) · `tests/test_ratios.py` |

### ✅ Bucket B — the instruments that read the cycle — **COMPLETE** (11 items)

H8 noise negative-control (`dsr_control.py`, 09-04) · H1 moving-block bootstrap
(`block_bootstrap.py`) · H2 buy-and-hold (`buy_and_hold.py`) · H12 beta/IR (`beta_ir.py`) ·
T11 pin PSR/DSR · H11 MinTRL as headline (`deflated_sharpe.py`) · H4 gate register +
U4 trials counter (`gate_register.py`) · H3 VIX trailing percentile (`market_regime.py`) ·
T7 exhaustive-enum tests (`tests/test_enum_exhaustiveness.py`) · A24 uncertainty rule
(`.claude/rules/ui.md`).

### ✅ Bucket C — partial, deliberately (7 of ~60)

W1–W5 working rules · **A11** session notifier (`notifier.py`) · **A40** worker liveness
(`worker_health.py`) — the last two pulled forward because they are **preconditions for an
unattended accrual**, not work to do during one. They retire the CAS and provisional-health
manual daily checks.

**Everything else in Bucket C stays under cycle 2's clock, by design.** The findings doc's
sequence is explicit: *"build only what must be frozen, start the clock, and let the
remaining ~60 items land while the evidence accumulates."* Three further slices are
**proposed for pulling forward** on the same argument that moved A11/A40 — see **Q1b**.

---

## 2. What "the rest of Phase 6 and Phase 6.8" actually is

Both phases are **GATE PASSED + CLOSED** (2026-08-20) and merged to `main` (ff, push still
pending — push is the user's). Neither has unbuilt slices. What remains is:

- **the shared, gated research track `R1 / R2 / F1`** (listed under both phases), and
- **three forward-evidence loops** carried as explicit non-blocking follow-ups.

Of those loops, one is **decided** (regime gate → REVERTED 2026-09-02), one is **stalled**
(momentum ×1.5: 3 minted, 0 resolved in 6 days — years away by forward accrual), and one is
**accruing** (pair df-vs-adf).

---

## 3. The queue

### Q0 — decisions only the user can make (see §4)

| id | decision | blocks |
|---|---|---|
| ~~**D1**~~ ✅ **DECLINED 2026-09-08** | Sign-off to touch the frozen engine for R1 — **NO**: R1-RVOL refuted read-only (VWAP untestable), so no frozen change is warranted | Q2.2 |
| ⏸ **D2** **PARKED 2026-09-08 → cycle-2 end** | R2 weekly spread-width gate — build or drop. R2 stays provisionally DROPPED (09-07); the FINAL call is deferred until cycle 2 completes, decided on its forward evidence. **Does NOT block cycle-2 start.** Claude owns the flag (review calendar). | Q2.3 |
| ~~**D3**~~ ✅ **RESOLVED 2026-09-08** | MCE 5b market-cap **vendor** — **NO vendor needed**: free-source spike found a free NSE-`/api/` path (`issuedSize × price`, the surface the app already uses for FII/DII); keystone retired, build deferred until a consumer. `docs/analysis/market-cap-source-spike-2026-09-08.md` | Q3.1 |
| ~~**D4**~~ ✅ **DECIDED 2026-09-08** | Concentration/sizing — **minimal rails**: notional cap kept, 6% heat cap unchanged, a max-concurrent-position cap (=3) BUILT in the RiskEngine (`off` → flips at cycle-2 reset), correlation/sector deferred | Q3.4 |
| ~~**D5**~~ ✅ **DECIDED 2026-09-08** | `compute_levels` payoff geometry — **KEEP THE TOURNIQUET** (the R-scored counterfactual showed geometry is not the lever) | Q3.5 |
| **D6** | **Reconciliation's matching key** — Kite has no client-order-id field | `KiteBrokerAdapter` (post-cycle-2, but decide first) |

### Q1 — Phase 7.1–7.4 — **the long pole, fully unblocked, starts now**

| # | slice | content |
|---|---|---|
| **7.0** ✅ **DONE 2026-09-06** | **Design pass first** | A33 OMS-as-projection-of-the-event-stream + A42 frozen/available cash + A35 `BrokerAdapter` interface, designed **together** — the review found these are one problem, not three |
| **7.1** ✅ **DONE 2026-09-06** | RiskEngine single-gate | one pre-trade gate absorbing: daily-loss circuit breaker · the 6 eligibility overlays · notional cap · R:R floor · **the heat cap** (fails CLOSED, `heat = qty × max(0, entry − commit_SL)`, initial risk not MTM). **Equivalence-pinned first** — identical verdicts to today's chain before any refactor |
| **7.2** ✅ **DONE 2026-09-07** | BrokerAdapter port | `PaperBrokerAdapter` behind the interface + a **read-only** Kite spike (order-status, margins, positions; **no placement**) so the shape is validated against reality |
| **7.3** ✅ **DONE 2026-09-07** | Order FSM | Denied vs Rejected vs Filled vs Cancelled + A32 event-bus robustness (per-handler isolation, bounded queue, **a dead bus must be loud**) + A22 partial-fill sibling rebalance + A16 lifecycle/repair queue + A34 timer primitive |
| **7.4** ✅ **DONE 2026-09-07** | Reconciliation + kill switch + audit | recover local state on restart · kill switch honoured everywhere · every decision reconstructable · T2 lifecycle-boundary tests (first step, start mid-stream, stop early) |

### Q1b — Bucket C slices **pulled forward** (proposed)

Three, on the **same argument that already pulled A11 and A40 out of Bucket C**: *"safe to
ship mid-cycle" answers whether a change will disturb the record — not what protects the
record while it is being made.* Everything else in Bucket C stays under the clock.

| # | item | why it cannot wait |
|---|---|---|
| **1.7.1b** ✅ **DONE 2026-09-06** | **A13** — pin the circuit breaker's **un-suppressibility** | **Rides with 7.1, same commit.** 7.1 refactors the breaker *into* the RiskEngine, which is exactly when a hard constraint can be silently lost. It is enforced today by convention and its call site, not by a test that fails if someone routes around it |
| **1.5** ✅ **DONE 2026-09-07** (`make config-check`) | **A27** — config dry-run | `settings` is an `@lru_cache` singleton, so a `.env` change reaches a running process only on re-import. This has bitten repeatedly — it is why CLAUDE.md carries a whole recipe for verifying a gate's live mode. **The cycle-2 reset is itself a config event** (heat cap → enforce, clock → reset); getting it wrong silently invalidates the *window*, not a day |
| **1.6** ✅ **DONE 2026-09-07** | **A3** — broker-token status | The Kite token dies **~6:00 AM IST daily** = 45–50 chances to lapse silently during cycle 2. On lapse the feed stops, `depth:` expires at its 60 s TTL, and spread-aware fills fall back to the flat floor — **paper fills quietly cheaper than reality**. That corrupts the recorded numbers rather than merely interrupting them, which is what makes it a data-quality precondition |

### ▶ Progress — 2026-09-06/07 overnight run

**✅ 7.0 design pass** (`docs/phases/phase-07.0-oms-design.md`) · **✅ 7.1 RiskEngine +
✅ A13** (`app/trading/risk_engine.py`, 33 tests) · **✅ 7.2 BrokerAdapter port**
(`app/broker/adapter.py` + `paper_adapter.py` + a read-only Kite spike, 27 tests) ·
✅ **7.3 DONE** — `order_events` (migration applied + reversible), `order_fsm.py`,
`event_bus.py`, `event_store.py`, and **the order path cut over**: `submitted` is written
BEFORE the gates run, so a decision can no longer fail to be recorded. 42 tests ·
✅ **7.4 DONE** — kill switch (first rule, **does not block exits**), idempotent restart
recovery, and reconciliation that **reports without repairing** and names what it could not
check. 19 tests.

**▶▶ PHASE 7.1–7.4 IS COMPLETE.** The cycle-2 *runtime* prerequisite is met; what remains
before the clock is the strategy/evidence half (CAS-2, MCE 5b+6, `compute_levels`, Minervini)
plus the five open decisions.

### ▶ Progress — 2026-09-09 overnight run (Bucket C, builds DURING accrual)

Twelve Bucket-C items shipped, all touching **no recorded number** (safe mid-cycle), each with
tests + CHANGELOG; the operational-safety cluster (the findings doc's "largest single win") is
done, and the U1 registry page/API landed. **Bucket C now stands at ~17 of ~60** (prior 7 =
W1–W5 · A11 · A40; A27/A3/A13 done pre-09-09).

| item | what | tests |
|---|---|---|
| **A28** | notifier delivery classified retryable-vs-permanent (`DeliveryOutcome`/`DispatchResult` + bounded retry; a 404/401 no longer reads as success) | +14 (34 total) |
| **A36** | proactive NSE calendar-coverage expiry alarm (`calendar_health.py` + daily beat + report line; optional XNSE cross-check) | 15 |
| **A9/A10** | progress envelope for long jobs (`app/core/progress.py`) wired into `make analysis` (stderr, 12 stages) | 14 |
| **H7** | shadow-gate decay alarm (`sharpe_decay.py`) — **only an ACTIVE gate's regression pushes** (bug-hunter MEDIUM fix); shadow regressions recorded, never pushed | 18 |
| **A39** | `cargo-deny` supply-chain gate (`engine/deny.toml` + `make engine-audit`; on-demand, tool not vendored) | TOML valid |
| **T9** | doc-sync ritual as a failing test (`test_doc_sync.py`) — W3 config drift, report-all-at-once, T8 shrinking-debt baseline | 8 |
| **A15** | schedule invariant (`test_schedule_invariants.py`) — CAS window ≥ beat tick; coverage-close == capture-end | 3 |
| **T13/T14** | T13 tautological here (batch ≡ incremental by construction — recorded); T14 external hand-computed RSI+ATR anchors independent of pandas-ta (ADX deferred) | +3 (engine) |
| **T10** | notifier negative-space: a policy-suppressed / throttled notification never reaches the wire | +2 |
| **U1** | Gate Register page (`/analytics/registry`) + `GET /analytics/gate-register` — shadow-gate evidence as data+UI; reverted/decided kept visible (U6); ui-reviewer PASS (contrast fix via hardened `--color-loss`) | 4 api + 5 vitest |

**Reviews:** bug-hunter on the ops-safety cluster (A28/A36/A9/A10 sound, one H7 MEDIUM fixed
same-day); ui-reviewer PASS-WITH-NOTES on U1 (all notes fixed).

### ▶ Progress — 2026-09-09 (later, user-directed): U1 detail/cohort TRIO (U10/U15/U17) shipped

Plan + sign-off in [`phase-U1-detail-cohort-plan.md`](phase-U1-detail-cohort-plan.md) (decisions
A/B/C/D as recommended). The trio needed **almost no new API** — `Signal.factor_scores` already
carries every factor incl. score-0 abstainers. Built:

| Item | Landed | Tests |
|---|---|---|
| **U10/U15/U17** | `app/signals/confidence_explain.py` (read-only reconstruction of the confluence arithmetic; frozen engine untouched) → `confidence_breakdown` on `GET /signals/{id}` (detail-only) → redesigned `SignalDetailModal` (U10 arithmetic w/ the abstainer-divisor SRTL surface · U17 one-bar vote · U15 named evidence + horizon) + a `formatScore` helper | 11 (incl. an 800-panel parity sweep) + 3 api + 3 vitest |

quant-verifier PASS — **1 HIGH fixed same-day:** naive `+=` accumulation ≠ frozen `sum()`
(Python 3.12 compensated summation) → off-by-one confidence at truncation edges; now sums via
`sum()` in engine order, bit-identical (0 mismatches over the sweep). ui-reviewer PASS-WITH-NOTES,
actioned: explanatory copy → `--color-text-secondary` (AA in all 5 themes), `formatScore` for the
unit-less values, direction in the bar aria-label. **W1:** fixed the stale `Sidebar.test.tsx` link
counts the U1 nav link had left behind. Reporting-only ⇒ **no recorded number, no clock reset.**
Backend 28 green · full Vitest 421 · mypy/ruff/eslint/tsc clean. **Bucket C now ~18 of ~60.**

**U11 + U20 also shipped 2026-09-09** (same session): **U11** = `benchmark_curve.py` +
`GET /analytics/benchmark-curve` + a dashed benchmark series on `EquityCurveChart` (aligned to the
frozen per-trade equity curve by exit date, fails closed; quant-verifier PASS, ui-reviewer one
`toFixed` fixed). **U20** = `gate_cohort.py` + `GET /analytics/cohort/{gate_key}` (would-block set via
`eligibility.preview`, one gate active — W2) + `has_cohort` on the register + `CohortPage` light-SVG
contact sheet at `/analytics/registry/:gateKey` (quant-verifier PASS-WITH-NOTES: honest scanned/count +
single-owner supported set fixed). ⚠ **Both render EMPTY in the current dev DB** (index_ohlcv_1d +
signals wiped 09-07) — test-backed; a browser smoke needs a dev-DB backfill (user deferred).
**Remaining U1 cluster: U19 only** (horizon/lag chart — a small new analytics endpoint).

**Remaining Bucket C, with an honest read:** **T4/T5/T6/T8** are already satisfied by the Bucket
A/B numeric-test discipline (ratios/block-bootstrap/etc.) — adding more would be hollow; **A5/A7/A12**
are largely covered by the existing dated-incident doc practice (W1–W5, CLAUDE.md truth bullets). So
the meaningful remainder is the **U1 detail/cohort sub-items still open** (U20 would-block cohort ·
U11 · U19 — these need a small analytics API each and are design-sensitive, best done with the user),
plus lower-priority **deployment/misc** (A4/A14/A17/A1/A41). **None attacks profitability** (both
levers spent); all harden the platform and its evidence.

Two findings worth carrying forward:

1. **A refused order is not a row today, it is an exception.** `Order.status` holds exactly
   two values in the codebase — the `"pending"` column default and `"filled"`. So the orders
   table records only successes, and *"what did the risk layer refuse last Tuesday, under
   which thresholds"* is not answerable from data. 7.3 fixes it by writing `submitted`
   **before** the gates run, so a decision cannot fail to be recorded.
2. **⚠ A DECISION IS WAITING (7.2, and it is the user's).** Reconciliation matches a broker
   row back to ours via `client_order_id` — and **Kite has no such field.** The nearest is
   `tag`, **20 characters**, not broker-guaranteed unique; our `paper:<uuid>` ids do not fit.
   Options: short live ids that fit a tag · match on `(symbol, side, quantity, timestamp)`
   (ambiguous exactly when two identical orders are placed together) · a local
   `broker_order_id → client_order_id` map written at ack time, accepting that an order lost
   *before* its ack is unmatchable. **(3) plus a short tag looks right**, but it is a call to
   make before `KiteBrokerAdapter` exists, and it would otherwise be found on live day 1.
3. **The equivalence pin earned its keep immediately.** The breaker runs *before* the signal
   lookup, so an unknown id on a tripped breaker answers **409, not 404** — and the obvious
   refactor (hoist the lookup so the argument is non-optional) silently inverts that. Caught
   by the pin, not by review.

### Q2 — the Phase 6 / 6.8 research track

| # | item | state |
|---|---|---|
| **2.1** ✅ **DONE 2026-09-07** | **F1 `market_cap` spike** | ⛔ **the two size proxies DISAGREE and neither contrast survives its bootstrap** ⇒ recommend **DROP 5b**. **D3 since RESOLVED 2026-09-08** by a free-source spike (no vendor; free NSE-`/api/` path) — see Q3.1 |
| **2.2** ✅ **DROPPED 2026-09-08** (D1 declined) | **R1 VWAP/RVOL as confluence factors** | **REFUTED read-only.** RVOL-at-entry is mildly INVERSE (§1) and injecting a graded RVOL factor makes the book significantly worse (−0.291R at t=−2.91 on the 294 it admits, via scorer dilution); the existing binary VOLUME factor already encodes RVOL and over-captures it. VWAP untestable (no intraday data). No frozen edit made. Report: `docs/analysis/rvol-factor-study-2026-09-08.md` |
| **2.3** ⛔ DROPPED 2026-09-07 · ⏸ **final call PARKED 2026-09-08 → cycle-2 end** (D2) | **R2 weekly spread-width gate** | a 9th gate raises the deflation bar for the other 8 (U4: 15 trials, a lower bound) · the book's Sharpe CI **[−0.223, +0.118]** leaves nothing to partition · both prior promotions were refuted. R2 stays dropped for now; **user 2026-09-08: don't finalise until cycle 2's evidence is in** — Claude flags it at cycle-2 end (review calendar). **May return as a sizing/slippage MODIFIER, never as a gate** |
| **2.4** ✅ **DECIDED NO 2026-09-07** | momentum ×1.5 retune | t = **+1.00** vs a 3.6 hurdle; **not one config clears the bar**, and ⭐ **the winner MOVED** (`structure ×0.5` now leads) — the original best-of-12 pick was the selection itself |
| **2.5** | pair df-vs-adf | accruing nightly — **no build**, just don't lose it |

### Q3 — remaining cycle-2 entry criteria (not named in the ask, but on the checklist)

| # | item | state |
|---|---|---|
| **3.1** ✅ **UNBLOCKED 2026-09-08** (D3 resolved) | MCE 5b `market_cap` writer + T1 PIT test | **No vendor** — free NSE-`/api/` path (`issuedSize × price`, once + CA-triggered; verify fields from the app IP first, `/api/` 403s from a datacenter IP). But **5b itself is DROPPED** (F1: no size signal) and nothing else needs `market_cap` yet, so BUILD only when a consumer appears (screener filter / a fundamentals feature). Spike: `docs/analysis/market-cap-source-spike-2026-09-08.md` |
| **3.2** ⛔ **DEFERRED 2026-09-07** | MCE 6 news veto | **none of its 3 preconditions holds**: 0/322 rating rows carry direction · no forward earnings calendar · **0 of 559 signals hit the existing guard, which has NEVER fired**. RSS+FinBERT is a separate DECISION (locked-stack change) |
| **3.3** ✅ **DONE 2026-09-07** | CAS Stage 2 — the overnight-reversal study | ρ = **−0.272**, 90% interval **[−0.478, −0.088]** excludes zero — the first clean directional signal in the programme. ⚠ Sign survives leave-one-out, **magnitude does not** (~half rests on 2026-08-31). NOT promotable at 7 days |
| **3.4** ✅ **DONE 2026-09-08** (D4) | Concentration/sizing decision | **Minimal rails.** Concentration is a cycle-1 sampling artifact (45–58% heat = ~25–29 sampler positions); cycle 2's ₹1L/1–2-position book can't over-concentrate, so a heat % barely binds and a COUNT is the binding rail. BUILT: `max_concurrent_positions=3` + `position_count_cap_mode` (off/shadow/active) in `risk_engine.py`, a hard design rail (no DSR bar), adding-to-existing exempt, both portfolio rails share one open-book read; `off` now, flips `active` at the cycle-2 reset. Notional cap (1.0) + 6% heat kept; correlation/sector deferred. 42 tests green (9 new) |
| **3.5** ✅ **CLOSED 2026-09-08** | `compute_levels` payoff geometry | **NOT the lever.** Read-only R-scored counterfactual (`scripts/tp_geometry_study.py`, sanctioned `tp_rule`, no frozen edit) on 1,152 swing+positional signals: no constant-R:R geometry (1.0–3.0R) beats frozen — every paired ΔR negative (|t| ≤ 0.65), baseline itself −0.026R, and higher R:R damages the wide-stop majority (the R:R-reversal trap). `compute_levels` stays frozen; the leak is upstream (R1). Report: `docs/analysis/tp-geometry-study-2026-09-08.md`. Untested: a *structural* next-S/R target |
| **3.6** ✅ **TESTED 2026-09-07** | Minervini trend template | ⭐ **0 of 91 entries pass** — DISJOINT from our selection, not an uninformative split. Binding conditions are trend-structure: **we systematically trade names in structural downtrends**. Needs a universe-level corpus rerun, NOT a gate |

### Q5 — ✅ **SPIKE DONE 2026-09-07 · DATA BACKFILLED 2026-09-08** (a review-calendar item that came due)

> ⭐ **The archive starts ~October 2019.** 2015/2018 return **404**; 2019-10-01 and the
> COVID low (2020-03-23) return **200**. So the request *as asked* is a NO — but an
> Oct-2019 start **contains the crash itself**, takes us from 3.2 to ~7 years, and serves
> the purpose better than 2018 would. **The survivorship fix is free**: a bhavcopy lists
> what traded *that day*, so the point-in-time universe reconstructs itself.
> **Sizing: days, not weeks.** ✅ **DATA DONE 2026-09-08:** `backfill_ohlcv_history.py`
> run to the archive floor — `ohlcv_1d` now spans **2019-10-01 → 2026-09-04** (~7 yrs ·
> 1,093 trading days · 2.08M bars · 3,373 names, 2,070 inactive/historical carrying a
> point-in-time universe). ⚠ **Bars are CA-UNADJUSTED** — every 7-yr split/bonus is a fake
> overnight gap; a multi-year study MUST adjust first (no historical CA table for these
> names). **The backtest STUDY is still NOT run**, but its blockers **D1/D5 are BOTH RESOLVED
> 2026-09-08** (D5 closed, D1 declined — the engine stays frozen as-is), so it is now clear to run;
> the binding precondition that remains is **CA-adjusting the historical bars** (above).
> Reports: `docs/analysis/historical-data-spike-2026-09-07.md` (spike) ·
> `docs/analysis/ohlcv-backfill-2026-09-07.md` (backfill)

**The pre-COVID regime-robustness backtest.** The user asked for this on 2026-08-28 and
**held it until after watch mode ended Fri 2026-09-04**. Watch mode is complete, so the
reminder is discharged here rather than carried.

- **It does NOT block cycle 2** — it touches no recorded number, so it runs during accrual.
- **⚠ Hard blocker: `ohlcv_1d` starts 2023-07-03.** Going back to 2018/2015 is a
  **data-acquisition project** (source + CA-adjust historical bhavcopy; reconstruct a
  point-in-time, survivorship-safe universe), not a query. **First step is a sourcing
  spike**, and the decision to proceed comes from the spike's answer.
- **⚠ Value is VALIDATION, not tuning.** Corpus base expectancy is +0.05R over the three
  years we hold; a longer test asks whether that survives another regime. The engine is
  frozen for the current one — older data informs robustness and must not drive tuning.

---

## 4. Concerns raised with the ask

**(a) R2 contradicts a standing ruling.** Gating was **closed as a programme** on 2026-09-04:
eight shadow gates, two promotions both refuted, and the best survivor (`sl_atr`) at
**t ≈ 0.41 against a 3.6 hurdle**. Bucket B then established that the book's Sharpe is
**−0.033 with a 90% interval [−0.223, +0.118]** over 105 closed positions — *at n=105 even
the loss is not established*, so *any* gate partitioning this series is partitioning noise.
Building a ninth gate also **adds a trial**, which raises the deflation bar for everything
else. **Recommendation: drop R2**, or re-scope it as a *sizing/slippage modifier* (the same
reframing already ruled for MCE 5a liquidity), which claims no edge and needs no bar.

**(b) ~~R1 is the one item that attacks the actual leak~~ — ✅ TESTED 2026-09-08: R1 is REFUTED (D1
DECLINED).** It was the one item changing what *generates* candidates rather than selecting among
them — but its only backtestable half, RVOL, carries no edge. Read-only study (`scripts/rvol_factor_study.py`,
1,152 baseline signals, injects a research factor through the frozen scorer — no frozen edit): **§1
RVOL-at-entry is mildly INVERSE** (elevated buckets worst: 1.5–2.0× −0.237R t=−1.71; ≥2.0× −0.157R),
so no factor design extracts edge from it; **§2 injecting a graded RVOL factor makes the book
significantly WORSE** (augmented −0.095R vs baseline −0.026R; the 294 newly-admitted signals −0.291R
at t=−2.91, because the scorer normalizes → dilutes). **VWAP is untestable** (no intraday data →
forward-capture only, Q7). ⇒ **R1-RVOL DROPPED, no frozen-engine sign-off.** The existing binary VOLUME
factor already over-captures volume confirmation. Report: `docs/analysis/rvol-factor-study-2026-09-08.md`.

**(c) ~~The demonstrated lever is D5~~ — ✅ TESTED 2026-09-08: D5 is NOT the lever.** `compute_levels`
pairs a **structural** stop with an **absolute-%** target, so R:R is an accident (**94 of 295 swing
signals R:R < 1 by construction**). The natural "fix" — a constant-R:R target — was measured
read-only (`scripts/tp_geometry_study.py`, 1,152 swing+positional signals): **it does not help**
(every paired ΔR negative, |t| ≤ 0.65) and forcing a higher R:R **damages the wide-stop majority**,
the exact mechanism that reverted the R:R≥1 gate. The premise ("fix the geometry ⇒ expectancy
improves") is false — you can't manufacture edge at the exit from edgeless entries. **D5 closed as
"keep the tourniquet"; `compute_levels` stays frozen.** ~~The real lever is generation (R1)~~ — **R1
was tested the same day and REFUTED (see (b))**, so with selection, exit geometry AND the queued
generation lever all spent, no queued item now attacks profitability; finding a new lever is the open problem.

**(d) The backtest models no trading costs at all.** Backtest P&L is **GROSS**, paper is
**NET** (22–62 bps round-trip + the flat ₹15.34 DP charge). Any R1 §8 regression, and Q2.4's
proposed backtest path, will be judged on a gross-cost engine. Treat every backtest
expectancy as an **upper bound** until this is addressed — also frozen-engine territory.

**(e) Heat has drifted to 58.0%** of capital (₹58,034, 29 open positions, 2026-09-04) with
still no portfolio cap. The cap lands in 7.1 and must **not** be set to enforce until cycle
2 — a 6% cap cuts cycle-1 entries ~74% and cycle 1's purpose is evidence volume.

**(g) D6 — the matching key, raised by the 7.2 spike.** `BrokerOrder.client_order_id` is how
reconciliation matches a broker row back to ours. **Kite has no such field**; the nearest is
`tag`, **20 characters** and not broker-guaranteed unique, and our namespaced ids
(`paper:<uuid>`) do not fit. Three options: short live ids that fit a tag · match on
`(symbol, side, quantity, timestamp)`, which is ambiguous exactly when two identical orders
go out together · or a local `broker_order_id → client_order_id` map written at ack time,
accepting that an order lost *before* its ack is unmatchable. **(3) plus a short tag looks
right.** It only binds when `KiteBrokerAdapter` is written (post-cycle-2), but deciding late
means discovering it on live day 1.

**(f) `main` has not been pushed.** Phase 6 + 6.8 merged fast-forward and are awaiting a
manual push. Push remains the user's (working rule W4).

---

## ⛔ 2026-09-07 — the dev database was destroyed, and what it changes here

A `pytest` run pointed at `trading_platform` instead of `trading_platform_test` truncated
every table. Full account in `CHANGELOG.md` and `RUNBOOK.md` §9. What it does to this queue:

**Unchanged — the build queue is code, and no code was lost.** Phase 7.0–7.4, every script,
every test and every report in `docs/analysis/` are committed. D3/D4/D6 are still
decisions (**D5 closed + D1 declined 2026-09-08 — both profitability levers spent**). The historical-backfill capability
was BUILT during the recovery and is proven
against the real archive.

**Restarted:**

| item | effect |
|---|---|
| **Q4 — cycle-2 gate** | needs a fresh book; cycle-1 accrual (138 positions, ~7 weeks) is gone |
| **CAS Stage-2 re-accrual** | 8 of the ≥30 needed sessions lost — ~2 weeks, on a clock that had not started |
| **2.5 pair df-vs-adf**, momentum ×1.5 forward evidence | restart from zero |

**No go-live milestone moved.** Cycle 1's 30-day clock was ruled *informational* on
2026-09-02 and cycle 2's had not started — see `docs/phases/phase-07-live-trading-plan.md`.

**User ruling: the lost rows are NOT reconstructed** from the daily reports. Exit coverage
there is only ~25%, and realised P&L would have to be recomputed under fee models that landed
2026-09-05, so a rebuilt book would look real while disagreeing with what was recorded. The
ledger stands as written; accrual restarts from day 1.

**▶ Q7 — OUTSTANDING RECOVERY GAP (queued 2026-09-08, deferred "later" by the user) — stock
membership/classification flags are sparse.** The reseed (`seed_stocks.py`, public CSVs) restored
symbol identity but almost none of the metadata: `is_fno` **45** (true ~180–220) · `is_nifty50`
**5** · `is_banknifty` **0** · `is_finnifty` **4** · `sector`/`industry` **165 of 1,322** ·
`market_cap_cr` **0** · all intraday OHLCV tables (`ohlcv_1m/5m/15m/1h`) **empty**. Consequences:
the screener and any flag-scoped bench/backtest silently shrink (a "NIFTY50" backtest runs on **5**
names), §7 F&O engine-health is under-counted, MCE sector-RS has no membership to benchmark against,
and **anything VWAP/intraday cannot be backtested at all** (bears directly on R1 — see Q2.2). **Not a
recorded-number change** (the frozen engine reads none of these flags), so it does NOT block cycle 2,
but it must be restored before any flag-scoped or intraday study is trusted. `market_cap_cr` now has a
known **free** path (**D3 resolved 2026-09-08** — NSE-`/api/` `issuedSize × price`, no vendor; build
deferred until a consumer). Fix the flags: re-derive index/F&O membership + sector from a source (the
NSE indices CSVs already used by `vix_service`/`backfill_indices`; F&O from the Kite instruments dump or
the NSE F&O list); intraday history has no free archive (forward-capture only).

