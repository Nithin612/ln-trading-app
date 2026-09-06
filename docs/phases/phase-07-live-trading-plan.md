# Phase 7 — Live-trading hardening, and the TWO-CYCLE paper plan

**Status: QUEUED TO BUILD (2026-09-06)** — on branch `feature/pre-cycle2-hardening`, whose
ordered queue is [`pre-cycle2-queue.md`](pre-cycle2-queue.md). **7.1–7.4 are the long pole and
are fully unblocked**, so they start first. ⚠ Per the external review, **7.0 is a DESIGN PASS
before any code**: A33 (OMS as a projection of the event stream) + A42 (frozen/available cash)
+ A35 (the `BrokerAdapter` interface) are **one problem, not three**, and must be designed
together. Buckets A and B — the cycle-2 prerequisites that had to precede this — are COMPLETE.
**✅ 7.0 DESIGN COMPLETE + ✅ 7.1 BUILT (2026-09-06/07) — [`phase-07.0-oms-design.md`](phase-07.0-oms-design.md).**
7.1 shipped as `app/trading/risk_engine.py`: one gate composing breaker → signal existence →
signal status → the A38 eligibility registry, then notional cap → heat cap. **Equivalence-pinned**
against a literal transcription of the pre-7.1 chain, and the pin **caught a real ordering
inversion before it shipped** — the breaker runs before the signal lookup, so an unknown id on a
tripped breaker answers 409, not 404, and the natural "hoist the lookup so `signal` is
non-optional" refactor silently flips that. The **heat cap is BUILT and `off`** until the cycle-2
reset. **A13** rode with it: the breaker runs first, has no disable knob (the test asserts the
*absence*), and still denies with every gate mode forced off. 33 new tests.
Its 7.0 design findings: **a refused order is not a row today, it is an exception**, so the
orders table records only successes and "what did we refuse, and under which thresholds" is not
answerable from data; **`submit()` must return an `Ack`, never a `Fill`**, or paper's synchronous
fill leaks into the interface and the abstraction is met on day 1 of live; and **available cash
is DERIVED from the active-order set, never stored** — a stored balance is a fourth writer to a
truth three tables already own, and it drifts silently.

(The original ruling that 7.1 opens the phase came from the Nautilus review in
`docs/PHASES.md`.) This doc did not exist before 2026-09-02 (the
phase row pointed at "—"); it now also carries the **two-cycle go-live governance** decided
by the user on 2026-09-02.

---

## 1. The governance decision (user, 2026-09-02)

> *"Once we book 30 profit days with the tuning we are doing now and with the upcoming
> phases — CAS, 6.8 pending, other e-books/Nautilus/GitHub-project tuning — then after
> building everything, instead of going live immediately, let's paper trade for the next 30
> days again. Going live can wait another 45 days after the first cycle reset. No point of
> going live without proper paper trading result with better strategy."*

**Two paper cycles, not one.**

| | **Cycle 1 — the sampler (running now)** | **Cycle 2 — the rehearsal** |
|---|---|---|
| purpose | accrue entry/exit/signal evidence FAST | prove the finished system in its live shape |
| book | deliberately wide: ~5 entries/day, ~5-day holds ⇒ **~25 concurrent positions** | disciplined: heat-capped ⇒ **~3–5 concurrent positions** |
| capital shape | each trade sized off ₹1L; the sampler represents ~₹5L | ₹1 lakh, as live will be |
| the 30-day clock | **informational** — it is measuring a book that will never be traded | **binding** — this is the go-live gate |
| length | until the build queue is done | **45–50 trading days** (targeting 30 profitable) |
| ends with | **clock reset** | go-live decision |

**Why the clock had to be re-scoped.** Cycle 1's book is ~25 correlated positions at 45.3%
of the live capital figure. Live is 1–2 positions on ₹1 lakh. Those two books can produce
**opposite signs from identical signals** — the wide one is substantially a bet on market
direction, the narrow one a bet on signal selection. A go-live gate computed from the wide
book is measuring the wrong thing, however green it goes.

**The bridge, already built (2026-09-02):** `app/services/heat_counterfactual.py` replays
every cycle-1 entry against a 6% cap on ₹1 lakh and reports that subset beside the full
book — so cycle 2's book shape can be *measured during cycle 1* without changing any
behaviour. First read (since the 08-17 clock epoch): **admitted 12 / skipped 35; capped
−₹13,303 vs full −₹19,093 (+₹5,790 total) but per-trade −₹1,478 vs −₹796.** Read that
carefully: **the cap is a RISK control, not a profitability fix** — it cuts total loss by
taking fewer trades at an unchanged negative expectancy. Nothing here repairs the
−0.303R/trade problem; only entry quality and payoff geometry can.

---

## 2. Cycle-2 entry criteria

Cycle 2 must rehearse the **finished** system, so it starts only when all of the following
are done. Nothing auto-advances.

**Strategy / evidence**
- [ ] CAS Stage 2 — the overnight-reversal study (Stage 1 accruing; `cas_daily`)
- [ ] MCE slice 5b (`market_cap` writer) and slice 6 (news veto)
- [ ] The deflated-Sharpe / multiple-testing bar **built and applied** — two gates already
      sit at a ✅ READY banner that should not be trusted without it
- [ ] Shadow-gate promotions decided under that bar (`sl_atr` 17/20 is closest)
- [ ] The `compute_levels` payoff-geometry fix, or a conscious decision to keep the R:R
      overlay as the permanent tourniquet (§6 spec change + §8 regression)
- [ ] Reading-derived candidates tested or explicitly dropped (Minervini trend template)

**Runtime (Phase 7 slices — see §3)**
- [x] **7.1 RiskEngine single-gate — DONE 2026-09-06** (equivalence-pinned; heat cap built,
      mode `off` until the cycle-2 reset) · [x] **7.2 BrokerAdapter port — DONE 2026-09-07**
      (`submit()` returns an `Ack`, never a `Fill`; read-only Kite spike shipped) ·
      [x] **7.3 order FSM — DONE 2026-09-07** (`order_events` is the durable record and the
      order path writes `submitted` BEFORE the gates run) · [x] **7.4 reconciliation + kill
      switch — DONE 2026-09-07** (recovery is idempotent; reconciliation reports and never
      repairs, and names what it could not check).
      **▶▶ PHASE 7.1–7.4 COMPLETE — the cycle-2 RUNTIME prerequisite is met.**
- [x] **The portfolio heat cap — BUILT inside the RiskEngine 2026-09-06** (see §4). Ships
      `heat_cap_mode=off`; the remaining step is the FLIP at the cycle-2 reset, not a build.

**Then:** reset the paper clock, set the heat cap to enforce, run 45–50 trading days.

---

## 3. The slice split — by what paper can actually PROVE

The rule: a slice belongs before cycle 2 if a paper adapter genuinely exercises it, and
after cycle 2 if only a real broker can validate it. Simulating a broker behaviour is a
*modelling choice*, and 6.8.2 taught us how much modelling quality matters (82% of live
NSE books were wider than the flat 2 bps we had been assuming).

### Before cycle 2 — paper exercises these for real

| slice | content | what cycle 2 proves about it |
|---|---|---|
| **7.1 RiskEngine single-gate** | one pre-trade gate replacing today's scatter: circuit breaker + the 6 eligibility overlays + notional cap + R:R floor + heat cap. Test-first, **equivalence-pinned** (identical verdicts to today's chain before anything is refactored) | 45 days of every rejection path firing on real signals |
| **7.2 BrokerAdapter port** | the interface a `KiteBrokerAdapter` will implement, with `PaperBrokerAdapter` behind it | the abstraction survives a full cycle instead of being met on day 1 of live |
| **7.3 Order FSM** | Denied vs Rejected vs Filled vs Cancelled state machine (the Nautilus distinction) | paper generates all of these states naturally |
| **7.4 Reconciliation + kill switch + audit trail** | recover local state on restart; kill switch honoured everywhere; every decision reconstructable | restart the worker mid-session repeatedly across 45 days |

**Why this ordering is not optional.** `.claude/rules/testing.md`: *"453 green tests once
coexisted with a dead live pipeline: test the SEAMS, not just the units."* A cycle-2
rehearsal running through the real ExecutionEngine gives the plumbing **45 days of runtime
hours with fake money**. The same rehearsal on today's `place_paper_order` proves the
strategy and leaves the plumbing at **zero** runtime hours — and v1 Phase 7's four
integration defects were *exactly* plumbing.

### After cycle 2 — only reality validates these

Kite order placement · GTT semantics · genuine partial fills and broker-side rejections ·
reconciliation against an actual broker book · access-token lifecycle *under live orders*.

**Risk + mitigation.** Designing the BrokerAdapter interface purely from the Kite docs,
having never called Kite, risks getting its shape wrong and discovering that on live day 1.
Mitigation: during 7.2 run a **read-only** Kite spike — order-status, margins, positions
endpoints; **no order placement** — to validate the interface against reality cheaply.

---

## 4. Where the heat cap lands, and why not sooner

The portfolio heat cap is **designed** (see the design in the 2026-09-02 session and
`heat_counterfactual.py`'s docstring) but deliberately **not built yet**:

- Its natural home is 7.1's RiskEngine, next to the notional cap and the R:R floor — which
  are currently scattered across `api/v1/trading.py` and `broker/paper_broker.py`. Building
  it now means retrofitting it into the RiskEngine later.
- It must **not** throttle cycle 1: the sampler's whole purpose is evidence volume, and a 6%
  cap cuts entries by ~74%.
- The counterfactual already answers the question a cap would answer, with no behaviour
  change. There is nothing to learn from enforcing early.

Definition when it lands (Elder/Tharp formulation):

    heat_i = qty × max(0, entry − commit_SL)     (long; mirror for a short)

Clamped at zero (a stop past entry exposes nothing and must not hold budget); **initial**
risk not mark-to-market (a from-the-mark definition *loosens* as the book deteriorates,
which is perverse for a risk cap); admission risk from the **commit** stop, never the
trailed `current_sl` (that leaks price action the decision could not see).

**It fails CLOSED** — a deliberate departure from the six selection overlays. For a
selection gate the error to avoid is suppressing a good trade on uncertainty; for a risk
rail it is *taking risk you cannot measure*. Same logic as the non-disableable daily-loss
breaker.

---

## 5. Go-live criteria (unchanged in spirit, sharpened in scope)

1. 30 profitable paper days **within cycle 2** — the disciplined, ₹1 lakh, heat-capped book.
2. Explicit user opt-in (`trading_mode`), enforced in code.
3. The daily-loss circuit breaker non-disableable — not for tests, not on request.
4. Live starts at **₹1 lakh, 1–2 positions**, per the recorded capital plan.

**Honest timeline.** Cycle 2 alone is 45–50 trading days ≈ **9–10 weeks**, and Phase 7.1–7.4
plus the strategy queue precede it. Live is realistically **4–6 months out**. That is the
direct consequence of the user's ruling, and the ruling is right: *"no point of going live
without proper paper trading result with better strategy."*
