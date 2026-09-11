# Round-8 external audit of `quant-panel-adjudication-2026-09-10.md`

**Reviewer stance:** quant + systems architect, reading the document as a *specification of an
estimation problem*, not as a review artifact. Every number below was recomputed. Where I could not
recompute it, I say so and it becomes a question in Part F instead of a claim.

**Standing rule I am obeying, from your own §15.4:** a claim about the data plane is a question, not
a finding, until someone runs the SQL. Part F is written accordingly — each ask states *why* it is
being asked and *what decision it moves*, so Claude Code can answer the intent rather than the
literal string.

---

## PART A — What the system is, read structurally

Stripping the seven rounds away, here is the object:

| layer | what it is | state |
|---|---|---|
| **scorer** | `confluence.py` — 15 factors, total weight 160, normalised by the weight of factors that *scored*, gate ≥70 | authored 2026-07-03, **genuinely pre-registered** against this corpus (R7-2) |
| **classifier** | `classify_signal` → swing / positional | 39/242 BUY → positional, **0/272 SELL** — `MULTIBAGGER_EMA` has no bearish branch |
| **level stage** | `safe_levels` → `compute_levels`, nearest swing pivot | **discards 60.8% of gate-passing swing panels.** FROZEN. Never designed as a selector |
| **geometry** | stop from pivot or EMA20 or flat-5% depending on caller; target flat 6% / 15% | ⇒ **R:R = k/w is an identity**, and three call sites disagree |
| **risk** | 2% risk, 6% heat, 3 slots, 1.0× per-position notional | **no portfolio cash rail** — 3 slots at the median stop = 120% of capital |
| **simulators** | `backtest/engine.py` (no fees, no horizon, no cap, no CA, defect #4) vs `paper_broker.py` (all of them) | **two different programs**, and this is the simplest explanation of most of §12.13b |
| **data plane** | `ohlcv_1d` 1,097 sessions with a 922-day hole; `positions`/`orders`/`corporate_actions` = 0; index 51 rows; VIX 17 | the binding constraint on almost everything |

**The number that should be at the top of the document and is not:**

> 16,428 panels → 514 gate-passers (3.13%) → 475 swing → 185 resolved trades. **1.13%.**
> Of the 98.87% attrition, **60.8% is a stop-placement rule** and **52.9% is a direction the account
> cannot hold.**

So the thing being measured is not "the scorer." It is *the scorer, intersected with a pivot-geometry
rule that was never specified as a filter, intersected with a direction constraint that was never
propagated, resolved through a simulator that differs from the live one on six axes.* Every estimand
argument in §12.13b is downstream of that sentence. §12.15's 3a/3b split is the right response and it
is still item 8 of 8.

---

## PART B — What is genuinely good, so it survives the cut

I want to be precise here rather than generous, because these are the parts worth carrying into
whatever replaces this programme.

1. **Provenance tagging + the `sample`/`verified` columns + the no-mixed-sample-tags rule.** This is
   better discipline than most professional research desks run. It is the single most transferable
   asset in the repository.
2. **Errors kept visible with strikethrough rather than edited away.** R7-K correcting three of the
   same round's own findings, published in the same document, is the behaviour that makes the rest
   of the numbers credible.
3. **`instrument_self_validation`** — reject a known null, accept a planted edge — and the honest
   admission in R7-K that four round-7 estimators have not had it.
4. **§12.10b, the denominator finding.** Correctly identified as the most productive result in the
   exercise. Part C shows it is *more* load-bearing than you have applied it.
5. **The 3a/3b split of KILL LINE 3**, and the recognition that a line keyed to total strategy R
   cannot kill a scorer.
6. **`Σ notional ≤ available cash`** — a genuine missing rail, correctly classified as an identity
   and therefore exempt from the promotion bar.
7. **The standing rule earned in §13f #5:** *a guard is not adopted until every number in the same
   document has been re-run through it.* Part C is largely an application of that rule to places you
   have not yet applied it.

---

## PART C — Eight defects, each recomputed

### C1 ⛔ Every "MDE" in the document is understated by exactly 1.40×

You define MDE as `2σ/√n_eff`. That is not a minimum detectable effect — it is the effect that would
*produce* t = 2 if observed exactly, i.e. 50% power. A minimum detectable effect at conventional
80% power is `(1.96 + 0.8416)·SE = 2.80·SE`.

You know this: §12.11b's Kimi Q8 table prints "MDE @ t=2" and "MDE @ 80% power" side by side. That
distinction then disappears from every other table in the document.

| cell | n | σ | infl | SE | **printed "MDE"** | **MDE at 80% power** |
|---|---:|---:|---:|---:|---:|---:|
| probe-185 mixed | 185 | 0.878 | 1.00 | 0.0645 | +0.129 | **+0.181** |
| probe-147 clean | 147 | 0.911 | 0.96 | 0.0734 | +0.150 | **+0.206** |
| probe-82 BUY | 82 | 0.957 | 1.21 | 0.1163 | +0.235 | **+0.326** |
| **probe-61 CLEAN × BUY** | 61 | 1.005 | 1.34 | 0.1487 | **+0.29** | **+0.417** |

**Consequences that change wording, not just decimals:**

- R7-A3's "a Sharpe-1.0 edge is still detectable at ×2.87" becomes **×2.05**.
- §12.10a's surviving claim, "detectability is retired," is weaker than stated everywhere it appears.
- KILL LINE 4's repair — *publish the MDE per cell before running* — will publish the wrong number
  unless the definition is fixed first. That is the one place where this defect can cause a wrong
  decision rather than a wrong sentence.

**Fix:** one constant. Print both columns, label the 2·SE one "critical effect at t=2" and stop
calling it MDE.

---

### C2 ⛔⛔ The two round-7 "inversions" are decompositions, not findings. Neither split is significant.

This is the largest defect in the document and it sits directly under the brief.

**The direction split (R7-A).** BUY −0.0992 (SE 0.1057) vs SELL −0.1885 (SE 0.0799):

```
difference = +0.0893    SE = 0.1325    t = 0.67    p = 0.50
```

**The gap filter (R7-I).** Clean −0.1341 (SE 0.0751) vs straddling −0.2059 (SE 0.1205):

```
difference = +0.0718    SE = 0.1420    t = 0.51    p = 0.61
```

Neither partition separates. In both cases you have taken a sample with a negative mean, cut it, and
observed that one half is less negative than the other — which is arithmetically near-guaranteed —
then read the *level* in each half rather than the *contrast between them*.

And the t-drop is mostly power loss, not the mean moving. Decomposing R7-I:

| step | t |
|---|---:|
| full sample | −2.31 |
| clean sample, **holding the mean fixed** at −0.1489 | −1.98 |
| clean sample, actual | −1.78 |

⇒ **0.33 of the 0.53 t-drop is n and σ; only 0.20 is the mean shift.** The sentence *"the hole biases
the mean DOWN and σ DOWN"* is not supported at t = 0.51. What is supported is *"removing 38
observations costs enough power to drop the headline below significance."* That is a true and useful
statement and it is a different statement.

Same for R7-A: **"the significantly-negative gross edge is carried by the untradeable half"** should
read **"splitting the book by direction leaves neither half powered, and the halves do not differ."**

⚠ This matters beyond wording, because §12.15, §17 Q7-1, §16.1's headline row and the entire brief
are keyed to "the tradeable book is different from the untradeable one." Measured, it is not
different — it is smaller.

**Fix:** run the interaction, not the subgroups. `R ~ 1 + is_BUY`, `R ~ 1 + straddles_gap`, and the
2×2, with date-clustered SEs. Report the interaction coefficient and its interval. That is the
statistic the four reviewers were actually asking for.

---

### C3 ⛔ The σ_R "monotone ladder" is 0.62 standard errors. It is noise, and you own the test that says so.

0.878 → 0.911 → 0.957 → 1.005 is read as *"σ_R rises monotonically as the population is restricted to
the honest one; every correction makes the problem harder"* and as *"independent support for §12.13b."*

Using your own estimator from §12.13b, `SE(s) = σ√((κ+2)/4n)` with excess kurtosis +8.19:

```
SE(σ) on n=61  = 1.005 × √(10.19 / 244) = 0.2054
|1.005 − 0.878| = 0.1274  =  0.62 SE
```

For comparison, the same formula gave **5.93 SE** for |1.489 − 0.878|, and you used it there to
establish that the corpus and probe samples differ structurally. Applied here it says the opposite:
these four numbers are one number. And they are **nested subsamples**, so even 0.62 SE overstates the
independence of the increments.

**What survives:** the corpus-vs-probe gap (5.93 SE) is real and item 2″ is the right response.
**What does not:** "1.005 is halfway back to 1.489" as evidence of anything, and "every correction
moves it the same way" as a pattern.

---

### C4 ⛔ Friction is a median-stop scalar applied as a book mean, and cost-in-R is 1/w

`cost_in_R = round-trip bps ÷ (100 × w)`. `w` has CV 0.51 with real mass below 1%. Therefore
`E[cost_in_R] ≠ cost_in_R(median w)` — by Jensen, strictly greater, and the gap is driven by exactly
the left tail your own §12.10b identified as the denominator pathology.

Rebuilding `w` from §7's own positional buckets (119/114/68/74/16 across 0–2 / 2–4 / 4–6 / 6–10 / 10%+):

| quantity | value |
|---|---:|
| cost at the median stop — **the scalar used throughout the document** | **0.076R** |
| E[cost in R] across the whole book | **0.128R** |
| E[cost in R] on the live-reachable book (w ≥ 2%) | 0.060R |
| understatement on the unrestricted corpus | **1.68×** |

So the friction number is roughly right *for the reachable book* and **wrong by ~1.7× for every
statistic computed on the unrestricted corpus** — which includes −0.065R, −0.1489R and every "net"
figure derived from them. R7-3's "the book is net-negative by 0.24R–0.32R at every point in the
10–30 bps range" is, if anything, understated.

**Fix:** stop using a scalar. Compute `roundtrip_charges` per trade at that trade's actual position
size, subtract trade by trade, and report the *distribution* of cost-in-R (mean, median, p90) beside
the mean net R. This is a two-line change in the probe and it should be done before any further net
statement is made.

---

### C5 ⛔⛔ §12.1, §12.2 and §4.4 share one denominator, and the two tests that killed the swing version have never been run on them

This is the most consequential unrun test in the document, and it is one line.

R7-J and R7-K killed the **swing** stop-width gradient twice over: it vanishes in raw % (t +2.30 →
+1.07) and it collapses and flips sign under the gap filter. Your own conclusion: *"the 2026-08-25
stop-width finding was a gap-contaminated R-denominator artifact."*

**The positional tables that carry §4.4, §12.1 and §12.2 have been subjected to neither test.** They
are still in Part I as "NEW AND DECISIVE," still cited as "the largest single recoverable term," and
still generating plan item 18 (the cap sweep).

They are the same variable. `R = ret / w`, restricted or bucketed on `w`.

Simulating the pure mechanical term — raw return **independent of** stop width, constant mean, sd
3.17% from §12.10b, `w` drawn from §7's own buckets:

| E[raw ret] | R (w<2%) | R (w≥2%) | ALL |
|---:|---:|---:|---:|
| −0.10% | −0.117 | −0.021 | −0.050 |
| −0.05% | −0.046 | −0.013 | −0.023 |
| **document measured** | **−0.306** | **+0.084** | **−0.032** |

⇒ **The direction and ordering of §12.1's "sign flip" fall out of 1/w with zero dependence between
return and stop width.** The magnitude does not — roughly a quarter of the measured spread is
mechanical under the most conservative assumption. So the effect is probably real *and* materially
overstated, which is exactly what happened to the swing gradient before the raw-% test finished it.

**§12.2's "dispersion lever" is the more fragile of the two.** *"The rejected cohort has both the
worst mean and the highest dispersion, so removing it cuts required n by 22%"* — a cohort divided by
a small number will always have the highest dispersion. If sd(R) falls because you removed small
denominators rather than because economic risk fell, the power gain is **nominal, not real**: you
have not reduced the variance of your P&L, only of your reporting unit. Required n scales σ_R², so a
mechanical σ_R reduction produces a mechanical and entirely fictitious power gain. Note that the
measured dispersion ratio (2.566 / 1.844 = 1.39×) is *far smaller* than pure 1/w predicts (≈5×),
which means raw-return volatility rises steeply with stop width and partially cancels it — i.e. the
two effects are tangled and only the raw-% and ATR-unit versions can separate them.

**⇒ Ask #1 in Part F.** If the positional tables die the way the swing ones did, then §4.4, §12.1,
§12.2, plan item 18 and the σ_R objective all die on the same afternoon, and the plan gets shorter
rather than longer.

---

### C6 ⛔ The only t ≥ 3.6 in seven rounds was computed with iid standard errors on leptokurtic, overlapping data

R7-J reports `rvol_20` at **t = +3.67** with the table labelled *"OLS, iid SEs, 185 trades."*

The dependent variable has **excess kurtosis +8.19**, the observations **overlap** (m = 2.08 mean
concurrency), and the regressor `RVOL-20` is itself strongly date-clustered — market-wide volume
spikes hit every name on the same day. Under those three conditions an iid OLS SE is not an
approximation, it is the wrong quantity.

You applied Newey–West to the *mean* (R7-H) and then did not apply anything to the *regression*.

**Predicted effect:** HC3 alone typically inflates the SE 10–25% on a variable with this tail;
clustering by date on a regressor with strong daily common variation frequently inflates it 1.5–2.5×.
A t of 3.67 becomes something in the range 1.5–3.0. That does not change the verdict — you already
have four reasons not to promote it — but it changes the *diagnosis*. You currently record it as
"the single most robust coefficient in the document and the single most firmly disqualified, which is
an uncomfortable pair." It may not be robust at all, in which case the discomfort dissolves and the
lesson is a different one: **the unit was never the only problem; the SE was.**

That matters because §16.1 now carries RVOL as a stamped, robust, disqualified-only-on-unit row, and
future rounds will re-open it on that basis.

---

### C7 ⭐ The panel-level score test — the one decisive question — is fully powered and is item 8 of 8

This is the most important thing in this audit.

Every trade-level statistic in the document is computed **downstream of three filters and a barrier
simulator**, each of which destroys information and adds variance. n = 61. The *upstream* question —
does the composite score carry cross-sectional information? — sits on **16,428 panels across ~790
clean sessions** and needs no CA source, no index history, no ledger, no holdout and no barrier model.

Power, treating overlapping horizons as h-fold redundant (conservative), with per-date IC dispersion
σ_IC = 0.10:

| dates | horizon | SE(IC) | t at IC=0.02 | t at IC=0.03 | MDE at 80% power |
|---:|---:|---:|---:|---:|---:|
| 790 (clean block) | **5d** | **0.0080** | **2.51** | **3.77** | **0.0223** |
| 790 | 20d | 0.0159 | 1.26 | 1.89 | 0.0446 |
| 1,097 (all) | 5d | 0.0068 | 2.96 | 4.44 | 0.0189 |
| 156 (`factor_sweep`'s dates) | 5d | 0.0179 | 1.12 | 1.68 | 0.0502 |

Your own break-even IC, derived in the KILL LINE 3 discussion, is **0.018–0.071**. The clean block at
h=5d resolves the bottom of that range at t = 2.5 and the middle at t ≈ 3.8.

**Three consequences:**

1. **The decisive test is affordable and the underpowered one is what you have been running.** Seven
   rounds have been spent refining a 61-trade cell with an 80%-power MDE of +0.42R, while the
   question that determines the programme's direction sits on 100× the observations.
2. **The horizon choice for #16 is decisive and must be pre-registered as 5d.** At 20d the same test
   is underpowered (t = 1.26 at IC = 0.02) and would return INCONCLUSIVE — KILL LINE 4's original
   defect, one level up. This is a pre-registration detail nobody has stated and it decides whether
   the test can fire.
3. **`factor_sweep`'s 156 non-overlapping dates were never enough.** SE(IC) = 0.018 against a
   break-even IC of 0.018 — the sweep's "nothing excludes zero" verdict was, on its own arithmetic,
   a **coin flip on a null it could not resolve**, entirely apart from the CA contamination §3.1
   already flagged. That is a second, independent reason the ranker question is open.

---

### C8 ⭐ §17 Q7-1's premise is false — the equity-beta null is computable today

Q7-1 concludes that §4.2's "negative alpha, not zero alpha" claim *"cannot be quantified while
`index_ohlcv_1d` holds 51 rows,"* and §16.3 item 3 makes the index backfill the gating item for the
document's most consequential interpretive claim.

You do not need `index_ohlcv_1d`. You need a benchmark, and `ohlcv_1d` contains 1,300–2,900 names per
year. Three constructions, all available now, all strictly better than NIFTY for this purpose:

1. **Equal-weight (or ADV-weight) basket of the eligible universe**, computed as-of each panel date.
   This is a *better* benchmark than NIFTY because it matches the universe you actually select from —
   NIFTY-50 is large-cap and your book is not.
2. **Matched-window random eligible name** — already specified as null #15(b). Its mean *is* the
   drift null, in the same units, through the same harness, with every harness bias cancelling.
3. **Same-name buy-and-hold over the identical window** — isolates timing and exit from drift within
   the name, which is the decomposition §4.2 actually wants.

⇒ §4.2 is not blocked. §16.3 item 3 is not blocked. Q7-1 option (ii) is answerable this week, and the
answer determines whether −0.084R is "no result" or "negative against a positive null." That is a
different Week-4 decision.

---

## PART D — The structural read

### D1. The three surviving positive results share one denominator

`§12.1` reachable-cohort flip · `§12.2` dispersion lever · `§4.4`/`§7` wide-stop gradient. All three
are statements about `R = ret/w` conditioned on `w`. One of the family — the swing gradient — has
already been killed by two tests. The other three have had neither. Treat them as one hypothesis with
a shared failure mode, not three independent lines of evidence. Part F Ask #1.

### D2. Effective breadth: the asymptote is real, but hold period is the free lever

Q7-2 asks whether `1 + (m−1)ρ̄` is the right form for a long-only book. Under a one-factor model
`ρ̄ ≈ β̄²σ²_mkt / σ²_total` — a **factor-share identity that does not depend on m**. So ρ̄ should be
roughly *flat* in slot count, and what asymptotes is instantaneous diversification at `1/ρ̄`:

| ρ̄ | max effective concurrent bets | m=3 | m=9 | m=20 |
|---:|---:|---:|---:|---:|
| 0.19 (measured, long-only) | **5.26** | 2.17 | 3.57 | 4.34 |
| 0.26 (measured, clean × long) | 3.85 | 1.97 | 2.92 | 3.37 |

⇒ **You are right that no amount of capital crosses it.** But you are conflating diversification with
accumulation. Effective *observations per year* = `m/(1+(m−1)ρ̄) × 250/hold`, and that keeps growing:

| configuration | effective obs / yr |
|---|---:|
| 3 slots, 5-day holds (today) | **109** |
| 9 slots, 5-day holds | 179 |
| **9 slots, 3-day holds** | **298** |
| 20 slots, 5-day holds | 217 |

⇒ **Hold period is a bigger breadth lever than slot count and it costs nothing.** Going 5d → 3d at
the same slots is worth more than the entire 2021–2023 backfill, which is Q7-4's answer: the backfill
is not worth days of ingestion, and the replacement lever is **turnover**, measured off the MFE/MAE
hazard curve you already have as item 20. ⚠ The offset is friction: cost-in-R is invariant to hold
period but cost *per year* scales with turnover, and the flat ₹15.34 DP charge is the binding term
(§12.3). The hazard curve and the cost table together decide it, and both are afternoons.

### D3. §4.5 uses the wrong law and reaches a conclusion that is too pessimistic per trade and correctly pessimistic per year

`IR ≈ IC√BR` is a *portfolio* law for an unconstrained, optimally-weighted, full-cross-section book.
You run a **gated tail selector** taking the top ~1–3%. The correct transfer is
`E[excess | selected] ≈ IC × σ_cs × E[z | selected]`, which you use correctly in the KILL LINE 3
discussion and not in §4.5.

At a 3% selection rate, `E[z|selected] = 2.27`:

| IC | σ_cs | E[excess]/trade | in R at a 5% stop |
|---:|---:|---:|---:|
| 0.02 | 5% | 22.7 bps | +0.045R |
| 0.02 | 7% | 31.8 bps | +0.064R |
| 0.04 | 5% | 45.4 bps | +0.091R |
| 0.04 | 7% | 63.5 bps | +0.127R |

Against 25.5 bps of round-trip charges: **IC = 0.02 is roughly break-even per trade and IC = 0.04 is
comfortably positive.** So *"a perfectly executed version of the current system is not investable"* is
wrong as stated — the per-trade economics of a modest IC work at this cost stack.

What fails is the **annual** number, through trade count: 60 positional trades a year at +0.09R and
2% risk is ~11% of capital gross. That is a *turnover* diagnosis, not a *signal-quality* diagnosis,
and it points at D2's lever rather than at abandoning the strategy class.

### D4. The document is running a frequentist test where the decision is Bayesian

"n = 61, t = −0.66, MDE +0.29R, **UNINFORMATIVE**" is the honest frequentist statement and it is also
misleading. The data are uninformative *relative to a flat prior over arbitrarily large effects*. They
are quite informative relative to a realistic one.

Posterior on the honest cell (μ̂ = −0.0843, SE = 0.1287), net break-even = 0.111R:

| prior sd on μ | posterior | P(μ>0) | **P(μ > net break-even)** | P(μ ≥ Sharpe-1.0) |
|---:|---|---:|---:|---:|
| 0.03R | −0.004 ± 0.029 | 44% | **0.00%** | 0.000% |
| 0.05R | −0.011 ± 0.047 | 41% | **0.44%** | 0.000% |
| 0.10R | −0.032 ± 0.079 | 34% | **3.5%** | 0.135% |
| 0.20R (absurdly generous) | −0.060 ± 0.108 | 29% | **5.8%** | 0.72% |

⇒ **Under any defensible prior the probability that the tradeable book has a positive net edge is
0.4%–5.8%.** That is not "no result." That is a decision.

And it resolves §17 Q7-1 cleanly: the choice between (i) NO RESULT and (ii) A NEGATIVE POINT ESTIMATE
is a false dichotomy created by using significance as the summary statistic. The correct answer is
**(iii): a posterior concentrated near zero with negligible mass above break-even** — which licenses
closure on economic grounds without claiming statistical closure, exactly the distinction §12.15
already draws.

⚠ Note what this does to the sunset: the programme's own arithmetic says the expected value of
continuing to *measure* the current strategy is close to zero, because the posterior barely moves for
any n you can accrue before 2026-10-31.

### D5. What n would actually be required

At the honest σ (1.005) and inflation (1.335), at 80% power:

| effect to detect | trades needed | years at 125/yr |
|---|---:|---:|
| +0.094R (Sharpe-1.0 net, long-only) | 1,198 | **9.6** |
| +0.111R (net break-even) | 859 | **6.9** |
| +0.205R (Sharpe-1.0 gross) | 252 | 2.0 |

⇒ Validating the current strategy on the live book is a **decade-scale** project. That was §5.2's
conclusion, it was retired twice by §12.8 and §12.10a, and at the honest σ it is **back**. This is the
one place where §12.5's original pessimism was closer to right than the two inversions that replaced
it — and the reason is C1 plus the σ ladder, not the argument §12.5 made.

---

## PART E — What I would do in the 50 days

Three measurements. All read-only. All afternoons. All decision-changing. Everything else on the
eight-item list is infrastructure for a question these three answer first.

| # | test | why it is decisive | cost |
|---|---|---|---|
| **E1** | **Raw-% and ATR-unit re-report of §12.1 / §12.2 / §7 (positional), with the gap flag** | Three of the four surviving positive results share one denominator, and the fourth already died to exactly these two tests | 1 afternoon |
| **E2** | **Panel-level score IC at h=5d on the clean block, date-clustered** | The only fully-powered test of the only question that changes direction. SE(IC) ≈ 0.008 against a break-even IC of 0.018 | 1 day |
| **E3** | **Drift null from the eligible-universe basket** (Part C8) | Decides whether −0.084R is "no result" or "negative against a positive null" — the Week-4 interpretive question | 1 afternoon |

Then make the Week-4 decision. If E1 kills the denominator family and E2 returns |IC| < 0.018 with a
tight interval, **3b fires cleanly and the closure is real** — and that is a good outcome for a
research programme, as §13c already said two rounds ago.

**The one build worth doing regardless of outcome** is Week-0 #2, the append-only ledger with the
`DecisionSnapshot → OrderIntent → Execution → PositionLifecycle → PerformanceRecord` chain. Not
because it helps this strategy — it does not, `positions` = 0 and cycle 2 cannot test expectancy —
but because it is the precondition for *any* successor, and it is the part of the apparatus that is
genuinely the asset.

**⛔ What I would drop outright:** the 2021–2023 backfill (Q7-4 — your prior of "no" is right, and D2
gives the replacement lever), the cap sweep (item 18 — pending E1, which will probably kill its
premise), and round 9.

---

## PART F — Questions for Claude Code

Each ask states the purpose, so the intent can be answered rather than the literal string. Ordered by
decision value per hour.

---

### F1 — Re-report the positional stop-width family in raw %, ATR units and net rupees, with the gap flag

**Ask.** On `positional_probe.py`'s sample, reproduce three tables in **four units side by side**
(`R`, `raw return %`, `return ÷ ATR20-at-entry`, `net ₹ after per-trade charges`), each additionally
split by `straddles_gap ∈ {true,false}`:

- (a) the three cohorts of §12.1: ALL / w ≥ 2% / w < 2%
- (b) the five stop-width buckets of §7: 0–2 / 2–4 / 4–6 / 6–10 / 10%+
- (c) `ret ~ stop_width%` univariate and with `ATR% + RVOL20 + log(close)`, with **HC3 and
  date-clustered SEs**

Report n, mean, sd, SE, t and the 90% interval in every cell, plus the count of gap-straddling trades.

**Why I am asking.** R7-J and R7-K killed the *swing* stop-width gradient twice: it vanishes in raw %
and collapses/flips under the gap filter. The positional tables that carry §4.4, §12.1 and §12.2 have
had **neither test applied**, and they are the same variable — `R = ret/w`, conditioned on `w`.
Simulation with return *independent* of stop width reproduces the direction and roughly a quarter of
the magnitude of §12.1's sign flip from the `1/w` term alone. If these die the way the swing version
did, §4.4, §12.1, §12.2, plan item 18 and the σ_R objective all close together and the plan gets
shorter. If they survive in raw % **and** on clean windows, they become the strongest result in the
document rather than the most fragile. Either outcome is worth an afternoon; the current state — three
findings resting on an untested denominator — is not.

---

### F2 — Run the panel-level score test at h=5d, before anything else

**Ask.** On all panels in the **gap-clean block only** (no level stage, no barriers, no R denominator,
no exits):

- forward **5-day raw return** regressed on the composite confluence score, and separately on the
  binary gate-pass indicator
- Spearman IC computed **per date**, then the time series of daily ICs summarised: mean, sd,
  Newey–West t at lag 4, and the count of dates
- the same for `return ÷ ATR20` as the dependent variable
- **also report h ∈ {5, 10, 20}** so the horizon choice is visible rather than assumed
- long-only and mixed, separately
- and the count of **distinct signal episodes** as well as panels (see F5)

**Why I am asking.** This is the decisive question — does the scorer carry cross-sectional information
— and it is the only test in the programme that is **fully powered**: ~790 clean dates at h=5d gives
SE(IC) ≈ 0.008 against your own break-even IC of 0.018–0.071, i.e. t ≈ 2.5 at the bottom of the range
and ≈ 3.8 at IC = 0.03. Every trade-level statistic you have is three filters and a barrier simulator
downstream of this, at n = 61 with an 80%-power MDE of +0.42R. **Please report the per-date IC
dispersion `sd(IC_t)` explicitly** — my power figures assume 0.10 and the whole calculation is linear
in it, so if it comes back at 0.20 the test is half as powerful and I need to know before recommending
it as decisive. And the horizon matters: at 20d the same test is underpowered and can only return
INCONCLUSIVE, which is KILL LINE 4's original defect one level up. This is 3b's endpoint stripped of
everything that made it item 8 of 8 — no CA source, no index, no holdout, no matched controls.

---

### F3 — Build the drift null from the eligible universe, not from the index

**Ask.** For each trade in the 185 / 147 / 82 / 61 cohorts, compute the **same-window** return of:

- (a) an equal-weight basket of the eligible universe as of the entry date
- (b) an ADV-weighted version of the same
- (c) a random eligible name (null #15b), averaged over ≥200 draws
- (d) the same name, buy-and-hold, entry bar to exit bar

Report the trade's raw return **minus** each benchmark, with the mean, SE and t of each difference
series, date-clustered.

**Why I am asking.** §17 Q7-1 and §16.3 item 3 both state that §4.2's "negative alpha, not zero alpha"
claim is **unquantifiable until `index_ohlcv_1d` is backfilled**. I believe that premise is wrong:
`ohlcv_1d` holds 1,300–2,900 names per year, and an equal-weight basket of the eligible universe is
not merely a substitute for NIFTY — it is a **better** benchmark, because NIFTY-50 is large-cap and the
book is not. This unblocks the document's most consequential interpretive claim today, and it decides
whether −0.084R reads as "no result" (Q7-1 option i) or "negative against a positive null" (option ii).
⚠ If there is a reason the eligible-universe basket cannot be constructed point-in-time from
`ohlcv_1d` — survivorship in `stocks`, a missing as-of liquidity rank, anything — **that is the
answer I need**, because it would mean the universe defect (0a.3) blocks more than the probes.

---

### F4 — Replace every subgroup comparison with an interaction test

**Ask.** On `probe-185`, fit and report with date-clustered SEs:

- `R ~ 1 + is_BUY`
- `R ~ 1 + straddles_gap`
- `R ~ 1 + is_BUY + straddles_gap + is_BUY×straddles_gap`
- the same three in **raw return %**

Report each coefficient, its SE, t and 90% interval — the **contrast**, not the level in each cell.

**Why I am asking.** I recomputed both round-7 splits and neither separates: BUY vs SELL is
`+0.0893 ± 0.1325, t = 0.67, p = 0.50`; clean vs straddling is `+0.0718 ± 0.1420, t = 0.51, p = 0.61`.
Decomposing R7-I further, **0.33 of the 0.53 t-drop is n and σ and only 0.20 is the mean shift.** So
"the negative edge is carried by the untradeable half" and "the hole biases the mean down" are
descriptions of two halves of a small sample, not measured differences. The brief, §12.15, §16.1's
headline row and Q7-1 are all keyed to those two claims. I would rather be shown the interaction
coefficient and be wrong than leave the headline resting on a partition that does not separate.

---

### F5 — Per-trade net R, and the cost-in-R distribution

**Ask.** In every probe, replace the scalar friction with a **per-trade** charge from
`roundtrip_charges` at that trade's actual position size and side, and report:

- mean, median, p10, p90 of `cost_in_R` across each cohort
- mean **net** R per cohort, with SE and t
- the same at slippage ∈ {0, 10, 15, 20, 30} bps/leg

**Why I am asking.** `cost_in_R = bps/(100·w)` and `w` has CV 0.51 with real mass below 1%, so
`E[cost_in_R] ≠ cost_in_R(median w)` — the Jensen gap is driven by exactly the left tail §12.10b
identified. Rebuilding `w` from §7's own buckets: cost at the median stop is 0.076R, the book mean is
**0.128R**, and on the reachable book (w ≥ 2%) it is 0.060R. So the scalar is roughly right for the
live-reachable book and **understates the unrestricted corpus by ~1.7×** — and −0.065R and −0.1489R
are unrestricted-corpus numbers. This is the same denominator pathology as F1, applied to the cost
side, and it is a two-line change.

---

### F6 — Episodes, not panels: how much of the sample is independent?

**Ask.** For `probe-185` and for the 16,428-panel walk:

- number of **distinct signal episodes** (same name, contiguous or near-contiguous gate-passing
  panels collapsed to one), alongside the panel and trade counts
- the distribution of panels per episode, and of days between consecutive same-name entries
- whether `_has_active_signal`'s latch is active in the probe path, or only in `signal_service`

**Why I am asking.** `_has_active_signal` latches an entry for the full validity window (30 trading
days for positional), and a stride-10 walk over 300-bar windows will re-present the same setup
repeatedly. If the independent unit is the episode rather than the panel or the trade, then every SE
in the document — including the ones I have used in this audit — is optimistic by `√(panels per
episode)`. The calendar-block bootstrap prices *calendar* overlap; it does not price **the same
signal being counted twice**. This is the one remaining way n = 61 could be smaller than 61, and it
would change the sign of my recommendation in Part E only in the sense of making it more urgent.

---

### F7 — Bars-per-name audit: is there a second, finer-grained hole?

**Ask.** Per year and per name:

- `bars_observed ÷ sessions_between(first_bar, last_bar)` — the distribution, and the count of names
  below 0.95
- the count and length distribution of **internal gaps > 5 sessions** within a name's series
- the same as a monthly session census against the NSE trading calendar, so any gap smaller than 922
  days is visible

**Why I am asking.** Your own year table implies ~83–86% bars per name per session in *every* year
(2024: 465,613 bars ÷ 2,304 names = 202 against 248 sessions; 2025: 208 against 248). That is
plausibly all listing dates — but if it is not, there is a **second version of §12.12 at the name
level**, and "the last 300 completed candles" is silently violated per name in the same way it was
violated per calendar. §12.12's standing rule — *a span is not a span until the session count is
queried* — has been applied to the table and not to the rows. This is one query and it either closes
the question or reopens the gap guard at a finer granularity.

---

### F8 — Give `ols_multi` the H8 treatment before RVOL is stamped into §16.1

**Ask.** For the R7-J regressions:

- re-run with **HC3** and with **cluster-by-date** SEs, reporting all three SE flavours side by side
- a **planted-edge arm**: inject a known coefficient into a shuffled column and confirm recovery
- a **null arm**: 16 coefficients on permuted outcomes × 500 draws, reporting how many clear t = 2 and
  t = 3.6 by chance
- the correlation of `RVOL-20` with `1/stop_width` and with `stop_width`, and the regression of
  `log(w)` on `RVOL-20`

**Why I am asking.** t = +3.67 was computed with **iid SEs** on a dependent variable with excess
kurtosis +8.19, on overlapping observations, with a regressor (`RVOL-20`) that has strong market-wide
daily common variation. Under those three conditions HC3 typically inflates the SE 10–25% and
date-clustering frequently inflates it 1.5–2.5×; the t could land anywhere from 1.5 to 3.0. Your own
R7-K note says `ols_multi` is *"the one that most needs the treatment"* and has not had it. This does
not change the do-not-promote verdict — you have four reasons already — but §16.1 currently stamps
RVOL as **robust and disqualified only by the unit**, and round 9 will re-open it on exactly that
basis. If the SE is the problem too, the row should say so. The `log(w) ~ RVOL` regression is the
direct test of the mechanism: if RVOL predicts *narrow stops*, then a coefficient on `ret/w` with no
coefficient on `ret` is fully explained.

---

### F9 — The two-simulator divergence, as one table

**Ask.** A single table of every behavioural difference between `backtest/engine.py` and the
`paper_broker` + `risk_engine` path: fees, slippage, validity horizon, notional cap, heat cap,
position count, cash constraint, gap/through-stop handling, SL-before-TP ordering, CA/ex-date
handling, fill price rule, `_has_active_signal` latching. For each: which side implements it,
file:line, and whether the difference is intentional.

**Why I am asking.** §12.13b spends five mechanisms and considerable argument on why `corpus-1975` and
`probe-185` estimate different quantities. The simpler and more complete explanation is that the
corpus and the live book **run different programs**, and nobody has ever written the divergence down
in one place. That table is also the specification for the "one kernel, one call contract" refactor —
which was accepted as a design and rejected on cost — and it is the cheapest way to bound how much of
the corpus-to-live bias cycle 2 is supposed to measure is just missing code.

---

### F10 — Hold-period sensitivity, as the replacement breadth lever

**Ask.** From the existing corpus, the time-to-outcome distribution: median and quartiles of
bars-to-exit, split by exit reason (stop / target / horizon cap), and `P(+1R before −1R | day d)` for
d = 1..20. Then, for hold ∈ {2, 3, 5, 10} days and slots ∈ {3, 6, 9}: trades/yr, effective
observations/yr at ρ̄ = 0.19, annual DP drag at ₹15.34 per delivery sell, and net R.

**Why I am asking.** Q7-4 asks what replaces breadth now that un-truncation is dead, and the answer is
**turnover, not names**. Under a one-factor model ρ̄ is a factor-share identity roughly independent of
m, so instantaneous diversification asymptotes at `1/ρ̄` = 5.26 bets — but effective observations per
year is `m/(1+(m−1)ρ̄) × 250/hold`, and that keeps growing: 109/yr today (3 slots, 5d) → 179 (9 slots,
5d) → **298 (9 slots, 3d)**. Shortening the hold is worth more than the entire 2021–2023 backfill and
costs nothing. The offset is the flat DP charge, which scales with turnover — so the hazard curve and
the cost table together decide it, and both are afternoons you have already scoped as items 20 and
Week-0 #6. **This also answers Q7-2 analytically:** ρ̄ should not rise with slot count under a
one-factor model; what has an asymptote is diversification, not accumulation.

---

### F11 — σ_R on `corpus-1975`, and please get all the cuts in one pass

**Ask.** The flag on `entry_confirmation_study.py` you already scoped as item 2″, but reporting σ_R
**and** mean **and** n simultaneously across the full cross of: classification (swing / positional) ×
direction (BUY / SELL) × window (gap-clean / straddling) × unit (R / raw % / ATR). Plus the same
denominator chain the probe emits (panels → gate-passers → class → level-stage survivors → resolved).

**Why I am asking.** Everything in §12.10a and half of §16.1 waits on this, and if it comes back as a
single number you will immediately need three more. Note also that I do **not** think the σ ladder
0.878 → 1.005 is evidence of anything: using your own `SE(s) = σ√((κ+2)/4n)` from §12.13b, the gap is
**0.62 SE** on nested subsamples. The same estimator gave 5.93 SE for the corpus-vs-probe gap, which
is why *that* one is real and worth measuring. Please compute and print `SE(σ)` beside every σ in the
output so the next round cannot read a trend into four nested points.

---

### F12 — Provenance of the 922-day hole

**Ask.** Was 2021-01 → 2023-06 ever ingested and subsequently lost, or never ingested? What is the
source and ingestion date of the pre-gap block versus the post-gap block, and do they share a
normalisation, adjustment and symbol-mapping path?

**Why I am asking.** §12.12 re-specifies 0a.6 as *"back-fill from the bhavcopy archive — the same
shape as the 2026-09-07 recovery."* That cost estimate only holds if the gap is a *missing* ingest.
If the two blocks came from different sources or different adjustment conventions, then stitching
them introduces a discontinuity that the gap guard will not catch — because the bars will exist and
the guard only flags absent sessions. That would be a third version of the same class of error, and
it should be known **before** anyone spends days on ingestion. It also bears on Part E: I am
recommending you drop the backfill, and I would rather drop it for the right reason.

---

## One closing observation

Your §13c meta-verdict, written two rounds ago, was right: *"The document has become the work. The
failure mode from here is not a bad test. It is a round 3."* Rounds 4 through 7 then happened, and
they were not wasted — round 7 alone found the 922-day hole and R7-K — but the scoreboard is explicit:
**4 of 37 points changed a decision, and 5 were refuted by a query the reviewer could have asked for.**

This audit found eight things, of which I would defend three as consequential: **C2** (neither
round-7 split is significant, so the headline rests on a partition that does not separate), **C5/F1**
(three surviving results share one untested denominator), and **C7/F2** (the decisive test is fully
powered and is item 8 of 8). The rest are corrections that tighten wording.

If those three are right, the honest position on 2026-10-31 is not "we could not tell." It is: *the
posterior on the tradeable book sits within a few percent of zero under any realistic prior; the
scorer's information content was tested at full power and returned X; and the apparatus — the
provenance discipline, the self-correction ledger, the instrument self-validation rule — is the
deliverable.* That is a programme reaching a conclusion, which is a different thing from a programme
running out of time.
