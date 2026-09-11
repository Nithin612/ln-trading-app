# E2 / B6 — PRE-REGISTRATION. Written and committed BEFORE the code exists.

**2026-09-12.** ⛔ **Nothing below may be changed after the first result is seen.** If something
here turns out to be wrong, the amendment goes in a dated section at the bottom **with the reason
and the timestamp**, and the original stays.

## Why this document exists

E2 is the last unrun question that can change the direction of the programme rather than its
wording. **Under-specifying the decisive test is how KILL LINE 3 went wrong twice** (§12.15), and
round 9 found E2 itself had silently drifted from its own pre-registered estimand — §12.15 defined
3b as a *matched-tail contrast* and §13.8 restated it as a *full cross-sectional IC*, which are
different objects (§12.28). Three reviewers converged on that independently. So the estimands, the
horizon, the thresholds and the decision tree are fixed **here**, in git, before a line is written.

⭐ **And the standing convention since Kimi's C5: publish the numeric prediction first.** Mine are
in §6. A wrong pre-registered prediction is worth more than a right post-hoc one.

---

## 1. The three estimands

Let `S(i,t)` be the composite confluence score for name `i` on session `t` — the **shipped**
scorer, `confluence.run_all_factors` + `score_from_factors`, called not reimplemented.

⭐ **The shipped scorer is testable as-shipped.** §12.32 measured `FII_DII_FLOW` — the only
non-price factor — scoring on **0 of 487** panels, because `fii_dii_daily` holds 4 rows. So there
is no "price-only variant" problem: the historically-reproducible score IS the deployed score.

| # | estimand | definition | what a NULL means | what a POSITIVE means |
|---|---|---|---|---|
| **3a** | ⭐ **UNCONDITIONAL IC** | Spearman ρ between `S(i,t)` and the h=5d forward return, computed **within each session** across the eligible universe, then averaged over sessions | ⭐ **the scorer carries no cross-sectional information and no pipeline repair recovers it** — clean closure | the information exists; ask where it is lost |
| **3b** | ⭐⭐ **MATCHED-TAIL CONTRAST** | mean h=5d forward return of **gate-passers** minus that of **date-and-characteristic-matched non-passers**. Matching: same session, nearest neighbour on (log market-cap proxy = log close, 20-day realised vol) among names that did NOT pass | the gate selects nothing | ⭐ the **gate** is the value even if the ranking is not |
| **3c** | gate-conditional IC | Spearman ρ within gate-passers only | ⚠ **A COLLIDER** — gate passage is a threshold on the same weighted sum `S` is. **Report it, never decide on it** | — |

⚠ **Eligible universe**, fixed here: names with ≥ 300 prior daily bars on that session, a close
> ₹1, and a window that passes **B4's span guard** (`window_has_holes` False). ⛔ **This inherits
the known 0a.3 survivorship bias** — the name set is drawn by *today's* liquidity — and that bias
is not fixed by this test. It is recorded, not solved. Direction: it should if anything *help* the
scorer, so a null is conservative.

## 2. The horizon: h = 5 sessions. Pre-registered, single.

⭐ **5d, and only 5d, as the decision horizon.** §16.1b: at h = 20d, `SE(IC)` ≈ 0.0159, so an
IC of 0.02 gives t ≈ 1.26 — **20d can only ever return INCONCLUSIVE**, which is KILL LINE 4's
defect one level up. 20d may be reported as a **secondary descriptive** column; it may not move
the decision.

⚠ **Overlap.** Forward windows on consecutive sessions share 4 of 5 days. Observations are
therefore sampled **every 5th session** (the `factor_sweep.py:271` convention, which round 8
confirmed already does this). The naive daily-cross-section t is *additionally* reported beside
the corrected one, per the harness rule, so the inflation stays visible.

## 3. Inputs that must become OUTPUTS

⛔ **Two quantities every power figure in two documents is linear in are currently ASSUMED. This
run must emit them, and they may not be taken from any prior document.**

| quantity | current status | why it must be measured here |
|---|---|---|
| **`sd(IC_t)`** | ⚠ `[ASSUMED] 0.10` (§16.1b) | Every SE(IC) and therefore every power claim scales with it. `factor_sweep.py` does **not** store per-date ICs (verified §18.2 R8), so this run is the only way to retire it |
| **`E[z \| selected]`** | ⚠ **2.268**, a NORMAL-TAIL approximation | It is applied to a **hard gate at 70 on a bounded score** whose passers have mean 77.8, sd 5.8 (§12.10c). That is not a normal tail. Every break-even-IC figure (0.018–0.071) and KILL LINE 3's SESOI is linear in it |

⚠ **Power must be coverage-weighted.** §12.23 measured the cross-section running **46 → 250**
names per session, with 65% of names below 95% coverage. At 46 names the pure-noise IC floor is
`1/√46 = 0.147`, which **exceeds the entire break-even band**. Sessions must therefore be reported
with their name count, and the headline must state the effective (coverage-weighted) n.

## 4. Thresholds, fixed now

Break-even IC from D3's transfer for a gated tail selector,
`E[excess | selected] ≈ IC · σ_cs · E[z | selected]`, against **25.5 bps** of explicit round-trip
charges — ⭐ note the round-10 finding that the paired basket on the tradeable book is *negative*,
so the drift-inclusive hurdle is ≈ break-even alone (+0.008R), not break-even + 0.088R.

| σ_cs (measured, not assumed) | `E[z\|sel]` | break-even IC |
|---|---|---|
| 5% | 2.268 | **0.0225** |
| 7% | 2.268 | 0.0161 |

⭐ **Decision bands, pre-registered:**

- **NULL** — the 90% interval on IC contains 0 **and** its upper bound is below the measured
  break-even IC. *(A null that cannot exclude a tradeable effect is INCONCLUSIVE, not a null.)*
- **POSITIVE** — the 90% lower bound exceeds the measured break-even IC.
- **INCONCLUSIVE** — anything else. ⚠ **This is a real outcome and must be reported as one.**

⛔ **The t ≈ 3.6 DSR bar does NOT apply here.** That bar governs *promoting a gate on a measured
edge* after multiple testing. This is a **single, pre-registered, non-selected** measurement of one
frozen quantity — there is no trial count to deflate. Applying a multiple-testing correction to a
test with one trial would be a category error in the conservative direction, and the decision this
feeds is "does the scorer carry information", not "turn something on".

## 5. ⭐ THE DECISION TREE — fixed before the result

```
3a NULL      and 3b NULL      ->  CLEAN CLOSURE. The scorer carries nothing; the gate
                                  adds nothing. No pipeline repair recovers it. This is
                                  the branch the round-10 evidence points at.
3a POSITIVE  and 3b NULL      ->  The information exists and the GATE DESTROYS IT.
                                  The 70 threshold is the bug; rebuild it as a calibrated
                                  model rather than a hard cut.
3a NULL      and 3b POSITIVE  ->  Not a ranker — a TAIL/EVENT selector. A different and
                                  valid strategy class; the ranking layer is the wrong
                                  frame and IC was the wrong statistic.
3a POSITIVE  and 3b POSITIVE  ->  Information survives to the offered set, so the loss is
                                  DOWNSTREAM (level stage / geometry / horizon / fill).
                                  Pipeline repair, NOT closure. Round 10 already named a
                                  candidate: entry timing (88% of the BUY book's gross
                                  loss is tape, not alpha).
any INCONCLUSIVE              ->  report the interval and the achieved power. Do NOT
                                  fill the gap with a prior.
```

⚠ **B7 is what separates two of these branches and it runs in the same pass.** 3a positive with
`MFE ≫ |MAE|` and realised R < 0 is a **geometry** repair, not closure — E2 alone cannot see that.

## 6. ⭐ PREDICTIONS, recorded before the run

⚠ **These are mine, they are falsifiable, and being wrong is the point.**

| quantity | my prediction | reasoning |
|---|---|---|
| **3a IC at h=5d** | ⭐ **−0.01 to +0.01, NULL** | `factor_sweep` found nothing in the same feature family on 212,129 observations; 4 factors carry nearly every scoring event and two are EMA-derived, so effective dimensionality ~2–3 |
| **3a 90% upper bound** | **below 0.0225** ⇒ a true NULL, not inconclusive | ~790 clean sessions should give SE(IC) ≈ 0.004–0.008 if `sd(IC_t)` lands near 0.10–0.15 |
| **3b contrast at h=5d** | **|Δ| < 0.20%, NULL** | §12.31c measured gross alpha ≈ 0 (t −0.07) downstream of the gate on the tradeable book |
| **measured `sd(IC_t)`** | **0.12 – 0.18**, i.e. **HIGHER than the assumed 0.10** | small cross-sections (46 → 250) inflate per-date IC noise, and the assumption predates that measurement |
| **measured `E[z\|selected]`** | **1.6 – 2.0**, i.e. **LOWER than the assumed 2.268** | a hard floor at 70 on a bounded score truncates the tail the normal approximation extrapolates into |
| **B7 hazard** | **front-loaded: >50% of trades resolve by day 2** | mean `T` is 3.59 with 14.6% same-session exits |
| **overall branch** | ⭐ **CLEAN CLOSURE (3a NULL, 3b NULL)** | — |

⭐ **If `E[z|selected]` comes in near 1.8 rather than 2.268, every published break-even-IC figure
rises by ~26% and the band becomes ~0.023–0.090.** That is a consequence of this run regardless of
which branch fires, and it must be propagated into §16.1.

## 7. What this run may NOT do

- ⛔ May not test more than one horizon **for the decision**.
- ⛔ May not tune the gate threshold, the factor weights, or the universe definition.
- ⛔ May not drop sessions or names except by the rules fixed in §1.
- ⛔ May not touch `app/analysis/`, `app/backtest/engine.py` or `docs/SIGNAL_ENGINE.md`.
- ⛔ May not decide anything on 3c.
- ⚠ If the run reveals a defect in this pre-registration, **fix it in an amendment below with the
  timestamp** and re-run everything — do not silently repair and report.

## 8. Amendments

*(none yet)*
