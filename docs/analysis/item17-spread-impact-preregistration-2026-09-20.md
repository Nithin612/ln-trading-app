# Item 17 — spread and impact, pre-registered before measurement

**Written 2026-09-20, before any estimator was run.** This document exists so the falsifier
cannot be rewritten after seeing the number. It follows the discipline that made item 19's
retirement defensible: the criterion is published first, and the measurement is run against it.

---

## 1. Why this is the first measurement of the successor programme

The daily-swing scorer retired on 2026-09-20 (`RETIREMENT-2026-09-20.md`). The open problem is a
**successor generator**, and the direction chosen on 2026-09-20 is the **intraday / MIS product
class** rather than another daily-swing feature.

The reason is cost arithmetic, computed from our own `fees.roundtrip_charges`:

| product | ₹20k position | ₹1L position |
|---|--:|--:|
| delivery | **29.89 bps** | 23.76 bps |
| intraday | **10.60 bps** | 8.24 bps |

Delivery's hurdle *rises* as capital is split, because the ₹15.34 DP charge is flat per delivery
sell; intraday has no DP charge and is flat in breadth. That dissolves the concentration-vs-breadth
tension the external panel named as the real strategic problem.

⛔ **But the pitch contains a trap that this document exists to state before it is measured.**
**Spread is NOT a differentiator between the two products.** Delivery pays the same spread on the
same stock at the same size. The 19 bps advantage above is a *charges* advantage and it is real
regardless of what the spread turns out to be.

⭐ **What spread actually decides is whether intraday's ABSOLUTE hurdle is reachable.** An intraday
trade must clear its whole round trip inside one session, and intraday price moves are smaller than
multi-day moves. So the binding question is the *level*:

> **intraday round-trip hurdle = charges + 2 × half-spread + impact**

At a 5 bps half-spread that is ≈ 20.6 bps (0.21% per trade). At 25 bps it is ≈ 60.6 bps (0.61% per
trade) — and an intraday generator would have to find six tenths of a percent of edge per trade,
before being right about anything. **That is the difference between a programme worth starting and
one that is arithmetically closed before it begins.**

---

## 2. What is being measured, and what is NOT available

⛔⛔ **There is no historical ground truth for spread anywhere in this system, and this was
verified rather than assumed:**

- `depth:{stock_id}` is **Redis-only, 60 s TTL, never persisted** (`app/broker/depth.py:39`).
- The 330 MB soak recording `recordings/soak-2026-07-13.jsonl` (4,850,973 lines) carries ticks as
  `{"k":"t","sid","ts","p","dv","q"}` — **price, day volume, quantity. The book was stripped by the
  recorder.** Checked directly; it is not a ground-truth source.
- No table stores quotes or depth (46 tables enumerated).

⇒ Item 17 therefore has **two arms, and only one of them can run today.**

### 17a — retrospective estimate from bars (runs now)

Effective half-spread **estimated** from OHLC bars by published estimators, across the test block.

### 17b — forward ground truth (real-time only, cannot be back-filled)

Persisted top-of-book samples from the live feed. This is the arm that **validates 17a**, and it
accrues only while `live_worker` is up on market days — the same property that made `cas_daily`
unrecoverable when it was lost. It is specified here so that 17a's result is never mistaken for a
measurement of reality.

⚠ **17a is an estimator. Until 17b exists, every number from 17a carries that tag.**

---

## 3. Estimators — two, independent, both validated against a planted spread

| estimator | source | why it is here |
|---|---|---|
| **Corwin–Schultz** high–low | Corwin & Schultz (2012) | the standard when quotes are unavailable |
| **Abdi–Ranaldo** close–high–low | Abdi & Ranaldo (2017) | independent construction; more robust to volatility |

⭐ **Two estimators are specified because agreement is evidence and disagreement is information.**
A single estimator that cannot be checked against anything is exactly the instrument this project
has been burned by.

⚠ **Known bias, stated in advance:** both conflate spread with volatility; Corwin–Schultz is
documented to be biased **upward** when volatility is high. ⇒ **a HIGH reading is the weaker
result** (it may be volatility, not spread) **and a LOW reading is the stronger one** (volatility
bias cannot manufacture a small spread). This asymmetry is pre-registered because it determines how
each branch of §5 should be read.

### Instrument validation — required, and it gates the result

Per `instrument_self_validation`: an instrument never run against a known answer has not been
validated. Before the real measurement:

1. **Planted spread** — synthetic bars generated from a diffusion with a KNOWN half-spread. Each
   estimator must recover it. **The number must MOVE with the planted value**, not merely "not
   raise" (the M64 lesson: a metric blind to the failure it reports is worthless).
2. **Zero-spread null** — synthetic bars with no spread must return ≈ 0, not a positive artifact.

⛔ **If an estimator fails either check, its numbers are not reported as spread.**

---

## 4. Cohort and sample — pinned, point-in-time, stated before the run

- **Bars:** `ohlcv_5m`, which covers **2023-07-03 → 2026-09-18, 797 sessions** — *exactly* the item-5
  test block. ⭐ **Both sealed holdouts (617 + 313 sessions) stay shut**; nothing here opens them.
- **Cohort:** point-in-time via `app/services/pit_cohort.liquid_as_of`, intersected with the names
  that actually have 5m bars that session. ⭐ **The intersection size is an OUTPUT, reported per
  session, never assumed** — the 5m table's median is **208 names/session** (min 201, max 2,301),
  so the tradable intraday cohort is far narrower than the 2,292-name active universe and the
  headline must say which population it describes.
- ⛔ **No live query defines the cohort** (the M62 / item-6 lesson: a cohort from a live query
  against mutable state is a timestamp, not a cohort).
- **Pairs are formed within a session only** — never across the overnight boundary.
- **Corporate actions** excluded via the authority cache (`nse_corporate_actions`), not a % screen.

---

## 5. ⭐⭐ THE FALSIFIER AND THE DECISION TREE — written before the number exists

The queue's stated falsifier is *"median half-spread on the tradability-screened subset < 5 bps ⇒
not binding"*. Made precise, and extended to a full tree so no outcome is undefined (the Q30
lesson — an undefined middle is how a decision rule gets rewritten after the fact):

Let **h** = median estimated half-spread, in bps, over the screened cohort, and let the implied
hurdle be **H = 10.60 + 2h** bps at a ₹20k intraday position (charges from `fees.roundtrip_charges`,
impact added separately where measurable).

| branch | condition | verdict |
|---|---|---|
| **A** | **h < 5 bps** (H < 20.6) | **NOT BINDING.** Spread does not close the intraday thesis. Proceed to design a successor generator for this product class. |
| **B** | **5 ≤ h < 15 bps** (20.6 ≤ H < 40.6) | **BINDING BUT NOT FATAL.** Proceed *only* with the hurdle carried as an explicit design constraint: the generator must target moves of **at least 3 × H**, and that target is pre-registered before it is built. |
| **C** | **h ≥ 15 bps** (H ≥ 40.6) | ⛔ **REFUTED AT THIS COHORT AND SIZE.** An intraday generator would need >0.6% of edge per trade net of being right. **Do not build one.** Re-scope to a larger-notional / narrower cohort and re-measure, or abandon the intraday direction. |

⭐ **Break-even is carried as an INTERVAL, not a point** — the standing carry-forward from the
retirement. Each branch is evaluated on the **bound that is unfavourable to proceeding**: branch A
requires the *upper* bound of h's interval to sit below 5 bps, not merely the point estimate.

⚠ **The volatility-bias asymmetry of §3 applies to the tree:** branch C reached on
Corwin–Schultz alone, with Abdi–Ranaldo disagreeing downward, is **not** a refutation — it is a
signal that the estimator is reading volatility. Branch C requires **both** estimators.

### What would invalidate this measurement entirely

- Either estimator failing its planted-spread validation.
- The screened cohort resolving to fewer than 30 names on a typical session (too thin to describe a
  tradable population).
- 17b, when it exists, disagreeing with 17a by more than a factor of two — in which case **17a is
  withdrawn, not adjusted.**

---

## 6. What this is not

⚠ This measures **cost**, not edge. A favourable answer does not mean an intraday strategy exists;
it means the arithmetic does not forbid one. The generator, and its own pre-registered estimand,
come after — and nothing in this document licenses skipping that step.

⛔ **No money-path change, no frozen-engine change, read-only throughout.**

---

# AMENDMENT 1 — 2026-09-20, after instrument validation, BEFORE any real data

⭐ **Recorded as an amendment rather than folded into §3, because changing an instrument
after pre-registering it is exactly the move that destroys a pre-registration's value.**
What makes this one legitimate is the ordering and the provision: §3 already said *"if an
estimator fails either check, its numbers are not reported as spread"*, and the validation
ran against synthetic data only. **No `ohlcv_5m` row had been read when these changes were
made.** The commits are in order: pre-registration `6a4af12`, then the validated
estimators `0813d33`, then the study.

## A1.1 — ⛔⛔ Corwin-Schultz is DISQUALIFIED from the branch decision

Its zero-spread null is **linear in volatility**, measured on synthetic zero-spread series:

| σ per bar | 10 bps | 30 bps | 80 bps |
|---|--:|--:|--:|
| CS reads | 1.55 | **4.33** | **11.44** |
| AR reads | 0.00 | 0.00 | 0.00–0.28 |

**The branch boundary is 5 bps, and CS's artifact alone spans branch A and branch B.**
⛔ **Pooling does not fix it — a bias is not noise**, and that contrast is asserted by a
test. ⇒ CS is reported as a **corroborating upper bound only**. A CS reading above AR is
the expected behaviour and is **not** the "disagreement" §5 warns about; genuine
disagreement would be CS reading *below* AR.

⚠ **§5's clause "branch C requires BOTH estimators" is therefore VOID and is withdrawn.**
It was written assuming two comparable instruments. It is replaced by: **branch C requires
AR's interval upper bound ≥ 15 bps**, with CS reported beside it.

## A1.2 — the estimate is pooled over 21 sessions, not per name-day

A single-session AR estimate is **knife-edge**: under a true zero spread ~half of windows
clamp to zero, so the cohort median sits exactly on the clamp boundary and flips between
0 and ~5 bps with nothing but the random seed. ⭐ **My first characterisation of AR's null
was luck of the seed, and re-running it with a different one is what exposed this.**

Pooling fixes it. At the hardest volatility (80 bps/bar), recovery of a planted **5 bps**
half-spread runs **3.58 (1 session) → 4.24 (5) → 5.07 (21) → 4.86 (63)**, and a planted
10 bps goes from 35.3% of windows clamping to 2.5% at 21 sessions. **21 sessions ≈ one
trading month, which is also the window Abdi & Ranaldo apply the estimator over.**

⇒ the unit of observation is a **name-month**, and the API takes a sequence of sessions so
that pairing across a session boundary is unexpressible rather than merely discouraged.

## A1.3 — two mechanisms I had stated backwards, corrected by running them

- ⛔ **A session gap makes Corwin-Schultz clamp to ZERO, not inflate.** The combined range
  explodes, α goes sharply negative, and the estimate **understates**. That is the more
  dangerous direction: a stock with no measurable spread looks cheap to trade.
- ⛔ **AR's MEAN is volatility-biased while its median is not** (under a zero spread the
  mean reaches 6.08 bps at σ=80 while the median stays at 0). ⇒ **the study reports the
  median**, with the **zero-clamp share** beside it as an independent read — ~50% under a
  true zero, ~0% once a real spread is present — precisely because it does not share the
  median's failure mode.

## A1.4 — a persistence gap found while checking for ground truth

§2 claimed no historical spread exists. That was checked against three further surfaces
before the run: `orders.broker_payload`, `positions.charges`, and `order_events.payload`.
⛔ **`half_spread_bps` appears in none of them.** It is computed at fill time and
discarded. ⇒ **M92's own half-spread evidence (0.36–2.22 bps on the four 2026-09-18 fills)
is not reproducible from the database today**, and item 17b is the only path to a durable
series.
