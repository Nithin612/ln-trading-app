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
| **D1** | Sign-off to touch the frozen engine for R1 | Q2.2 |
| **D2** | R2 weekly spread-width gate — build or drop | Q2.3 |
| **D3** | MCE 5b market-cap **vendor** | Q3.1 |
| **D4** | Concentration/sizing — is the notional cap enough? | Q3.4 |
| **D5** | `compute_levels` payoff geometry — fix, or consciously keep a tourniquet | Q3.5 |

### Q1 — Phase 7.1–7.4 — **the long pole, fully unblocked, starts now**

| # | slice | content |
|---|---|---|
| **7.0** ✅ **DONE 2026-09-06** | **Design pass first** | A33 OMS-as-projection-of-the-event-stream + A42 frozen/available cash + A35 `BrokerAdapter` interface, designed **together** — the review found these are one problem, not three |
| **7.1** ✅ **DONE 2026-09-06** | RiskEngine single-gate | one pre-trade gate absorbing: daily-loss circuit breaker · the 6 eligibility overlays · notional cap · R:R floor · **the heat cap** (fails CLOSED, `heat = qty × max(0, entry − commit_SL)`, initial risk not MTM). **Equivalence-pinned first** — identical verdicts to today's chain before any refactor |
| **7.2** ✅ **DONE 2026-09-07** | BrokerAdapter port | `PaperBrokerAdapter` behind the interface + a **read-only** Kite spike (order-status, margins, positions; **no placement**) so the shape is validated against reality |
| **7.3** ✅ **DONE 2026-09-07** | Order FSM | Denied vs Rejected vs Filled vs Cancelled + A32 event-bus robustness (per-handler isolation, bounded queue, **a dead bus must be loud**) + A22 partial-fill sibling rebalance + A16 lifecycle/repair queue + A34 timer primitive |
| **7.4** | Reconciliation + kill switch + audit | recover local state on restart · kill switch honoured everywhere · every decision reconstructable · T2 lifecycle-boundary tests (first step, start mid-stream, stop early) |

### Q1b — Bucket C slices **pulled forward** (proposed)

Three, on the **same argument that already pulled A11 and A40 out of Bucket C**: *"safe to
ship mid-cycle" answers whether a change will disturb the record — not what protects the
record while it is being made.* Everything else in Bucket C stays under the clock.

| # | item | why it cannot wait |
|---|---|---|
| **1.7.1b** ✅ **DONE 2026-09-06** | **A13** — pin the circuit breaker's **un-suppressibility** | **Rides with 7.1, same commit.** 7.1 refactors the breaker *into* the RiskEngine, which is exactly when a hard constraint can be silently lost. It is enforced today by convention and its call site, not by a test that fails if someone routes around it |
| **1.5** | **A27** — config dry-run | `settings` is an `@lru_cache` singleton, so a `.env` change reaches a running process only on re-import. This has bitten repeatedly — it is why CLAUDE.md carries a whole recipe for verifying a gate's live mode. **The cycle-2 reset is itself a config event** (heat cap → enforce, clock → reset); getting it wrong silently invalidates the *window*, not a day |
| **1.6** | **A3** — broker-token status | The Kite token dies **~6:00 AM IST daily** = 45–50 chances to lapse silently during cycle 2. On lapse the feed stops, `depth:` expires at its 60 s TTL, and spread-aware fills fall back to the flat floor — **paper fills quietly cheaper than reality**. That corrupts the recorded numbers rather than merely interrupting them, which is what makes it a data-quality precondition |

### ▶ Progress — 2026-09-06/07 overnight run

**✅ 7.0 design pass** (`docs/phases/phase-07.0-oms-design.md`) · **✅ 7.1 RiskEngine +
✅ A13** (`app/trading/risk_engine.py`, 33 tests) · **✅ 7.2 BrokerAdapter port**
(`app/broker/adapter.py` + `paper_adapter.py` + a read-only Kite spike, 27 tests) ·
✅ **7.3 DONE** — `order_events` (migration applied + reversible), `order_fsm.py`,
`event_bus.py`, `event_store.py`, and **the order path cut over**: `submitted` is written
BEFORE the gates run, so a decision can no longer fail to be recorded. 42 tests.

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
| **2.1** | **F1 `market_cap` spike** | ready — and it is the input to **D3**, so it runs first |
| **2.2** | **R1 VWAP/RVOL as confluence factors** | ⛔ blocked on **D1**. Frozen engine ⇒ needs §8 regression + regenerated Rust oracle fixtures in the same commit. Changes which signals exist ⇒ **Bucket-A class, must precede the clock** |
| **2.3** | **R2 weekly spread-width gate** | ⛔ blocked on **D2** — *recommend DROP*, see §4 |
| **2.4** | momentum ×1.5 retune | forward route is stalled; needs a **backtest path** to decide at all |
| **2.5** | pair df-vs-adf | accruing nightly — **no build**, just don't lose it |

### Q3 — remaining cycle-2 entry criteria (not named in the ask, but on the checklist)

| # | item | state |
|---|---|---|
| **3.1** | MCE 5b `market_cap` writer + T1 PIT test | ⛔ blocked on **D3** (a vendor decision, not a build task) |
| **3.2** | MCE 6 news veto — Google News RSS + FinBERT | ready |
| **3.3** | CAS Stage 2 — the overnight-reversal study | **unblocked** (Stage 1 closed healthy: 1,664 rows / 8 sessions) |
| **3.4** | Concentration/sizing decision | ⛔ **D4** |
| **3.5** | `compute_levels` payoff geometry | ⛔ **D5** — *the known lever* |
| **3.6** | Minervini trend template | test **or explicitly drop** — the checklist accepts either |

### Q5 — a review-calendar item that came due (⏰ raised unprompted)

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

**(b) R1 is the one item here that attacks the actual leak** — it changes what *generates*
candidates rather than what selects among them, and selection is the part already
demonstrated to be exhausted. That makes it the highest-value item in Q2 **and** the one
needing the most ceremony: hard constraint #1 (protected spec) + §8 regression + oracle
fixture regen.

**(c) The demonstrated lever is D5, and it was not in the ask.** `compute_levels` pairs a
**structural** stop with an **absolute-%** target, so R:R is an accident: **94 of 295 swing
signals have R:R < 1 by construction**, and at a 37.5% win rate the arithmetic needs 1.67R
and cannot close. It is on the cycle-2 entry checklist and it changes a recorded number.

**(d) The backtest models no trading costs at all.** Backtest P&L is **GROSS**, paper is
**NET** (22–62 bps round-trip + the flat ₹15.34 DP charge). Any R1 §8 regression, and Q2.4's
proposed backtest path, will be judged on a gross-cost engine. Treat every backtest
expectancy as an **upper bound** until this is addressed — also frozen-engine territory.

**(e) Heat has drifted to 58.0%** of capital (₹58,034, 29 open positions, 2026-09-04) with
still no portfolio cap. The cap lands in 7.1 and must **not** be set to enforce until cycle
2 — a 6% cap cuts cycle-1 entries ~74% and cycle 1's purpose is evidence volume.

**(f) `main` has not been pushed.** Phase 6 + 6.8 merged fast-forward and are awaiting a
manual push. Push remains the user's (working rule W4).
