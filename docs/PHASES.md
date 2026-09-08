# Phase plan & status

Two eras: the **v1 build-out** (2025 → mid-2026, complete) and the **v2
upgrade** (current — approved 2026-07-03). The v2 plan's full rationale,
architecture decisions, and risks live in `docs/UPGRADE_PLAN.md`; each
completed phase writes a detailed report to `docs/phases/`.

Rule unchanged since v1: one phase at a time, vertical slices, green tests +
working demo + agent reviews before the next phase starts (`/phase-gate`).

---

## ▶ STATE AT A GLANCE (updated 2026-09-08) — read this block first

**▶▶ 2026-09-08 (latest) — D3 RESOLVED by a free-source spike: NO vendor needed. The Q0 decision queue is CLEARED for cycle-2 start — D2's final call is PARKED to cycle-2 end (user 2026-09-08), D6 is post-cycle-2.**
The long-standing "`market_cap` has no writer → pick a vendor" **keystone is RETIRED.** Spike
(`docs/analysis/market-cap-source-spike-2026-09-08.md`): no free BULK file carries per-stock market cap
(bhavcopy = OHLCV+delivery, `ind_close_all` = per-index), **but a free per-symbol path exists on the NSE
`/api/` surface the app ALREADY uses in production** (`fii_dii_service` → `fiidiiTradeReact`) —
`quote-equity` returns `issuedSize` (shares outstanding) + `trade_info.totalMarketCap`/`ffmc`, so
`market_cap = issuedSize × price` is computable daily from stored OHLCV after only an occasional
(CA-triggered) shares-outstanding fetch — far lighter than MCE 5b's XBRL scraper, and **$0**. ⚠ NSE
`/api/` 403s from a datacenter IP, so confirm the field names from the app's own IP before building.
**Build DEFERRED — nothing needs `market_cap` now** (F1 killed the size floor ⇒ 5b dropped; cycle 2
doesn't use it; only the inert screener filter consumes it); build from this free path when a real
consumer appears.

**▶▶ 2026-09-08 — D4 DECIDED (concentration/sizing) + the max-concurrent-position cap BUILT.**
Ruling: **minimal rails.** Keep the per-position notional cap (leverage 1.0); the 6% heat cap stays
as-is (built, `off`, fails closed, flips at the cycle-2 reset); and a NEW **max-concurrent-position
cap** is BUILT in the RiskEngine (`position_count_cap_mode` off/shadow/active + `max_concurrent_positions=3`,
`off` now → flips `active` at the cycle-2 reset alongside the heat cap). ⭐ **Rationale: concentration
is a CYCLE-1 sampling artifact** — the 45–58% heat came from ~25–29 sampler positions; cycle 2's
₹1L / 1–2-position book can't structurally over-concentrate, so a heat *percentage* barely binds and a
**count** is the rail that actually enforces the 1–2 intent. It is a HARD design rail (like
`entry_diversity`), **no deflated-Sharpe bar**; adding to an existing position is exempt; both
portfolio-state rails share one open-book read. Correlation/sector-aware heat DEFERRED (over-engineering
for 1–2 positions). Empirically a heat cap is a RISK control, not a profitability fix (counterfactual:
per-trade −₹1,478 vs −₹796). 42 risk-engine tests green (9 new). **Open decisions now: D2 (R2 — recommend
drop) · D3 (MCE vendor), plus D6 (post-cycle-2).**

**▶▶ 2026-09-08 — D1 DECLINED: R1's testable half (RVOL) is refuted, VWAP is untestable — and with it, the LAST queued profitability lever is spent.**
No frozen-engine sign-off. `scripts/rvol_factor_study.py` (read-only — injects a research factor
through the frozen scorer, so **no frozen edit, no recorded number moved**) on **1,152 baseline
swing+positional signals** (150 liquid names): **§1 (design-free): RVOL-at-entry carries NO positive
outcome signal and is mildly INVERSE** — the two *elevated* buckets are the worst (1.5–2.0× −0.237R,
t=−1.71; ≥2.0× −0.157R), exactly where the existing VOLUME factor fires. **§2: injecting a graded RVOL
factor makes the book significantly WORSE** (augmented −0.095R vs baseline −0.026R; the 294 signals it
newly admits average **−0.291R at t=−2.91**) — the scorer normalizes, so a graded confirmation dilutes
and re-shuffles rather than adds. **VWAP has no intraday data to test on** (deferred to forward-capture,
Q7). ⇒ **R1-RVOL DROPPED**; the existing binary VOLUME factor already over-captures volume confirmation.
Report: `docs/analysis/rvol-factor-study-2026-09-08.md`. **(D3 + D4 have since been resolved too — see
the top entries; D2's final call is parked to cycle-2 end and D6 is post-cycle-2 — no decision blocks cycle-2 start.)** ⭐ **With selection (gating — closed as a programme), exit geometry (D5)
and the queued generation lever (R1) ALL now spent, no queued item attacks profitability.** The edge
question is unresolved and the remaining pre-cycle-2 work is *entry criteria* (MCE 5b+6/D3, sizing/D4,
CAS-2 re-accrual) + the (built) Phase 7 — not a new lever. Finding one is now the real open problem.

**▶▶ 2026-09-08 — D5 DECIDED: the take-profit geometry is NOT the lever; the tourniquet stays.**
The BANKED CAUTION's own prescription — a read-only, **R-scored** target-rule counterfactual — was
built (`scripts/tp_geometry_study.py`, riding the sanctioned `tp_rule` freeze-extension, so **no
frozen code was touched and no recorded number moved**) and run on **1,152 swing+positional signals**
(150 liquid names by traded value, CA-clean 2023-07-03+; paired on `(stock, entry_date)`, entries+stops
held fixed, only the target varied). **No constant-R:R geometry (1.0–3.0R) improves expectancy:** every
candidate's paired ΔR vs frozen is *negative* (−0.012 to −0.025R, |t| ≤ 0.65, wrong sign), the baseline
itself is −0.026R, and the only cohort a higher R:R helps is the tight-stop *minority* (199/1,152) — at
the cost of the **wide-stop majority** (547 trades: rr_2.0 −0.090, rr_3.0 −0.110R), the exact
R:R-reversal mechanism that reverted the R:R≥1 gate. ⇒ **`compute_levels` stays frozen; D5 is CLOSED as
"keep the tourniquet".** You cannot manufacture edge at the *exit* from entries that carry none — the
leak is upstream in candidate *generation* (R1 — **since REFUTED too, see the D1 entry above**). Report:
`docs/analysis/tp-geometry-study-2026-09-08.md`. Untested: a *structural* (next-S/R) target rather than
the constant-R:R family — a genuinely different hypothesis, but a strong prior says re-slicing an edgeless
set won't rescue it. ⚠ Separately surfaced: the post-wipe reseed left the membership/classification
flags sparse (`is_fno` 45, `is_nifty50` 5, `is_banknifty` 0, `sector` 165/1322, `market_cap_cr` 0) — a
metadata-restore task, harmless to this study (universe derived from `ohlcv_1d` traded value, not flags).

**▶▶ 2026-09-07 — CAS STAGE 2 IS DONE, AND IT FOUND SOMETHING.** The closing-auction
move **REVERSES overnight, cross-sectionally**: Spearman **ρ = −0.272**, 90% **day-block**
interval **[−0.478, −0.088]** (excludes zero), **6 of 7 days negative**, monotonic quintiles,
**Q1−Q5 spread +1.27%**. This is the **first clean directional signal the programme has
produced** after eight refuted gates — which is why it got the strictest available reading.
⭐ **The control is cross-sectional demeaning within each day**, which removes the market factor
*exactly* and discharges the standing "control for the oversold regime" warning; ⚠ it therefore
says **nothing about a market-wide auction effect**, by construction.
⭐ **The independent unit is the DAY, not the row** — 1,664 rows are **7 usable blocks**, and
resampling rows would have shrunk the interval ~**14×** and manufactured significance.
⚠ **The tail check SPLITS:** the **sign survives every leave-one-out** (all 7 negative), but the
**magnitude does not** — dropping 2026-08-31 takes ρ to **−0.125 (46% of full sample)**, so ~half
the effect rests on one afternoon that carries ~5× the usual dispersion.
⚠ **NOT PROMOTABLE, and the report says so itself:** 7 days cannot clear **t ≈ 3.6**, and that
hurdle is **flat in n**. **Keep the Stage-1 capture running and re-run at ≥30 days.**
Script: `scripts/cas_stage2_study.py` (seeded, rerunnable) · report:
`docs/analysis/cas-stage2-2026-09-07.md`.


**▶▶ 2026-09-07 (latest) — PHASE 7.1–7.4 IS COMPLETE. The cycle-2 RUNTIME prerequisite is met.**
On branch `feature/pre-cycle2-hardening`; full suite green throughout. **7.2** shipped the
`BrokerAdapter` port whose one rule is that **`submit()` returns an `Ack`, never a `Fill`** — paper
gives up its own synchrony so the abstraction is not met on day 1 of live — plus a **read-only Kite
spike** (`ThrottledKite` deliberately has **no `place_order` method**; the absence is the
safeguard). **7.3** made the order path record its own decisions: `order_events` is durable and
`submitted` is written **BEFORE the gates run**, so a decision can no longer fail to be recorded.
⭐ **The defect it nearly shipped with:** `get_db` rolls back when a handler raises, so without an
explicit commit *before* `raise HTTPException` the denial row is written and discarded — the record
vanishing in exactly the branch it exists to capture, with every other test still green.
**7.4** added the **kill switch** (the FIRST rule, ahead of the breaker — and it deliberately
**does NOT block exits**, because a switch that traps you in open positions is a hazard dressed as
a safety feature), **idempotent restart recovery**, and **reconciliation that reports and never
repairs** — and that **names what it could not check**, since the paper gateway's
`fetch_open_orders()` is structurally empty and a bare "clean" would read as evidence when it is
the absence of evidence.
⚠ **Still open: the strategy/evidence half of the cycle-2 checklist** (CAS-2 · MCE 5b+6 ·
Minervini; **D5/`compute_levels` CLOSED + D1/R1 DECLINED 09-08 — both profitability levers spent**)
**and the decisions D2–D4**, plus **D6** newly raised by the
Kite spike: **Kite has no client-order-id field** (`tag` is 20 chars, not guaranteed unique) and
our namespaced ids do not fit — reconciliation's matching key needs a decision before
`KiteBrokerAdapter` is written.


**▶ 2026-09-06/07 (latest) — PHASE 7 HAS STARTED: 7.0 DESIGNED, 7.1 BUILT.** On branch
`feature/pre-cycle2-hardening`. **7.0** (`docs/phases/phase-07.0-oms-design.md`) settled A33+A42+A35
together, as the review insisted they must be. Its findings: **a refused order is not a row today,
it is an exception** — `Order.status` holds exactly two values in the codebase (the `"pending"`
default and `"filled"`), so the orders table records only successes and *"what did the risk layer
refuse last Tuesday, under which thresholds"* is **not answerable from data**; **`submit()` must
return an `Ack`, never a `Fill`**, or paper's synchronous fill leaks into the interface and the
abstraction is met on day 1 of live; and **available cash is DERIVED from the active-order set,
never stored** (a stored balance is a fourth writer to a truth three tables already own, and it
drifts silently). **7.1** shipped `app/trading/risk_engine.py` — ONE gate composing breaker →
signal existence → signal status → the A38 registry, then notional cap → heat cap; it *composes*
rather than reimplements, so `restrictions.py` stays the single declaration (W2).
⭐ **The equivalence pin earned its keep immediately:** the breaker runs *before* the signal
lookup, so an unknown id on a tripped breaker answers **409, not 404** — and the obvious refactor
(hoist the lookup so the argument is non-optional) silently inverts that pair. Caught by the pin,
not by review. **The heat cap is BUILT and `off`** (`heat_cap_mode`) — a 6% cap cuts cycle-1
entries ~74% and cycle 1 exists to accrue volume, so it flips at the **cycle-2 reset**. Unlike the
six selection overlays it **FAILS CLOSED**: unmeasurable open risk refuses the next entry rather
than counting as zero. **A13** rode with it (the breaker runs first, has **no disable knob** — the
test asserts the *absence* — and still denies with every gate mode forced off). 33 new tests;
`trials_attempted()` deliberately **stays 15** (the heat cap keeps its counted trial, because it
did claim an edge and was refuted — dropping it would be the selection bias the deflation corrects).


**▶ 2026-09-06 (latest) — BUCKETS A AND B ARE COMPLETE, AND THE PRE-CYCLE-2 QUEUE IS OPEN ON A NEW
BRANCH.** All 8 Bucket-A items (the ones that change a recorded number) and all 11 Bucket-B items
(the instruments that will read the cycle) have code **and** tests on disk — verified against the
artifacts, not the checkboxes (**W1**), which is how the findings doc's own Bucket-B table was
caught four items stale. Bucket C stands at **7 of ~60** (W1–W5 · A11 · A40) and the rest builds
*under* cycle 2's clock, deliberately. **New working branch `feature/pre-cycle2-hardening`**
(approved, cut from `feature/phase6-overlay-walkforward-retune` @ `518b84f`) carries what is left:
**Phase 7.1–7.4 — the long pole, fully unblocked, starting now** · the shared Phase-6/6.8 research
track R1/R2/F1 · and the cycle-2 entry criteria that were not in the original ask but sit on the
checklist (MCE 5b+6 · CAS-2 · sizing; `compute_levels`/D5 + R1/D1 both closed 09-08). Queue, deps, rationale:
[`docs/phases/pre-cycle2-queue.md`](phases/pre-cycle2-queue.md).
⚠ **NO decision blocks cycle-2 start.** **D2** (R2 build-or-drop) is **PARKED to cycle-2 end** (user
2026-09-08 — R2 stays provisionally dropped; the final keep-or-revive call waits on cycle-2 forward
evidence; Claude flags it at cycle-2 end via the review calendar). **D6** (reconciliation matching key)
is post-cycle-2. ✅ **D3 RESOLVED 2026-09-08** — free-source spike: no
vendor needed (free NSE-`/api/` `issuedSize × price` path; keystone retired; build deferred until a
consumer). ✅ **D4 DECIDED 2026-09-08** — minimal rails: notional + 6% heat kept, a max-concurrent-position
cap (=3) BUILT in the RiskEngine (`off`, flips at cycle-2 reset); concentration is a cycle-1 artifact so a
count binds, not a heat %. ✅ **D1 DECLINED 2026-09-08** — R1-RVOL refuted (elevated RVOL mildly inverse;
injecting it −0.291R at t=−2.91), VWAP untestable. ✅ **D5 CLOSED 2026-09-08** — no constant-R:R geometry
beats frozen; `compute_levels` stays frozen. **Both profitability levers (exit geometry + generation) are
spent** — see the D1 top entry.
⚠ **"The rest of Phase 6 / 6.8" has no unbuilt slices** — both are GATE PASSED + CLOSED; what
remains is R2/F1 (**R1 DROPPED 09-08 — refuted**) plus three forward-evidence loops (one decided,
one **stalled**, one accruing).


**▶ 2026-09-04 (latest) — H8 DONE: THE DEFLATED-SHARPE BAR IS VALIDATED, AND GATING IS CLOSED AS A
PROGRAMME.** The bar rejects noise (1.10% on best-of-20 zero-edge selection, against a 5% design
allowance) **and** accepts real edges (80% power at a true per-trade Sharpe of 0.52), so its
verdicts can be acted on. **⭐ Restated as a t-statistic the bar demands t ≈ 3.6, flat in n** — just
above Harvey/Liu/Zhu's recommended t > 3.0 for a new factor, so it is defensibly calibrated rather
than arbitrary; and because the hurdle does not fall with n, **more data cannot rescue a candidate
that is not already ahead** (which is exactly what MinTRL has been saying). ⇒ **`sl_atr` is DECIDED:
NO** (t ≈ 0.41 vs 3.6 — short by ~9×, despite passing all three readiness guards); its 20-trade
trigger is withdrawn. ⇒ **The leak is upstream of gating, now demonstrated:** eight gates, two
refuted promotions, best survivor at t = 0.41 — the trades carry no edge to partition. Report:
`docs/analysis/dsr-negative-control-2026-09-04.md`; guard: `tests/test_dsr_control.py` (14 tests).
⚠ H8 as specified was insufficient — it asked only "does the bar reject noise", which a bar that
rejects everything passes trivially; the power arm was added and is what made the verdict readable.

**▶ 2026-09-04 (later) — GATE STATE RECONCILED. The R:R floor is VERIFIED `shadow` in both live
processes** (fresh settings load + uvicorn reload-child and celery start times both post-dating the
09-03 revert commit at 09:34:45). `config.py`'s default moved `"active"` → `"shadow"` so a fresh
checkout cannot run the refuted state, and its comment block — still arguing the premise the tape
falsified — was rewritten. **The reusable recipe for verifying a gate without reading the
hook-protected `.env` is now in CLAUDE.md.** ⚠ The same pass found `STATUS.html` three weeks stale
on gate modes (**"2 live · 5 shadow"**, regime shown ACTIVE in four places) plus five other stale
figures; all corrected. **`STATUS.html` hardcodes modes in prose, tables and an ASCII diagram — grep
every gate name there on every flip.** No live behaviour changed by any of this.

**▶ 2026-09-04 — WATCH MODE COMPLETE + a 30-repo external review landed.**
- **CAS Stage-1 accrual finished healthy**: `cas_daily` = **1,664 rows / 8 sessions**, last
  2026-09-04, no session missed. The daily row-count check is **discharged**, not carried forward.
- **`docs/quant-agent-findings.md` (4,358 lines)** — 30 external repos audited across five queues
  (analysis · UI/UX · architecture · testing · workbench), **91 items, all bucketed** into a
  sequenced **"Execution plan — sequenced to cycle 2"**. Governing rule: *anything that changes a
  recorded number must land BEFORE cycle 2's clock*; ~60 items touch no recorded number and can be
  built during accrual. **Zero lines of external code adopted.**
- **Six findings were about OUR code**: **A21** marks aren't spread-aware though fills are ·
  **A25** we harvest depth from `MODE_FULL` ticks without checking the mode (fail-open ⇒ silent) ·
  **A29/A30** no flat DP charge, and the backtest ignores circuit bands the order path enforces ·
  **A42** no frozen-capital concept (harmless until Phase 7 has pending orders) · **T13/T14**
  `incremental_equals_batch` on 2 indicators only, and the fixture chain (Rust←Python←pandas-ta)
  has **no external anchor**. Plus one **validation**: our PSR is *correct* where QuantStats' —
  the field's most-used tearsheet library — is **wrong** (it feeds pandas *excess* kurtosis into a
  formula expecting *Pearson*, overstating PSR).
- **Calibration to hold** (from a 4,843-paper replication record): **median published Sharpe 0.37,
  half indistinguishable from zero on their own sample, ~half the median edge is index beta.**
  A −0.303R book measured honestly is an *early-stage* position on that distribution, not an
  anomalous one; **2–3%/day is not on that distribution at all.**
- ⚠ **Heat drifted 45.3% → 58.0%** of capital (₹58,034, 29 open positions). Still no portfolio cap.
- ⚠ **The plan buys evaluation, not edge.** The known lever — `compute_levels` producing **94/295
  swing signals with R:R < 1 by construction** — is frozen-engine work and is **not** in the plan.

**▶ 2026-09-03 — the deflated-Sharpe bar shipped** (see the entry below) and **user rulings**:
never create a branch without approval; **`feature/phase6-overlay-walkforward-retune` is THE
working branch** for everything except Phase 7.


**▶ DECISION 2026-09-02 — the REGIME GATE IS REVERTED TO SHADOW** (user sign-off; decision record:
`docs/analysis/regime-gate-revert-2026-09-02.md`). The gate went ACTIVE 2026-08-14 on a ✅ READY
banner at **44** resolved suppressed trades. Its pre-registered revert condition
(`phases/phase-06-plan.md` follow-up 1: *"if the banner diverges (⏳ NOT READY), revert"*) fired on
2026-08-21 and has stayed fired for **7 consecutive report days**: the suppressed set is
**net-POSITIVE on the live tape** (+0.090 expR at 09-01, sign never once negative, `decided` grown
54 → 88 = **4.4× the 20-trade bar**). **All three §8 metrics that justified the flip have inverted** —
win rate 30% kept vs 36% suppressed, Sharpe −0.041 vs +0.044, maxDD 34.5R vs 11.2R; gating moves
total-R from −2.0R ungated to **−10.0R**, i.e. the gate SUBTRACTS ~8R by removing a +7.9R cohort.
Verified enforcing (0 transitional positions opened since 08-14) — so this was real, not a phantom.
It was also suppressing **37 of 204** visible signals. **Action:** `REGIME_GATE_MODE=shadow` + backend
& worker restart (user-run — `.env` is hook-protected); gate modes are now documented in
`.env.example`. **Lesson (standing):** a gate promoted on 44 observations was refuted by 88 — no
shadow→active flip without its pre-registered count AND a multiple-testing-aware bar.
**No other gate mode moved:** diversity stays ACTIVE (evidence intact); chase 4/20, sl_atr 17/20,
liquidity 19/20 (already ruled don't-flip), circuit 0/20, sector-RS do-not-flip all stay shadow.

**▶ ALSO 2026-09-02 — entry/eligibility audit** (from a desk question: *"signals were already dead in
live market"*). Findings, evidence-backed on 99 resolved trades since 07-19: (1) **expectancy is
−0.303R/trade** (24 closed since the 08-17 cut: 37.5% win, avg win +1.14R, avg loss −1.17R) — needs
1.67R payoff at that win rate; (2) **payoff is capped by construction** — `compute_levels` pairs a
STRUCTURAL stop with an ABSOLUTE-% target (swing TP = entry +6%, positional +15%), so R:R is an
accident: **94 of 295 swing signals have R:R < 1**, 213 < 2, and 6 of the 23 open positions have
targets closer than their stops. There is **no minimum-R:R gate anywhere**; (3) **tight stops are the
₹ sink** — 14 trades with stops <2% of price lost ₹25,951 at 29% win, worst −2.01R, because fill cost
is a fixed price amount (6 of 10 fills on 09-01 pinned the 50bps impact cap = order ~10× top-of-book);
(4) **overlays gate the ORDER path, not the DISPLAY path** — 41 of 204 listed signals carry a Buy
button that 409s; (5) **`size_for_fill` uses `abs(fill − stop_loss)`** so a BUY can be sized/filled
BELOW its own stop — **one such position already exists in the DB** (bug, fix queued); (6) **portfolio
heat is 45.3%** of ₹1L across 23 open positions (18 underwater) with **no heat cap and no
max-position limit in the codebase** — Elder's rule is 6%, Tharp's 6–10%; (7) the **entry price is
literally yesterday's close** (`signal_service.py:236`) and the live entry zone is **symmetric
±0.5%**, so a BUY drifting DOWN into entry fires "Entered zone" — the setup failing reads as the
setup triggering. Cohort split: **44 trades carrying ≥1 mechanical defect = −₹19,649; the 55 clean
ones = +₹5,256 at 55% win.** Fix queue (post-watch-mode, none started): display honesty → R:R floor
overlay (shadow-first) → directional trigger zones + entry window → heat cap → position-advisory
upgrade.

**▶ ⚠ MARKET-REGIME SIDECAR NOW READS ✅ READY (2026-09-02) — DO NOT ACT ON IT.** The gate would
block **405 of 545 signals (74% of the book)**. Its blocked set has a **HIGHER win rate than the
eligible set (52% vs 45%)** but a much worse mean (−₹302 vs −₹7) — the signature of a few large
losers driving the average, which is what the memory already warned about ("BLUNT … mean driven by
few big losers"). **The coded readiness bar tests count + mean + mean-comparison, but NOT whether the
sign survives removing the tail** — and the regime gate cleared that same bar in August on 44
observations and was refuted by 88. This is precisely the gap the post-watch-mode queue's item 1
(deflated Sharpe / multiple-testing bar) exists to close. **Build the bar before believing this
banner.** (Meanwhile the regime gate's own suppressed set reached **91 resolved at +0.078 expR** on
09-02 — an 8th consecutive positive reading, further confirming the revert.)

**▶ ✅ SHIPPED 2026-09-02 (user-approved): the DENOMINATOR FIX + the HEAT COUNTERFACTUAL.**
`paper_sampling_capital_inr` (**reporting only** — never touches sizing, so no trade changes size and
history stays comparable) lets the daily report print exposure against BOTH the ₹1L LIVE figure and
the declared ₹5L sampling scale, labelled: the same 23 positions are *45.3%* of one and *9.1%* of the
other. Replacing one misleading denominator with a different one would have been no improvement.
Plus `app/services/heat_counterfactual.py` + a `heat-counterfactual-<date>.md` sidecar in
`make analysis`. ⚠ **Two self-corrections worth keeping:** (1) the first run defaulted to
`OUTCOME_EPOCH` and silently spanned the **08-17 cut**, where sizing moved from the signal entry to
the actual fill AND the honest fill model started — the tell was admission risks of ₹5,663 against a
₹2,000 budget; it now takes `user.paper_clock_started_at`, the clock's own epoch. (2) the first
verdict string said "the cap would have HELPED" on TOTAL P&L alone, which is misleading because
admission is CHRONOLOGICAL (selects by arrival time, not quality — one ₹6,000 entry can eat the whole
budget); it now reports per-trade too and names that limit in the report body.

**▶ ▶ GOVERNANCE 2026-09-02 — TWO PAPER CYCLES, NOT ONE (user ruling).** Full plan:
[`phases/phase-07-live-trading-plan.md`](phases/phase-07-live-trading-plan.md).
**Cycle 1 = the sampler running now** — deliberately wide (~5 entries/day, ~5-day holds ⇒ ~25
concurrent positions) to accrue evidence fast; **its 30-day clock is INFORMATIONAL**, because a
~25-position book at 45.3% of the live capital figure is not the book that will ever be traded (live
= ₹1 lakh, 1–2 positions) and the two can produce OPPOSITE SIGNS from identical signals.
**Cycle 2 = the rehearsal** — after CAS Stage 2, MCE 5b + 6, the tuning/promotions, the
deflated-Sharpe bar, AND Phase 7.1–7.4, **reset the clock** and run **45–50 trading days targeting
30 profitable** on a heat-capped ₹1 lakh book. **That** clock is the binding go-live gate. User's
words: *"no point of going live without proper paper trading result with better strategy."*
⚠ **Honest timeline: cycle 2 alone is ~9–10 weeks, so live is realistically 4–6 months out.**
**Bridge already built:** the heat COUNTERFACTUAL measures cycle-2's book shape during cycle 1 with
zero behaviour change — first read **admitted 12 / skipped 35, capped −₹13,303 vs full −₹19,093
(+₹5,790 total) but per-trade −₹1,478 vs −₹796** ⇒ **the cap is a RISK control, not a profitability
fix**; it cuts total loss by taking fewer trades at an unchanged negative expectancy. Nothing there
repairs −0.303R/trade. **The heat cap itself is DESIGNED but deliberately NOT BUILT** — it belongs
inside 7.1's RiskEngine (building it now means retrofitting), and it must not throttle cycle 1
(a 6% cap cuts entries ~74%).

**▶ ✅ SHIPPED 2026-09-02 (user-approved): the NOTIONAL CAP + the R:R ≥ 1 OVERLAY.**
(1) **Per-position notional cap** (`paper_max_notional_leverage = 1.0`) — risk-first sizing bounds a
trade's RISK but not its SIZE, so a four-paise stop sized **50,000 shares = ₹1,18,65,000 on ₹1,00,000
capital** and returned 201. Cap = capital × leverage, existing position included, **reject never
clamp**. **This deliberately replaced the proposed `paper_min_risk_pct` floor and needs NO spec
change** — a %-of-price minimum stop is the wrong instrument (2% is comfortable on HDFC, a knife-edge
on a ₹39 micro-cap); the volatility-relative gate that does that job (`sl_atr`, 17/20, reproduced by
the 08-25 horizon study at the same 1.0× threshold) already exists. ⚠ PER POSITION only —
portfolio-wide is still the unbuilt heat cap (book at 45.3% across 23 positions).
(2) **R:R floor overlay** (`app/signals/rr_guard.py`, `rr_min = 1.0`) — rejects a signal
whose target is closer than its stop: **11 of 190 listed signals (5.8%)**, and 6 of 23 open positions
were in that state. **It shipped ACTIVE with NO forward-evidence bar on purpose:** unlike every other
overlay it enforces an **identity** (planned R:R < 1 needs a >50% win rate merely to break even), so
there was held to be no hypothesis to falsify. **Raising the floor above 1.0 IS empirical** (1.67 is
fitted to our 37.5% win rate) and must pass the multiple-testing bar.
**⛔ SUPERSEDED — this gate was REVERTED TO SHADOW on 2026-09-03, one day later, and the reasoning
above is the thing that failed.** The identity is true; the unstated premise attached to it ("which
no trend-following system sustains") was an assertion never checked, and the tape falsified it in a
week: the blocked cohort was the book's ONLY profitable one (24 trades, **+₹10,585**, 63% win, 33%
tp_hit vs the allowed set's 77 trades, −₹26,792, 48%, 16%), because a nearer target is mechanically
easier to hit AND **R:R<1 is a proxy for a WIDE stop** — the good cohort. Mode **verified `shadow`
in both live processes 2026-09-04**, with the `config.py` default and `.env.example` moved to match.
See CLAUDE.md constraint 8 and the review calendar below. **Complementary to `sl_atr`, not redundant:** the two
are structurally disjoint (a tight stop produces a LARGE ratio; R:R<1 needs a WIDE stop) — 11 vs 21
signals with **zero overlap**, pinned by a test. Root cause remains `compute_levels` pairing a
structural stop with an absolute-% target — a §6 spec change, deliberately not done here.

**▶ ⚠ TWO PRE-EXISTING SIZING HOLES FOUND 2026-09-02 — ONE FIXED (the notional cap above), ONE STILL
OPEN.**
(1) **HIGH: no minimum risk-distance floor and no notional cap.** A signal one tick from its stop
(LTP ₹237.30 vs SL ₹237.26 ⇒ ₹0.04/share risk) is accepted — reproduced as **201 CREATED, 50,000
shares, ₹1,18,65,000 notional on ₹1,00,000 capital**. The 09-02 wrong-side fix closed the
*negative*-distance half of this hole and left the *near-zero* half, which produces a WORSE position
than the bug that was fixed, and that row enters the paper book, the R statistics and the 30-day
clock. Same tiny-SL pathology as the known `RR≈228` artifacts. Fix = a `paper_min_risk_pct` floor
(reject, never clamp) + a hard affordability check. **I'd do this before anything else on the queue.**
⚠ **quant-verifier reproduced it independently AND established that the code is SPEC-FAITHFUL** —
`docs/SIGNAL_ENGINE.md` §6 defines no minimum risk distance — so this is a **SPEC change** (§6 edit +
§8 regression + explicit sign-off, per the protected-spec rule), not a bugfix that can be slipped in.
**STILL OPEN —** (2) **LOW-MED: `used = abs(existing_entry - stop_loss)` invents risk** — a profitable long whose stop
has trailed above entry is refused a repeat entry with "already at your per-trade risk budget", which
is false. Fix = directional `used` **clamped at 0** (the naive directional fix hands out negative risk
as free budget). Both are money-path sizing changes ⇒ user's call, post-watch-mode.

**▶ AGENT REVIEWS 2026-09-02 — THREE rounds, 21 defects, all fixed: bug-hunter (9) →
quant-verifier (PASS-WITH-NOTES) → ui-reviewer (FAIL).** ui-reviewer failed the diff on RENDERING:
it MEASURED the contrast and the new blocked state was unreadable in every theme — **`opacity: 0.55`
on the row stacked on the Button primitive's own `disabled:opacity-50` = 0.275 alpha, putting
"Blocked" at 1.52–1.99:1 and the badge at 2.15–2.83:1 against a 4.5 AA floor.** The one row that
most needs reading became the least readable, on the widest Buy surface. It also proved in jsdom that
a native `disabled` drops the button out of the tab order AND kills its own tooltip
(`disabled:pointer-events-none`), so **the block reason was unreachable by keyboard AND mouse** —
an `aria-label` on an element nobody could reach. And `TradeBlock.unknown` was **read by zero call
sites** while its docstring promised it "must LOOK different". Fixes: loss-accent border instead of
the dim · `aria-disabled` + a click guard on all five surfaces (focusable, tooltip works, still
inert) · a visible `⚠ unchecked` marker · the themed `StatusPill kind="rejected"` instead of a
hand-rolled `text-[9px]` badge · label/glyph centralised. **Two pre-existing issues fixed because
this work made them load-bearing:** the Dashboard trade button had NO focus-visible ring (§10.1) on
the landing page, and **daybreak `--color-loss` was 3.95:1 — below AA for every existing
hit_sl/rejected/sell pill** → red-700, measured at 5.30:1 (following the file's own `--color-warning`
precedent). **Lesson worth keeping: three reviews found 21 defects in work that passed its own green
suite twice — the tests asserted what was INTENDED, not what the code did.**

**▶ AGENT REVIEWS 2026-09-02 — bug-hunter (9 defects) then quant-verifier (PASS-WITH-NOTES); all
fixed.** quant-verifier confirmed spec conformance (frozen engine + fixtures untouched, no new
look-ahead, sizing formula intact with `risk_pct` not re-divided, money Decimal end-to-end, shadow
measurement byte-identical) and found the preview DISAGREEING with the order path in three ways:
(a) **it compared the raw LTP while the broker compares its post-slippage fill**, disagreeing in a
half-spread band BOTH ways — LTP 237.25 vs SL 237.26 previewed blocked while the order path fills
237.30 and allows it, i.e. **a false BLOCK that HIDES a tradeable signal**, the worse error; now
judged on `simulate_fill(...).fill`. (b) **the broker has TWO unconditional pre-fill rejections and
only one was previewed** — the off-market guard fires whenever there is no live tick and
`allow_offmarket_entry` is False (the DEFAULT), so **outside market hours every row read
`blocked=False` while the order path 422'd all of them**; probably the app's most common wasted
click. (c) **a FIFTH Buy surface** (`StylePage`, posting real Signal ids with no eligibility fields)
— now stamped server-side, and `gate_modes()` moved into `eligibility` so all five share one
definition. Also: `unassessed` now reaches the CLIENT (it was log-only, so "unknown" was
indistinguishable from "verified clear" exactly where the clicks happen) and renders as an
enabled-but-marked state; a non-finite Redis LTP would have 500'd the detail endpoint (`Decimal("nan")`
parses without raising — the same bug class fixed one file over in the same commit); and the "all four
share one helper" claim was false until `OpportunitiesTable`/`AlertBell` were actually converted.
**Gate: backend 1574 passed · ruff + mypy (app/ + scripts/) clean · frontend typecheck 0, eslint
clean, 411 vitest.**

**▶ AGENT REVIEW 2026-09-02 — bug-hunter found 9 real defects IN the same-day eligibility work; all
fixed** (details in CHANGELOG). The three that matter for future work: (a) **`make typecheck` only ran
`mypy app/`, so `scripts/` was never type-checked** — that hole hid a missed `render_markdown` caller
that would have crashed the hand-run regime sidecar; now `mypy app/ scripts/` with the 9 legacy
scripts visibly grandfathered in `pyproject.toml`. (b) **the `unassessed` tripwire was imaginary** —
`preview()` got 3 of 8 gate modes, so an ACTIVE liquidity gate produced `blocked=False` on a row the
order path 409s, while three docs claimed the drift "cannot silently return"; now a COMPLETE mode map
+ a parametrized test per uncovered gate. (c) **only 2 of 4 Buy surfaces were wired** — the Dashboard
landing page still fired guaranteed-409 orders; all four now route through one shared `tradeBlock()`.
It also CONFIRMED the load-bearing claim: checking only the first spread-only fill is sufficient
(property-checked over 20,000 randomized books incl. crossed books and zero top-of-book size, 0
violations).

**▶ SHIPPED 2026-09-02 (audit items 1, 2, 7):** the display path now shows what is actually
tradeable (`app/signals/eligibility.py`, one source of truth, stamped on the list AND the detail
endpoint AlertBell reads; blocked rows stay visible but un-clickable with the order path's own
reason); the `size_for_fill` wrong-side-stop bug is fixed (`side` required, directional risk
distance, reject-never-clamp) with canary regression tests; and both gate sidecars now print their
REAL mode instead of hardcoding "SHADOW". Details in CHANGELOG + the CONTINUE HERE queue below.

**▶ OPS 2026-09-02:** a **duplicate Celery beat** was found running (an orphan `worker -B` reparented
to systemd alongside the `make worker` tree) — every scheduled task was firing twice, including the
60s `position_monitor` on the live open book. **✅ RESOLVED** — user killed the orphan; one
`make worker` tree remains. ⚠ **`REGIME_GATE_MODE=shadow` was set in `.env` but `settings` is an
`@lru_cache` module singleton, so the RUNNING backend kept enforcing `active` until restarted** —
check a mode change actually took effect in the live process, not just in the file.


**▶ STILL IN WATCH MODE until Fri 2026-09-04 — no money-path build this week.** CAS Stage 1
(`cas_daily`) landed 2026-08-25 and must ACCRUE before Stage 2 can run. **Accrual is HEALTHY as of
2026-09-02: 6 sessions captured, 208 rows each (08-26, 08-27, 08-28, 08-31, 09-01, 09-02) = 1,248
rows, no missed window.** `make worker` must stay up across 15:15–15:33 IST daily and an auction
window cannot be back-filled. Check the row count each morning:
`docker exec -i tp_postgres psql -U tpuser -d trading_platform -c "SELECT trade_date, count(*) FROM cas_daily GROUP BY 1 ORDER BY 1;"`

**▶ NEW FINDING 2026-08-25 — the HORIZON / stop-width study** (`docs/analysis/horizon-recovery-2026-08-25.md`).
From a desk observation that stopped-out names "failed for the day then recovered". Confirmed and
explained: **11 of 16 stop-out losers with forward bars traded back through their entry, median 1
trading day** — but "just hold" is far worse (NDRAUTO −₹54,701), so the bounce is transient. The split
is **stop width ÷ average daily range**: below 1.0× → **8/8 recovered, −1.45R realised**; at/above 1.0×
→ 3/8 recovered, −1.17R. Tight stops also **overshoot the intended −1R** (−1.70R under 0.25×) because
the honest 6.8.2 fill cost is a fixed price amount. Risk-normalised replay (R, not ₹ — the first pass
held qty constant and was a **sizing artifact**) over all 82 closed trades: planned SL −0.05R →
1.5×range **+0.11R**, with the entire gain inside the tight-stop group. **This independently reproduces
the already-built `sl_atr` shadow gate at its exact 1.0× threshold from a different yardstick** — but
readiness is still 12/20 so it STAYS shadow. Second half: **we grade multi-day trades on a one-day
clock** — ≥1R on the entry day = 12% for both classes, but **within their own horizon swing 36% /
positional 54%**, median +1R on **d+3** for positionals. Actions: (a) make the daily report's "reached
≥1R" horizon-aware, (b) surface `sl_atr_mult` at entry (already stamped on every order); REJECTED:
widening stops on the money path, and holding through stops.

**▶ `docs/STATUS.html` REBUILT 2026-08-25** — the readable mirror of this block, now current through
6.8 + MCE 5a + CAS + the horizon finding. 29 sections, four pre-rendered SVG charts (no JS charting,
no CDN), a Full/Overview detail toggle for presenting, a light/dark/auto theme toggle, and a table
view under every chart. Self-contained: open `docs/STATUS.html` in any browser.

## ▶ (previous stamp: 2026-08-22)

**v2 Phases 0–2 ✅ done · Phase 3 (realtime) ✅ GATED 2026-08-14 · Phase 4 ✅ done ·
Phase 5 ✅ GATED 2026-08-07 · Phase 6 ✅ GATED + CLOSED 2026-08-20 (6.1–6.5 built shadow-first; regime
gate ACTIVE 2026-08-14; 3 forward-evidence loops continue post-close) · Phase 6.8 ✅ GATED + CLOSED
2026-08-20 (merged to main, pushed) · Phase 7 not started.**

**▶ Phase 6.8 (Execution Realism & Exchange-Safety, paper-safe) — APPROVED 2026-08-17 (user) as the
next BUILD phase, inserted between Phase 6 and the MCE. Scope LOCKED: 6 paper-safe slices (depth
capture → spread-aware slippage → circuit-band overlay + open-book-MTM gap + CA-adjust open positions
+ silent-outage alarm) + a research track (VWAP/RVOL candidate factors, weekly spread-width gate) + an
F1 `market_cap` spike (pulled forward to de-risk MCE). Frozen engine untouched. **▶ 6.8.1 (order-book
depth capture) DONE 2026-08-17** — top-of-book cached to `depth:{stock_id}`, wired into the soak-proven
`live_worker` (folded into the per-batch LTP pipeline, budget untouched); bug-hunter MED + perf-auditor
HIGH caught + fixed; **live smoke PASSED 15:26 IST (1690 `depth:*` keys off real Kite MODE_FULL ticks,
TTLs cycling 50–59 s)**. **▶ 6.8.2 (spread-aware slippage) DONE 2026-08-17** — paper fills now priced
off the real book (`half-spread + k·qty/top_qty` impact, flat bps as a FLOOR so a fill is never
cheaper than before, fail-open to flat when depth is absent), both entry and exit, + daily-report §9
"Fill realism" showing the ₹ the flat model was under-charging; 27 tests. **The live book justified
it emphatically: 82.1% of 1666 books have a half-spread wider than the flat 2 bps** (median spread
11.85 bps, p90 87, p99 280). **Agent-reviewed CLEAN (bug-hunter + quant-verifier) + deployed onto the
Phase-6 branch. Clean-slate cut done 2026-08-17: clock reset + all 26 open positions flattened at the
15:29 IST close (net +₹7,222.66, book empty) — pre-/post-6.8.2 paper P&L are non-comparable, so the
new model starts fresh.** **▶ 6.8.3 (circuit-band eligibility overlay) BUILT shadow-first 2026-08-17**
— skips entering a name pinned within `circuit_proximity_pct` (1.5%) of its ADVERSE band (long→lower,
short→upper): a long into the lower circuit has no buyers, so its stop can't fill. Bands from a
market-hours task's batched Kite `quote()` → Redis `circuit:{stock_id}`; the order path only READS the
cache (fail-open). Reviews: bug-hunter 1 MEDIUM (shadow double-count) FIXED + regression; quant-verifier
PASS-WITH-NOTES (frozen engine untouched, direction verified). 30 tests. **▶ 6.8.4 (continuous open-book
MTM) DONE 2026-08-17** — carried holds (opened a prior day, still open) now get the rolling MFE/MAE
narrative marked to each day's cutoff (no look-ahead), and the weekly open-MTM is a per-trading-day
series; pure-reporting, frozen engine untouched. Reviews: quant-verifier PASS, test-guardian gaps all
fixed; 27 daily-report tests. **▶ 6.8.5 (CA-adjust OPEN paper positions) DONE 2026-08-18** — a
split/bonus now R-preservingly adjusts a held paper position on its ex-date (entry/peak ÷factor; SL/TP
by distance×old_qty/new_qty so R is exact even when a fractional entitlement floors qty); ratio is
admin-verified only (auto-feed deferred — no NSE CA source); ex-date worker is idempotent + catch-up.
New `corporate_actions` + `position_corporate_actions` tables (migration `a7b8c9d0e1f2` — run `make
migrate`). Reviews: quant-verifier PASS (1 HIGH R-drift on fractional entitlement FIXED), bug-hunter
BUGS-FOUND (catch-up + concurrent-run, both FIXED); 14 tests. **▶ 6.8.6 (silent-feed-outage alarm) DONE
2026-08-18** — a trading-calendar-aware staleness check on the EOD feeds (`ohlcv_1d`/`fo_bhavcopy`/
`fii_dii_daily`) raises a loud "⚠️ FEED STALENESS ALARM" header in the daily report + a `log.warning`
when a feed falls behind (weekend/holiday/pre-EOD aware — no false alarms); turns the silent month-long
07-02→07-17 outage failure mode into a loud one. Reviews: bug-hunter 2 LOW fixed, test-guardian gaps
all fixed; 13 tests, no migration. **▶ ALL SIX PAPER-SAFE SLICES (6.8.1–6.8.6) DONE.** Remaining =
the gated, non-blocking research track (R1 VWAP/RVOL factors — frozen-engine change, LAST · R2 weekly
spread-width gate · F1 `market_cap` spike). **✅ PHASE 6.8 GATE PASSED 2026-08-20** (`/phase-gate`,
worker stopped for a quiescent dev DB: backend 1477 · parity 16 · walkforward 9 · replay 19 · frontend
375 · cargo ok; §8 drift gate clean = frozen engine untouched; `make analysis` smoke green incl. the
6.8.6 feed-staleness alarm firing) — **PHASE CLOSED, merged to `main` fast-forward, awaiting the user's
`git push`.** Paper day-1 stays deferred until the user says "proceed". Close report: the phase-06.8
doc's "Phase gate — CLOSE REPORT (2026-08-20)" section.

**▶ R-track entry-quality overlay DONE 2026-08-18/19 (SRTL leak → the real leak is ENTRY, not exit).**
Post-mortem of the SRTL paper loss (BUY at 80% confidence on RSI_DIVERGENCE *alone*, ₹39 micro-cap ×
2666 qty → −₹3.5k / 1.78R) exposed two gaps the ≥70% gate misses. Built as a downstream eligibility
overlay (`app/signals/entry_quality.py`, frozen engine untouched, the `regime_guard`/`circuit_guard`
pattern) with **two independently-moded checks**: (1) **factor-diversity** (`entry_diversity_gate_mode`
**ACTIVE** — user sign-off, enforces the stated "≥2 factors, never a single indicator" rule; the
confidence math normalizes by scoring-factor weight, so one 0.8 factor reads 80%) — single-factor
signals no longer enter; (2) **stop-too-tight** (`entry_sl_atr_gate_mode` **SHADOW** — a tunable
`|entry−SL| < k·ATR`). A shadow-report sidecar (`app/services/entry_quality_shadow.py` → `make
analysis` writes `entry-quality-shadow-<date>.md`) accrues flagged-vs-passed outcomes + an sl_atr
flip-readiness banner. Evidence (dev-DB): diversity-flagged signals that traded netted −₹6,093 (9) vs
passed +₹3,880 (60). Reviews: quant-verifier PASS + bug-hunter CLEAN; 24 tests, no migration. The
exit-ladder replay that ran alongside (`docs/analysis/exit-ladder-research-2026-08-18.md`) is PARKED:
net-₹100/hard-₹500 booking both REJECTED (risk-dial, not booster); the only supported exit change is
arming breakeven earlier (`profit_lock_breakeven_inr` 2000→~800), deferred until more data.
**Context layer deferred to the MCE:** sector/index relative-strength + fundamentals + news as
GATES/MODIFIERS (never additive) — the *top-down* complement to this *breadth* fix, captured in
[`phases/phase-MCE-market-context-engine.md`](phases/phase-MCE-market-context-engine.md) (each
§8-backtested on ≥2y before live; the daily report must surface them once built).
**GOVERNANCE (user 2026-08-17): all 6.8 slices build on the Phase-6 branch itself; paper-trading day 1
is DEFERRED until the phase is done AND the user says proceed; merge to `main` only after.** Full
adjudication of the `REAL_WORLD_NSE_BSE`
external review + the sliced build: `phases/phase-06.8-execution-realism-plan.md`.**
Suites grew with the Phase-6 slices (added `test_signal_excursions`,
`test_entry_attribution`, `test_corpus_attribution`, `test_seasonality`); run
`make check` for the exact totals. Pre-Phase-6 baseline: backend **1123**
(non-replay), frontend **370**, parity 16, walkforward 9, replay 19, cargo 86.

**Phase 6 (outcome tracking + entry-selection) — 6.1 + 6.2 DONE (2026-08-13).**
6.1 = signal-level MFE/MAE on `signal_outcomes`; 6.2 = entry-quality attribution
(live + corpus via the parity-clean Rust `run_universe`, engine frozen) + per-factor
attribution. **The verdict — the entry-selection leak: the 70–79 confidence band +
transitional ADX regime are net-negative; 80–89 + trending are the edge; factor-wise
RSI_DIVERGENCE/ADX predict edge while DARK_CLOUD_COVER/EVENING_STAR/MACD_CROSS/RSI_LEVEL
actively hurt.** The **gate experiment** (`scripts/gate_experiment.py`) then tested the
levers on the corpus: **skipping the transitional ADX regime (keeping the 70 gate)
nearly doubles captured R (+73.8 vs +41.2 total-R) and triples per-trade expectancy —
it beats raising the confidence gate to 80.** All behaviour-changing → §8 backtest +
sign-off first; the engine stays frozen.

**The §8 walk-forward then confirmed it (`scripts/gate_walkforward.py` →
`gate-walkforward-<date>.md`, 2026-08-13). The finding HOLDS out-of-sample:** the three
metrics §8 gates a merge on all improve — win rate 40→43%, per-trade Sharpe +0.034→+0.097,
max drawdown 36.5R→20.4R (every move > ±5% ⚠ → needs sign-off) — skip-transitional wins
expectancy in **5/5** sequential time folds (biggest lift in the *worst* fold), and an
anchored walk-forward that learns the bad regime only from the *past* and applies it
forward lifts OOS expectancy **+0.067→+0.142**. quant-verifier PASS; read-only.

**The regime gate is now BUILT as a shadow-first overlay (2026-08-13)** —
`app/signals/regime_guard.py` + `regime.py`, wired into the paper-order path
(`settings.regime_gate_mode`, default **shadow**), engine untouched (a downstream
eligibility filter, the `risk_guards.py` pattern). It MEASURES and does not suppress;
`scripts/regime_gate_shadow.py` → `regime-gate-shadow-<date>.md` shows what it would do
to the LIVE cohort (first read: suppressed set −0.061R, gating lifts live expectancy
−0.034→−0.016 — consistent with the backtest). quant-verifier PASS + bug-hunter CLEAN.

**6.4 weight-retune EXPERIMENT DONE 2026-08-13** (`scripts/weight_retune.py` →
`weight-retune-<date>.md`; quant-verifier FAIL→resolved). Group-weight coordinate sweep
(the 6.2 leak is per-factor but the lever is per-group, and groups mix helping+hurting
factors, so it's measured not theorised): **lead = `momentum ×1.5`** (expR +0.052→+0.070,
total-R +41.2→+50.4, Sharpe +0.034→+0.045, maxDD 36.5→32.4R, 4/5 folds). All six weight
groups are cross-engine consistent (an earlier "DOW_TREND engine-specific" caveat was
WITHDRAWN 2026-08-14: a *scoring* DOW_TREND is tagged `structure` in both engines — see
`dow-trend-grouping-gotcha` in memory; do NOT "fix" its group).

**6.4 shadow-promote DONE 2026-08-14** (migration `d2e3f4a5b6c7`): `momentum ×1.5` and a
`retune_base` control now run as 1d/eod SHADOW profiles over Nifty50 (no setup gate = base
engine + multipliers), minting `is_shadow` signals on the nightly path — the FORWARD A/B of
the experiment, measured by 6.1/6.2 attribution (bucketed by `profile_key`), never tradeable.
Both arms share the rr-2 exit so the A/B isolates the entry effect. Verified end-to-end.

**First-class ADX level DONE 2026-08-14** (migration `e3f4a5b6c7d8`): `Signal.regime` is now
persisted at commit — recovered from the frozen ADX factor's decision BRANCH (not its
0.1-rounded prose), so the raw-choppy [19.95, 20) edge is no longer misbucketed as
transitional — and the regime gate reads this durable field instead of parsing prose on the
money path. This CLEARS the second active-flip precondition (quant-verifier PASS-WITH-NOTES +
bug-hunter CLEAN; frozen engine untouched, the `risk_guards.py` pattern). Money-path behaviour
is unchanged until the flip (default `shadow` = no-op); the flip now waits only on user §8
sign-off + forward shadow agreement. **The one INFO follow-up is DONE too (2026-08-14): the
live shadow measurement now buckets by the persisted `signals.regime`, so evidence and
enforcement share one partition** (quant-verifier PASS — no §8/corpus number moved).

**NEXT — recommended lead first; each starts on user command (nothing auto-advances):**
**(1) Flip the regime gate shadow→active — ✅ DONE 2026-08-14 (user decision, reversible).**
Both preconditions were met — the first-class ADX level (migration `e3f4a5b6c7d8`; `signals.regime`
branch-recovered, gate reads it) and the §8 sign-off, which the user gave by choosing to flip — and
the accumulated live cohort already cleared the forward-evidence bar (44 suppressed trades, all
three §8 metrics improve live). Applied via `REGIME_GATE_MODE=active` in `.env` + backend/worker
restart (user-run; `place_order` reads the setting live); the paper order path now REJECTS
transitional (20–25) entries. **Monitoring live** via the daily Flip readiness banner — now a
monitor; if it turns ⏳ NOT READY the live tape diverged, reconsider/**revert**
(`REGIME_GATE_MODE=shadow` + restart). The live before/after P&L is a weak/confounded comparison;
the shadow counterfactual stays the rigorous read. Review the live impact ~2026-09-15 (keep/revert); **(2a) promote the momentum ×1.5 retune** once its
shadow A/B (`retune_momentum_x15` vs `retune_base`, in the daily attribution Setup×shadow
table) beats base forward — then create an active retune profile on sign-off (nothing to
build until evidence accrues; ~1–2 signals/arm/day); **(3) 6.5 pair-trading — ✅ BUILT shadow-first (slices 1–4, 2026-08-15)**: `pair_signals`
model + dual-arm (df/adf) nightly minter + spread-outcome tracker + attribution — all additive,
shadow-only, accruing nightly (see `phases/phase-06-6.5-pairtrading-plan.md`). Nothing left to
build; the attribution report answers df-vs-adf once evidence accrues.
(An earlier "(2b) fix the DOW_TREND grouping bug" item was investigated 2026-08-14 and
WITHDRAWN — there is no bug; a scoring DOW_TREND groups `structure` in both engines. An
attempted fix inverted parity and was reverted; see `dow-trend-grouping-gotcha`.) Detail:
[`phases/phase-06-plan.md`](phases/phase-06-plan.md). Reports:
`docs/analysis/attribution-<date>.md` + `attribution-corpus-<date>.md` +
`gate-experiment-<date>.md` + `gate-walkforward-<date>.md` + `regime-gate-shadow-<date>.md`
+ `weight-retune-<date>.md`.
**Local `main` is ~12 commits ahead of origin (+ uncommitted Phase-6 work) — push is manual.**

> **Phase-3 gate — ✅ RUN + PASSED 2026-08-14 (Fri EOD).** See
> `phases/phase-03-realtime.md` §Gate closure for the verdict block. Full suite green
> (backend **1246** / frontend **375** / cargo **86**, incl. all 44 parity+walkforward+replay
> marker tests); regression Δ0 (frozen engine untouched); soak ×2 + 14-day shadow week
> re-verified. Phase 3 is CLOSED. (The earlier pin said "Friday 2026-08-15" — off by one.)

### Interstitial slice: "Intraday activation + v1 surface uplift" (2026-08-07/08)

Agreed as the work to do BEFORE Phase 6, so its noise doesn't land inside the
phase. Merged to main and pushed. **Full report:
[`phases/interstitial-intraday-activation.md`](phases/interstitial-intraday-activation.md)**
— read that rather than reconstructing from commits. Phase 6 itself is now
UNDERWAY (6.1 + 6.2 done — see the STATE block above):
[`phases/phase-06-plan.md`](phases/phase-06-plan.md) is the live tracker.

1. **Stock master repaired.** NO stock had a correct company name: the equity
   master's `NAME OF COMPANY` column was never read, so 2,274 of 2,333 carried
   their own ticker and the 59 index members carried their **sector** (ADANIENT
   was "Metals & Mining"). The reseed had also silently stopped working — an NSE
   ticker rename arrives as a new symbol holding the old row's ISIN, dies on
   `uq_stocks_isin`, and rolls the entire run back; six real renames were
   blocking it. Renames now resolve **in place** so the row keeps its id and its
   OHLCV history. Sector coverage **59 → 500**.
2. **v1 surface uplift.** Watchlists gained live LTP / change % / previous close
   (they had been the only live surface in the app with no prices, while the
   backend was already fanning ticks out per watchlist). New `GET
   /screener/fields` reports **counted** per-field coverage, so a sector filter
   says "only 500 of 2,365 stocks have a sector" instead of silently returning
   nothing. The Intraday empty state stopped blaming the EOD clock.
3. **The intraday shadow layer** — see below.

**Intraday was dark for TWO reasons, only one of which was known.** The three
profiles were `inactive`, *and* nothing scheduled them either way:
`nightly_suggestions` ran only the `'eod'` schedule and `on_close_suggestions`
was still a Phase-3 stub, so the `intraday_15m` / `time_0925` schedules had no
caller at all. The menu was structurally unable to populate regardless of status.

`status='shadow'` is the third profile state: runs on the real schedule, measured
to outcome, **never tradeable** (the order path admits `'active'` only, so this
is enforced by code that already existed). It exists because walk-forward says
the trio must not be activated — all three are negative risk-adjusted — while
leaving them off produced no evidence to ever revisit that verdict with.

**quant-verifier returned FAIL on the first cut and was right.** The CRITICAL is
worth remembering: shadow outcomes were being counted in the tradeable
hit-rate — and `status` alone could not fix it, because `status` is a lifecycle
field the sweeper overwrites at exactly the moment an outcome finalises. Hence
an immutable `signals.is_shadow`. Two scheduling bugs alongside it: the 09:16
IST beat scored the *previous* session's bar and then held the dedup slot all
day, and the 15:16 beat minted 24-hour "intraday" signals. Full record in
CHANGELOG under 2026-08-08.

**First real fire: Monday 2026-08-10.** Signal *production* is still unproven —
Saturday correctly produced zero. Read **§8 of `docs/analysis/<date>.md`** after
the first session: it distinguishes "not a trading day" from "no bars, the worker
never ran" from "ran but nothing cleared the gate". A silent shadow layer is a
failed layer.

**Phase 5 — GATED 2026-08-07 (see [phase-05](phases/phase-05-ui-overhaul.md) §7
for the verdict block).** bug-hunter + ui-reviewer run, all findings in new code
fixed with regression tests — incl. a HIGH that would have shipped the F&O page
with **every Greek null by default**, because index options are weekly but
futures monthly and only 3 of 12 NIFTY expiries have a same-expiry future.
The gate also closed the Phase-4 expiry bug §8 had handed forward, and the owed
quant-verifier pass turned up a **CRITICAL look-ahead** next to it — both fixed
with revert-proven canaries (`phases/phase-04-fo-suggestions.md` §9).
**Caveat on the gate:** `make check` as a single target cannot run in a worktree
(its ESLint leg shells out to `pnpm install`, which tries to purge a
`node_modules` this box cannot reinstall — the known snap-store breakage). Every
leg was therefore run individually and all passed; the frontend legs ran against
the main checkout's `node_modules`. Backend-only diff, so that substitution is
sound, but a single-command `make check` on main is still worth doing once the
pnpm store is repaired.
The **60 fps budget is MEASURED and MET** — React commit p99 **7.6–8.8 ms** vs
16.7 ms in real Chrome 151 (`docs/PERFORMANCE.md`; harness `frontend/perf/`).
**Visual smoke passed in all 5 themes** via `perf/theme-gallery.html` +
`perf/shoot-themes.mjs` (no backend or session needed). Only `/phase-gate`
remains; the one thing not covered is a page-level smoke with LIVE data, which
needs a logged-in session.
**Machine follow-up:** the pnpm store for `frontend/node_modules` was pruned by a
snap refresh, so **no new frontend dependency can be installed** until
`store-dir` is repointed outside `~/snap/` and one full `pnpm install` runs.
That is why virtualization is an in-repo hook rather than `@tanstack/react-virtual`.

**Phase 3 — BOTH exit criteria are now MET; only the gate ritual is left.
(Corrected twice on 2026-08-07: the checklist used to call the soak "UNPROVEN",
contradicting both the narrative below and `PERFORMANCE.md`; and it then called
the shadow week outstanding when the log shows three weeks of clean runs. Read
the artifacts before trusting a checkbox.)**

- [x] **Quiet-box full-session soak — MET ×2 (2026-07-15 + 07-16).** Budget
      restated to p99 ≤ 50 ms by user ruling on 07-14 and then met on the
      optimized worker across two full sessions; verdict recorded 07-16
      (`PERFORMANCE.md` §Budgets, ledger §Fourth soak). **No further soak is
      needed.**
- [x] **Clean shadow week — MET. (Corrected 2026-08-07: this said "the ONLY
      outstanding Phase-3 item" and implied one clean day. It had in fact been
      running daily for three weeks and the log was never read back.)**
      `backend/shadow/shadow_week.log` records **14 consecutive trading days,
      2026-07-20 → 08-06, every one `PASS diffs=0 errors=0`** (2295–2299 stocks
      matched per day, 58–93 signals emitted under BOTH engines). The criterion
      is "a clean week"; this is nearly three.
      *One caveat, stated for honesty:* the 08-06 entry is soft — no 08-06 daily
      bar exists in the DB (the worker was down that evening, see below), so that
      run almost certainly re-scored the 08-05 close under an 08-06 cutoff.
      **07-20 → 08-05 alone is 13 clean days on real data**, so the criterion
      stands on its own without it.
- [ ] **`/phase-gate` for Phase 3** — the only thing left. Nothing to wait for:
      the evidence for both exit criteria is already on disk.

> **Ops note (2026-08-07), not a Phase-3 item.** Every EOD table stops at
> **2026-08-05** — `ohlcv_1d`, `india_vix_daily`, `fii_dii_daily`, `fo_bhavcopy`
> and `signals` (last nightly generation 08-05 22:44 IST). The worker stack was
> only restarted 08-07 09:13, so 08-06's 18:40 EOD and 19:15 generation beats
> never ran; the 08-06 analysis + shadow runs that DO exist were manual. The
> ≤ 21-day EOD self-heal should absorb 08-06 at the next evening beat — verify
> it did rather than assuming.

**Not a Phase-3 item:** the 30-day paper clock is the **Phase-7** go-live gate,
and it only *starts* when the live path runs (slice 3.7).

Everything else in Phase 3 (slices **3.0–3.7**) is DONE and on `main` — live
worker + Rust LiveEngine, committed/forming layers, record-replay, tick
triggers + alert UI, watchlists, provisional leaderboards, outcome ticks,
shadow-compare harness. Detail: the narrative below + `phases/phase-03-realtime.md`.

**Not a Phase-3 blocker (common confusion):** the **30-day paper clock** is the
*Phase-7* go-live gate. It runs daily now; the loop is `make analysis` →
`docs/analysis/` (+ `FIX_PLAN.md`). Current evidence: the binding constraint is
**entry/regime selection, not exits** (1/15 trades reached +1R on 08-03→05) —
which is what Phase-6 expectancy calibration is for.

---

## v2 upgrade phases (current)

| # | Phase | Status | Report | Key deliverable |
|---|-------|--------|--------|-----------------|
| 0 | Claude workbench · repo hygiene · triage · F&O recorders | **✅ done 2026-07-03** | [phase-00](phases/phase-00-workbench.md) | git + hooks/agents/rules/skills · 9 defects fixed (incl. dead live pipeline, 100× sizing) · F&O bhavcopy/VIX/chain recorders live |
| 1 | Rust engine core + parity + benchmarks | **✅ done 2026-07-05** (gate: `make check` green + quant-verifier signoff) | [phase-01](phases/phase-01-rust-engine.md) | tradecore wheel · 4 oracle fixtures · cross-language parity EXACT (96 windows + 125 trades) · 5 adjudicated canon decisions · **2y×49 backtest 883.8s → 0.143s (~6,180×)** |
| 2 | Strategy profiles — 4 style engines, offline | **✅ done 2026-07-07** (gate: suites 616/131/35 green · smoke · reviews; 8c trails by approved plan) | [phase-02](phases/phase-02-strategy-profiles.md) | versioned profiles + 8 seeds · NSE calendar · FII/DII + EOD chain wired · suggestions API · **walk-forward evidence: rrbo +41.3%/+1.97 sharpe POSITIVE; dc1/dc2/multibagger FLAGGED** · §8 golden harness in make check · Kite login + throttled REST + intraday backfill |
| 3 | Realtime v2 — tick-to-tick | **▶ in progress** (started 2026-07-09) | [phase-03](phases/phase-03-realtime.md) | live-worker + Rust LiveEngine, committed vs forming layers, record/replay harness, latency budget p99 ≤ 50 ms tick→publish at full universe (restated 2026-07-14; original 10 ms was authored for 200–500 instruments). **Kite subscription required from slice 3.3.** Slice 3.0 (pre-work MEDIUMs) ✅ 2026-07-09 |
| 4 | F&O analytics | **✅ backend done · phase-gate PASS 2026-08-06** (merged to main; UI = Phase 5) | [phase-04](phases/phase-04-fo-suggestions.md) | 4.1 chain/PCR/max-pain/basis/VIX-regime · 4.2 Rust BS/Black-76 IV+Greeks (`tradecore`) + IV-rank · 4.3 option-selling engine (defined-risk index-only; breakeven-POP; expectancy report-only=VRP; fail-closed VIX veto; user-calibrated `SellRules`). Follow-ups: confluence direction-tilt, event/ban gate (=deferred Market Context Engine), Kite SPAN margin, forward-validation dashboard (P6) · 🧭 **Nautilus doc** §9 — Greeks as a first-class data type; options/accounting (margin) refs |
| 5 | UI overhaul | **✅ slices 5.1–5.4 done, MERGED to main 2026-08-07** (`make check` green; bug-hunter + ui-reviewer clean; 60 fps MEASURED and MET; visual smoke passed in all 5 themes — only `/phase-gate` remains) | [phase-05](phases/phase-05-ui-overhaul.md) | 5.1 `useLiveQuotes` v2 (rAF-batched; fixed socket-churn, resubscribe-per-render + subscription-leak bugs) + `useVirtualRows` · 5.2 **F&O page** (chain ladder w/ per-leg IV+Greeks via `/fo/chain?greeks=true`, `/fo/underlyings`, `/fo/expiries`, strategy cards, expectancy labelled report-only) · 5.3 style pages v2 (committed-vs-forming, outcome stats w/ small-sample refusal, factor drawer) · 5.4 Live Signals feed + opt-in notifications (bursts coalesce). **IA + slate default were already done in Phase 3.** 🧭 **Nautilus doc** §4.2 — cache-then-publish lets UI subscribe without touching producers |
| 6 | Outcome tracking + entry-selection | **✅ GATE PASSED + CLOSED 2026-08-20 — 6.1–6.5 built shadow-first; regime gate ACTIVE; code on `main` (pushed); 3 forward-evidence loops continue post-close (regime keep/revert ~09-15 · momentum-retune promote · pair df/adf)** — close report in `phase-06-plan.md` | [phase-06-plan](phases/phase-06-plan.md) | 6.1 MFE/MAE · 6.2 entry attribution (live+corpus) · gate experiment + §8 walk-forward · regime-gate overlay (ACTIVE) · 6.4 weight-retune (shadow) · 6.5 pair-trading (shadow, slices 1–4) · 🧭 **Nautilus doc** §7 — mimalloc on batch backtest sweeps; §4.3 richer bar aggregations for research |
| 6.8 | Execution Realism & Exchange-Safety (paper-safe) | **✅ GATE PASSED 2026-08-20 — CLOSED + merged to `main` (ff, awaiting push); all six slices done + reviewed; research track (R1/R2/F1) optional/gated; paper day-1 deferred until user "proceed"** | [phase-06.8-plan](phases/phase-06.8-execution-realism-plan.md) | 6.8.1 ✅ order-book depth capture (`depth:{stock_id}`; both consumers; pipelined on live-worker) · 6.8.2 ✅ spread-aware slippage/impact (replaces flat 2bps) · 6.8.3 ✅ circuit-band eligibility overlay (shadow-first, regime-gate pattern; band-refresh task → Redis `circuit:{stock_id}`) · 6.8.4 ✅ open-book-MTM carried-position gap (rolling MFE/MAE for carried holds + weekly per-day open-MTM series) · 6.8.5 ✅ CA-adjust OPEN paper positions (R-preserving split/bonus; admin-verified ratio; ex-date worker, idempotent+catch-up; migration `a7b8c9d0e1f2`) · 6.8.6 ✅ silent-feed-outage alarm (trading-calendar-aware EOD staleness header) · research (gated, non-blocking): R1 VWAP/RVOL as confluence factors (§8+oracle regen) + R2 weekly spread-width gate · spike: F1 `market_cap` writer (de-risks MCE keystone) |
| 7 | Live-trading hardening | planned — **now split: 7.1–7.4 run BEFORE paper cycle 2, Kite-only parts after** | [phase-07-plan](phases/phase-07-live-trading-plan.md) | **Before cycle 2 (paper exercises them for real):** 7.1 RiskEngine single-gate (test-first, equivalence-pinned — absorbs the circuit breaker + 6 overlays + notional cap + R:R floor + the heat cap) · 7.2 BrokerAdapter port (`PaperBrokerAdapter` behind the interface `KiteBrokerAdapter` will implement) · 7.3 order FSM (Denied vs Rejected vs Filled) · 7.4 reconciliation-on-restart + kill switch + audit trail. **After cycle 2 (only reality validates):** Kite order placement · GTT · genuine partial fills/rejections · broker-book reconciliation · token lifecycle under live orders. Mitigation for designing the adapter blind: a READ-ONLY Kite spike in 7.2 (order-status/margins/positions, no placement). 🧭 **Nautilus doc** §6 |

> **🧭 Nautilus doc pointers** (added 2026-08-01): before starting and at the
> phase-gate of Phases 4–7, consult `docs/NAUTILUS_TRADER_ANALYSIS.md` for the
> adopt/adapt/avoid items relevant to that phase (§6 gap-analysis · §9 India
> adaptations · §8 don't-copy). **Phase 7 opens with slice 1 = the RiskEngine
> single-gate consolidation** (test-first, equivalence-pinned) — it closes the
> caller-side circuit-breaker seam before the live-order path exists (the exact
> class of bug that gave v1 Phase 7 its four integration defects).

**▶ CONTINUE HERE (next session, any account) — updated 2026-09-06.**

**▶▶ NEW WORKING BRANCH: `feature/pre-cycle2-hardening`** (created 2026-09-06 with user
approval, from `feature/phase6-overlay-walkforward-retune` @ `518b84f` — 69 commits ahead of
`main`, 0 behind). It carries **everything still owed before cycle 2's clock starts**. The
ordered queue, the entry check and the open decisions live in
[`docs/phases/pre-cycle2-queue.md`](phases/pre-cycle2-queue.md); the same queue is registered
as the session task list.

- **✅ ENTRY CHECK PASSED — Buckets A and B are COMPLETE**, verified against the artifacts
  rather than the checkboxes (W1): all 8 Bucket-A items and all 11 Bucket-B items have code
  **and** tests on disk. **Bucket C is 7 of ~60** (W1–W5 · A11 · A40) and the rest stays
  under cycle 2's clock, deliberately.
- **Scope:** Phase 7.1–7.4 (**the long pole, fully unblocked — start here**) · the shared
  Phase-6/6.8 research track R1/R2/F1 · and the cycle-2 entry criteria that were not in the
  original ask but are on the checklist (MCE 5b+6 · CAS-2 · sizing; **`compute_levels`/D5 CLOSED
  09-08 — geometry is not the lever**).
- **⚠ "The rest of Phase 6 / 6.8" has no unbuilt slices.** Both are GATE PASSED + CLOSED
  (2026-08-20). What remains is the gated research track `R2/F1` (**R1 DROPPED 09-08 —
  refuted**) plus three forward-evidence loops — one **decided** (regime → reverted), one
  **stalled** (momentum ×1.5: 3 minted / 0 resolved in 6 days), one **accruing** (pair df-vs-adf).
- **⚠ NO DECISION BLOCKS CYCLE-2 START.** **D2** (R2 build-or-drop) is **PARKED to cycle-2 end**
  (user 2026-09-08 — R2 provisionally dropped; final call waits on cycle-2 evidence; Claude flags it
  at cycle-2 end, review calendar). **D6** (reconciliation matching key) is post-cycle-2.
  ✅ **D3 RESOLVED 2026-09-08** — free-source
  spike: no vendor needed (free NSE-`/api/` `issuedSize × price` path; keystone retired; build
  deferred until a consumer). ✅ **D4 DECIDED 2026-09-08** — minimal rails; max-concurrent-position
  cap (=3) BUILT (`off`, flips at cycle-2 reset), notional + 6% heat kept, correlation/sector deferred.
  ✅ **D1 DECLINED 2026-09-08** — R1-RVOL refuted, VWAP untestable. ✅ **D5 CLOSED 2026-09-08** — no
  constant-R:R geometry beats frozen. **Both profitability levers are spent.** Rationale in queue §4.



**▶ WATCH MODE IS COMPLETE (ran 2026-08-26 → Fri 2026-09-04).** CAS Stage-1 accrual finished
healthy: **`cas_daily` holds 1,664 rows across 8 sessions, last captured 2026-09-04** (verified by
query, this session). No session was missed. The daily "check the row count each morning"
obligation is **discharged** — do not carry it forward as a standing task.

**▶ WHAT'S NEXT — the execution plan in `docs/quant-agent-findings.md` ("Execution plan — sequenced
to cycle 2").** A 30-repo external review (2026-09-03/04) produced 91 items across five queues
(analysis · UI · architecture · testing · workbench), all bucketed by **when they must land**:

> **The rule: anything that changes a recorded number must land BEFORE cycle 2's clock starts.**
> We have already paid this once — paper P&L before and after 2026-08-17 is not comparable because
> the spread-aware fill model landed mid-window and the 30-day clock reset. **Corollary: ~60 of the
> 91 items touch no recorded number and can be built *during* accrual.**

- **Bucket A — freeze the numbers (~7 d):** ✅ **A38 DONE 2026-09-05** (point-in-time
  `Restrictions` registry, subsumes A30/A31 — both live paths migrated, behaviour proven
  unchanged by differential fuzz; ⚠ the BACKTEST leg is blocked on the engine freeze) ·
  ✅ **A21 DONE 2026-09-05** (mark-to-exit: marks now priced by the SAME model as fills, so
  reported open MTM stops being optimistic by ~a half-spread per position; reporting-only —
  nothing branches on unrealized P&L) · ✅ **A37+T3 DONE 2026-09-05** (participation impact `k×p²` on both fill paths and every mark
  surface; the real book has a position at **17% of daily volume** that was priced at the 2 bps
  floor) · ✅ **A29 DONE 2026-09-05** (flat ₹15.34 DP charge on the delivery SELL leg — **₹1,610.70 was
  never levied across all 105 closed positions, 15.8% of the book's loss**; a flat cost is the one
  charge that is not neutral to position size, and small is the shape live trading will have) · ✅ **A23 DONE 2026-09-05** (effective-dated fee registry; each leg costed on its own
  date, pre-coverage dates refused rather than guessed) · ✅ **A26 DONE 2026-09-05** (hot-set cap now HARD for discovery, SOFT for
  signal/trigger-bound stocks — a committed signal can no longer be dropped to satisfy a CPU
  budget; overflow escalates with numbers + remedy and is durable in the health record) ·
  ✅ **A25 DONE 2026-09-05** (tick-mode assert on the depth path — both live paths now census each
  batch's `mode`; a quote-mode tick on our MODE_FULL subscription carries no book, so `depth:` goes
  stale and spread-aware fills silently fall back to the flat floor, i.e. **paper fills quietly
  cheaper than reality**. Detect/count/shout + a durable `tickmode:health:{day}` read by the daily
  report; deliberately does NOT reopen the socket) ·
  ✅ **H6 DONE 2026-09-05** (degenerate-ratio hygiene — `app/core/ratios.py` is now the single
  definition: UNDEFINED is `None` **never `0.0`** (a zero-risk signal read as *the worst possible*
  R:R, the same number), OFF-SCALE is clamped **and marked** (`>50`, because a truncated 228 printed
  as "50.00" reads as a real setup). **`MAX_RR = 50` is read off the book** — p99 of all 656 signals
  is 28.5 and **exactly one row (0.15%) exceeds 50**, the tiny-SL artifact with a **2.6 bps** stop.
  ⭐ **Rule: clamp what you REPORT, never what you DECIDE.** Four literals doing three jobs in four
  modules — two disagreeing by 1000× — consolidated without collapsing them).
  **▶ Bucket A is now COMPLETE — every item that changes a recorded number has landed.**
- **▶▶ Bucket B IN PROGRESS — the instruments that read the cycle (~5 d):**
  ✅ H8 noise negative-control (2026-09-04) · ✅ **H1 block bootstrap** (2026-09-05) ·
  ✅ **H2 buy-and-hold benchmark** (2026-09-05) · ✅ **H12 beta/IR** (2026-09-05) ·
  ✅ **T11 pin PSR** (2026-09-05) · ✅ **H11 MinTRL as headline** (2026-09-05) ·
  ✅ **T7 exhaustive-enum tests** (2026-09-05) · ✅ **A24 uncertainty rule** (2026-09-05,
  `.claude/rules/ui.md`) · ✅ **H4 gate register + U4 trials counter** (2026-09-05 —
  `app/services/gate_register.py`; **observed trials 15 vs 20 assumed**, but that is a LOWER
  BOUND because threshold variants are not yet recorded, so it does NOT license calling the bar
  conservative; `DEFAULT_TRIALS` left untouched — raising it is a decision for the user) ·
  ✅ **H3 VIX trailing percentile** (2026-09-05 — the inherited absolute `20` is India's
  **94.8th percentile**: median VIX 13.35 over 784 sessions, above 20 on only 5.1% of days.
  Now self-calibrating, with the absolute as a shallow-history fallback and `vix_basis` naming
  which ran. VIX still never blocks) · **▶▶ BUCKET B IS COMPLETE.**
  ⚠ **The REVIEW CALENDAR below is now duplicated as data.** When an item's status moves, update
  `gate_register.REGISTER` too — a contract test maps every `*_gate_mode` knob to an entry, but it
  cannot check that a *verdict* is current. None of these changes a recorded number, so
  they build DURING accrual — Bucket A was the part that had to land first, and it has.

> **⭐⭐ WHAT BUCKET B HAS ALREADY ESTABLISHED — read this before arguing about any gate.**
> **(1) The book has not measured an edge in EITHER direction.** Block bootstrap on all 105
> closed positions: Sharpe **−0.033**, 90% interval **[−0.223, +0.118]**, sign fails to survive
> in ~30% of resampled histories. At n=105 even the LOSS is not statistically established. It is
> not that we measured a small negative edge — we have not measured anything, so **any gate
> partitioning this series is partitioning noise.** That is why no partition has ever cleared the
> DSR bar, and it is a stronger statement than the ₹ figure alone supports.
> **(2) The book lost to doing nothing by 15.92 percentage points.** 2026-08-17 → 09-04:
> NIFTY 50 **−1.61%**, the book **−17.52%**. And under-deployment does NOT excuse it — the index
> FELL and the book fell ten times further with only ~45% of capital at risk, so partial
> deployment makes the comparison worse, not better.
> **(3) Market exposure is far above the published median.** Beta **+0.638** overall (LONG +0.34,
> **SHORT +1.49**) against a +0.17 median across 4,843 replications.
> **(4) A sizing finding, surfaced but NOT resolved.** Equal-weighted return is **+0.382%/trade**
> while capital-weighted is **−0.118%**. This is **concentration, not selection** —
> Spearman(notional, return%) = **−0.061**, and the largest quartile's mean return is *positive*
> (+0.084%) while its rupee total is **−₹25,404**. Its median notional is **₹122,566 on ₹100,000
> of capital**; those rows predate the per-position notional cap. **Worth a decision: whether the
> cap alone is enough, or sizing needs a second look.**
- **Then:** Phase 7.1–7.4 (the long pole) · MCE 5b (**blocked on a vendor decision, not code**) +
  MCE 6 · CAS-2 · tuning → **then** cycle 2's 45–50 day clock on ₹1L.
- **▶ Bucket C — ~60 items, and DELIBERATELY NOT NEXT.** This block used to omit it entirely,
  which made the plan look 60 items shorter than it is (found 2026-09-06 when the user asked
  "what about bucket C"). The findings doc's sequence is explicit: Bucket C runs **underneath
  cycle 2's clock, continuously** — *"build only what must be frozen, start the clock, and let
  the remaining ~60 items land while the evidence accumulates."* Five groups: **operational
  safety/alerting** (A11 session notifier · A40 worker-liveness · A27 config dry-run ·
  A28 retryable classification · A3 broker-token status · A36 calendar-expiry alarm ·
  H7 Sharpe-decay alarm · A9/A10) — *the largest single win and safe to ship mid-cycle* ·
  **tests and invariants** (T9 doc-sync as failing tests · T8 · T10 · T13 · T14 · T12 · T4 ·
  T5 · T6 · A13 · A15 · H5) · **rules and hygiene** (A12 · A5 · A7 · A39 `cargo-deny`) ·
  **UI** (U1 registry page folding in U2/U3/U5/U6 → the signal-detail trio U10/U15/U17 →
  U20 → U11 → U19 → polish) · **deployment and misc** (A4 · A14 · A17 · A1 · A41 — A41 only
  *after* P7 introduces a durable repair queue).
  ⚠ **The W rules were the exception** — the sequence put them in parallel with Buckets A/B,
  ~1.5 h total. ✅ **W1–W5 DONE 2026-09-06** (CLAUDE.md "Working rules").
  ✅ **A11 DONE 2026-09-06** — the session notifier (`app/services/notifier.py`), pulled forward
  out of Bucket C on the argument that **A11/A40 are preconditions for an UNATTENDED accrual,
  not work to do during one**: "safe to ship mid-cycle" answers *will it disturb the record*,
  not *what protects the record while it is being made*. Retires the CAS and provisional-health
  manual checks. ⚠ **A quiet channel does NOT mean the capture worked** — this reports what RAN;
  the CAS alarm is an ABSENCE and needs A40 — ✅ **A40 DONE 2026-09-06**
  (`app/services/worker_health.py`), the other half of the same argument. Three layers, each
  stating what it cannot see: heartbeat (`worker:heartbeat:{role}`, absence IS the signal) ·
  a post-window CAS coverage check that fires on the absence · a daily-report section
  rendered ABOVE the scorecard, in a different process from the worker it judges — which is
  what closes the beat task's blind spot. ⚠ **`app.tasks.health_tasks` was missing from
  Celery's `include`**, so the heartbeat would have been silently dead; a contract test now
  asserts every beat entry resolves to a registered task.
  **⛔ The CAS + provisional-health MANUAL DAILY CHECKS ARE RETIRED — do not carry them
  forward.**
  **▶ Everything else in Bucket C stays under cycle 2's clock, deliberately.**
- **Honest sizing: 3–4 months to cycle-2 start**, consistent with "live is 4–6 months out".

⚠ **The plan buys evaluation, not edge.** Nothing in the 91 items is a new entry signal, and none
of the 30 repos produced one. **The known lever is already on record and is NOT in the plan:**
`compute_levels` pairs a structural stop with an absolute-% target, so **94 of 295 swing signals
have R:R < 1 by construction** — at a 37.5% win rate the arithmetic needs 1.67R and cannot close.
That is frozen-engine territory (spec change + §8 regression), not a review finding.

**⚠⚠ THE BACKTEST MODELS NO TRADING COSTS AT ALL (found 2026-09-05 while wiring A23).**
Grepping `app/backtest/` for fees, charges or commission returns **nothing** — not undated fees,
**zero fees**. So **backtest P&L is GROSS while paper P&L is NET**, and every comparison ever drawn
between backtest expectancy and the live book is off by the whole charge load: **22–62 bps
round-trip plus the flat ₹15.34 DP charge** (A29 — which alone is 15.8% of the paper book's loss).
On a −0.303R book that gap is not a rounding detail. **This is the most consequential member of the
A21/A30/A31 "realism added here but not there" family**, and it is frozen-engine territory
(`app/backtest/engine.py`), so it needs explicit sign-off + an §8 regression + regenerated Rust
fixtures — the same blocker A38's and A37's backtest legs hit. **Until then, treat every backtest
expectancy as an upper bound, not a comparable number.**

**⚠ PAPER SIZING NOW DEVIATES FROM `SIGNAL_ENGINE.md` §6 ON THIN NAMES (A37, 2026-09-05).**
§6 specifies `qty = floor(capital × risk% ÷ |entry − SL|)`. Sizing from the actual FILL rather
than the signal entry is pre-existing and user-sanctioned (CLAUDE.md: *"size risk-first from the
actual fill"*); what is new is the MAGNITUDE. With a quadratic participation term the fill is
size-dependent and the size↔price loop has **no fixed point**, so the refinement stops at a
deliberately conservative point: measured **4,545 → 854 shares (−81%)** at ADV ₹2 lakh with a 1%
stop, carrying ₹461 of risk against a ₹2,000 budget. Benign on the real book's shape (ADROITINFO:
1,000 → 930, risk ₹1,953). **Recorded here so the deviation is visible when cycle-2 R statistics
are read** — an R denominated on a budget the trade never used will understate risk-adjusted
return on thin names. Not a spec change; the spec's formula is still what the risk budget means.

**⚠ Heat has drifted: 45.3% → 58.0% of capital** (₹58,034 across 29 open positions, 2026-09-04).
Still no portfolio-level cap. The per-position notional cap is unaffected.

**✅ RESOLVED 2026-09-04 — the R:R gate state is VERIFIED `shadow`, and the three records now agree.**
The open question was whether the 09-03 revert had actually reached the running processes, since
`config.py` still defaulted to `"active"` and `.env` cannot be read. It had. Evidence chain, each
link checked rather than assumed:
- a **fresh settings load** returns `rr_gate_mode = shadow`; because the *code* default was
  `"active"`, that mismatch is itself proof `.env` is overriding — no need to read the file;
- the **uvicorn `--reload` CHILD** (not the parent, which never restarts on reload) started
  **2026-09-03 12:28:21**, and the **celery worker** at **2026-09-04 08:37:49**;
- the revert commit is **2026-09-03 09:34:45** (`git log -S` on the CHANGELOG heading).
Both live processes re-imported config *after* the flip ⇒ both hold `shadow`. The general recipe is
now written down in CLAUDE.md ("HOW TO VERIFY A GATE'S LIVE MODE") so this costs minutes next time.
**Also done:** `config.py`'s default moved `"active"` → `"shadow"` so a fresh checkout or CI can no
longer silently run the refuted state, and its comment block — which still argued the *falsified*
premise that no trend-following system sustains a >50% win rate — was rewritten to record why that
premise was wrong. CLAUDE.md and `STATUS.html` re-synced. Nothing was flipped on the strength of a
doc, and no live behaviour changed.

⚠ **`STATUS.html` had drifted further than the R:R line** and was corrected in the same pass: it
claimed **"2 live · 5 shadow"** gates and showed the **regime gate as ACTIVE** in four places (the
KPI tile, the gate table, the Phase-6 row and the risk list) — three weeks after the 09-02 revert.
It also still called the R:R overlay "queued", carried `sl_atr` at 12/20 (now 17/20), CAS at "0
rows · starts 08-26" (now 1,664 / 8 sessions), MCE as "2 inert pending backfill" (backfill verified
done), and heat at 25.6% (now 58.0%). This is the second time the hardcoded-mode problem has bitten
— **grep every gate name in `STATUS.html` on every mode flip**, it has no live data source.

Optional low-risk work — **three of the original four are now DONE; only one remains:**
1. ~~Deep index backfill~~ — ✅ DONE (verified 2026-09-02). `index_ohlcv_1d` holds **782 bars per
   index, 2023-07-03 → 2026-09-02**, and the market-regime sidecar reports **0 signals** lacking
   200-DMA history, so MCE slice 4 is NOT inert. ⚠ **But only 3 indices are registered** (NIFTY50,
   BANKNIFTY, FINNIFTY — all broad or financial), so **MCE slices 1/3 benchmark EVERY stock against
   NIFTY50**: it is a *market*-RS gate wearing a *sector*-RS label. Its "do not flip" verdict
   therefore **cannot be read as "sector RS has no edge"** — it has never been tested. The blocker
   is a DATA gap: ingest the sector indices (NIFTY IT / PHARMA / AUTO / FMCG / METAL …) the
   Option-B NSE indices CSV already carries, then re-read the sidecar.
2. **⬅ THE ONLY ONE STILL OPEN — the two reporting changes from the horizon finding:** make the
   daily report's "reached ≥1R" line horizon-aware, and surface `sl_atr_mult` as a column in §2 of
   the report and on the Opportunities list. Both read-only/UI; neither touches the order path.
3. ~~`PAPER_SAMPLING_CAPITAL_INR`~~ — ✅ DONE. It is set to 500,000 and the daily report has printed
   **both** denominators since 2026-09-03 (§5: "₹58,034 = 58.0% of the ₹100,000 LIVE capital …
   against the ₹500,000 SAMPLING scale that is 11.6%"). **Push remains manual and pending.**
4. ~~Kill the duplicate Celery beat~~ — ✅ RESOLVED (verified 2026-09-04): one `make worker` tree
   only, no orphan `worker -B`.

**▶ ⚠ RAISED UNPROMPTED 2026-09-04 (review-calendar duty) — STOP WAITING FOR `sl_atr`'s 20th TRADE.**
`sl_atr` is the standing "highest-value pending flip" at 17/20 and is the **only** gate that passes
all three readiness guards (`side_proxy` ✅ · `tail` ✅ — the would-block set stays net-negative at a
−₹545 trimmed mean · `win_rate` ✅ 41% vs 51%), with a would-block set at **−₹18,998 over 17**.
**It still FAILS the deflated-Sharpe bar, and the failure is not about sample size:** the eligible
set — the book a flip would leave you holding — has **Sharpe +0.046 against a 20-trial benchmark of
+0.215**, DSR **6.7%** against a 95% bar, verdict *"more data cannot rescue it; the candidate is not
ahead"* (and trials are treated as independent, so the true deflation is worse). **Three months of
shadow accrual has produced zero promotable gates and two reverts. The leak is upstream of gating.**
⇒ **The next action is H8, not more accrual** (see below). Do not spend another week waiting for
three more resolved trades to answer a question the bar says the count cannot answer.

**▶ ✅ DONE 2026-09-04 — H8, THE NEGATIVE CONTROL. VERDICT: THE BAR IS SOUND, AND `sl_atr` IS DEAD.**
Report: [`analysis/dsr-negative-control-2026-09-04.md`](analysis/dsr-negative-control-2026-09-04.md).
Code: `app/services/dsr_control.py` (pure, stdlib, seeded) · `scripts/dsr_negative_control.py` ·
`tests/test_dsr_control.py` (14 tests — the standing guard, not just a one-off report).

⚠ **H8 as specified in `quant-agent-findings.md` was NOT sufficient and was extended.** It asks only
*"does the bar reject pure noise?"* — but **a bar that rejects everything passes that trivially**,
and ours rejects everything. A specificity-only test would have gone green on a useless instrument.
Both arms were built:

| arm | result | expected |
|---|---|---|
| specificity · random content-free partitions of the real book | **0.00%** cleared | ≤ 5% ✅ |
| specificity · **best of 20 zero-edge candidates** (the selection we actually perform) | **1.10%** cleared | ≤ 5% ✅ |
| power · minimum detectable true per-trade Sharpe @ 50% | **0.43** (t ≈ 3.83) | — |
| power · minimum detectable true per-trade Sharpe @ 80% | **0.52** (t ≈ 4.55) | — |

**⭐ THE HEADLINE: the bar is equivalent to demanding a t-statistic of ≈3.6 on the trade series, and
that hurdle is FLAT IN n** (3.76 at n=30 · 3.62 at n=78 · 3.55 at n=1000). That converts an opaque
probability into a number the literature already argues about — **Harvey, Liu & Zhu (2016) recommend
t > 3.0 for accepting a new factor**, precisely for multiple testing. **Our bar sits just above that:
defensibly calibrated, not arbitrary, not broken.** It also finally explains why MinTRL keeps
returning `None` — the benchmark falls as `1/√n` while the required t stays put, so **more data does
not lower the bar**; it only sharpens an estimate that has to be large in the first place.

**Consequences, in force from now:**
1. **`sl_atr` is DECIDED: NO. Stop accruing.** Its eligible set is Sharpe **+0.046 over n=78 ⇒
   t ≈ 0.41** against a ≈3.6 hurdle — short by ~9×, and far below even the low-power region where
   the bar could be accused of missing something. It passes all three readiness guards and still has
   no measurable edge in the book it would leave behind. The 20-trade trigger is **withdrawn**; the
   count was never the constraint.
2. **"Fails the bar" ≠ "no edge" — except when it is this far short.** The bar has ~0 power between
   t ≈ 2.6 and t ≈ 3.5, so a genuine but modest edge is invisible to it. That is the price of
   multiple-testing correction and the right trade for a promote-to-money decision. **A future gate
   failing at t ≈ 2–3 deserves a different conversation from `sl_atr` at t = 0.41 — so record the t,
   not just the pass/fail.**
3. **The leak is upstream of gating, now demonstrated rather than suspected.** Three months of shadow
   accrual, eight gates, two promotions both refuted, best surviving candidate at t = 0.41. No
   partition of these trades will clear t ≈ 3.6, because the trades carry no edge to partition.
   **Selection has been optimised; what GENERATES the candidates has not.**

⚠ **Stated limits** (in the report): the bootstrap assumes i.i.d. trades while ours overlap and
cluster by regime, so specificity is if anything optimistic; `trials = 20` is still an assumption
until **U4** counts them; and the power arm plants a *constant* edge, so a regime-dependent one is
harder to see than these curves suggest.

**▶ BANKED CAUTION — ✅ MEASURED + RESOLVED 2026-09-08. The caution held: geometry is NOT the lever.**
The prescription below (a read-only, R-scored target-rule counterfactual, run before any spec change)
was executed — `scripts/tp_geometry_study.py` on 1,152 swing+positional signals — and **confirmed the
caution**: no constant-R:R geometry beats the frozen absolute-% target (paired ΔR negative, |t| ≤ 0.65),
and forcing a higher R:R damages the wide-stop majority exactly as the reversal predicted. **D5 closed
as "keep the tourniquet".** Report: `docs/analysis/tp-geometry-study-2026-09-08.md`. The original
caution, preserved:
The standing line (94/295 swing signals at R:R<1 by construction) has acquired **counter-evidence**:
the R:R revert showed that cohort was the *profitable* one (+₹10,585, 63% win) and that **nearer
targets hit twice as often** (33% vs 16% tp_hit), while the tight-stop and horizon findings both say
**wide** stops win. The emergent pattern across three independent findings is **wide stop + near
target** — close to the opposite of "make targets ratio-based". Changing the spec on the old
argument would be **the third instance of the mistake made twice already**. ⇒ **Recommendation: a
read-only target-rule counterfactual first** — replay every closed trade against ratio-based (2R/3R),
ATR-multiple and today's absolute-% rules, **scored in R, never ₹** (risk-first sizing makes a
constant-qty replay a test of bet size, not level placement — that error inverted the horizon
study's first pass). Propose a §6 spec change only if one rule clearly wins. Read-only ⇒ it can run
during cycle-2 accrual.

**▶ FROM THE 2026-09-02 ENTRY/ELIGIBILITY AUDIT — items 1, 2 and 7 are ✅ DONE (2026-09-02).**
In priority order, all reversible, none touching the frozen engine:
1. ✅ **DONE — display honesty.** New `app/signals/eligibility.py` = one source of truth for "what
   would an ACTIVE gate do to this signal": pure, evaluated in the SAME order as the order path,
   reason passed through VERBATIM so the list and the failed click can't word it differently.
   Stamped on BOTH `GET /signals/active` (atr=None, no per-row I/O) and `GET /signals/{id}` (real
   ATR — and that's the endpoint AlertBell reads, so the bell is fixed too, not half the problem).
   New `SignalOut.blocked/blocked_by/block_reason`. Blocked rows are still LISTED — flagged, never
   hidden — with a `⊘ blocked` badge, a dimmed row and a disabled Buy carrying the reason.
   Covered: regime · diversity · sl_atr (with ATR). NOT covered (needs live state): circuit,
   liquidity, chase, market-regime, sector-RS — all shadow today; an ACTIVE gate the preview can't
   judge lands in `unassessed`, never in "clear", so the drift can't silently return. **⚠ Flipping
   any uncovered gate ACTIVE means extending that module IN THE SAME COMMIT.** 12 backend tests
   incl. the contract test (list-blocked ⇒ order path 409s with the SAME string) + 6 frontend.
2. ✅ **DONE — `size_for_fill` wrong-side bugfix.** `side` is now a REQUIRED keyword and the risk
   distance is directional; a BUY at/below its own stop (or a SELL at/above) sizes to 0 and the
   order is rejected, with `place_paper_order` raising an accurate "price has moved through this
   signal's stop loss — the setup is void" instead of the generic "size rounds to 0". 4 regression
   tests with canaries (old code: 43 shares; fixed: 0). **The one pre-existing bad row in the dev
   DB is untouched** — the fix is forward-only; decide separately whether to close it out.
3. **R:R floor overlay** (shadow-first, moded, the `regime_guard` pattern) — the biggest remaining
   arithmetic defect: 94/295 swing signals have targets closer than their stops. A money-path build,
   so post-watch-mode.
4. **Directional trigger zones + an entry window** — split the symmetric ±0.5% zone into
   `trigger_cross` / `pullback_zone` / `void`, and separate the ENTRY window (D+1…D+2) from the HOLD
   window (5/30 trading days). Note: the signal-age sidecar says age itself shows **no** penalty yet;
   **displacement in R is the discriminator**, so gate on displacement and use age only to stop
   re-listing. (`conviction.ts` currently documents an age-decay claim the sidecar contradicts — fix
   that comment.)
5. **Portfolio heat cap** — 45.3% of capital at risk across 23 open positions today, with no cap in
   code. Elder 6% / Tharp 6–10% ⇒ 3–5 concurrent positions at ₹1L and 2%/trade.
6. **Position-advisory upgrade** — `position_health.py` already returns CUT/WATCH with reasons; add a
   positive HOLD verdict, an explicit ACTION (cut / trim ½ / trail to breakeven / hold), a broader
   technical read than Kaufman ER alone, and PUSH a CUT to AlertBell instead of waiting for a page
   visit.
7. ✅ **DONE — sidecar preamble bug** (extended after review: `entry_quality_shadow` had the same
   hardcoding and is the only gate that actually BLOCKS money, so it mattered most; and the banner now
   stamps `MODE_EFFECTIVE_FROM`, without which the first report after the 09-02 revert would have said
   "nothing is suppressed" about the 88 suppressed trades from the ACTIVE window — in the very report
   that feeds the keep/revert decision). `regime_gate_shadow` AND `circuit_gate_shadow` both
   hardcoded "SHADOW: nothing is suppressed" — false for the 19 days the regime gate ran active, so
   the reports used to justify keeping it on misstated their own regime. `render_markdown` now takes
   the live `mode` and renders it via one shared `eligibility.mode_banner` (active ⇒ "⚠ THE GATE IS
   ACTIVE — these signals ARE being suppressed on the order path right now"). 3 regression tests
   incl. a canary that the old string must NOT appear in active mode. Also ✅ **`conviction.ts`**: the
   age-decay term was documented as "the single most evidence-backed term" citing the signal-age
   study, which actually headlines "no stale-entry penalty visible yet" — re-documented on its
   MECHANICAL rationale (less runway near expiry) with a pointer that DISPLACEMENT is the measured
   discriminator. No behaviour change; the ranking weights are untouched.

**▶ ▶ REVIEW CALENDAR — Claude owns this and must RAISE each item unprompted when its
trigger fires (user rule 2026-09-03). Never flip on an argument; read the data first.**
The bar for every gate is **≥20 resolved would-block trades AND the would-block set
net-negative AND worse than the eligible set** — plus, from 2026-09-03, **the sign must
survive trimming the tail** and the partition must not be a proxy for something else.

| item | mode | stands at | trigger to re-check | current verdict |
|---|---|---|---|---|
| **CAS Stage 1 accrual** | — | 6 sessions × 208 rows | **Fri 2026-09-04** (watch-mode end) | on track; `make worker` must be up 15:15–15:33 IST daily, a missed window is unrecoverable |
| **`sl_atr`** | shadow — **DECIDED 2026-09-04: NO** | 17/20 resolved flagged; **t = 0.41 vs a hurdle of 3.6** | ⛔ **none — stop accruing.** The count was never the constraint | ⛔ **CLOSED by H8.** It passes all three readiness guards and is still the clearest case the bar has ever rejected: its eligible set is Sharpe **+0.046 over n=78 ⇒ t ≈ 0.41**, short of the bar's ≈3.6 hurdle by ~9×. H8 proved the bar is SOUND (rejects noise at 1.1%, accepts real edges at ≥80% power), so this verdict is the instrument working, not failing. Report: `docs/analysis/dsr-negative-control-2026-09-04.md` |
| **anti-chase** | shadow | 4/20 resolved chased | when ≥20 resolved | far off; retrospective reconstruction says the chase cohort is the loss, forward-stamped n is thin |
| **liquidity** | shadow | 19/20 resolved illiquid | when ≥20 — but ⚠ | 5a deep-dive already ruled **DON'T flip** (illiquid set net-POSITIVE); reframe as a sizing/slippage modifier |
| **circuit band** | shadow | 0/20 resolved blocked | when ≥20 resolved | nothing to measure yet |
| **sector-RS** | shadow | would-block not worse than eligible | after sector indices are ingested | ⚠ **never actually tested** — only 3 broad indices exist, so it benchmarks every stock against NIFTY50. Data gap, not a verdict |
| **market regime** | shadow | banner says ✅ READY | **a 2y corpus run only** | ⛔ **DO NOT FLIP — the banner is measuring SIDE.** NIFTY was below its 200-DMA 33/33 days; 39 LONG all blocked, 11 SHORT all kept. It would block the better-median, better-win cohort on a mean where **NDRAUTO alone is 94% of the long loss** |
| **R:R ≥ 1** | shadow (reverted 09-03; **mode VERIFIED live 09-04**, `config.py` default moved to match) | 24 resolved would-block | needs a proper bar + tail check | ⛔ blocked the only profitable cohort (**+₹10,585 / 63% win**); R:R<1 is a proxy for a WIDE stop |
| **regime (ADX 20–25)** | shadow (reverted 09-02) | 91 resolved suppressed, +0.078 expR | re-promotion needs a FRESH forward window | settled: do not re-promote on the same §8 backtest |
| **momentum ×1.5 retune** | shadow | **3 minted, 0 resolved** in 6 days | — | ✗ **stalled** — at ~0.5 signals/day with no resolutions this decision is years away by this route; needs a backtest path instead |
| **pair df-vs-adf** | shadow | nightly minter accruing | when both arms have resolutions | accruing |
| **profit-lock breakeven** | live rung ₹2,000 | A/B built 09-03; 20 of 99 differ | ADR-denominated variant, pre-registered k | ⛔ ₹800 NOT shipped — 13 runners clipped vs 7 blow-ups prevented; the knob's UNITS are wrong |
| **deflated-Sharpe bar** | ✅ BUILT 09-03 · ✅ **VALIDATED 09-04 (H8)** | every gate FAILS it — and the bar is now proven sound, so that is a finding about the gates | re-read each `make analysis` | `app/services/deflated_sharpe.py`. **Not one gate's eligible-set Sharpe even exceeds its 20-trial benchmark**, so MinTRL is `None` for all — more data cannot rescue them. market-regime −0.004 vs +0.331 (DSR 2.9%) · chase +0.032 vs +0.266 (4.9%) · sector-RS −0.105 (0.3%) · liquidity −0.150 (0.1%); bar 95%. **The constraint is NOT sample size — the leak is upstream of gating** |
| **pre-COVID backtest** | held by the user 2026-08-28 | — | **⏰ TRIGGER FIRED — raised 2026-09-06** (was: "hold until after watch mode ends Fri 2026-09-04") | reminder DISCHARGED, queued as Q5 on `feature/pre-cycle2-hardening`. **Does not block cycle 2** (touches no recorded number). ✅ **DATA ACQUIRED 2026-09-08:** `ohlcv_1d` now spans **2019-10-01 → 2026-09-04** (~7 yrs · 1,093 trading days · 2.08M bars · 3,373 names incl. 2,070 inactive/historical for a point-in-time survivorship-safe universe) — back to the bhavcopy archive floor (2019-09-02 = 404). ⚠ **Bars are CA-UNADJUSTED** — 7 yrs of splits/bonuses read as fake gaps and MUST be handled first. **The backtest STUDY is NOT run** — its blockers D1/D5 are both RESOLVED 2026-09-08 (engine stays frozen), so it is now clear to run; the remaining precondition is CA-adjusting the historical bars. Value is VALIDATION, not tuning: the engine is frozen for the current regime |
| **readiness guards** | ✅ **BUILT 2026-09-03** | market-regime now vetoed | — | `flip_readiness.py`: `side_proxy` · `tail` · `win_rate`, run as a veto BEFORE each sidecar's own test. Every banner also now ships an **evidence-of-record** block (n · resolved · mean · median · **trimmed mean** · win% + guards + DSR). It exposed that market-regime's would-block **trimmed mean is +₹200** against a −₹302 mean — trimming REVERSES the sign |
| **D2 / R2 spread-width gate** | provisionally DROPPED 2026-09-07 (user sign-off); **final call PARKED 2026-09-08** | R2 not built — the drop stands for now | ⏰ **WHEN CYCLE 2 COMPLETES — Claude MUST raise it then** | User 2026-09-08: hold the final keep-dropped-or-revive decision until cycle 2's forward evidence is in; **do not re-litigate before then, and do NOT let it block cycle-2 start.** Prior lean is DROP (a 9th gate adds a deflation trial and gating is closed as a programme) unless cycle-2 data changes the picture |

**▶ POST-WATCH-MODE RESEARCH QUEUE (after Fri 2026-09-04)** — a consolidated "wind it back" list of the
analysis threads parked during watch mode lives in the **`post-watchmode-research-queue`** memory
(read-only research, none on the money path). Headline order: (1) a deflated-Sharpe / multiple-testing
bar before promoting any shadow gate; (2) shadow-test a Minervini/O'Neil trend-template gate for the
entry-leak; (3) CAS Stage-2 (excess-vs-acceptance); (4) intraday §8-shadow review; (5) the 2018+
longer-history backtest (data-sourcing spike first). Sources: the two ebook-review memories +
`docs/reading/e-book-suggested-takeaways-2026-08-29.md`. Ongoing monitor: ~~the regime-gate keep/revert
(~09-15)~~ — **DECIDED 2026-09-02: REVERTED to shadow** (7 straight days of a net-positive suppressed
set, 88 decided = 4.4× the bar; `docs/analysis/regime-gate-revert-2026-09-02.md`). The remaining
readiness watch is **`sl_atr` at 17/20** — the closest of any gate to a decision, and independently
reproduced at its 1.0× threshold by the 08-25 horizon study.

**▶ 2026-08-25 also produced:** `docs/analysis/horizon-recovery-2026-08-25.md` (the horizon +
stop-width study — read its §6/§7 before acting on it; it is retrospective, not a walk-forward) and
a full rebuild of `docs/STATUS.html`.

**▶ CAS Stage-0 CONFIRMED + Stage-1 DONE 2026-08-25 — next = Stage 2 (study).** Stage 0 (probe) proved
Kite `/quote` carries `indicative_close_price` + `total_imbalance_qty` (+ reference/limit bands) — no
vendor. Timing: populate ~15:21, EXECUTE ~15:29; gotcha: `ohlc.close` = prior day's close (true close =
last_price/indicative after 15:29). **Stage 1 (auto-capture) BUILT + reviewed:** `cas_daily` table
(migration `c9d0e1f2a3b4`, applied to dev) + `app/services/cas_capture.py` + `app/tasks/cas_tasks.py`
(market-hours Celery beat task, self-guards to 15:15–15:33 IST, F&O universe, upsert freezes the 3:15
price + KEEPS LAST NON-ZERO imbalance) — runs daily whenever `make worker` is up. 8 tests; bug-hunter
BUGS-FOUND→HIGH fixed (latest-imbalance was storing the post-match 0, destroying the predictor). **NEXT:
Stage 2 — once `cas_daily` accrues (~weeks), study the overnight reversal (next-day return from
`ohlcv_1d` vs the CAS move; read-only, control for the oversold regime, block-bootstrap like the regime
study).** NEVER an intraday predictor. Doc: `docs/CAS_CLOSING_AUCTION_ANALYSIS_2026-08-21.md`; memory
[[cas_closing_auction]]. Pending (non-urgent): push the branch (`fd29930`, `27b9e28`, `f74518b`, + the
new CAS-probe-window + CAS-Stage-1 commits); daily `docs/analysis/*.md` via the normal flow (raw
`cas-probe-*.jsonl` large — keep local).


**Handover items from the 2026-08-19 two-session split — now RESOLVED:**
1. **Provisional breadth-flood fix — MERGED 2026-08-20 (`c1b4752`).** The `--ff-only` Session 1 asked for
   was impossible (the branches had diverged from base `845ff5c`), so the code fix `c8f3b50` was
   **cherry-picked** onto this branch (linear history preserved; the stale `8359bd1` docs commit was NOT
   replayed — its one useful artifact, `docs/analysis/provisional-health-watch.md`, was carried
   separately). The running `make live-worker` picks up the new behaviour on its next restart. Forward
   watch still has NO scheduler — run `scripts/provisional_health.py --days 7` each session.
2. **Red baseline — RESOLVED** (`e32fd48`), re-verified 2026-08-20: order-path set = **138 passed,
   exit 0**.

**▶ ANTI-CHASE work DONE 2026-08-21 (two slices, shadow-first — the SRTL/weak-entry leak's timing half).**
Motivated by a chase_r-vs-outcome measurement (39 resolved paper trades): **chase_r ≤ 0.33 → +₹275 avg /
62% win over 37 trades; the only 2 past 0.33R (incl. SRTL) were both losers, −₹3,074 avg.** Two slices:
(1) **Entry-context surfacing on BOTH AlertBell + the Live Signals page** (frontend-only) — each entry
alert now shows SL/TP/**R:R**, confidence, **signal age**, the **validity window** (`Nd left` / `till
HH:MM` IST + `⚠ stale` ≥80% elapsed + `choppy`), and a **"best by <date>"** trade-window (the
80%-elapsed mark — directly flags the stale-entry / ~day-25-of-30 leak); Live Signals also **defaults to
Entry-only**; `AlertBell 38 + LiveSignals 17 tests`, ui-reviewer PASS-WITH-NOTES ×2. **Both surfaces are
still the ephemeral `useAlertStream` feed** (session, 100-cap, trigger-price snapshots, no dedup) — the
proposed NEXT step is to repurpose Live Signals into a persistent, **live-priced**, deduped,
lifecycle-aware signals *list* (keep-until-resolved + a top-5 conviction ranking), backed by the signals
API (which already dedupes into `sources_count` + carries `status`/`validity_until`/`near_expiry`).
(2) **Anti-chase eligibility gate** (`app/signals/chase_guard.py`, the 6th order-path
overlay, mode **shadow**) — blocks when the LIVE LTP has run > `chase_max_r` (0.33) × 1R past entry;
direction-aware, fail-open on no-price/zero-risk; stamps `broker_payload["chase_gate"]` (distinct from
the broker's post-fill `chase`); sidecar `chase_shadow.py` → `chase-shadow-<date>.md` (chased/near-entry/
no-data + flip banner) in `make analysis`. `test_chase_gate.py 17 tests`, order-path regression 156 green,
**quant-verifier PASS-WITH-NOTES + bug-hunter CLEAN** (findings applied: 4dp chase_r stamp, deterministic
`ORDER BY placed_at`). Flip readiness **NOT READY** (2/20 chased resolved) — accrues; flip needs sign-off.
Two-window autopsy (04–12 vs 13–21 Aug) confirmed the recent "losing streak" is **n=4 + a down-drifting
tape** (NIFTY 1 up/7 down days), NOT degraded selection — finding: a market-regime **slope/breadth** term
(not the 200-DMA level, below in both windows) is what separates the good window; fold into MCE slice 4.

**▶ USER PLAN 2026-08-21: build items (a)→(b)→(c) IN ORDER, each after user verification. (a) DONE.**
**(a) make-analysis diagnostics — ✅ DONE 2026-08-21:** `signal_age_report.py` (→ `signal-age-<date>.md`,
how far into a signal's validity we ENTERED + P&L by age bucket) + `market_regime_report.py` (→
`market-regime-<date>.md`, NIFTY vs 200-DMA AND 20-DMA + breadth + VIX, flags level-vs-breadth disagree),
both read-only, wired into `daily_analysis.py`; 8 tests; quant-verifier PASS-WITH-NOTES (1 HIGH fixed —
cohort re-keyed on `Position.opened_at`, not `Signal.created_at`). **EVIDENCE: the entry-age edge is
monotonic — 20–40% elapsed = +₹7,182/67% win (sweet spot); EVERY band past 40% is net-negative. Trade
fresh (≤40% of validity), not stale.** **(b) persistent Live-Signals list — ✅ DONE 2026-08-21:** new `OpportunitiesTable.tsx` stacked above the
alert feed on the Live Signals page — sourced from `/signals/active` (deduped + keep-until-resolved),
**live-priced** (`useLiveQuotes`/`PriceCell`, chase recomputes on the LIVE tick), ranked by a v1
`conviction.ts` score (confidence − age-decay [folds in item-(a)'s ≤40% finding] − choppy), top-5 ★, rest
by recency+confidence. 12 tests; full FE suite 401; ui-reviewer PASS-WITH-NOTES. **(c) 3y regime study
→ playbook — ✅ DONE 2026-08-21:** `scripts/regime_study.py` + `app/services/regime_study.py` →
`docs/analysis/regime-study-<date>.md` (575 sessions, NIFTY/Bank/Fin + VIX). **HEADLINE: the two-window
hypothesis is REFUTED — below-200-DMA + WEAK breadth had the BEST fwd-20 (+1.33% vs below+strong +0.21%);
textbook mean-reversion.** quant-verifier PASS-WITH-NOTES: math correct (1e-9 forward-return match, no
look-ahead). **Block-bootstrap (added) verdict: the edge is NOT statistically established** —
P(weak>strong)=83% (short of significance), non-overlap subsample too small (2 strong pts) + flips sign;
the naive +1.33% rests on ~2 overlapping episodes. 6 tests. **⇒ MCE slice-4 must NOT add a breadth term
in EITHER direction from this.** FII/DII flow = DATA GAP (recorder only 36 sessions; no historical API —
backfill needs a new source). **All three user items (a/b/c) DONE + verified.** **Weekend add-ons:
block-bootstrap hardening of (c) + a CAS (Closing-Auction-Session) analysis/plan doc
(`docs/CAS_CLOSING_AUCTION_ANALYSIS_2026-08-21.md`) — plan only, no code.**

**▶ MCE IN PROGRESS — slices 1–4 built 2026-08-20 + slice 5a built 2026-08-21** (details + NEXT in
the CONTINUE HERE block below). Slice 1 = `sector_rs.py` (RS overlay); slice 2 = index price store
(`index_ohlcv_1d`, migration `b8c9d0e1f2a3`) + benchmark provider + wiring; slice 3 = sector-RS shadow
sidecar + flip to `shadow`; slice 4 = the market-regime gate (200-DMA + VIX) + `scripts/backfill_indices.py`;
**slice 5a = the liquidity junk gate (`liquidity_guard.py`), mode shadow** — blocks entries too illiquid
to exit (the SRTL archetype), from ohlcv_1d (real data now). **Index benchmark source = Option B (real
index OHLC via the NSE indices CSV `vix_service` already downloads — NO Kite dep).** All slices
agent-reviewed (quant-verifier PASS ×5 + bug-hunter ×3, findings actioned). Full sliced plan in
[`phases/phase-MCE-market-context-engine.md`](phases/phase-MCE-market-context-engine.md)
("Sliced plan (started 2026-08-20)").

Phases **0–5 CLOSED** · **Phase 6 ✅ GATED + CLOSED 2026-08-20** · **Phase 6.8 ✅ GATED + CLOSED +
merged to `main` (pushed) 2026-08-20**. The regime gate is **ACTIVE** in the paper book (flipped
2026-08-14, reversible via `REGIME_GATE_MODE=shadow` + restart). **The STATE AT A GLANCE block at the
top of this file is the live truth** — read it, not the historical narrative below.

**Phase 6 & 6.8 are done and on `main`.** What remains from Phase 6 are three forward-evidence loops
that continue POST-close (none a code task, none blocking — carried in the phase-06 close report):
1. **Regime gate** — active; monitor the daily `regime-gate-shadow-<date>.md` Flip-readiness banner,
   keep-vs-revert review ~2026-09-15 (first live read had the suppressed set NOT net-negative — watch it).
2. **Momentum ×1.5 retune** — promote once its forward shadow A/B (`retune_momentum_x15` vs
   `retune_base`) beats base (weeks of accrual + user sign-off).
3. **Pair-trading (6.5)** — the nightly minter + outcome tracker run themselves;
   `pair-attribution-<date>.md` answers df-vs-adf once evidence accrues; tune knobs from THAT.

**▶ MCE IN PROGRESS — slices 1–4 DONE 2026-08-20 + slice 5a DONE 2026-08-21 (all mode `shadow`/off —
no money-path change).** Slice 1 = `sector_rs.py` (RS overlay); slice 2 = index price store
(`index_ohlcv_1d`, migration `b8c9d0e1f2a3`) fed from the NSE indices CSV (Option B, no Kite dep) +
benchmark provider + wiring; slice 3 = sector-RS shadow sidecar + flip to `shadow`; slice 4 = the
market-regime gate (200-DMA + VIX, `market_regime.py` + sidecar + `scripts/backfill_indices.py`);
**slice 5a = the liquidity junk gate** — `app/signals/liquidity_guard.py` (block entries too illiquid
to exit: median daily traded value ₹=close×volume < floor, side-independent) + `app/services/liquidity.py`
+ order-path wiring (savepoint fail-open) + `liquidity_shadow.py` sidecar + `settings.liquidity_*`
(₹1cr/day floor). All order-path overlays fail-open in a savepoint; the 5 verdict stamps live in an
`_overlay_stamps` helper. Reviews across the slices: quant-verifier PASS ×5 + bug-hunter ×3 (all
findings fixed w/ regression tests). 18 slice-5a tests; order-path regression green (188).
**⚠ 5a DEEP-DIVE VERDICT (2026-08-21): DON'T flip the liquidity gate; reframe it as a sizing/slippage
MODIFIER later (user decision).** Illiquid set net-positive vs liquid net-negative, robust across floors
₹50L→₹5cr + median + win-rate; and **SRTL is the ONLY illiquid+diversity-flagged trade — the ACTIVE
diversity gate already catches it**, so liquidity is redundant for the SRTL archetype AND would cut a
net-winning set. Realized P&L over a benign sample can't measure liquidity's real value (tail/exitability
risk), so it belongs as an execution-realism modifier, not an entry P&L gate. Keeps shadow (measuring).
This also QUESTIONS 5b (a market-cap size floor may be no better — cross-tab a proxy before the XBRL build).
**▶ NEXT = run the deep index backfill, then let evidence accrue.** BOTH the sector-RS (needs ~21
sessions) and the market-regime 200-DMA (needs ~200 sessions + ~2y for §8) are INERT until index
history is deep enough. The EOD catch-up only heals ≤21d — so run
**`cd backend && uv run python scripts/backfill_indices.py 2023-07-01 <today>`** once to seed depth
(idempotent, resumable, ~2y of NSE index+VIX). The nightly `make worker` keeps it current after. Then
the sidecars' would-block/eligible buckets populate; a shadow→active flip on any gate needs the R-track
(§8-on-≥2y + sign-off; reversible via the `*_gate_mode` setting).
**Slice 5b + 6 (not built):** **slice 5b = XBRL `market_cap` writer** — a greenfield NSE/BSE scraper
(no XBRL/shares-outstanding code exists; `filings_consumer` polls only announcement JSON), populates
`market_cap_cr` (0/2365). **⚠ QUESTIONED by the 5a finding** — a market-cap *size* floor may gate no
better than liquidity; cross-tab a cheap proxy before paying the scraper cost (XBRL may still proceed
for quality-scores value, but not as a junk gate on current evidence). **Slice 6 = news veto** (extend
`event_guard`). Also open (non-blocking): paper day-1 for the 6.8 stack (deferred until
the user says "proceed" — no clock started), and the gated 6.8 research track (R1/R2/F1).

**Next BUILD phase = Phase 6.8 (Execution Realism & Exchange-Safety)** — APPROVED 2026-08-17 (user),
inserted between Phase 6 and the **Market Context Engine** (which stays the phase after 6.8, before
Phase-7 live). Full adjudication of the `REAL_WORLD_NSE_BSE` external review + the sliced build:
`phases/phase-06.8-execution-realism-plan.md`. **▶ 6.8.1 DONE + live-smoke verified and 6.8.2
(spread-aware slippage) DONE + agent-reviewed CLEAN (bug-hunter + quant-verifier) + deployed onto
this Phase-6 branch, all 2026-08-17. ▶ 6.8.3 circuit-band eligibility overlay BUILT shadow-first +
reviewed (bug-hunter 1 MEDIUM fixed, quant-verifier PASS) 2026-08-17. ▶ 6.8.4 continuous open-book MTM
DONE + reviewed (quant-verifier PASS, test-guardian gaps fixed) 2026-08-17. ▶ 6.8.5 CA-adjust OPEN
paper positions DONE + reviewed (quant-verifier PASS w/ 1 HIGH fixed, bug-hunter 2 fixed) 2026-08-18.
▶ 6.8.6 silent-feed-outage alarm DONE + reviewed (bug-hunter 2 LOW fixed, test-guardian gaps fixed)
2026-08-18. ▶▶ ALL SIX PAPER-SAFE SLICES (6.8.1–6.8.6) DONE. ✅ **PHASE 6.8 GATE PASSED + CLOSED
2026-08-20 — merged to `main` (fast-forward), awaiting the user's `git push`** (gate: backend 1477 ·
parity 16 · walkforward 9 · replay 19 · frontend 375 · cargo ok; smoke green). Paper day-1 still
deferred until the user says "proceed". MCE now IN PROGRESS — slices 1–4 built (see the MCE block in CONTINUE HERE).**

**▶ R-track entry-quality overlay DONE 2026-08-18/19 (commits `965b562` + `845ff5c`) — the SRTL
paper loss exposed that the real leak is ENTRY, not exit.** A BUY at 80% confidence fired on
RSI_DIVERGENCE *alone* (₹39 micro-cap × 2666 qty → −₹3.5k / 1.78R) because the confluence
confidence normalizes by the weight of the factors that *scored*, so one 0.8 factor reads 80% and
clears the ≥70% gate. Fix = a downstream eligibility overlay (`app/signals/entry_quality.py`, frozen
engine untouched, the `regime_guard`/`circuit_guard` pattern) with **two independently-moded checks**:
**(a) factor-diversity — `entry_diversity_gate_mode` ACTIVE (user sign-off)**, enforcing the "≥2
factors, never a single indicator" rule → single-factor signals now 409 on the paper order path;
**(b) stop-too-tight — `entry_sl_atr_gate_mode` SHADOW**, a tunable `|entry−SL| < k·ATR`, measured
only. A shadow sidecar (`app/services/entry_quality_shadow.py` → `make analysis` writes
`entry-quality-shadow-<date>.md`) accrues flagged-vs-passed outcomes + an sl_atr flip-readiness banner
(the evidence to eventually activate sl_atr, gated like the regime gate). Reviews: quant-verifier PASS
+ bug-hunter CLEAN; 24 tests, no migration. The exit-ladder replay that ran alongside
(`docs/analysis/exit-ladder-research-2026-08-18.md`) PARKED profit-booking floors (net-₹100 and hard-₹500
both rejected — risk dials, not boosters); the only supported exit change is arming breakeven earlier
(`profit_lock_breakeven_inr` 2000→~800), deferred until more data. **Context complement deferred to the
MCE** (sector/index relative-strength + fundamentals + news as GATES/MODIFIERS, never additive):
[`phases/phase-MCE-market-context-engine.md`](phases/phase-MCE-market-context-engine.md) — each
§8-backtested on ≥2y before live; the daily report must surface each once built.**
(6.8.3 was the plan's "best new idea": a long whose stock hits LOWER circuit has zero buyers, so its
stop cannot fill at any price; bands cached to Redis by a market-hours task, order path reads only,
fail-open, shadow-first — evidence accrues via `circuit-gate-shadow-<date>.md` once paper trading
resumes. 6.8.4 gave carried multi-day holds the rolling MFE/MAE narrative + a weekly per-trading-day
open-MTM series — pure reporting, no look-ahead. 6.8.5 R-preservingly adjusts a held paper position
for a split/bonus on its ex-date — verified `corporate_actions` ratio, admin-entered only, ex-date
worker idempotent+catch-up; **run `make migrate`** for `a7b8c9d0e1f2`). **6.8.2 clean-slate cut (2026-08-17, done):** clock reset in the UI + all
26 open paper positions flattened at the 15:29 IST close (net +₹7,222.66) → book empty. Remaining
follow-up (not a code task): **watch §9 "Fill realism"** in the daily reports to see the ₹ the flat
model had been under-charging, and retune `paper_impact_k_bps` from THAT evidence rather than
pre-data. **GOVERNANCE (user, 2026-08-17):** all Phase-6.8 slices build on
`feature/phase6-overlay-walkforward-retune` itself (no per-slice sub-branches); **paper-trading
day 1 on the new model is DEFERRED until every necessary 6.8 slice is done AND the user is told to
proceed**; merge to `main` only after the whole phase is good. (Lesson from the perf review, now in the plan Build log: `live_worker.py` is the live
path; `tick_consumer.py` is the dormant v1 — a feature wired only into v1 is inert in production.) The F1 spike pulls the `market_cap` data-source decision
forward, which unblocks MCE's fundamentals layer. Post-Phase-6 research/features remain phase-mapped in
the Architecture-review backlog below (Nautilus runtime → Phase 7; competitor/fundamentals → MCE, now
unblocked by F1's `market_cap` writer; seasonality → unblocked + small). Local branch is ahead of
origin — push is manual.

Suites as of 2026-08-10: backend **1120**, frontend **370**. All work through
`b795326` is merged to main **and pushed to origin**.

**Do these — ⚠ HISTORICAL (superseded 2026-08-15; the current next-steps are in the summary above
+ the STATE block). Kept only as a record; do NOT action items 0–2:**

0. **TODAY'S OPEN QUESTION — did the intraday shadow layer produce anything?**
   Monday 2026-08-10 was its first live session. **Every scheduled beat fired**
   — confirmed from Celery's own result records (Redis db 2), not inferred:

   ```
   09:26:13  SUCCESS  time_0925     {'gainer_925': 0}
   09:31:25  SUCCESS  intraday_15m  {'pdh_pdl': 0, 'orb_15m': 0}
   09:46:25  SUCCESS  intraday_15m  {'pdh_pdl': 0, 'orb_15m': 0}
   10:01:26  SUCCESS  intraday_15m  {'pdh_pdl': 0, 'orb_15m': 0}
   10:16:29  SUCCESS  intraday_15m  {'pdh_pdl': 0, 'orb_15m': 0}
   ```

   Data was healthy throughout (6,197 fresh 15m bars, live worker current), so
   **the zeros come from "nothing cleared the confidence gate", not from a
   broken pipeline or a missed schedule.** The stack was stopped ~09:32 and
   restarted ~09:46; that window fell entirely between two 15m slots, so nothing
   was lost. Read **§8 of `docs/analysis/2026-08-10.md`** after the evening run
   for the full day.
   If §8 shows zeros for several sessions running, the question becomes whether
   `min_confidence: 70` is simply unreachable for these setups. That is a real
   finding about the profiles and exactly what the shadow layer was built to
   surface — **do not "fix" it by lowering the gate without evidence.**
   *(Method note, because it cost time: Celery results carry no task name unless
   `result_extended` is on, and they live in Redis **db 2**, not db 0. Identify a
   task by its return payload shape. Process uptime is NOT evidence of when a
   beat ran — a restart resets it.)*
1. **`/phase-gate` for Phase 3 — SCHEDULED BY THE USER, MANUALLY, FOR FRIDAY.**
   Explicit instruction 2026-08-08: **do not run it early.** Nothing is being
   waited on; both criteria are already satisfied on disk — the soak is MET ×2
   (`PERFORMANCE.md`) and the shadow week is MET with **14 consecutive clean days
   07-20 → 08-06** in `backend/shadow/shadow_week.log`. Do NOT re-run either.
   (Both checkboxes were stale for weeks — the work was done and never read back.
   If a checkbox here disagrees with an artifact, trust the artifact.) Keep
   running `scripts/shadow_day.sh` daily so the streak is unbroken on the day.
2. **Phase 6 — outcome tracking + entry-selection: UNDERWAY, not a plan anymore.**
   The three sign-off questions were answered 2026-08-12 and the build has run
   through 6.4 (see the STATE block + `docs/phases/phase-06-plan.md`, the live
   tracker). The binding-constraint diagnosis held: **entry/regime selection, not
   exits** — and it is now quantified and fixed shadow-first. What remains is
   behaviour-changing and user-gated: flip the regime gate shadow→active, promote
   the `momentum ×1.5` retune once its forward shadow A/B beats base, then 6.5
   pair-trading. Nothing here auto-advances.
3. ~~One imminent bug is logged, not fixed~~ — **FIXED 2026-08-07**, plus a
   CRITICAL look-ahead the owed quant-verifier pass turned up next to it.
   `_pick_expiry` walks the in-window expiries instead of dead-ending on the
   first (recovers **26 of 35** lost trading days), the chain is now bound to the
   forward's own day, and weeklies stay excluded per §7.6 via an explicit
   `SellRules.require_exact_expiry_future`. No calibrated number moves. Detail:
   `phases/phase-04-fo-suggestions.md` §9.
   **▶ ONE USER RULING IS OPEN:** flipping that flag takes the engine from
   33/42 to 42/42 producing days, but real OI data (§9.3) shows a NIFTY weekly's
   whole chain carries ~1% of the monthly's, so the fill model would overstate
   credit. Don't flip it without a chain-level liquidity gate first.
4. ~~Check the EOD self-heal actually caught 2026-08-06.~~ **Partly resolved —
   re-checked 2026-08-10 10:10 IST.** `ohlcv_1d` and `india_vix_daily` are
   current to **08-07** (the last trading day), so the ≤21-day catch-up works.
   But **`fo_bhavcopy` and `fii_dii_daily` still stop at 08-06** — one session
   behind. Those feed §7 F&O engine health and the §2.7 flow factor, so a
   persistent lag quietly degrades both. Worth one look at whether the 08-07
   evening beats for those two ran; the self-heal should absorb it, but verify
   rather than assume — that is exactly the mistake that let the earlier
   month-long outage hide.

Kite subscription ACTIVE. Push to origin is MANUAL (user). History on main is
linear — merge phase branches with `--ff-only`.

**✅ 2026-07-11 (Saturday session): the deferred FULL three-leg gate
ran GREEN on the perf-fix commit exactly as shipped** — 731 backend /
131 frontend / 16 parity / 9 walkforward / 11 replay, plus
ruff·mypy·eslint·tsc and cargo fmt·clippy·test; `make check` exit 0.
**Both LOW hardening fixes from the perf-fix review then landed same
session** (ledger recipes verbatim): (a) `PUBSUB NUMPAT`
publish-everything sentinel — a pattern subscriber can no longer be
silently starved by CHANNELS-based gating; (b) watched-set refresh is
wall-clock inside `process_item` instead of riding droppable pulses
(also closes the startup gap: first-second forming events used to
publish to nobody until the first pulse). +2 regression tests,
stash-proven to FAIL pre-fix; targeted live suite 50 green;
bug-hunter re-review CLEAN (executed repros).
**Same evening (user-approved):** the provisional-confidence design is
PINNED (ledger §Decisions — throttled batch rescore of a bounded hot
set on a refresher thread; O(1)-incremental rejected; implementation
AFTER the soak) and the **3.5 alert UI is DONE** (topbar AlertBell +
useAlertStream; smoked against the real stack; ledger §Alert UI).
**Late session, budget-extended: the Tailwind v4 token migration is
DONE (thread 3, `10a9d2b` — all 898 broken sites; 5-theme verified;
ui-reviewer PASS-WITH-NOTES with the polish backlog recorded) and the
WATCHLIST slice is DONE (`cb2092d` — model→migration→API→WS
fanout→UI; bug-hunter MEDIUM fixed with executed repro; end-to-end
browser-verified server-side alert filtering; ledger §Watchlists).**
Frontend 161 / backend 744-ish tests green at session end; the only
3.5 remainder is the provisional-confidence implementation (post-soak,
design pinned).
**SOAK #2 RAN 2026-07-13 — measured but not proven; HARDENING FIXES
SHIPPED SAME NIGHT** (full record: ledger §Second soak). Run #4 clean
40 min → p50 7.5 ms · p99 (20,50] · dwell FIXED; **p99<10 ms NOT met at
2,055 instruments — user ruling pending** (restate at scale vs optimize
+ re-soak). The day's four stability failures are FIXED (commit
766050e, +9 tests, bug-hunter reviewed): Celery-OOM gate, writer
exit-race, 36-min drain wedge, and a heartbeat + `make soak` target.
07-13 candles rebuilt from Kite — 5m/15m/1h full (75/25/7 buckets,
~2040 stocks, matches the clean 07-10 rebuild); only 1m left empty
(low-value); 1d/EOD never affected.
**SOAK #3 RAN 2026-07-14 (`make soak`, first outing) — STABILITY PASS**
(full record: ledger §Third soak). 9.05M ticks / 828k candles / 0
skipped across 6h13m; 745 heartbeats, queues ~0 throughout; a 14:18
Kite WS drop exercised the whole 766050e fix slate live (exit-3 →
8 s restart, no DB coverage dip, second recording header); Celery list
0 all day; recording lossless (tick+pulse counts == worker counters
exactly). Latency CONFIRMED steady-state across both segments: **p50
7.5 ms · p99 (20,50] · max <100 ms · dwell p99 2 ms — p99<10 ms still
NOT met at 2,055 instruments; the ruling is now purely a user
decision** (restate at scale vs optimize + re-soak — no more data
needed). Only data damage: the pre-09:15 start was missed (worker up
09:26:42) → first ~12 min thin/absent; REPAIRED same session via the
new committed `backend/scripts/repair_morning_window.py` (+6 tests) —
official-5m refetch + 15m/1h recompute; 07-14 5m/15m/1h now
walk-forward-trustworthy (ledger §Third soak).

**RULING MADE 2026-07-14 evening (user): option (b) + restatement —
EXECUTED same night** (commit 8eac05a; ledger §Decisions + §Optimization
slate): budget now **p99 ≤ 50 ms @ full universe** (PERFORMANCE.md), and
both scoped optimizations shipped with bug-hunter review clean-after-
fixes (SET dedupe w/ 10 s keep-alive + observed-failure cache clear;
commit-burst batching; live suite 66 green). Same night: morning-repair
re-run proved the 14 failures are deterministic STALE kite_instruments
tokens (re-sync deliverable), not API flake.

**RE-SOAK RAN TWICE — 2026-07-15 + 2026-07-16 (optimized worker
8eac05a): STABILITY PASS ×2; BUDGET MET; NO TIGHTENING** (full record:
ledger §Fourth soak). 9.35 M + 9.54 M ticks, 848 k committed candles
each day, 0 skipped, queues never past 2/10,000; three more Kite 1006
drops (incl. the first back-to-back double drop, 07-16 14:42) all
recovered unattended in 8–17 s; both recordings lossless. Latency
verdict (honest): every segment's total p99 still in **(20,50]** →
the (10,20] tightening criterion NOT met, budget line stays **p99 ≤
50 ms** — but the slate did move the interior (processing p50
7.5→5.0 ms both days; processing p99 into (10,20] on 07-15's main
segment; max 98→89 ms). **The End-Phase-3 "full-session soak clean"
criterion is now MET on both stability and latency — no open ruling.**
Data: 07-15 started 3.3 min late → thin 09:15 open bucket, REPAIRED
same night (`repair_morning_window.py --day 2026-07-15 --until-ist
09:20`); 07-16 started 09:12:31 (first pre-09:15 soak) — only blemish
is the volume-undercounted 5m 14:40 bucket from the double restart
(GREATEST-merge keeps the larger partial; accepted per the 07-14
precedent).

**✅ STREAMING REPLAY DIGEST — DONE 2026-07-17 (ledger §Streaming
replay digest):** `app/broker/replay.py` is streaming end-to-end
(iter_recording/iter_events/replay_stream + atomic emit; old API =
thin wrappers, golden digest byte-identical); ~38 MB flat RSS, ~3 min
per full-day recording (was exit-137 on a 15 GB box). Replay suite
11 → 19; bug-hunter no tier-A (MEDIUM emit-clobber fixed +
regressions). **ALL FOUR soak recordings pinned; replay ≡ live EXACT
on every recording with surviving counters** (07-14: 828,180/14,097 ·
07-15: 847,995/15,493 · 07-16: 848,693/14,654 committed/triggers all
exactly matching worker counters; 07-13 partial-reconciled by design —
runs 1–3 console logs were lost that day). Determinism contract holds
at full-day, full-universe, multi-restart scale.

**✅ THROTTLEDKITE ROUTING — DONE 2026-07-17 (ledger §ThrottledKite
routing):** `fetch_historical` deleted; gap-fill fetches through ONE
shared `ThrottledKite` (full-universe fill now paces ~3 req/s ≈ 35 min,
documented as post-outage repair, not bulk rebuild). bug-hunter found
the diff clean AND three pre-existing latents in the same seam — all
fixed + stash-proven same session: UTC-as-IST fetch window (mid-session
gap-fill was a silent no-op — requested windows shifted 5.5 h into the
past), poisoned-transaction silent COMMIT-as-ROLLBACK data loss (now
commit-per-instrument + rollback), dead-session-token grind (now aborts
CRITICAL at first TokenException; stale-instrument InputExceptions stay
isolated). Suites 49 green + full non-parity leg.

**✅ KITE_INSTRUMENTS RE-SYNC — DONE 2026-07-17 (ledger
§kite_instruments re-sync):** root cause was upsert-only sync — rows
absent from Kite's dump (= dead instruments) were never deleted; 1,584
carcasses accumulated and the "16 stale tokens" were 15 stocks moved
to NSE's T2T series (token rotated) + 1 delisted (AURIGROW) — split
corrected 2026-07-17 during the (c) execution — whose leftover
plain-symbol NSE rows kept joining the universe.
`sync_instruments` now sweeps rows absent from the dump (watermark +
partial-dump tripwire at 50%); EXECUTED live: 60,751 upserted / 1,582
swept / forensic snapshot kept; worker join 2,056 → 2,037 — soaks and
repairs no longer touch dead instruments by construction. **Surfaced
for user decision (ledger §Decisions): 296 active master stocks are
T2T-series (`-BE`) listings the join has NEVER covered** — include via
suffix mapping, accept exclusion, and/or deactivate the ~15 truly-dead
master rows.

**✅ T2T UNIVERSE RULING — MADE + EXECUTED 2026-07-17 (user: (a)+(c);
ledger §Decisions + §Universe deactivation):** (a) the 296 T2T
(`-BE`-series) stocks stay excluded from live coverage — self-healing
exclusion (daily sync + plain-symbol join re-cover any stock NSE
returns to the EQ series automatically); they remain active master
rows. Future re-inclusion path recorded in §Decisions + memory: option
(b) suffix-mapping SCOPED to the Investment engine if it graduates in
Phase 6. (c) EXECUTED via new committed
`scripts/deactivate_dead_stocks.py` (+4 tests, T2T-canary): 15 ghost
rows deactivated (14 dead-everywhere incl. GUJGASLTD/JBCHEPHARM/
RELINFRA-class corporate deaths + v1 noise like NIFTYNXT50; 1
BSE-only mover AVAILFC), forensic_stocks_deactivated + documented
reversal; active master 2,348 → 2,333. Corrected en route: the "16
stale tokens" were 15 T2T series-moves + 1 delisting (not "12 BSE + 4
delisted").

**⚠ INCIDENT (pre-existing, discovered 07-17): EOD INGESTION DOWN
SINCE 2026-07-02** — Celery worker/beat never ran in the v2 era;
ohlcv_1d (+ FII/DII etc.) frozen at 07-02; the 07-15/16 soaks'
prev-day trigger levels came from 07-02 dailies; screener read
2-week-old state. **✅ RESOLVED 2026-07-18** — root-cause fix: EOD
beat tasks are now SELF-HEALING (services/eod_catchup.py heals every
missing session ≤21d lookback, interior holes included); `make worker`
added (celery worker -B, part of the daily ritual — stop it during
soaks; missed evenings heal on the next run). Backfill EXECUTED
07-03→07-17: ohlcv_1d 11/11 sessions (~2,030–2,046 rows/day),
fo_bhavcopy 11/11 (~33–38k rows/day), india_vix_daily 11/11; CA sweep
quarantined 4 corporate actions from the gap (KRISHANA+MBAPL ≈5:1
splits 07-03, MWL ≈10:1 07-10, GOLDIAM ≈4:3 bonus 07-10 — pending
review). FII/DII: live NSE endpoint serves ONLY the latest day and a
FLAT shape the old parser didn't know (parsed to zero records
forever) — parser fixed (+regression test), 07-17 captured; 07-02→
07-16 permanently unavailable from this source (historical fetcher =
Phase 4, factor scores missing days as zero by design). Full detail:
phase-03 ledger §EOD restart.

**✅ PROVISIONAL CONFIDENCE + LEADERBOARDS — DONE 2026-07-18 (ledger
§Provisional confidence + leaderboards): SLICE 3.5 IS NOW COMPLETE.**
Refresher-thread batch rescore per the pinned design (frozen scorer on
the forming-appended window canon; convergence to the committed score
pinned by test); `LiveBook` frozen+Mutex with a `forming_snapshot` FFI
getter (GIL-released, deadlock-impossible lock scoping); per-style
leaderboards SET(TTL)+PUBLISH with signal rows never clipped;
`subscribe_provisional` WS fanout + REST reconciliation + dashboard
ProvisionalPanel (provisional-labelled end-to-end). +21 backend / +12
frontend tests, all real seams (incl. run_cycle e2e through the real
tradecore book). Worker thread behind `live_provisional_enabled`.

**✅ SLICE 3.6 OUTCOME TICKS — DONE 2026-07-19 (@fc50483; ledger
§Outcome ticks + §Reviews outcome ticks).** Direction-aware SL/TP touch
cross levels joined the trigger set (BUY: SL=cross_down/TP=cross_up;
SELL mirrored; outcome truth = touch, not proximity); `signal_outcomes`
replaced with the tick-level first-touch schema (monotonic ladder open →
entry_touched → tp_first/sl_first/expired_*, crash-window upgrades
toward truth; reversible migration `s5t6u7v8w9x0` up→down→up proven; the
v1 EOD shape was dead — 0 rows, no code); durable alerts-stream
consumer-group recorder in the worker (ack-after-commit, PEL crash
recovery, per-entry SAVEPOINT poison isolation, behind
`live_outcome_recorder_enabled`); expiry sweeper finalizes lapsed
signals each 5-min beat (epoch-floored); REST /signals/{id}/outcome +
SignalDetailModal Outcome strip. Reviews: bug-hunter 2 MEDIUM + 3 LOW
fixed; quant-verifier HIGH (redelivery reorder) fixed + gap-through-SL/
at-level limits documented with a **user ruling QUEUED (§Decisions)**.
Gate 829/16/9 backend + 177 frontend. Observability only — never feeds
scoring/sizing/gating/backtests.

**✅ SLICE 3.7 SHADOW-COMPARE HARNESS — DONE 2026-07-19 (@25011bb;
ledger §Shadow compare + §Reviews).** `app/services/shadow_compare.py`
re-scores each committed 1d close under BOTH engines through the one
`score_signal` (explicit `impl=` — no global toggle, no reimplementation)
and reports decision/direction/confidence diffs; EOD sweep over raw
`is_active` (== nightly), per-stock error isolation. `scripts/
shadow_week.py --day` writes a gitignored report, exits nonzero on any
diff/error. SCOPE = base flow-free 1d decision (excluded flows stamped;
frozen Python not deletable until flows reach tradecore). EXECUTED
07-17 vs real DB: 2,293/2,293 matched exactly, 73 emitted signals all
agreeing. quant-verifier + bug-hunter both fixed (toggle race removed).
Gate 840/16/9 + 177 frontend.

**▶ NEXT ACTION = SLICE 3.7 LIVE RUN — LIVE-GATED (needs market days,
cannot run overnight):** (1) SHADOW WEEK — run `scripts/shadow_day.sh
<day…>` (wrapper over `shadow_week.py`, appends PASS/FAIL to
`backend/shadow/shadow_week.log`) once per day AFTER the evening EOD
beats land the close (~19:30 IST — equities EOD 18:40, nightly 19:15;
4:30 PM is too early, the bar isn't ingested yet); zero diffs required
(day-one 07-17 already clean). A gap can be caught up in one evening —
the EOD catch-up heals the backlog, then run the wrapper across the
backfilled days. (2) full-session SOAK — already MET ×2 (07-15/16).
(3) the 30-day paper clock STARTS at 3.7 (starts when `make live-worker`
runs the live path). Then the Phase-3 exit gate (`/phase-gate`).
Pre-open ritual: start `make worker` (from repo ROOT, not backend/)
before 18:30 IST so the evening beats self-heal + generate; then
`make live-worker WORKER_ARGS=--gap-fill` pre-open (its own gap-fill
heals the intraday hole for the subscribed universe — no
`backfill_intraday.py` needed). Watch the provisional cadence (overrun =
tune `live_provisional_refresh_s`/hotset cap) and the outcome recorder
(`XPENDING alerts:live outcome-recorder` ~0). **User rulings CLEARED
2026-07-23 (§Decisions, both RULED):** outcome-tick gap-through-SL =
(a) now + (c) Phase 6; the 4 CA quarantines = keep flagged, re-inclusion
folded into the Phase-4/6 adjusted-history migration.

Open threads, in order:
1. **FIRST SOAK RAN 2026-07-10 — PARTIAL; latency verdict OPEN** (full
   honest record: phase-03 ledger §First soak session). Clean hour:
   1.33M ticks / 125,606 candles / 0 skipped; then a self-inflicted
   load-63 incident (pytest+builds on the soak box) starved the consumer
   and Kite dropped the WS; a 4-hour session-limit freeze followed
   (worker down 11:41–15:29). Crash-restart, drain-and-record, and the
   GREATEST-volume merge all behaved as designed; two-header recording
   replayed and pinned (digest in the ledger; replay committed-count ≡
   live exactly). **Re-run a QUIET-BOX soak next trading day for the
   p99 < 10 ms verdict** — same ritual as before, plus: NOTHING heavy on
   the box market-open→close (no pytest/cargo/maturin), don't start the
   backend API while the worker runs, and run the worker via
   **`make live-worker`** (supervisor target, built + smoked
   2026-07-10: exit 0 breaks — never restart-loops after close; exit 4
   waits 60s with the login-ritual prompt; anything else restarts after
   5s; `WORKER_ARGS=--gap-fill` passes through, LIVE_RECORD_PATH via
   env). The smoke also live-validated the 3.5 level pipeline:
   2,049/2,049 stocks' trigger levels applied through the real DB → FFI
   with zero rejections. Perf state: publish-path fixes AND both LOW
   hardening items are applied and full-gate-validated — the soak now
   measures the fixed path; pin the NEW-format shutdown stats line
   (dwell/processing split + avg batch size) in the ledger, and recall
   the audit caveat: at true 2,049-tick full batches the un-gateable
   LTP SET floor (~11 ms) still brushes the budget — restate the
   budget at soak scale or add unchanged-price SET dedupe, decided on
   the soak's numbers.
   **Data incident RESOLVED same evening** (ledger §post-close
   forensics): the v1 consumer wrote off-canon candles TWICE (zombie
   09:56–11:06; drowning 13:01→close restart) and resume-point gap-fill
   couldn't heal the midday holes. User-approved delete + full-day
   rebuild from Kite REST executed and VERIFIED: 5m 75/75, 15m 25/25,
   1h 7/7 canon buckets, zero off-canon, 1,880–2,031 stocks per bucket
   (evidence kept in `forensic_ohlcv_{1m,5m,15m,1h}_20260710`).
   **v1-consumer auto-start REMOVED from `app/main.py` lifespan**
   (canary test proven to fail on the old code); the consumer now
   starts ONLY via `POST /broker/kite/consumer/start` — never while the
   worker runs. The quiet-box soak is UNBLOCKED.
2. **Slice 3.5 CORE DONE + MERGED 2026-07-10** (`main` at `70df694`;
   built on branch `slice-3.5-tick-triggers`). Rust trigger engine +
   replayable "lv" level lines + live_levels.py sources + alerts:live
   stream + /ws/live subscribe_alerts fanout; Rust 55 tests, +25
   backend tests; 3.4 golden digest untouched. Reviews: quant-verifier
   FAIL→fixed + bug-hunter BUGS-FOUND→fixed (dup S/R ids HIGH confirmed
   by executed repros both sides; consumer-ack mark_sent; details in
   the ledger §Reviews 3.5); suite 727 green post-fix; `make
   engine-build` run in main (set_levels FFI live).
   **Still open within 3.5:** ONLY forming-candle provisional
   confidence + per-style leaderboards — design DECIDED 2026-07-11
   (ledger §Decisions: throttled batch rescore of a bounded hot set;
   implementation after the soak). Alert UI DONE 2026-07-11 (§Alert
   UI); watchlists + watchlist-scoped fanout DONE 2026-07-11
   (§Watchlists — bug-hunter MEDIUM fixed with executed repro). Then
   3.6 outcome ticks, 3.7 shadow week + full-session soak (30-day
   paper clock).
3. **Tailwind v4 token-class migration — ✅ DONE 2026-07-11 (same
   session it was discovered):** all 898 broken `[--color-x]` sites
   (46 files) converted to the v4 `(--color-x)` form; verified in
   headless Chrome across all five themes (opaque theme-distinct
   surfaces — previously rgba(0,0,0,0) everywhere; `/20` opacity
   modifiers compile per theme; zero console errors; daybreak renders
   as a true light theme for the first time). Riders: dashboard
   dup-key warning fixed (two "" action columns in the static header
   array → positional keys), StocksPage filter badge → accent-bg/accent
   AA pair, Popover aria-expanded/haspopup. Still deferred to a future
   UI pass (ledger §Alert UI): raw-button topbar chrome + 44px targets,
   Popover focus management, daybreak warning-token contrast, aria-live
   status rows.
4. **Session-ops knowledge (this machine):** single-process `make test`
   OOM-killed twice at the gainer golden under desktop load (Chrome+IDE,
   15GB) — run the gate as three fresh legs instead:
   `pytest -m "not parity and not walkforward"` · `-m parity` ·
   `-m walkforward` (sequential, never concurrent — shared test DB).
   Background shells: poll every ~5 min (log growth + `[b]racket`-trick
   process check); pgrep/pkill -f patterns must NEVER appear in their
   own command line (two self-match incidents on 2026-07-09/10).
5. **Profile tuning** (dc1/dc2/multibagger negative; intraday trio
   flagged) — Phase 6 workflow; verdicts pinned in goldens. Wiring
   session context (3.0) was necessary, not sufficient, for activation.
6. Latent LOW calendar items in the phase-02 report backlog (UTC-date
   trading-day walks; `same_day` weekend validity); Muhurat/special-hours
   sessions unsupported by the worker's standard 09:15–15:30 SessionSpec
   (documented, accepted until the calendar carries session hours).
7. `git push` remains manual (credential-free remote by design).

Daily ops: Kite token dies ~6:00 AM IST; ritual =
`cd backend && uv run python scripts/kite_login.py` (terminal-only).
Chain recorder auto-activates while a token is live.

Phase-2 state (closed 2026-07-07): report
`phases/phase-02-strategy-profiles.md`; walk-forward verdicts — rrbo
POSITIVE (+41.3%/+1.97); dc1/dc2/multibagger FLAGGED; intraday trio
FLAGGED (gainer_925 +56.2% AFTER the 8c-4 look-ahead purge). All 8
goldens replay in `make walkforward`.

Phase-1 state (closed): F/G/H applied 2026-07-05, canon table in
ARCHITECTURE.md; standing baseline 599 trades / +52.1% / sharpe +0.13 on
the pinned 2y×49 corpus.

**Decision gates (unchanged in spirit from v1):**
- End Phase 1: parity green or no cutover.
- End Phase 2: every profile shows documented expectancy (or is flagged) before realtime work.
- End Phase 3: full-session soak clean before F&O/UI build on top. 30-day paper clock starts here.
- Before Phase 7 live pilot: 30 profitable paper days with discipline, static IP, kill-switch tested.

**Zerodha API:** not needed for Phases 0–2 (NSE public data + existing DB).
Nice-to-have from Phase 2 (historical intraday backfill). **Required at
Phase 3 start.** The chain-snapshot recorder (built in Phase 0) activates
automatically once a token exists.

---

## v1 build-out (complete — kept for history)

| # | Phase | Status |
|---|-------|--------|
| 0 | Infrastructure (docker compose: Timescale+Redis) | ✅ |
| 1 | Auth & user master (JWT, rotation, admin-only creation) | ✅ |
| 2 | Stock master + 50-filter screener + saved screens | ✅ |
| 3 | Categories master (M2M tagging) | ✅ |
| 4 | EOD ingestion (5y OHLCV, FII/DII, bulk/block deals) | ✅ |
| 5 | Signal engine offline (14 factors, confluence ≥70%, backtest harness) | ✅ |
| 6 | Dashboard v1 + corporate filings feed + event guard | ✅ |
| 7 | Live data via Kite WS (unit-tested; end-to-end defects repaired in v2 Phase 0) | ✅* |
| 8 | Paper trading (positions, trail SL, circuit breaker) | ✅ |
| 9 | Strategy lab (grid search, presets, equity curves) | ✅ |
| 10 | Trading journal (auto-populate, emotions, screenshots) | ✅ |
| 11 | External portfolio (CAMS CAS import, net worth) | ✅ |
| 12 | Live trading | → became v2 Phase 7 |

\* v1 Phase 7 shipped with four integration defects that made the live path
inoperable end-to-end (documented in UPGRADE_PLAN.md and repaired, with
regression tests, in v2 Phase 0 — see `docs/phases/phase-00-workbench.md`).

## Architecture-review backlog (2026-08-01) — phase-mapped

From the external-review synthesis
(`~/Downloads/ARCHITECTURE_RECOMMENDATIONS.md`), each item fit-checked
against the code (the code is ground truth). **Done now (2026-08-01):** the
honest-fill program that was current-stage-relevant and invariant-safe —
**P0.3 gap-through-stop** (paper SL exits book the gapped market, not the
stop), **adverse slippage on** (`paper_slippage_bps` default 0→2 bps), and a
**paper-clock reset** (`users.paper_clock_started_at` + `POST
/trading/paper-clock/reset` + card button) so the 30-day count restarts under
one consistent fill model. See CHANGELOG 2026-08-01. Everything else maps to an
existing planned phase and is recorded
here so it is not lost. The reframing finding: **live trading does not exist
yet** (`place_order` is paper-only, no Kite order/GTT path), so every "live"
recommendation is a Phase-7 design constraint, not a now-fix.

**Phase 6 (outcome tracking + calibration):**
- Empirical regime-conditional **expectancy tables** (confidence-bucket × class
  × ADX/market regime → resolved TP-first %, avg R, sample size) from the
  outcome recorder — **CALIBRATION ONLY, never auto-adapting weights** (the
  frozen-and-adjudicated discipline holds). Data not yet ripe (outcome epoch
  2026-07-19). Then let expectancy — not raw confluence — inform sizing, and
  **replace the "30 calendar days profitable" go-live gate** with "N trades
  across ≥2 regimes, positive expectancy, bounded max drawdown" (the current
  gate is display-only today; `schemas/user.py` deliberately omits
  `trading_mode` from updates). (review P1.1)
- **Signal-level MFE/MAE** in the outcome recorder. Position-level MFE already
  exists (`positions.peak_price`/`peak_pnl`); MAE and signal-level (all
  signals, not just taken trades) do not. (review P1.2)
- **PKScreener setup-catalog harvest** — VCP / NR7 / momentum / delivery
  setups as *candidate factors* for the confluence scorer (never standalone,
  gated ≥70%, §8 backtest required). Idea list only; see
  `docs/EXTERNAL_LIBS_REVIEW_2026-08-02.md`.
- **MoneyControl scan-catalog harvest** (same effort as PKScreener above) —
  ~20 named technical + fundamental scans transcribed with formulas in
  `docs/COMPETITOR_TOOLS_REVIEW_2026-08-11.md` §3, to become `SavedScreen` /
  `STARTER_SCREENS`. **Discovery/sieve only, upstream of the ≥70% gate — never
  a signal.** Technical scans need the screener to expose indicator/price fields
  (today's `rsi_14`/`price_vs_ema50`/`fii_net_5d_cr` are `available=False`
  stubs; data we already ingest, medium lift). Fundamental scans are blocked on
  the fundamentals layer (see Market Context Engine below — every one thresholds
  on `MarketCap`, which has no writer today).
- **Pair-trading / market-neutral profile candidate** (Varsity Trading Systems —
  `docs/VARSITY_REVIEW_2026-08-12.md` §1.3) — cointegration-screened
  (correlation → linear regression → ADF) market-neutral entries. **Regime-agnostic:
  the one new idea from the 2026-08 external study that directly attacks the
  choppy-tape problem** where our directional profiles give profit back (LEDGER
  0–1/5 reaching 1R). A NEW profile inside the confluence framework, shadow-first,
  §8 backtest required — never a bypass of the ≥70% gate. Highest-value new candidate.
- **Cross-sectional momentum ranking** (Varsity Trading Systems) — rank the
  universe by momentum as a sieve/discovery lever, upstream of the gate. Lower
  priority than pair-trading.
- **Kronos (post-Phase-6, research-track only)** — an OHLCV foundation-model
  *confidence input* experiment, gated-input-only, measured against the
  Phase-6 outcome baseline; never a direction generator, never in the live
  path. Deferred per the "AI/ML only after the rule engine proves out" policy
  (see external-libs review §4).
- **FinNifty→BankNifty lead-lag (post-Phase-6, research-track only)** — the
  masterclass "data hack" that Bank Nifty ≈ 70% CNX Finance; test FinNifty as a
  leading confluence INPUT for Bank Nifty option signals, §8-gated, never a
  standalone direction generator. See `docs/TRADING_MASTERCLASS_REVIEW_2026-08-12.md` §3.

**Market Context Engine (named phase after Phase 6 — see auto-memory):**
- **Proactive pre-event (earnings) blackout** — suppress new signals N trading
  days before a known results/event date, scaled by class. Needs a forward
  earnings/event-calendar source; today's `event_guard` is reactive
  (post-filing 60 min) only. (review P1.4)
- **One simple top-down market/sector gate** — suppress/downweight longs when
  NIFTY is below its 200-DMA or India VIX is high, plus a sector-RS check on
  existing sector metadata. Behaviour-changing → needs a §8 backtest.
  **NOT** a multi-state regime engine. (review P2.1)
- **Fundamental data layer + quality scores** (from the 2026-08-11 competitor
  review — `docs/COMPETITOR_TOOLS_REVIEW_2026-08-11.md` §4–5). New
  `stock_fundamentals` table (ratios + latest statements + quarterly
  shareholding) feeding a fundamental **gate/modifier** and the four closed-form
  quality scores (Altman Z / DuPont / Graham / Ohlson — greenfield, no
  look-ahead). **Blocked on a data-source decision:** NSE publishes no free
  shares-outstanding feed, so `market_cap_cr` has never been populated — it is
  the keystone unlock (the existing screener's headline numeric filter *and*
  every fundamental scan threshold on it). Candidate sources: BSE/NSE XBRL
  results (extend `filings_consumer`) vs a paid fundamentals API. Never additive;
  §8 backtest before any behaviour change. **Authoritative computation reference:**
  Zerodha Varsity Fundamental Analysis + Integrated Financial Modelling
  (`docs/VARSITY_REVIEW_2026-08-12.md` §1.1) — real ratio analysis + DCF. The
  masterclass `FV = BookValue × 10` heuristic is REJECTED (arbitrary, not a
  valuation); its promoter>35% / pledge<10% rules are valid scan thresholds.
- **Per-stock seasonality flag** — monthly return distribution over the existing
  5y EOD OHLCV (e.g. "seasonally weak in August, n=18") as a soft context
  modifier. **The one piece needing no new data or engine change** — cheap,
  genuinely new; report n and refuse to rank thin samples.

**Phase 7 (live-trading hardening — opens with the RiskEngine slice):**
- **Exchange-resident protective stops (Kite GTT / SL-M)** as the primary live
  exit; the position monitor becomes a supervisor/reconciler, and each trail
  ratchet becomes a MODIFY of the exchange-side order. (review P0.1)
- **LTP-absence alarm** for an open live position (loud, matching the
  "dead consumer is loud" culture); in live, the exchange stop covers the
  process's blind window. The paper monitor currently skips silently on absent
  LTP. (review P0.2)
- **Sector-exposure caps + a single total-open-risk (exposure heat) number** —
  simple caps in the RiskEngine gate. **NOT** VaR/ES, **NOT** a rolling
  correlation matrix. (review P2.2) *(Varsity Risk Management M9 teaches Kelly /
  VaR / correlation-aware portfolio variance — `docs/VARSITY_REVIEW_2026-08-12.md`
  §1.4; deliberately NOT adopted here — simple caps chosen. Revisit only if simple
  caps prove insufficient, never as a first build.)*
- **Defined-risk option-selling profile (Iron Condor) — the ONLY sanctioned form
  of the masterclass "passive income" short strangle.** Sell ATM CE+PE but BUY
  protective wings → same theta harvest, BOUNDED max loss (Varsity Option
  Strategies — `docs/VARSITY_REVIEW_2026-08-12.md` §1.2). The naked short strangle
  as taught is REJECTED (uncapped tail / gap risk). Requires the live options
  order path (this phase), paper-first, event-day blackout, the never-disableable
  daily-loss breaker, and a §8 backtest incl. gap-through-SL. Detail in
  `docs/TRADING_MASTERCLASS_REVIEW_2026-08-12.md` §4.
- **Corporate-action adjustment of OPEN positions** through an ex-date
  (entry/SL/TP/qty, so R is preserved). CA quarantine currently covers the
  selection universe only, not held positions. (review P1.5)
- **Fill-model reference (LEAN / Nautilus §4)** when building the execution
  handler — a catalog to consult for realistic paper/live fill behaviour, not
  a dependency. See `docs/EXTERNAL_LIBS_REVIEW_2026-08-02.md` §3 (LEAN).

**Optional test hardening (any time):** exact-boundary parity fixtures
straddling confidence 69/70 and ADX 19/20/40/41. The Python↔Rust ADX-regime
logic is already textually identical (`confluence.rs` ≡ `confluence.py`; the
`+5`/`−5` lands on the *threshold*, not the score, after `int()` truncation),
so this only hardens the float-comparison edge (already bounded by the 1e-6
Wilder tolerance). Low value, cheap. (review P1.3)

**Rejected — verified against this system:** auto-adaptive/self-learning
weights (curve-fits; breaks frozen-engine discipline) · VaR/Expected Shortfall
· execution algos (VWAP/TWAP/iceberg — irrelevant at this size) · rolling
correlation matrix · factor family-capping (already tested & rejected
2026-07-05 item H: ~400 weak trades, crushed total P&L). (review "Do NOT build")

## Consciously deferred (unchanged)

Mobile native app · Account Aggregator integration · AI/ML signal
generation (only after the rule-based engine proves out) · multi-tenancy /
SaaS hardening · MCX commodities. FinBERT sentiment stays deferred
(column exists, never populated).
