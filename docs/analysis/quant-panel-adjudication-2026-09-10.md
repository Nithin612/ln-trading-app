# Adjudicating the external quant panel — claim by claim, against the code and the DB

**Date:** 2026-09-10, last updated **2026-09-11 (round 9 — ⭐ the first round that shipped a probe with itself)** · **Branch:** `feature/pre-cycle2-hardening`
**Inputs:** `/home/nithin/swing_Profit Analysis.txt` and `/home/nithin/positional_Profit_Analysis.txt`
— five external reviews each (Perplexity · Claude · ChatGPT · Gemini · Kimi) of
`docs/SYSTEM_REVIEW_FOR_QUANT.md` and `docs/POSITIONAL_REVIEW_FOR_QUANT.md`, plus two
companion documents (`~/Downloads/REVIEWER_RESPONSE_2026-09-10.md`,
`~/Downloads/positional_QUANT_REVIEW_RESPONSE.md`).

---

## ▶ BRIEF FOR REVIEWERS — read this before the 3,200 lines below

> ### ⭐⭐⭐ ROUND 9 (2026-09-11) — E3 WAS RUN, AND THE PAIRED NULL REFUTED THE DOCUMENT'S OWN α
>
> **Five responses; §17b had asked for exactly two things — run E1/E2/E3, or refute a §16.1 row.**
> One did the second correctly, three converged independently on a defect in E2's estimand, and
> ⭐ **the round shipped code**: `swing_dependence_probe.py` gained the holding period `T`, a
> **paired** matched-window basket return, the entry-day Kaufman ER and a confidence-normalizer
> decomposition, plus a `--dump-trades` artifact; `scripts/round9_cells.py` reads it.
> **`probe-185` reproduced to 4 decimals**, so the artifact is validated against the record it
> replaces. Adjudication §12.24–§12.30 · **measurements §12.31** · **the factor inventory §12.32** ·
> plan §13.9 · ⭐ **what we build now §13.10** · ⭐ **what is parked and why §13.11** · ledger §13i ·
> card **§16.1c** · ⭐⭐ **PART VI = every panel question answered, per source (§18.1–§18.5)**.
>
> ⛔⛔ **THE BIGGEST CORRECTION IS MINE. §12.20a's "the correct null roughly DOUBLES the deficit"
> IS WITHDRAWN.** I multiplied a drift measured on 789 *post-gap* sessions by an **assumed**
> 5-session horizon and subtracted it from trades occupying **different** sessions whose mean hold
> is **3.59**. `[measured]` **Paired, over each trade's own entry-to-exit window, the basket is
> NEGATIVE on the tradeable book: −0.166% (BUY), −0.338% (E3).**
>
> ⇒ ⭐⭐ **GROSS ALPHA ON THE TRADEABLE BOOK IS ZERO: paired excess −0.0218%, t = −0.07 (n=82).**
> The ALL book's matched basket is **+0.247%** and the BUY book's is **−0.166%** ⇒ **the SELL
> signals fire into rising tape and the BUY signals into falling tape.** The book's gross loss is
> **not stock selection — it is WHEN it trades, plus cost.** No round had looked, because no round
> had the paired column. ⚠ `t = −0.07` is the absence of evidence for any α, not evidence of zero.
>
> ⭐⭐ **E3 — the cell the whole programme turns on — RUN.** `clean × BUY × w ≥ 2%`, n = **49**:
> gross **−0.1212R (t −1.26)** · **NET −0.1772R (t −1.84)** explicit · **−0.2432R (t −2.52)** at
> 15 bps/leg. ⭐ **Date-clustering moves every t by ≤ 0.06.** ⛔ §16.1b's **`t = −2.19` is
> withdrawn as the wrong cohort's number** (it includes sub-2% stops the order path refuses) —
> **and the verdict re-derives on the right cohort at −1.84.** ⚠ **Both published predictions
> (Kimi's −1.1…−1.4, mine −0.95…−1.10) were too optimistic because both held σ at 1.0050; the
> reachable cell's σ is 0.6712.**
>
> ⭐⭐ **THE STOP-WIDTH FAMILY, CLOSED A THIRD TIME AND BY A MECHANISM §12.18f MISSED.** There is a
> THIRD mechanical term — `R = (α + drift·T)/w`, and `d(T)/dw = +0.384, t = +6.69`. The contrast
> decays and **flips sign** as the terms are removed: **R −0.386 (t −1.55) → raw % −0.262 (t −0.78)
> → excess vs the matched basket +0.069 (t +0.17).** ⛔ **"Independence is MEASURED" is withdrawn —
> t = +1.07 is a NON-REJECTION**, and ~25% of that slope is drift×T (predicted +0.0264, measured
> removal +0.0298). ⚠ **Re-reporting in raw % was never enough; only pairing is.**
>
> ⭐⭐ **THE HEADLINE THE DECISION SHOULD BE WRITTEN IN, and it needs no t-statistic:**
> **per rupee-day deployed, the tradeable book underperforms simply holding the universe it selects
> from by 19–56 pp/yr (30–63 pp/yr on the reachable cell) net of explicit charges** — 39–90 pp/yr
> with a 15 bps/leg slippage assumption. ⚠ **The range is the aggregation choice, not uncertainty;
> the sign is invariant to every choice in the section.**
>
> ⛔ **TWO HYPOTHESES TESTED AND REFUTED, and both refutations make the closure CLEANER.**
> (a) ⭐ **The confidence normalizer** (`confluence.py:160` divides by the weight of *scoring*
> factors, so sparse conviction outranks broad agreement — confirmed in the code): **all four rival
> ranking keys are ρ ≈ 0, every p > 0.46** ⇒ **the negative covers the FACTOR SET, not one summary
> of it.** (b) ⭐ **The undeclared `choppy` display filter** hides **67%** of the offered set and
> separates **nothing**: contrast −0.0001, **p = 0.999** ⇒ **delete it.**
>
> ⭐ **AND THE ROUND'S REAL CONVERGENCE: three sources, three routes, one defect in E2** — the
> specified test (full cross-sectional IC) is not the deployed question, and the gate-conditional
> version is a **collider** on the score's own output. **E2 becomes three estimands** (3a
> unconditional · 3b matched-tail · the collider, reported never decided on) with `sd(IC_t)` and
> `E[z|selected]` as **OUTPUTS**. §12.28.
>
> ⭐ **NEW MECHANICAL RULE — the sample-tag rule in the TIME dimension:** ⛔ **a benchmark measured
> over one set of sessions may not be subtracted from a return measured over a different set. Pair
> it, or do not subtract it.** Eighth instance of the family; first in time rather than population.
>
> ⭐ **AND THE FACTOR INVENTORY, READ FROM THE FROZEN SCORER (§12.32): 26 registry entries, not 15;
> 325 declared weight of which the mean that SCORES is 30.6 (9.4%); and THREE factors never score on
> 487 panels — `DOW_TREND` (weight 20, the heaviest), `MARUBOZU`, and `FII_DII_FLOW`.** ⭐ The last
> of those **removes a blocker two reviewers built packages around: the only non-price term is
> already inert, so E2 can test the SHIPPED scorer rather than a "price-only variant."** And four
> factors carry nearly every scoring event (PRICE_VS_EMA 70% · ADX 46% · MACD_HISTOGRAM 43% ·
> RSI_LEVEL 36%), two of the top three EMA-derived ⇒ **effective dimensionality ~2–3, not 15.**
>
> ⛔ **THE PANEL IS CLOSED AT ROUND 9 (§17c).** What remains is **B1–B8 (§13.10)**: builds and
> measurements, not arguments. **No reviewer can shorten that list.** ⭐ **What is parked, and the
> specific reason each item is parked rather than dropped, is §13.11.**

> ### ⛔⭐ ROUND 8 (2026-09-11) — AN EXTERNAL AUDIT RECOMPUTED ROUND 7 AND MOST OF IT HOLDS
>
> **Three round-8 responses arrived; one of them (`~/Downloads/round8-external-audit-2026-09-11.md`,
> 727 lines) is the first review in eight rounds to arrive as a reproducible RECOMPUTATION. Every
> number in it was re-derived here before adjudication: 11 of 13 claims reproduce exactly.**
> Full adjudication in §12.18; the two findings that verifying it produced are §12.19 and §12.20.
>
> ⛔⛔ **TWO OF ROUND 7'S HEADLINE SENTENCES ARE WITHDRAWN.** Both round-7 "inversions" were
> **decompositions read as findings** — I reported the *level* in each half of a small sample and
> called the ordering a result, without ever comparing the halves:
>
> | split | difference | SE | **t** | p |
> |---|---:|---:|---:|---:|
> | BUY vs SELL | +0.0893 | 0.1325 | **+0.67** | 0.50 |
> | clean vs gap-straddling | +0.0718 | 0.1420 | **+0.51** | 0.61 |
>
> And **0.33 of the 0.52 t-drop from the gap filter is power loss; only 0.20 is the mean moving.**
> ⇒ *"the negative edge is carried by the untradeable half"* becomes **"splitting by direction leaves
> neither half powered, and the halves do not differ."** ⭐ **What survives is structural, not
> statistical: a cash-delivery account cannot hold an overnight short, so 55.7% of the trades are
> untradeable by construction whatever their mean.** The reason for preferring the BUY cell was never
> statistical — claiming the populations *differ measurably* was the error.
>
> ⭐⭐ **THE DECISION IS BAYESIAN, AND IT IS NOT "UNINFORMATIVE".** On the honest cell
> (μ̂ −0.0843, SE 0.1287) against the 0.111R net break-even, the posterior gives
> **P(positive net edge) = 0.4%–5.7% across prior sds from 0.03R to an absurdly generous 0.20R.**
> ⛔ **R7-K's "the evidence base is EMPTY, not negative" is withdrawn** in favour of the third option
> neither Q7-1 branch contained: **a posterior concentrated near zero with negligible mass above
> break-even ⇒ ECONOMIC closure without STATISTICAL closure**, which is the distinction §12.15 already
> draws. **And the expected value of continuing to MEASURE this strategy is near zero, because the
> posterior barely moves for any n reachable before the sunset.**
>
> ⛔ **Three more corrections to round 7:** every **"MDE" is 1.40× too small** (`2·SE` is 50% power;
> 80% needs `2.8016·SE`, so the honest cell's real MDE is **+0.417R** and "detectable at ×2.87"
> becomes **×2.05**); the **σ_R ladder 0.878 → 1.005 is 0.62 SE** — noise, by this document's own
> `SE(s)` estimator, and **t = 0.82** on a proper two-sample test; and at the honest σ, **validating
> on the live book is DECADE-SCALE again** (1,198 trades ≈ **9.6 years** for a Sharpe-1.0 net edge),
> so §5.2's original pessimism was closer to right than the two inversions that replaced it.
>
> ⭐ **AND THE TWO THINGS VERIFYING IT PRODUCED, neither of which is in any review:**
>
> 1. ⭐⭐ **THE EQUITY-BETA NULL IS COMPUTABLE TODAY AND I HAD JUST DECLARED IT BLOCKED.** An
>    equal-weight basket of the eligible universe, built from `ohlcv_1d` alone: **789 sessions,
>    +0.0816%/day, t +2.06, +22.8% annualised, +81.2% cumulative.** A 5-session hold's null is
>    **+0.088R** ⇒ **the honest cell reads α = −0.137R to −0.172R, roughly DOUBLE the raw deficit.**
>    §16.3 item 3 is withdrawn one section after being written (§12.20).
> 2. ⭐⭐ **A MONEY-PATH BUG: `paper_tick_size` is ONE constant (₹0.05) and the market has TWO grids.**
>    NSE moved sub-₹250 securities to a ₹0.01 tick — measured, the on-₹0.05 fraction for those names
>    went **0.98 (2019) → 0.87 (2023) → 0.49 (2024) → 0.22 (2025)**, while nothing above ₹250 changed.
>    `_round_tick` rounds adversely to ₹0.05 regardless, so **a ₹39 name is charged ~10 bps of
>    round-trip rounding the market does not — 40% of the whole real charge stack, 0.064R at a 2%
>    stop** — on exactly the cheap-tight-stop cohort that carries §12.1 and §7 (§12.19).
>
> ⭐ **Two structural reads worth more than the corrections.** **ρ̄ is FLAT in m** under a one-factor
> model, which refutes my own Q7-2 — and **hold period is a bigger breadth lever than slot count**:
> 9 slots at 3-day holds gives **298** effective obs/yr against 109 today, which answers Q7-4 (drop
> the back-fill; the lever is turnover). And **§4.5 used `IR ≈ IC√BR`, a portfolio law, for a gated
> TAIL selector** — at the correct transfer, **IC = 0.02 is break-even per trade and IC = 0.04 is
> comfortably positive at this cost stack**, so §4.5's "not investable" is a *turnover* diagnosis,
> not a signal-quality one.
>
> ⭐ **The one decisive test is still item 8 of 8:** the panel-level score IC at **h = 5d** (which must
> be pre-registered — at 20d it can only return INCONCLUSIVE) sits on ~790 clean sessions with
> **SE(IC) ≈ 0.008** against a 0.018–0.071 break-even, while seven rounds went into a 61-trade cell
> whose real MDE is +0.417R. ⚠ **And `σ_IC = 0.10` is an ASSUMPTION** that every IC power number in
> both documents is linear in — it must be an output of that test, never an input.
>
> ---
>
> ### ⛔⭐ ROUND 7 (2026-09-11) — superseded in part by round 8 above; read both
>
> **Four reviewers all led with the same request — split the headline by direction — and it had been
> an unrun plan item since round 1. It ran. The headline inverts.**
>
> | cohort | n | mean R | **t** |
> |---|---:|---:|---:|
> | ALL — round 6's headline | 185 | −0.1489 | **−2.31** |
> | **BUY — the only book cash delivery can hold** | 82 | **−0.0992** | **−0.94** |
> | SELL — untradeable overnight | 103 | −0.1885 | −2.36 |
>
> ⇒ **"A significantly negative gross edge" is carried by the untradeable half.** The tradeable book
> is **not distinguishable from zero, negative in expectation** (§12.16 R7-A).
>
> **Four more things changed, and three of them are corrections to round 6's own conclusions:**
>
> 1. ⛔⛔ **`ohlcv_1d` HAS A 922-DAY HOLE** — 2020-12-23 → 2023-07-03. **1,097 sessions, not ~1,730.**
>    **33.2% of round 6's panels were scored across it.** It **kills plan item #2**: un-truncation
>    yields n ≈ 2,662, or **exactly 0** at a 300-bar window — not 4,300 (§12.12). ⭐ *No reviewer
>    could have found this; it is not in any document. Nor could any reviewer have found it with the
>    code either — it took a query.*
> 2. ⭐ **ρ̄ ≈ 0 was a DIRECTIONAL-CANCELLATION ARTIFACT.** Long-only, variance inflation is
>    **1.19–1.23×** (ρ̄ ≈ **+0.19**), not 1.00×. ⇒ ₹3L buys **×1.63** effective observations — and
>    **Kimi's stress case turned out to be the real case** (§12.16 R7-A2).
> 3. ⛔ **§12.10a's headline inverts a THIRD time.** On the long-only corpus the MDE is **+0.0714R,
>    ABOVE explicit friction** — so *"the corpus can detect an edge below friction, with room to
>    spare"* is **withdrawn**. A Sharpe-1.0 edge is still detectable at ×2.87; the margin is 1.3×,
>    not 4× (§12.16 R7-A3).
> 4. ⭐ **The level stage — 60.8% of gate-passers — has never been evaluated as a selector, and the
>    cohort it DISCARDS outperforms the cohort it keeps by +0.16R** (t 1.43–1.54, two independent
>    fallback rules, paired by date). Claude's finding; the best of any round since R5-4 (§12.16 R7-C).
>
> 5. ⭐⭐ **Gemini's one control variable refuted one of OUR findings and surfaced the only t ≥ 3.6 in
>    seven rounds** — `RVOL-20` at **t = +3.67** (+3.14 long-only). ⛔ **And round 6's own rule
>    disqualifies it: in raw return % it is t = −0.28.** The same disqualification lands on the
>    **stop-width gradient** (t +2.30 in R, **+1.07 in %**, +1.06 long-only) ⇒ **the 2026-08-25
>    stop-width finding is substantially a DENOMINATOR EFFECT** (§12.16 R7-J).
> 6. ⭐ **The hole is a SECOND independent reason the headline is not robust:** on gap-clean windows
>    alone the mean moves −0.1489 → **−0.1341** and **t −2.31 → −1.79**, below significance on data
>    hygiene, before any direction split (§12.16 R7-I).
>
> 7. ⭐⭐ **AND THEN THE HONEST CELL — clean windows × long only: `n = 61, −0.084R, t = −0.66,
>    σ_R 1.0050, MDE +0.29R`. UNINFORMATIVE** (§12.16 R7-K). σ_R rises monotonically as the
>    population is restricted — **0.878 → 0.911 → 0.957 → 1.005** — so every correction makes the
>    problem harder. ⛔ **It also corrects three of my own round-7 claims: Claude's Finding D does NOT
>    survive the gap filter** (paired +0.16R → +0.09R, t 0.7, and it REVERSES on the clean tradeable
>    book); **the Kelly interval includes zero on the clean BUY book** (`f*=0` still holds exactly);
>    and **the stop-width gradient collapses and flips sign.** ⭐ What got STRONGER: `RVOL-20` is
>    robust to the filter (t +3.65 / +3.13) and still dead in raw % — **only the unit kills it.**
>
> **Two structural repairs follow:** KILL LINE 3 splits into **3a (strategy closure) / 3b (feature-
> family closure)**, because three reviewers independently showed a line keyed to total strategy R
> cannot kill a scorer (§12.15); and **`Σ notional ≤ available cash` does not exist in the code** —
> three slots at the median stop need **120% of capital** (§12.14).
>
> ⚠ **§16.1 now carries a `sample` and a `verified` column per row, and one mechanical rule:
> NO FORMULA MAY COMBINE TWO QUANTITIES WHOSE SAMPLE TAGS DIFFER.** This document has committed that
> error five times; round 7 is the first with a defence against the sixth.
>
> ⛔ **Shipped since 2026-09-10: four commits, all documentation. Of nine cut items, ONE has shipped
> as code. 50 days to the 2026-10-31 sunset.** §17 is four questions, not a review request.

This document has absorbed **eight rounds and twenty-eight external reviews**. It is long because it
keeps its own errors visible rather than editing them away — including the three occasions on which
a reviewer overturned its central conclusion. To make the next round pay, please:

⭐ **READ §16 FIRST — "REFERENCE CARD AND REVIEWER NOTES."** It fixes the shared constants (with
`[measured]` vs `[ASSUMED]` marked on each) and gives each reviewer its own evidence-backed note on
where its reasoning has repeatedly gone wrong. **Most of the arithmetic disagreements across six rounds
came from sources using different values for the same quantity** — and in round 6 the three
load-bearing constants were finally measured, and **all three had been wrong** (§12.10). §16.3 names the three
things worth attacking next — none of which is this document's internal consistency.

⭐ **THEN §15 — "REBUTTALS, WITH THE EVIDENCE."** Every claim rejected across six rounds is
listed there with the code line, query result or arithmetic that refutes it, **and what would change
my mind.** If you disagree, attack the evidence in the row; a restatement that does not engage it
will be recorded as already-answered. §15.4 carries three standing instructions, the first of which
is: **a claim about the data plane is a question, not a finding, until someone runs the SQL.**

### Where things are — the map

⚠ **Section numbers are historical and deliberately stable** — several `§N` references in the text
point at `SYSTEM_REVIEW_FOR_QUANT.md` or `POSITIONAL_REVIEW_FOR_QUANT.md`, so renumbering this
document would silently break them. The parts below group the sections; the numbers do not run
consecutively within each part, and that is intentional.

| part | sections | what it holds |
|---|---|---|
| **I — the system, adjudicated** | §0–§9 | the original ten reviews checked against code and DB. ⚠ **§8 is a superseded plan, kept for the record** |
| **II — the measurements** | §12–§12.23 | every number this exercise produced, in the order it was measured. **§12.10 supersedes the earlier sections' assumptions, and §12.12–§12.17 (round 7) supersede several of §12.10's** |
| **III — the plan** | §13, §13.7, §13.8 | the cut to nine items, the week-by-week sequence, the kill lines and the sunset clause. ⭐ **§13.7 is the post-round-7 plan and supersedes three of the eight items** |
| **IV — the round ledgers** | §10–§11, §13b–§13h | what each round contributed, took, refined and rejected, plus the meta-verdict (§13c) |
| **V — governance and reference** | §14–§17 | open questions · rebuttals with evidence · the reference card and per-reviewer notes · **§17 = the four questions back to the panel** |

### ⭐ Answer coverage — every question, and where its answer lives

The last round's three reviewers sent **32 specific questions** rather than opinions. **All 32 are
accounted for below** — answered, bounded, or recorded as impossible with the reason. Nothing is
silently dropped.

| # | question | status | where |
|---|---|---|---|
| C1 | calendar-block bootstrap, 3 block lengths | ✅ | §12.10 — full table; 10d/30d converge at 1.00×, **60d published as an anomaly** |
| C2 | pairwise correlation of overlapping R | ✅ | §12.10 — **−0.013** on 263 pairs |
| C2b | …split same-sector / cross-sector | ⛔ **blocked** | §12.11 — sector is 165/1,322; splitting would select on *which names got labelled* |
| C3 | block length **and unit** in §12.4 | ✅ | §12.11 — **8 trades**, date-blind |
| C4 | three units, full moments | ✅ | §12.10b — kurtosis **+8.19 / −0.25 / +0.02** |
| C5 | stop-width distribution | ✅ | §12.10b — CV 0.51 |
| C6 | is the 1,975 corpus all signals or gate-passers? | ✅ | §12.11 — **neither**, 3 stages downstream; ratios given, upstream counts never recorded |
| C7 | Δ_select | ⚠ **partial** | §12.10c — **t = +0.29**, but unpaired-by-date with an analytic SE, not a paired bootstrap |
| C8 | confidence buckets | ✅ | §12.10c — **not monotone**; 80–84 is the worst |
| C9 | intended vs achieved fill price | ✅ | §12.11 — columns exist, **tables empty** |
| C10 | shared level function | ✅ | §12.11 — shared fn, **divergent call contract** |
| C11 | backtest → fees / risk_engine | ✅ | §12.11 — **neither, zero references** |
| C12 | panel / signal / gate-passer / trade | ✅ | §12.10d — one denominator chain |
| K1 | swing dependence: eff n, inflation, concurrency, ρ̄ | ✅ | §12.10 |
| K1c | which inflation formula the **code** uses | ✅ | §12.11 — **none; it exists only in this document** |
| K2 | same on the un-truncated corpus | ⛔ **gated** | on 0a.6 |
| K3 | Sharpe → per-trade-R derivation | ✅ | §12.11b — `μ_net = S·σ·√I/√N` |
| K4 | fill price, R denominator, defect-#4 count | ✅ | §12.11b + §12.10d — next open · **fill** price · **1.08%** |
| K5 | ex-date stop behaviour | ✅ | §12.11b — **none exists; stops hit the raw price** |
| K6 | Kite adjustment policy | ❌ **not attempted** | needs a doc/API check, not a query |
| K7 | gate provenance, commit dates | ✅ | §12.11b — scorer **07-03**, first corpus analysis **08-12** |
| K8 | calibration power at sd(ε) ∈ {0.2,0.3,0.5} | ✅ | §12.11b — works to ≈0.35R, dead at 0.5R |
| K9 | slippage proxy + sensitivity | ✅ | §12.11b — the assumed 0.06R = **15 bps/leg** |
| K10 | tax handling + post-tax rows | ✅ | §12.11 + §12.11b — **none exists**; rows added |
| A | capital trace + the slot contradiction | ✅ | §12.11 + §12.11b — **two policies presented as one** |
| B | end-to-end look-ahead trace | ❌ **not attempted** | the one genuinely unstarted item |
| C | enumerate barrier/fill branches, repair defect #4 | ⚠ **partial** | counted (1.08%); **not enumerated, not repaired** — repair is 0a.2 |
| D | universe query point-in-time | ⚠ **partial** | §12.6 — defect located and the fix specified; **not yet applied** |
| E | CA: price vs knowledge-time reconstruction | ✅ | §13e R5-4 — the Kite-ratio method serves **price**, not knowledge-time; the trade is named |
| F | dependence → effective n | ✅ | §12.10 — by bootstrap rather than a covariance matrix |
| G | measure slippage, regress it | ⛔ **impossible** | §12.11 — `orders`/`positions` empty; **only cycle 2 can produce it** |
| H | capital ladder, two policies | ✅ | §12.11b |
| I | contradiction scan | ⚠ **partial** | §12.11 — capital equations scanned; the full repo-wide scan is not done |

**Totals across 33 rows (32 questions; C2 is split into C2 and C2b): 24 answered · 4 partial ·
3 impossible or gated, each with its reason · 2 not attempted.** The two unstarted items are named
rather than buried: **Kite's adjustment policy** (a documentation/API check, not a query) and
**ChatGPT's end-to-end look-ahead trace**.


### ⭐ Round-7 coverage — 37 points across four sources, adjudicated one at a time

**Method: every point checked against code, a query or arithmetic before adjudication.** §13f
carries the scoreboard and each reviewer's own slips with the derivation.

| # | point | status | where |
|---|---|---|---|
| **R7-A** | **split the headline by direction** (all four sources) | ⭐⭐ ✅ **RAN — headline inverts** | §12.16 R7-A |
| R7-A2 | is ρ̄ ≈ 0 real for a long-only book? | ⭐ ✅ **no — 1.19–1.23×, ρ̄ ≈ +0.19** | §12.16 R7-A2 |
| R7-A3 | does detectability survive the tradeable restriction? | ⛔ **partly — MDE 0.0714R > friction** | §12.16 R7-A3 |
| **R7-B** | Δ_select as a continuous rank statistic (Claude C · ChatGPT §5 · Kimi) | ✅ **ρ = −0.018, perm p 0.807, detectable at 0.147** | §12.16 R7-B |
| R7-B2 | is the 80–84 dip SELL-concentrated? (Kimi Q7) | ⛔ **REFUTED — worst in both directions** | §12.16 R7-B2 |
| **R7-C** | simulate the 289 level-stage rejects (Claude D) | ⭐ ✅ **RAN: +0.16R t 1.5** — ⛔ **then REFUTED by the gap filter (R7-K)** | §12.16 R7-C, R7-K |
| R7-D | dependence in cash / % / downside, not only R (ChatGPT §3) | ⚠ **measured, does not bite; direction does** | §12.16 R7-D |
| R7-E | empirical Kelly, not `p − q/b` (Claude · ChatGPT §9 · Kimi 6) | ✅ **f\* = 0.0000 everywhere** — ⚠ the CI claim withdrawn (R7-K) | §12.16 R7-E, R7-K |
| R7-F | winsorization state of every round-6 moment (Claude Q5) | ✅ **0 of 185 clipped — tails unassisted** | §12.16 R7-F |
| R7-G | class mix behind the σ gap (Claude A · Kimi Q2) | ✅ **475 swing / 39 positional, all 39 BUY** | §12.16 R7-A, §12.13b |
| R7-G2 | how was 1 CA found in 185 windows? (Claude Q6) | ⚠ **narrow detector; index leg BLOCKED (51 rows)** | §12.16 R7-G2 |
| R7-H | overlap-corrected t on the daily series | ✅ **NW t −2.01 all / −1.91 BUY** | §12.16 R7-H |
| **R7-I** | ⭐ **the 922-day `ohlcv_1d` hole** (mine) | ⛔⛔ **33.2% of panels; kills item #2** | §12.12 |
| **R7-J** | control the stop-width gradient for ATR% (Gemini item 4) | ⭐⭐ ✅ **hypothesis REFUTED; RVOL t=+3.67 found and disqualified** | §12.16 R7-J |
| R7-1 | the ex-date question's third answer (Claude) | ⭐ ✅ **accepted — a parity defect, not an open question** | §12.17 |
| R7-2 | the holdout is insurance, not a precondition (Claude) | ✅ **accepted** | §12.17 |
| R7-3 | slippage changes the hurdle, not the verdict (Claude) | ✅ **confirmed by arithmetic** | §12.17 |
| R7-4 | "manufactured tails" is too absolute (ChatGPT §8) | ✅ **refined** | §12.17 |
| R7-5 | R-space ≠ portfolio-space (ChatGPT §3) | ⚠ **valid in principle, refuted in this coordinate** | §12.17, R7-D |
| R7-6 | stride 10 is a diagnostic (ChatGPT §4 · Kimi 3) | ✅ **accepted; "brackets 12" was backwards** | §12.17 |
| R7-7 | the universe query is still not point-in-time (all four) | ⭐ ✅ **quantified: 46% of 2021 invisible** | §12.17 |
| R7-8 | three truths · `DecisionSnapshot` · split archive from contract (ChatGPT §12/§18) | ✅ **all three accepted and acted on** | §12.17, §13.7 |
| R7-9 | CA price ≠ knowledge chronology (ChatGPT §13) | ✅ **accepted; schema specified** | §12.17 |
| R7-10 | "fix the pytest DB leak" (Gemini 1) | ⛔ **shipped 2026-09-07** | §15.7 |
| R7-11 | "fix defect #4 at `engine.py:212`" (Gemini 3) | ⛔ **wrong line, wrong repair** | §15.7 |
| R7-12 | Kite ratios + stride 1 from 2019-10 (Gemini 2–3) | ⛔ **the bars do not exist** | §15.7 |
| R7-13 | Gemini item 4 — the one runnable new ask | ⭐⭐ ✅ **credited — it partially refuted one of OUR findings** | §12.17, R7-J |
| R7-14 | the margin lives in a 0.039R window (Kimi 5) | ⚠ **framing right, priority wrong** | §12.17 |
| R7-15 | shipped-status is stale (Kimi 6c/Q6) | ✅ **answered: 1 of 9, 50 days left** | §12.17, §13.7 |
| R7-16 | diff-verify the reference card (Kimi Part 6) | ✅ **adopted as §16.1's sample/verified columns** | §16.1 |
| **R7-17** | **KILL LINE 3 is keyed to the wrong stage** (ChatGPT §7 · Claude D · Kimi Q8) | ⭐⭐ ✅ **split into 3a / 3b** | §12.15 |
| **R7-18** | **no portfolio cash constraint exists** (ChatGPT §11) | ⭐ ✅ **confirmed by code — 120% at the median stop** | §12.14 |
| R7-19 | capital → granularity → risk → breadth (ChatGPT §10) | ✅ **accepted; corrects §12.13a's attribution** | §12.13a |
| R7-20 | one kernel, one call contract (Claude · ChatGPT §17) | ✅ **design accepted; cost estimate rejected** | §12.17, §15.7 |
| R7-21 | ChatGPT §24's twenty-audit interrogation | ⚠ **cut to four; §18 wins over §24** | §13f, §15.7 |
| R7-22 | Kimi Catch 1 — ρ̄ never propagated to §12.9 | ⭐⭐ ✅ **confirmed; table re-run** | §12.13a |
| R7-23 | Claude Finding A — σ/n sample mixing | ⭐ ✅ **confirmed; mechanism added** | §12.13b |
| R7-24 | Kimi Catch 4 — the card carries retired inputs | ✅ **confirmed; card rebuilt** | §16.1 |

**Totals: 37 points · 21 taken · 8 refined · 8 rejected on evidence**, plus **two findings of my own** (R7-I the data hole, R7-K the honest cell) **of which R7-K refuted three of my own round-7 results.** ⭐ **Four changed a decision**
(R7-A, R7-C, R7-17, R7-18) and **five were refuted by a query the reviewer could have asked for**
(R7-10 · R7-11 · R7-12 · R7-B2 · Kimi Catch 2's t). ⇒ **§17 asks four questions, not for a review.**

**Do NOT re-adjudicate rounds 1–7.** The ledgers at **§10** (round-2 scoreboard, 35 rows) and
**§13b** (round-3 ledger) record what was taken, refined and rejected, with the evidence and the
verification tag. Claims already settled there — the R:R identity, the CA contamination of
`factor_sweep`, the notional-cap reachability, the σ_R lever, the three broken kill lines — do not
need re-deriving.

**What is SETTLED (do not re-open without new evidence):** cycle 2 cannot test expectancy · the null
was never written down · 57% of generator output is untradeable · `factor_sweep` is CA-contaminated
so the ranker question is *open, not closed* · the corpus contains trades live refuses · required n
scales σ_R² · survivorship lives in our probe's universe query, not the database · all three original
kill lines were broken.

⚠ **AND NOTE WHAT ROUND 6 CHANGED, because most of the earlier text is now superseded:** σ_R, ρ̄ and
the variance inflation were **measured** and all three assumptions were wrong; **detectability is no
longer the binding constraint — friction is**; the fat tails were shown to be an artifact of the R
denominator; and **Δ_select measured t = +0.29, so the score carries no selection premium.** Sections
written before §12.10 that lean on σ_R = 1.489 or ρ̄ = 0.5 are marked but not deleted.

**What is LIVE and would genuinely benefit from attack:**

1. **§12.5's two-number correction, added 2026-09-11.** Is the corpus-vs-live-book distinction right?
   It concludes *all validation belongs on the corpus; the live book confirms plumbing only.* If that
   holds it is the most consequential structural claim in the document.
2. **The un-truncation (Week 0a.6).** Restoring the corpus to 2019-10 triples n but pulls in the COVID
   crash and the 2020–21 melt-up. Does the power gain survive the regime heterogeneity it imports, or
   does it just make a mixture bigger?
3. **The TOST repair of KILL LINE 3.** Is |IC| = 0.02 the right SESOI, and how should it be *derived*
   from the cost table rather than picked? A wrong margin makes "statistical closure" meaningless in
   either direction.
4. **§14 Q5, still unanswered after three rounds:** if KILL LINE 3 fires, what survives? The apparatus
   is the stated asset, but an apparatus with no strategy is a cost centre.

**What a reviewer CANNOT check from prose, so please don't spend the round there:** the data plane.
Three rounds have now guessed at survivorship, CA coverage and universe construction, and each time
the answer required a query. If a claim depends on what is actually in the database, mark it as a
question rather than a finding.

⚠ **Standing caveat on this document's own status (§13c):** three rounds, thirteen reviews, and
**zero Week-0 items shipped.** The recommendation on record is to stop reviewing and start building;
the user has elected to run round 4 anyway, which is their call. The most useful round 4 is therefore
a **short** one that attacks the four items above and says nothing about the rest.

---

**Method.** Every substantive claim was checked against the code on disk or a read-only
query against the dev DB on 2026-09-10. Nothing was taken on the reviewers' word, and
nothing was taken on our own documents' word either (W1). Provenance is marked
`[code]` / `[db]` / `[derived]` / `[doc]`.

**One-line verdict.** The panel is right about almost every mechanism and wrong about the
one thing it was most unanimous on. ⚠ **Credit correction (2026-09-11, round 2): "two
pieces of arithmetic" understates the panel by about half.** The SELL-untradeability
assembly in §4.3 — including the 1.8%-versus-4.19% selectivity figure — is the panel's,
almost verbatim; and Kimi answered the ₹1L viability question flatly ("**No.**") with the
same DP/bps arithmetic §5.2 presents as unnamed. Round 2 then landed three direct hits on
this document (§3.1, §4.2, §4.4). Recorded because it changes how much weight the next
round deserves. Its most valuable contributions were **cycle 2 cannot pass its own gate**, and
**the correct null was never written down**. Its blind spot is that the evidence base it
reasons from no longer exists.

---

---

# PART I — THE SYSTEM, ADJUDICATED

## 0. The reviewers were reviewing a document, not a system

Nine of the ten reviews never touched the code; they reasoned from my prose. That worked
remarkably well where the prose was precise (the notional-cap identity, the denominator
pathology, the cost hyperbola — all confirmed below) and failed where it was loose. Two
inferred errors are now replicated across ten reviews.

The operational lesson is ours, not theirs: **the review document is the interface, and
its imprecision propagates at scale.** Both review docs need the corrections in §3 before
they are shown to anyone else.

---

## 1. CONFIRMED — verified in code or DB

| # | Claim | Verification |
|---|---|---|
| 1 | Confidence normalises by the weight of factors that **scored** | `[code]` `confluence.py:160` — `total_weight = sum(f.weight for f in factors if f.score != 0.0)` |
| 2 | At fixed conviction the gate is **inversely related to breadth of evidence** | `[derived]` from #1. One factor w=10 s=0.8 → 8/10 = **80, passes**. Four factors (15/10/10/10 at 0.6/0.5/0.5/0.4) → 23/45 = **51, fails** — nearly 3× the evidence, rejected |
| 3 | Volume can never vote against price | `[code]` `confluence.py:145-157` — score sign forced to match the other factors, zeroed when they net to zero. ⚠ This is **specified** in SIGNAL_ENGINE.md §3 and adjudicated 2026-07-04, so it is a spec choice, not a slip |
| 4 | FII/DII is cross-sectionally constant, weight 5, and dilutes the denominator for every name on the same day | `[code]` `institutional.py:11` `_WEIGHT = 5`; inputs are market aggregates (`fii_net_5d`, `dii_net_5d`) |
| 5 | `DOW_TREND` (weight 20) is dead on daily | `[code]`+`[db]` already ours; today's probe re-confirms **0% participation** on positional panels |
| 6 | Three-way divergence in positional levels; root cause is an optional parameter with a plausible semantic default | `[code]` `risk.py:63` `ema20_daily: Decimal \| None = None` → `risk.py:110` silent `entry − 5%`. `signal_service.py:245,434` **passes** it; `profiles/pipeline.py:367` and `backtest/engine.py:322` **do not** |
| 6b | **NEW, ours:** the divergence covers **targets** too | `[code]` `pipeline.py:379` overrides TP via `_tp_from_template`; `engine.py:341` applies `config.tp_rule`. Three stops **and** three targets |
| 7 | `positional` carries **no** stop cap | `[code]` `risk.py:117` — `if classification != "positional":` skips the cap check entirely |
| 8 | The backtest applies **zero** costs | `[code]` no `fee`/`slippage`/`charge`/`stt`/`brokerage` token anywhere in `backtest/engine.py` |
| 9 | The backtest enforces **no** validity horizon | `[code]` `engine.py:243` `for i in range(fill_idx, len(candles))` walks to end of data; only `session_last` (intraday) can force an exit |
| 10 | The 1.0× notional cap is algebraically a **2% minimum-stop-width** filter | `[code]`+`[derived]` `risk_engine.notional_cap_reason`: cap = `capital × leverage`, `qty = capital × risk_pct/100 ÷ risk_per_share` ⇒ capital cancels ⇒ rejects `stop_width% < risk_pct/leverage` |
| 11 | `WINSOR_R = 10` is applied to the **mean** (median reported raw) | `[code]` `positional_probe.py:170` inside `summarize` |
| 12 | The entry-zone alert is a **symmetric** band while direction-aware machinery sits unused in the same file | `[code]` `live_levels.py:238` emits `kind: "zone"` over `entry ± live_entry_zone_pct`; `cross_up`/`cross_down` are used at lines 126, 252, 266 for PDH/PDL and SL/TP touches |
| 13 | `_has_active_signal` latches a stale entry for the full validity window | `[code]` `signal_service.py:165-190`, matched on `status == "active"` and unexpired. A positional signal therefore latches **yesterday's close** as its entry for 30 trading days |
| 14 | The backtest trades SELL signals as shorts; the paper broker will open a SHORT | `[code]` `engine.py:232` `buy = direction == "BUY"` (both sides simulated); `paper_broker.py:508` `pos_side = "LONG" if side == "BUY" else "SHORT"` |
| 15 | The ADX threshold schedule lives **inside** the freeze and has never been tested | `[code]` `confluence.py:168-172` — weak ⇒ `+5`, strong ⇒ `max(65, min−5)` |
| 16 | Data plane is degraded | `[db]` see §2 |

---

## 2. The state of the data plane `[db]`

| Table | Rows | Note |
|---|---:|---|
| `ohlcv_1d` | 2,081,473 | 2019-10-01 → 2026-09-10, **CA-unadjusted** |
| `stocks` active | 1,322 | sector populated on **165** (12.5%) |
| `index_ohlcv_1d` | **51** | ⛔ CLAUDE.md claims the backfill "is already done" — **false** |
| `india_vix_daily` | **17** | was 784 sessions pre-destruction |
| `signals` | 33 | BUY 26 / SELL 7 · swing 27 / positional 6 |
| `positions` | **0** | ⛔ the entire cycle-1 book |
| `cas_daily` | 43 rows, **1 session** | ⛔ CLAUDE.md claims "1,664 rows across 8 sessions, accrual HEALTHY" — **false** |
| `ohlcv_5m` | 0 | every intraday hypothesis remains untestable |

---

## 3. REFUTED — where the panel is wrong, and it matters

### 3.1 ⛔ "You have never computed factor-level IC. Do it first. It is two days of work."

> ⚠ **CORRECTED 2026-09-11 (round 2, Kimi — the sharpest catch against this document).**
> The counter-evidence below is **itself CA-contaminated**, and I applied a standard to the
> panel that I failed on my own instrument. `[code]` `scripts/factor_sweep.py` has **no
> corporate-action filter of any kind**: it computes features (`close/sma200`,
> `close/hi252`) *and* labels (`LEAD(close, horizon)`) on CA-unadjusted prices, so a ≥40%
> halving corrupts both, in a correlated way. Roughly 49 events × ~250 days of SMA200
> contamination ≈ **5.8% of the 212,129 observations** carry grossly wrong values, against
> a target IC of 0.02–0.04. **⇒ The sweep does NOT license "no cross-sectional IC exists
> in our universe." It licenses only "none was detectable on contaminated data." The
> ranker question is REOPENED, pending a re-run on the adjusted plane (§13, Week 2 #17).**
> This is `instrument_self_validation` applied to my own counter-evidence, and it is the
> single most important correction in round 2.

Said independently by **four of five reviewers** (Claude §2.2, ChatGPT §24, Perplexity, Kimi).

**We built it and ran it three days ago.** `backend/scripts/factor_sweep.py`, run 2026-09-07
at h=5 and h=20:

- **212,129 observations** on **156 non-overlapping dates**, universe floor ≥ ₹1 Cr median daily traded value
- day-block bootstrap (the date is the independent unit), non-overlapping sampling, **and trial-count deflation** — a guard *none* of the five proposed
- 17 configurations: every SMA pair, close-vs-{SMA20/50/150/200, VWAP20/50}, RVOL at four lookbacks, 52-week position
- **Verdict: nothing in the top 6 has an interval excluding zero.** Best |Q5−Q1| spread −0.313% on `close_over_sma20`, interval [−1.030, +0.405]%

Reports: `docs/analysis/factor-sweep-h5-2026-09-07.md`, `factor-sweep-h20-2026-09-07.md`.

**Why this matters more than the correction.** The features that came back flat —
`sma50_over_sma200`, `close_over_sma200`, `pos_52w`, `sma150_over_sma200` — are *precisely*
the feature family a Minervini-style trend template or a 12-month-momentum ranker is built
from. So the panel's other unanimous recommendation, **"build a cross-sectional ranker,"**
already has a strong measured prior against it on our own universe, which none of them knew.

**The residual gap is real but much narrower than stated:** the sweep pointed at *candidate*
features and never at **our own 15 factors individually, nor at the composite confluence
score**. That specific test has not been run, and it is the one worth running.

### 3.2 ⛔ Gemini's injection script does not do what it says

`run_injection_backtest()` fills `results_r` with `np.random.normal(loc=0.01, scale=1.2, size=1975)`
and computes a Newey–West t on it. It measures **synthetic noise**, not our corpus. Do not run
it as given. Its `functional_dow_trend_factor` (lookback 60) is a reasonable candidate;
the harness around it is not.

### 3.3 ⛔ Gemini's pivot arithmetic is wrong (the conclusion is still right)

"Four non-overlapping pivots requires a minimum of 4 × 11 = 44 bars." Pivots at n=5 need
11-bar windows but those windows may sit 6 bars apart, so the bound is not 44. Our own
derivation is the correct one: inside a 20-bar lookback a pivot index can only sit at
5…14, any two differ by ≤ 9 < 11, so their windows necessarily overlap. Same verdict,
sound reasoning — keep ours.

### 3.4 ⛔ "Normalise confidence by the full 160 weight" (Gemini, Perplexity, Kimi)

Arithmetically self-defeating. Our measured p90 scoring weight is 55 of 160, so the
realistic maximum confidence would collapse to ≈ 34 and the 70 gate becomes unreachable.
You would then refit the threshold — trading one arbitrary parameter for another.
Claude's counter-proposal (drop the ratio, rank on the raw weighted sum) is the only one
of the three that is internally consistent.

### 3.5 ⛔ "Enable the heat and position caps to fix profitability"

Already measured. `app/services/heat_counterfactual.py`: a 6% cap took total P&L from
−₹19,093 to −₹13,303 but moved per-trade from −₹796 to −₹1,478. **A risk control, not a
profitability fix** — and we recorded the trap that chronological admission selects by
arrival time, not by quality.

### 3.6 ⛔ Gemini's "hard floor on stop width of 3.5%"

We considered and rejected the %-of-price form of this (`paper_min_risk_pct`): 2% is
comfortable on HDFC and a knife-edge on a ₹39 micro-cap. `sl_atr` measures the same thing
in ATRs and is the right instrument. Also note we already own a 2% version by accident
(§1 #10) — adding a second instrument for one job violates W2.

---

## 4. NEW AND DECISIVE — five things not in any of our documents

### 4.1 ⭐ Cycle 2 cannot test expectancy. The gate is unpassable by construction.

From our own §11.1: n = 1,975, mean R = −0.065, t = −1.94 ⇒ SE = 0.0335R ⇒
**σ_R = 0.0335 × √1975 = 1.489**. `[derived]`

Cycle 2 is specified as 45–50 sessions at 1–2 concurrent positions with ~5-day holds
⇒ **n ≈ 20–30 trades**.

| Bar | Required mean R at n=25 |
|---|---:|
| Our DSR bar, t = 3.76 | **+1.12R / trade** |
| A plain one-sided t = 2.0 | **+0.60R / trade** |
| What a Sharpe-1.0 system actually delivers (250 trades/yr) | **+0.094R** |
| What a Sharpe-0.37 system (median of the replication literature) delivers | **+0.035R** |

**Cycle 2 demands roughly 12× what a world-class system produces.** It would fail if the
strategy were excellent. The methodological error is a category confusion: the deflated
Sharpe ratio corrects for *how many hypotheses you searched*, which is right for promoting
one shadow gate out of eight and wrong for a single pre-registered confirmation where
there is no multiplicity to deflate.

**Consequence for the roadmap, actionable with no new research:** re-scope cycle 2 as an
**operational-correctness rehearsal** — do the caps fire, does heat stay bounded, do fills
reconcile, does the order FSM survive 45 days of runtime hours. That is a legitimate and
valuable thing for it to be. It is not, and cannot be, an expectancy gate. The expectancy
decision has to be made on the panel and the corpus, where n is two orders of magnitude
larger.

### 4.2 ⭐ The correct null was never written down, and it changes the sign of the verdict

> ⚠ **CORRECTED 2026-09-11 (round 2, Claude and ChatGPT independently).** Three repairs,
> two of which weaken this section and one of which strengthens it:
> **(a) "Negative alpha" is over-claimed** and asserted with exactly the small-n looseness
> this document criticises elsewhere. Per-trade alpha +0.0010 on 40–105 observations will
> not exclude zero, and the −13.42pp versus NIFTY is **not a valid comparison without a
> time-in-market adjustment** — two or three positions on ₹1L is not a 100%-invested book,
> so underperforming a fully-invested benchmark while averaging half-invested is
> arithmetic, not alpha destruction. **Correct claim: the null is unwritten and is probably
> positive; measure it.** The verdict needs a properly specified regression (market beta,
> sector, size/liquidity, vol, time-varying beta, HAC errors), not a beta subtraction.
> **(b) Under DISCRETE daily monitoring the martingale null is NEGATIVE, not zero** — so
> "worse than a coin flip" may be a description of what a coin flip actually costs on
> daily bars. ⚠ Claude's stated mechanism ("targets fill at the limit or better") is
> **wrong for our engine**: `[code]` `engine.py:250-255` gaps *both* sides at the open. The
> real mechanism is `[code]` `engine.py:257-261` — `hit_sl` is checked **before** `hit_tp`
> on both-hit bars, a deliberate conservatism. Plus zero log-drift implies **positive**
> arithmetic drift (+σ²/2), so barriers are not drift-neutral either.
> **(c) The drift correction ARGUES FOR §4.4's gradient.** For a time-capped exit
> E[R] ≈ μT/w, which is *larger* for tight stops — so a drift artifact would have produced
> the **opposite** sign to the one measured. The gradient is not a drift artifact.

Under a driftless martingale the expected R of **any** barrier configuration is exactly
zero: `R = (exit − entry) / |entry − stop|`, the denominator is fixed at entry, and
`E[exit] = entry`. Stop width, target width and time cap are all irrelevant.
**A coin flip scores 0.000R.** `[derived]`

Our positional live rule scores **−0.090R gross**. Our swing corpus scores **−0.065R gross**.
Both are *worse than a coin flip before a single rupee of cost*.

And zero is not even the right null. The book is **100% long** (435/435 positional signals
BUY, 40/40 live positional trades LONG) with measured **beta +0.92**, over a window in
which Indian equities rose substantially. The free drift, expressed in R at a 3.24% median
stop, is large and positive. Corroborated from the other side by our own numbers:
per-trade alpha **+0.0010** against beta **+0.92**, and **−13.42pp** versus NIFTY50
buy-and-hold.

**We have been reading "indistinguishable from zero" as "no edge." The honest reading is
"negative alpha" — we are destroying drift that was on the ground.** That is a materially
different and more actionable diagnosis. The missing measurement is one script: same
panels, same barriers, replace the entry decision with (a) "buy this name" and (b) "buy a
random liquid name."

### 4.3 ⭐ 57% of the generator's output is untradeable, and it is in the headline corpus

`[doc]` §4.3 records 189 gate-passing panels splitting **108 SELL / 81 BUY**.
`[code]` the backtest simulates both sides; the paper broker opens SHORT positions.
`[doc]` NSE cash equity delivery cannot hold an overnight short — our own CLAUDE.md
already says so, in the A29 fees bullet: *"a delivery SHORT is charged on ENTRY — an
artefact of the paper model, since a cash-equity delivery short is not actually possible."*

We knew the fact and never propagated it to the corpus. Three consequences, and the
document resolves none of them:

- if SELLs are discarded, true tradeable selectivity is **81/4,511 = 1.8%**, not 4.19%
- if they are in the 1,975 trades, the −0.065R headline **blends a tradeable long book
  with an untradeable short one**, and the two have opposite exposure to positive drift
- the generator carries a structural bearish tilt (bearish engulfing 7.3% + bearish harami
  4.9% = 12.2% of panels against 8.2% for their bullish counterparts), so a bearish-tilted
  selector is paying a drift headwind in a rising market

**Every side-conditional statistic in both review documents needs re-reporting split by
direction.** This is hours of work and it determines whether §11.1 measures a strategy we
could trade at all.

### 4.4 ⭐ The 8% swing stop cap is anti-correlated with P&L on three independent lines

> ⚠ **CORRECTED 2026-09-11 (round 2, Claude). The heading is wrong: there are not three
> independent lines. There is one variable measured twice, plus an identity.**
> `[code]` `risk.py:101,111` — the targets are **flat 6%** (swing) and **flat 15%**
> (positional), so **R:R = 6/w and 15/w exactly**. "R:R < 1" and "wide stop" are therefore
> the *same variable*: swing R:R < 1 ⟺ w > 6%. The R:R-revert cohort's 7.29% average stop
> was not corroboration of the wide-stop finding — it **was** the wide-stop finding.
> **The repaired argument is narrower, measured, and stronger** (see §12): positional, the
> class with **no** cap, shows its best cohort above 10% stop width, and its
> live-reachable mean is **+0.084R against −0.032R unrestricted**; swing's reachable band
> is **[2%, 8%]** — floored by the notional-cap identity and truncated by the class cap —
> so swing structurally cannot reach the region where the positional gradient pays.
> That rests on one measured gradient on an uncapped class plus an identity about which
> region the cap deletes. ⚠ Also: harness defect #4 (a gap-through-stop booked as ~+1R)
> **flatters tight stops**, which biases the gradient *toward flat* — the true gradient is
> steeper than measured, and −0.306R for w < 2% is an **upper bound** on its real
> performance. Direction strengthened, magnitude further in doubt.

We have every piece and never assembled them:

- `[doc]` §5.2 — 38.1% of daily windows are rejected by the 8% cap; **98 of 189 (51.9%)**
  gate-passing signals die at the level stage; survivors are "disproportionately those
  whose nearest pivot happened to be close"
- `[doc]` §12.5 — cost in R is a hyperbola in stop width: 5.00% → 0.11R, 0.65% → 0.83R
- `[doc]` §11.3 — the R:R < 1 cohort, which is a **proxy for a wide stop**, was the book's
  only profitable one (24 trades, +₹10,585, 63% win)
- `[doc]` §12.5 — tight stops also *overshoot* −1R, realising −1.70R below 0.25× daily range

⇒ **The cap systematically rejects the cheap, profitable cohort and retains the expensive,
losing one.** It is not a neutral geometry filter with a side effect.

Magnitude, from our own numbers: backtest uncosted −0.065R vs paper costed −0.303R is a
0.238R gap against a 0.11R median cost estimate. The **residual ≈ 0.13R is composition** —
the traded book's stops are narrower than the corpus median (2.13% chased vs 5.33% clean).
That is more than half of the total gap, from one filter, and **removing the cap is not on
any tier of our plan.**

⚠ Governance caveat, which our own rule demands: the "wide stops are good" evidence is 24
trades and those 24 rows **no longer exist in the DB** (§2). It is corroborated by an
identity and by the overshoot finding, which is why it is worth testing — but the R:R
reversal is exactly the lesson that an identity plus a small sample burns you. **Run the
sweep (cap at 8 / 12 / 16 / none, reporting mean R, cost-in-R and n) before changing
anything.**

### 4.5 ⭐ Breadth is the dimension the architecture never considered

`IR ≈ IC × √breadth`. At ~60 positional trades a year and an optimistic IC of 0.02,
`IR ≈ 0.02 × √60 ≈ 0.15`. **A perfectly executed version of the current system is not
investable.** `[derived]`

This is also the mechanical reason nothing has ever cleared our promotion bar, and it is
not fixable with better signals — only with more independent bets: more names, shorter
holds, more decisions. Which leads directly to §5.2.

---

## 5. What every reviewer missed

### 5.1 The evidence base under both reviews no longer exists

Every P&L number the panel reasons from — 105 closed positions, −₹12,369, beta +0.92,
the 24-trade R:R cohort, the 40 positional trades, 1,664 `cas_daily` rows across 8
sessions — comes from tables that today hold **0 positions rows and 1 CAS session** (§2).
The 2026-09-07 `DATABASE_URL`-into-pytest incident took the book of record, and only
`stocks` and `ohlcv_1d` were recovered.

Claude's §4.5 comes closest ("category-1 failure") but treats it as a process defect. It
is more than that: **it is the reason most of the panel's recommendations cannot be
executed as written**, because the cohorts they want re-partitioned are gone. It also
means every forward-evidence loop still listed as open in `docs/PHASES.md` (momentum-retune
promotion, pair df-vs-adf) is **dead and does not know it**.

⇒ **The highest-priority engineering item is not on anyone's tier list: an append-only
trade ledger with off-box nightly export.** A day's work, and the precondition for every
other item being worth doing.

### 5.2 The tension nobody named: at ₹1 lakh, cost economics and statistical validation pull in opposite directions

- **Cost pushes toward concentration.** Cost-in-R = round-trip bps ÷ (100 × stop width %),
  and the DP charge is a **flat ₹15.34** per delivery sell. So bps falls as position size
  rises: 100 × ₹39 pays 61.6 bps against 22.4 bps for 400 × ₹2,500. Fewer, larger positions
  are strictly cheaper.
- **Validation pushes toward breadth.** `IR ≈ IC × √breadth`, and at ₹1L with a 5% median
  stop you can hold 2–3 positions ⇒ 100–150 trades/yr ⇒ SE on the annual mean R ≈ 0.13R.

**You cannot have both at this capital.** The 3-position cap we built for D4 makes the cost
side better and the validation side *worse*, and nothing in our plan acknowledges the
trade-off.

The honest structural conclusion: **single-name delivery swing trading at ₹1 lakh is not a
validatable strategy class, independent of whether it has edge.** Three escapes, ranked by
how much of our infrastructure transfers whole:

1. **Breadth from time, not names** — an instrument where one decision carries the book
   (index / ETF / basket). Validation becomes a time-series problem with ~750 daily
   observations instead of 25 trades. Almost all of the execution and risk stack transfers.
2. **Go where the measured effect is** — the closing-auction overnight reversal
   (ρ = −0.272, 90% day-block interval excluding zero) is the **only directional result the
   programme has ever produced that survived an interval**, it is cross-sectional so it
   generates breadth naturally, and it is *microstructure* rather than technical analysis —
   territory that is far less mined than forty years of daily-bar TA on liquid equities.
   ⚠ Its data was destroyed too: `cas_daily` is back to 1 session, so the ≥30-session
   re-run starts from scratch and accrues only in real time. **Start it now.**
3. **Shorter holds, wider universe** — more breadth, but costs bite harder per trade.

### 5.3 Nobody costed the recommendation all five made

All five converge on "build cross-sectional ranking." A ranker needs a daily, full-universe,
**point-in-time** feature panel. We currently have CA-unadjusted prices, sector on 12.5% of
names, 51 rows of index history and 17 of VIX. A ranker built on that would rank
contaminated inputs — using features `factor_sweep` has already shown to be flat (§3.1).
**Sequence: durability → data plane → point the existing IC machinery at our own score →
then decide about a ranker.** Kimi gets closest ("restore pipelines first, analytics
second") but never connects it to the ranking recommendation.

### 5.4 Two governance edits that cost nothing and unblock three items

**(a) Split the freeze.** `FROZEN-BEHAVIOUR` (changes what the strategy does — sign-off,
backtest regression, DSR bar, Rust fixtures) versus `FROZEN-CONTRACT` (fixes a divergence
between code and spec with no intended behavioural change — parity regression and a diff
review, ship in a day). The backtest horizon cap, the level-policy unification and the
directional alert are all the second category and are currently queued behind a bar
designed for hypotheses. **We are paying promotion-bar prices for bug fixes.**

**(b) Make the burden of proof asymmetric, explicitly.** "No flip on an argument" was
correct after two reversals, but applied symmetrically it became a ratchet: unjustified
behaviour already in the code is retained on "not significant" while removal needs t ≈ 3.6.
The rule should read: **the bar applies to ADDING behaviour; REMOVING unjustified behaviour
requires only the absence of evidence for keeping it.** That single line resolves the
positional-class question, the ADX-schedule question and the FII/DII-in-the-scorer question
with no new research.

---

## 6. Corrections owed to our own documents (W1)

| Document | Claim | Reality |
|---|---|---|
| `CLAUDE.md` | "The index backfill is already done" | `[db]` 51 rows |
| `CLAUDE.md` | "CAS Stage-1 accrual finished HEALTHY: 1,664 rows across 8 sessions" | `[db]` 43 rows, **1 session** |
| `CLAUDE.md` / `PHASES.md` | forward-evidence loops (momentum retune, pair df-vs-adf) "continue post-close" | `[db]` `positions` = 0 — they cannot accrue; restart or close them |
| `SYSTEM_REVIEW_FOR_QUANT.md` §11.1 | headline corpus quoted undivided | must be split BUY/SELL; 57% may be untradeable (§4.3) |
| `POSITIONAL_REVIEW_FOR_QUANT.md` §9.4 | stop-width gradient | ✅ challenge tested and refuted — annotate as unwinsorized-verified (§7) |
| both | live-tape figures | annotate: derived from a book destroyed 2026-09-07, not currently reproducible |

---

## 7. The panel's sharpest challenge to our own numbers — tested, and REFUTED

Claude's §3.1 is the best single piece of adversarial reasoning in the ten reviews, and it
argues our positional stop-width gradient is an artifact of our own winsorizer. The
mechanism: with a flat +15% target, `R at target = 15 / stop_width%`, so `WINSOR_R = 10`
bites **only below a 1.5% stop** — inside the 0–2% bucket and nowhere else. Predicted
magnitude: *"~16 winners in that bucket, half of them clipped by ~4R → ≈0.27R of measured
mean, which is the entire reported −0.257R."*

`[code]` The mechanism is real — `positional_probe.py:170` winsorizes the mean and reports
the median raw. So I re-ran the probe (250 names, 430 gate-passing positional panels)
reporting the winsorized mean, the **raw** mean and the clip count side by side. `[corpus]`

| Stop width | n | mean R (winsorized) | **mean R (raw)** | **clipped** | median R | win |
|---|---:|---:|---:|---:|---:|---:|
| 0–2% | 119 | −0.251 | **−0.222** | **3** | −1.000 | 13.4% |
| 2–4% | 114 | −0.027 | −0.027 | 0 | −1.000 | 19.3% |
| 4–6% | 68 | +0.153 | +0.153 | 0 | −1.000 | 32.4% |
| 6–10% | 74 | +0.103 | +0.103 | 0 | −1.000 | 35.1% |
| 10%+ | 16 | +0.543 | +0.543 | 0 | +1.084 | 62.5% |

**Verdict: the challenge is correct in mechanism and wrong in magnitude by ~10×.** Only
**3 of 119** trades in the tight bucket were clipped at all, and unwinsorizing moves the
mean from −0.251 to −0.222 — it does not change the sign, the ordering, or the conclusion.

Why the prediction over-shot: `R at target = 15/w` only applies to trades that **reach**
the target, and at a 13.4% win rate in that bucket most winners exit at the 30-day cap or
part-way, not at +15%. The clip is rare, not systematic.

**The gradient stands, and it may now be cited unwinsorized** — with two round-2 caveats
stamped on it: the 0–2% bucket is **not live-reachable** (§12.1), and harness defect #4
flatters tight stops so the true gradient is steeper than shown. ⚠ **And this table plus
§7.1's five variants plus §4.4's proposed sweep are a 14-cell search with no trial count —
the exact sin the DSR bar exists to prevent (round 2, Claude). The sweep in §13 is
pre-registered for that reason; "the accidental rule beats the intended one" is a five-cell
search reporting its best cell at t = −1.41 and must not be cited as a finding.** ⚠ The panel's *other* two
caveats on this table remain unanswered and should be: stop width is a volatility proxy
(regress R jointly on stop width, ATR%, breakout body ratio and price level before calling
it a stop finding rather than a volatility finding), and the 10%+ bucket is n=16.

### 7.1 Two further results from the same run, neither of them expected

**(a) The accidental rule beats the intended one.** On identical panels, the flat-5% stop
that `pipeline.py` and `backtest/engine.py` fall back to *by accident* (§1 #6) outperforms
the EMA20 stop that `signal_service` applies deliberately:

| rule | n | mean R | win | block-bootstrap Sharpe (90%) |
|---|---:|---:|---:|---|
| EMA20 stop, no horizon | 391 | −0.016 | 24.6% | −0.003 [−0.109, +0.079] |
| EMA20 stop, 30-day cap | 367 | **−0.087** | 29.4% | — |
| flat-5% stop, no horizon | 425 | **+0.091** | 28.9% | +0.050 [−0.052, +0.147] |
| flat-5% stop, 30-day cap | 395 | +0.035 | 34.9% | — |
| swing rules, same names | 85 | **+0.221** | 44.7% | +0.125 [−0.064, +0.280] |

Paired on 387 identical panels: **mean ΔR = −0.116, t = −1.41** in favour of flat-5%. Not
significant — but the panel advised unifying the stop rule "based on reproducibility, not
on which looks better," and it is worth knowing that the rule we ship live is the worse of
the two on our own corpus. **No bootstrap interval excludes zero for any variant.**

**(b) The 8% cap evidence, on the positional side.** `[corpus]` The best-performing bucket
in the table above is the widest (10%+, +0.543R, 62.5% win) and the worst is the tightest —
which is exactly the direction §4.4 predicts. Applying the swing rules' 8% cap to these
same panels would reject **234 of 430 (54.4%)**. That is direct, independent support for
running the stop-cap sweep, on a corpus that still exists.

## 8. ⛔ SUPERSEDED — the original plan (kept for the record; the live plan is §13)

**Week 0 — stop the bleeding (no research value, blocks everything else)**
1. Append-only trade ledger + nightly off-box immutable export (§5.1)
2. Restart CAS accrual and intraday capture **today** — both accrue only in real time (§5.2)
3. Fix the six document/reality conflicts in §6

**Week 1 — repairs that need no hypothesis (after the freeze split, §5.4a)**
4. One `LevelPolicy`: make `ema20_daily` required, delete the fallback, let the type checker
   enumerate the call sites (§1 #6)
5. Enforce the validity horizon in the backtest; apply the existing fee + fill model to it
6. Directional entry-zone alert — wire the `cross_up`/`cross_down` already in the file

**Week 2 — the four read-only tests, all on data we hold, none touching the freeze**
7. **Split the corpus by direction** and re-report everything (§4.3) — hours, and it
   determines whether the headline describes a tradeable strategy
8. **Write down the null** — random-selection and buy-and-hold on identical barriers (§4.2)
9. **Stop-cap sweep** at 8 / 12 / 16 / none (§4.4) — the largest single recoverable term
10. **Point `factor_sweep`'s machinery at our own 15 factors and the composite score** — the
    one genuine gap in §3.1, and the decisive test of whether the scorer carries information

**Then, and only then, the strategic decision (§5.2)** — whether to keep searching for a
stock-selection edge at a capital level where no such edge can be validated, or to move
breadth from names to time, or to follow the only measured directional effect we own into
microstructure.

**Re-scope cycle 2 now** (§4.1) — it is an operational-correctness rehearsal. Say so in
`PHASES.md` before it starts, or it guarantees either an indefinite hold or a promotion on
noise.

---

## 9. What the panel confirmed is genuinely good — worth recording

Independently, across five reviewers with different priors: the validated deflated-Sharpe
bar (rejecting a known null **and** detecting a planted edge, with the power arm), the
Newey–West H0 canary that reproduces the inflation before correcting it, §11.4 publishing
three defects in our own instruments that all flattered the results, the paired designs on
identical panels, read-only probes that import the frozen engine rather than reimplementing
it, pre-registration, the provenance tagging, reverting the R:R floor in 24 hours and then
finding the structural explanation, and "clamp what you report, never what you decide."

Kimi's summary is the one to keep: *"your architecture is good enough to trust its own
measurements; your signals were never good enough to deserve it."* The apparatus is the
asset. It is also, per §5.2, transferable to a strategy class where the arithmetic works.

---
---

# PART II — THE MEASUREMENTS

## 12. First measurements — the reachable cohort, dispersion and cost

### 12.1 ⭐ The corpus contains trades the live order path would refuse — and they are the worst cohort

`[code]` The per-position notional cap is **unconditional** in the paper broker
(`risk_engine.notional_cap_reason`, no mode gate, called on every order), and it is
algebraically `w ≥ risk_pct / leverage` = **2%**. `[code]` `backtest/engine.py` applies **no
cap** — only `compute_quantity`. So every corpus statistic includes ~30% of trades the live
system rejects.

Restricting to the live-reachable set — a **pre-specified** restriction derived from an
identity about a rail already in production, not a searched partition:

| cohort | n | mean R | sd(R) | n needed @ t=2 for +0.10R | median R | win | total R |
|---|---:|---:|---:|---:|---:|---:|---:|
| ALL (what the corpus reports) | 385 | **−0.032** | 2.088 | 1,744 | −1.000 | 23.4% | −12.2 |
| **REACHABLE (w ≥ 2%)** | 271 | **+0.084** | 1.844 | 1,360 | −1.000 | 29.2% | +22.6 |
| REJECTED BY THE CAP (w < 2%) | 114 | **−0.306** | 2.566 | 2,633 | −1.000 | 9.6% | −34.9 |

**The sign flips — but the interval does not exclude zero (§12.4), so this is a corrected
measurement, not a discovered edge.** ⚠ Caveats, all of which matter: gross of costs (friction at these widths
is ~0.05–0.11R, so net is ~0 to +0.03R); the cohort is smaller; and per R2-33 the rejected
bucket is *flattered* by harness defect #4, so its true performance is worse than −0.306R.
Bootstrap interval in §12.4.

### 12.2 ⭐ The dispersion lever, quantified

Required n scales with σ_R², so σ_R is a first-class objective and nobody was treating it as
one. From the table above: **removing the sub-2% cohort raises mean R by 0.116R *and* cuts
required n by 22%** (1,744 → 1,360), because the rejected cohort has both the worst mean and
the **highest dispersion**. Two objectives, one intervention.

For the swing corpus, σ_R = 1.489 `[derived]` from §11.1 (SE = 0.065/1.94, × √1975):

| σ_R | n to detect +0.10R at t=2 | years at 125 trades/yr |
|---:|---:|---:|
| 1.489 (swing today) | 887 | 7.1 |
| 1.844 (positional, reachable) | 1,360 | 10.9 |
| 2.088 (positional, all) | 1,744 | 14.0 |
| 1.000 | 400 | 3.2 |
| 0.800 | 256 | 2.0 |

Two consequences. **(a) Positional is the *less* validatable class by ~2×** (R2-35) — a reason
to drop the relabel that is independent of expectancy, and it cuts against §9.6's "not
significant either way." **(b) The excess dispersion is the R:R identity** (R2-1): R:R = k/w
varies 1:17 across the corpus, so a constant-R:R target compresses σ_R directly. **D5 already
proved a constant-R:R target costs ~nothing in expectancy** (every paired ΔR negative,
\|t\| ≤ 0.65) — it was closed on the wrong objective. **Reopen it as a power decision** (R2-5).

### 12.3 ⭐ The CAS cost go/no-go

`[derived]` A daily-turnover strategy pays the flat ₹15.34 DP charge on every exit:

| concurrent positions | DP charges/yr | as % of ₹1 lakh |
|---:|---:|---:|
| 1 | ₹3,835 | 3.8% |
| 2 | ₹7,670 | 7.7% |
| 3 | ₹11,505 | **11.5%** |

`[code]` `fees.py:228-231` charges it on **every** delivery sell with **no BTST exemption**, so
these are the figures our own model reports. **Whether Zerodha exempts BTST (shares never
enter the demat) is the entire go/no-go for the closing-auction escape, and it is one support
ticket.** Establish it *before* CAS is ranked as an escape — but do **not** pause the accrual
while establishing it (R2-26).

### 12.4 Bootstrap interval on the reachable cohort — the flip does NOT establish an edge

Moving block bootstrap, 2,000 resamples, blocks of 8, same probe:

| cohort | observed Sharpe | 90% interval | Sharpe ≤ 0 in |
|---|---:|---|---:|
| ALL (uncapped corpus) | **−0.011** | [−0.120, +0.076] | **57%** of plausible histories |
| **REACHABLE (w ≥ 2%)** | **+0.045** | [**−0.061**, +0.148] | **25%** of plausible histories |

**The honest reading.** Applying the notional-cap identity moves the point estimate from a coin
flip to mildly positive, and more than halves the probability of a negative Sharpe (57% → 25%).
**It does not produce an interval excluding zero, so it establishes no edge.** What it establishes
is narrower and still worth having:

1. **A measurement defect, not a discovery.** Every corpus statistic we have ever quoted includes
   ~30% of trades the live order path unconditionally refuses. That is a bug in how we measure,
   and it must be fixed regardless of what the corrected number turns out to be (§13, Week 1 #10).
2. **The corrected baseline is ~0, not negative.** "The engine destroys money" and "the engine is
   a coin flip after its own rails are applied" are different diagnoses, and the second is the
   supported one.
3. **The dispersion result is unaffected** and is the durable half: the rejected cohort has both
   the worst mean *and* the highest variance, so removing it cuts required n by 22% no matter what
   the mean does (§12.2).

⚠ And it remains gross of costs. At these stop widths friction is ~0.05–0.11R against a +0.084R
gross mean, so **net expectancy is approximately zero** — comfortably below the +0.15R kill line in
§14. On its own evidence this cohort does not clear the bar to be traded; it clears the bar to be
**measured correctly**.

## 12.5 ⭐ Required gross edge — the synthesis this document kept circling

Three numbers this document already had — §4.1's *edge required to be detectable at a given n*,
§12.2's *σ_R drives required n*, and Week-0 #6's *friction per trade* — are three inputs to **one**
number, and it never composed them (Claude, round 3):

> **required gross edge per trade = friction(w) + MDE over the horizon you are willing to wait**

`[derived]`, MDE at t=2 over three years of accrual:

| class | friction | σ_R | trades/yr | n over 3 yrs | MDE @ t=2 | **required gross** |
|---|---:|---:|---:|---:|---:|---:|
| swing, reachable band | ~0.11R | 1.489 | ~125 | 375 | +0.154R | **+0.264R** |
| positional, reachable | ~0.08R | 1.844 | ~60 | 180 | +0.275R | **+0.355R** |
| *benchmark: Sharpe 1.0* | — | — | 250 | — | — | *delivers +0.094R* |
| *benchmark: Sharpe 0.37 (median of the replication literature)* | — | — | 250 | — | — | *delivers +0.035R* |

**Both classes require 2.8× and 3.8× a world-class edge merely for that edge to be VISIBLE inside
three years — before anyone asks whether it exists.** That is §4.1's cycle-2 argument applied to the
research corpus rather than to the paper book, at a much larger scale, and it reaches the same
conclusion.

⚠ **CORRECTED 2026-09-11 (found while briefing round 4): this table solves for the WRONG n, and
there are TWO required-edge numbers, not one.** The +0.264R above assumes **3 years of forward
accrual at the LIVE book's rate** (~125 trades/yr, 2–3 concurrent positions). But the research
corpus does not accrue at the live rate — the backtest trades the whole universe, and **1,975 trades
over 3.19 years is ~619 trades/yr.** Solving on the corpus instead:

| basis | span | n | MDE @ t=2 | required gross |
|---|---:|---:|---:|---:|
| research corpus, as truncated today | 3.19 yr | 1,974 | +0.067R | +0.177R |
| research corpus, **un-truncated to 2019-10** | 6.94 yr | ~4,300 | +0.045R | +0.155R |
| live book, 3 yrs forward (the original row) | 3 yr | 375 | +0.154R | +0.264R |

⛔ **ALL THREE ROWS ABOVE ARE WRONG — CORRECTED 2026-09-11 (round 4, Claude; Kimi reached the same
conclusion from a different, incorrect derivation). They use NOMINAL n. I accepted the
effective-breadth correction in round 2, applied it to the live book in round 3, and failed to apply
it to the corpus — the identical failure mode, twice.** And the corpus is **more** overlapped, not
less: ~620 trades/yr at 5-day holds is **~12 concurrent positions** against the live book's 2–3.
At ρ̄ = 0.5, `1 + (m−1)ρ̄`:

| basis | nominal n | m | **effective n** | MDE @ t=2 | **required gross** |
|---|---:|---:|---:|---:|---:|
| corpus, truncated | 1,974 | ~12 | 304 | +0.171R | **+0.28R** |
| corpus, **un-truncated** | ~4,300 | ~12 | 662 | +0.116R | **+0.23R** |
| live book, 3 yr forward | 375 | 2.5 | 214 | +0.203R | **+0.31R** |

**The corpus advantage falls from 3.4× to 1.7×.** The structural claim survives — the corpus still
wins — but §12.5's own uncomfortable sentence gets considerably harder to escape.

⚠ **And the BENCHMARK must move with the hurdle** (ChatGPT R4, a real internal inconsistency): the
"+0.094R from a Sharpe-1.0 system" figure is itself computed under independence. Under the same
`m=2.5, ρ̄=0.5` it becomes **+0.125R**, and under the corpus's `m=12` it becomes **+0.240R**. *You
cannot use independent-trade mathematics to set the hurdle and correlated-trade mathematics to argue
the hurdle is hard.* Corrected ratio: **2.52×**, not 2.80×. The conclusion holds, ~10% weaker.

⭐ **THE CONSEQUENCE I WROTE AND DID NOT ACT ON (Claude R4 — the sharpest sentence of four rounds).**
§12.5 says the Week-2/3 tests are unlikely to change the decision *"regardless of their outcome"* —
and then keeps all nine. If required gross is +0.23R to +0.31R and the benchmark is +0.125R, **the
answer is fixed by arithmetic, and the only tests that can move it are ones that change FRICTION,
σ_R, or BREADTH.** Every other test measures the edge, which cannot be validated at any outcome.
⇒ **The plan is reorganised around those three inputs in §13a; most of the original list falls away.**

⭐ **This resolves the §5.2 tension rather than restating it.** The corpus can detect an edge the
live book can never validate — so **all validation belongs on the corpus, and the live book confirms
operational correctness only.** That is exactly §4.1's cycle-2 conclusion, now generalised to the
whole programme, and it is a much more useful statement than "₹1 lakh is not validatable."

⭐ **AND THE CORPUS IS TRUNCATED FOR TWO REASONS THAT ARE BOTH DEAD.** The swing corpus starts
**2023-07-03** because (a) `ohlcv_1d` once began there — a **hard data blocker RESOLVED 2026-09-08**,
three days before the corpus was reported, when the bhavcopy acquisition took the table back to
**2019-10-01**; and (b) it was described as "the CA-clean window from 2023-07-03", a claim our own
memory records as **⛔ FALSE**. ⇒ **Un-truncating roughly TRIPLES the corpus, 1,975 → ~4,300 trades,
using data already in the table.** Added as Week-0a #6.

⚠ **This also defuses a collision between two round-3 recommendations that no reviewer could see.**
Claude proposed freezing a **2024-01+** holdout. Against the corpus *as truncated*, that leaves a
development set of **six months** — fatal. Against the un-truncated corpus it is comfortable:
**dev 2019-10 → 2023-12 (n ≈ 2,631, MDE +0.058R)** and **holdout 2024-01 → 2026-09 (n ≈ 1,665,
MDE +0.073R)**. **The holdout is only affordable if the corpus is un-truncated first** — so 0a.6 must
precede 0a.1.

⚠ **And these figures are optimistic, because they assume independent trades.** R2-11 (effective
breadth) was accepted in round 2 and then **not propagated into §12.2** — an unforced inconsistency
between two items both marked ✅. With `m` concurrent positions at average pairwise correlation
`ρ̄`, the variance of the mean inflates by `1 + (m−1)ρ̄`:

| concurrency | ρ̄ | variance inflation | 7.1 years becomes |
|---:|---:|---:|---:|
| 2.5 (cycle-2 shape) | 0.30 | 1.45× | 10.3 yr |
| 2.5 (cycle-2 shape) | 0.50 | 1.75× | **12.4 yr** |
| 23 (cycle-1 sampler) | 0.50 | 12.0× | **85 yr** |

That last row is why the wide sampler can never validate anything, at any horizon — a fact worth
more than the 30-day clock it was built to feed.

**What this table replaces and reconciles.** It **supersedes KILL LINE 1** (whose +0.30R sat just
above the worst reachable friction and therefore fired on nothing) and it **reconciles the four
unreconciled thresholds** this document had accumulated — +0.094R (§4.1 benchmark), +0.10R (§12.2
power table), +0.15R (KILL LINE 4) and +0.30R (KILL LINE 1) — by deriving one and letting the rest
follow. **It can be produced this week from numbers already in hand.** It also says, uncomfortably,
that the nine Week-2/3 tests are unlikely to change the decision *regardless of their outcome* —
which is worth knowing before spending three weeks on them.

## 12.6 ⭐ Survivorship — the bias is in our own universe query, not the database

Claude, Kimi and ChatGPT independently flagged survivorship — Kimi noting the word "appears nowhere
in 14 sections," which was true and fair. **Measured today, the database is NOT the problem; two of
my own probes are.** `[db]`

| check | result |
|---|---|
| `stocks` total rows | **3,392** |
| of which `is_active = false` (delisted / suspended, **retained**) | **2,070** |
| price series whose LAST bar is > 90 days old (de-facto dead names **with history**) | **542** |
| series starting after 2019-11 (late listings, correctly absent before listing) | 1,859 |
| a listing date exists (`stocks.listed_on`) | ✅ — but there is **no** `delisted_on` / `suspended_on` |

So the corpus **can** see the losers. What cannot see them is the universe selector I wrote:

```sql
-- positional_probe.py:92  AND  engine_selectivity_probe.py:106
WHERE time > now() - interval '180 days'      -- ⛔ excludes all 542 dead names
GROUP BY stock_id HAVING count(*) > 100
ORDER BY percentile_cont(0.5) WITHIN GROUP (ORDER BY close * volume) DESC  -- ⛔ ranks on TODAY's
LIMIT 250                                      --    liquidity, applied to 2019-2026
```

**Two defects in one query, in both probes**: requiring recent bars **imposes** survivorship that the
data does not have, and ranking by *current* liquidity is a **look-ahead selection** of the names that
turned out to be liquid. Every figure in §7, §12.1 and §12.4 inherits both. `squeeze_study.py:65`
filters `s.is_active` and is therefore explicitly survivor-only. ✅ **`factor_sweep.py` is CLEAN on
this axis** — its `adv20 >= :min_adv` floor is computed per row from a rolling window, which is
point-in-time correct (it carries the CA defect, not this one).

⇒ **The repair is one query, not a data-acquisition project.** Rank liquidity in a trailing window
**as of each panel date**, and admit a name whenever it had bars then — the delisted names are
already in the table. Kimi's and ChatGPT's proposed NSE symbol-master reconstruction is not needed.
**Direction of the bias: upward.** Every historical expectancy number is flattered, so the true
figures are worse than measured — including §12.1's sign flip.

## 12.7 ⛔ Two plan-blocking data gaps, found by query

Kimi asked whether the CA-event history exists for 2019–2023 before un-truncating, and whether the
composite score is reproducible on the un-truncated panel. Both questions were right and **both
answers are worse than it guessed.** `[db]`

| table | rows | span | consequence |
|---|---:|---|---|
| `corporate_actions` | **0** | — | ⛔ **The CA adjustment layer (Week 0 #1) has NO event source at all** — not for 2019–23, not for any period. It is not "build the table," it is "find the data." **0a.6 (un-truncation) is gated behind this**, because un-truncating without it imports contaminated years while fixing the truncation. |
| `fii_dii_daily` | **4** | 2026-09-08 → 09-10 | ⛔ **Test #16 is infeasible as specified, on ANY window.** `confluence.py:121` feeds `fii_dii_factor(fii_net_5d, dii_net_5d, …)` into the composite, and three days of flow history cannot reproduce a historical composite score. Kimi predicted this for the un-truncated panel; it is true of the truncated one too. |
| `stocks.sector` populated | 165 / 1,322 | — | 12.5% coverage — the sector-RS input to the composite has the same problem, one order of magnitude less severely. |

**Required, pre-registered before #16 runs, not discovered mid-test:** a **price-only composite
variant frozen by commit hash**, with the FII/DII and sector-RS terms explicitly excluded and the
exclusion recorded. `factor_sweep.py` sidestepped this by using price-only features; the production
composite cannot. ⚠ **The variant is a different estimand from the shipped score** and the kill line
must say so — closing on a price-only variant closes *that* variant, not the engine as specified.

⭐ **The generalisable lesson, and it is the fourth time this has bitten:** three rounds of reviewers
guessed at survivorship, CA coverage and universe construction, and every single time the answer
required a query rather than an argument. **A claim about the data plane is a question, not a
finding, until somebody runs the SQL.** That is now the standing instruction in the round brief.

## 12.8 ⛔ The headline ratio was malformed — and fixing it inverts the conclusion

**The single most consequential correction of five rounds, and it is against my own headline.**

`required gross = friction + MDE` **includes friction**. A Sharpe ratio is, by convention, computed
on returns **net** of costs. **§12.5 therefore compared a GROSS requirement against a NET benchmark
— counting friction on one side of the ratio only.** `[derived]`

⚠ **And I introduced a second inconsistency myself:** the benchmark used **N = 250 trades/yr** while
the live book's accrual row used **N = 125**. Different N on the two sides of the same comparison.

Consistent gross-versus-gross, ρ̄ = 0.5, deployed book at m = 2.5:

| basis | effective n | MDE (gross) | a Sharpe-1.0 book **grosses** | detectable? |
|---|---:|---:|---:|:--|
| live book, 3 yr forward | 214 | +0.203R | +0.286R | **YES, ×1.41** |
| corpus, truncated | 304 | +0.171R | +0.189R | **YES, ×1.11** |
| corpus, **un-truncated** | 662 | +0.116R | +0.189R | **YES, ×1.63** |

⭐ **"Both classes need 2.8–3.8× a world-class edge merely to be visible" is WRONG. A world-class
edge is detectable with an 11–63% margin.** We are **standing on the line, not far from it.**

**This changes what the plan is FOR.** "You need 2.5× a world-class edge, so the answer is fixed by
arithmetic" licenses closure — and §13c's cut was justified partly on it. *"You can just barely detect
a world-class edge and nothing weaker"* licenses the opposite: it makes **un-truncation, the σ_R work
and the friction measurement DECISIVE rather than merely surviving**, because they are the three
things that move you across a line you are standing on.

⚠ **State the convention explicitly, because the answer swings on it.** If the benchmark is defined
*gross* instead, a Sharpe-1.0 system nets 0.015R against a 0.116R MDE and fails by ~8×. **The
programme's fate currently rests on an unstated convention. It is NET. Recorded.**

⚠ **The σ_R lever is weaker than §12.2 implies** (Claude): a Sharpe-1.0 system's mean R **also**
scales with σ_R, so cutting σ_R shrinks the hurdle *and* the benchmark together. Only the friction
term is fixed in R at a given stop width. Cutting σ_R 26% narrows the required-minus-benchmark gap
from ~0.028R to ~0.021R — real, but roughly **a quarter** of the improvement §12.2 suggested.

⚠ **My own caveat, which cuts the other way and nobody raised:** the corpus takes *every* signal
while the deployed book takes the best 2–3 per day. If the gate or the picker adds anything, **the
corpus population mean is LOWER than the deployed book's**, so "can the corpus detect a Sharpe-1.0
deployed book" is not well-posed. The well-posed question is whether the corpus can detect the gross
**population** edge, and the mapping between the two is unmeasured. This is the strongest remaining
argument for pessimism and it is not in any reviewer's version.

### 12.8b ⛔ Half the friction term is an unmeasured assumption

`[code]` Computed against the **real fee model** (`roundtrip_charges`, delivery, ₹500 name):

| stop width | ₹1L position | explicit charges | bps | **cost in R** |
|---|---:|---:|---:|---:|
| 2% | ₹1,00,000 | ₹236 | 23.6 | 0.118 |
| **5% (median)** | ₹40,000 | ₹102 | **25.5** | **0.051** |
| 10% | ₹20,000 | ₹58 | 28.9 | 0.029 |

**§12.5 uses friction ≈ 0.11R at the median 5% stop. The explicit charges are 0.051R.** The other
**~0.06R — more than half the friction term — is a slippage assumption that has never been measured
on the corpus**, and it drives every conclusion in this document, including a margin now known to be
11–63% (Claude). ⇒ **Week 0 #5 (fee/slippage reconciliation) goes BACK into the eight-item cut.**
It was dropped while §12.5 named friction one of the only three levers that can move the answer.

## 12.9 ⭐ Capital sensitivity — computed against our own fee model

The user asked what changes at ₹1.5L / ₹2L / ₹3L. Answer: **much less than intuition suggests, and
the one thing that changes a lot is not the swing book.**

### What does NOT change: slot count is scale-free

`slots = heat cap ÷ risk per trade = 6% ÷ 2% = 3`, **at every capital level.** Capital cancels, the
same way it cancels in the notional-cap identity (§1 #10). ⭐ **Capital does not buy positions — the
risk rules do.** Running 9 slots at ₹3L means cutting risk to 0.67%/trade, **which you could equally
do at ₹1L.** What capital actually buys is the *affordability* of finer slicing: at ₹1L a 9-slot book
puts ₹13.3k per position and the flat DP charge becomes 11.4 bps; at ₹3L the same 9 slots are ₹40k
each and DP is 3.8 bps.

### What barely changes: friction on the swing book

| capital | position @ 5% stop | bps | cost in R |
|---|---:|---:|---:|
| ₹1.0L | ₹40,000 | 25.5 | 0.0511 |
| ₹1.5L | ₹60,000 | 24.3 | 0.0485 |
| ₹2.0L | ₹80,000 | 23.6 | 0.0472 |
| ₹3.0L | ₹1,20,000 | 23.0 | 0.0460 |
| ₹10L | ₹4,00,000 | 22.1 | 0.0442 |

**Tripling capital saves 2.5 bps — 0.005R per trade, about 10% of explicit friction.** STT at ~20 bps
round trip dominates and is purely proportional; only the flat ₹15.34 DP scales away.

### What DOES change a lot: the daily-turnover book

Annual DP drag at 3 slots:

| capital | swing (5-day holds) | **CAS (1-day holds)** |
|---|---:|---:|
| ₹1.0L | 2.30% | **11.51%** |
| ₹1.5L | 1.53% | 7.67% |
| ₹2.0L | 1.15% | 5.75% |
| ₹3.0L | 0.77% | **3.83%** |

⭐ **Capital helps the microstructure book enormously and the swing book almost not at all.**
⚠ **This corrects §12.3 as applied**, and corrects a round-5 error: ChatGPT's capital table applied
the **11.5% → 3.8%** figures to the strategy generally. Those are the **CAS** numbers. For the swing
book the correct figures are **2.30% → 0.77%**. Claude had this right.

### What capital does NOT buy: statistical power

| capital | slots | trades/yr | inflation | **effective obs/yr** | m_eff |
|---|---:|---:|---:|---:|---:|
| ₹1.0L | 3 | 150 | 2.00 | **75** | 1.50 |
| ₹1.5L | 4 | 200 | 2.50 | 80 | 1.60 |
| ₹2.0L | 6 | 300 | 3.50 | 86 | 1.71 |
| ₹3.0L | 9 | 450 | 5.00 | **90** | 1.80 |

⛔⛔ **STALE — EVERY CELL OF THE TABLE ABOVE WAS COMPUTED AT THE RETIRED ρ̄ = 0.5** (Kimi Catch 1,
confirmed cell by cell in §12.13a). Under the **measured** long-only ρ̄ ≈ +0.19, ₹3L buys **×1.63**
effective observations; under the mixed ρ̄ = −0.013 it buys ×3.26. **Neither is +20%.** ⭐ And the
causal attribution changes with it: the 3/4/6/9 ladder is **Policy B**, which cuts `risk_pct` and
**is available at ₹1L** — so breadth is bought by the risk policy, not by the capital (§12.13a).

~~⭐ **Tripling capital buys +20% effective observations.** Correlation strangles the rest — going 3→9
slots triples nominal trades and raises variance inflation 2.0→5.0.~~ ⚠ **Adjudicating the two
reviewers: Kimi said +6% (too low), Claude said +33% (too high). Measured: +20%.**
~~**The MDE wall does not move when you add cash.**~~ ⛔ **superseded — §12.13a.**

### The verdict on capital

**Adding ₹2L is a friction-and-CAS decision. It is not a validation decision and not an edge
decision.** ⚠ And the asymmetry that decides it: **if the paired-calibration test (Week-4 #22) shows
the corpus-to-live bias is real, more capital loses more money at exactly the same rate.**
⇒ **Ordering is strict: ship the eight (nine, with #5 restored) → run cycle 2 as the paired
calibration → then decide capital with the BTST answer and the bias number in hand.**

⭐ **The one qualitative change capital buys is a capability, not a scaling: the F&O door** (Claude).
Stock futures make the 57% SELL output tradeable; options open the covered-call / cash-secured-put
overlay — a documented, persistent, non-directional premium that reuses the risk and execution stack
while discarding the signal engine. ⚠ **But verify before acting:** at SEBI's raised contract values
and 15–25% SPAN + exposure margin, one stock-futures lot may need ₹2.5–4L, in which case ₹3L buys a
single undiversified lot and **the F&O door opens at ₹10L, not ₹3L.** ⇒ **run the existing lot-size
feasibility check across the whole capital ladder, not just at ₹1L** — same afternoon, and it
answers the capital question directly.

⚠ **And the framing that actually decides it, in ₹/day rather than R:** at 2% risk and ~125 trades/yr,
a system netting +0.09R/trade returns ~22% of capital — **₹22k/yr at ₹1L, ₹67k/yr at ₹3L.** Neither
pays for the engineering already done. **The capital level at which this programme has positive
expected value including your own time is probably ₹10L or above**, and that is a more useful thing
to know than the friction delta between ₹1L and ₹3L.

## 12.10 ⭐⭐ The three load-bearing assumptions, measured — and all three were wrong

Round 6 asked for evidence rather than argument. `backend/scripts/swing_dependence_probe.py`
(read-only, SELECT-only, frozen scorer and frozen `_simulate_trade` imported and CALLED) walked
**16,428 swing panels across 238 liquid names at stride 10** and measured what five rounds assumed.
**All three inputs were wrong, and all three in the same direction.**

| input | assumed (rounds 3–5) | **MEASURED** | effect |
|---|---:|---:|---|
| σ_R, swing | 1.489 *(back-derived from a t)* | **0.878** | required n falls **65%** |
| variance inflation | 1.75× live / **6.50× corpus** | **1.00×** | MDE improves up to **2.55×** |
| ρ̄ | **0.50** | **−0.013** | ⛔ **ROUND 7: measured on a 56%-SHORT book. Long-only it is ≈ +0.19 and inflation is 1.19–1.23× — the near-zero was a DIRECTIONAL CANCELLATION (§12.16 R7-A2)** |
| friction | 0.11R | **0.051R** explicit | §12.8b |

**Claude Q1 in full — the calendar-block bootstrap at all three block lengths**, so convergence is
visible rather than asserted. σ_R = 0.8776, iid SE = 0.0645, nominal n = 185:

| block | blocks | SE(mean R) | inflation vs iid | effective n | MDE @ t=2 |
|---:|---:|---:|---:|---:|---:|
| 10 days | 74 | 0.0644 | **1.00×** | 186 | +0.1289R |
| 30 days | 38 | 0.0650 | **1.01×** | 182 | +0.1300R |
| 60 days | 19 | 0.0510 | **0.62×** | 296 | +0.1020R |

⚠ **The 60-day row is published because it is an anomaly, not because it helps.** An inflation
*below* 1.0 is deflation — it implies negative serial dependence — and on **19 blocks** it is far more
likely to be noise than signal. **10d and 30d agree at 1.00–1.01× and that is the result**; 60d is
under-blocked and should not be quoted. Convergence between 10d and 30d is the evidence Claude asked
for.

**Three independent measurements agree that dependence is nil:** §12.4's trade-block bootstrap on
positional gave 1.046×; this probe's **calendar-block** bootstrap on swing gives **1.00× at both 10-
and 30-day blocks**; and the **direct pairwise correlation of R across overlapping trades is −0.013
on 263 pairs.** ⭐ Claude's structural argument predicted exactly this and deserves the credit: **R is
a barrier-truncated, path-dependent transform, and truncation compresses correlation** — so ρ̄ on R
was never going to resemble ρ̄ on returns. Nobody tested it for three rounds.

### 12.10a ⭐ The headline inverts again — detectability stops being the constraint

| basis | n | MDE @ t=2 | required gross | Sharpe-1.0 grosses | detectable |
|---|---:|---:|---:|---:|---:|
| corpus, truncated | 1,975 | +0.0395R | +0.0905R | +0.1295R | **×3.28** |
| corpus, **un-truncated** | ~4,300 | +0.0268R | +0.0778R | +0.1295R | **×4.84** |
| live book, 3 yr | 375 | +0.0906R | +0.1416R | +0.1295R | ×1.43 |

⭐⭐ **The corpus is amply powered. "We are standing on the line" (§12.8) and "2.8–3.8× short"
(§12.5) were BOTH artifacts of two unmeasured assumptions.** And the deeper consequence:

> ~~**Detectability is no longer the binding constraint — FRICTION is.** The corpus can detect a gross
> edge of +0.027R to +0.040R, which is *below* the +0.051R of explicit charges. **Anything that nets
> positive is detectable with room to spare.**~~
>
> ⛔ **WITHDRAWN BY ROUND 7 (§12.16 R7-A3).** This row pairs a σ measured on `probe-185` with the
> corpus's n — forbidden by §16.1's sample-tag rule. On the **long-only** book (σ 0.957, I 1.21) the
> MDE is **+0.0714R, ABOVE the 0.051R of explicit charges.** ⭐ What survives: a Sharpe-1.0-class
> edge is still detectable at **×2.87**, so "can this ever be validated" is still answered yes and
> §12.5's "2.8–3.8× short" is still retired. **What does not survive is "with room to spare"** — the
> margin is **1.3×, not 4×.**

That retires the entire "can this ever be validated" question that consumed rounds 3–5. It was never
the real problem. ⚠ **And it makes the following far more uncomfortable:** on this sample the gross
mean is **−0.1489R with SE 0.0645 ⇒ t = −2.31** — a *significantly negative* gross edge on
185 trades. ⛔ **SUPERSEDED BY ROUND 7 (§12.16 R7-A): that t is carried by the 55.7% of trades that
are SELLs, which a cash-delivery account cannot hold overnight. BUY-only: n=82, −0.0992R, t = −0.94.
And on gap-clean windows alone (R7-I) the mixed figure itself falls to t = −1.79.**

~~The programme has been asking "can we detect an edge?" when the powered answer available was "the
sign is negative."~~ ⇒ **The powered answer on the tradeable book is "NOT DISTINGUISHABLE FROM ZERO,
and negative in expectation" — a materially different verdict, and it changes what KILL LINE 3 firing
would mean (§12.15).**

### 12.10b ⭐ The fat tails are an artifact of the R denominator

The **same 185 trades**, three units:

| unit | sd | skew | **excess kurtosis** |
|---|---:|---:|---:|
| **R** | 0.878 | +1.76 | **+8.19** |
| raw return, % | 3.169 | +0.43 | **−0.25** |
| return ÷ ATR20-at-entry | 1.267 | +0.40 | **+0.02** |

⭐ **The fat tails are manufactured by our own denominator.** In R the outcomes look violently
leptokurtic; the identical trades in **% are mesokurtic (−0.25)** and in **ATR units almost exactly
normal (+0.02)**. Stop-width CV = 0.51 (mean 4.43%, p5 0.48%, p95 7.64%) is the mechanism.
⇒ **Every MDE, every DSR calculation and the "kurtosis 11.46" bootstrap in this programme inherit a
tail their unit created.** Adopt Claude's fix: **keep R for position sizing; report in bps and ATR
units.** It is a reporting change, not a strategy change. ⚠ **Wording refined by ChatGPT §8, which is
right that "manufactured" overstates it:** R introduces *denominator-induced heteroskedasticity and
exaggerates tail shape*; it does not prove the strategy carries no tail risk.
⭐⭐ **AND THIS IS THE MOST PRODUCTIVE FINDING OF THE WHOLE EXERCISE, because in round 7 it
disqualified two of our own best results** — the RVOL coefficient at t = +3.67 and the stop-width
gradient at t = +2.30 both **vanish in raw return %** (§12.16 R7-J). `[measured]` 0 of 185 trades
were winsorized, so none of this owes anything to clipping (R7-F).

### 12.10c ⭐ Δ_select and the confidence curve — the answer to the original question

| confidence | n | mean R | median | win |
|---|---:|---:|---:|---:|
| 70–74 | 75 | −0.158 | −0.171 | 37.3% |
| 75–79 | 38 | −0.002 | −0.009 | 44.7% |
| **80–84** | 42 | **−0.292** | −0.520 | 35.7% |
| 85–89 | 27 | −0.150 | −0.197 | 40.7% |
| 90+ | 3 | +0.230 | +0.082 | 66.7% |

**Confidence is NOT monotone in outcome** — the 80–84 bucket is the *worst* in the book, and the only
positive cell has n=3. And **Δ_select = +0.045R, SE 0.153, t = +0.29** (top decile, conf ≥ 88, n=29).

⇒ **The score's top decile is statistically indistinguishable from the average gate-passer.** After
six rounds, that is the measured answer to *"sometimes I cannot select the right stock"*: **the
system's own ranking carries no selection premium to capture.**

⚠ **ROUND 7 — the conclusion holds but this test could not have established it** (Claude Finding C):
the decile contrast has **MDE +0.31R**, so it could not distinguish a spectacular edge from zero.
✅ **§12.16 R7-B re-runs it as a continuous rank statistic on all 185: Spearman ρ = −0.018, permutation
p = 0.807, and the test CAN detect ρ ≈ 0.147.** The answer is unchanged and is now properly powered.
⚠ Kimi Q7's proposed escape — that the 80–84 dip is a shorts artifact — is **REFUTED**: it is the
worst bucket in both directions (R7-B2). And the "only positive cell" (90+) contains **one** BUY trade.

### 12.10d The denominator chain, and the defect-#4 count

| stage | count |
|---|---:|
| panels scored (name × decision bar, 300-bar window) | 16,428 |
| clearing the ≥70% gate | **514 (3.13%)** |
| direction split | BUY 242 / **SELL 272 (52.9%)** |
| classified swing | 475 |
| **rejected at the level stage** | **289 (60.8% of swing)** |
| dropped as unadjusted CAs | 1 |
| **resolved trades** | **185** |

**Kimi Q4 — defect #4 counted: 2 of 185 = 1.08%.** Real but rare. ⚠ **This disciplines my own
round-3 claim** that defect #4 makes the stop-width gradient "steeper than measured" — at 1%
frequency it cannot move a mean materially. Overstated; corrected.

⚠ **Sampling caveat, stated before anyone else does:** stride 10 gives 185 trades against the
corpus's 1,975, so observed concurrency here is **2.08 mean / 8 max**, roughly a tenth of the density
of a stride-1 walk. ⛔ **ROUND 7, accepting Kimi Catch 3: "brackets rather than refutes" below was
BACKWARDS — 2.08 does not bracket 12, it samples a different regime.** The **dependence** result is robust to this (ρ̄ is a per-pair quantity and the
calendar-block bootstrap prices what overlap exists), but **σ_R and the mean should be re-measured at
stride 1** before either is treated as final.

## 12.11 Code answers — the reviewers' questions, answered from the source

Round 6 asked for evidence, not opinion. Every answer below is a file:line or a query result.

| # | question | answer |
|---|---|---|
| Claude Q3 | block length **and unit** in §12.4's bootstrap — 8 trades or 8 days? | **8 TRADES.** `block_bootstrap.moving_block_bootstrap(returns: Sequence[float])` is date-blind. ⚠ **This undermines the claim on BOTH sides of Claude's Finding 1:** positional holds 30 sessions at ~12 concurrent, so 8 *trades* spans far less than one holding period — the bootstrap **could not have detected** overlap dependence. 1.046× was never evidence that dependence is low. ✅ But §12.10's **calendar-block** bootstrap now measures the same thing properly and agrees |
| Claude Q9 | does any table hold intended price beside achieved fill? | **YES — schema supports it.** `orders.price` (intended) + `orders.filled_price` (achieved) + `broker_payload` JSONB already stamping `chase_r`; and `signals.entry` vs `positions.avg_entry_price`. ⛔ **But `orders` = 0 rows and `positions` = 0 rows.** ⇒ **slippage is unmeasurable retrospectively; only cycle 2 can produce it.** This is the branch Claude said would change the plan — it does |
| Claude Q10 | do the three files share a level function? | **A shared function with a divergent call contract, which is worse than three implementations because it looks unified.** `signal_service.py` → `safe_levels` → `compute_levels`, **passes `ema20_daily`**; `pipeline.py` → `safe_levels`, **does not**; `engine.py` → `compute_levels` **directly**, does not |
| Claude Q11 | does `backtest/engine.py` call `fees.py` or `risk_engine`? | **Neither. Zero references.** |
| Claude Q12 | define panel / signal / gate-passer / trade | §12.10d — one denominator chain, measured |
| Claude Q2b | pairwise correlation split **same-sector vs cross-sector** | ⛔ **NOT POSSIBLE TODAY.** `stocks.sector` is populated on **165 of 1,322** names (12.5%), so the overwhelming majority of the 263 overlapping pairs have at least one side with no sector. Splitting would report a statistic on a 12.5% subsample selected by *which names happened to get a sector label*, which is its own selection effect. ⇒ **blocked behind the sector backfill**, and recorded as blocked rather than approximated |
| Claude Q6 | is the 1,975-trade corpus **all signals** or only **gate-passers**? | **Neither — it is three stages downstream of both.** `[doc]` §11.1 of `SYSTEM_REVIEW_FOR_QUANT.md` defines it as *resolved trades*: panels → gate-passers → class-filtered → level-stage survivors → **resolved trades**. `[corpus]` The attrition measured on the same pipeline (§12.10d): **16,428 panels → 514 gate-passers (3.13%) → 475 swing → 185 trades**, i.e. **89 panels per trade and 2.8 gate-passers per trade.** ⚠ So "1,975 trades" implies on the order of **5,500 gate-passers and ~175,000 panels** at those ratios — but that is an extrapolation from a stride-10 walk, **not a count**, and the honest answer is that the corpus's own upstream counts were never recorded. **Any future corpus run must emit the full chain, not just the trade count** |
| Kimi Q1b | which inflation formula does the code use? | **Neither — `1+(m−1)ρ̄` appears NOWHERE in the codebase.** It exists only in this document. So Kimi's Catch #1 critiques my prose, not an implementation; there is no code to audit. ✅ Its structural point stands (the mean-of-overlapping estimand wants `1+2(m−1)ρ̄`) — **and is now moot, because ρ̄ measures −0.013** |
| Kimi Q4 | count defect-#4 events | **2 of 185 = 1.08%** (§12.10d) |
| Kimi Q10 | any tax handling? | **None.** No `tax`/`stcg`/`ltcg` in `fees.py` or `paper_broker.py`. ⭐ **Kimi's point stands and is unaddressed** — ~20% STCG is second-order at ₹1L and **first-order at the ₹10L scale where §12.9 says the programme becomes EV-positive.** Any capital table that ignores tax is wrong at exactly the scale that matters |
| ChatGPT I | contradiction scan on the capital equations | `config.py`: `paper_max_notional_leverage = 1.0` · `heat_cap_pct = 6.0` · `max_concurrent_positions = 3`. ⛔ **And ChatGPT is right that §12.9 contradicts itself** — it says "slots = heat ÷ risk = 3 at every capital level" and then tables 3/4/6/9 slots at ₹1L/1.5L/2L/3L. The second holds only if `risk_pct` is *also* cut, which appears in the prose and not in the table. **Two different policies presented as one; the ladder must be run under both, as ChatGPT's item H asks** |

### 12.11a ⭐ Taxes and the Kelly fraction — two items nobody had raised

**Taxes — zero mentions in 1,443 lines, and none in the code.** Confirmed above. First-order at ₹10L.

**The Kelly fraction is negative at the measured statistics.** ⛔ **ROUND 7: `p − q/b` is the
binary-bet formula and the wrong instrument** for a continuous, barrier-truncated, time-capped payoff
(Claude, ChatGPT §9 and Kimi all flagged it). ✅ **The empirical estimator gives `f* = 0.0000`
exactly, and μ/σ²'s 90% bootstrap CI excludes zero even BUY-only after costs** (§12.16 R7-E) — so the
conclusion HARDENS and the magnitude below was wrong by ~2.6×. ~~At p ≈ 0.25 win rate and b ≈ 1,
`f* = p − q/b ≈ −0.5`.~~ ⭐ **The corpus's own numbers imply the growth-optimal live risk is ZERO.**
Cycle 2 staying on paper is not prudence — **it is what the arithmetic mandates.** Nobody across six
rounds stated it that plainly, and it belongs in the Week-4 capital branch as the default.

### 12.11b Derivations and arithmetic

**Kimi Q3 — the Sharpe→per-trade-R conversion, DERIVED. Never shown in six rounds, which is exactly
why the number moved every round.**

> Annualised Sharpe `S = (annual mean) / (annual sd)`. With `N` trades/yr, per-trade mean `μ` and sd
> `σ`, and variance inflation `I`: annual mean `= Nμ`, annual variance `= Nσ²I`, so
> **`S = μ√N / (σ√I)`** ⇒ **`μ_net = S·σ·√I / √N`** and `μ_gross = μ_net + friction`.

| S | N | I | σ_R | μ_net | μ_gross |
|---:|---:|---:|---:|---:|---:|
| 1.00 | 125 | 1.00 | 0.878 | **+0.0785R** | +0.1295R |
| 1.00 | 250 | 1.00 | 0.878 | +0.0555R | +0.1065R |
| 1.00 | 125 | 1.75 | 0.878 | +0.1038R | +0.1548R |
| 0.37 | 125 | 1.00 | 0.878 | +0.0290R | +0.0800R |

⭐ **The benchmark is meaningless without N and I stated.** That is the whole reason it moved from
0.094 → 0.125 → 0.176 → 0.0785 across rounds 4–6.

**Kimi Q8 — cycle-2 paired-calibration power, the assumption bounded.**

| sd(ε) | SE at n=25 | MDE @ t=2 | MDE @ 80% power |
|---:|---:|---:|---:|
| 0.2R | 0.040R | +0.080R | +0.112R |
| 0.3R | 0.060R | +0.120R | +0.168R |
| 0.5R | 0.100R | +0.200R | +0.280R |

⇒ **The test functions up to sd(ε) ≈ 0.35R** if the target is a 0.10R bias at t=2. **At 0.5R it is as
dead as the expectancy gate it replaced.** Kimi is right that this must be *estimated first*, not
presumed — so cycle 2's first job is to estimate sd(ε), and only then to test the bias.

**Kimi Q9 — the slippage proxy, and what the assumption is worth.**

| slippage, bps/leg | round trip | cost in R @ 5% stop | total friction |
|---:|---:|---:|---:|
| 0 | 0 bp | 0.000R | 0.051R |
| 10 | 20 bp | 0.040R | 0.091R |
| **15** | **30 bp** | **0.060R** | **0.111R** ← the document's assumption |
| 20 | 40 bp | 0.080R | 0.131R |
| 30 | 60 bp | 0.120R | 0.171R |

**The assumed 0.06R is 15 bps/leg.** Plausible for a liquid mid-cap on a market order — and entirely
unmeasured. ⭐ **Since it cannot be measured retrospectively (§12.11 Q9), report every friction-
dependent conclusion at 10 / 15 / 20 bps until cycle 2 pins it.**

**Kimi Q10 — post-tax rows.** At +0.09R/trade, 125 trades, 2% risk, STCG 20%:

| capital | gross/yr | **post-tax** |
|---:|---:|---:|
| ₹1L | ₹22,500 | **₹18,000** |
| ₹3L | ₹67,500 | **₹54,000** |
| ₹10L | ₹2,25,000 | **₹1,80,000** |

**ChatGPT items A + H — the §12.9 contradiction resolved, as two named policies.**

| capital | **A: fixed 2% risk** slots / size / risk | **B: fixed ~₹40k position** slots / size / risk |
|---:|---|---|
| ₹1.0L | 3 · ₹40,000 · 2.00% | 3 · ₹40,000 · 2.00% |
| ₹1.5L | 3 · ₹60,000 · 2.00% | 4 · ₹40,000 · 1.33% |
| ₹2.0L | 3 · ₹80,000 · 2.00% | 6 · ₹40,000 · 1.00% |
| ₹3.0L | 3 · ₹1,20,000 · 2.00% | 9 · ₹40,000 · **0.67%** |

⭐ **These are different strategies.** Policy A holds risk constant and grows position size; policy B
holds position size constant and grows *count* by cutting per-trade risk. §12.9 stated A's identity
and then tabled B's slot ladder. **B is what buys the +20% effective breadth — and B is available at
₹1L too**, by cutting `risk_pct`. Capital is not what unlocks it.

**Kimi Q4 (rest) — fill accounting.** `engine.py:212`: `entry_price = float(fill_candle["open"])` —
**fill at the next open.** And both probes compute the R denominator from **`rec.entry_price`, the
FILL price, not the signal price** (`swing_dependence_probe.py:176`, `positional_probe.py:153`) —
which is the correct choice and worth stating, since a signal-price denominator would have hidden
entry displacement inside R.

**Kimi Q5 — ex-date stop behaviour.** ⛔ **No ex-date handling exists in `backtest/engine.py` at all.**
Stops are hit at the **raw unadjusted price**. ⭐ Kimi's point stands in full: **a modelling decision
is hiding inside what the plan presents as a data repair.** Whether a real resting stop fires on a
40% ex-split morning, or is adjusted/cancelled by the exchange, determines whether CA "contamination"
is a bug or an accurate simulation. That must be decided explicitly, not inherited.

**Kimi Q7 — gate provenance, and the answer partly REFUTES the in-sample worry.** `[git]`
`confluence.py`, carrying the 70 threshold, the weights and the ADX schedule, was added
**2026-07-03** in the pre-upgrade baseline. The first corpus analysis (`entry_attribution.py`) landed
**2026-08-12** — **six weeks later.** ⇒ **The scorer is NOT in-sample: it was authored from the spec,
not fitted to this data.** ⚠ **What IS in-sample is everything after 08-12** — the eight shadow
gates, the weight-retune experiments, the regime and R:R promotions. **Kimi's claim (c) is therefore
right about the overlay programme and wrong about the scorer**, and that distinction matters: it
means #16 tests a genuinely pre-registered object.

## 12.12 ⛔⛔ `ohlcv_1d` HAS A 922-DAY HOLE — and it reaches into every round-6 number

**Nobody in twenty-five reviews could have found this, because it is not in any document.** Round 7
began by asking the reviewers' universe question as a query rather than a code read, and the query
returned a session census instead of an answer:

| year | bars | names | **sessions** |
|---|---:|---:|---:|
| 2019 | 90,248 | 1,598 | 61 |
| 2020 | 367,556 | 1,742 | 246 |
| **2021** | **0** | **0** | **0** |
| **2022** | **0** | **0** | **0** |
| 2023 | 215,468 | 2,081 | 123 |
| 2024 | 465,613 | 2,304 | 248 |
| 2025 | 529,758 | 2,552 | 248 |
| 2026 | 412,830 | 2,909 | 171 |

`[db]` The largest gap between consecutive sessions is **2020-12-23 → 2023-07-03 = 922 days.**
Total distinct sessions: **1,097** — not the ~1,730 a continuous 2019-10 → 2026-09 span implies.

⭐ **This explains `_CLEAN_SINCE = 2023-07-03` in `entry_confirmation_study.py`**, a constant three
documents describe as a *CA-clean window* choice. It is not a CA choice. **It is the first date of
the contiguous modern block.** The "false CA-clean claim" already recorded in memory was half the
story: the date was never about corporate actions at all.

### What it does to the round-6 measurements

`[measured]` The probe walks a **300-bar** window, so a panel whose window opens before the hole and
closes after it computes EMA200, ATR, ADX, every pivot and every S/R level **across a 2.5-year
discontinuity, as if 2020-12-23 and 2023-07-03 were consecutive sessions.** Counted on the identical
universe and stride that produced round 6 — and reproducing its panel count **exactly**, which is
what establishes this is the same walk:

| panel state | count | share |
|---|---:|---:|
| **window STRADDLES the 922-day hole** | **5,462** | **33.2%** |
| window wholly pre-gap | 170 | 1.0% |
| window wholly post-gap (clean) | 10,796 | 65.7% |
| **total (= round 6's 16,428, exactly)** | **16,428** | 100% |

⇒ **A third of round 6's panels are scored on a series that never existed.** The no-look-ahead rule
(`.claude/rules/trading-domain.md`: "compute on candle N, valid from N+1") is not violated — the bars
are all in the past — but the **window canon is**: "the last 300 *completed* candles" silently became
"300 rows, whatever calendar they span."

### ⛔ And it kills plan item #2 of eight

`docs/analysis/quant-panel-adjudication` §13's CUT item 2 — **0a.6, un-truncate the corpus** — claims
extending to 2019-10 takes `n` from **1,975 to ~4,300 (×2.18)** and the corpus MDE from +0.067R to
+0.045R. That was the plan's single largest breadth lever. Against the measured session counts:

| walk | usable bars/name pre-gap | post-gap | achievable n | plan claimed |
|---|---:|---:|---:|---:|
| corpus (`run_single_stock`, starts bar 50) | 256 | 736 | **~2,662 (×1.35)** | 4,300 (×2.18) |
| probe (300-bar window) | **0** | 480 | **1,975 (×1.00)** | 4,300 |

⭐ **At a 300-bar window the entire 2019–2020 block yields ZERO usable panels** — 307 sessions cannot
supply 300 prior bars plus a 7-bar forward horizon. At the corpus's bar-50 walk it yields ×1.35, and
the corrected MDE is **+0.0340R (σ=0.878) / +0.0577R (σ=1.489)**, not +0.0268R / +0.0454R.

⇒ **0a.6 is not blocked on the CA source it was blocked on. It is blocked on 615 missing sessions.**
Reaching n = 4,300 requires back-filling **2021-01 → 2023-06** from the bhavcopy archive — a data
acquisition task of the same shape as the 2026-09-07 recovery, not a query and not seven minutes of
Kite calls. ⚠ **Claude's round-7 note that "un-truncation is still blocked behind a CA source that
doesn't exist" names the wrong blocker**, and so did every prior round including mine.

### The three actions this forces

1. **Every probe and study gets a gap guard.** `swing_dependence_probe.py` now carries
   `GAP_LO/GAP_HI` and a `--clean-only` flag; the default keeps round 6 reproducible, and
   `--clean-only` re-measures on windows that are wholly one side. **A study that reports a number
   over a period containing the hole must say which side of it the number comes from.**
2. **0a.6 is re-specified** as *back-fill 2021-01 → 2023-06, then un-truncate* — and it drops out of
   the eight-item cut, because it is now days of ingestion rather than a query. What replaces it in
   the cut is §12.12's own guard plus the R7 measurements below.
3. ⭐ **The standing rule this earns (W1's data-plane sibling):** **a span is not a span until the
   session count is queried.** Three documents, six rounds and twenty-five reviews asserted "~7
   years, 2019-10 → 2026-09" from `min(time)` and `max(time)` — two numbers that are both true and
   together say nothing about what lies between them.

## 12.13 ⭐ Two accepted corrections that were never propagated — both confirmed by arithmetic

Round 7's two sharpest catches are the same failure mode this document has now committed **five**
times: **a correction is accepted in one section and left standing in another.** Both are confirmed.

### 12.13a ⭐ Kimi Catch 1 — §12.9's capital-power table was computed at the RETIRED ρ̄ = 0.5

`[verified]` Every inflation cell in §12.9's "What capital does NOT buy" table is exactly
`1 + (m−1)·0.50`:

| slots m | `1+(m−1)·0.5` | §12.9 printed | match |
|---:|---:|---:|---|
| 3 | 2.00 | 2.00 | ✅ |
| 4 | 2.50 | 2.50 | ✅ |
| 6 | 3.50 | 3.50 | ✅ |
| 9 | 5.00 | 5.00 | ✅ |

**§12.10 measured ρ̄ = −0.013 and retired the 0.5. Nobody re-ran the table.** Re-run:

| capital | slots | trades/yr | infl @ ρ̄=0.5 | N_eff | **infl @ ρ̄=−0.013** | **N_eff** |
|---|---:|---:|---:|---:|---:|---:|
| ₹1.0L | 3 | 150 | 2.00 | 75 | 0.974 | **154** |
| ₹1.5L | 4 | 200 | 2.50 | 80 | 0.961 | **208** |
| ₹2.0L | 6 | 300 | 3.50 | 86 | 0.935 | **321** |
| ₹3.0L | 9 | 450 | 5.00 | 90 | 0.896 | **502** |

⭐ **₹3L buys ×3.26 the effective observations, not the +20% §12.9 states.** The MDE tightens
**×1.81**. ⇒ **"Tripling capital buys +20% effective observations", "the MDE wall does not move when
you add cash" and "adding ₹2L is not a validation decision" are all STALE**, and the round-5
adjudication of Kimi's +6% and Claude's +33% against a "measured +20%" is stale with them. **Claude's
+33% was the closest of the three.**

⚠ **But the causal attribution survives, and this is where Kimi's conclusion needs ChatGPT's
correction bolted on.** The 3/4/6/9 ladder is **Policy B** (§12.11b) — it grows slot count by
*cutting `risk_pct`*, and §12.11b already established Policy B **is available at ₹1L.** Under Policy
A (fixed 2% risk) the slot count is **3 at every capital level**, so:

> ⭐ **The ×3.26 is bought by the RISK POLICY, not by the capital.** Capital buys only the
> *affordability* of the finer slice. ChatGPT's chain is the correct one:
> `capital → affordable position granularity → risk allocation → concurrent bets → effective breadth`
> — not `capital → breadth`.

`[measured]` And the granularity floor is real but mild. Policy B at ₹1L, 9 slots = ₹11,111/position:

| share price | qty | actual | size error |
|---:|---:|---:|---:|
| ₹39 | 284 | ₹11,076 | 0.3% |
| ₹500 | 22 | ₹11,000 | 1.0% |
| ₹1,500 | 7 | ₹10,500 | **5.5%** |
| ₹2,500 | 4 | ₹10,000 | **10.0%** |

⇒ **9 slots at ₹1L is executable, with 5–10% size quantization on names above ~₹1,500.** That is the
honest version of "capital buys breadth": it buys it *cleanly*; ₹1L buys it *coarsely*.

⚠ **Kimi's own caveat is correct and binding:** ρ̄ = −0.013 was measured at observed concurrency
**2.08**. At 9 slots the overlap structure differs and ρ̄ could rise. Stress case, ρ̄ = +0.2:
N_eff 107 / 125 / 150 / 173 ⇒ ₹3L buys **×1.62**. ⇒ **the verdict is "the burden of proof moved",
not "case closed"** — and the ρ̄-vs-concurrency relation is now an open measurement (R7-Q4).

### 12.13b ⭐ Claude Finding A — §12.10a pairs a σ from one sample with an n from another

`[verified]` §12.10a's row `corpus, truncated · n=1,975 · MDE +0.0395R` uses **σ = 0.878, measured on
185 probe trades**, with **n = 1,975, the corpus**. Claude's recomputation reproduces exactly:

| basis | n | σ used | MDE @ t=2 | vs explicit friction 0.051R |
|---|---:|---:|---:|---|
| corpus, truncated | 1,975 | **1.489** | **+0.0670R** | MDE **EXCEEDS** friction |
| corpus, un-truncated (as planned) | 4,300 | 1.489 | +0.0454R | just below |
| probe sample | 185 | 0.878 | +0.1291R | far above |
| **as printed in §12.10a** | 1,975 | 0.878 | +0.0395R | below |

And the two σ are not sampling noise: with excess kurtosis +8.19,
`SE(s) = σ√((κ+2)/4n) = 0.103`, so **|1.489 − 0.878| = 5.93 SE.**

⭐ **The mechanism Claude's table implies but does not state, and it narrows the conclusion further:
σ CANCELS in the detectability ratio.** Write it out —

> `detectable = (S·σ·√I/√N + friction) / (2σ/√n) = [S·√I·√n / 2√N] + [friction·√n / 2σ]`

The first term is **σ-free** (1.99× at n=1,975, N=125, I=1 — identical under either σ). Only the
*friction* term carries σ: 1.29× at σ=0.878, 0.76× at σ=1.489, which is the whole of the 3.28 → 2.75
move. ⇒ **σ barely touches "can the corpus detect a Sharpe-1.0 book". What σ decides is the
blockquote claim — MDE against FRICTION:**

| σ | truncated (n=1,975) | un-truncated (n=4,300) |
|---:|---|---|
| 0.878 | MDE 0.0395 **< 0.051 — claim holds** | MDE 0.0268 **< 0.051 — holds** |
| 1.489 | MDE 0.0670 **> 0.051 — claim FAILS** | MDE 0.0454 < 0.051 — holds |

⇒ **Claude's narrower restatement is adopted verbatim:** *"detectability is not the binding
constraint" survives; "the corpus can detect a gross edge below explicit friction" holds only under
the probe's σ, or on the un-truncated corpus* — **and §12.12 has just removed un-truncation from
reach.** So the claim now rests entirely on which σ belongs to the corpus.

⚠ **One correction to Claude's framing, which changes the repair.** **1.489 was never measured.** It
is back-derived from `SE = 0.065/1.94`, ×√1975 (§16.1 says so). So the fix is *not* "pair 1.489 with
1,975" — it is that **σ on the 1,975-trade corpus has never been measured at all**, and §12.10a used
the only measurement in existence on a different population. `[code]` Five structural mechanisms
separate the two samples, none of them noise:

| # | corpus (`entry_confirmation_study.py`) | probe (`swing_dependence_probe.py`) |
|---|---|---|
| 1 | **all classes** — §3b breaks out swing *and* positional; σ_R positional is **1.844–2.088** | **swing only** (`classify_signal(...) != "swing": continue`) |
| 2 | walk starts at **bar 50** (`run_single_stock`, `range(50, len-1)`) | **bar 300** — a different factor-availability regime |
| 3 | `_CLEAN_SINCE = 2023-07-03`, so **wholly post-hole** | 2019-10 onward ⇒ **33.2% of panels straddle the hole (§12.12)** |
| 4 | **stride 1**, with the `_has_active_signal` latch | **stride 10**, no latch |
| 5 | universe: `is_active` + mdv ≥ ₹5cr, top 250 | top 250 by **today's** 180-day mdv |

⭐ **Mechanism 1 alone plausibly closes the gap**: a swing+positional blend containing a σ≈2.0
component cannot have the same σ as swing alone. ⇒ **the σ reconciliation is a class-mix question, and
it is answerable by one flag on the corpus study** (report σ_R per classification), not by a stride-1
re-run.

⭐ **Claude's proposed mechanical guard is ADOPTED and made executable, merged with Kimi Catch 4's:**
**every quantity in §16.1 carries the sample it was measured on and the date it was verified, and no
formula in this document may combine two quantities whose sample tags differ.** §16.1 now has both
columns. Kimi's version — *"no round-N document ships until a script diff-verifies every §16.1 row"* —
is the enforcement, and it is why §16.1's rows are now individually stamped rather than collectively
promised.

## 12.14 ⭐ ChatGPT's cash constraint — CONFIRMED BY CODE, and it is genuinely new

ChatGPT item 11 asks whether the per-position notional cap is the only cash restriction, or whether a
portfolio-level one exists. `[code]` **It is the only one. There is no portfolio-level cash
constraint anywhere in the codebase.** `grep` for `available_cash` / `available_funds` /
`total_notional` / a sum over open positions' notional across `paper_broker.py` and
`risk_engine.py` returns **nothing**. The four rules that exist are all per-position or
per-risk-budget: `notional_cap_reason` (per position), `heat_cap_reason` (sum of *risk*, not of
notional), `position_count_reason` (a count), `admission_risk`.

`[measured]` What that permits, at ₹1L and 2% risk, with risk-first sizing:

| stop width | risk ₹ | position ₹ | % of capital | **3 slots** | feasible in cash? |
|---:|---:|---:|---:|---:|---|
| 2.0% | 2,000 | 1,00,000 | 100.0% | **300%** | ⛔ |
| 3.0% | 2,000 | 66,667 | 66.7% | **200%** | ⛔ |
| **5.0% (the median)** | 2,000 | 40,000 | 40.0% | **120%** | ⛔ |
| 8.0% | 2,000 | 25,000 | 25.0% | 75% | ✅ |
| 10.0% | 2,000 | 20,000 | 20.0% | 60% | ✅ |

⭐ **At the median 5% stop, three concurrent positions require 120% of capital, and nothing in the
code notices.** The per-position cap (`capital × leverage = ₹1,00,000`) binds only below a 2% stop —
which is the same `risk_pct ÷ leverage` minimum-stop-width identity already recorded in §1 #10 and
`POSITIONAL_REVIEW_FOR_QUANT.md`. It was never a *portfolio* rail and was never described as one.

⇒ Three consequences, in order of how much they matter:

1. **Cycle 1's 45.3%-heat / 23-position book was not merely over-risked — it was cash-impossible.**
   Gross notional across 23 positions at a ~4.4% mean stop is on the order of **₹10L on a ₹1L
   figure.** §12.9's `paper_sampling_capital_inr` reporting fix (9.1% of ₹5L) makes the *risk* read
   sensibly and says nothing about the notional, which is the quantity a broker would have refused.
2. **Cycle 2's "heat-capped ₹1L book" is under-specified.** A 6% heat cap plus a 3-position cap plus
   a 1.0× per-position notional cap still admits 120% gross notional. ⇒ **cycle 2 needs a fourth
   rail: `Σ notional ≤ available cash`** — and it belongs in Phase 7.1's RiskEngine beside the other
   three, as one more `*_reason` function. This is the first *new rail* any of twenty-five reviews
   has produced, as opposed to a re-tune of an existing one.
3. **It is a cheap, pre-registration-free build.** Like the diversity gate, it enforces an identity
   (you cannot spend money you do not have) rather than a claim about the tape — so it is exempt from
   the t ≈ 3.6 bar under §5.4's asymmetric-burden edit, on the same argument that exempted the
   position-count cap in D4.

⚠ **What ChatGPT gets slightly wrong:** it frames this as possibly "a major difference between
mathematical quantity, paper-broker feasibility and actual delivery feasibility." There is no
difference — the paper broker has no cash model at all, so paper and mathematical are the *same*
number, and only delivery differs. The defect is narrower than described and easier to fix.

## 12.15 ⭐⭐ THREE REVIEWERS, THREE ROUTES, ONE REPAIR — KILL LINE 3 is still keyed to the wrong stage

This is the strongest convergence of the exercise, stronger than round 4's three-way IC flag, because
the three arrived from unrelated starting points and none cites the others:

| source | route | the claim |
|---|---|---|
| **ChatGPT §7** | decomposition logic | *"TOST inside ±friction ⇒ the feature family is dead"* cannot be established from **total strategy R**. Selection +0.10R with exit destruction −0.15R reads as −0.05R and kills a signal that carried information |
| **Claude Finding D** | the denominator chain | the **level stage removes 60.8% of gate-passing swing panels** on pivot proximity — which §4.4 says selects tight stops, and §12.1/§7 say tight stops are the worst cohort. **It has never been evaluated as a selector** |
| **Kimi Q8** | the evidence hierarchy | #16's primary endpoint should be the **conditional economic effect** — gate-passers vs *matched eligible non-passers* — because the document's own hierarchy ranks that first and IC fourth |

⭐ **Put together they say one thing: KILL LINE 3 declares the death of the SCORER using an endpoint
measured three stages downstream of it.** Between the score and the number the line reads sit the
classifier, the level stage (−60.8%), the barrier geometry, the horizon and the fill model — and at
least one of those (the level stage) is independently suspected of being anti-correlated with
outcome. **A line that cannot distinguish "the score has no information" from "the level policy
destroys the information the score has" is not a closure instrument.** That is the third time a kill
line in this document has been keyed to the wrong quantity (KL3-original, KL4, KL6), and the third
time the defect was structural rather than arithmetic.

### ✅ KILL LINE 3 — REPAIRED AGAIN (round 7). Two verdicts, two endpoints, stated separately.

The repair is not a new threshold. It is the recognition that **"the strategy as configured is dead"
and "the feature family is dead" are claims about different objects and need different measurements**
— a distinction the line already draws for *statistical vs economic* closure and must now also draw
for *stage*:

> **3a — STRATEGY CLOSURE (the configured pipeline).** Endpoint: **cost-adjusted mean R of resolved
> gate-passing trades**, SESOI = friction at the class's median stop. Unchanged from the round-4
> repair, and it is sound *for what it measures*. Verdict on firing: **this pipeline, with this level
> policy, this geometry and this horizon, has no monetisable edge.** ⛔ **It may NOT be reported as
> the death of the feature family.**
>
> **3b — FEATURE-FAMILY CLOSURE (the score itself).** Endpoint: the **conditional forward return of
> gate-passers against date-and-characteristic-matched eligible non-passers** (Kimi Q8), in **bps and
> ATR units** (§12.10b), measured **before** the level stage and the exit policy intervene, with the
> overlap-corrected `newey_west_t` (lag = horizon−1) and the CA filter. Firing requires the 90%
> interval **inside ±SESOI on this endpoint** — not on 3a's.
>
> ⚠ **A third outcome is now explicit and is the one the level-stage finding makes likely:**
> **3a fires and 3b does not** ⇒ the score carries information the pipeline destroys ⇒ **the repair is
> a pipeline repair, not closure**, and the level stage is the first suspect. This branch did not
> exist in any prior version of the line, and §12.16's measurement is what decides whether it is the
> live one.

⚠ **Against ChatGPT on one point:** its proposed five-level kill hierarchy (complete strategy → where
is the loss → selection → setup/timing → exit) is the right *decomposition* and the wrong *governance
object*. Five sequential gates on a programme that has shipped zero of nine cut items in 50 days
before its own sunset is how the plan got cut from 29 items to 8 in the first place. **Two endpoints
under one line is the same logic at the capacity we actually have** — and §12.16 measures the stage
ChatGPT's hierarchy would reach at level 2, now, rather than pre-registering four more.

## 12.16 ⭐⭐ ROUND-7 MEASUREMENTS — the direction split changes the headline

`backend/scripts/swing_dependence_probe.py`, extended (read-only, SELECT-only, frozen scorer and
frozen `_simulate_trade` imported and CALLED — W2: the round-6 probe was **extended, not forked**).
Same 238 names, same stride 10, and it **reproduces every round-6 number exactly** — 16,428 panels,
514 gate-passers, 185 trades, σ_R 0.8776, ρ̄ −0.0126, Δ_select +0.0447/t+0.29 — which is what
licenses reading the new columns as the same walk.

### R7-I ⭐ The 922-day hole, split — it biases the mean DOWN and σ DOWN

`[measured]` Flagging each trade by whether its 300-bar scoring window straddles the hole (§12.12):

| cohort | n | share | mean R | σ_R | SE | **t** | win | med stop |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **straddling the hole** | 38 | 20.5% | **−0.2059** | **0.743** | 0.1205 | −1.71 | 31.6% | 4.88% |
| **clean window** | 147 | 79.5% | **−0.1341** | **0.911** | 0.0751 | **−1.79** | 41.5% | 4.58% |

⛔ **SUPERSEDED BY ROUND 8 (§12.18b).** The contrast is `+0.0718, SE 0.1420, t = +0.51`, and
**0.325 of the 0.522 t-drop is power loss while only 0.197 is the mean moving.** ⇒ the supportable
statement is **"removing 38 observations costs enough power to drop the headline below
significance"** — *not* "the hole biases the mean down". The σ claim below falls with it (§12.18, C3:
the ladder is 0.62 SE).

~~⇒ ⭐ **A SECOND independent reason round 6's headline is not robust.**~~ Removing the trades scored
across a 2.5-year discontinuity moves the mean from −0.1489 to **−0.1341** and the t from **−2.31 to
−1.79** — below significance, **but on POWER, not on the mean.** ⇒ **the headline
fails on two unrelated grounds: population (R7-A) and data integrity (here).**

⭐ **And it confirms §12.13b's mechanism 3 quantitatively:** the straddling cohort has **lower σ
(0.743 vs 0.911)**, so the hole was *compressing* dispersion — indicator series stitched across a
922-day gap produce artificially tame stops and outcomes. **The clean σ of 0.911 is much closer to
the BUY-only 0.957 than to the mixed 0.878**, which is the direction §12.13b predicted.

⚠ Note **20.5% of trades** straddle against **33.2% of panels** — gap-straddling panels are
*less* likely to survive to a trade, which is itself a selection effect of the hole.

### R7-A ⭐⭐ The direction split — four reviewers asked, and it inverts the headline

**All four reviewers led with this** (Claude Finding B, Kimi Catch 2, ChatGPT §2's trace, Gemini's
"Direction Isolation"), and it had been Week-2 item 14 since round 1 without ever running.
`[code]` **Nothing between the gate and the trade removes SELLs** — `classify_signal` and
`safe_levels` are both direction-agnostic — so the shorts were in the headline, as charged:

| cohort | n | **mean R** | sd | SE | **t** | win | median |
|---|---:|---:|---:|---:|---:|---:|---:|
| **ALL** (round 6's headline) | 185 | **−0.1489** | 0.878 | 0.0645 | **−2.31** | 39.5% | −0.169 |
| **BUY — the tradeable book** | 82 | **−0.0992** | 0.957 | 0.1057 | **−0.94** | 43.9% | −0.118 |
| SELL — **not holdable on cash delivery** | 103 | −0.1885 | 0.811 | 0.0799 | **−2.36** | 35.9% | −0.193 |

⛔⛔ **SUPERSEDED BY ROUND 8 (§12.18b): this sentence is WITHDRAWN.** The two halves were never
compared. The **contrast** is `+0.0893, SE 0.1325, t = +0.67, p = 0.50` — **they do not differ.**
⭐ What survives is structural, not statistical: **a cash-delivery account cannot hold an overnight
short, so 55.7% of these trades are untradeable by construction whatever their mean**, which is why
the BUY cell is still the right population. The error was claiming the populations differ *measurably*.

~~⭐⭐ **The significantly-negative gross edge is carried by the untradeable half.**~~ Restricted to the
direction an NSE cash-delivery account can actually hold overnight, the book is **t = −0.94 — a coin
flip with a negative point estimate.** ⇒ **§12.10a's "the programme has been asking *can we detect an
edge* when the powered answer was *the sign is negative*" must be withdrawn as stated.** The powered
answer on the tradeable book is **"not distinguishable from zero, and negative in expectation."**
That is a materially different verdict and it changes what KILL LINE 3 firing would mean (§12.15).

⚠ **In raw % the same split reads −0.19% BUY (t −0.52) and −0.44% SELL (t −1.44)** — so the
direction asymmetry is not a stop-width artifact (BUY mean stop 4.34%, SELL 4.51%: nearly identical).

⭐ **And the attrition explains the 52.9% → 55.7% SELL drift:** `[measured]` the classifier sends
**39 of 242 BUYs to `positional` and 0 of 272 SELLs** — because `positional` is `MULTIBAGGER_EMA`'s
footprint and that factor has no bearish branch. **An independent confirmation of
`POSITIONAL_REVIEW_FOR_QUANT.md`'s "435/435 BUY, structurally long-only"**, arriving from a different
script. So the swing book is **203 BUY / 272 SELL = 57.3% short** before the level stage, and
**82/185 = 44.3% long** after it.

### R7-A2 ⭐ ρ̄ ≈ 0 WAS PARTLY A DIRECTIONAL-CANCELLATION ARTIFACT — and it hands Kimi its own stress case

`[measured]` Re-running the calendar-block bootstrap on the **BUY-only** book:

| book | n | σ_R | 10d inflation | 30d inflation | implied ρ̄ at m=2.08 |
|---|---:|---:|---:|---:|---:|
| mixed (round 6) | 185 | 0.878 | **1.00×** | 1.01× | **−0.013** |
| **BUY only** | 82 | 0.957 | **1.23×** | **1.19×** | **≈ +0.19** |

⭐ **A long-only book of overlapping trades IS positively dependent — they share market beta, which
is exactly what a +0.92-beta book should do.** Round 6 measured ρ̄ on a book that is 56% short, where
long and short overlap **cancels**. ⇒ **ρ̄ = −0.013 is a correct measurement of the wrong portfolio.**

⇒ **This is the round's most consequential internal correction, and it partly walks back §12.13a:**

| capital | slots | trades/yr | N_eff @ ρ̄=−0.013 | **N_eff @ ρ̄=+0.19 (long-only)** |
|---|---:|---:|---:|---:|
| ₹1.0L | 3 | 150 | 154 | **108** |
| ₹3.0L | 9 | 450 | 502 | **176** |
| | | | **×3.26** | **×1.63** |

⭐⭐ **Kimi asked for precisely this stress case (ρ̄ = +0.2, "since ρ̄ at 9 slots is unmeasured") and
its own answer — ×1.62 — is the number to use.** Both halves of Kimi Catch 1 land: the table WAS
stale, and the correction it proposed is itself superseded by the stress case it had the discipline
to request. ⚠ Still unmeasured: whether ρ̄ **rises with concurrency**. 1.19–1.23× is at m=2.08; at
9 slots it could be higher again.

⚠ And note what this does to ChatGPT §3: **ChatGPT asked the right question in the wrong coordinate**
— see R7-D.

### R7-B ⭐ Δ_select as a continuous statistic — Claude Finding C confirmed, and the answer is unchanged

Claude's objection to §12.10c is arithmetically right: the top-decile contrast (n=29, SE 0.153) has
**MDE +0.31R**, so it could not have detected a spectacular edge. `[measured]` The continuous
estimators, on **all 185**:

| cohort | n | **Spearman ρ(conf, R)** | perm p | OLS slope R per conf-pt | 90% CI | **detectable ρ at t=2** |
|---|---:|---:|---:|---:|---|---:|
| ALL | 185 | **−0.018** | 0.807 | −0.0011 | [−0.0175, +0.0152] | **0.147** |
| BUY only | 82 | −0.077 | 0.495 | −0.0091 | [−0.0385, +0.0203] | 0.222 |
| SELL only | 103 | +0.072 | 0.485 | +0.0070 | [−0.0130, +0.0271] | 0.198 |

⭐ **This is now a properly powered negative, not a decorative one.** The test can detect
|ρ| ≈ 0.15 and measures −0.018 with a permutation p of 0.81. ⇒ **Claude's demand was right and its
prediction was wrong:** the conclusion "the system's own ranking carries no selection premium" does
**not** rest on the underpowered decile contrast any more — it now rests on a statistic that would
have found a real effect of plausible size. ⚠ **What remains true from Claude's objection:** a ρ of
0.05–0.10 is still not excluded, and ChatGPT's collider point (R4-15) still applies — this is
predictive power **within gate-passers**, which is the conditional quantity, not the unconditional
one. **The unconditional test is 3b (§12.15), and it has not been run.**

### R7-B2 Direction × confidence — Kimi Q7's hypothesis REFUTED

Kimi asked whether the 80–84 dip is SELL-concentrated, which would make the story *"the score
mis-ranks shorts"* (repairable) rather than *"the score is uninformative"* (fatal). `[measured]`:

| bucket | BUY n | BUY mean R | SELL n | SELL mean R |
|---|---:|---:|---:|---:|
| 70–74 | 45 | −0.019 | 30 | **−0.368** |
| 75–79 | 12 | +0.063 | 26 | −0.032 |
| **80–84** | 18 | **−0.433** | 24 | **−0.186** |
| 85–89 | 6 | −0.225 | 21 | −0.129 |
| 90+ | **1** | +1.093 | 2 | −0.201 |

⛔ **REFUTED: 80–84 is the worst bucket in BOTH directions.** It is not a shorts artifact. ⭐ **And
round 6's "the only positive cell has n=3" is worse than reported — the positive half of it is ONE
BUY trade at +1.09R.** ⚠ Every cell here is n ≤ 45; the honest reading of the whole table is that
confidence and outcome are unrelated and the bucket pattern is noise, which is what R7-B measures
directly.

### R7-C ⭐⭐ The level stage, simulated — Claude Finding D, the best new finding of round 7

**Claude alone spotted this, and it is the largest number in the denominator chain that six rounds
walked past:** 289 of 475 gate-passing swing panels (**60.8%**) die at the level stage, on a
criterion (`safe_levels` → nearest swing pivot) that §4.4 says selects **tight** stops and §12.1/§7
say tight stops are the **worst** cohort. `[measured]` Re-simulating those 289 panels with the pivot
stop replaced by a fallback, everything else identical:

| cohort | rule | n | mean R | SE | t | win | med stop width |
|---|---|---:|---:|---:|---:|---:|---:|
| **accepted** (the 185) | pivot | 185 | **−0.1489** | 0.0645 | −2.31 | 39.5% | 4.65% |
| **rejects** | flat 5% | 288 | **−0.0923** | 0.0583 | −1.58 | 41.3% | 5.00% |
| **rejects** | 2×ATR20 | 286 | **−0.0803** | 0.0470 | −1.71 | 44.1% | 6.57% |
| rejects, BUY only | flat 5% | 120 | −0.0419 | 0.0812 | −0.52 | 45.8% | — |
| rejects, BUY only | 2×ATR20 | 120 | −0.0609 | 0.0642 | −0.95 | 46.7% | — |

**Paired by entry date** (the estimator that shares the day's market conditions):

| rule | shared days | **mean(reject − accept)** | SE | t |
|---|---:|---:|---:|---:|
| flat 5% | 56 | **+0.1599R** | 0.1114 | **+1.43** |
| 2×ATR20 | 55 | **+0.1661R** | 0.1076 | **+1.54** |

⛔⛔ **AND THEN IT DID NOT SURVIVE THE GAP FILTER — see §12.16 R7-K correction 1.** On clean windows
the paired contrast falls to **+0.0953R (t 0.69)** and **+0.0887R (t 0.66)**, and **on the clean
tradeable book it REVERSES** (rejects BUY −0.1180R vs accepts BUY −0.0843R). **The +0.16R below was
substantially gap contamination plus a shorts effect.** ⭐ Claude's structural point — that the
largest filter in the pipeline had never been evaluated — stands and is still the best contribution
of the round; the effect does not. **Read the rest of this section as the measurement that closed the
question, not as a finding.**

⇒ **SUPPORTED, NOT ESTABLISHED — and the distinction matters.** The cohort the level stage discards
**outperforms the cohort it keeps by ≈ +0.16R**, the sign is identical under two independent fallback
rules and under both the unpaired and paired estimators, and the mechanism Claude predicted is
visible (rejects carry **wider** stops: 5.00%/6.57% vs 4.65%). ⚠ **But t = 1.43–1.54 is not a
result.** At this SE the MDE is ≈ +0.22R, so a real +0.16R effect is exactly the size this test
cannot resolve — the §4.1 error again, now in my own measurement, and stated before anyone else says
it.

~~⭐ What it changes anyway, regardless of significance: +0.16R is larger than the entire deficit;
288 extra trades available today; the live branch of the repaired KILL LINE 3. ⇒ this goes into the
cut at stride 1 and `--clean-only`.~~
⛔ **WITHDRAWN — `--clean-only` RAN (R7-K) and the effect did not survive it.** What survives is
narrower and still worth keeping: **the level stage yields +223 simulable trades on clean data**, so
it remains the cheapest way to enlarge a sample, and **3b's branch of KILL LINE 3 still needs its own
endpoint** (§12.15) — it just cannot be justified by an anti-selectivity effect any more.

### R7-D ChatGPT §3's portfolio-space dependence — right question, wrong coordinate

`[measured]` on the same 263 overlapping pairs:

| unit | ρ̄ |
|---|---:|
| R (winsorized) | −0.0126 |
| raw return % | −0.0113 |
| **cash P&L (₹)** | **+0.0282** |
| downside: P(both lose \| overlap) 0.327 vs P(lose)² 0.354 | **lift 0.925×** |

⇒ ⛔ **ChatGPT's specific fear does not materialise: all three units agree at ≈ 0, and co-losing is
*less* frequent than independence would give (0.925×).** ⚠ **But the distinction ChatGPT drew is
still correct in principle, and the reason it doesn't bite here is an identity it did not invoke:**
risk-first sizing fixes every position's *planned* loss at the same ₹2,000, so cash P&L ≈ R × a
constant and ρ̄(cash) cannot diverge far from ρ̄(R). **The mechanism that DOES bite is direction, not
unit (R7-A2)** — so the right version of ChatGPT's point is *"you measured dependence on a book that
is 56% short."* Same conclusion, different coordinate. Full credit for the challenge; the coordinate
is corrected.

### R7-E ⭐ Empirical Kelly — three reviewers were right about the instrument, and the conclusion hardens

`[measured]` `max_f E[log(1+fR)]` on the actual net distribution, replacing `f* = p − q/b`:

| book | n | mean R | **f\* (empirical)** | μ/σ² | **90% bootstrap CI on μ/σ²** |
|---|---:|---:|---:|---:|---|
| ALL, gross | 185 | −0.1489 | **0.0000** | −0.193 | [−0.4495, **−0.0459**] excludes 0 |
| **BUY, gross** | 82 | −0.0992 | **0.0000** | −0.108 | [−0.4994, **+0.0678**] **includes 0** |
| ALL, net (−0.111R) | 185 | −0.2599 | **0.0000** | −0.337 | [−0.6547, −0.1564] excludes 0 |
| **BUY, net (−0.111R)** | 82 | −0.2102 | **0.0000** | −0.229 | [−0.7217, **−0.0164**] **excludes 0** |

⭐ **The conclusion survives the correct instrument and is sharper than the wrong one gave.**
`f* = 0.0000` exactly — the objective is monotone decreasing in `f`, so the growth-optimal bet is not
"small", it is **none**. ⚠ **§12.11a's `f* ≈ −0.5` was wrong in magnitude by ~2.6×** (the continuous
estimator gives −0.19); direction unchanged. ⭐ **And Claude's prediction was RIGHT on the honest sample** —
it forecast "the upper end of f\* will not be far below zero", and on the **clean** BUY book the
interval is **[−0.8443, +0.0163], which includes zero** (R7-K correction 2). ⛔ **So my claim that
"after costs the growth-optimal fraction is negative with 90% confidence on the tradeable book" is
TRUE on the all-windows sample above and FALSE on the clean one. Withdrawn.** ✅ **What survives in
every cell: `f* = 0.0000` exactly** — the objective is monotone decreasing in `f`, so the
growth-optimal bet is not "small", it is **none**, and that does not depend on the interval.

### R7-F Winsorization state — Claude Q5 answered, and the tail claim stands unassisted

`[measured]` **0 of 185 trades were clipped at ±10R (0.00%).** Every round-6 moment is therefore raw:

| unit | mean | sd | skew | **excess kurtosis** |
|---|---:|---:|---:|---:|
| R (winsorized ≡ raw) | −0.1489 | 0.8776 | +1.76 | **+8.19** |
| raw return % | −0.3279 | 3.1689 | +0.43 | **−0.25** |
| return ÷ ATR20 | −0.1391 | 1.2673 | +0.40 | **+0.02** |

⇒ **§12.10b's denominator finding owes nothing to clipping.** ⚠ And it sharpens §12.12's relevance to
`WINSOR_R`: on **this** sample the winsor bound is inert, so the memory's "ten trades own the answer"
finding belongs to the **corpus** (where stops of 0.23–0.86% produced |R| > 10), not here — another
place the two samples must not be blended.

### R7-G2 The CA detector — Claude Q6 was right to ask

`[measured]` 1 hard drop (|1-day move| > 25% inside the **trade** window). Widening to |move| > 8%
across the **300-bar scoring** window flags **133 of 185 trades (71.9%)**.

⇒ **The 1-in-185 figure is a statement about a narrow detector, not about clean data.** It looks only
inside the holding window and only above 25%. ⚠ **But the 71.9% is not evidence of CA contamination
either** — an 8% single-day move is ordinary in a mid-cap, and **the discriminating leg of the test
(a >8% name move on a <2% index day) is BLOCKED: `index_ohlcv_1d` holds 51 rows.** ⇒ honest verdict:
**unresolved, and unresolvable until the index backfill is redone.** Memory's 49-unadjusted-CAs
finding came from the corpus's universe and window, so it does not transfer either (§12.13b).

### R7-H Overlap-corrected t — the daily series, per the harness rule

`[measured]` `newey_west_t(daily mean R, lag = 4)`:

| book | daily obs | mean | naive t | **Newey-West t** |
|---|---:|---:|---:|---:|
| ALL | 92 | −0.1259 | −1.63 | **−2.01** |
| BUY | 57 | −0.1665 | −1.72 | **−1.91** |

⚠ **Neither reaches |t| = 2 on the day-weighted series**, and the direction of the correction is
*away* from zero here rather than toward it — a reminder that Newey-West corrects an SE, it does not
uniformly deflate. **Report both bases**: the trade-weighted BUY t is −0.94, the day-weighted
BUY NW t is −1.91, and the gap is composition (days carrying more trades are not the average day).
**Neither basis reaches significance on the tradeable book.**

### R7-J ⭐⭐ Gemini's regression — its hypothesis is REFUTED, and it turned up the only t ≥ 3.6 in seven rounds

Gemini's one runnable new ask, and **the single most productive reviewer contribution of round 7
measured by surprise per minute of compute.** Its hypothesis: the stop-width gradient is a proxy for
volatility. `[measured]` OLS, iid SEs, 185 trades (BUY-only in brackets):

| model / regressor | β | SE | **t** | 90% CI | R² |
|---|---:|---:|---:|---|---:|
| **`Rw ~ stop_width%`** (univariate) | +0.06499 | 0.02821 | **+2.30** | [+0.019, +0.111] | 0.028 |
| **`Rw ~ stop_width% + ATR% + RVOL + log(close)`** | | | | | **0.100** |
|   stop_width_pct | **+0.06302** | 0.02765 | **+2.28** | [+0.018, +0.109] | |
|   atr_20_pct | −0.03113 | 0.07277 | **−0.43** | [−0.151, +0.089] | |
|   **rvol_20** | **+0.19811** | 0.05400 | ⭐ **+3.67** | [+0.109, +0.287] | |
|   log_close | +0.03141 | 0.04558 | +0.69 | [−0.044, +0.106] | |
| **`ret_pct ~ same`** (no R denominator) | | | | | **0.009** |
|   stop_width_pct | +0.11235 | 0.10480 | **+1.07** | [−0.060, +0.285] | |
|   rvol_20 | −0.05770 | 0.20469 | **−0.28** | [−0.394, +0.279] | |
| BUY only: stop_width (with controls) | [+0.04725] | 0.04447 | **[+1.06]** | [−0.026, +0.120] | 0.134 |
| **BUY only: rvol_20** | **[+0.19501]** | 0.06207 | ⭐ **[+3.14]** | [+0.093, +0.297] | |

`corr(stop_width%, ATR%) = +0.108` (Spearman) — **barely correlated, so the two are cleanly
separable here.**

⛔ **GEMINI'S HYPOTHESIS IS REFUTED.** The stop-width coefficient does not shrink under the
controls (+0.065 → +0.063), and **ATR% is insignificant with the wrong sign** (t = −0.43). The
gradient is **not** an ATR proxy — ⚠ **but see R7-K correction 3: on clean windows the gradient
COLLAPSES (t +1.06) and on the clean tradeable book its SIGN FLIPS NEGATIVE.** Gemini asked the right
question and the answer to the underlying worry turned out to be worse than the hypothesis it
proposed.

⭐⭐ **But the regression found something nobody was looking for: RVOL-20 at t = +3.67 (and +3.14 on
the tradeable book alone) — the ONLY coefficient in seven rounds and twenty-five reviews to clear
this programme's own t ≈ 3.6 promotion bar (H8, `app/services/dsr_control.py`).** It is also the largest
term in the model; it triples R² (0.028 → 0.100) where stop width alone barely moved it.

### ⛔ And then our own round-6 rule disqualifies it. Read this before getting excited.

**Four reasons it must NOT be promoted, in descending order of how fatal they are:**

1. ⛔⛔ **IT DOES NOT EXIST IN THE UNIT WE COMMITTED TO TESTING IN.** In raw return %, RVOL is
   **t = −0.28** — sign-flipped and nowhere near significance. §12.10b's own adopted rule is *"keep R
   for position sizing; report and test in bps and ATR units"*, and **in bps this effect is absent.**
   A variable that predicts `ret/stop_width` but not `ret`, with `stop_width` already in the model,
   is predicting the denominator's interaction, not the return. ⭐ **§12.10b — round 6's cheapest
   finding — has now disqualified round 7's most exciting one.**
2. ⛔ **The same disqualification lands on the stop-width gradient itself:** significant in R
   (t = +2.30), **absent in raw % (t = +1.07)**, and **absent on the tradeable book (t = +1.06)**.
   ⇒ **the stop-width finding of 2026-08-25 — which independently "reproduced the `sl_atr` gate at
   its exact 1.0× threshold" — is substantially a DENOMINATOR EFFECT.** That is a partial refutation
   of one of our own standing results, produced by a reviewer's control variable.
3. ⛔ **D1 already tested RVOL read-only and REFUTED it** (2026-09-08): elevated RVOL mildly inverse,
   injecting it into the scorer gave **−0.291R at t = −2.91**. ⚠ **The two are not strictly
   contradictory** — D1 asked *"does adding RVOL to the confluence score improve outcomes"*, R7-J
   asks *"conditional on a signal existing, does entry-day RVOL predict its R"* — but a variable that
   is inverse as a generator and positive as a conditioner, in one unit only, is a **red flag for a
   denominator artifact, not a discovery.**
4. ⚠ **Multiplicity and provenance.** This is **1 of 16 coefficients** printed in this table alone
   (4 regressors × 2 units × 2 cohorts); at Bonferroni-16 the 5% threshold is t ≈ 2.96, which it
   clears — but the honest denominator is the whole round-7 search, which is far larger. **And the
   universe carries 46% look-ahead survivorship** (R7-7), so this is not even a clean sample.

⇒ ⭐ **VERDICT: RECORDED, NOT PROMOTED, and it is a queued test rather than a finding.** The
pre-registered form, if it is ever run: **`ret_pct` (and `ret/ATR20`) ~ RVOL on a point-in-time
universe, gap-clean windows, long-only, with `newey_west_t`, against the t ≈ 3.6 bar.** ⚠ **On
present evidence the prior is that it returns nothing**, because the effect is already absent in
raw % on this very sample. ⛔ **Under §16.1's rules and CLAUDE.md's standing rule — "NEVER flip a
gate/knob on an argument, check the accruing data first" — this is exactly the shape of the two
gates that were promoted and refuted in 2026-09.** It is logged here so that it cannot be
rediscovered in round 9 and mistaken for new.

⭐ **Credit, unreservedly: Gemini asked for one control variable and it partially refuted one of our
own findings and surfaced the only t ≥ 3.6 the programme has produced.** §16.2's prescription —
*"pick ONE number, plug it in, print the result"* — worked exactly as written, on the first attempt.

### R7-A3 ⭐⭐ And the consequence: §12.10a's headline INVERTS A THIRD TIME on the tradeable book

§12.10a's blockquote is the most-quoted sentence in the document:

> ~~"The corpus can detect a gross edge of +0.027R to +0.040R, which is *below* the +0.051R of
> explicit charges. **Anything that nets positive is detectable with room to spare.**"~~

`[derived]` Recompute it with the long-only book's own σ (0.957) and its own inflation (1.21) — per
§16.1's new rule that σ, n and I must share a sample tag:

| basis | n | σ | I | MDE @ t=2 | Sharpe-1.0 gross | detectable | **vs explicit friction 0.051R** |
|---|---:|---:|---:|---:|---:|---:|---|
| corpus, mixed (as printed) | 1,975 | 0.878 | 1.00 | +0.0395 | +0.1895 | ×4.80 | **below — claim holds** |
| **corpus, long-only (44.3% assumed)** | **875** | **0.957** | **1.21** | **+0.0714** | +0.2052 | ×2.87 | ⛔ **ABOVE — claim FAILS** |
| live book, 3 yr, long-only | 375 | 0.957 | 1.21 | +0.1087 | +0.2052 | ×1.89 | ⛔ above |
| **this probe, BUY-only** | **82** | 0.957 | 1.21 | **+0.2325** | +0.2052 | ⛔ **×0.88** | ⛔ above |

⚠ **The middle row violates §16.1's own sample-tag rule and is labelled so deliberately** — it
applies the probe's 44.3% long share, its σ and its inflation to the corpus's n. It is an
**illustration of the direction and rough size of the correction, not a measurement**, and the
correct version is §16.3 item 1. ⭐ **Two things bias it in opposite directions:** the corpus is
mixed-**class** and `positional` is 100% BUY (R7-A), so its long share is probably **higher** than
44.3%; but positional σ_R is **1.844–2.088**, so its σ is probably **higher** too — and σ hurts the
MDE linearly while n helps only as √n. **Both point the same way for the verdict.**

⇒ ⛔ **The blockquote is WITHDRAWN for the tradeable book.** Three corrections compound: the corpus
loses 55.7% of its rows to untradeable shorts, σ rises 0.878 → 0.957, and inflation rises 1.00 →
1.21. **The long-only corpus cannot detect an edge below explicit friction**, and **the 185-trade
probe cannot detect a Sharpe-1.0 edge at all (×0.88).**

⭐ **What survives, and it is still a real change from rounds 3–5:** a *Sharpe-1.0-class* edge remains
detectable on the long-only corpus at **×2.87** — so "can this ever be validated?" is still answered
yes, and §12.5's "2.8–3.8× short" is still retired. **What does not survive is "with room to spare."**
The margin between a world-class edge and break-even on the tradeable book is **0.205R − 0.111R =
0.094R against an MDE of 0.071R — a 1.3× margin, not a 4× one.**

⚠ **This is the third inversion of this headline in three rounds** (§12.8 → §12.10a → here), and the
pattern is now diagnostic rather than embarrassing: **every inversion came from measuring an input
that had been assumed, and every one moved in the direction of "the sample is smaller and the
population narrower than the number implied."** ⇒ **§16.1's sample-tag rule exists to make the next
one impossible, not to apologise for these.**

### R7-K ⭐⭐ THE CLEAN × LONG-ONLY CELL — the honest estimate, and it corrects three of my own round-7 claims

`--clean-only` re-runs the identical walk with gap-straddling windows **excluded at the panel stage**
(10,966 panels, 408 gate-passers, 372 swing, 224 level-stage rejects, **147 trades**). Crossing it
with the direction split gives the one cell every conclusion actually depends on: **the tradeable
direction, on data that exists.**

| restriction | n | mean R | **σ_R** | SE | **t** | inflation | **MDE @ t=2** |
|---|---:|---:|---:|---:|---:|---:|---:|
| mixed, all windows *(round 6)* | 185 | −0.1489 | **0.878** | 0.0645 | **−2.31** | 1.00× | +0.129 |
| mixed, clean windows | 147 | −0.1341 | 0.911 | 0.0751 | −1.79 | 0.92–0.99× | +0.150 |
| BUY, all windows | 82 | −0.0992 | 0.957 | 0.1057 | −0.94 | 1.19–1.23× | +0.235 |
| ⭐ **BUY, clean windows** | **61** | **−0.0843** | **1.0050** | 0.1287 | **−0.66** | **1.24–1.43×** | **+0.287 … +0.308** |

⛔ **SUPERSEDED BY ROUND 8 (§12.18, C3): the ladder is NOISE — 0.62 SE by this document's own
`SE(s)` estimator, and t = 0.82 on a proper two-sample test against the derived complement (n=124,
σ 0.811).** "Halfway back to 1.489" is not evidence of anything and "every correction moves it the
same way" is not a pattern. ✅ **The corpus-vs-probe gap (5.93 SE) is unaffected and still real.**

~~⭐⭐ σ_R rises MONOTONICALLY as the population is restricted: 0.878 → 0.911 → 0.957 → 1.005, halfway
back to the corpus's 1.489.~~ The ordering is as stated; **the magnitude is within noise.** **The same is true of dependence: 1.00× → 1.24–1.43×**
(ρ̄ ≈ **+0.26** at the observed m = 2.28, higher again than the +0.19 of R7-A2).

⇒ ⭐ **THE HONEST ESTIMATE OF THE TRADEABLE BOOK IS `n = 61, −0.084R, t = −0.66`** — and round 8
corrects both the MDE and the verdict. **The real MDE at 80% power is +0.417R, not +0.29R** (C1:
`2·SE` is 50% power). ⛔ **And "uninformative / empty, not negative" is WITHDRAWN** (D4): the posterior
against the 0.111R net break-even gives **P(positive net edge) = 0.4%–5.7%** across prior sds from
0.03R to 0.20R ⇒ **economic closure without statistical closure**, which is §17 Q7-1's option **(iii)**
and neither of the two branches I wrote. ⚠ **And the NET test is not uninformative at all: costed per
trade rather than by a scalar, BUY-only reads −0.2435R at t = −2.19** (§12.18g). Round 6's t = −2.31 does
not survive *either* correction, and it survives their conjunction least of all.

#### ⛔ Three corrections this forces on my own round-7 sections above

1. ⛔⛔ **R7-C — CLAUDE'S FINDING D DOES NOT SURVIVE.** On clean windows the paired contrast falls
   from **+0.1599R (t 1.43) → +0.0953R (t 0.69)** at a flat 5% stop and **+0.1661R (t 1.54) →
   +0.0887R (t 0.66)** at 2×ATR20. **And on the clean tradeable book it REVERSES: rejects BUY
   −0.1180R vs accepts BUY −0.0843R** — the level stage's discards are *worse*, not better.
   ⇒ **the +0.16R was substantially gap contamination plus a shorts effect.** ⭐ **Claude's
   STRUCTURAL point stands undiminished and remains the best contribution of the round — the largest
   filter in the pipeline had never been evaluated as a selector, and now it has been.** What does
   not stand is the effect. **The honest verdict is: the level stage is not measurably anti-selective
   on clean, tradeable data, and the question is closed at this sample size rather than promoted to
   plan item 2′.** (It remains worth re-asking at stride 1, but it is no longer a lever — see the
   plan note below.)
2. ⛔ **R7-E — I over-claimed the Kelly interval.** *"After costs the growth-optimal fraction is
   negative with 90% confidence on the tradeable book alone"* is true on the all-windows BUY sample
   (CI [−0.7217, −0.0164]) and **FALSE on the clean one: [−0.8443, +0.0163] INCLUDES ZERO.** ✅ What
   survives unchanged: **`f* = 0.0000` exactly in every cell** — the objective is monotone decreasing
   in `f`, so the growth-optimal bet is *none*, and ⭐ **Claude's prediction that "the upper end of
   f\* will not be far below zero" is CORRECT on the honest sample.** Credit where it is due.
3. ⛔ **R7-J — the stop-width gradient collapses entirely, which is a STRONGER refutation than the
   unit argument.** ALL: **t +2.30 → +1.06** univariate, **+2.28 → +1.12** with controls. **BUY-only,
   clean: the sign FLIPS NEGATIVE** (−0.032 univariate, t −0.56; −0.019 with controls, t −0.34).
   ⇒ **the 2026-08-25 stop-width finding survives NEITHER the unit change NOR the gap filter.** It
   was a gap-contaminated, R-denominator artifact. ⚠ **`sl_atr`'s independent "reproduction" of that
   gradient at 1.0× inherits the same defect and must be re-read accordingly** — it was already
   DECIDED: NO at t = 0.41 against the 3.6 bar, so nothing downstream changes, but the reason it was
   wrong is now known.

#### ⚠ What round 7's OWN instruments have NOT had done to them

`instrument_self_validation` is a standing rule here: **every metric gets the H8 treatment — reject a
known null, accept a planted edge, and prove the design choice — run on the real book, and expect it
to carry the defect it hunts.** Four estimators were written this round and **none has had that
treatment**: `spearman` + `perm_p` (R7-B), `ols_slope` / `ols_multi` (R7-J), `kelly_empirical`
(R7-E), and `simulate_rejects` (R7-C).

**What they DO have, stated so the gap is not overstated either:** the probe **reproduces every
round-6 number exactly** (16,428 panels · 514 gate-passers · 185 trades · σ_R 0.8776 · ρ̄ −0.0126 ·
Δ_select +0.0447/t +0.29), which validates the shared walk but **nothing new**; the permutation
p-values behave (0.807 at ρ = −0.018, and 0.752 at ρ = −0.074 on an independent 20-trade run);
Spearman's sign **flips between the all-windows and clean samples**, which is what noise does and
what a broken estimator would not reliably do; and `kelly_empirical` returns the boundary solution
`f* = 0` on four independent negative-mean samples, which is the analytically correct answer.

⚠ **The one that most needs the treatment is `ols_multi`**, because it produced the round's only
t ≥ 3.6. A planted-edge arm (inject a known coefficient into a shuffled column and confirm recovery)
and a null arm (16 coefficients on permuted outcomes, confirming ~0.8 of them clear t = 2 by chance)
are both cheap. ⭐ **Until that runs, R7-J's RVOL result carries one more reason to stay
"recorded, not promoted" than the four already listed** — and it is a *fifth* reason, not a
restatement of the unit argument.

#### ⭐ And one thing that got STRONGER

⛔⛔ **SUPERSEDED BY ROUND 8 (§12.18e): RVOL WAS AN IID-STANDARD-ERROR ARTIFACT.** Under **HC3 its
t is +0.61** (BUY-only +0.53) and **date-clustered +0.98** (+0.90) — HC3 inflates the SE **six-fold**
(0.0540 → 0.3235), and 185 trades sit on only **92 distinct entry dates** while RVOL is a market-wide
*daily* quantity. It is robust to the *gap filter* and not to the *estimator*. ⇒ **"the single most
robust coefficient in the document" and the "uncomfortable pair" below are both WITHDRAWN — there was
no pair, and the unit was never the only problem: the SE was.**

~~**`RVOL-20` is robust to the gap filter: t = +3.65 (ALL, clean) and +3.13 (BUY-only, clean)**~~, against
+3.67 / +3.14 on all windows — essentially unmoved, and it triples R² in both. ⛔ **And it is still
`t = −0.36` in raw return % (BUY-only: −0.67).** ⇒ **the only thing that kills it is the unit, and the
unit is the one §12.10b commits us to.** ~~It is now the single most robust coefficient in the document
and the single most firmly disqualified, which is an uncomfortable pair.~~ ⛔ **Withdrawn — §12.18e.** **Its pre-registered form (R7-J) is unchanged and its prior is unchanged:
`ret_pct` and `ret/ATR20`, point-in-time universe, gap-clean, long-only, `newey_west_t`, against
t ≈ 3.6.**

⚠ **Everything else is stable across the filter**, which is worth recording because it bounds how much
the hole distorted: Δ_select stays noise (**ρ +0.042 ALL / +0.025 BUY**, permutation p 0.60 / 0.85 —
sign-flipped from −0.018, which is what noise does) · portfolio-space ρ̄ still ≈ 0 in all three units
(−0.022 R / −0.012 % / **+0.029 cash**, downside lift 0.945×) · 0 of 147 winsorized · defect #4 at
1.36% · Newey-West **−1.75 ALL / −1.97 BUY**. ⭐ **And the gate pass rate is HIGHER on clean windows —
3.72% vs 3.13% — so gap-straddled panels were LESS likely to pass the gate**, one more way the hole
was silently shaping the sample.

## 12.17 The rest of round 7, answered from the source

| # | reviewer point | verdict |
|---|---|---|
| **R7-1** | **Claude: the ex-date question has a THIRD answer** — neither a bug nor an accurate simulation, but a **missing operational rule**: no operator holds through an ex-date with an unadjusted resting stop, so the correct simulation *is* the correct operating procedure (scale stop and target by the CA factor, or flatten) | ⭐ **ACCEPTED, and it dissolves Kimi Q5.** The ambiguity was never about data. `[code]` `backtest/engine.py` has no ex-date handling and stops fire at the raw price; 6.8.5 already CA-adjusts **open paper positions** R-preservingly on the ex-date (`migration a7b8c9d0e1f2`) — so **the live side already implements Claude's rule and the backtest does not.** `[code]` `app/services/ca_adjust.py`'s own docstring states the invariant Claude proposes — *"R and reward:risk are preserved EXACTLY… entry scales by the nominal ratio, matching the exchange's ex-date price adjustment"* — with the ratio taken from a **verified** `corporate_actions` row, never a price gap. ⇒ **this is a PARITY DEFECT WITH A WRITTEN PRECEDENT, not an open modelling question.** ⚠ **And the honest caveat: the live rule cannot fire either — `corporate_actions` = 0 rows**, so the code is correct and inert. The decision Kimi asked for is therefore already made in our own repository; what is missing is the event source, on both sides |
| **R7-2** | **Claude: scorer provenance means the holdout is insurance for the next thing, not a precondition for judging this one** | ✅ **ACCEPTED.** `[git]` `confluence.py` 2026-07-03, first corpus analysis 2026-08-12. A clean out-of-sample read on the **base scorer** already exists; 0a.1 protects everything authored after 08-12 (the overlays, shadow gates, retunes). ⇒ **0a.1 stays first in the cut** (it costs nothing) but **stops being a blocker for 3b** |
| **R7-3** | **Claude: slippage uncertainty does not change the verdict, only the hurdle** | ✅ **CONFIRMED by arithmetic.** Against a measured gross of −0.149R the book is net-negative by **0.24R at 10 bps/leg and 0.32R at 30 bps** — every point in the range. ⚠ **This refines Kimi Catch 5**, which puts the slippage measurement "at the front of the plan": it belongs at the front of *deciding whether a future edge clears costs*, and nowhere in *the current verdict*. Both are right about the magnitude; only Claude is right about the priority |
| **R7-4** | **ChatGPT §8: "the fat tails are manufactured by our own denominator" is too absolute** | ✅ **REFINED, ChatGPT is right.** Adopted wording: **R introduces denominator-induced heteroskedasticity and exaggerates tail shape; it does not prove the strategy carries no tail risk.** Keep R for sizing; test hypotheses in bps and ATR multiples. §12.10b's conclusion is unchanged, its phrasing is |
| **R7-5** | **ChatGPT §3: R-correlation ≠ portfolio correlation; measure cash-P&L and downside dependence** | ✅ **VALID and MEASURED — see §12.16 R7-D.** The distinction is real: R is barrier-truncated *and* divided by a stop width that varies with CV 0.51, so ρ̄(R) ≈ 0 is compatible with correlated ₹ outcomes. ⚠ **But note the sizing identity that blunts it:** risk-first sizing makes every position's *planned* loss the same ₹2,000, so cash P&L is ≈ R × a constant, and ρ̄(cash) cannot diverge from ρ̄(R) as much as ChatGPT's framing implies. Measured below |
| **R7-6** | **ChatGPT §4 / Kimi Catch 3: stride 10 is a diagnostic, not a final distribution estimate** | ✅ **ACCEPTED and relabelled.** ⚠ **Kimi is right that §12.10d's "brackets rather than refutes" was backwards** — concurrency 2.08 does not bracket 12, it samples a different regime. The dependence result survives (ρ̄ is per-pair; the calendar-block bootstrap prices the overlap that exists); **σ_R and the mean do not**, and §12.13b now lists five reasons they cannot be transferred |
| **R7-7** | **ChatGPT §14 / Claude Q9 / Gemini item 5: the universe selector was diagnosed and not repaired — and the round-6 probe inherited it** | ⭐ **CONFIRMED, and quantified for the first time.** `[code]` `swing_dependence_probe.py:46-49` ranks by `time > now() - interval '180 days'` — **today's liquidity, as-of-today, for a walk that starts in 2019.** `[db]` The bias: of the top-250 by median traded value **as of 2021-01-01, only 135 (54.0%) are in today's top-250 — 46% of the real 2021 universe is invisible to the probe**; and **1,294 names that are inactive today held >100 bars in H2-2020**, so the DB is not the constraint, the query is. ⇒ **0a.3 rises in the cut**, and it now covers three probes, not two |
| **R7-8** | **ChatGPT §12/§18: three truths (market / decision / execution), a `DecisionSnapshot` causal chain, and split the archive from the contract** | ✅ **ACCEPTED, all three.** The `DecisionSnapshot → OrderIntent → Execution → PositionLifecycle → PerformanceRecord` chain is the right schema for Week-0 #2 (the append-only ledger) and supersedes the vaguer "log orders" framing. And §18 is correct that this document has become **both history and specification** at 2,094 lines — that is exactly how §16.1 came to contradict §12.11b. ⇒ **acted on: the reference card is now the contract and is individually stamped; PART IV is explicitly the archive** |
| **R7-9** | **ChatGPT §13: CA price reconstruction ≠ information chronology** | ✅ **ACCEPTED and it sharpens R5-4.** A Kite-adjusted ÷ our-unadjusted ratio reconstructs *prices* correctly and says nothing about *when the adjustment became knowable*. ⇒ the CA table needs `economic_event_time · announcement_time · effective_time · knowledge_time · factor · type · source · source_version`, and a backtest must read it as-of `knowledge_time`. ⚠ **Second-order for our actual use** (splits and bonuses are announced weeks ahead of the ex-date, so `knowledge_time < effective_time` in essentially every case), but it costs nothing to store and cannot be reconstructed later |
| **R7-10** | **Gemini item 1: "fix the DB data-plane leak — ensure pytest never connects to `DATABASE_URL`"** | ⛔ **ALREADY SHIPPED, 2026-09-07.** `[code]` `tests/conftest.py:36` `_refuse_non_test_database()` aborts at import time unless every URL names a database ending `_test`; backups run `0 11 * * 1-5`. Gemini's own table lists this as a live "Critical Infra Defect". **This is the fourth time Gemini has asserted a state without checking it** — and the first where the answer was already in the document it was reviewing |
| **R7-11** | **Gemini item 3: "fix harness defect #4 at `backtest/engine.py:212` — ensure gap exits fill at candle open"** | ⛔ **WRONG FIX, WRONG LINE, RIGHT DEFECT.** `[code]` `engine.py:212` is `entry_price = float(fill_candle["open"])` — the *correct* fill. Gap exits **already** fill at the open: `engine.py:249-255` returns `_exit(i, o, sl=True)` for any bar after the fill. The actual defect is narrower: **on the FILL bar the gap branch is deliberately skipped** (`if i > fill_idx`), so an entry that opens *through* its own stop is filled anyway and then "stopped out" at the stop — **above its entry, booking ≈ +1R.** ⇒ the repair is a **through-stop rejection at the fill**, mirroring `paper_broker:544-554` which already has one. ⚠ And `engine.py` is **FROZEN**: the fix needs sign-off, an §8 regression and regenerated Rust fixtures in the same commit |
| **R7-12** | **Gemini item 2/3: Kite CA ratios and a stride-1 walk "from 2019-10 to 2026-09"** | ⛔ **BOTH REST ON DATA THAT DOES NOT EXIST** (§12.12). There are no bars for 2021-01 → 2023-06, so no ratio can be computed there and no walk can traverse it. Gemini's request is internally consistent and unrunnable |
| **R7-13** | ⭐ **Gemini item 4: a multivariate stop-width regression — `Gross_R ~ stop_width + ATR% + breakout_vol_ratio + log(close)` — to test whether the stop-width gradient is trade geometry or a proxy for volatility** | ⭐ ✅ **THE ONE GENUINELY NEW AND RUNNABLE ASK OF GEMINI'S ROUND, and it is the exact prescription §16.2 gave it working.** The gradient is load-bearing (it is the only surviving positive result in `POSITIONAL_REVIEW_FOR_QUANT.md` and it independently reproduces the `sl_atr` gate), and **nobody has ever controlled it for ATR%.** Measured in §12.16 R7-J. Credit where due: this is Gemini's first contribution since R4-24 |
| **R7-14** | **Kimi Catch 5: the whole game sits inside a 0.039R window and cycle 2 is the only instrument that can ever close it** | ✅ **the framing is right**, ⚠ **the priority is not** — see R7-3. And §12.12 changes the window: at the corpus's real σ the margin is wider or narrower depending on which σ belongs to it, which is now R7-Q2 |
| **R7-15** | **Kimi Catch 6c / Q6: shipped-status is stale by construction** | ✅ **ACCEPTED and answered.** `[git]` Since the document landed (2026-09-10): **four commits, all documentation.** Of the nine cut items, **one has shipped as code** — #10, measure ρ̄, delivered by `swing_dependence_probe.py` on 2026-09-11 (still **untracked**). **Zero Week-0 items.** ⛔ **50 days to the 2026-10-31 sunset**, and `cas_daily` holds **43 rows across 1 session** against a ≥30-session trigger |
| **R7-16** | **Kimi Part 6: "no round-N document ships until a script diff-verifies every §16.1 row against the latest measurements"** | ✅ **ADOPTED**, merged with Claude's sample-tag guard into one mechanism: §16.1 now carries **`sample` and `verified` columns per row**, and a row whose sample tag differs from the n it is being combined with is a defect by construction rather than by review |

## 12.18 ⭐⭐ ROUND 8 — an external audit recomputed round 7, and most of it holds

**Source:** `~/Downloads/round8-external-audit-2026-09-11.md` (727 lines), one of three round-8
responses. It is the first review in eight rounds to arrive as a **reproducible recomputation** rather
than a reading, and it is the strongest single review of the exercise. **Every number in it was
re-derived here independently before adjudication; 11 of 13 claims reproduce exactly.**

### 12.18a The scoreboard, and what it does to round 7

| # | claim | verdict |
|---|---|---|
| **C2** | the two round-7 "inversions" are **decompositions, not findings** | ⭐⭐ ✅ **CORRECT, and it is the largest defect in round 7** |
| **C8** | §17 Q7-1's premise is false — the equity-beta null **is computable today** | ⭐⭐ ✅ **CORRECT and decisive — built and measured, §12.20** |
| **C1** | every "MDE" is understated by exactly **1.40×** | ✅ **CORRECT** — `2·SE` is 50% power; 80% needs `2.8016·SE` |
| **C3** | the σ_R "monotone ladder" is **0.62 SE — noise** | ✅ **CORRECT**, and my own two-sample version gives **t = 0.82** |
| **C4** | friction is a median-stop scalar applied as a book mean; `cost_in_R = 1/w` so Jensen bites | ⚠ **STRUCTURE CORRECT, magnitude committed the sample-tag error it diagnoses** — §12.18c |
| **C5** | §12.1/§12.2/§4.4 share one denominator and have had **neither** test that killed the swing version | ⭐ ✅ **CORRECT** — §12.18d |
| **C6** | the only t ≥ 3.6 was computed with **iid SEs on leptokurtic, overlapping, date-clustered** data | ⭐ ✅ **CORRECT** — §12.18e |
| **C7** | the panel-level score test is **fully powered** and is item 8 of 8 | ✅ core **CORRECT**; ⛔ **consequence #3's derivation is wrong** — §12.18f |
| **D1** | the three surviving positive results are **one hypothesis**, not three | ✅ **CORRECT** |
| **D2** | ρ̄ is **flat in m** under a one-factor model; **hold period** is the bigger breadth lever | ⭐ ✅ **CORRECT — and it REFUTES my §17 Q7-2 and answers Q7-4** |
| **D3** | §4.5 uses `IR ≈ IC√BR`, the wrong law for a **tail selector** | ⭐ ✅ **CORRECT — it refines one of the panel's five round-1 "decisive" findings** |
| **D4** | the document runs a frequentist test where **the decision is Bayesian** | ⭐⭐ ✅ **EXACT — and it resolves Q7-1 with an option I had not considered** |
| **D5** | at the honest σ, **decade-scale validation is back** | ✅ **CORRECT** |

### 12.18b ⭐⭐ C2 — neither round-7 split separates. My headline framing is withdrawn.

`[verified]` Both splits, recomputed as the **contrast** rather than as two levels:

| split | group A | group B | **difference** | SE | **t** | p |
|---|---|---|---:|---:|---:|---:|
| **direction (R7-A)** | BUY −0.0992 (n=82) | SELL −0.1885 (n=103) | **+0.0893** | 0.1325 | **+0.67** | 0.50 |
| **gap filter (R7-I)** | clean −0.1341 (n=147) | straddling −0.2059 (n=38) | **+0.0718** | 0.1420 | **+0.51** | 0.61 |

And decomposing the R7-I t-drop, which I reported as evidence that "the hole biases the mean DOWN":

| step | t |
|---|---:|
| full sample | **−2.307** |
| clean n and σ, **mean held at −0.1489** | −1.982 |
| clean sample, actual | **−1.785** |

⇒ **0.325 of the 0.522 t-drop is power loss and only 0.197 is the mean moving.**

⛔⛔ **Two of round 7's headline sentences are therefore WITHDRAWN AS STATED:**

| ⛔ withdrawn | ✅ what the measurement supports |
|---|---|
| *"the significantly-negative gross edge is carried by the untradeable half"* | **"splitting the book by direction leaves neither half powered, and the halves do not differ (t = 0.67)"** |
| *"the hole biases the mean DOWN and σ DOWN"* | **"removing 38 gap-straddled observations costs enough power to drop the headline below significance (t = 0.51 on the contrast)"** |

⚠ **This is the deepest thing round 8 caught, and it is a failure of statistical reasoning rather
than of arithmetic.** Cutting a negative-mean sample in two **guarantees** one half is less negative;
I read the *level* in each half and called the ordering a finding. ⭐ **It is also the fourth distinct
instance of the same family in this document** — after the σ/n pairing, the gross-vs-net error and the
m=12-vs-2.5 row — and the family is now nameable: **a quantity computed on a subgroup is not evidence
about the subgroup until it is compared with the complement.**

⚠ **What survives, and it is not nothing.** The *structural* fact is unaffected by significance: **an
NSE cash-delivery account cannot hold an overnight short, so 55.7% of the resolved trades are
untradeable by construction, whatever their mean.** That is a statement about the instrument, not
about the data, and it is why the BUY-only cell is still the right population (§12.16 R7-K). **The
error was claiming the two populations *differ measurably*; the reason for preferring one of them was
never statistical.**

### 12.18c ⚠ C4 — the structure is right and the magnitude reproduces the very error it diagnoses

`cost_in_R = round-trip bps ÷ (100·w)`. Because `w` has CV 0.51 with real mass below 1%, Jensen gives
`E[cost_in_R] > cost_in_R(median w)` **strictly**, and the gap is driven by exactly the left tail
§12.10b identified as the denominator pathology. ⭐ **That is correct, it is load-bearing, and every
"net" figure in this document uses the scalar.**

⛔ **But the 1.68× understatement is computed from §7's POSITIONAL stop buckets and then applied to
this document's SWING median-stop scalar.** `positional` and `probe-185` are different samples with
different stop distributions — positional puts **119 of 391 trades under a 2% stop**, swing puts far
fewer. ⇒ **this is a `sample` tag violation under §16.1's own new rule, committed inside the audit
that is otherwise the most careful of the eight rounds.** Recorded without prejudice: the rule exists
because the error is easy, and this is its fifth instance with a different author.

✅ **Measured on the swing sample's own `w` in §12.18g.**

### 12.18d ⭐ C5 / D1 — three surviving positive results are one hypothesis with one untested denominator

`[verified by inspection]` **§12.1** (the reachable-cohort sign flip), **§12.2** (the dispersion lever)
and **§4.4/§7** (the wide-stop gradient) are all statements about `R = ret/w` **conditioned on `w`**.
R7-J and R7-K killed the **swing** member of that family twice — it vanishes in raw % (t +2.30 →
+1.07) and it collapses and flips sign under the gap filter. **The positional members have had
neither test**, and they still sit in Part I as "NEW AND DECISIVE", still carry "the largest single
recoverable term", and still generate plan item 18.

⭐ **The audit's sharpest structural point: treat them as ONE hypothesis with a shared failure mode,
not three independent lines of evidence.** ⇒ **plan item 2‴ (§13.8): re-report the positional family
in raw %, ATR units and net ₹, split by the gap flag.** If it dies the way the swing version did,
**§4.4, §12.1, §12.2, plan item 18 and the σ_R objective close on the same afternoon and the plan gets
shorter.** If it survives both tests it becomes the strongest result in the document instead of the
most fragile. **Either outcome is worth one afternoon; three findings resting on an untested
denominator is not.**

⚠ **And the audit's warning about §12.2 specifically is the one I would have missed:** *"a cohort
divided by a small number will always have the highest dispersion."* If σ_R falls because small
denominators were removed rather than because economic risk fell, the power gain is **nominal, not
real** — required n scales σ_R², so a mechanical σ_R reduction buys a mechanical and entirely
fictitious power gain. ⭐ Its own counter-evidence is equally sharp: the measured dispersion ratio
(2.566/1.844 = **1.39×**) is far below what pure `1/w` predicts (**≈5×**), so raw-return volatility
must rise steeply with stop width and partially cancel it — **the two effects are tangled and only the
raw-% and ATR versions can separate them.**

### 12.18f-C7 C7 — the core is right, and consequence #3 is wrong by √5

✅ **The core claim is correct and is the most useful thing in the audit after C2 and C8:** every
trade-level statistic in this document sits **three filters and a barrier simulator** downstream of
the question that decides the programme's direction, at n = 61 with an 80%-power MDE of **+0.417R**.
The upstream question — does the composite score carry cross-sectional information — sits on **16,428
panels across ~790 clean sessions** and needs no CA source, no index, no ledger, no holdout and no
barrier model. `[verified]` with per-date IC dispersion σ_IC = 0.10 and overlapping horizons treated
as h-fold redundant:

| dates | horizon | SE(IC) | t at IC=0.02 | t at IC=0.03 | MDE at 80% power |
|---:|---:|---:|---:|---:|---:|
| 790 clean | **5d** | **0.0080** | **+2.51** | **+3.77** | 0.0223 |
| 790 clean | 20d | 0.0159 | +1.26 | +1.89 | 0.0446 |
| 1,097 all | 5d | 0.0068 | +2.96 | +4.44 | 0.0189 |

⭐ ✅ **Consequence #2 is adopted and is a pre-registration detail nobody had stated: the horizon for
3b must be pre-registered at 5d.** At 20d the same test returns t = 1.26 against a break-even IC of
0.02 and **can only ever say INCONCLUSIVE** — KILL LINE 4's original defect, one level up.

⛔ **Consequence #3 — "`factor_sweep`'s verdict was a coin flip on its own arithmetic" — is wrong as
derived.** `[code]` `scripts/factor_sweep.py:271` is `keep = set(all_days[::horizon])`: **the 156
dates are already non-overlapping**, so applying a further ÷5 overlap discount double-counts a
correction the script had already made. At 156 genuinely independent dates SE(IC) = 0.0080, not
0.0179 — identical to the 790-clean-at-5d row, because **790/5 ≈ 156: they are the same effective
sample.**

⭐ **The conclusion nevertheless survives, by the sweep's OWN published interval rather than by an
overlap argument.** `[doc]` `factor-sweep-h5-2026-09-07.md` reports `close_over_sma20` at spread
**−0.313%** with a 90% day-block interval of **[−1.030, +0.405]%** ⇒ **SE(spread) = 0.436%.** The
IC→spread transfer is `spread = IC · σ_cs · (E[z|Q5] − E[z|Q1])`, and that bracket is **2.800** for a
normal:

| σ_cs | **SE(IC)** | resolves at t=2 | resolves at 80% power |
|---:|---:|---:|---:|
| 5% | 0.0312 | IC 0.062 | IC 0.087 |
| 6% | 0.0260 | IC 0.052 | IC 0.073 |
| 7% | 0.0223 | IC 0.045 | IC 0.062 |

⇒ **the sweep resolved only the TOP of its own 0.018–0.071 break-even band**, and the largest |IC| it
measured was **0.0224**. **So it could not have detected an economically break-even IC — right
answer, wrong derivation**, and this is a second independent reason the ranker question is open,
alongside the CA contamination already recorded.

⚠ ⭐ **AND A GAP NEITHER DOCUMENT NOTICED: `σ_IC = 0.10` is an ASSUMPTION.** It enters at §12.15,
is inherited by the audit's entire power table, and **every IC power number in both documents is
linear in it.** The pure-noise floor is **0.063 at 250 names/date and 0.027 at 1,360** — so 0.10 is
conservative if per-date IC is mostly sampling noise and optimistic if IC genuinely varies over time.
⇒ **`sd(IC_t)` must be reported as an output of 3b, not assumed as an input**, and the audit says so
itself: *"the whole calculation is linear in it, so if it comes back at 0.20 the test is half as
powerful and I need to know before recommending it as decisive."* **Adopted.**

### 12.18e ⭐⭐ C6 — MEASURED, and the collapse is far worse than predicted. RVOL was an SE artifact.

The audit predicted HC3 would inflate the SE 10–25% and date-clustering 1.5–2.5×, taking t from
+3.67 into the 1.5–3.0 range. `[measured]` — `ols_multi` extended with HC3 and entry-date-clustered
sandwich estimators (92 clusters on 185 trades, 57 on 82):

| regressor | β | **t (iid)** | **t (HC3)** | **t (date-clustered)** |
|---|---:|---:|---:|---:|
| **`rvol_20`** (ALL) | +0.19811 | ⛔ **+3.67** | ⭐ **+0.61** | ⭐ **+0.98** |
| **`rvol_20`** (BUY only) | +0.19501 | ⛔ **+3.14** | ⭐ **+0.53** | ⭐ **+0.90** |
| `stop_width_pct` (ALL) | +0.06302 | +2.28 | +1.51 | **+2.17** |
| `stop_width_pct` (ALL, univariate) | +0.06499 | +2.30 | +1.94 | **+2.18** |
| `atr_20_pct` (ALL) | −0.03113 | −0.43 | −0.37 | −0.41 |

⇒ ⛔⛔ **THE ONLY t ≥ 3.6 IN SEVEN ROUNDS WAS AN IID-STANDARD-ERROR ARTIFACT.** HC3 inflates RVOL's
SE **six-fold** (0.0540 → 0.3235) and the t falls to **+0.61**. **C6 is confirmed and understated:
the audit's floor of 1.5 was optimistic.**

⭐ **And the mechanism the audit named is visible in the contrast.** `stop_width` barely moves under
either robust estimator (+2.30 → +1.94 → +2.18) while RVOL collapses — **because stop width is a
per-trade property and RVOL is a market-wide daily one.** A volume spike hits every name on the same
session, so RVOL carries almost no independent information per trade beyond the date it belongs to.
`[measured]` 185 trades across only **92 distinct entry dates**.

⇒ **§16.1's RVOL row is rewritten.** It was stamped *"the single most robust coefficient in the
document and the single most firmly disqualified, which is an uncomfortable pair worth stating
plainly."* ⛔ **There is no pair. It was never robust.** The audit's conclusion is adopted verbatim:
**"the unit was never the only problem; the SE was."** ⭐ **And this retires the fifth reason it stayed
unpromoted by removing the need for the other four** — though all four still hold and the pre-registered
form in R7-J is unchanged.

⚠ **The lesson generalises beyond RVOL and is the one to carry:** `newey_west_t` was applied to the
*mean* in R7-H and nothing was applied to the *regression* in R7-J, in the same round, by the same
author. **A robust SE is not a refinement on a leptokurtic, overlapping, date-clustered panel — an
iid SE there is simply the wrong quantity.** ⇒ **every regression in this programme reports iid, HC3
and clustered t side by side from now on**, which is now how `ols_multi` prints.

### 12.18f-C5 ⭐⭐ C5 — MEASURED, and the mechanical term explains the ENTIRE gradient

`[measured]` The pure arithmetic: draw `w` from the **measured swing distribution**, draw a raw return
that is **independent of `w`** with the measured sd (3.169%), form `R = ret/w`, and bucket on `w`:

| E[raw ret] | R (w<2%) | R (w≥2%) | ALL | **spread** |
|---:|---:|---:|---:|---:|
| −0.100% | −0.1741 | −0.0260 | −0.0501 | −0.1481 |
| −0.050% | −0.0758 | −0.0138 | −0.0238 | −0.0620 |
| 0.000% | +0.0349 | −0.0019 | +0.0040 | +0.0368 |
| ⭐ **−0.328%** *(the measured mean)* | **−0.5138** | **−0.0668** | **−0.1379** | **−0.4470** |
| ⭐ **MEASURED** *(n 30 / 155)* | **−0.4726** | **−0.0862** | **−0.1489** | **−0.3864** |

⇒ ⭐⭐ **The mechanical `1/w` term with ZERO dependence between return and stop width reproduces
**116%** of the measured tight-vs-wide spread** (−0.4470 predicted vs −0.3864 observed). **There is no
residual to explain.** The audit's conservative estimate was "roughly a quarter of the magnitude"; the
measurement says **all of it, and slightly more than all of it.**

`[measured]` And the gradient was never significant to begin with, once asked as a contrast:
**tight (n=30) −0.4726 vs wide (n=155) −0.0862, diff −0.3864, SE 0.2492, t = −1.55.**

⭐ **The independence assumption is not an assumption — it is measured.** R7-J's `ret_pct ~ stop_width`
gives t = **+1.07 (iid) / +1.21 (HC3) / +1.41 (clustered)**: raw return is statistically independent
of stop width on this sample. **That is exactly the condition under which every `R`-vs-`w` gradient is
arithmetic.**

⇒ ⛔⛔ **THE WHOLE DENOMINATOR FAMILY IS CLOSED ON THE SWING SAMPLE.** §4.4's wide-stop gradient,
§12.1's reachable-cohort sign flip and §12.2's dispersion lever are **one artifact of dividing by a
small number**, not three lines of evidence. D1 is confirmed in full. ⚠ **The positional members are
still unmeasured** and plan item 2‴ stands — but the prior has moved hard: the swing version is not
merely "not supported", it is **fully explained** by arithmetic.

### 12.18g ⭐⭐ C4 — MEASURED. Right structure, and the magnitude is 2.77×, not 1.68×.

`[measured]` Per-trade `cost_in_R = round-trip bps ÷ (100·w)` on the swing sample's own `w`:

| quantity | **explicit only (25.5 bps)** | **+ 15 bps/leg slippage (55.5 bps)** |
|---|---:|---:|
| cost at the **median** stop (4.65%) — **the scalar the document uses** | **0.0549R** | 0.1195R |
| **E[cost in R] across the book** | ⛔ **0.1522R** | ⛔ **0.3313R** |
| **understatement factor** | ⛔ **2.77×** | ⛔ **2.77×** |
| median / p90 / p99 / max | 0.055 / 0.249 / **0.989** / **5.935** | 0.120 / 0.543 / 2.153 / 12.918 |
| **E[cost in R] on the live-reachable book (w ≥ 2%, n=155)** | ⭐ **0.0573R** | 0.1248R |

⇒ ⭐ **The audit's structural claim is right and its own caveat is the precise answer: the scalar is
CORRECT for the reachable book (0.0573R vs 0.0549R — a 4% error) and WRONG BY 2.77× for the
unrestricted corpus.** Its 1.68× was computed from positional buckets (a `sample` violation, §12.18c);
measured on swing it is **2.77×**.

⭐⭐ **And costing per trade instead of by a scalar changes a verdict:**

| book | gross | **net, per-trade explicit** | **net, per-trade + slippage** |
|---|---:|---:|---:|
| ALL (n=185) | −0.1489 | **−0.3011, SE 0.0764, t −3.94** | −0.4802, SE 0.1043, **t −4.60** |
| **BUY (n=82)** | −0.0992 | ⭐ **−0.2435, SE 0.1112, t −2.19** | ⭐ **−0.4134, SE 0.1250, t −3.31** |

⇒ ⭐⭐ **The tradeable book, costed correctly, is SIGNIFICANTLY NEGATIVE at t = −2.19 on explicit
charges alone.** That is the one place round 8 makes the picture *sharper* rather than softer, and it
is the counterweight to D4's "the frequentist test is uninformative": **the gross test is
uninformative; the NET test is not.**

⚠ **Two honest bounds on that number, both of which cut the other way.** **(1)** It charges the
sub-2% cohort at up to 5.9R, and **the live order path REFUSES those trades** (the notional cap is a
2% minimum-stop-width rule, §1 #10) — so the ALL row includes trades that cannot be taken. **(2)** The
BUY row is **all windows, not gap-clean, and not restricted to w ≥ 2%.** ⇒ **the single number the
whole programme turns on is `clean × BUY × w ≥ 2% × net, per-trade`, and it has never been computed in
one pass.** That is exactly what the audit's F11 asks for — *"please get all the cuts in one pass"* —
and it is now plan item 2⁗. **Everything else in this document is a corner of that cell.**

### 12.18h ⭐ D2, D3, D4, D5 — four structural reads, all four arithmetically exact

**D2 — ρ̄ is flat in m, and hold period is the free breadth lever. This REFUTES my own Q7-2.**
`[verified]` Under a one-factor model `ρ̄ ≈ β̄²σ²_mkt/σ²_total` is a **factor-share identity that does
not depend on slot count**, so ρ̄ should be roughly *flat* in m — and what asymptotes is instantaneous
diversification at `1/ρ̄`. ⛔ **My Q7-2 hypothesis (ρ̄ RISES with concurrency, so breadth has an
asymptote no capital crosses) is half right and half wrong: the asymptote is real, the mechanism is
not.** And the consequence is the more useful half:

| configuration | effective bets | **effective obs / yr** |
|---|---:|---:|
| 3 slots, 5-day holds (today) | 2.17 | **109** |
| 9 slots, 5-day holds | 3.57 | 179 |
| 20 slots, 5-day holds | 4.34 | 217 |
| ⭐ **9 slots, 3-day holds** | 3.57 | ⭐ **298** |

⇒ ⭐⭐ **Hold period is a bigger breadth lever than slot count, and it costs no capital.** `250/hold`
multiplies while `m/(1+(m−1)ρ̄)` saturates. **This is §17 Q7-4's answer: the 2021–2023 back-fill is not
worth days of ingestion, and the replacement lever is TURNOVER**, decided by the MFE/MAE hazard curve
(plan item 20) against the cost table. ⚠ The offset is real and is the reason it is a measurement
rather than a decision: **cost-in-R is invariant to hold period but cost per YEAR scales with
turnover, and the flat ₹15.34 DP charge is the binding term** (§12.3 measured CAS at 11.5%/yr at ₹1L
on 1-day holds). **Both are afternoons and neither has been run.**

**D3 — §4.5 uses the wrong law, and this refines one of the panel's five round-1 "decisive" findings.**
`IR ≈ IC·√BR` is a portfolio law for an unconstrained, optimally-weighted, full-cross-section book.
We run a **gated tail selector** taking the top 1–3%. The correct transfer is
`E[excess | selected] ≈ IC · σ_cs · E[z | selected]` — which §12.15's KILL LINE 3 discussion uses
correctly and §4.5 does not. `[verified]` at a 3% selection rate, `E[z|selected] = 2.268`:

| IC | σ_cs | E[excess]/trade | in R at a 5% stop |
|---:|---:|---:|---:|
| 0.02 | 5% | 22.7 bps | **+0.045R** |
| 0.02 | 7% | 31.8 bps | +0.064R |
| 0.04 | 5% | 45.4 bps | +0.091R |
| 0.04 | 7% | 63.5 bps | **+0.127R** |

Against **25.5 bps** of explicit round-trip charges: **IC = 0.02 is roughly break-even per trade and
IC = 0.04 is comfortably positive.** ⇒ ⚠ **§4.5's "a perfectly executed version of this system is not
investable" is too strong as stated.** The per-trade economics of a modest IC work at this cost stack.
**What fails is the ANNUAL number, through trade count** — ~60 positional trades a year at +0.09R and
2% risk is ~11% of capital gross. ⭐ **That is a TURNOVER diagnosis, not a signal-quality diagnosis,
and it points at D2's lever rather than at abandoning the strategy class.** Recorded as a refinement,
not a refutation: §4.5's conclusion about *investability at this turnover* stands; its derivation and
its per-trade implication do not.

**D4 — ⭐⭐ the document runs a frequentist test where the decision is Bayesian, and this resolves
Q7-1.** `[verified exactly]` Posterior on the honest cell (μ̂ = −0.0843, SE = 0.1287), normal-normal,
against the **net break-even of 0.111R**:

| prior sd on μ | posterior | P(μ > 0) | **P(μ > break-even)** | P(μ ≥ Sharpe-1.0 gross) |
|---:|---|---:|---:|---:|
| 0.03R | −0.0043 ± 0.0292 | 44.1% | **0.004%** | 0.000% |
| 0.05R | −0.0111 ± 0.0466 | 40.6% | **0.44%** | 0.000% |
| 0.10R | −0.0317 ± 0.0790 | 34.4% | **3.5%** | 0.14% |
| 0.20R *(absurdly generous)* | −0.0596 ± 0.1082 | 29.1% | **5.7%** | 0.72% |

⇒ ⭐⭐ **Under ANY defensible prior the probability that the tradeable book has a positive net edge is
0.4%–5.7%. That is not "uninformative". That is a decision.** And it dissolves §17 Q7-1's dichotomy:
the choice between **(i) NO RESULT** and **(ii) a negative point estimate under a positive null** was
a false one created by using *significance* as the summary statistic. **The correct answer is (iii): a
posterior concentrated near zero with negligible mass above break-even** — which licenses **economic**
closure without claiming **statistical** closure, exactly the distinction §12.15 already draws.
⛔ **My R7-K wording — "the evidence base for the tradeable book is EMPTY, not negative" — is
withdrawn in favour of (iii).** ⚠ And note what it does to the sunset: **the expected value of
continuing to MEASURE this strategy is near zero, because the posterior barely moves for any n
reachable before 2026-10-31.**

**D5 — at the honest σ, decade-scale validation is back.** `[verified]` σ = 1.005, I = 1.335,
80% power:

| effect to detect | trades needed | years at 125/yr |
|---|---:|---:|
| +0.094R (Sharpe-1.0 net, long-only) | **1,198** | **9.6** |
| +0.111R (net break-even) | 859 | 6.9 |
| +0.205R (Sharpe-1.0 gross) | 252 | 2.0 |

⇒ **§5.2's original pessimism was closer to right than the two inversions that replaced it** (§12.8 →
§12.10a), and **the reason is C1 plus the σ ladder, not the argument §5.2 actually made.** ⭐ That is
worth recording precisely because it is the third time this headline has moved: **the corrections
have now returned to the neighbourhood of the round-3 position by a completely different route.**

## 12.19 ⭐⭐ VERIFYING F12 FOUND A MONEY-PATH BUG — `paper_tick_size` is one constant and the market has two grids

**This came out of checking the audit's F12**, which asks whether the 922-day gap is a *missing
ingest* or *two stitched sources* — because if the conventions differ, stitching introduces a
discontinuity the gap guard cannot catch (the bars exist; the guard only flags absent sessions). The
question was worth an afternoon on its own terms and it answered reassuringly. **Then the diagnostic
it required turned up something else.**

### 12.19a F12's answer: same source, same convention — the backfill is safe from that hazard

`[db]` Comparing the two blocks on every property a different source would disturb:

| property | **PRE-gap** 2019-10 → 2020-12 | **POST-gap** 2023-07 → 2026-09 |
|---|---:|---:|
| rows | 457,804 | 1,623,669 |
| close on the **₹0.01** grid | **1.0000** | **1.0000** |
| close on the **₹0.05** grid | **0.9696** | **0.6752** |
| integer volume · zero-volume rows · NULL OHLC | 1.0000 · 0 · 0 | 1.0000 · 0 · 0 |
| `is_complete` | 1.0000 | 1.0000 |
| distinct time-of-day | 1 (`00:00:00`) | 1 (`00:00:00`) |
| distinct names | 1,764 | 3,129 (**1,518 in both**) |

The ₹0.05 discrepancy looked at first like exactly the source divergence F12 feared. **It is not.**
`[db]` Split by price, the cause is unambiguous:

| price bucket | pre-gap on-₹0.05 | post-gap on-₹0.05 |
|---|---:|---:|
| < ₹50 | 0.9837 | **0.3335** |
| ₹50–250 | 0.9569 | **0.4013** |
| ₹250–1k | 0.9654 | 0.9390 |
| > ₹1k | 0.9734 | 0.9759 |

…and, for sub-₹250 names only, **by year**:

| 2019 | 2020 | 2023 | 2024 | 2025 | 2026 |
|---:|---:|---:|---:|---:|---:|
| 0.9777 | 0.9686 | 0.8738 | **0.4920** | **0.2200** | **0.2290** |

⇒ ⭐ **Nothing changed above ₹250, everything is on the ₹0.01 grid in both blocks, and the transition
is a smooth phase-in through 2024–25.** That is **NSE moving sub-₹250 securities from a ₹0.05 tick to
a ₹0.01 tick**, not two data sources. ✅ **F12's answer: the blocks are the same series and the
back-fill is safe from the convention hazard it asks about.** (It remains not worth doing, for D2's
reason.)

### 12.19b ⭐⭐ But `_round_tick` snaps every fill to ₹0.05, and for 78% of cheap-stock closes that is the wrong grid

`[code]` `app/core/config.py:189` — `paper_tick_size: float = 0.05`, **one global constant, price-
independent.** `[code]` `app/broker/paper_broker.py:71-92` — `_round_tick` reads it and **always
rounds ADVERSELY** (a BUY ceils, a SELL floors), by a deliberate and correct contract: *"the model can
only make a fill worse"*, because an off-grid price is not transactable.

⭐ **The directional rounding is right. The grid is wrong.** For an off-grid reference the expected
adverse penalty is `tick/2`, so:

| share price | penalty @ ₹0.05 tick | @ the real ₹0.01 tick | **overcharge, round trip** |
|---:|---:|---:|---:|
| ₹20 | 12.50 bps | 2.50 bps | ⛔ **20.0 bps** |
| **₹39** *(the SRTL archetype)* | 6.41 bps | 1.28 bps | ⛔ **10.3 bps** |
| ₹80 | 3.12 bps | 0.62 bps | 5.0 bps |
| ₹150 | 1.67 bps | 0.33 bps | 2.7 bps |
| ₹250 | 1.00 bps | 0.20 bps | 1.6 bps |
| ₹2,500 | 0.10 bps | 0.02 bps | 0.16 bps |

⇒ **On a ₹39 name the paper broker charges ~10 bps of round-trip rounding the market does not — about
40% of the entire real 25.5 bps charge stack, and 0.064R of pure model artifact at a 2% stop.**

⛔⛔ **CORRECTED IN ROUND 9 (§12.30a) — THIS SENTENCE WAS WRONG.** It read: *"this lands on
exactly the cohort that carries the document's remaining positive results — §12.1's
reachable-cohort flip, §7's stop-width buckets and §12.10b's denominator pathology."* `[code]`
**`_round_tick` exists ONLY in `app/broker/paper_broker.py` (defined `:71`, called `:245`, `:263`,
`:291`, and nowhere else in the repo).** Neither probe nor the backtest engine references it, and
`positions` = `orders` = 0. ⇒ **The bug contaminates NO number in this document.** It is a genuine
before-cycle-2 fix with a much smaller blast radius than stated, and §12.21c's parity matrix was
right while this prose was wrong — two sections of the same round disagreeing. ⚠ **And the
magnitude is the EXCESS over the true grid, 10.26 bps ⇒ 0.0513R at a 2% stop — not 0.064R, which
is the total wrong-grid cost** (Kimi C6). The artifact is still largest on cheap tight-stop names.

⭐ **It also completes the diagnosis of a finding already in the record.** CLAUDE.md and
`_round_tick`'s own docstring cite quant-verifier's measurement that **"27.2% of our 1m closes are off
the ₹0.05 grid"** and treat it as a data quirk justifying adverse rounding. `[db]` **The real cause is
now known: the ₹0.05 grid is not the market's grid for sub-₹250 names since 2024**, where 78% of
closes sit off it. The 27.2% was correct and its *explanation* was missing.

⚠ **Direction matters and it is the opposite of C4's.** C4 says the median-stop scalar **understates**
friction across the book; this says the tick grid **overstates** it on cheap names. **They are
independent, they partially offset, and neither has been measured against the actual per-trade
`w`.** ⇒ both are settled by the same two-line change (§12.18g / plan item 2⁗).

⭐ **Under the document's own governing rule this is a BEFORE-cycle-2 item: it changes a recorded
number** (every paper fill and every mark on a sub-₹250 name). The fix is a **price-dependent tick**
— `₹0.01` below ₹250, `₹0.05` at or above — which is a schedule, not a model choice, and therefore
carries **no forward-evidence bar** on the §5.4 asymmetric-burden argument. ⚠ **Confirm the exact
NSE/SEBI effective dates before hardcoding a threshold**; the measured phase-in (0.87 → 0.49 → 0.22
across 2023 → 2024 → 2025) suggests a staged rollout rather than one cutover, so the schedule may
need to be date-dependent as well as price-dependent — which is itself an argument for reading it
from a table rather than a constant.

## 12.20 ⭐⭐ THE EQUITY-BETA NULL, COMPUTED — C8 was right, §4.2 was never blocked

§17 Q7-1 and §16.3 item 3 both asserted that §4.2's central interpretive claim — *"we have negative
alpha, not zero alpha"* — **cannot be quantified while `index_ohlcv_1d` holds 51 rows.** ⛔ **That
premise is false, and the audit is right that it is false.** `ohlcv_1d` holds 1,300–2,900 names per
year; an **equal-weight basket of the eligible universe, as of each session**, is not merely a
substitute for NIFTY — it is a **better** benchmark, because NIFTY-50 is large-cap and this book is
not. **It took one query.**

`[db]` Equal-weight daily return of the top-250-by-median-traded-value universe, over the contiguous
post-gap block:

| quantity | value |
|---|---:|
| sessions with a basket return | **789** |
| names per session | 46 → 250 |
| **mean daily drift** | **+0.0816%** |
| sd · SE · **t** | 1.1153% · 0.0397% · **+2.06** |
| annualised (252d) | **+22.8%** |
| cumulative over the block | **+81.2%** |

⇒ ⭐ **The universe drifted up 81% over the window the corpus is measured on, and the drift is itself
significant at t = +2.06.** §4.2's claim that the correct null for a 100%-long, beta-0.92 book in a
rising market is **strongly positive** is now a number rather than an argument.

### 12.20a What it does to the honest cell

At the probe's 5-session horizon cap and the measured median swing stop of 4.65%:

| horizon | drift | **drift in R** | SE |
|---|---:|---:|---:|
| 3 sessions | +0.245% | +0.053R | 0.026R |
| 4 sessions | +0.326% | +0.070R | 0.034R |
| **5 sessions** *(the cap)* | **+0.408%** | **+0.088R** | 0.043R |

So the honest cell, measured **against the drift null instead of against zero**:

| hold | α = observed − null | SE (iid) | t | SE (infl-adj) | t |
|---|---:|---:|---:|---:|---:|
| 3d | **−0.137R** | 0.131 | −1.04 | 0.151 | −0.91 |
| 4d | **−0.155R** | 0.133 | −1.16 | 0.153 | −1.01 |
| **5d** | **−0.172R** | 0.136 | **−1.27** | 0.155 | **−1.11** |

⇒ ⭐⭐ **The correct null roughly DOUBLES the point-estimate deficit**: −0.084R against zero becomes
**−0.137R to −0.172R against the drift.** It remains under-powered (|t| ≈ 1.0–1.3), **but combined
with D4's posterior it settles Q7-1 decisively in favour of option (iii)** — a posterior concentrated
below zero with negligible mass above break-even, which is **economic** closure, not statistical
closure.

⚠ **Three caveats, stated because they bound the number rather than because they rescue it.**
**(1)** The true null is the drift over the **actual mean holding period**, which is ≤ 5 sessions
because trades exit early at stop or target — so **+0.088R is an upper bound** and the 3-day row is
probably nearer the truth. The mean hold is one column the probe does not yet emit (plan item 2⁗).
**(2)** A **beta** adjustment would raise the null further, since the closed book measured β = +0.92
against a basket that is itself the market — so ignoring β is conservative in the same direction.
**(3)** The universe is selected by **today's** liquidity (the 0a.3 defect, §12.17 R7-7), so the
basket inherits survivorship and its drift is, if anything, **overstated** — which makes the
computed α **conservative** as a deficit but means the number must be re-run after 0a.3.

### 12.20b And it retires the gating item I had just written

⛔ **§16.3 item 3 ("the equity-beta NULL, computed — gated on the index backfill") is WITHDRAWN
one section after being written.** It was gated on `index_ohlcv_1d`, and `index_ohlcv_1d` was never
the right instrument. ⭐ **The general lesson, which is the same one §12.12 produced from the other
direction: a blocker asserted from the name of a table is not a blocker until someone asks whether
the quantity can be built from something else.** The index backfill is still worth redoing — the
market-regime and sector-RS overlays genuinely need it — but **nothing in §4.2 or §16.3 waits on it.**

## 12.21 ⭐ ROUND 8, SOURCE 2 — the architecture reading, and the two questions of it that were answerable

The second round-8 response is an **architecture and estimand reading** rather than a recomputation.
Its framing sections are its value; its 20-section interrogation is a **resend of the one §13f already
cut**, and the cut is held (below). Two of its questions were answerable from the code today, and
**both answers are consequential.**

### 12.21a ⭐⭐ Its section H — "find the code that chooses the actual 2–3 positions" — ANSWERED, and it is the answer to the user's original question

`[code]` `app/api/v1/signals.py:267-289`. The deployed offered-set is built in four steps:

| step | code | what it does |
|---|---|---|
| 1. dedup | `max(grp, key=(confidence_pct, _reward_risk(s), created_at))` | one representative per `(stock, direction, classification)` — **keyed on confidence** |
| 2. drop near-expiry | `if not include_expiring` — **default `False`** | removes signals with ≥80% of validity elapsed |
| 3. drop choppy | `if not include_choppy` — **default `False`** | removes signals whose daily Kaufman **ER < 0.30** (`CHOPPY_ER`) |
| 4. **rank** | `reps.sort(key=(confidence_pct, created_at), reverse=True)` | ⭐ **descending CONFIDENCE** |

…then the human picks from the top of that list.

⇒ ⭐⭐ **THE DEPLOYED PICKER'S RANKING KEY IS `confidence_pct`, AND R7-B MEASURED
`Spearman ρ(confidence, R) = −0.018` (permutation p = 0.807) ON A TEST POWERED TO DETECT ρ = 0.147.**

**That is the direct, measured answer to the question that started this exercise —
*"sometimes I cannot select the right stock."*** The quantity the UI sorts by, and therefore the
quantity that decides which 2–3 of ~200 signals get traded, **carries no measured information about
outcome.** It is not that the picker is applied badly; it is that its key is uninformative. ⇒ this is
3b's question arriving from the *implementation* side, and it is why 3b is the decisive test.

### 12.21b ⭐ And finding that turned up a SECOND display/order divergence, in the opposite direction

`[code]` **Neither the near-expiry filter nor the choppy filter exists in `restrictions.py`** — the
registry A38 established as *the* single source of truth for tradability — **and neither is applied by
the order path.** `grep` for `choppy`/`CHOPPY`/`near_expiry` across `restrictions.py` and
`paper_broker.py` returns nothing.

⇒ **A signal that is choppy or near-expiry is HIDDEN from the default listing and would be ACCEPTED by
`place_order`.** ⚠ **This is display/order drift in the OPPOSITE direction from the one fixed on
2026-09-02.** That one was *display too permissive* — 41 of 204 listed signals showing a Buy button
that could only 409. This one is **display too restrictive**: two undeclared eligibility rules,
defaulting to ON, that the order path does not know about and the registry does not declare.

⭐ **And it matters for the research question, not just for tidiness:** the **corpus applies neither**,
so the deployed offered set is **narrower than the corpus along two axes nobody has accounted for.**
That is a concrete, measurable instance of §12.8's corpus-vs-deployed estimand gap — previously stated
as a conceptual worry and now a named pair of filters. ⇒ **plan item: fold both into `restrictions.py`
with an `enforced_by` of `DISPLAY`, or delete them; then re-run the offered-set counts.** Either way,
**`restrictions.py` is not currently the single source of truth its docstring claims** — the third
standing claim round 8 has had to correct.

### 12.21c ⭐ Its section A — the parity matrix, filled in from the code

Its strongest ask, and most of it was already known in pieces. `[code]` Assembled:

| behaviour | RESEARCH probe | BACKTEST `engine.py` | PAPER `paper_broker` | DISPLAY path |
|---|---|---|---|---|
| explicit charges (`fees.py`) | ⛔ no | ⛔ **no — zero references** | ✅ yes | n/a |
| slippage / spread model | ⛔ no | ⛔ **no** | ✅ yes | n/a |
| tick rounding | ⛔ no | ⛔ **no** | ⚠ yes, **wrong grid** (§12.19) | n/a |
| `risk_engine` (heat, count, notional) | ⛔ no | ⛔ **no — zero references** | ✅ yes (`off`) | preview only |
| **Σ notional ≤ cash** | ⛔ no | ⛔ no | ⛔ **DOES NOT EXIST** | ⛔ no |
| tax | ⛔ no | ⛔ no | ⛔ **does not exist** | ⛔ no |
| through-stop rejection at the fill | ⛔ no | ⛔ **no — this IS defect #4** | ✅ `eligibility.through_stop_reason` | ✅ preview |
| ex-date CA adjustment | ⛔ no | ⛔ no | ✅ `ca_adjust.py` (inert — 0 rows) | n/a |
| validity horizon enforced | ✅ via `session_last` | ⚠ **only if `session_last` passed; else walks to end of data** | ✅ | ✅ |
| `ema20_daily` → `compute_levels` | ⛔ no | ⛔ no | ✅ via `signal_service` | n/a |
| near-expiry / choppy filters | ⛔ no | ⛔ no | ⛔ **no** | ⚠ **yes, both default ON** |

⇒ ⭐ **Its central claim is correct and the matrix is the evidence: research, backtest, paper and
display are four different experiments.** The backtest — which produced the 1,975-trade headline — is
the most divergent of the four: **it applies no cost, no slippage, no rounding, no risk rule and no
rejection.** ⚠ **That is not a new finding** (§12.11 Q11 recorded "neither, zero references" in round
6) **but it has never been assembled as one table, and assembled it reads differently**: the corpus
is not "the strategy without costs", it is **a different object that shares only the scorer and the
level function.**

### 12.21d ⛔ Where I push back, with the round-8 numbers

Its headline framing is: *"the current evidence does not justify 'the strategy is bad' — it justifies
'we have not yet constructed a sufficiently trustworthy experiment.'"*

⚠ **That was the right call on round-7 evidence and it is too weak on round-8 evidence.** Three
measurements now say more than "we cannot tell":

1. **The NET test is not underpowered.** Costed per trade rather than by a median scalar, the
   tradeable book reads **−0.2435R at t = −2.19** on explicit charges alone and **−0.4134R at
   t = −3.31** with the slippage assumption (§12.18g).
2. **The posterior is not diffuse.** P(positive net edge) = **0.4%–5.7%** across prior sds from 0.03R
   to an absurdly generous 0.20R (§12.18h D4).
3. **The one remaining positive family is fully explained by arithmetic.** The mechanical `1/w` term
   reproduces **116%** of the measured stop-width spread with return independent of `w` — and that
   independence is itself measured at t = +1.07 (§12.18f).

⇒ **The supportable statement is narrower and stronger than either of ours:** *the GROSS question is
underpowered and will stay so for a decade at this turnover (D5); the NET question is answered
negatively; and the one decisive unrun test is the panel-level score IC, which is fully powered.*
⭐ **"We have not constructed a trustworthy experiment" is true of the gross-expectancy question and
false of the net one.**

### 12.21e ✅ What is adopted from it, and it is a lot

| # | its point | verdict |
|---|---|---|
| 1 | ⭐ **contiguous-SESSION feature computation**, not row-count windows — a stateful EMA/ATR/ADX can be corrupted *before* a panel-level guard sees it | ✅ **ACCEPTED and it is deeper than my §12.12 guard.** ⚠ Bounded honestly: the probe slices a 300-row window per panel, so the panel guard **does** cover it there; it is the **live path** and `run_single_stock`'s bar-50 walk that are exposed. **A feature window must be defined by elapsed market sessions in a contiguous calendar, not by row count** |
| 2 | ⭐ **`UniverseSnapshot` as a reusable object**, not a SQL fix repeated in three scripts | ✅ **ACCEPTED as the shape of 0a.3.** `(as_of, stock_id, eligible, reason, liquidity, price_floor, tradability, listing_state, ca_state, source_version)`, consumed by every probe and backtest through one API |
| 3 | ⭐ **an immutable EXPERIMENT MANIFEST** — make invalid statistical combinations impossible in software rather than in prose | ⭐ ✅ **ACCEPTED, and it is the right generalisation of §16.1's sample-tag rule.** *"The problem is no longer human statistical discipline"* is exactly right — the rule has been violated five times, once by the auditor enforcing it |
| 4 | **don't adopt `1 + (m−1)ρ̄` as the portfolio model; use the realised daily portfolio P&L variance** | ✅ **ACCEPTED**, and round 8's D2 supplies the better intermediate model (factor-share, flat in m) |
| 5 | **Policy B is a mathematical allocation policy, not a validated executable one** | ✅ **ACCEPTED** — and §12.14's missing cash constraint is the proof, not an analogy |
| 6 | **cycle 2's purpose is to validate simulator-to-execution FIDELITY**, per field (entry, stop, target, qty, fees, exit reason), not to ask "did it make money" | ✅ **ACCEPTED** as a refinement of the paired-calibration reframe; the per-field residual table is better than a single `ε` |
| 7 | **three data "truths"** — market / decision / execution — as one immutable causal record | ✅ already adopted in round 7 as the ledger schema (§12.17 R7-8) |
| 8 | **a formal decision TREE rather than a plan list** | ⚠ **partially adopted.** §12.15's 3a/3b split plus §13.8's ordering is the tree for the questions that remain; a full eight-node tree is more governance than a programme with 50 days and one shipped item can execute |
| 9 | the **20-section evidence-extraction interrogation** | ⛔ **CUT AGAIN — this is a resend.** §13f adjudicated it in round 7: it is 3–4× the capacity that forced §13's CUT, and **its own §18 says the document is becoming "poor operational specification"**, which cannot both be acted on. ⭐ **And round 8 strengthens the cut rather than weakening it: C7 shows the decisive question is ONE query**, so a 20-part audit is now demonstrably not the shortest path to the decision. Sections A and H were answered above **because they were cheap and decision-changing**; the remaining eighteen stay in §14b |

## 12.22 ROUND 8, SOURCE 3 — accurate restatement, five asks, two already answered in the document it reviewed

The third round-8 response is a **structural restatement with five executable asks**. ⭐ **The
restatement is accurate** — its architecture diagram, its directional-edge table, its
denominator-artifact section and its ρ̄ table all reproduce this document's numbers correctly, which
is a genuine and under-rated service: **it is the first evidence that the document is readable by
someone who was not in the rounds that produced it.** The asks are adjudicated one at a time.

| # | ask | verdict |
|---|---|---|
| **1** | data-plane audit: a generated-weekday query for missing sessions, plus `corporate_actions` / `cas_daily` counts | ⭐ ✅ **RAN, and it found something small and real** — §12.22a |
| **2** | portfolio-engine audit: "report line numbers where portfolio cash checks are missing" | ⛔ **ALREADY ANSWERED in §12.14 of the document it reviewed** — no `available_cash`, no Σ-notional check anywhere; 3 slots at the median stop = 120% of capital |
| **3** | re-evaluate `RVOL-20` and `stop_width` in raw % and ATR units to remove denominator artifacts | ⛔ **ALREADY ANSWERED — R7-J did exactly this**, and round 8 added the third unit. ✅ **Its instinct was right and its own round-7 question is what produced the answer** |
| **4** | replace the look-ahead universe query with a **rolling trailing-liquidity rank as of the panel date** | ✅ **CORRECT — this is 0a.3**, and ChatGPT's `UniverseSnapshot` is the better shape for it (§12.21e) |
| **5** | "decouple pytest from the dev DB using an **explicit sqlite / ephemeral-Postgres container fixture**" | ⛔ **REJECTED TWICE OVER** — §12.22b |

### 12.22a ⭐ Its item 1 ran, and `nse_holidays` is incomplete for 2019–2020

`[db]` Its query as specified returns **675 "missing" weekdays** between 2020-01-01 and 2024-01-01.
⚠ **651 of those are inside the 922-day hole and only 7 are recorded NSE holidays**, so as written the
query conflates three different things — the hole, real holidays, and genuine ingest gaps. Separating
them is what made it useful:

`[db]` Missing weekdays **outside** the hole, across 2019-10 → 2026-09: **64**, of which **18 are not
in `nse_holidays`** — and reading the dates, they are almost all real Indian market holidays:
2019-10-02 (Gandhi Jayanti) · 2019-10-08 (Dussehra) · 2019-10-28 (Diwali) · 2019-11-12 (Guru Nanak) ·
2019-12-25 · 2020-02-21 (Mahashivratri) · 2020-03-10 (Holi) · 2020-04-02 · 2020-04-06 · 2020-04-10
(Good Friday) · 2020-04-14 · 2020-05-01 (Maharashtra Day) · 2020-05-25 (Id) · 2020-10-02 · 2020-11-16
(Diwali) · 2020-11-30, plus 2026-09-11 (today, no bar yet).

⇒ ⚠ **`nse_holidays` is incomplete over 2019–2020** — 7 recorded against ≥17 that occurred.
**CLAUDE.md's constraint #5 says trading-day arithmetic needs the NSE calendar, and validity windows
are in TRADING days**, so any trading-day arithmetic over the pre-gap block is currently wrong.
⚠ **Bounded honestly: it affects only the pre-gap block, which D2 says to drop anyway**, and the
post-gap block's 64−18 = 46 missing weekdays are all recorded holidays. ⇒ **a real defect, low
severity, and worth fixing only if the pre-gap block is ever used.** Credit to the ask.

### 12.22b ⛔ Its item 5 is rejected on two independent grounds

1. **It is already shipped.** `[code]` `tests/conftest.py:36` `_refuse_non_test_database()` aborts at
   import unless every URL names a database ending `_test`; backups run `0 11 * * 1-5`. **This is the
   second round in which the same fix has been requested** (R7-10), and both times it was described in
   the document being reviewed.
2. ⛔ **Its proposed mechanism contradicts a standing project rule.** `.claude/rules/testing.md`:
   *"Real Postgres test DB (`trading_platform_test`) and real Redis — **no DB mocks**… NOT SQLite."*
   The suite's value comes from exercising asyncpg, TimescaleDB hypertables and real Redis semantics;
   **a SQLite fixture would remove the thing the tests exist to test.** ⇒ this is the first round-8 ask
   from any source that would have made the system **worse** if adopted uncritically.

### 12.22c ⚠ And one place it read past a correction

Its diagnostic table records the level stage as *"anti-predictive or neutral… confirms the level stage
acts as a noisy or inverted gate."* ⛔ **§12.16 R7-K, in the document it was given, already withdrew
that**: on gap-clean windows the paired contrast falls to +0.095R (t 0.69) and **reverses on the clean
tradeable book**. ⚠ Recorded because it is the specific failure mode §16.2's note predicts — reading
the headline and not the correction beneath it — and because **round 8 then confirmed the withdrawal
twice over** (C5's mechanical term explains 116% of the gradient).

⭐ **The fair summary across two rounds:** this source is **reliable when it quotes the document and
unreliable when it models the system from outside it.** R7-13's one control variable was worth more
than every other point in round 7; item 1 above was worth a small real finding; items 2, 3 and 5 were
answerable by reading §12.14, R7-J and `conftest.py`. **The prescription in §16.2 stands unchanged and
is now evidenced twice: ask, do not assert — one question per round, phrased as a measurement.**

## 12.23 ⭐ The gap guard is incomplete — a 300-ROW window is not a 300-SESSION window

**Both the architecture source (its §6) and the audit (its F7) raised the same thing from different
directions, and they are right.** The audit asks whether there is *"a second, finer-grained hole"*;
the architecture source states the invariant: *"a feature window is defined by elapsed market sessions
within a contiguous market calendar — not merely by row count."* ⭐ **My §12.12 guard tests only
whether a window's two ENDPOINTS straddle the one known 922-day hole. It says nothing about what
happens inside the window.**

`[db]` Answering F7 first: **there IS a second hole and it is per-NAME, which no date-level query can
see.** On the post-gap block — **790 sessions, 3,129 names** — bars per name run **median 620, p10 67**,
and **2,048 of 3,129 names (65%) sit below 95% coverage.** A name with 67 bars across 790 sessions
carries a 300-row window only if it spans years.

`[measured]` So how much does the guard miss, on the probe's own 16,428 panels?

| panel state | count | share |
|---|---:|---:|
| window straddles the 922-day hole — **the guard catches these** | 5,462 | 33.2% |
| window is internally **non-contiguous by >10%** — ⛔ **the guard MISSES these** | **204** | **1.2%** |
| window spans exactly 300 sessions for 300 rows | — | median **300**, p90 **300** |
| worst case | — | **516 sessions for 300 rows** |

⇒ ⭐ **The concern is correct and the residual is small: 1.2% of panels, median 368 sessions per 300
rows, worst 516.** The probe's `count(*) > 100` and `len >= 340` filters do most of the work, which is
why it is 1.2% and not 65%.

⇒ **The fix is a one-line strengthening and it is strictly better than what shipped: test the SPAN,
not the endpoints.** `sessions_between(window[0], window[-1]) <= WINDOW × (1 + tol)` against the
market's own session calendar catches the 922-day hole, every per-name hole, and every future hole,
without naming any of them. ⭐ **`GAP_LO`/`GAP_HI` are hardcoded constants describing one known
incident — which is exactly the shape W5 warns about ("no hardcoded copy of a value that has an
owner"). The session calendar is the owner.**

⚠ **And the exposure is larger outside the probe than inside it**, which is the architecture source's
actual point: `run_single_stock` walks from **bar 50** with no guard at all, and the **live path**
computes stateful EMA/ATR/ADX incrementally with no session-contiguity check anywhere. **The probe is
the best-guarded of the three consumers and it is the only one that was measured.**

## 12.24 ⭐⭐ ROUND 9 — THE STANDING INVITATION WAS TAKEN UP, AND ONE CARD ROW FALLS

§17b asked for exactly two things: **run one of E1/E2/E3, or name a number in §16.1 you can
refute.** Five responses arrived. ⭐ **One did the second and did it correctly**, and — more
usefully — showed that **E1 as specified cannot answer its own question.** Three others converged
independently on a **defect in E2's estimand** that none of them could have coordinated on. The
fifth restated the document accurately and asked for the builds.

⚠ **This round is different from rounds 2–8 in one respect that matters: it produced a probe.**
`swing_dependence_probe.py` gained four column families (holding period `T`, the **paired**
matched-window basket return, the entry-day Kaufman ER, and the confidence-normalizer
decomposition) plus a `--dump-trades` artifact; `scripts/round9_cells.py` reads that artifact and
emits every cell below. **One expensive pass, then every contrast is a cheap read** — which is the
shape Kimi's R4 asked for and the reason five adjudications could be settled without five walks.

### The scoreboard

| source | shape | decision-changing | verdict |
|---|---|---:|---|
| **Claude** (`round8-followup-audit`) | ⭐ recomputation + a redesigned test | **3** | ⭐⭐ **the round.** Refuted a §16.1b row, found a third mechanical term in the stop-width family, and computed plan item 22. Two errors of its own, both found below |
| **Kimi** | ⭐ independent recomputation + 12 scoped asks | **2** | ⭐ **C3 is the best untested idea in the round** and C5 predicted E3 correctly before it ran. Also duplicated Claude's tick catch independently |
| **Deepseek** | structural map + 8 purpose-stated requests | **1** | ⭐ **the collider framing of E2 is the sharpest statement of the round's biggest convergence** |
| **ChatGPT** | estimand/architecture reading + 6 verification packages | **1** | ⭐ the MDE-convention schema and the E2 estimand point; the rest is architecture already adopted in §12.21e |
| **Gemini** | accurate restatement + a 4-task brief | **0** | ⛔ all four tasks are already answered in the document it was reading (§12.14, §12.12, §12.19, E2). See §13i |

⇒ **7 decision-changing points from 5 sources.** That is a higher rate than round 7 (4 of 37) or
round 8 (3 of 29) **and the reason is visible**: the two sources that recomputed produced five of
the seven, and the source that only read produced none. ⭐ **§17b's rule is confirmed by its own
first application.**

## 12.25 ⭐⭐ THE REFUTATION SUSTAINED — §16.1b's net-cost row does not survive its own unit rule

**The claim under attack** (§12.18g, adopted into §12.21d point 1 and into §13.8's decision
paragraph): *"the tradeable book, costed correctly, is SIGNIFICANTLY NEGATIVE at t = −2.19 on
explicit charges alone… the gross test is uninformative; the NET test is not."*

`[measured]` **Reconstructed from the document's own published rows**, exactly:

| book | gross | SE_gross | net | SE_net | mean ratio | SE ratio | **t ratio** | **t_net** | doc |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ALL (n=185) | −0.1489 | 0.0645 | −0.3011 | 0.0764 | 2.022 | 1.185 | 1.706 | **−3.941** | −3.94 |
| **BUY (n=82)** | −0.0992 | 0.1055 | −0.2435 | 0.1112 | 2.455 | 1.054 | **2.330** | ⭐ **−2.190** | **−2.19** |

⇒ **The net t is the gross t multiplied by a constant that is entirely determined by the cost and
the `1/w` distribution.** `net_R = (ret − c)/w`: subtracting a roughly-constant cost in bps moves
the numerator and leaves the `1/w` amplification intact, so the mean grows 2.46× while the SE grows
only 1.05×. **No new data enters the estimator between the gross test and the net test.**

⚠ **Where I refine the refutation rather than accept it wholesale.** Claude's framing — *"no new
information enters"* — is **too strong as a general statement**: a test against a non-zero null is
a legitimately different question from a test against zero, and it is precisely the question D4's
posterior asks. **The `1/w` amplification of the COST is also not an artifact** — for a risk-first
sized book a fixed bps charge genuinely consumes half the risk budget on a 0.5% stop, and that is
economics, not arithmetic. ⭐ **The refutation bites for a different and narrower reason, which is
the one that survives: the trades doing the amplifying are trades the live order path REFUSES.**

`[measured]` **The same net question, in the unit §12.10b commits the document to:**

| book | quantity | mean | SE | **t** | **t, ×1.21 BUY inflation** |
|---|---|---:|---:|---:|---:|
| ALL | net, explicit | −0.5829% | 0.2330% | **−2.50** | −2.50 |
| ALL | net, + 15 bps/leg | −0.8829% | 0.2330% | −3.79 | −3.79 |
| **BUY** | **net, explicit** | **−0.4450%** | 0.3500% | ⭐ **−1.27** | ⭐ **−1.05** |
| BUY | net, + 15 bps/leg | −0.7450% | 0.3500% | −2.13 | −1.76 |

⇒ ⛔⛔ **"THE NET QUESTION IS ANSWERED NEGATIVELY" IS TRUE OF THE MIXED BOOK AND FALSE OF THE
TRADEABLE ONE.** In raw % the BUY book reads **t = −1.27** (−1.05 with the inflation the document
measured and used for the MDE two rows away in the same section). **§12.21d's pushback against the
architecture source rests on a number that does not survive either of this document's own rules.**

⭐ **And the E3 cell was predictable before it ran — Kimi C5 published the prediction, which is the
correct way to run a test.** From the document's own inputs (clean × BUY gross −0.0843R, σ 1.0050,
n 61; E[cost in R] on the reachable book **0.0573R**, §12.18g):

| cohort | net R | SE | **t** |
|---|---:|---:|---:|
| clean × BUY × w≥2%, explicit, iid | **−0.1416** | 0.1287 | **−1.10** |
| clean × BUY × w≥2%, explicit, ×1.157 inflation | −0.1416 | 0.1489 | **−0.95** |
| clean × BUY × w≥2%, + 15 bps/leg, iid | −0.2091 | 0.1287 | −1.63 |

⚠ **And restricting to `w ≥ 2%` also DROPS trades, so n < 61 and the SE rises further.** Kimi's
published prediction was *"net ≈ −0.15R, t ≈ −1.1 to −1.4, not significant"*; the arithmetic says
**−0.142R, t −0.95 to −1.10.** ⇒ **E3 was decided by the document's own numbers before the probe ran.**

### ⚠ THE PREDICTIONS ABOVE WERE PUBLISHED BEFORE THE PROBE RAN — and §12.31 says two of them were wrong

⭐ **Kimi's C5 is the right methodology and it is worth naming: it published a numeric prediction
for E3 before E3 existed, so E3 became a TEST rather than a search.** I published a second one
(−0.142R, t −0.95…−1.10) from the same inputs. ⛔ **Both were too optimistic, and for the same
reason: they held σ fixed at the clean×BUY value of 1.0050.** Dropping the sub-2% cohort removes
the high-variance tail, `σ` falls to **0.671**, the SE falls with it, and the measured cell is
**−0.1772R at t = −1.84** — closer to the number under attack than to the prediction.

⇒ ⭐⭐ **The adjudication therefore SPLITS, and neither source had it right:**

| claim | verdict |
|---|---|
| *"`t = −2.19` is the wrong cohort's number"* — Claude Part B | ✅ **UPHELD.** It is `BUY`, all windows, all stop widths, including trades the order path refuses |
| *"the net question is NOT answered on the tradeable book"* — Claude Part B's conclusion | ⛔ **REFUTED BY MEASUREMENT.** On the correct cohort it is **t = −1.84** explicit and **t = −2.52** at 15 bps/leg (§12.31) |
| *"net ≈ −0.15R, t −1.1…−1.4, not significant"* — Kimi C5 | ⚠ **half right** — the mean is −0.177R, the t is −1.84 |
| §12.18g's **conclusion** (*the net question is answered negatively*) | ⭐ **SURVIVES its own number's withdrawal.** The number was from the wrong cohort; the right cohort says the same thing less loudly |

⇒ **The cleanest statement of what round 9 did to §16.1b's row: the NUMBER is withdrawn, the
VERDICT is re-derived on the correct population, and it is weaker than published and still
negative.** ⚠ **That is not the same as "Claude's refutation failed"** — without it, the document
would still be quoting a `t` from a population its own order path refuses.

### ⭐ What survives, and it is stronger than the t ever was

⚠ **None of this rescues the strategy, and two things get sharper:**

1. ⭐⭐ **Plan item 22, open since round 1, computed.** Per rupee-day deployed, against the basket
   the book selects from — **and the sign is invariant to the one input nobody had measured:**

   | book | net of | per trade | T=2 | T=3 | T=4 | T=5 |
   |---|---|---:|---:|---:|---:|---:|
   | ALL | explicit | −0.583% | −94.0 pp/yr | −69.5 | −57.3 | −49.9 |
   | **BUY** | **explicit** | **−0.445%** | **−76.6 pp/yr** | **−57.9** | **−48.6** | ⭐ **−43.0** |
   | BUY | +15 bps/leg | −0.745% | −114.4 | −83.1 | −67.5 | −58.1 |

   ⚠ **The table above is the PREDICTION, computed from an assumed `T` because nobody had measured
   it.** `[measured]` **mean `T` is 3.59 sessions, not 5** (median 5, and **14.6% of trades exit in
   the SAME session**) — so the per-trade loss is spread over fewer days and the per-day figure is
   worse than every column above. ⛔ **But the basket half of the comparison also moved, and it
   moved further: see §12.31. The measured gap is −19 to −56 pp/yr on BUY, not −43.**
   **What survives unconditionally is the SIGN, and that it needs no significance test.**

2. ⭐ **The posterior against the drift-inclusive hurdle.** ⚠ **Two SEs for one cell, same round:**
   D4 used **0.1287** (iid) and §16.1b's MDE row used **0.1490** (inflation-adjusted). `[verified]`
   Recomputed consistently at the inflation-adjusted SE, against three hurdles:

   | prior sd | P(μ > 0) | P(μ > 0.111 break-even) | ⭐ **P(μ > 0.199 = break-even + drift)** |
   |---:|---:|---:|---:|
   | 0.03R | 45.6% | 0.005% | **0.000%** |
   | 0.05R | 42.9% | 0.58% | **0.001%** |
   | 0.10R | 37.6% | 4.9% | **0.33%** |
   | 0.20R *(absurdly generous)* | 32.5% | 8.3% | **1.70%** |

   ⚠ **This is the arithmetic of the published inputs and BOTH of its inputs were wrong.** The
   `0.199R` hurdle is `break-even + 0.088R`, and the `+0.088R` is an **unpaired** drift taken from
   a different block of sessions than the trades occupy. ⛔ **Paired, the basket over these
   trades' own windows is NEGATIVE** (§12.31), so the drift-inclusive hurdle is **+0.008R**, not
   +0.199R — a 25× change that runs AGAINST the document. ⭐ **The SE inconsistency Claude found
   is real and is fixed; the conclusion it was used to draw is withdrawn.**

⇒ ⭐ **THE SUPPORTABLE STATEMENT, THIRD REVISION:** *the GROSS question is underpowered and will
stay so for a decade; the NET question is answered negatively on the MIXED book and is **NOT**
answered on the tradeable one; and the decision does not depend on either, because the ₹/day gap
against the basket is 43–77 pp/yr and the posterior against that hurdle is under 2%.*
**The decision is economic and it was never going to be a t-statistic.**

⚠ ⭐ **AND THE FAMILY ERROR, SIXTH INSTANCE.** §12.18g read a level (`t = −2.19` on one cohort)
and never asked whether it survived the restriction that the cohort's own order path imposes.
That is C2's error — *a quantity computed on a subgroup is not evidence about the subgroup until
it is compared with its complement* — wearing a different hat: **a quantity computed on a
population is not evidence about a SUB-population until it is recomputed there.** It was committed
inside §12.18, the section that named it.

## 12.26 ⭐⭐ A THIRD MECHANICAL TERM IN THE STOP-WIDTH FAMILY — and it is why E1 as specified could not have worked

**This is the most valuable thing in round 9 and it is not the refutation.** §13.8's E1 says:
re-report the positional stop-width family in raw %, ATR units and net ₹. ⭐ **Re-reporting in
raw % removes ONE mechanical term and leaves a second one of comparable size.**

`R = (α + drift·T) / w`, where `T` is the realised holding period:

| term | direction of its effect on the tight-vs-wide R spread | removed by raw %? |
|---|---|---|
| `1/w` amplification | makes **tight** look **worse** (negative contribution to the spread) | ✅ yes |
| ⭐ **`drift × T` accrual** | ⭐ makes **tight** look **BETTER** (positive contribution) | ⛔ **NO** |
| genuine stop-geometry α | unknown — this is the only thing E1 wants | — |

⚠ **Correction to the source that found it.** Claude's own summary row reads *"`drift × T` accrual
makes **wide** look better"*, and its own next table contradicts it: the drift contribution is
`drift·T/w`, which is **larger for tight stops** (`+0.192R` at `T`=1.5/`w`=0.638%) than for wide
(`+0.075R` at `T`=4.5/`w`=4.91%). A tight stop is held for fewer days but divides by a much smaller
number, and the division wins. **The prose ("the two terms push in opposite directions") is right;
the table's label is inverted.** The numbers, and the conclusion, are unaffected.

`[verified]` **Sizing it against the document's own `E[1/w]`:**

| `T_tight` / `T_wide` | drift-in-R, tight | drift-in-R, wide | **contribution to the spread** |
|---|---:|---:|---:|
| 1.0 / 4.5 | +0.128 | +0.075 | **+0.053R** |
| 1.5 / 4.5 | +0.192 | +0.075 | **+0.117R** |
| 2.0 / 4.5 | +0.256 | +0.075 | **+0.181R** |

⇒ ⭐⭐ **The drift term is the same order of magnitude as the effect being interpreted, and its
sign and size depend entirely on `E[T | w]` — a quantity the probe did not emit until this round.**

### ⭐⭐ And it is already visible in §12.18f's own residual — which is my addition, not the source's

§12.18f simulated a spread of **−0.4470** against a measured **−0.3864**: a **14% over-prediction**,
which the document read as *"the mechanical term explains all of it, and slightly more than all of
it."* `[verified]` **Solve the residual for the one unknown:**

```
observed − simulated = +0.0606R
+0.0606 = 0.0816 × (T_tight/0.638 − T_wide/4.91)      [with T_wide = 4.5]
⇒ T_tight = 1.06 sessions
```

⇒ ⭐ **A 0.64% stop being hit in ~1 session is not a fitted parameter, it is the physically obvious
answer** — and it reproduces the residual exactly. **"The mechanical term explains 116% of the
spread" and "two mechanical terms partially cancel and neither has been isolated" fit the same data,
and the second one also explains the 16 percentage points of over-shoot that the first has to
discard.**

### ⭐⭐ The stronger version: §12.18f's independence is NOT measured, it is un-rejected

§12.18f's load-bearing sentence is: *"The independence assumption is not an assumption — it is
measured. R7-J's `ret_pct ~ stop_width` gives t = +1.07."*

⛔ **t = +1.07 is a failure to reject independence. It is not a measurement of independence** —
and the distinction is exactly the one this document has spent nine rounds enforcing everywhere
else. ⭐ **Worse: the drift×T hypothesis makes a POINT prediction for that slope, and the point
estimate matches it.**

| quantity | value |
|---|---:|
| `[measured]` R7-J slope, `ret_pct ~ stop_width%` | **+0.11235** (SE 0.10480, t +1.07, 90% CI [−0.060, +0.285]) |
| `[derived]` drift×T prediction at `T` 1.0 → 4.5 over `w` 0.638 → 4.91 | **+0.0669** |
| `[derived]` drift×T prediction at `T` 1.5 → 4.5 | **+0.0573** |

⇒ ⭐⭐ **The measured slope is POSITIVE, of the sign drift×T requires, 1.7–2.0× its predicted
magnitude, and comfortably inside its own CI.** The data cannot separate "independent" from
"exactly the drift×T dependence a rising market forces" — **and §12.18f chose the first without
noticing the second was on the table.** The conclusion (`1/w` explains most of the swing gradient)
survives; the claim that independence is *established* does not.

### ⇒ E1 is re-specified, and it merges with §12.20

⭐ **E1 must carry a fourth unit: `raw return % − matched-window basket return %`, per trade, over
each trade's ACTUAL entry-to-exit window** — plus mean and median `T` per bucket, so the mechanism
is visible rather than inferred. **§12.20 and E1 are the same measurement and were written as two
plan items.** `swing_dependence_probe.py` now emits `T`, `bench` and `excess` per trade for exactly
this reason; `positional_probe.py` needs the same three columns.

⚠ **And one thing the paired column fixes that nobody raised:** `[measured]` the basket's drift is
**not a constant**. Over the full span of the probe's own universe it is **+0.2042%/day**; over the
post-gap block §12.20 measured **+0.0816%/day** — a **2.5× difference**. ⇒ **Using one scalar
drift for all trades is itself a sample-tag violation.** The paired estimator does not need a
scalar at all, which is a second and independent reason to prefer it.

## 12.27 ⭐ THE POSITIONAL CONTRAST, COMPUTED FOR THE FIRST TIME — and the sign argument is the SEVENTH instance

§13.8 states E1's expected outcome as *"if positional dies the same way [as swing], §4.4, §12.1,
§12.2, plan item 18 and the σ_R objective all close on one afternoon."* ⛔ **That prior was never
supported, and §12.1's own rows have never been turned into a contrast.**

`[verified]` From §12.1's published table, computed here for the first time:

| cohort | n | mean R | sd | SE | t vs 0 |
|---|---:|---:|---:|---:|---:|
| ALL | 385 | −0.0320 | 2.088 | 0.1064 | −0.30 |
| WIDE (w ≥ 2%) | 271 | **+0.0840** | 1.844 | 0.1120 | +0.75 |
| TIGHT (w < 2%) | 114 | **−0.3060** | 2.566 | 0.2403 | −1.27 |
| ⭐ **CONTRAST tight − wide** | — | ⭐ **−0.3900** | — | **0.2652** | ⭐ **t = −1.47, p = 0.141** |
| MDE @ 80% power | — | **+0.7428R** | — | — | the observed contrast is **0.53×** of it |

⇒ ⭐ **§12.2's headline — "removing the sub-2% cohort raises mean R by 0.116R" — is a contrast
quoted without an SE, and §12.1's "the sign flips" is a level read in two halves.** Neither
positional bucket is distinguishable from zero and neither is distinguishable from the other.
**The positional stop-width family is not "about to close like swing"; it is UNDERPOWERED, and
that is a different plan item.**

### ⚠ But the structural argument against it is itself a level-read — the seventh instance

Claude's C1 argues: under `ret ⊥ w`, `E[R|bucket] = E[ret]·E[1/w|bucket]` and `E[1/w] > 0` always,
so **every bucket must carry the sign of the raw mean**. Swing's buckets are −0.4726 and −0.0862
(same sign ✅ consistent); positional's are −0.306 and **+0.084** (opposite ⇒ *"`1/w` cannot produce
this at any μ_ret"*).

⭐ **The algebra is right and the inference from it is not.** `[verified]`

| question | answer |
|---|---:|
| P(true WIDE mean < 0 \| +0.084 ± 0.1120) | ⭐ **22.7%** |
| P(true TIGHT mean > 0 \| −0.306 ± 0.2403) | 10.1% |

⇒ **Roughly one chance in four that the wide bucket is truly negative and the pure-`1/w` story
holds after all.** The sign pattern is a property of two point estimates that are each within 1.3
SE of zero. ⛔ **"`1/w` cannot produce this" should read "the point estimates are inconsistent with
it; the data does not exclude it."** ⭐ **That is the family error — reading a level instead of
testing it — committed by the source that named the family, in the same document that named it.
Seventh instance, and the third committed by whoever was enforcing the rule.**

⇒ ✅ **E1's verdict: the CATCH is accepted (the prior was unsupported, the contrast was never
computed, and it is t = −1.47), the MECHANISM claim is downgraded to "suggestive, 23% chance of
being noise", and E1's SPECIFICATION changes per §12.26 — four units plus `T`, not three.**

## 12.28 ⭐⭐ THE ROUND'S REAL CONVERGENCE — E2's ESTIMAND IS AMBIGUOUS, AND THE SPECIFIED ONE IS NOT THE DEPLOYED QUESTION

⭐ **Three sources, working from three different framings, arrived at the same defect in the one
test the 2026-10-31 decision is supposed to rest on.** That is the strongest convergence in nine
rounds, and unlike round 7's four-way direction-split convergence it is about an **unrun** test,
so it is still cheap to act on.

| source | its route to the defect |
|---|---|
| **Deepseek** (Request 1) | ⭐⭐ **the collider.** The 70 gate is a threshold on the same weighted sum the score IS, so IC *within gate-passers* is conditioned on the estimator's own output. Only the **unconditional** IC is not a collider |
| **Kimi** (C1) | ⭐ **estimand drift.** §12.15 pre-registered **3b** as *the conditional forward return of gate-passers vs date-and-characteristic-matched eligible non-passers*. §13.8's E2 silently became *full-cross-sectional panel IC*. Those are different objects and only the first maps to the picker's job |
| **ChatGPT** (§16) | ⭐ **the tail-vs-cross-section mismatch.** The system does not buy the cross-section; it scores → gates → presents ~200 → a human takes 2–3. A full-universe IC can be ≈0 while tail selection is useful, and vice versa |

⇒ ✅ **ALL THREE ACCEPTED. They are one defect seen from three sides, and §12.10c already carried
the principle** (*"near-zero IC can coexist with a valuable event strategy"* — ChatGPT's R4 point,
accepted in round 4 and then not applied when E2 was specified in round 8).

### ⭐ The repair: E2 is THREE estimands, and they cost one pass

| # | estimand | what a null means | what a positive means |
|---|---|---|---|
| **E2a** | ⭐ **UNCONDITIONAL IC** — composite score vs h=5d forward return, across the eligible universe, per date | **the scorer carries nothing and no pipeline repair recovers it** — this is 3a, and it is clean closure | the information exists; ask where it is lost |
| **E2b** | ⭐⭐ **MATCHED-TAIL CONTRAST** — gate-passers vs date-and-characteristic-matched non-passers (the pre-registered 3b) | the gate selects nothing | ⭐ the gate is the value and the ranking is not |
| **E2c** | gate-conditional IC within passers | ⚠ **a COLLIDER — report it, never decide on it** | — |

⇒ ⭐ **The decision tree is what makes this worth the repair, and none of the three branches is
reachable from E2 as written:**

```
E2a ≈ 0  and  E2b ≈ 0   ->  clean closure: the scorer carries nothing
E2a > 0  and  E2b ≈ 0   ->  information exists, the GATE destroys it  ->  the 70 threshold is the bug
E2a ≈ 0  and  E2b > 0   ->  a tail/event selector, not a ranker  ->  a different (valid) strategy class
E2a > 0  and  E2b > 0   ->  information survives to the offered set  ->  the loss is DOWNSTREAM
                            (level stage / geometry / execution) -> pipeline repair, not closure
```

⚠ **And two inputs must become OUTPUTS of the same pass, not assumptions carried into it:**

1. ⭐ **`sd(IC_t)`.** §16.1b already flags 0.10 as `[ASSUMED]` and every power number as linear in
   it — but §13.8 still calls E2 "fully powered", which is **"fully powered conditional on an
   assumption"** (ChatGPT §17). ⚠ **Kimi C8 adds the harder half: the cross-section is not 250
   names.** §12.23 measured **46 → 250** names per session and **65% of names below 95% coverage**;
   at 46 names the pure-noise IC floor is `1/√46` = **0.147**, which exceeds the entire 0.018–0.071
   break-even band. **Early sessions contribute ~nothing and the power table has to be
   coverage-weighted.** ✅ Both accepted. ⭐ **And Kimi's cheapest suggestion first: if
   `factor_sweep.py` stored per-date ICs, `sd(IC_t)` is measurable TODAY and retires before E2 runs.**
2. ⭐ **`E[z | selected]` = 2.268** (Claude D4). It is a **normal-tail** approximation applied to a
   hard gate at 70 on a bounded score whose passers have mean 77.8, sd 5.8 (§12.10c) — not a normal
   tail. Every break-even-IC figure (0.018–0.071) and therefore **KILL LINE 3's SESOI** is linear in
   it. ✅ **Accepted: measure it in the same pass.**

⚠ ⭐ **The honest consequence for the decision date: E2 is no longer "one query".** It is one pass
producing three estimands and two previously-assumed constants. It is still an afternoon of compute
and it is still the only fully-powered question left — but §13.8's "the decisive test is ONE query"
was an under-specification, and under-specifying the decisive test is how KILL LINE 3 went wrong
twice.

## 12.29 ⭐⭐ THE CONFIDENCE NORMALIZER — Kimi C3, CONFIRMED BY CODE, and it reframes ρ = −0.018

⭐ **The best untested idea in the round, and it costs four columns on a probe that already runs.**

`[code]` `app/analysis/confluence.py:159-166`:

```python
total_weighted = sum(f.weight * f.score for f in factors)
total_weight   = sum(f.weight for f in factors if f.score != 0.0)   # <- SCORING factors only
normalized     = total_weighted / total_weight
confidence_pct = int(abs(normalized) * 100)
```

⇒ ⭐⭐ **The denominator counts only the factors that FIRED. One factor scoring 0.8 reads 80%.
Four factors agreeing at 0.6/0.5/0.5/0.4 read ~50% and fail the gate.** The key mechanically
**rewards sparse conviction and punishes broad agreement** — which is the precise inverse of what
the word "confluence" means and of what `trading-domain.md`'s first rule demands.

⚠ **This is not new as a mechanism** — it is §1 #2 of CLAUDE.md, it is why the `entry_diversity`
gate exists, and it is how SRTL entered on `RSI_DIVERGENCE` alone. ⭐ **What is new is the
inference Kimi draws, and it is right: the deployed picker sorts DESCENDING on this key
(§12.21a), so the top of the offered list is systematically enriched in SPARSE-EVIDENCE signals.
`ρ(confidence, R) = −0.018` may therefore be a property of the NORMALIZER rather than of the
FACTORS, and the document has been reading it as the latter.**

⇒ ✅ **ACCEPTED AND BUILT.** `swing_dependence_probe.py` now emits four columns per trade from the
frozen scorer's own output — `wsum` (the un-normalized weighted sum), `nsc` (breadth: how many
factors scored), `wsc` (the denominator itself) and `top` (the largest single contribution's
share) — and `round9_cells.py` re-ranks the same panels by each. **Nothing is recomputed or
reimplemented; the frozen scorer is read.** Three outcomes, all decision-relevant:

- **a rival key ranks materially better** ⇒ ⭐ the information was **destroyed by one division**,
  the repair is a one-line change to a *reporting* quantity (not to the frozen scorer's decision),
  and §13.8's closure paragraph is wrong about which object carries the failure
- **no key ranks** ⇒ ⭐ **the closure is much cleaner than it was** — the negative now covers the
  factor set, not just one summary of it
- **breadth ranks but confidence does not** ⇒ the `entry_diversity` gate, which is ACTIVE on a
  hard-rule argument and has never been credited with a measured edge, is doing real work

⚠ **One honest bound.** `confidence_pct` is also the **gate**, not only the sort key, so every
trade in the artifact already passed a ≥70 filter on it. Re-ranking *within* the passers is
therefore **range-restricted** — a rival key gets a fairer test than confidence does. ⇒ **A null
on the rival keys is strong evidence; a positive on them is suggestive and belongs in E2a's
unconditional pass, not here.** That is the same collider §12.28 just repaired, and it applies to
this test too.

## 12.30 ⭐ FOUR CORRECTIONS TO THE RECORD — three from the round, all cheap, all confirmed here

### 12.30a ⛔⛔ The tick bug contaminates NO number in this document — §12.19b overstated its blast radius

⭐ **Claude D3 and Kimi C6 caught this independently, and the code settles it.**

§12.19b: *"This lands on exactly the cohort that carries the document's remaining positive results
— §12.1's reachable-cohort flip, §7's stop-width buckets and §12.10b's denominator pathology."*

`[code]` **Verified by grep, three ways:**

| consumer | applies `_round_tick`? |
|---|---|
| `scripts/swing_dependence_probe.py` (the source of §12.10b, §12.18f, R7-J, R7-K) | ⛔ **no — zero references** |
| `scripts/positional_probe.py` (the source of §12.1, §7) | ⛔ **no — zero references** |
| `app/backtest/engine.py` (the source of the 1,975-trade headline) | ⛔ **no — zero references** |
| `app/broker/paper_broker.py` | ✅ yes — `_round_tick` at `:71`, called at `:245`, `:263`, `:291`, **and nowhere else in the repo** |

⇒ ⛔ **`positions` = `orders` = 0 rows, and the only consumer of the wrong grid is the paper
broker. The bug contaminates nothing in the adjudication.** It is a **genuine before-cycle-2 fix
with a much smaller blast radius than stated**, and §12.21c's parity matrix was right while
§12.19b's prose was wrong — **two sections of the same round disagreeing, in the round that
adopted the larger claim into §16.1b.** ✅ **§12.19b is corrected in place below.**

### 12.30b ⚠ The 0.064R figure is the WRONG one of two — Kimi C6

`[verified]` On the ₹39 archetype, half-tick adverse per leg:

| quantity | value | in R at a 2% stop |
|---|---:|---:|
| rounding at the ₹0.05 grid, round trip | 12.82 bps | **0.0641R** |
| rounding at the true ₹0.01 grid, round trip | 2.56 bps | 0.0128R |
| ⭐ **EXCESS — the actual artifact** | ⭐ **10.26 bps** | ⭐ **0.0513R** |

⇒ §12.19b's sentence uses the **excess** for its "~10 bps" and "40% of the 25.5 bps stack" and the
**total** for its "0.064R". ✅ **The artifact is 0.051R, not 0.064R.** Direction and the
before-cycle-2 classification are unchanged.

### 12.30c ⚠ Two sections are numbered `12.18f` — Claude D5

`[verified]` Line 2417 (`C7 — the core is right…`) and line 2506 (`C5 — MEASURED…`), with
`12.18e` at 2469 **between** them. §16.1b cross-references "§12.18f" for both. ⭐ **In a document
whose §16.1 is explicitly the contract, an ambiguous cross-reference is the same class of defect
as an unstamped sample tag.** ✅ **Renumbered in place: the C7 section becomes `12.18f-C7` and the
C5 section `12.18f-C5`, and §16.1b's pointers are disambiguated.**

### 12.30d ⚠ "MDE" needs a convention, not just a number — ChatGPT §4

§16.1b adopted **`2.8016·SE` at 80% power**, correcting `2·SE`. ⭐ **Right correction, and it is
still under-specified:** 2.8016 = `z(0.975) + z(0.80)` is **two-sided α=0.05 at 80% power**. A
one-sided α=0.05 test at the same power needs **2.487·SE**; the document also reasons in 90%
intervals, t≈2, and a DSR bar at t≈3.6 — **which are four conventions in one reference card.**

✅ **ACCEPTED as a schema rule rather than a number.** ⚠ Bounded honestly: `[verified]` it changes
nothing operationally (the honest cell's MDE is +0.417R two-sided and +0.371R one-sided; no
plausible edge is between them). ⭐ **The reason to adopt it anyway is that this exact class of
ambiguity — a statistic quoted without the convention that defines it — is what produced the
`2·SE` error the same card corrected one round ago.** From here, no MDE is quoted without
`alpha · sidedness · power · SE-flavour`.

## 12.31 ⭐⭐⭐ ROUND-9 MEASUREMENTS — E3 RUN, AND THE PAIRED NULL INVERTS §12.20

`[measured]` `swing_dependence_probe.py --stocks 250 --stride 10 --dump-trades` (2026-09-11,
**185 trades — `probe-185` reproduced exactly**, every published moment matches to 4 decimals)
→ `scripts/round9_cells.py`. ⭐ **The artifact is the deliverable: one pass, 185 × 25 columns,
and every cell below is a cheap read off it.**

### 12.31a ⭐⭐ The holding period, emitted for the first time — and the 5-session null was never right

| cohort | n | **mean T** | median T | **T = 0 (same-session exit)** | mean w | E[1/w] |
|---|---:|---:|---:|---:|---:|---:|
| ALL | 185 | **3.59** | 5.0 | **14.6%** | 4.43% | 0.597 |
| BUY | 82 | 3.55 | 5.0 | 17.1% | 4.34% | 0.566 |
| clean | 147 | 3.68 | 5.0 | 13.6% | 4.41% | 0.586 |
| clean × BUY | 61 | 3.77 | 5.0 | 14.8% | 4.37% | 0.438 |
| ⭐ **clean × BUY × w≥2% (E3)** | **49** | **4.00** | 5.0 | 10.2% | 5.20% | **0.220** |

⇒ ⭐ **Every "per day" statement and every fixed-horizon null in the record was conditional on a
number nobody had measured**, and §12.20's 5-session assumption over-states the exposure window by
**~39%** on the mixed book. ⭐ **`T` also rises sharply with stop width — `d(T)/dw = +0.384,
SE 0.057, t = +6.69`** — which is the premise of §12.26's third mechanism, now measured, and the
largest |t| in nine rounds. ⚠ **It is a structural fact, not an edge claim, so the DSR bar does
not apply to it** — but it settles that the mechanism exists.

### 12.31b ⭐⭐ E3 — the one cell the programme turns on, computed in one pass

`[measured]` **clean × BUY × w ≥ 2%, n = 49.** Charges = the measured 25.5 bps explicit stack;
slippage reported as a ladder because it can never be measured retrospectively (`orders` = 0).

| quantity | mean | iid SE | **t** | clustered SE | **t (date-clustered)** |
|---|---:|---:|---:|---:|---:|
| gross R | −0.1212 | 0.0959 | −1.26 | 0.0991 | −1.22 |
| ⭐ **NET R, explicit** | ⭐ **−0.1772** | 0.0961 | ⭐ **−1.84** | 0.0986 | **−1.80** |
| NET R, +10 bps/leg | −0.2212 | 0.0963 | −2.30 | 0.0983 | −2.25 |
| ⭐ **NET R, +15 bps/leg** | **−0.2432** | 0.0965 | ⭐ **−2.52** | 0.0982 | **−2.48** |
| NET R, +30 bps/leg | −0.3092 | 0.0970 | −3.19 | 0.0978 | −3.16 |
| gross raw return % | −0.5781 | 0.4941 | −1.17 | 0.5142 | −1.12 |
| NET raw return %, explicit | −0.8331 | 0.4941 | −1.69 | 0.5142 | −1.62 |
| NET return / ATR20 | −0.3510 | 0.2017 | −1.74 | — | — |
| NET cash ₹ | −307.50 | 184.57 | −1.67 | 191.13 | −1.61 |
| ⭐ **E[cost in R] on this cohort** | ⭐ **+0.0561** | 0.0034 | +16.4 | — | — |

⇒ ⭐⭐ **THREE THINGS THIS SETTLES AT ONCE.**
**(1)** **§12.18g's `E[cost in R] = 0.0573R` estimate for the reachable book is confirmed at
0.0561R (2% error)** — the Jensen correction was right and its own caveat was the precise answer.
**(2)** ⭐ **Date-clustered SEs move nothing** — every t shifts by ≤0.06. ChatGPT's §6 demand (*"we
cannot have RVOL invalid under iid and the net mean apparently valid under iid"*) is **answered:
the net mean survives clustering, and RVOL did not.** The two are different because RVOL is a
market-wide per-DATE regressor and the net mean is per-trade. ✅ **Legitimate, and now verified
rather than asserted.**
**(3)** ⛔ **Restricting to the live-reachable book makes the swing gross WORSE, not better**
(−0.0843 → −0.1212) while cutting σ from **1.0050 → 0.6712.** ⚠ **This is the OPPOSITE of §12.1's
positional result**, where the reachable cohort was the better one — so the two classes do not
share the mechanism, which is a second independent reason E1's prior (§12.27) was unsupported.

### 12.31c ⭐⭐⭐ THE PAIRED DRIFT NULL — and it REFUTES §12.20a's central claim

§12.20a: *"the correct null roughly DOUBLES the point-estimate deficit: −0.084R against zero
becomes −0.137R to −0.172R against the drift."* `[measured]` **Paired per trade, over each
trade's OWN entry-to-exit window:**

| cohort | **basket over the trade's own window** | t | **PAIRED excess (trade − basket), gross** | t | **NET excess** | t |
|---|---:|---:|---:|---:|---:|---:|
| ALL | **+0.2468%** | +1.72 | −0.5746% | −2.15 | −0.8296% | −3.11 |
| ⭐ **BUY** | ⛔ **−0.1659%** | −0.71 | ⭐ **−0.0218%** | ⭐ **−0.07** | −0.2768% | −0.83 |
| clean | +0.1969% | +1.24 | −0.6055% | −2.05 | −0.8605% | −2.91 |
| clean × BUY | ⛔ **−0.3037%** | −1.09 | −0.2250% | −0.60 | −0.4800% | −1.29 |
| ⭐ **E3** | ⛔ **−0.3376%** | −1.05 | −0.2405% | −0.54 | −0.4955% | −1.11 |

⇒ ⛔⛔ **THE BASKET OVER THE TRADEABLE BOOK'S OWN WINDOWS IS NEGATIVE.** §12.20 measured
+0.0816%/day on the post-gap block and multiplied by an assumed 5 sessions to get **+0.408%**;
the trades' actual windows returned **−0.166% (BUY) and −0.338% (E3)**. ⭐ **The "correct null"
is not +0.088R, it is −0.048R on the E3 cell — a swing of 0.136R, in the direction that makes the
book look BETTER.**

⇒ ⭐⭐ **AND THE FINDING THAT FALLS OUT IS THE MOST INTERESTING THING IN THE ROUND: on the
tradeable book, GROSS ALPHA IS ZERO.** `excess = −0.0218%, t = −0.07` on 82 BUY trades. **The
book's gross loss is not stock selection. It is WHEN it trades.** The ALL book's basket is
+0.247% while the BUY book's is −0.166%, so **the SELL signals fire into rising tape and the BUY
signals into falling tape** — a measurable, adverse timing property that no round has looked for
because no round had the paired column.

⚠ **Three bounds, stated because they constrain the reading rather than rescue it.**
**(1)** `t = −0.07` on `n = 82` is **not** evidence of zero alpha; it is the absence of evidence
of any alpha, with an MDE of roughly ±0.93% per trade. **(2)** The basket inherits the **0a.3
survivorship defect** (today's liquidity), so its drift is if anything **overstated** — which makes
the measured α **conservative**. **(3)** The paired excess is **not beta-adjusted**; at β = +0.92
the correct adjustment is small and moves α slightly positive.

⇒ ⛔ **CONSEQUENCE — three published conclusions are withdrawn, two of them mine and one of them
round 9's own:** **§12.20a's "the correct null roughly doubles the deficit"** · **§16.1b's
"α = −0.137R…−0.172R"** · **round-9 Claude's "P(beats the basket) is under 2% at any prior."**
⭐ **All three used an UNPAIRED drift from a different block of sessions than the trades occupy.**
⚠ ⭐ **THE RULE THIS EARNS, and it is the generalisation of §16.1's sample-tag rule to TIME: a
benchmark measured over one set of sessions may not be subtracted from a return measured over a
different set. Pair it, or do not subtract it.**

### 12.31d ⭐⭐ THE STOP-WIDTH FAMILY — closed a third time, and by the mechanism §12.18f missed

`[measured]` The same contrast, three units, `ALL` (n = 185):

| unit | tight (w<2%, n=30) | wide (w≥2%, n=155) | **contrast** | SE | **t** | p |
|---|---:|---:|---:|---:|---:|---:|
| **R** | −0.4726 | −0.0862 | **−0.3864** | 0.2492 | **−1.55** | 0.121 |
| **raw %** *(removes `1/w`)* | −0.5475 | −0.2854 | **−0.2622** | 0.3381 | **−0.78** | 0.438 |
| ⭐ **excess vs matched basket** *(removes `1/w` AND `drift×T`)* | −0.5169 | −0.5858 | ⭐ **+0.0690** | 0.4143 | ⭐ **+0.17** | 0.868 |

⇒ ⭐⭐ **The gradient decays −0.386 → −0.262 → +0.069 as the two mechanical terms are removed in
turn, and the sign FLIPS.** §12.18f closed the family on the `1/w` term alone and its simulation
over-shot by 14%; **that 14% is the `drift×T` term, and pairing removes it.** ✅ **Claude's C2/C3
is CONFIRMED BY MEASUREMENT, not merely accepted as an argument.**

`[measured]` **And the slope decomposition confirms the mechanism quantitatively:**

| regression (ALL) | slope | SE | t |
|---|---:|---:|---:|
| `d(ret %)/dw` | +0.1053 | 0.1030 | +1.02 |
| ⭐ `d(T)/dw` | ⭐ **+0.3844** | 0.0574 | ⭐ **+6.69** |
| `d(excess %)/dw` *(basket removed)* | **+0.0755** | 0.1183 | +0.64 |

⇒ Removing the basket removes **0.0298** of the `ret ~ w` slope; the drift×T prediction is
`basket_per_day × dT/dw` = 0.0688 × 0.384 = **0.0264**. ⭐ **Agreement to 12%.** ⇒ §12.18f's
*"independence is not an assumption — it is measured"* is **withdrawn**: the slope is a
**non-rejection** whose point estimate is ~25% drift×T and ~75% unexplained noise, and the
document read the first as the second.

⚠ **On the clean × BUY cell all three contrasts are ≈ 0 with MDEs of 1.5–2.0R** — the tradeable
book cannot see this family at all. ⇒ **The swing stop-width question is CLOSED and should not be
re-opened in any unit; E1 remains worth running on POSITIONAL only, per §12.27.**

### 12.31e ⛔ TWO HYPOTHESES TESTED AND REFUTED — and both refutations make the closure cleaner

**(i) Kimi C3 — the confidence normalizer. REFUTED.** `[measured]` Four rival ranking keys,
computed from the frozen scorer's own factor list, on the same 185 panels:

| ranking key | ρ vs R | perm p | ρ vs raw % | perm p |
|---|---:|---:|---:|---:|
| ⭐ `confidence_pct` **(the deployed sort key)** | −0.0179 | 0.807 | −0.0262 | 0.728 |
| raw weighted sum *(un-normalized)* | +0.0544 | 0.465 | +0.0375 | 0.608 |
| breadth — # of factors that scored | +0.0295 | 0.691 | +0.0149 | 0.834 |
| weight that scored *(the denominator itself)* | +0.0416 | 0.569 | +0.0187 | 0.795 |
| concentration — top factor's share | −0.0435 | 0.555 | −0.0179 | 0.801 |

Breadth buckets (ALL): 1 factor **−0.187** · 2 **−0.175** · 3 **−0.073** · 4 **−0.275** · 5 +0.374
(n=3). **No monotone pattern.**

⇒ ⛔ **The mechanism Kimi identified is real and confirmed in the code (§12.29), and the
information it was hypothesised to be destroying does not exist.** ⭐⭐ **This is the second
outcome pre-registered in §12.29 and it is the valuable one: the negative now covers the FACTOR
SET, not just one summary of it.** Removing the normalizer recovers nothing. ⚠ Bounded as
pre-registered: all 185 trades already cleared a ≥70 gate **on confidence**, so this is
range-restricted and a null here is stronger than a positive would have been. **The unconditional
version is E2a.**

**(ii) Claude G4 — the `choppy` display filter as a selector. REFUTED.** `[measured]`

| cohort | ER < 0.30 (**HIDDEN** by the UI) | ER ≥ 0.30 (shown) | contrast | SE | t | p |
|---|---:|---:|---:|---:|---:|---:|
| ALL, R | −0.1489 (n=124) | −0.1488 (n=61) | **−0.0001** | 0.1344 | **−0.00** | **0.999** |
| ALL, excess vs basket | −0.5714 | −0.5811 | +0.0097 | 0.5535 | +0.02 | 0.986 |
| clean × BUY, R | −0.0056 (n=35) | −0.1903 (n=26) | +0.1846 | 0.2384 | +0.77 | 0.439 |

⇒ ⛔ **`p = 0.999` is as close to a perfect null as this document has produced.** The filter that
hides **67% of the offered set** separates nothing. ⚠ **And on the tradeable cell its sign is
wrong** — the HIDDEN cohort is the better one (+0.18R, not significant). ⇒ ✅ **A9 is decided by
measurement: DELETE both undeclared filters rather than declare them.** Deleting them also removes
two axes from §12.8's corpus-vs-deployed estimand gap **at zero cost**, which is the cheapest
estimand repair in nine rounds.

### 12.31f ⭐ ₹/DAY — plan item 22, measured, and the aggregation choice moves it 2×

⚠ **Two defensible aggregations, and Claude's Part F used neither explicitly.** *Mean-of-ratios*
counts a same-session exit as a full day of exposure; *ratio-of-means* (total return ÷ total days
deployed) is **what the account experiences**, and is the one a capital decision should use.

| cohort | slip | mean-of-ratios vs basket | **ratio-of-means vs basket** |
|---|---:|---:|---:|
| ALL | 0 | −0.365 vs +0.075 %/d = **−110.9 pp/yr** | −0.156 vs +0.066 = **−56.0 pp/yr** |
| **BUY** | **0** | −0.247 vs −0.026 = **−55.8 pp/yr** | −0.119 vs −0.045 = ⭐ **−18.8 pp/yr** |
| BUY | 15 | −0.374 vs −0.026 = −87.6 pp/yr | −0.200 vs −0.045 = **−39.1 pp/yr** |
| **E3** | **0** | −0.338 vs −0.088 = **−63.0 pp/yr** | −0.203 vs −0.082 = ⭐ **−30.4 pp/yr** |
| E3 | 15 | −0.443 vs −0.088 = −89.5 pp/yr | −0.276 vs −0.082 = **−48.9 pp/yr** |

⇒ ⭐ **Claude's "−43 pp/yr" is inside the measured range and is not the number.** The honest
statement: ⭐⭐ **per rupee-day deployed, the tradeable book underperforms holding the universe it
selects from by 19–56 pp/yr net of explicit charges (30–63 pp/yr on the reachable cell), and by
39–90 pp/yr with a 15 bps/leg slippage assumption.** ⚠ **The range is aggregation, not
uncertainty** — both ends are computed on the same trades — and **the sign is invariant to every
choice made anywhere in this section.**

⭐ **And the 2× gap between the two aggregations has a single, measurable cause.** `[measured]`
The **27 same-session exits (14.6%)** are not a rounding detail — they are the worst cohort in the
book by a wide margin:

| cohort | n | mean R | win rate |
|---|---:|---:|---:|
| **`T` = 0 (exit on the entry bar)** | **27** | ⛔ **−0.7034** | **14.8%** |
| `T` ≥ 1 | 158 | −0.0541 | 43.7% |

⇒ **Mean-of-ratios charges each of those a full day of exposure for a −0.70R outcome**, which is
where the entire gap between −56 and −19 pp/yr comes from. ⚠ **Both treatments are defensible and
neither is a bug** — a stop hit on the entry bar really did consume a day of capital, and it really
did not consume five. ⭐ **The finding underneath the aggregation argument is the more useful one:
`_simulate_trade` books 1 trade in 7 as dying on the bar it opened, at −0.70R, and that cohort has
never been separated out anywhere in the record.** It is also where harness defect #4 lives
(2 of 185 booked `hit_sl` with a positive return, 1.08%). **Worth one column in B7's MFE/MAE pass.**

⇒ ⭐⭐ **THAT is the sentence the 2026-10-31 decision should be written in, and Part F was right
about that even though its number was not.** It needs no t-statistic, no prior, no MDE and no
convention — which is exactly why it survived a round in which almost every t-statistic moved.

### 12.31g The posterior, with the prior on the right quantity and the hurdle paired

⚠ **One methodological fix of my own before the table: the prior belongs on the GROSS mean.** A
prior of the form *"an unfitted TA scorer has no edge"* is a claim about gross edge; **costs are
known, not estimated, and must not be shrunk toward zero.** §12.18h D4 had this right. `[measured]`
**E3 cell, gross −0.1212R, iid SE 0.0959, clustered 0.0991; hurdles from the SAME 49 trades:**
`E[cost]` **+0.0561R** · paired basket **−0.0478R** ⇒ **break-even + basket = +0.0083R.**

| prior sd | P(μ > 0) | P(μ > break-even) | ⭐ **P(μ > break-even + PAIRED basket)** | P(same, @15 bps/leg) |
|---:|---:|---:|---:|---:|
| 0.03R | 35.3% | 0.97% | **25.2%** | 0.15% |
| 0.05R | 28.0% | 3.2% | **22.0%** | 1.2% |
| 0.10R | 18.1% | 4.3% | **15.1%** | 2.4% |
| 0.20R | 12.7% | 3.7% | **10.8%** | 2.3% |

⇒ ⛔ **Round-9 Claude's "P(beats the basket) < 2% at every prior" is REFUTED: it is 11%–25%**,
because the hurdle it used (+0.199R) was built from an unpaired drift and the paired one is
+0.008R. ⚠ **And round-8's own "0.4%–5.7%" is confirmed in shape against the CASH hurdle
(1.0%–4.3% here) but it is not the decision-relevant hurdle.** ⭐ **The honest summary: against
cash the book is ~96% likely to lose; against the market it selects from, it is ~15–25% likely to
win, and it takes single-name risk to do it.** ⚠ **That is a WORSE argument for trading it than
the published one, not a better one** — it says the book is a high-variance way to slightly
under-perform a basket you can buy with one order.

## 12.32 ⭐⭐ THE FACTOR INVENTORY, READ FROM THE FROZEN SCORER — Kimi R3 and Deepseek R5, answered

`[measured]` `run_all_factors` called on **487 real panels** across 40 liquid names, counting how
often each factor actually **scores** (`score != 0.0`, which is the only condition under which it
enters the confidence denominator — `confluence.py:160`):

| factor | weight | scored | % of panels |
|---|---:|---:|---:|
| ⛔ **DOW_TREND** | ⛔ **20** *(the heaviest)* | **0** | ⛔ **0.00%** |
| PRICE_VS_EMA | 15 | 341 | ⭐ **70.02%** |
| BULLISH_HARAMI | 15 | 37 | 7.60% |
| BEARISH_ENGULFING | 15 | 23 | 4.72% |
| PAPER_UMBRELLA | 15 | 15 | 3.08% |
| BULLISH_ENGULFING · PIERCING · BEARISH_HARAMI · DARK_CLOUD · EMA_CROSS · EVENING_STAR · MORNING_STAR · HANGING_MAN · SHOOTING_STAR | 15 each | 3–9 each | **0.21–1.85%** |
| ⛔ **MARUBOZU** | 15 | **0** | ⛔ **0.00%** |
| MACD_HISTOGRAM | 10 | 211 | ⭐ **43.33%** |
| RSI_LEVEL | 10 | 173 | ⭐ **35.52%** |
| SR_ZONE | 10 | 91 | 18.69% |
| VOLUME | 10 | 81 | 16.63% |
| RSI_DIVERGENCE | 10 | 45 | 9.24% |
| MACD_CROSS | 10 | 37 | 7.60% |
| BBANDS | 10 | 29 | 5.95% |
| MULTIBAGGER_EMA | 10 | 2 | 0.41% |
| ADX | 5 | 225 | ⭐ **46.20%** |
| FIBONACCI | 5 | 22 | 4.52% |
| ⛔ **FII_DII_FLOW** | 5 | **0** | ⛔ **0.00%** |
| **TOTAL declared weight** | **325** | — | — |
| ⭐ **mean weight that SCORES per panel** | ⭐ **30.6** | — | ⭐ **9.4% of declared** |

⇒ ⭐ **FIVE THINGS THIS SETTLES, THREE OF THEM NEW.**

**(1)** ⭐ **There are 26 named factors, not 15.** The candlestick detectors are separate
`FactorResult`s and `_best_pattern_factor` selects at most one per panel, so the "15 factors" in
every review document (ours included) is a description of *families*, not of the registry. **The
declared weight sums to 325 and cannot all fire.**

**(2)** ⛔ **Three factors NEVER score on 487 panels: `DOW_TREND` (weight 20 — the heaviest),
`MARUBOZU` (15) and `FII_DII_FLOW` (5) — 40 of 325 declared weight points, 12.3%, structurally
dead.** `DOW_TREND` reconfirms the standing finding (it cannot score by construction on a 20-bar
lookback with `swing_n=5`); `FII_DII_FLOW` is dead because `fii_dii_daily` holds **4 rows**.

**(3)** ⭐⭐ **Kimi C2's warning is CONFIRMED and its consequence is smaller than feared.** The
shipped composite *is* irreproducible historically — but only because of `FII_DII_FLOW`, **which
contributes nothing on live panels either**. ⇒ **E2 can test the SHIPPED scorer, not a "price-only
variant", because the non-price terms are already inert.** ⭐ **That removes a blocker Kimi
correctly identified and ChatGPT's package 3 was built around.**

**(4)** ⭐⭐ **Deepseek R5's question — *"is 'confluence' a real object or a naming convention?"* —
is largely answerable without the correlation matrix.** Four factors carry almost every scoring
event: **PRICE_VS_EMA 70% · ADX 46% · MACD_HISTOGRAM 43% · RSI_LEVEL 36%.** Everything else is
under 19%. ⚠ **And two of the top three are EMA-derived momentum measures**, so the effective
dimensionality is plausibly **2–3, not 15.** ⇒ **The correlation matrix is downgraded from "cheap
and interesting" to "confirmatory", and it is queued behind B6 rather than beside it.**

**(5)** ⭐ **`mean weight that scores = 30.6 of 325` (9.4%)** independently reproduces
`SYSTEM_REVIEW_FOR_QUANT.md`'s "**30 of 160 weight points**" on a different sample and a different
denominator convention. ⚠ **The two documents disagree on the total (160 vs 325) because one counts
families and the other counts registry entries — fix the review document, not this one (W1).**

---

# PART III — THE PLAN

## 13. THE REVISED PLAN

Changes from §8: **CA adjustment moves above the ledger** (R2-13); three Week-0 items added
(offered-set snapshot, fee reconciliation, cost table); the four Week-2 tests become nine, all
**pre-registered**; and every phase now ends in a **kill line with a date** (R2-6).

### ⛔ THE CUT — the plan was 3–4× over capacity, and a readiness gate does not fix that

29 items across four weeks for **one operator with a day job.** Kimi's readiness gate correctly names
the failure mode (kill lines fired on unready data under deadline pressure) and then prescribes a
*gate* rather than a *cut* — and a gate on an over-capacity plan produces indefinite slippage, which
is the other way this ends. Combined with §12.5's "regardless of their outcome": **the only tests
that can move the answer are ones that change friction, σ_R or breadth.**

⭐ **THE PLAN IS EIGHT ITEMS. Everything else waits on #16's outcome.**

| # | item | why it survives the cut |
|---|---|---|
| 1 | **0a.1** freeze the holdout (two locks) | ⭐ **RE-ORDERED TO FIRST (round 5, Kimi): costs nothing, depends on nothing, DO IT TODAY.** Freezing a date is a commitment device, not a test run — gating it behind un-truncation was a leftover from the pre-§12.7 plan |
| 2 | **0a.6** un-truncate the corpus | changes **breadth**. ⚠ Was gated on `corporate_actions` = 0 — **UNBLOCKED by R5-4**: derive the factors from Kite-adjusted ÷ our unadjusted series, ~7 minutes of API calls. Fallback if that fails: truncate at the first fully-adjusted date and proceed anyway |
| 3 | **0a.2** repair harness defect #4 + re-baseline | nine tests would otherwise run through a known-wrong exit ledger |
| 4 | **0a.3** fix the universe selector | one query; removes survivorship **and** look-ahead |
| 5 | **Week 0 #1** CA layer, **with cost-stack bitemporality folded in** | ⚠ **blocked: no CA event source exists (§12.7)** |
| 6 | **Week 0 #2** append-only ledger + off-box export | `positions` = 0 rows; nothing else is worth doing without it |
| 7 | **Week 0 #6** the cost-feasibility table | changes **friction**; kills classes on arithmetic in an afternoon |
| 8 | **#16** in the **repaired economic form** | the one test whose outcome the arithmetic does not already fix. ⚠ price-only variant only if R5-5's FII/DII scrape fails |
| **10** | **Measure ρ̄** — pairwise correlation of concurrent trades' R | ⭐ **NEW (§15.6).** It is `[ASSUMED]` at 0.5 and drives every effective-n figure in this document. At 0.3 every MDE improves ~23%; at 0.7 they worsen ~16%. **One query** |
| **11** | **Measure the slippage residual** | ⭐ **NEW (§12.8b).** Explicit charges are 0.051R at the median stop; the document uses 0.11R. The ~0.06R gap is assumed and drives every conclusion |
| **9** | **Week 0 #5** fee/slippage reconciliation | ⭐ **RESTORED (round 5, Claude).** It was cut while §12.5 named friction one of only three levers that can move the answer — and §12.8b shows **half the friction term is an unmeasured assumption** |

> ⛔ **PROGRAMME SUNSET (round 5, Kimi — the hole in our own standing rule).** Every phase has a kill
> line; the programme did not. **If zero Week-0 items have shipped by 2026-10-31, the programme
> CLOSES** — not pauses — with the ledger archived as the deliverable. A programme with no
> pre-written answer to *what would make us stop* is a hobby, and that includes stopping the
> reviewing.

**Plus two afternoons that are not research and gate strategy choices:** the **BTST/DP support
ticket** (Kimi R4: §13b calls it "the single most decision-relevant item in the plan" and **no week
owned it** — it is now **Week 0 #8**) and the **F&O lot-size feasibility check** at ₹1L.

## 13.9 ⭐⭐ THE PLAN AFTER ROUND 9 — five items closed by measurement, and the AGREED/NOT-AGREED split

⭐ **User ruling, 2026-09-11:** *"complete what is agreed so far between the AI chats; after
building and testing the accepted criteria, then plan, discuss and work on the remaining unagreed
points. Too much discussion exhausts the models and redirects us from the goal."*

✅ **Adopted, and the document's own ledger argues FOR it.** §13g measured the marginal value of
review breadth as negative; §13c said the document had become the work. ⭐ **Round 9 is the first
round where that was not true, and the reason is mechanical: it shipped a probe.** Of five
sources, the two that recomputed produced five of the seven decision-changing points; the one that
only restated produced none. ⇒ **The split below is the operating plan, and nothing in the
NOT-AGREED column blocks anything in the AGREED column.**

### ✅ AGREED AND ALREADY DONE — closed by this round's measurement, not by argument

| # | item | outcome |
|---|---|---|
| **A1** | the probe artifact: `T`, paired `bench`/`excess`, entry-day `er`, four normalizer columns, `--dump-trades`; plus `scripts/round9_cells.py` | ✅ **SHIPPED.** 185 × 25 columns. `probe-185` reproduced to 4 dp, so the artifact is validated against the record it replaces |
| **A2** | ⭐⭐ **E3** — `clean × BUY × w≥2% × net-per-trade`, five units, four SE flavours | ✅ **RUN (§12.31b).** **n=49, net −0.1772R, t −1.84** explicit · **−2.52** at 15 bps/leg. Date-clustering moves every t by ≤0.06 |
| **A5** | the confidence-normalizer decomposition (Kimi C3) | ✅ **RUN and REFUTED (§12.31e).** Every rival key ρ ≈ 0, all p > 0.46 ⇒ ⭐ **the closure now covers the factor set, not one summary of it** |
| **A9′** | measure `_choppy` as a selector before deciding its governance | ✅ **RUN and REFUTED (§12.31e).** `p = 0.999` on 185 trades ⇒ ⭐ **DELETE both undeclared filters**; the governance question answered itself |
| **A11** | ⭐ the ₹/day statement as the headline (plan item 22, open since round 1) | ✅ **COMPUTED (§12.31f).** **−19 to −56 pp/yr vs the basket** net of explicit charges; −39 to −90 with slippage. **Sign invariant to every choice** |
| — | ⭐⭐ **the PAIRED drift null** — which nobody had asked for as a measurement, only as an estimator | ✅ **RUN, and it REFUTED three published conclusions** (§12.31c), two of them mine and one round 9's own |

### ✅ AGREED AND STILL TO BUILD — in this order

| # | item | who converged | why | cost |
|---|---|---|---|---|
| **B1** | ⭐ **delete `_near_expiry` and `_choppy`** from `signals.py`, or declare them in `restrictions.py` with `enforced_by = DISPLAY` | Claude, ChatGPT §12, Kimi R5 — **and now measurement** | `restrictions.py` is not the single source of truth its docstring claims; the filters hide 67% of the offered set and select **nothing** (p 0.999) | 2 h |
| **B2** | ⭐ **`Σ notional ≤ available cash`** as a RiskEngine rail | ChatGPT (r7), Gemini, Deepseek | ⛔ **does not exist in code**; 3 slots at the median 5% stop need **120% of capital**. Identity-enforcing ⇒ no DSR bar. ⭐ **PRECONDITION for cycle 2** | ½ day |
| **B3** | ⭐ **`paper_tick_size` → a price- AND date-dependent schedule TABLE** | **four of five sources** | published exchange schedule ⇒ no forward-evidence bar; changes a recorded number ⇒ before cycle 2. ⚠ blast radius is the **paper broker only** (§12.30a) and the artifact is **0.051R**, not 0.064R | ½ day |
| **B4** | ⭐ **gap guard tests SPAN, not endpoints**, against the session calendar | Claude, ChatGPT §9, Deepseek | catches the 922-day hole, the per-name holes (1.2% of panels) and every future hole without hardcoding any; `GAP_LO`/`GAP_HI` violate **W5** | ½ day |
| **B5** | ⭐ **E1 re-specified** — positional in **four** units (add the paired basket column), + mean/median `T` + `E[1/w]` per bucket, + contrasts with SEs, split by the gap flag | Claude C2/C3 | ⭐ **the swing version of this is now CLOSED by measurement** (§12.31d) **and positional is NOT the same mechanism** — opposite bucket signs, and reachable is the *better* cohort there and the *worse* one on swing | ½ day |
| **B6** | ⭐⭐ **E2 as THREE estimands** — unconditional IC (3a) · matched-tail contrast (3b) · gate-conditional IC (reported as a collider, never decided on). `sd(IC_t)` and `E[z\|selected]` as **OUTPUTS**; coverage-weighted power | ⭐ **Deepseek + Kimi + ChatGPT, independently** | the version in §13.8 cannot reach three of the four decision branches (§12.28). ⭐ **The last unrun question that can change direction** | 1 day |
| **B7** | ⭐ **MFE/MAE + `P(+1R before −1R \| day d)`** — two more columns on A1's artifact | Claude E1, Deepseek R4, open since round 2 | **the companion to B6**: it separates *"no signal"* from *"signal destroyed by the barrier geometry"*, and the optimal hold falls out of the same curve | ½ day, folded into B6 |
| **B8** | ⭐⭐ **the append-only ledger** — `DecisionSnapshot → OrderIntent → Execution → PositionLifecycle → PerformanceRecord`, + ChatGPT's `ExperimentManifest` / `DataSnapshot` / `UniverseSnapshot` | **all five, every round since 7** | ⭐ **not for this strategy — for any successor.** The only real build in the plan | the build |

### ⛔ NOT AGREED — parked until the above is built and read

| item | status after round 9 |
|---|---|
| *"the net question is answered negatively"* | ⭐ **RESOLVED (§12.25 / §12.31b): the NUMBER (t −2.19) is withdrawn as the wrong cohort's; the VERDICT re-derives at t −1.84 explicit, −2.52 at 15 bps.** Claude's refutation was half right and the half it got wrong was the conclusion |
| *is `confidence_pct` uninformative, or is the PICKER uninformative?* | ⭐ **the distinction is ACCEPTED and the measurement is BLOCKED** — ρ = −0.018 licenses *"the deployed RANKING is uninformative"*, not *"the human is bad"*; the human's choices died with the book (`positions` = 0). **Needs B8** |
| **hold period as the breadth lever** | ⚠ still a hypothesis. ⭐ **Now partly costed: mean `T` is 3.59, not 5, so the book already turns over 39% faster than the plan assumed** and the 109 obs/yr figure is understated. **Needs B7's hazard curve before it is a decision** |
| ⭐⭐ *"point the apparatus at ALLOCATION rather than selection"* (Claude Part F) | ⭐ **STRENGTHENED and still parked.** §12.31c measured **gross α ≈ 0 on the tradeable book (t = −0.07)** — the loss is timing and cost, not selection — which is the sharpest argument yet that the SELECTION layer is the part with no demonstrated value. ⛔ **A new strategy class 50 days from the decision date. Record as the answer to §14 Q5; do not start building** |
| a unified `ExecutionKernel` across research/backtest/paper/live | ✅ correct, ⛔ weeks. B2/B3 close the two divergences that change a recorded number |
| tax as its own layer (ChatGPT §24) | ✅ correct in principle, immaterial at ₹1L, changes no recorded number |
| PIT `UniverseSnapshot` (0a.3) | ✅ required, ⭐ **and now also gating the paired basket** (§12.31c bound 2). Folded into B8's schema |
| factor correlation matrix (Deepseek R5) | ⚠ **downgraded by measurement.** §12.31e already shows no ranking key on the factor set carries information; the spectrum would explain *why*, not *whether*. **Queued behind B6** |
| data-gap reconstruction costs · F&O to escape the short constraint | ⛔ both presuppose the programme continues past the sunset |

⚠ **What did NOT change: no queued item attacks profitability.** Round 9 sharpened five
instruments, withdrew four published numbers and closed two hypotheses. **It found no edge, and it
was not looking for one.**

## 13.10 ⭐⭐⭐ WHAT WE ARE BUILDING NOW — the decided queue, with acceptance criteria

⭐ **User ruling 2026-09-11: build the agreed half, then discuss the rest.** This is that half.
**Everything here is converged across sources or settled by measurement — nothing below is waiting
on an opinion.** Ordered by dependency, then by cost. ⚠ **None of it changes the frozen engine,
and only B2/B3 change a recorded number** (both before cycle 2 by the governing rule).

| # | build | acceptance criteria — how we know it is done | ~cost |
|---|---|---|---|
| ⭐ **B1** | **Delete `_near_expiry` and `_choppy` from the display path** (`app/api/v1/signals.py:267-289`) | the two filters are gone or declared in `restrictions.py` with `enforced_by = DISPLAY` · offered-set counts re-run and recorded · a test asserts the listing and the order path admit the same set · `restrictions.py`'s docstring claim becomes true | **2 h** |
| ⭐ **B2** | **`Σ notional ≤ available cash` as a RiskEngine rail** | a new `Restriction` + context loader (one sequence, W2) · rejects when `Σ(open notional) + new > capital` · `off` by default, flips `active` at the cycle-2 reset alongside heat and the position-count cap · a test proves 3 slots at the median 5% stop are refused · `.env.example` + docs in the same commit (W3) | **½ d** |
| ⭐ **B3** | **`paper_tick_size` → a price- AND date-dependent SCHEDULE table** | ⚠ **a table with `valid_from`/`price_lo`/`price_hi`/`tick`/`source`, NOT a constant and NOT a hardcoded `0.01 if price < 250`** — the phase-in is staged (on-grid 0.98 → 0.49 → 0.22 across 2019/2024/2025) · `_round_tick` reads the schedule · the adverse-rounding contract is preserved · a test pins a ₹39 name at ₹0.01 and a ₹2,500 name at ₹0.05 · **W5: the exchange owns this value, so cite the source in the table** | **½ d** |
| ⭐ **B4** | **The gap guard tests SPAN, not endpoints** | `sessions_between(w[0], w[-1]) ≤ WINDOW × (1+tol)` against the market's own session calendar · `GAP_LO`/`GAP_HI` **deleted** (W5 — the calendar is the owner) · re-run the probe and confirm it catches the 5,462 straddling panels **and** the 204 internally non-contiguous ones · applied to `run_single_stock`'s bar-50 walk too, which has no guard at all | **½ d** |
| ⭐ **B5** | **E1 re-specified — the positional family in FOUR units** | `positional_probe.py` gains `T`, `bench`, `excess` (the same three `swing_dependence_probe.py` now has, from the same `basket_series` owner — **do not write a second one**) · buckets reported in R · raw % · ÷ATR20 · **excess vs the matched basket** · **contrasts with SEs, not levels** · mean/median `T` and `E[1/w]` per bucket · split by the gap flag | **½ d** |
| ⭐⭐ **B6** | **E2 as THREE estimands** | **3a** unconditional IC of the composite across the eligible universe, h = **5d pre-registered** · **3b** the matched-tail contrast (gate-passers vs date-and-characteristic-matched non-passers) · the gate-conditional IC **reported and labelled a collider, never decided on** · ⚠ **`sd(IC_t)` and `E[z\|selected]` emitted as OUTPUTS** · power **coverage-weighted** (the cross-section runs 46→250 and `1/√46` = 0.147 exceeds the whole 0.018–0.071 break-even band) · the decision tree in §12.28 pre-registered **before** the run | **1 d** |
| ⭐ **B7** | **MFE/MAE + `P(+1R before −1R \| day d)`** — folded into B6's pass | per-trade MFE/MAE in raw %, ATR and R · the hazard curve for d = 1..20 · time-to-MFE / time-to-MAE by stop-width bucket and direction · ⭐ **and the `T = 0` cohort separated out** (§12.31f: 27 trades, −0.70R, 14.8% win) | **½ d** |
| ⭐⭐ **B8** | **The append-only ledger** | `DecisionSnapshot → OrderIntent → Execution → PositionLifecycle → PerformanceRecord`, plus ChatGPT's `ExperimentManifest` / `DataSnapshot` / `UniverseSnapshot` · every node carries `code_commit · spec_version · experiment_id · data_version · created_at` · **off-box nightly export** · ⚠ **its purpose is a SUCCESSOR, not this strategy** — `positions` = 0 is why nine rounds of live-tape argument were unfalsifiable | **the build** |

### ⭐ Why this order and not another

**B1 → B2 → B3 → B4 are the cheap correctness repairs and two of them gate cycle 2.** B2 in
particular is the **first new safety rail in twenty-five reviews** and the only item on this list
that could lose real money: three slots at the median 5% stop currently require **120% of
capital** with nothing checking. **B5 → B6/B7 are the last two measurements that can change
direction.** B8 is the only thing on the list that survives the strategy.

⚠ **Sequencing rule:** B1–B4 ship first because they are *hours*, they unblock nothing and block
nothing, and they close the two before-cycle-2 items. **B6 is the expensive one and it should be
specified in writing (the three estimands, the horizon, the decision tree) before a line of it is
written** — under-specifying the decisive test is how KILL LINE 3 went wrong twice.

## 13.11 ⭐ WHAT IS PARKED, AND EXACTLY WHY — the panel has NOT converged on these

⚠ **"Parked" here means one of three things, and the reason is stated per row because they need
different treatment:** ⛔ **BLOCKED** (a fact makes it unanswerable today) · ⚠ **UNCONVERGED** (the
sources genuinely disagree, or one source is alone) · ⏸ **SEQUENCED** (agreed, but it cannot be
worth doing before B1–B8 return).

| item | who wants it | status | the actual reason, stated |
|---|---|---|---|
| **Does the HUMAN picker add or destroy value?** | ChatGPT §11 · Claude E3 · Deepseek R3 | ⛔ **BLOCKED** | ⭐ **All three are RIGHT that ρ = −0.018 licenses *"the deployed RANKING is uninformative"* and NOT *"the human is bad"* — those are different claims and the document merged them.** ⛔ **The measurement is impossible: `positions` = `orders` = 0, destroyed 2026-09-07, and the offered-set → selected-set mapping was never logged even when they existed.** ⇒ **B8 is the unblock, and it only starts the clock forward.** ⚠ **Until then, say "the ranking key carries no measured information" and stop there** |
| ⭐⭐ **"Point the apparatus at ALLOCATION instead of selection"** | Claude Part F (alone) | ⚠ **UNCONVERGED + ⏸ SEQUENCED** | ⭐ **Round 9's own measurement made this the sharpest strategic read on the table** — §12.31c found **gross α ≈ 0 (t −0.07)** on the tradeable book, so the selection layer is the part with no demonstrated value, while the basket is measured, significant and buyable in one order. ⛔ **It is nonetheless a NEW STRATEGY CLASS 50 days from the decision date, proposed by one source, with no other source having seen the α result.** ⇒ **Recorded as the answer to §14 Q5. Do not start building. Re-raise on 2026-10-31 as the successor question, not as a rescue** |
| **Hold period as the breadth lever (3-day holds)** | round-8 D2 · Kimi pushes back · ChatGPT §10 pushes back | ⚠ **UNCONVERGED** | ⭐ **Kimi and ChatGPT are both right that "more observations ≠ more information"** — shortening the hold changes μ, turnover cost, DP drag and the `w`-distribution together. ⭐ **And round 9 partly costed it: mean `T` is already 3.59, not 5, so the 109 obs/yr figure was understated by ~39% and the lever is smaller than D2 claimed.** ⇒ **B7's hazard curve decides it. Not before** |
| **A unified `ExecutionKernel` across research / backtest / paper / live** | ChatGPT §23 · Deepseek | ⏸ **SEQUENCED** | ✅ **Correct, and §12.21c already documents the four divergent experiments in one table.** ⛔ **It is weeks of work.** ⭐ **B2 and B3 close the only two divergences that change a recorded number; the rest are research-vs-production differences that are documented, bounded and not currently misleading anyone** |
| **Tax as its own P&L layer** | ChatGPT §24 (alone) | ⏸ **SEQUENCED** | ✅ Right in principle — tax is asymmetric, holding-period-dependent and portfolio-level, so burying it in "friction" is wrong. ⛔ **Immaterial at ₹1L and it changes no recorded number today.** ⇒ **a B8 schema field, not a build** |
| **PIT `UniverseSnapshot` (item 0a.3)** | ChatGPT §9/§25 · Deepseek | ⏸ **SEQUENCED into B8** | ✅ Still required, ⭐ **and round 9 gave it a second consumer: the paired basket inherits the same today's-liquidity bias** (§12.31c bound 2). ⚠ **That bias makes the measured α CONSERVATIVE, so it does not change any round-9 sign** — which is why it can wait for B8's schema rather than being a separate build |
| **Factor correlation matrix / effective factor count** | Deepseek R5 (alone) | ⏸ **SEQUENCED, and downgraded** | ⭐ **§12.32 answered most of it without the matrix**: four factors carry nearly every scoring event and two of the top three are EMA-derived, so effective dimensionality is plausibly 2–3. ⭐ **And §12.31e already showed no ranking key on the factor set carries information** ⇒ **the matrix would explain *why*, not *whether*. Queued behind B6** |
| **The turnover / IC frontier** (h × selection-rate grid) | Deepseek R6 (alone) | ⏸ **SEQUENCED** | ⭐ **Genuinely the right shape of question** — D3 established that a gated tail selector's transfer is `IC·σ_cs·E[z\|selected]` and that IC 0.02 is roughly break-even *per trade*, so the failure is annual and therefore about turnover. ⛔ **But every cell of that frontier is computed from an IC we have not measured yet.** ⇒ **it is a B6 follow-on, and it is the right one** |
| **Data-gap reconstruction costs** (2021–23 · CA · index · FII/DII) | Deepseek R8 | ⏸ **SEQUENCED, and one part now moot** | ⭐ **§12.32 removed the FII/DII item from the critical path** — the factor scores on **0 of 487** panels, so back-filling it changes no score. The 2021–23 back-fill is already **DROPPED** (D2). ⇒ **what remains is the CA table and the index history, and neither gates any round-9 conclusion** |
| **F&O to escape the cash-delivery short constraint** | Gemini (alone) | ⛔ **NOT NOW** | ⭐ The constraint is real and structural — **55.7% of generated signals are untradeable by construction.** ⛔ **But moving instrument class to rescue a book with zero measured gross α is the definition of chasing.** ⇒ **A successor question, behind the allocation one** |
| **An eighth/ninth review round** | — | ⛔ **CLOSED (§17c)** | **7 decision changes came from claims a probe could test; ~60 other points came from architecture already adopted, questions the document answers, or restatement.** **No reviewer can shorten B1–B8** |

⛔ **§13.8 BELOW IS SUPERSEDED BY §13.9 ABOVE** — E3 ran, two of its items closed by measurement, and E1/E2 were re-specified. Kept for the record.

## 13.8 ⭐⭐ THE PLAN AFTER ROUND 8 — three measurements, one build, and a decision date

⚠ **Round 8 shortened the plan rather than lengthening it, which is the first time that has
happened.** Two items were killed by measurement (the level-stage lever, the index-backfill gate),
one was killed by arithmetic (the 2021–23 back-fill, D2), and the decisive test was shown to be a
single query. **What follows is the whole plan.**

### The three measurements. All read-only, all afternoons, all decision-changing.

| # | test | why it is decisive | status |
|---|---|---|---|
| **E1** | ⭐⭐ **Re-report the POSITIONAL stop-width family in raw %, ATR units and net ₹, split by the gap flag** | **Three of the four surviving positive results share one denominator and the fourth is now FULLY explained by arithmetic** — the mechanical `1/w` term reproduces **116%** of the swing spread with return independent of `w` (§12.18f). If positional dies the same way, **§4.4, §12.1, §12.2, plan item 18 and the σ_R objective all close on one afternoon** | **NOT RUN** — needs `positional_probe.py`, same four units + gap flag + HC3/clustered SEs |
| **E2** | ⭐⭐ **Panel-level score IC at h=5d on the clean block, date-clustered** | **The only fully-powered test of the only question that changes direction.** ~790 clean sessions, SE(IC) ≈ 0.008 against a 0.018–0.071 break-even. It needs **no CA source, no index, no ledger, no holdout, no barriers and no R denominator.** ⚠ **Pre-register h = 5d** — at 20d it can only return INCONCLUSIVE. ⚠ **Report `sd(IC_t)` as an OUTPUT** — every power figure is linear in it and 0.10 is an assumption (§12.18f) | **NOT RUN — this is 3b, and it is the whole decision** |
| **E3** | ⭐ **The one cell the programme turns on, in ONE pass: `clean × BUY × w ≥ 2% × net-per-trade`** | Every number in this document is a corner of that cell and **it has never been computed in one pass.** Round 8 got to `BUY × net-per-trade` = **−0.2435R, t = −2.19** (§12.18g) but not clean, not reachable-restricted, and without the mean holding period the drift null needs | **PARTIAL** — the audit's F11 asks for exactly this |

### The one build worth doing regardless of outcome

**Week-0 #2 — the append-only ledger**, with ChatGPT's
`DecisionSnapshot → OrderIntent → Execution → PositionLifecycle → PerformanceRecord` chain. ⭐ **Not
because it helps this strategy** — it does not; `positions` = 0 and cycle 2 cannot test expectancy —
**but because it is the precondition for any successor, and it is the part of the apparatus that is
genuinely the asset.** Round 8's independent judgement matches §13c's from two rounds ago.

### ⛔ Dropped, with the reason

| dropped | reason |
|---|---|
| **the 2021-01 → 2023-06 back-fill** | D2: **hold period is a bigger breadth lever and costs nothing** — 9 slots × 3-day holds gives 298 effective obs/yr vs 109. Both §17 Q7-4's prior and the audit's recommendation agree |
| **the level-stage lever (item 2′)** | the effect did not survive the gap filter (R7-K) and the gradient is arithmetic (§12.18f). ⭐ Kept only as a **+223-trade sample-enlarger** |
| **the cap sweep (item 18)** | pending E1, which will probably kill its premise |
| **§16.3 item 3 — the index-backfill gate** | the null was computable from `ohlcv_1d` all along (§12.20) |
| **round 9** | §13g: **4 of 37 round-7 points and 3 of 29 round-8 points changed a decision.** The marginal value of review breadth is negative, and round 8 was only worth it because it *recomputed* rather than read |

### ⚠ Two BEFORE-cycle-2 repairs that change a recorded number

Under the governing rule (*anything that changes a recorded number lands before cycle 2's clock*):

1. ⭐ **`paper_tick_size` must be price-dependent** (§12.19). ₹0.05 is the wrong grid for sub-₹250
   names since 2024, and a ₹39 name is overcharged ~10 bps round trip — **0.064R at a 2% stop, on
   exactly the cheap-tight-stop cohort §12.1 and §7 are built on.** It is a published exchange
   schedule, not a model choice ⇒ **no forward-evidence bar** under §5.4. ⚠ Read the schedule from a
   table, not a constant: the measured phase-in (0.87 → 0.49 → 0.22 across 2023–25) suggests a staged
   rollout, so it is date-dependent as well as price-dependent.
2. ⭐ **The gap guard must test SPAN, not endpoints** (§12.23). `sessions_between(w0, w1) ≤ 300×(1+tol)`
   against the market's own session calendar catches the 922-day hole, the per-name holes (1.2% of
   panels today) and every future hole, **without hardcoding any of them** — which is W5's rule, and
   `GAP_LO`/`GAP_HI` violate it.

### And three items that are now *narrower* than they were

- **0a.3 (the universe)** — still required, and **ChatGPT's `UniverseSnapshot` is the right shape**:
  one as-of object consumed by every probe and backtest, not a SQL fix repeated in three scripts.
  ⚠ It also gates §12.20's drift null, whose basket currently inherits the same survivorship.
- **The two undeclared display filters** (`_near_expiry`, `_choppy` at ER < 0.30, both defaulting ON)
  — fold into `restrictions.py` with `enforced_by = DISPLAY` or delete. **`restrictions.py` is not
  currently the single source of truth its docstring claims** (§12.21b).
- **`nse_holidays` is incomplete for 2019–2020** (§12.22a) — 7 recorded against ≥17 that occurred.
  Only matters if the pre-gap block is ever used, which D2 says it should not be.

### ⭐ The decision, and what it will say

⭐ **On present evidence the 2026-10-31 verdict is not "we could not tell."** It is:

> **the posterior on the tradeable book sits within a few percent of zero under any realistic prior
> (0.4%–5.7%); the net-of-cost test on that book is significantly negative (t = −2.19 on explicit
> charges alone); the one remaining positive result family is fully explained by dividing by a small
> number; the scorer's ranking key carries no measured information (ρ = −0.018 on a test powered to
> 0.147) and IS the deployed picker's sort key; and the scorer's cross-sectional information content
> was tested at full power by E2 and returned X.**

⭐ **That is a programme reaching a conclusion, which is a different thing from a programme running
out of time.** And the apparatus — the provenance discipline, the self-correction ledger, the
sample-tag rule, the instrument self-validation rule — is the deliverable either way.

## 13.7 ⛔ THE PLAN AFTER ROUND 7 — SUPERSEDED BY §13.8 ABOVE; kept for the record

⚠ **The cut is not re-opened.** Round 7 produced 37 reviewer points; four changed a decision. What
follows swaps three items that round-7 measurement **killed or superseded** for three that it
**created**, and leaves the count at eight. `[git]` **Shipped since 2026-09-10: four commits, all
documentation. Of the nine cut items, ONE has shipped as code** — #10 (measure ρ̄), delivered by
`swing_dependence_probe.py` on 2026-09-11 and **still untracked.** ⛔ **50 days to the 2026-10-31
sunset.**

| # | item | round-7 status |
|---|---|---|
| 1 | **0a.1** freeze the holdout (two locks) | ✅ **UNCHANGED, still first, still un-started.** ⭐ **But downgraded from blocker to insurance** (R7-2): the base scorer is genuinely pre-registered against this corpus, so **3b can be read without it** |
| 2 | ~~**0a.6** un-truncate the corpus~~ → **BACK-FILL 2021-01 → 2023-06** | ⛔ **KILLED AS SPECIFIED** (§12.12). Un-truncation yields **0 additional panels** at a 300-bar window and n≈2,662 at bar-50, not 4,300. Re-specified as a **data-acquisition** task, and **DROPPED FROM THE CUT** pending Q7-4 — days of ingestion for more n on a population that does not transfer |
| **2′** | ~~simulate the level-stage rejects as the breadth lever~~ → **the level stage is CLOSED as a suspect; keep it only as a sample-enlarger** | ⛔ **DOWNGRADED THE SAME DAY IT WAS PROPOSED.** `--clean-only` ran (R7-K): the paired contrast falls **+0.16R → +0.09R (t 0.69)** and **REVERSES on the clean tradeable book** (rejects BUY −0.118R vs accepts −0.084R). ⭐ Claude's structural point stands — the largest filter in the pipeline is now measured — but **there is no anti-selectivity effect to chase.** What remains: **+223 simulable trades on clean data**, the cheapest sample-enlarger available, and **3b still needs its own endpoint** (§12.15) |
| **2″** | ⭐ **NEW, and it is what actually replaces item 2 — σ_R on `corpus-1975`, split by class and direction** | ⭐ **One flag on `entry_confirmation_study.py`.** σ on the corpus has NEVER been measured (1.489 is back-derived from a t), and R7-K's monotone ladder (**0.878 → 1.005** as the population is honestly restricted) is direct evidence the two samples differ structurally. **Everything in §12.10a and §16.1 that pairs a σ with n = 1,975 is waiting on it** |
| 3 | **0a.2** repair harness defect #4 + re-baseline | ✅ **UNCHANGED**, and the repair is now specified correctly: a **through-stop rejection at the fill bar**, mirroring `paper_broker:544-554` — **not** the gap-exit change Gemini proposed (R7-11). ⚠ frozen engine ⇒ sign-off + §8 regression + Rust fixtures in the same commit. **Frequency 1.08%**, so this is correctness, not magnitude |
| 4 | **0a.3** fix the universe selector | ⭐ **RAISED, and now covers THREE probes.** `swing_dependence_probe.py:46-49` inherited the defect. **Quantified: 46% of the 2021 top-250 is invisible to a today-ranked query** (R7-7) |
| **4′** | ⭐ **NEW — the gap guard** | ⭐ **SHIPPED with this round**: `GAP_LO/GAP_HI` + `--clean-only` in the probe. **Every study must declare which side of the hole its number comes from** (§12.12) |
| 5 | ~~Week 0 #1 CA layer~~ | ⚠ **still blocked (no CA event source), and DE-PRIORITISED.** R7-1 resolves the *modelling* question without it (the live side already CA-adjusts open positions R-preservingly; the backtest does not — a **parity defect with a written precedent**). R7-9 adds the `knowledge_time` columns to its schema when it is built |
| 6 | **Week 0 #2** append-only ledger + off-box export | ⭐ **RAISED TO FIRST AMONG BUILDS**, and given a schema: ChatGPT §12's `DecisionSnapshot → OrderIntent → Execution → PositionLifecycle → PerformanceRecord` (R7-8). `positions` = 0 · `orders` = 0 · `corporate_actions` = 0 · `cas_daily` = **43 rows / 1 session** |
| 7 | **Week 0 #6** the cost-feasibility table | ✅ **UNCHANGED.** Kills classes on arithmetic in an afternoon |
| 8 | **#16** in the repaired economic form | ⭐ **RE-SPECIFIED AS 3a + 3b** (§12.15). **3b's endpoint is Kimi Q8's**: gate-passers vs date-and-characteristic-matched eligible non-passers, in **bps and ATR units**, `newey_west_t(lag = horizon−1)`, CA-filtered, measured **before** the level stage |
| **8′** | ⭐ **NEW — `Σ notional ≤ available cash`** | ⭐ **the first new RAIL any of 25 reviews produced** (§12.14, ChatGPT §11). 3 slots at a 5% stop = **120% of capital**, unchecked. Enforces an identity ⇒ **exempt from the t≈3.6 bar** under §5.4, like the diversity and position-count rails. Belongs in Phase 7.1's RiskEngine as one more `*_reason` |
| 9 | **Week 0 #5** fee/slippage reconciliation | ⚠ **DEMOTED** (R7-3): the book is net-negative by **0.24R–0.32R at every point in the 10–30 bps range**, so slippage changes a **future** hurdle and **not the current verdict.** ⛔ Kimi Catch 5's "front of the plan" is **not adopted** |
| ~~10~~ | ~~measure ρ̄~~ | ✅ **DONE** — and **re-done**: mixed −0.013, **long-only ≈ +0.19** (R7-A2) |
| ~~11~~ | ~~measure the slippage residual~~ | ⛔ **IMPOSSIBLE, closed.** `orders` = 0 rows; only cycle 2 can produce it |

### ⭐ And one re-scope that round 7 forces on cycle 2

§12.14 establishes that a 6% heat cap + a 3-position cap + a 1.0× per-position notional cap still
admit **120% gross notional**. ⇒ **cycle 2's "heat-capped ₹1 lakh book" was under-specified and item
8′ is a precondition, not an enhancement.** Combined with the panel's round-1 finding that cycle 2
cannot test expectancy (§4.1) and R4-3's paired-calibration reframe, cycle 2's specification is now:
**an operational-correctness rehearsal that measures the corpus-to-live bias on paired trades, on a
book whose gross notional is actually feasible.** Nothing about edge.

### ⭐ Week 0a — DO THIS FIRST, before any Week-2 test is designed

**0a.6 — UN-TRUNCATE THE CORPUS FIRST (§12.5).** The swing corpus starts 2023-07-03 on a data
blocker resolved 2026-09-08 and a "CA-clean window" claim that is false. Rebuilding it over
2019-10 → 2026-09 takes n from **1,975 to ~4,300**, drops the corpus MDE from +0.067R to **+0.045R**,
and is the **precondition for 0a.1** — a 2024-01 holdout against the truncated corpus leaves six
months of development data. ⚠ Un-truncating spans the COVID crash and the 2020–21 melt-up, so it must
land together with the CA layer (Week 0 #1) and the regime split (Week 1 #13), not before them.

**0a.1 — FREEZE A HOLDOUT. This is now the binding problem** (Claude and ChatGPT, independently).
Every instrument in this plan handles multiplicity you can **count**: pre-registration, trial-count
deflation, day-block bootstrap. None handles the multiplicity you **cannot** count — 20+ hypotheses,
8 shadow gates, 2 promotions, 2 reversals, three rounds of reviewers, and **every corpus statistic in
this document computed on the same 2019–2026 window, by a gate that was itself fitted on that
window.** Deflation cannot deflate a trial count nobody recorded. ⇒ **Freeze 2024-01 onward NOW.**
Run every test in #14–#21 on 2019–2023 only. A survivor must **replicate out of sample** at a
pre-committed threshold. It costs ~35% of the data, and it is the difference between KILL LINE 3
meaning something and KILL LINE 3 being a ritual. It also supplies the branch the line was missing:
**marginal survivors in the t 2.6–3.5 dead zone go to the holdout, and only a holdout replication
promotes.**

**0a.2 — Repair harness defect #4 as a `FROZEN-CONTRACT` fix, and re-baseline** (Kimi). A
gap-through-stop booked as ~+1R is **exit-accounting correctness, not a hypothesis**, and it was
misfiled as a caveat. **Every Week-2 test except the IC runs through that same barrier-hit
accounting** — the cap sweep, both nulls, the hazard curves, the reachable-cohort statistics — so
nine "decisive tests" would run through an exit ledger known to be wrong *in the direction that
biases the very variable under study*. This violates the plan's own first principle (the argument
that moved CA above the ledger). Ship the repair with a parity regression on a golden set that
**includes a gap-through-stop day**, then re-baseline. ⚠ **§12.1's sign flip and §12.2's σ_R were
measured through the defective harness — directionally informative, but they must be re-run after
the fix.**

**0a.3 — Fix the universe selector** (§12.6). One query, in both probes: rank liquidity as of each
panel date, admit a name whenever it had bars then. Do not build the NSE symbol-master
reconstruction — the delisted names are already in `stocks`.

**0a.4 — Backfill the index and VIX history** (Kimi — a genuine omission I recorded as a doc
correction and then left out of the plan). `index_ohlcv_1d` holds 51 rows and `india_vix_daily` 17.
The permutation nulls (#15), the beta regression (Q1's control) and the whole "breadth from time"
escape all need NIFTY history. Public data, an afternoon.

**0a.5 — Every ledger row carries the engine commit hash and spec version** (Kimi). Otherwise the
append-only ledger still cannot attribute a result to a code+spec state.

> ⭐ **READINESS GATING, not calendar gating** (Kimi). Week 0 holds seven items for one operator by
> 09-18, and Week 0a adds five. If it slips, the risk is not a missed date — it is **Week-2 kill
> lines executed on contaminated or unrepaired data under deadline pressure**, which is precisely
> the mechanism (contaminated sweep → false prior) that round 2 had to cure. **Keep the kill-line
> DATES as decision points, but make execution conditional on a written readiness attestation**:
> adjusted plane verified · defect #4 repaired and golden-tested · universe selector fixed · index
> history present · null harness costed. **A kill line fired on unready data is worse than a
> postponed one — it produces confident wrong closure.**

### Week 0 — by 2026-09-18. Protect and instrument. Nothing downstream is valid without these.

1. **CA adjustment layer, bitemporal** (`event_time` / `knowledge_time`). An adjustment-factor table
   **plus event classification**, not adjusted prices (R2-14). ⭐ **Above the ledger** because it
   invalidates every Week-2 test: all are about barrier-hit frequency and an unadjusted CA is a fake
   barrier hit (R2-13). ⚠ **CORRECTED by round 3 (ChatGPT): the `>25%` rule and the ex-date exclusion
   must NOT become permanent core rules.** A >25% move can be a genuine takeover, demerger, earnings
   shock or regulatory event, and excluding every window containing an ex-date creates its own
   selection bias — **it drops exactly the moves a "multibagger" factor exists to catch, biasing the
   study against the strategy in the one place the strategy claims to work.** ⇒ demote `>25%` to an
   **ingestion ALARM**; the permanent rule is *every CA-induced discontinuity is explicitly classified
   and handled*, producing a `research_price` from point-in-time adjustment factors. Exclusion is a
   temporary safety measure only.
2. **Append-only trade ledger** + off-box nightly immutable export. `positions` currently holds
   0 rows; there is nothing to measure.
3. **Nightly snapshot of the OFFERED SET** — every presented candidate with its score and
   rank-at-presentation, written before the open (R2-9). Without it, cycle 2 produces another
   P&L that cannot be attributed between generator and picker.
4. **Restart CAS accrual and intraday capture today.** Both accrue only in real time and cannot
   be back-filled (R2-26 rejects deferring this).
5. **Reconcile the fee model to contract notes, daily** (R2-15).
6. **The cost-feasibility table** — minimum gross edge per trade to break even as a function of
   position size × holding period × stop width, at the real cost stack, filled for current
   swing, current positional, index/ETF and closing-auction reversal. An afternoon, and several
   cells will be visibly impossible.
7. The §6 corrections plus the round-2 corrections above.

> ~~**KILL LINE 1 (original).** Any class whose required gross edge exceeds +0.30R/trade is struck.~~
> ⛔ **SUPERSEDED by §12.5 and left stale in this checklist for a round — caught by Claude R4.**
> ✅ **KILL LINE 1 (repaired).** The threshold is **not a fixed number**; it is the per-class
> `friction(w) + MDE(effective n)` computed in §12.5's corrected table. A class is struck when its
> **required gross exceeds what a Sharpe-1.0 system delivers under the SAME dependence assumption**
> — currently **+0.125R at m=2.5, ρ̄=0.5** (ChatGPT R4: the benchmark must move when the hurdle
> moves). On today's numbers every equity class already fails this, which is the point.

### Week 1 — by 2026-09-25. Contract repairs and the free measurements.

8. **Split the freeze**: `FROZEN-BEHAVIOUR` (sign-off + regression + DSR bar + Rust fixtures) vs
   `FROZEN-CONTRACT` (code/spec divergence, no behavioural intent — parity regression + diff
   review, ship in a day). ⚠ **With Kimi's guard rail: removal may delete behaviour or restore
   the spec default; it may never select between two live behavioural variants** (R2-7).
9. **One `LevelPolicy`**: make `ema20_daily` **required**, delete the fallback, let the type
   checker enumerate the call sites. ⚠ **Preserve the spec-primary rule (EMA20).** Switching to
   flat-5% is a promotion, not a repair, and its evidence is t = −1.41.
10. **Enforce the validity horizon in the backtest**, apply the existing fee/fill model, **and
    apply the notional cap** — so the corpus contains only live-reachable trades (R2-3).
11. **Directional entry-zone alert**; and the parity regression must assert **entry-price**
    equality, not just level equality — the `_has_active_signal` latch means live and backtest
    currently price different trades (R2-15).
12. **Stamp SELL signals `tradeable=False`** and exclude them from every tradeable statistic and
    from the order path — keep generating them as evidence for a future futures short book
    (R2-25 refined by R2-24).
13. **Regime decomposition by calendar year** — one `GROUP BY` (R2-16).

> **KILL LINE 2 (2026-09-25):** if the year-by-year split shows the sign flipping by regime,
> every aggregate number in this document and both review docs is a mixture and must be
> re-reported per regime before any of it is cited again.

### Week 2–3 — by 2026-10-09. The decisive tests. All read-only, all pre-registered, none touching the freeze.

14. **Direction split** — re-report both corpora BUY/SELL (R1 §4.3).
15. **Both nulls**, run through the **identical harness and cost model** so every harness bias
    cancels in the comparison (round 3, Q3):
    **(a) shuffle entry dates within name** → tests **timing**;
    **(b) random eligible name within date** → tests **selection**.
    These are the two halves of "am I picking the wrong stock, or the wrong entry?"
    ⚠ **Round-3 refinements, both taken (ChatGPT):** (a) the random name must be drawn from the
    **same eligible universe after every non-alpha constraint** (liquid · tradable · price floor ·
    CA-clean · same segment), or the null is too easy to beat; (b) a uniformly shuffled date destroys
    real temporal structure (regime, earnings season, vol regime) — use **matched temporal
    permutation** (same name, same regime and vol bucket, nearby calendar, different signal date) or
    block permutation.
16. **Composite-score IC** on the **CA-adjusted, holdout-protected** panel — **ONE primary endpoint
    at ONE pre-chosen horizon**, definition frozen by commit hash; the 15 individual factors and the
    other horizons are labelled secondary and can neither fire nor forestall a kill line (round 3,
    Claude). ⚠ **DEMOTED from "the decisive test"** on two independent round-3 objections:
    **(a)** it answers the wrong question for a *gated* system — we trade the gate-passing **tail**
    (~2–4% selectivity), and a score can rank the full cross-section while the gate selects the wrong
    region of that ranking, or rank it flat while carrying real information in the top decile (Kimi);
    **(b)** IC is the wrong primary estimand for a **sparse event** signal, where conditional forward
    return, hit probability, excess return vs a matched control and `P(+1R before −1R)` are the
    natural tests — a near-zero IC can coexist with a valuable event strategy, and a significant IC
    can be economically useless after costs (ChatGPT). ⇒ **report three estimands:** full-universe
    IC · **IC within gate-passers (the tradeable question)** · Q5−Q1 spread among eligible names.
    ⭐ **And the evidence hierarchy is now: 1. conditional economic effect · 2. stability / OOS ·
    3. cost-adjusted expectancy · 4. IC.** Not "IC = ultimate truth."
17. **Re-run `factor_sweep` on the adjusted plane** (R2-2). This must precede any verdict on the
    ranker, in either direction.
18. **Pre-registered reachable-band cap sweep**: floor ∈ {2%}, cap ∈ {8, 12, 16, none},
    cost-bearing, on adjusted data. Grid and reporting rule committed **before** running.
19. **The σ_R / constant-R:R power test** (R2-4, R2-5) — a *power* decision, not an expectancy one.
20. **Hazard curves + MFE/MAE surface, by setup type** (R2-10, R2-12): `P(+1R before −1R | day d)`,
    median time-to-MFE and time-to-MAE, split breakout / pullback / reversal / continuation.
21. **Effective breadth** — from the correlation matrix, and ⚠ **not from correlation alone**
    (ChatGPT R4): add beta, sector and factor concentration, holding-period overlap and signal
    overlap; two names can show low unconditional correlation and highly correlated conditional
    **downside**. ⭐ And measure it on **P&L covariance under the actual sizing/stop/horizon**, not on
    raw asset-return correlation — that is the covariance that actually applies to you.
22. ⭐ **CAPITAL-TIME ECONOMICS — the objective this plan was missing** (ChatGPT, raised in ROUND 1
    and not actioned until now). The account does not earn R, **it earns ₹/day.** +0.20R × 20
    trades/yr loses to +0.07R × 400. Report per class: expected ₹ per deployed capital per day ·
    R/day · annualised return · turnover · capital utilisation · expected and maximum drawdown ·
    cost/yr. **Every other test reports into this**, rather than it being one test among many.
23. **The Q1 confounding control, moved forward to Week 1** (Claude R3): one regression of R on stop
    width with ATR%, log(price), log(ADV) and sector as covariates, HAC errors. Partial coefficient
    on `w` survives ⇒ a **stop** finding; ATR% absorbs it ⇒ a **volatility** finding. Closes the
    caveat §7 has carried unanswered for three rounds, and must run **before** any stop rule changes.
24. **Tail risk** (ChatGPT R4, absent from every prior version): CVaR / expected shortfall, the
    gap-loss distribution and maximum adverse gap. Daily bars plus a known gap-through-stop defect
    make this the exposure we are least instrumented for, and it feeds the sample-size arithmetic —
    mean +0.10R with a 99th-percentile −7R is a different instrument from the same mean at −2R.
25. **Simple benchmark strategies, not just placebo nulls** (ChatGPT R4): buy-and-hold the eligible
    universe · equal-weight · sector-neutral random · momentum · trend · simple breakout.
    ⭐ *A random strategy is a weak baseline; a simple robust one is a demanding baseline* — and a
    complex model should have to justify its complexity against the latter.
26. **Ablation, pre-registered** (ChatGPT R4): all / minus-A / minus-B …, asking whether each
    component adds incremental economic value. This is the direct test of the "indicator democracy"
    problem, and it must be staged and pre-committed or it becomes another unregistered search.

> ⛔ **KILL LINES 3, 4 and 6 AS FIRST WRITTEN WERE BROKEN. Round 3 (2026-09-11) audited them and
> all three defects are confirmed by arithmetic. The repaired versions are below; the originals are
> kept struck through, because the failure mode is instructive — I wrote a gate with the exact
> defect I had diagnosed in cycle 2 one section earlier.**
>
> ~~**KILL LINE 3 (original).** If no factor and not the composite has a 90% interval excluding
> zero at any horizon, the programme is closed permanently.~~
> ⛔ **Two independent defects.** (a) **It cannot fire.** #16 is 15 factors + the composite at five
> horizons = **80 intervals**; at 90% coverage `P(at least one exclusion | everything null)` =
> **0.9998**, with ~8 expected by chance. The most consequential gate in this document was a
> near-certain non-fire (Claude). (b) **If it did fire it would be unsound** — the document itself
> says power is ~0 between t 2.6 and 3.5, so a flat result is *absence of evidence, not evidence of
> absence*, and closing on it inverts the very error the programme exists to avoid (Kimi).
>
> ⚠ **THE REPAIR BELOW WAS ITSELF HALF-WRONG — corrected 2026-09-11 (round 4; Claude, Kimi and
> ChatGPT all flagged it independently, the clearest three-way convergence of the exercise).**
> **The line was keyed to IC four lines after #16 demoted IC to fourth in the evidence hierarchy.**
> Those cannot both be right. ✅ **The primary endpoint is now the top of that hierarchy: the
> COST-ADJUSTED MEAN R of gate-passing trades**, on the holdout-protected adjusted plane, with
> **SESOI = friction at the class's median stop width**. Everything is then in one unit, the margin
> is *derived* rather than picked, no IC-to-R transfer is needed, and the TOST reads plainly: *is net
> edge inside ±friction?* The three IC estimands remain, as **secondary** evidence.
>
> ⛔ **And the |IC| = 0.02 margin was set against ourselves.** The transfer for top-decile selection
> is `E[excess] ≈ IC × σ_cs × E[z|selected]`, E[z] ≈ 1.755. At σ_cs(5d) ≈ 5–7% and a 22–62 bps round
> trip, **break-even IC is 0.018 to 0.071** — so 0.02 sits at or below every break-even in the range.
> A true IC of 0.03, economically worthless at our cost stack, would have cleared it, been labelled a
> survivor, and burned a holdout cycle. ⚠ **Gemini's proposed replacement,
> `IC_min = cost_in_R / (breadth × σ_R)`, is rejected — it does not type-check** (the result carries
> units of 1/count) and returns 0.0006–0.0066, four to a hundred times too permissive. It conflates
> `IR = IC√BR` (portfolio level) with the IC-to-return transfer (per selection).
>
> ⭐ **Apply line 4's own principle to this line** (Claude R4): line 4 publishes the MDE per cell
> before running; the equivalence analogue is **publish the achievable SE against the chosen SESOI
> before running.** TOST establishes equivalence only if the 90% interval fits inside ±SESOI, i.e.
> `SE < SESOI/1.645`. At ~156 independent dates with per-date IC dispersion ≈ 0.10, SE ≈ 0.008
> against a required 0.0122 — **feasible, but it must be shown**, because a line that can only ever
> return INCONCLUSIVE is the original defect in mirror image.
>
> ⚠ **One-sided in practice** (Claude R4): a negative IC is informative but untradeable on a
> long-only cash book, so `|IC|` conflates *no information* with *information you cannot use*. State
> the direction, or the closure verdict overstates what was established.
>
> ⛔ **SUPERSEDED AGAIN BY ROUND 7 — see §12.15.** ChatGPT §7, Claude's Finding D and Kimi Q8
> converged from three unrelated directions on the same defect: **this line declares the death of
> the SCORER using an endpoint measured three stages downstream of it**, and one of those stages
> (the level stage, −60.8%) is independently measured at +0.16R *against* the trades it keeps.
> **§12.15 splits it into 3a (strategy closure) and 3b (feature-family closure).** The text below
> is 3a and is sound for what it measures; it may NOT be reported as the death of the feature family.
>
> ✅ **KILL LINE 3 (as repaired, superseded endpoint retained for the record) — an equivalence test
> on ONE pre-registered primary endpoint.** Original endpoint: the composite score at a single
> pre-chosen horizon, definition frozen by commit hash. The 15 individual factors and the other four horizons are **labelled secondary
> exploration and can neither fire nor forestall this line.** Decision by **TOST against a
> pre-specified smallest effect size of interest** (SESOI), set from the Week-0 cost table rather
> than picked — provisionally |IC| = 0.02, below which the edge is not monetisable at this cost
> stack anyway:
> · 90% interval lies **entirely inside** ±SESOI ⇒ irrelevance is **established** ⇒ **statistical
>   closure**, the feature family is dead everywhere.
> · interval **straddles** the margin ⇒ **INCONCLUSIVE.** Closure may then rest only on the
>   *economic* argument (cost floor, validatability, breadth) and must be labelled as such.
> · interval **excludes zero and exceeds SESOI** ⇒ survivor ⇒ **goes to the holdout** (§13a), and
>   only a holdout replication promotes it.
> ⭐ **Statistical closure and economic closure are different verdicts with different consequences**
> — economic closure preserves the strategy for a larger account; statistical closure kills the
> feature family. The document previously conflated them.
>
> ~~**KILL LINE 4 (original).** No cap-sweep cell showing gross > +0.15R *and* net > 0 with an
> interval excluding zero ⇒ delete the swing class.~~
> ⛔ **Unpassable by construction — §4.1's error one level down.** At the reachable positional
> cohort (n=271, σ_R=1.844) the **minimum detectable effect at t=2 is +0.224R**, so the conjunction
> silently requires ≥0.224R, not 0.15R. A *true* +0.15R effect yields **t = 1.34** and an interval
> containing zero. On the swing cells that actually carry the decision (n≈200–400) the MDE is
> **+0.149R to +0.211R** — at or above the threshold being tested.
>
> ✅ **KILL LINE 4 (repaired).** **Publish the MDE for every cell as part of the pre-registration,
> before the sweep runs.** Cells whose MDE exceeds the decision threshold are **decorative and must
> be labelled so.** The threshold itself is **derived per class from §12.5**, not chosen — and it is
> a **function of stop width**, since charges + slippage reach 0.4–0.8R below 2% (Kimi), so a uniform
> line is far too lenient exactly where it gets applied most.
>
> **KILL LINE 5 (2026-10-09) — the null line.** Unchanged, and round 3 strengthened its design:
> if the strategy does not beat **both** nulls (#15), there is neither a selection nor a timing edge.
> ⭐ **Round 3's answer to open question 3 supersedes the analytic-null debate entirely: run both
> permutation arms through the IDENTICAL harness with the IDENTICAL cost model, and every harness
> bias — the SL-before-TP conservatism and defect #4 alike — appears in both arms and cancels in the
> comparison.** Corollary, now a standing rule: **never compare a harness number to an analytic
> null again.**
>
> ~~**DECISION LINE 6 (original).** Adopt a constant-R:R target iff σ_R falls ≥15% and the paired
> ΔR interval includes zero.~~
> ⛔ **Optimises the wrong quantity and can adopt a rule that makes things worse.** A constant-R:R
> target lowers σ_R **mechanically**, by truncating the right tail — which is precisely where the
> wide-target winners live — and it lowers **μ** with it. If σ falls 20% while μ falls 25%, required
> n **rises**. The objective is required n = (σ/μ)², so a criterion on σ **alone** is unsound.
>
> ✅ **DECISION LINE 6 (repaired).** Adopt iff **required n falls** — i.e. the criterion is on
> **σ/|μ|**, or directly on n, computed paired on the same signal set. Report σ, μ, skew, kurtosis,
> tail contribution and serial correlation beside it (ChatGPT), because reducing σ helps only if the
> economic meaning of R has not been distorted in the process.

### Week 4 — 2026-10-16. Decide, against the lines above. Not one round later.

22. ⭐ **CYCLE 2 IS A PAIRED CALIBRATION MEASUREMENT — not merely a rehearsal** (Claude R4, the best
    idea of the round, and it *rescues* cycle 2 rather than downgrading it).
    **Power is the wrong axis on which to assign roles.** The corpus and the live book estimate
    *different quantities* — eight documented ways they differ — so **increasing n on a biased
    estimator converges on the bias with tighter error bars**, and §12.6 establishes one bias runs
    upward. Three roles, not two: **the corpus can REJECT but never PROMOTE** (enough power to
    falsify, too much bias to confirm) · **the live book can do neither** · **only the PAIR can
    measure the bias between them, and nothing else can.** That third role was unassigned.
    ⇒ For each of the ~25 trades, record **backtest-predicted R against realised R on the identical
    signal.** The *unpaired* test dies at n=25 because σ_R = 1.489; the *paired* difference shares
    signal, name, window and barrier geometry, so sd(ε) ≈ 0.2–0.3R ⇒ **SE ≈ 0.05R at n=25, enough to
    detect a systematic 0.10R corpus-to-live bias at t=2.** The power argument that kills the
    expectancy gate does not touch the calibration test. It also decomposes the 0.238R gap into
    cost-model error, composition, picker and fill quality — the original question.
    ⭐ **ACCEPTANCE CRITERIA (Kimi raised these in round 3; they appeared in the round-3 ledger as
    neither taken nor rejected — they dropped silently, which is exactly what the ledger exists to
    prevent. Recorded now):** fills within model + 2 bps on **≥95%** of orders · **100%** of cap
    rejections and daily-breaker firings logged with a reason · the entry-displacement distribution
    reported (intended vs actual, flagging any >0.33R cohort) · **every ledger row carries
    `signal_id` and the engine commit hash — an order lacking either counts as a rehearsal failure.**
    Without these, cycle 2 was the one phase exempt from the standing rule that a test which cannot
    fail is not a test.
23. **Only if #16 survives:** build the calibrated scorer (R2-19) as a **shadow parallel** — never
    a replacement — and hold it to the DSR bar.
24. **CAS**: pre-register the ≥30-session threshold **now** (day-clustered interval excluding
    zero, same trial-count deflation, **and net of the DP charge established in §12.3**). Assign
    it **zero** weight in the Week-4 decision until it re-earns one.

> ⭐ **Standing rule from R2-6, the one this document lacked: every phase ends in a kill line
> with a date. A test that cannot fail is not a test, and a programme with no pre-written
> answer to "what would make us stop" is a hobby.**

---

# PART IV — THE ROUND LEDGERS

## 10. LEDGER — round 2: taken, refined, rejected

Legend: ✅ taken · ⚠ refined or conditional · ❌ rejected. "mine" = derived this session while
verifying, not proposed by any reviewer.

| # | Claim | Source | Verdict | Evidence |
|---|---|---|---|---|
| R2-1 | "Three independent lines" on the cap is one variable measured twice — a flat target makes R:R = k/w an identity | Claude | ✅ **§4.4 corrected** | `[code]` `risk.py:101,111` flat 6%/15% ⇒ R:R = 6/w, 15/w. Swing R:R<1 ⟺ w>6%. The R:R-revert cohort's 7.29% stop **was** the wide-stop finding |
| R2-2 | `factor_sweep`'s flat verdict is itself CA-contaminated, so it cannot be the prior against the ranker | **Kimi** | ✅ **§3.1 corrected — sharpest catch of round 2** | `[code]` no CA filter anywhere in `factor_sweep.py`; features **and** labels on unadjusted prices; ~5.8% of 212,129 obs corrupted vs a target IC of 0.02–0.04 |
| R2-3 | The 0–2% bucket is not live-reachable — the notional cap already rejects w<2% | Claude | ✅ **taken and extended** | `[code]` cap unconditional in the paper broker; `[code]` backtest applies **no** cap ⇒ the corpus holds trades live refuses. Measured in §12.1 |
| R2-4 | Fixing the **unit** is cheaper than fixing the edge — required n scales with σ_R² | Claude | ✅ **best new idea in round 2** | `[corpus]` measured sd(R) and n@t2 in §12.2 |
| R2-5 | D5 closed constant-R targets on **expectancy**; nobody tested **validatability** — different objectives, one tested | mine (from R2-4) | ✅ **reopens D5 without contradicting it** | D5: every paired ΔR negative, \|t\| ≤ 0.65 ⇒ it costs ~nothing in expectancy. σ_R falls if R:R is constant |
| R2-6 | No kill criteria, no dates — endless optionality is how quant programmes die | **Kimi** | ✅ **the biggest gap in my §8** | 20+ hypotheses, 8 gates, 2 promotions, 2 reversals; the standing risk is no longer false positives, it is never stopping. §14 |
| R2-7 | The removal rule is a loophole: "remove the EMA20 stop" back-doors flat-5% on t = −1.41 | **Kimi** | ✅ **guard rail added** | `[corpus]` ΔR −0.116, t −1.41, interval includes zero. Guard: *removal may delete behaviour or restore the spec default; it may never select between two live variants* |
| R2-8 | Write the required-gross-edge kill line explicitly: friction ≈0.11R ⇒ candidates need > ~+0.15R gross | Kimi | ✅ taken | §14 line 4 |
| R2-9 | Snapshot the **offered set** nightly, not just orders — the human picker stage is uninstrumented | **Kimi** | ✅ **Week 0** | It is the direct answer to the original complaint ("sometimes I cannot select the right stock"). Without it cycle 2 yields another unattributable P&L |
| R2-10 | Hazard curves: `P(+1R before −1R \| day d)`, time-to-MFE/MAE — *"a 2–5 day strategy masquerading as a 30-day one"* | **ChatGPT** | ✅ **taken; sharpest single line in round 2** | Corroborated by our horizon finding (+1R typically on d+3; positional reaches 1R 54% within its own window). Sets the horizon empirically instead of by convention, and a shorter hold buys breadth |
| R2-11 | Effective breadth comes from the correlation matrix, not the position count | **ChatGPT** | ✅ **taken; worsens my §4.5** | Beta +0.92 ⇒ 20 trades in banks+NBFC+PSU are not 20 bets. Strengthens the "breadth from time, not names" escape |
| R2-12 | Decompose by **setup type** (breakout/pullback/reversal/continuation), each with its own MFE-MAE surface | ChatGPT | ✅ taken | Absent from my plan: I had direction split and stop-width buckets, no setup taxonomy |
| R2-13 | CA is load-bearing and I demoted it to a table row — it invalidates the direction split, the null **and** the cap sweep | Claude | ✅ **CA moves above the ledger** | All three tests are about barrier-hit frequency, and unadjusted CAs are fake barrier hits. A ≥40% halving is a guaranteed stop-out, so contamination lands in the tight buckets — the shape of §7's gradient |
| R2-14 | Kite's adjusted history is restated retroactively ⇒ adjusted closes are silent look-ahead; needs bitemporal `event_time`/`knowledge_time` | Claude | ✅ taken | Architecturally correct; adjusted *prices* are the wrong fix, an adjustment-factor table is the right one |
| R2-15 | The DP charge was absent on all 105 closed positions ⇒ −0.303R is itself understated, and the 0.238R gap has a **third** term (the cost model was wrong) | Claude | ✅ taken | In CLAUDE.md (A29) but never connected to the gap decomposition |
| R2-16 | Regime **decomposition** by calendar year — one `GROUP BY`, never done. Everyone asked for a regime *filter*; nobody asked for the split | Claude | ✅ **Week 1** | Window spans the COVID crash, the 2020–21 melt-up, 2022 chop and the 2023–24 small-cap mania. One mean R over that is a mixture of ≥4 distributions |
| R2-17 | This document now commits the sin the DSR bar exists to prevent — 5 buckets + 5 variants + a 4-point sweep, no trial count | Claude | ✅ **taken; sweep pre-registered** | Fair and self-implicating. §7's "the accidental rule beats the intended one" is a 5-cell search reporting its best cell at t = −1.41 |
| R2-18 | A permutation null (shuffle entry dates within name) beats "buy a random liquid name" | Claude | ⚠ **both, not either** | They test **different halves**: shuffle-date-within-name holds selection fixed and tests **timing**; random-name-within-date holds timing fixed and tests **selection**. Those are exactly the two halves of the original question, so run both |
| R2-19 | Replace `confidence` with a calibrated model (regularised logistic / monotone GBM, walk-forward by date block) | Claude | ⚠ **conditional** | It genuinely subsumes the denominator debate, the FII/DII dilution, the untested ADX schedule and the volume clamp — all become coefficients. But it needs the **CA-adjusted plane first**, must ship as a **shadow parallel scorer** (never a replacement), and must clear the DSR bar like anything else. Gated behind §14 line 2 |
| R2-20 | "Negative alpha" is over-claimed; −13.42pp vs NIFTY needs a time-in-market adjustment | Claude **+ ChatGPT** | ✅ **§4.2 softened** | Two independent arrivals — which should have *raised* its weight in my round-2 summary, and instead made ChatGPT's contribution invisible. Corrected |
| R2-21 | Under discrete daily monitoring the martingale null is **negative**, not zero | Claude | ✅ taken, **mechanism corrected** | `[code]` `engine.py:257-261` checks `hit_sl` **before** `hit_tp` on both-hit bars — deliberate conservatism, and the real mechanism. Claude's stated mechanism ("targets fill at the limit or better") is wrong for our engine: `engine.py:250-255` gaps *both* sides at the open |
| R2-22 | Zero log-drift ⇒ positive arithmetic drift; and drift favours **tight** stops (E[R]≈μT/w), the opposite of the observed gradient | Claude | ✅ **taken — and it argues FOR §4.4** | A drift artifact would have produced the opposite sign to the one measured |
| R2-23 | Credit assignment: the SELL finding and the ₹1L verdict were both in the panel | Claude | ✅ **§0 corrected** | Honest bookkeeping; it changes how much weight round 3 deserves |
| R2-24 | Shorts *are* tradeable in stock futures (~200 F&O names); at ₹1L lot sizes make most infeasible | Claude | ✅ taken | Stronger and more specific than "untradeable" |
| R2-25 | Disable SELL emission now, as an action | Kimi | ⚠ **refined** | Better: **keep generating, stamp `tradeable=False`**, exclude from every tradeable statistic and from the order path. Deleting them destroys the evidence base for a future futures short book (R2-24) |
| R2-26 | Hold off restarting CAS accrual until the cost table is computed | Claude | ❌ **rejected on asymmetry** | The accrual is a built Celery task at zero marginal cost; a missed session is **permanently** unrecoverable; the table takes an afternoon. Do both today and stop the accrual if the table kills it |
| R2-27 | The flat DP charge destroys the CAS escape: ~₹11,500/yr at 3 positions | Claude | ✅ **taken as a GO/NO-GO, not a verdict** | `[derived]` 1/2/3 positions × 250 sells × ₹15.34 = ₹3,835 / ₹7,670 / ₹11,505 = **3.8 / 7.7 / 11.5% of ₹1L per year**. `[code]` `fees.py:228-231` charges it on **every** delivery sell with **no BTST exemption**, so this is what *our model* would report. Whether Zerodha actually exempts BTST is one support ticket and it is the entire go/no-go |
| R2-28 | §7's median R = −1.000 in every bucket contradicts the 62.5% win in the 10%+ bucket | Kimi | ❌ **rejected — misread** | `[doc]` my §7 table shows median **+1.084** for that bucket. The −1.000 seen is the corpus-wide median quoted in `PHASES.md`. Right instinct, wrong row — and exactly the check worth running |
| R2-29 | Deprecate TA confluence for a 4-factor orthogonal model | Gemini | ❌ **rejected for now** | A rebuild recommendation with no measurement attached, and it presumes the ranker conclusion that **R2-2 just reopened** rather than settled |
| R2-30 | Regime **cube** (market × sector × setup × vol × RS) | ChatGPT | ⚠ **deferred** | A fishing expedition with no trial-count control — what the DSR bar exists to stop. R2-16's calendar-year split first; the cube earns its place only if the year split shows instability |
| R2-31 | Don't decide keep/kill positional yet | **ChatGPT** | ✅ **taken, and vindicated by measurement** | Round-1 Claude said "delete it now." §12.1 shows the reachable cohort reads **+0.084R gross**, so deletion would have removed a positive-gross cohort. ⚠ But §12.2 shows positional needs ~2× the trades to validate — an argument against the **relabel** owing nothing to expectancy |
| R2-32 | The four-experiment attribution ladder (Selection × Setup × Entry × Exit) | ChatGPT | ⚠ **partly new** | A = the composite-score IC (already queued); D = partly D5; **B (setup taxonomy) and the MFE/MAE surface are new** and are now Week 2 #20 |
| R2-33 | Harness defect #4 (gap-through-stop booked as ~+1R) **flatters tight stops** ⇒ the true stop-width gradient is steeper than measured | **mine** | ✅ new | Tight stops gap through more often, so −0.306R for w<2% is an **upper bound** on its real performance. Strengthens the direction, weakens the magnitude further |
| R2-34 | Swing's live-reachable stop band is **[2%, 8%]** — floored by the notional-cap identity, truncated by the class cap | **mine** | ✅ new | `[doc]` swing pivot p50 4.91%, p90 **16.17%**, **34.4% beyond the 8% cap**. The positional gradient's best cohort is >10%, which swing **structurally cannot reach** |
| R2-35 | Positional σ_R ≈ 1.84–2.09 vs swing 1.489 ⇒ positional needs **~2× the trades** to validate | **mine** | ✅ new | (2.09/1.489)² = 1.97×. A power argument against the positional relabel that is independent of expectancy |

## 11. LEDGER — round 2: sources ranked

- **Claude** — the most defects found in *this* document (R2-1, R2-3, R2-4, R2-17, R2-20, R2-21, R2-23). R2-4 is the best single idea of either round.
- **Kimi** — the single most important catch (R2-2: my own counter-evidence carries the disease I diagnosed in everyone else's) plus the biggest structural gap (R2-6: no kill lines).
- **ChatGPT** — the most genuinely new *research designs* (R2-10 hazard curves, R2-11 effective breadth). ⚠ Under-credited in my first round-2 summary because two of its points arrived independently with Claude's and I attributed them to Claude alone — the opposite of what independent corroboration should do.
- **Gemini** — one unmeasured rebuild recommendation (R2-29), which presumes a conclusion round 2 reopened.

---

## 13b. LEDGER — round 3: what was refined, rejected and answered

Three sources this round (Gemini returned nothing). **Round 3 was the strongest of the three because
it audited THIS DOCUMENT'S STATISTICS rather than the system's** — and it found that the kill lines,
the headline improvement of round 2, were broken in three independent ways.

**Taken and acted on above:** the three kill-line repairs · the holdout (0a.1) · defect #4 as a
contract repair (0a.2) · the universe-selector fix (0a.3) · index backfill (0a.4) · commit hash on
ledger rows (0a.5) · readiness gating · the required-gross-edge synthesis (§12.5) · effective-n
propagation (§12.5) · the CA-rule softening · both null refinements · the IC demotion and its three
estimands · capital-time economics · the Q1 regression moved to Week 1.

**Refined rather than taken:**

| claim | source | why refined |
|---|---|---|
| σ_R = 1.489 is backed out of a t that may be HAC/clustered, so it **overstates** σ | Claude | ⚠ **Premise wrong, conclusion right, direction inverted.** `[code]` every corpus t in our scripts is `mean / (sd/√n)` — a **plain iid t** — so the back-out is arithmetically valid. But an iid t on a series with **concurrent correlated positions is inflated in magnitude**, which means the required-n figures derived from it are **UNDERSTATED**, not overstated (§12.5's inflation table). Measure `stddev(R)` directly anyway; the reason is dependence, not the estimator. |
| Reconstruct a point-in-time universe from the NSE symbol master | Kimi, ChatGPT | Not needed — §12.6. The delisted names are already in `stocks` (2,070 inactive, 542 dead series). One query, not a data project. |
| Merge the corpora to buy power (open Q6) | Kimi | ⚠ **Claude is right against Kimi here:** pooling populations with different σ (1.489 vs 1.844–2.088), horizons and targets **inflates** pooled σ and can *lower* power. ⇒ **Resolution: delete the positional RELABEL, don't pool two rule sets.** Its panels then trade under one swing rule set with the cap raised — power by deletion, which is also what the asymmetric-burden rule already licenses. |
| Calendar-year regime split is too crude | ChatGPT | Kept as the **cheap first diagnostic** (it is one `GROUP BY`), but KILL LINE 2 becomes **interval-based, not sign-based** (Kimi — with ~6 years and modest n per cell, "the sign flipped" will sometimes be noise), and a **regime-interaction test** is added after it. Still no cube. |
| "₹1 lakh is not a validatable strategy class" is too strong | ChatGPT | ✅ **Softened, and the sequence corrected.** The honest claim is *validation at ₹1L is extremely slow*; the constraint is **execution-economic, not fundamentally statistical.** You can validate at scale-free units (notional-normalised returns, fractional sizing, portfolio simulation, longer history) and **then** ask whether the validated edge survives ₹1L friction. That ordering matters and §5.2 had it collapsed. |
| Escape 1 (index/ETF) gives "~750 observations instead of 25 trades" | Claude | ⚠ **My §5.2 conflated observations with BETS.** In `IR ≈ IC × √BR`, BR is independent **decisions**; a trend or vol-target overlay on one index makes perhaps 10–30 a year no matter how many daily bars exist. What index/ETF actually buys is **cost economics** and **estimation efficiency** — real, but not breadth. **Breadth requires cross-section: escape 2 or nothing.** ⇒ the escapes reorder, and **the DP/BTST go/no-go in §12.3 becomes the single most decision-relevant item in the plan** — one support ticket. |

**Rejected:**

| claim | source | why |
|---|---|---|
| The `>25%` filter and ex-date exclusion as permanent rules | (my own Week-0 #1) | Self-rejected on ChatGPT's argument — see the corrected Week-0 #1. |
| Deprecate confluence for a 4-factor orthogonal model | Gemini (r2) | Still unmeasured, and still presumes what R2-2 reopened. Gemini returned nothing in round 3. |

**Answers to the round-2 open questions, settled rather than deferred:**

- **Q1 (is the reachable flip an artifact?)** **Not survivorship** — the cap is a *deterministic
  function* of `w`, so restricting to `w ≥ 2%` is a **domain restriction, not a selected sample**. The
  live risk is **confounding**, and the control is one regression → moved to Week 1 (#23).
- **Q2 (is the σ_R comparison paired?)** Yes, on the same signal set — but that is not the objection
  that bites. Pair on **required n**, not σ. See the repaired DECISION LINE 6.
- **Q3 (what is the correct null?)** ⭐ **Stop formulating it analytically.** The three competing
  formulations exist *because* the harness has offsetting biases no closed form captures. Run both
  permutation arms through the identical harness and cost model; the biases cancel in the comparison.
  **Standing rule: never compare a harness number to an analytic null.**
- **Q4 (is "breadth from time" available at ₹1L?)** **No — it is not breadth.** See the escape-1 row
  above. It buys cost and estimation efficiency, not independent bets.
- **Q6 (keep the `classification` dimension?)** **No.** Delete the relabel — not by merging two rule
  sets, but by dropping positional's levels/horizon rules (R2-35: it needs ~2× the trades; §9.6: the
  relabel is unsupported either way). ⭐ And the architectural principle behind it (ChatGPT):
  **classification must be an OUTPUT of evidence, never a CAUSE of different behaviour.**
- **Q5 (if KILL LINE 3 fires, what survives?)** Still open, and now the sharpest question in the
  programme. Carried to §14.

## 13c. ⛔ THE META-VERDICT — and the recommendation that follows from it

Round 3's closing observation is the most important sentence produced across all three rounds, and it
is aimed precisely at this document:

> *"Two rounds, five reviewers each, an 800-line adjudication, and a nine-test plan with six kill
> lines. Zero Week-0 items shipped. The document has become the work. The failure mode from here is
> not a bad test. It is a round 3."*

Round 3 happened, and it paid for itself — but **only because it audited the plan's own statistics.**
It found three broken kill lines, a look-ahead in my universe selector and the required-gross-edge
synthesis. A round 4 has nothing comparable left to find, because what remains unexamined is no longer
the document — **it is the data plane, and no reviewer can inspect that from prose.**

⭐ **RECOMMENDATION: stop the review cycle here.** The next artifact should be a shipped Week-0a/0
item, not another review. Concretely, in order: freeze the holdout · repair defect #4 · fix the
universe query · publish the required-gross-edge table (§12.5) · then run test #16 as a single
pre-registered primary endpoint on holdout-protected, adjusted data. On §12.5's arithmetic the likely
outcome is that KILL LINE 3 fires cleanly — **and that is a perfectly good result for a research
programme to reach.** Kimi's R2-6 diagnosis applies to the adjudication process itself: a programme
with no pre-written answer to "what would make us stop" is a hobby, and that now includes stopping
the reviewing.

## 13d. LEDGER — round 4: four sources, reviewed one at a time

⚠ **Process change, at the user's instruction:** rounds 1–3 were adjudicated in bulk and ChatGPT was
under-credited **twice** as a result — when two sources reach the same conclusion independently I had
been crediting the more forceful one. Round 4 was read **one source at a time, completed, then the
next.** ChatGPT round 1 was also re-read from scratch.

### What re-reading ChatGPT round 1 turned up

Two items that later rounds rediscovered and credited elsewhere:

- ⭐ **The σ_R lever originated with ChatGPT in round 1**, swing §10: *"You correctly normalize
  everything to R. But R = entry − stop. So if the stop is arbitrary, your R is arbitrary too."*
  Claude formalised it in round 3 with the σ_R² scaling and got the credit in §10. **The mechanism
  was stated eight days earlier.**
- ⭐ **The capital-scaling question**, swing §12: *"Your strategy may be much more viable at ₹5L /
  ₹10L / ₹25L — but that needs to be quantified rather than assumed."* Round 4's Kimi calls the
  capital decision "the real Week-4 decision" and ChatGPT R4 restates it as capacity modelling. **It
  was on the table from the first review and never actioned.** Now Week-4's pre-written branch.

Six smaller round-1 items never picked up, all still live: a **family-decomposed evidence panel**
replacing the `confidence` label · **Direction / Setup / Timing as three separate scores** that gate
the decision (the *decision-time* counterpart to the selection/timing nulls, which only measure) · an
**entry state machine** with explicit setup-invalidation · a **"no trade if the gap exceeds X ATR"**
filter, never tested · the **23-field permanent-ledger spec** (more complete than my offered-set
spec) · **"correlation with existing book"** as a per-candidate field.

### Round-4 scoreboard

| # | claim | source | verdict | evidence |
|---|---|---|---|---|
| R4-1 | The corpus rows in §12.5 use nominal n; the corpus is **more** overlapped (m≈12) than the live book | **Claude** | ✅ **§12.5 corrected — same failure as R2-11, twice** | corpus advantage 3.4× → **1.7×**; required gross +0.28R / +0.23R / +0.31R |
| R4-2 | The Sharpe benchmark is also computed under independence and must move with the hurdle | **ChatGPT** | ✅ **taken — a real internal inconsistency** | +0.094R → **+0.125R** at m=2.5; ratio 2.80× → **2.52×** |
| R4-3 | ⭐ **Cycle 2 is a PAIRED CALIBRATION measurement**, and only the corpus/live pair can measure the bias between them | **Claude** | ✅ **best idea of the round — it rescues cycle 2** | paired sd(ε) ≈ 0.2–0.3R ⇒ SE ≈ 0.05R at n=25 ⇒ detects a 0.10R bias at t=2 |
| R4-4 | ⭐ *"Regardless of their outcome"* — only friction, σ_R and breadth can move the answer | **Claude** | ✅ **taken; the plan is reorganised around the three inputs** | required +0.23–0.31R vs a +0.125R benchmark |
| R4-5 | The plan is 3–4× over capacity; gating an over-capacity plan yields slippage, not protection | **Claude** | ✅ **CUT TO EIGHT** | 29 items → 8 + two afternoons |
| R4-6 | KILL LINE 3 keys to IC four lines after #16 demotes IC | **Claude + Kimi + ChatGPT** | ✅ **re-keyed to cost-adjusted mean R; SESOI = friction** | clearest 3-way convergence of the exercise |
| R4-7 | |IC| = 0.02 is at or below break-even | **all three** | ✅ **taken** | transfer `IC × σ_cs × E[z]`, E[z]=1.755 ⇒ break-even **0.018–0.071** |
| R4-8 | Apply line 4's MDE principle to line 3: publish the achievable SE against the SESOI first | **Claude** | ✅ taken | SE ≈ 0.008 vs required <0.0122 — feasible, but must be shown |
| R4-9 | `corporate_actions` may lack 2019–23 events | **Kimi** | ✅ **CONFIRMED, worse — 0 rows for ANY period** | §12.7; 0a.6 gated behind sourcing it |
| R4-10 | #16 may be infeasible — the composite needs FII/DII + sector | **Kimi** | ✅ **CONFIRMED, worse — infeasible on ANY window** | `fii_dii_daily` = 4 rows / 3 days; price-only variant now mandatory |
| R4-11 | The BTST ticket is unscheduled despite being called the most decision-relevant item | **Kimi** | ✅ confirmed | 4 mentions, no week owned it → **Week 0 #8** |
| R4-12 | Cycle-2 acceptance criteria dropped silently from the round-3 ledger | **Kimi** | ✅ **confirmed — my process failure** | zero hits in §13b; now recorded with criteria |
| R4-13 | The holdout sterilises the test **run**, not the test **choice** | **Kimi** | ✅ taken | ⇒ weight holdout **failures heavily, successes lightly** |
| R4-14 | Two locks: holdout (2024+) **and** a prospective test (2026+) | **ChatGPT** | ✅ taken | *"a holdout becomes validation the moment you use it"* |
| R4-15 | IC within gate-passers is a **collider** — separate marginal / conditional / **incremental** | **ChatGPT** | ✅ taken | the gate depends on the factors; #16 conflated all three |
| R4-16 | Three-layer nulls; my "never use an analytic null" was too absolute | **ChatGPT** | ✅ **self-rejected** | the missing layer is the **engine-calibrated** null |
| R4-17 | **Feature lineage table** — deflation only works if you know what trials occurred | **ChatGPT** | ✅ taken | origin · hypothesis · date · search history · holdout eligibility |
| R4-18 | **Simple benchmarks**, not just random placebos | **ChatGPT** | ✅ taken | *a random strategy is a weak baseline* |
| R4-19 | **CVaR / gap-loss tails**, absent entirely | **ChatGPT** | ✅ taken | aimed at our known gap-through-stop weakness |
| R4-20 | **Capacity across ₹1L → ₹1cr** | **ChatGPT** (R1 **and** R4) | ✅ taken | the Week-4 capital branch |
| R4-21 | Keep the horizon **descriptor**, delete only the **rule set** | **ChatGPT** | ✅ **refines my R3 "delete the relabel"** | consistent with classification-as-output |
| R4-22 | `fees.py` needs cost-stack bitemporality for pre-2023 | **Claude** | ⚠ **half already shipped (A23)** | `effective_from` + `schedule_for` exist; `SCHEDULE_HISTORY` has **1 entry**. Tradeability half has no mechanism |
| R4-23 | Un-truncation: pre-check σ(early)/σ(late) < √2, and stratify by regime **from the outset** | **Claude** | ✅ taken | converts an open question into one query |
| R4-24 | High power on a heterogeneous mixture **hides factor decay** | **Gemini** | ✅ taken — its one contribution | distinct from the estimand argument |
| R4-25 | Block-bootstrap SE ≈ 2× iid ⇒ corpus MDE optimistic 3–4× | **Kimi** | ❌ **arithmetic rejected**, ✅ **conclusion upheld via Claude** | ratio **1.046×**; but m≈12 gives the same answer — see §15.2 |
| R4-26 | `IC_min = cost / (breadth × σ_R)` | **Gemini** | ❌ rejected — does not type-check | §15.2 |
| R4-27 | Pivot to ETF/Index where flat DP charges don't bite | **Gemini** | ❌ rejected on two counts | §15.3 |

### Source assessment after four rounds

- **Claude** — the arithmetic auditor, and the only reviewer who has twice caught me failing to
  propagate a correction I had already accepted. Signature: *recompute the claim.* Ceiling: it checks
  work more often than it reframes the problem — though R4-3 (paired calibration) is a genuine reframe.
- **Kimi** — the governance conscience; asks *does this document obey its own rules*, and has been
  right every round it asked. This round: wrong arithmetic, right conclusion, and **two data
  questions that blocked the plan**. Dismissing it on the arithmetic alone would have cost real work.
- **ChatGPT** — the best estimand thinker, and **under-credited by me twice**. Two of its round-1
  points were rediscovered by others in rounds 3–4. Signature: *you are measuring the wrong quantity.*
- **Gemini** — four rounds, one usable contribution, one unsound formula, one factually wrong pivot
  recommendation, one inaccurate self-credit. Both other reviewers recommended dropping it and the
  record supports that. If retained, treat its formulas as hypotheses to verify, never as results.

## 13e. LEDGER — round 5: the headline inverted

| # | claim | source | verdict | evidence |
|---|---|---|---|---|
| R5-1 | ⭐ **The headline ratio compares GROSS required against NET benchmark** | **Claude** | ✅ **§12.8 — the conclusion INVERTS** | consistent gross-vs-gross: Sharpe-1.0 detectable at **×1.11–×1.63**, not 2.8–3.8× short |
| R5-2 | Half the friction term is an unmeasured slippage assumption; put Week 0 #5 back | **Claude** | ✅ **§12.8b — restored to the cut** | real fee model gives **0.051R** at a 5% stop against the 0.11R the document uses |
| R5-3 | The σ_R lever is weaker than §12.2 implies — the benchmark scales with σ_R too | **Claude** | ✅ taken | gap narrows 0.028R → 0.021R, ~¼ of the claimed improvement |
| R5-4 | ⭐ **The CA blocker is an afternoon: derive factors from Kite-adjusted ÷ our unadjusted** | **Claude** | ✅ **unblocks the critical path** | the step in the ratio **is** the factor, on the exact ex-date, as actually applied. ~1,300 names ≈ 1 request each at 3 req/s ≈ **7 minutes**. Strictly better than an event feed — no reconciliation needed |
| R5-5 | FII/DII is a scraping afternoon, not a procurement project | **Claude** | ✅ taken | NSE publishes daily historical cash-segment files ⇒ #16 may run on the **shipped** composite, not a price-only variant |
| R5-6 | ⭐ **KILL LINE 1 as repaired is "a conclusion wearing a gate's clothing"** | **Claude** | ✅ **re-scoped** | a gate you already know fires on everything is not a decision rule. ⇒ **comparative, not absolute**: lowest required gross among the classes in the cost table wins the next quarter; classes above 2× the leader are struck |
| R5-7 | ⭐ **0a.1 (freeze the holdout) costs nothing and depends on nothing — un-gate it** | **Kimi** | ✅ **sequencing inverted** | freezing a *date* is a commitment device, not a test run. The 6-month dev problem constrains *running* tests, not *freezing*. **Do it today**; un-truncation only enlarges the dev side later |
| R5-8 | ⭐ **No programme sunset** — every phase has a kill line, the programme doesn't | **Kimi** | ✅ **taken** | **if zero Week-0 items ship by 2026-10-31, the programme CLOSES** (not pauses) with the ledger archived as the deliverable. The standing rule had a hole exactly where it mattered most |
| R5-9 | The holdout can be confounded by regime mismatch — pre-commit the guard | **Kimi** | ✅ taken | dev spans COVID+melt-up+chop, holdout is a trending bull. **If KILL LINE 2 fires, the holdout verdict must be regime-matched or recorded as CONFOUNDED, not negative** — written before the first test, not after a failure |
| R5-10 | Capital changes the *executable* universe (integer lots, minimum quantities, feasibility) | **ChatGPT** | ✅ taken | selection itself becomes capital-dependent; belongs in the §12.9 ladder |
| R5-11 | Capacity is a **curve with an optimum**, not a ceiling — fixed costs dominate low, impact dominates high | **ChatGPT** | ✅ taken | ⚠ our participation model says impact is immaterial at ≤₹3L, so the knee is well above the range in question |
| R5-12 | Don't let economic closure become too aggressive — require *no viable capital regime* too | **ChatGPT** | ✅ taken | reinforced by §12.8: the margin is now positive, so absolute closure is premature |
| R5-13 | **Still not one picture in 1,443 lines** | **Claude** | ✅ taken | cumulative R of gate-passers vs the matched-random null, cost drag shaded, one line per year. Ten minutes of matplotlib, and it shows concentration in *time* and in *trades* — the two things summary statistics hide |
| R5-14 | ⚠ **§15 is an advance with a hazard**: the document becomes harder to attack each round while the data plane stays empty | **Claude** | ✅ **recorded as a standing caution** | the counter-measure is the one the document keeps recommending and not taking: **ship something** |
| R5-15 | DP drag is 11.5% → 3.8% of capital as you scale ₹1L → ₹3L | **ChatGPT** | ❌ **misapplied** | those are the **CAS/daily-turnover** figures. For the swing book at 5-day holds it is **2.30% → 0.77%** (§12.9). Claude had it right |
| R5-16 | Tripling capital buys ~6% more effective breadth | **Kimi** | ❌ **too low** | measured **+20%** (75 → 90 effective obs/yr) |
| R5-17 | Tripling capital buys ~33% more effective breadth | **Claude** | ⚠ **too high** | measured **+20%** |
| R5-18 | Higher power on a heterogeneous mixture hides factor decay | **Gemini** | ✅ already taken (R4-24) | its only contribution across five rounds |

### Source assessment after five rounds

- **Claude** — the arithmetic auditor, and this round it overturned the document's central claim by
  spotting a units error nobody else saw in five rounds. R5-4 (deriving CA factors from the ratio of
  adjusted to unadjusted series) is also the single most practically valuable idea anyone has
  contributed: it converts the plan's critical-path blocker from a procurement project into seven
  minutes of API calls. ⚠ Its own arithmetic is not infallible (R5-17), so verify it too.
- **ChatGPT** — the estimand thinker; R4-15 (IC-within-gate-passers is a collider) remains the best
  single statistical contribution of the whole exercise, and both other reviewers said so
  independently this round. ⚠ Weaker on arithmetic: R5-15 misapplied the CAS figures to the swing
  book, and R4-2 was the right instinct carrying the gross/net error that R5-1 then had to fix.
- **Kimi** — the governance conscience, and the only reviewer who consistently asks *what stops this*.
  R5-7 (un-gate the holdout freeze) and R5-8 (programme sunset) are both process fixes no one else
  proposed, and the sunset clause is the logical completion of its own round-2 kill-line argument.
  ⚠ Arithmetic unreliable a second time (R5-16).
- **Gemini** — five rounds, one contribution. Every other reviewer has now recommended dropping it.

⭐ **The transferable pattern across five rounds:** the reviewers who paid asked **"what quantity are
you measuring?"** (ChatGPT) and **"does the data actually exist?"** (Kimi) and **"recompute that"**
(Claude). The one that didn't kept proposing architecture. If there is ever another round, prompt for
those three questions and nothing else.

## 13f. LEDGER — round 7: four sources, read line by line

Legend: ✅ taken · ⚠ refined or conditional · ⛔ rejected · ⭐ best of the round.
**Method: every claim was checked against code, a query, or arithmetic before adjudication. Nothing
was taken on a reviewer's word and nothing on this document's own word (W1).**

### Round-7 scoreboard

| source | landed | of which measured true | refuted | best contribution |
|---|---:|---:|---:|---|
| **Claude** | 11 | 8 | 2 | ⭐⭐ **Finding D — the level stage is an unevaluated selector** (R7-C). ⚠ **Its EFFECT was then refuted by the gap filter** (R7-K), but the structural point — the largest filter in the pipeline had never been measured, and now is — is still the most valuable contribution of any round since R5-4 |
| **Kimi** | 9 | 7 | 2 | ⭐⭐ **Catch 1 — ρ̄ never propagated into §12.9** (§12.13a), plus the ρ̄=+0.2 **stress case that turned out to be the real case** (R7-A2) |
| **ChatGPT** | 12 | 8 | 1 | ⭐ **§7 — a kill line cannot close a feature family from total strategy R** (§12.15), and **§11 — no portfolio cash constraint exists** (§12.14) |
| **Gemini** | 5 | 1 | 3 | ⭐ **item 4 — control the stop-width gradient for ATR%** (R7-J). Its first runnable contribution since R4-24, and it produced a partial refutation of one of our own findings |

### The convergences, and why they matter more than the individual catches

| what | who | outcome |
|---|---|---|
| **split the headline by direction** | **all four**, independently, all leading with it | ⭐⭐ **RAN. It inverts the headline** (R7-A): BUY-only t = −0.94 |
| **Δ_select needs a continuous estimator** | Claude C · ChatGPT §5 · Kimi | ✅ **RAN.** Properly powered now; same sign, ρ = −0.018 |
| **Kelly needs the empirical distribution** | Claude · ChatGPT §9 · Kimi 6 | ✅ **RAN.** f\* = 0.0000; conclusion hardens (R7-E) |
| **a kill line keyed to the wrong stage** | ChatGPT §7 · Claude D · Kimi Q8 | ⭐⭐ **three routes, one repair** — KILL LINE 3 split into 3a/3b (§12.15) |
| **the universe query is still not point-in-time** | all four | ✅ **quantified for the first time: 46% of the 2021 universe is invisible** (R7-7) |
| **one kernel / one call contract** | Claude · ChatGPT §17 | ✅ adopted as a design item, with the frozen-engine caveat (§12.17 R7-8) |
| **σ from one sample, n from another** | Claude A · Kimi 3 | ✅ **confirmed** (§12.13b) — ⚠ **and Kimi committed it while diagnosing it** (below) |

### ⚠ Where each reviewer's own arithmetic slipped — with the derivation, per §15.4.3

**Kimi — committed Claude's Finding A while diagnosing Kimi Catch 2.** Catch 2 closes:
*"applied to the corpus itself (mean −0.065R, σ=0.878), t ≈ −3.3 — the negative-edge conclusion
likely strengthens at stride 1."* That is σ from the **probe** with n and the mean from the
**corpus** — the exact pairing Claude's Finding A condemns four paragraphs earlier in the same round.
Worked: `−0.065 / (0.878/√1975) = −3.29`; with the corpus's own back-derived σ,
`−0.065 / (1.489/√1975) = −1.94`, **which is the published t.** ⇒ **there is no new t; −3.3 is the
old t recomputed with a foreign σ.** ⭐ Recorded without prejudice, because Kimi's *governance* point
in the same catch is right and ran, and because this document has now made the same error five times.

**Claude — named the wrong blocker on un-truncation.** *"Un-truncation is still blocked behind a CA
source that doesn't exist"* — §12.12 measures the blocker as **615 missing sessions**, not the CA
source. ⚠ **Every prior round including mine asserted the same thing**, so this is a shared miss
rather than Claude's; it is recorded here because Claude's round-7 framing ("the CA layer and the
un-truncation are infrastructure for a future question") **depends** on the blocker being cheap, and
it is not.

**ChatGPT — the 20-section interrogation is the over-scoping its own §18 warns against.** §24 asks
for 20 numbered audits, several of them multi-day (§1's full causal trace, §13's capacity curve at
ten capital levels, §11's exhaustive branch enumeration with a golden per branch). §13's CUT exists
because the plan was **3–4× over capacity for one operator with a day job**, and §18 — in the same
response — says the document is becoming *"excellent research archaeology and poor operational
specification."* ⇒ **both cannot be acted on.** ✅ **Adjudication: §18 wins, §24 is cut to the four
items that can change a decision** (direction split · selection attribution · exit/level attribution
· the cash constraint), all four of which ran or are specified below. The other sixteen are recorded
in §14 as open questions, not scheduled as work. ⚠ ChatGPT's framings remain the best on the panel
and this is the third round in which their scope has exceeded the programme's capacity.

**Gemini — three of five items rest on state it did not check.** (a) the pytest/`DATABASE_URL` leak
was **fixed 2026-09-07** and the fix is in the document Gemini reviewed (R7-10); (b) the CA-ratio and
stride-1 requests need **2021–2023 bars that do not exist** (R7-12); (c) the defect-#4 fix is at the
wrong line and is the wrong repair (R7-11). ⭐ **And then item 4 was excellent** — a control variable
nobody had thought to add, on the one finding that most needed it. **That is exactly the
one-number-at-a-time prescription §16.2 wrote, and it worked.** Keep doing that.

### My own errors this round, stated before anyone else finds them

1. ⛔ **I drafted R7-J's regression table before the run finished, from expectation.** Caught and
   deleted before it entered the document; the published table is the run's output. **This is the
   failure mode the whole document is about, committed by its author, in the round that condemned it
   in three reviewers.** Recorded permanently.
2. ⚠ **R7-C's own t = 1.43 is the §4.1 error in my measurement** — an MDE of +0.22R against an effect
   of +0.16R. Stated in the section rather than buried.
3. ⚠ **§12.10d's "2.08 brackets rather than refutes 12" was backwards**, as Kimi says. Corrected.
4. ⚠ **Round 6 measured ρ̄ on a 56%-short book and called it *the* dependence** (R7-A2). The
   measurement was right; the population was not the one any conclusion is about.
5. ⛔⛔ **I published R7-A, R7-C, R7-E and R7-J before running the `--clean-only` variant of the very
   guard I had just built** — and it then corrected three of them (R7-K). **The gap guard was
   shipped in §12.12 as the round's own recommendation, and the round's own measurements did not wait
   for it.** ⇒ ⭐ **Standing rule earned: a guard is not adopted until every number in the same
   document has been re-run through it.** The corrections are in R7-K rather than edited away,
   because that is the only way this document has ever caught anything.
6. ⚠ **I called Claude's Finding D "the best of any round since R5-4" on the strength of a t = 1.5
   that did not survive.** The structural credit is still deserved; the superlative was attached to
   the effect and should have been attached to the question.

## 13h. LEDGER — round 8: three sources, and one of them recomputed the round

Legend: ✅ taken · ⚠ refined · ⛔ rejected · ⭐ best of the round.
**Method unchanged and now load-bearing: every claim re-derived here before adjudication.**

| source | landed | verified true | refuted | best contribution |
|---|---:|---:|---:|---|
| **the audit** (`round8-external-audit`) | 13 | **11 exact, 1 partial** | 1 | ⭐⭐ **C2 — neither round-7 split separates.** Plus **C8** (the null is computable), **C6** (RVOL was an SE artifact) and **D4** (the decision is Bayesian). **The strongest single review of eight rounds** |
| **the architecture reading** | 11 | 8 | 1 | ⭐ **section H — the deployed picker ranks on `confidence_pct`**, which R7-B measures at ρ = −0.018. The answer to the question that started this |
| **the restatement** | 5 | 2 | 3 | ⭐ its **item 1 query**, which surfaced that `nse_holidays` is incomplete for 2019–2020 |

### What round 8 did to round 7 — the tally, stated plainly

**Five round-7 claims withdrawn, all five mine:**

| ⛔ withdrawn | why |
|---|---|
| *"the negative edge is carried by the untradeable half"* | the contrast is t = +0.67, p = 0.50 (C2) |
| *"the hole biases the mean DOWN and σ DOWN"* | t = +0.51; 0.33 of the 0.52 t-drop is power (C2) |
| *"σ_R rises monotonically … every correction makes it harder"* | 0.62 SE — noise; t = 0.82 two-sample (C3) |
| *"the evidence base for the tradeable book is EMPTY, not negative"* | P(positive net edge) = 0.4–5.7% ⇒ option (iii) (D4) |
| *"RVOL is the single most robust coefficient in the document"* | HC3 t = +0.61, clustered +0.98 (C6) |

**Two round-7 gating claims retired within a section of being written:**
**§16.3 item 3** (the equity-beta null, "gated on the index backfill") — the null was computable from
`ohlcv_1d` all along (§12.20). **§17 Q7-2** (does ρ̄ rise with concurrency?) — under a one-factor
model it is flat in m, and the real lever is hold period (D2).

**And three findings round 8 produced that were in no review:** the **tick-grid bug** (§12.19), the
**computed drift null** (§12.20), and the **per-name second hole** that my own guard misses (§12.23).

### ⚠ Where each round-8 source slipped — with the derivation

**The audit — C7's consequence #3 is wrong by √5.** It argues `factor_sweep` "was a coin flip on its
own arithmetic" by discounting its 156 dates 5-fold for overlap. `[code]` `factor_sweep.py:271` is
`keep = set(all_days[::horizon])` — **the dates are already non-overlapping and the correction is
double-counted.** ⭐ **The conclusion survives by the sweep's own published day-block interval**
(SE(spread) 0.436% ⇒ SE(IC) 0.022–0.031 ⇒ it resolved only IC ≈ 0.05–0.07, the top of its own
0.018–0.071 break-even band). **Right answer, wrong route** — §15.4.3's rule applied to the most
careful review of the exercise.
⚠ **And C4 committed §16.1's sample-tag violation while diagnosing a friction error**: its 1.68×
understatement is computed on *positional* stop buckets and applied to a *swing* scalar. Measured on
swing it is **2.77×** — so the direction was right, the magnitude was understated, and the route was
the one the rule forbids. ⭐ **Fifth instance of that error, fifth different author. The rule is
earning its place.**

**The architecture reading — the interrogation is a resend, and its own §18 is the argument against
it.** §13f cut the same 20-section audit in round 7 for being 3–4× capacity; it returned essentially
unchanged, in a response whose §18 correctly says the document has become *"excellent research
archaeology and poor operational specification."* **Both cannot be acted on.** ⭐ And round 8
*strengthens* the cut: C7 shows the decisive question is **one query**, so a 20-part audit is now
demonstrably not the shortest path to the decision. ⚠ Its headline framing — *"the evidence does not
justify 'the strategy is bad'"* — was right on round-7 evidence and is **too weak on round-8's**
(§12.21d): the gross question is underpowered, the **net** question is answered at t = −2.19.

**The restatement — two of five asks were answered in the document it reviewed, and one would have
made things worse.** `conftest.py`'s guard has now been requested twice (R7-10, item 5), and item 5's
proposed SQLite fixture contradicts `.claude/rules/testing.md` outright. ⚠ It also read past R7-K and
re-asserted the withdrawn level-stage claim. ⭐ **Reliable when it quotes the document, unreliable when
it models the system from outside it** — and its one control variable in round 7 remains worth more
than most sources' whole rounds.

### My own errors this round, stated before anyone else finds them

1. ⛔⛔ **I read the LEVEL in each half of two splits and called the ordering a finding, without ever
   computing the CONTRAST.** Both round-7 "inversions" were decompositions. **This is a failure of
   statistical reasoning, not of arithmetic**, and it is the fourth member of a family this document
   now has a name for: **a quantity computed on a subgroup is not evidence about the subgroup until it
   is compared with its complement.**
2. ⛔ **I applied `newey_west_t` to the mean in R7-H and nothing to the regression in R7-J, in the
   same round.** RVOL's t was an iid artifact and I stamped it into §16.1 as "robust".
3. ⛔ **I declared the equity-beta null blocked on a table name** (`index_ohlcv_1d` = 51 rows) without
   asking whether the quantity could be built from something else. It took one query. ⭐ **Same shape
   as §12.12's own lesson — a blocker asserted from a table name is not a blocker** — committed one
   section after writing that lesson down.
4. ⛔ **I shipped a gap guard that tests two endpoints against two hardcoded constants**, when the
   market's session calendar was the owner of the quantity (W5). It misses 1.2% of panels.
5. ⚠ **I used `2·SE` as "MDE" throughout** while §12.11b printed both columns.

---

## 13i. LEDGER — round 9: five sources, one probe, seven decision changes

⭐ **The first round that shipped code with itself**, per §17b's rule. `swing_dependence_probe.py`
gained four column families and a `--dump-trades` artifact; `scripts/round9_cells.py` is new.

### Round-9 scoreboard

| source | points | changed a decision | refuted by measurement | net |
|---|---:|---:|---:|---|
| **Claude** | 7 (B, C1, C2/C3, D1–D5, E1–E3, F, G1–G7) | ⭐ **3** — the wrong-cohort `t`, the third mechanism, the ₹/day framing | **2** — Part B's conclusion, D1's `<2%` posterior | ⭐⭐ **the round** |
| **Kimi** | 12 asks + 9 criticisms | ⭐ **2** — C3's normalizer mechanism, C5's pre-registered prediction | **1** — C3's hypothesis (the refutation is the useful outcome) | ⭐ **second, and C5's methodology is the best habit in the round** |
| **Deepseek** | 8 requests | ⭐ **1** — the collider framing of E2 | — | ⭐ sharpest single sentence |
| **ChatGPT** | 6 packages, 36 sections | ⭐ **1** — the E2 estimand + the MDE convention schema | — | architecture mostly already adopted in §12.21e |
| **Gemini** | 4 tasks | **0** | — | ⛔ see below |

### ⚠ Where each source slipped — with the derivation, per §15.4.3

- **Claude, Part B.** Its closed form `t_net/t_gross = (μ_ret − c)/μ_ret` predicts **−2.202** and
  the exact reconstruction gives **−2.190** (it neglects the 5.4% SE inflation). ⭐ Right to 0.01
  and the structural point stands. ⛔ **Its CONCLUSION — "the net question is not answered on the
  tradeable book" — is refuted by the cell it asked for: t = −1.84 explicit, −2.52 at 15 bps.**
  The prediction failed because it held σ at the clean×BUY value; the reachable restriction cuts
  σ from 1.0050 to 0.6712.
- **Claude, C2's table label.** *"`drift × T` accrual makes **wide** look better"* — its own next
  table shows the drift contribution is `drift·T/w`, **larger for tight** (+0.192R) than wide
  (+0.075R). The prose ("opposite directions") is right; the row label is inverted. Numbers and
  conclusion unaffected.
- **Claude, C1's mechanism claim.** *"`1/w` cannot produce this at any μ_ret"* reads two point
  estimates each within 1.3 SE of zero. `[verified]` **P(the wide bucket is truly negative) =
  22.7%** ⇒ pure `1/w` is **not excluded**. ⭐ **That is the family error — reading a level
  instead of testing it — committed by the source that named the family. Seventh instance.**
- **Claude, D1 and Part F.** Both hang on §12.20's **unpaired** +0.0816%/day drift. Paired, the
  basket over these trades' own windows is **negative**, so `P(beats the basket) < 2%` becomes
  **11%–25%** and the −43 pp/yr becomes a −19…−63 pp/yr range. ⭐ **The estimator it recommended
  (pairing) is what refuted the conclusions it drew without it** — which is the strongest possible
  endorsement of the recommendation and the weakest possible one of the conclusions.
- **Kimi, C5's prediction.** −0.15R / t −1.1…−1.4 vs measured −0.177R / **t −1.84**. ⭐ **Publishing
  it anyway was the right call** — a wrong pre-registered prediction is worth more than a right
  post-hoc one, and it is why §12.31b reads as a test.
- **Kimi, C6's tick arithmetic.** ✅ **Correct and adopted**: the artifact is the **excess**
  (10.26 bps ⇒ **0.0513R** at a 2% stop), not the total (12.82 bps ⇒ 0.0641R). §12.19b used both
  for the same quantity.
- **Kimi, C9.** Reported the document truncated at §16.1b. ⚠ **Not reproducible here** — the file
  is 4,500 lines with §16.2, §16.3, §17 and §17b all present. **A transfer artifact, and it means
  its adjudication of §17's four questions was made without reading them.**
- **ChatGPT, §29's P0 list.** Four of its eight P0 items were already answered in the document it
  was reading (the cash rail §12.14, the parity matrix §12.21c, the collider §12.10c, the
  raw-%/ATR re-report R7-J). ⚠ **§17b's standing request, ignored for the fifth round running.**
- ⛔ **Gemini.** All four of its "execute these sequentially" tasks are answered in the document it
  was given: the tick bug is §12.19 (**and its proposed hardcoded `0.01 if price < 250 else 0.05`
  is exactly what §12.19b warns against** — the phase-in is staged, so it needs a dated table);
  the cash constraint is §12.14; the 922-day hole is §12.12 and §12.23; the IC-in-raw-% test is
  E2. ⭐ **Its restatement of the document is accurate, which is worth something — but round 9
  measured the marginal value of a source that reads without recomputing at exactly zero, for the
  second round running.**

### ⭐ My own errors this round, stated before anyone else finds them

1. ⛔⛔ **§12.20a's "the correct null roughly DOUBLES the deficit" is mine, and it is wrong.** I
   multiplied a drift measured on **789 post-gap sessions** by an **assumed** 5-session horizon and
   subtracted it from trades occupying **different** sessions with a mean hold of **3.59**. Paired,
   the basket on the tradeable book is **negative**. ⭐ **This is §16.1's sample-tag rule in the
   TIME dimension, and I wrote the rule.** Sixth… ⚠ eighth instance.
2. ⛔ **I published the E3 prediction (−0.142R, t −0.95…−1.10) with σ held fixed at 1.0050** — the
   same "combine a σ from one sample with an n from another" defect, in the section adjudicating
   that defect. Measured σ on the reachable cell is **0.6712**.
3. ⚠ **My first posterior shrank a NET mean toward zero.** The prior is a claim about GROSS edge;
   costs are known and must not be shrunk. Caught and fixed before it entered the document
   (§12.31g), recorded here permanently.
4. ⚠ **My first ₹/day table used mean-of-ratios without saying so**, which counts a same-session
   exit as a full day and roughly doubles the gap. **Both aggregations are now printed** and the
   account-relevant one is the smaller.

# PART V — GOVERNANCE AND REFERENCE

## 14. Open questions — NOT review prompts

⛔ **These are not review prompts. They are questions only the data can answer, and every one of
them needs a shipped item first. Rounds 5 and 6 answered Q1–Q4 and Q6; see §13b and §12.10.** Recorded so they are not lost, not so they are
re-litigated.

1. **Is the reachable-cohort sign flip (§12.1) a real effect or a survivorship artifact of the
   notional cap?** The restriction is identity-derived, not searched — but the cap correlates
   with stop width, which correlates with volatility. What is the right control?
2. **Does the σ_R argument (§12.2) survive the objection that a constant-R:R target changes the
   trade population**, not just its scaling? D5 measured paired ΔR on identical signals, so the
   population is held fixed there — but is the σ_R comparison equally paired?
3. **What is the correct null for a long-only book in a rising market**, expressed so that it can
   be computed rather than argued? §4.2 now has three competing formulations (martingale,
   discrete-monitoring, drift-adjusted) and the two permutation nulls in #15 may not span them.
4. **Is the "breadth from time not names" escape actually available at ₹1 lakh**, given that an
   index/ETF book has one position and therefore n = sessions, not trades? What is the unit of
   observation there, and does the DSR bar even apply?
5. **If KILL LINE 3 fires, what survives?** The apparatus is the stated asset — but an apparatus
   with no strategy is a cost centre. What is the minimum viable next hypothesis that reuses the
   execution/risk/statistics stack without reusing the signal engine?
6. **Is there a defensible reason to keep the `classification` dimension at all**, given R2-35
   (positional needs 2× the trades) and §9.6 (the relabel is unsupported either way)? Dropping it
   merges the corpora and buys statistical power directly.

### 14b Round-7 additions — and where ChatGPT's other sixteen audits went

⚠ **§13f adjudicated ChatGPT §24's twenty-item interrogation down to four.** The four ran (direction
split · selection attribution · exit/level attribution · the cash constraint). **The other sixteen
are recorded HERE as open questions, which is what they are — not scheduled as work**, because the
plan is eight items and one has shipped in 50 days. Each is a legitimate question; none of them can
be answered before the sunset alongside the eight.

7. ⭐ **Is `1 + (m−1)ρ̄` the right functional form for a long-only equity book?** Dependence there is
   a shared *factor*, not a pairwise correlation, so a one-factor form (`ρ̄ ≈ β²σ²_mkt/σ²_total`)
   would make breadth a function of β and residual variance — and would predict ρ̄ **rises** with
   slot count, giving effective breadth an asymptote that no capital crosses (§17 Q7-2). Our measured
   long-only ρ̄ ≈ +0.19 at m = 2.08 is one point on a curve nobody has drawn.
8. ⭐ **Is the level stage's anti-selectivity evidence about the SCORER or about `compute_levels`?**
   R7-C measures +0.16R in favour of the discarded cohort at t = 1.5. D5 already closed the *target*
   geometry; the *stop* side has never been tested and `compute_levels` is FROZEN (§17 Q7-3).
9. **Is the 2021-01 → 2023-06 back-fill worth days of ingestion**, given that everything it buys is
   more n on an estimator whose population does not transfer to the live book (§12.12, §17 Q7-4)?
10. **Can the correct null (Q3) be stated quantitatively without an index series?** `index_ohlcv_1d`
    holds **51 rows**, so the equity-beta null that §4.2 requires cannot currently be computed —
    which leaves the whole "negative alpha, not zero alpha" claim unquantified (§17 Q7-1).
11. ⭐ **Does `RVOL-20`'s t = +3.67 in R survive being re-asked in raw % on a point-in-time,
    gap-clean, long-only sample?** Our prior is no — it is already t = −0.28 in raw % on this sample
    (R7-J). Logged so it cannot be rediscovered as new in round 9.

**ChatGPT §24's unscheduled sixteen, listed so they are not silently dropped:** the full end-to-end
timestamped look-ahead trace (§24.1 — still the one genuinely unstarted item, now in its third round
of being named) · the capital/cash feasibility trace at ten capital levels (§24.2 — partially
answered by §12.14's 120% finding) · stride-1 full-density denominator chain (§24.4) · setup taxonomy
and setup × score interaction (§24.5) · MFE/MAE/hazard exit attribution (§24.6) · the CA
knowledge-time audit (§24.8 — schema specified in §12.17 R7-9, unbuilt) · the point-in-time universe
*reconstruction* as opposed to the diagnosis (§24.9 — the diagnosis is R7-7) · the slippage
regression (§24.10 — ⛔ **impossible**, `orders` = 0) · exhaustive barrier-branch enumeration with a
golden per branch (§24.11 — the branch inventory is real work; the count is 1.08%) · the separated
tax/cost stack (§24.12 — no tax code exists) · the true capacity curve (§24.13) · the six-level
benchmark hierarchy (§24.14 — already plan item #25) · the primary-estimand proposal (§24.15 —
answered in part by §12.15's 3a/3b split) · the kill-line audit (§24.16 — §12.15 is that audit) ·
the single-source-of-truth object audit (§24.18 — the `DecisionSnapshot` chain, accepted as the
ledger schema) · the research-provenance lineage table (§24.19 — R7-2 answers the part that mattered).


## 15. ⭐ REBUTTALS, WITH THE EVIDENCE — read before re-raising anything

**Purpose.** Across four rounds several claims have been raised, refuted, and raised again in a later
round by a different reviewer. This section exists so a rejection can be *checked* rather than
re-argued. Every row carries the actual evidence — a code line, a query result, or arithmetic you can
reproduce — plus **what would change my mind**, so the rebuttal is falsifiable rather than defensive.

**If you disagree with a row, attack the evidence in it.** A restatement of the original claim
without engaging the counter-evidence will be recorded as already-answered.

### 15.1 Rejected on measurement (a query settles it)

| claim | raised by | evidence against | what would change my mind |
|---|---|---|---|
| "You have never computed factor-level IC — do it first, it's two days of work" | Claude, ChatGPT, Perplexity, Kimi (R1) | `scripts/factor_sweep.py`, run **2026-09-07**: 212,129 observations, 156 non-overlapping dates, day-block bootstrap **plus trial-count deflation** (a guard none of the four proposed). Reports: `docs/analysis/factor-sweep-h{5,20}-2026-09-07.md` | Nothing — it was run. ⚠ But see §3.1: the run is **CA-contaminated**, so it does not license "no IC exists." That correction stands independently. |
| "Your corpus is survivorship-biased — reconstruct a point-in-time universe from the NSE symbol master" | Kimi, ChatGPT, Claude (R3) | `[db]` `stocks` = **3,392 rows**, of which **2,070 inactive are RETAINED**; **542** price series have a last bar >90 days old (dead names *with history*); `stocks.listed_on` exists. **The database can see the losers.** | Evidence that a *material* number of 2019–2026 delistings are absent from `stocks` entirely. The 542 dead series argue against it. |
| "…so reconstruct the universe from external sources" | Kimi, ChatGPT (R3) | Not needed. The defect is **one query in our own probes** — `positional_probe.py:92` and `engine_selectivity_probe.py:106` both use `WHERE time > now() - interval '180 days'` (excluding all 542 dead names) then rank by **today's** liquidity. `factor_sweep.py` is clean (rolling `adv20`). | If ranking as-of-panel-date turns out to need data `ohlcv_1d` lacks. It doesn't. |
| "The composite-score IC test is feasible" (implicit in every round's plan, mine included) | mine | `[db]` `fii_dii_daily` = **4 rows, 2026-09-08 → 09-10**; `stocks.sector` populated on **165/1,322**. `confluence.py:121` feeds both into the composite. **#16 is infeasible on any window** without a price-only variant. | Recovering FII/DII history to 2019. Until then the price-only variant is a *different estimand* and must be labelled one. |
| "Un-truncate, then apply the CA adjustment layer" | mine (0a.6) | `[db]` `corporate_actions` = **0 rows**. The layer has **no event source for any period**. 0a.6 is gated behind sourcing it. | A CA event feed. This is a data-acquisition task, not a build task. |
| "`fees.py` needs effective dating for the pre-2023 window" | Claude (R4) | ✅ **Half already shipped (A23):** `fees.py:101` has `effective_from`, `schedule_for(on)` selects by date, `compute_charges(..., on=)` uses it. ⚠ **But `SCHEDULE_HISTORY` holds exactly one entry floored at 2000-01-01** — machinery built, unpopulated. The **tradeability** half (ASM/GSM, T2T, circuit state at signal time) has no mechanism at all. | Nothing — the conclusion holds. The work is *populate a list*, not *build a system*, which is smaller than claimed. |

### 15.2 Rejected on arithmetic (reproduce it and see)

| claim | raised by | the arithmetic | what would change my mind |
|---|---|---|---|
| "The block-bootstrap SE is roughly double the iid SE at n=271, so §12.5's corpus MDE is optimistic 3–4×" | Kimi (R4) | From §12.4's own output: 90% Sharpe interval [−0.061, +0.148] ⇒ half-width 0.1045 ⇒ SE(Sharpe) 0.0635 ⇒ **SE(mean R) = 0.1171R**. iid SE = 1.844/√271 = **0.1120R**. **Ratio 1.046×, not 2×.** The claim compared its bootstrap **MDE** (0.234R) against the nominal **SE** (0.112R) — the factor of two is the t=2, counted twice. | ⭐ **Already changed — by Claude's separate derivation.** Kimi's *conclusion* is right (corpus MDE **was** optimistic) via concurrency, not via the bootstrap: m≈12 ⇒ required gross +0.23–0.28R, which converges with Kimi's own +0.19–0.27R. **Right answer, wrong evidence.** Both are now recorded. |
| "`IC_min = cost_in_R / (breadth × σ_R)`" | Gemini (R4) | Does not type-check: cost-in-R and σ_R are dimensionless, breadth is a count ⇒ the result has units of 1/count, but an IC is a correlation. Numerically it returns **0.0006–0.0066** against a defensible **0.018–0.071**, i.e. **4–100× too permissive** — wrong in the direction that stops KILL LINE 3 firing. Root cause: `IR = IC√BR` (portfolio) conflated with `E[ret] = IC × σ_cs × E[z]` (per selection). | A derivation in which breadth legitimately enters the per-selection transfer. It doesn't. |
| "Two swing pivots at n=5 need a minimum of 4 × 11 = 44 bars" | Gemini (R1) | Pivot windows may sit **6 bars apart** and still not overlap in the relevant sense, so 44 is not the bound. Our derivation is the correct one: inside a 20-bar lookback a pivot index can only sit at 5…14, any two differ by ≤9 < 11. **Same conclusion, sound reasoning — use ours.** | Nothing; the conclusion is agreed. Only the derivation is rejected. |
| "Normalise confidence by the full 160 weight" | Gemini, Perplexity, Kimi (R1) | Measured p90 scoring weight is **55 of 160** ⇒ realistic maximum confidence collapses to ≈34 and the 70 gate becomes unreachable, forcing a re-fit of the threshold — one arbitrary parameter for another. | A proposal that does not require re-fitting the gate. Dropping the ratio entirely (score on the raw weighted sum) is the one that qualifies. |
| "§7's median R = −1.000 in every bucket contradicts the 62.5% win rate" | Kimi (R3) | `[doc]` §7's table shows median **+1.084** for that bucket. The −1.000 is the corpus-wide median quoted in `PHASES.md`. **Right instinct, wrong row** — and exactly the consistency check worth running. | Nothing; the table is correct as printed. |

### 15.3 Rejected on reasoning (the conclusion doesn't follow)

| claim | raised by | why | what would change my mind |
|---|---|---|---|
| "Deprecate TA confluence for a 4-factor orthogonal model" | Gemini (R2) | A rebuild recommendation with **no measurement attached**, and it presumes the ranker conclusion that §3.1 **reopened** rather than settled. Sequencing also fails: a ranker built on today's data plane would rank contaminated inputs on features `factor_sweep` already found flat. | Run it *after* the CA-adjusted `factor_sweep` re-run. If cross-sectional IC appears, the orthogonal-factor idea is live again — **rejected as a conclusion, not as a hypothesis.** |
| "Pivot to ETF/Index, where flat DP charges don't destroy net expectancy" | Gemini (R4) | Wrong twice. `fees.py:228` charges the DP on `product == "delivery" and side == "SELL"` — an ETF sold from delivery is charged identically; what makes ETFs cheaper is **lower turnover**, not exemption. And it recommends escape 1 without engaging the settled finding that index/ETF is **not a breadth solution** (observations ≠ bets). | A turnover-and-cost model showing an ETF book clears the hurdle. The cost table (Week 0 #6) will settle it either way. |
| "Hold off restarting CAS accrual until the cost table is computed" | Claude (R3) | Asymmetry. The accrual is a **built Celery task at zero marginal cost**; a missed session is **permanently unrecoverable**; the table takes an afternoon. Do both today; stop the accrual if the table kills it. | Nothing — Claude conceded this in round 4. |
| "Merge the corpora to buy statistical power" | Kimi (R3) | Pooling populations with different σ (1.489 vs 1.844–2.088), horizons and targets **inflates** pooled σ and can *lower* power. ⇒ **delete the positional relabel; don't pool two rule sets.** Power by deletion. | ⚠ Partly changed by ChatGPT R4: keep a horizon **descriptor** (1–5d / 5–20d / 20–60d) as a research label while deleting the **rule set**. Adopted. |
| "Never compare a harness number to an analytic null" | **mine** (R3) | ⚠ **Self-rejected on ChatGPT R4's argument.** The correct rule is *never use an analytic null as the **sole** benchmark for a non-trivial execution engine.* Three layers are needed, and I had only two: **analytic** (what an idealised process gives) · **engine-calibrated** (a known random process pushed **through our harness** — the only way to measure the harness's own bias rather than cancelling it) · **permutation placebo** (our rule against matched alternatives). | Nothing — the correction is adopted. |

### 15.4 Standing instruction for future rounds

1. **A claim about the data plane is a question, not a finding, until someone runs the SQL.** Four
   rounds, four occasions where a confident data claim was resolved only by a query — survivorship,
   CA coverage, FII history, universe construction — and on three of those the reviewer's conclusion
   was directionally right and its stated mechanism wrong.
2. **Reproduce the arithmetic before asserting a factor.** Two of the four rejections in §15.2 are
   dimensional or double-counting errors that a single evaluation would have caught.
3. **A conclusion can survive its own broken derivation.** Kimi's corpus-MDE claim is the case in
   point: wrong evidence, right answer, and dismissing it on the evidence alone would have lost a
   real finding. Attack the derivation and the conclusion **separately**.




---

### 15.5 Round-5 rejections, with the derivation

**Every row shows the arithmetic so it can be checked rather than re-argued.**

| claim | raised by | the derivation | what would change my mind |
|---|---|---|---|
| "DP drag is 11.5% of capital at ₹1L and 3.84% at ₹3L, so capital materially fixes the strategy's cost problem" | **ChatGPT** | ⚠ **Those are the CAS/daily-turnover figures applied to the swing book — wrong by 5×.** DP drag = `slots × (250 ÷ hold_days) × ₹15.34 ÷ capital`. At 3 slots: **hold = 1 day** ⇒ 750 sells/yr ⇒ ₹11,505 ⇒ **11.51% of ₹1L, 3.83% of ₹3L** ✓ your numbers. **hold = 5 days** (the swing book) ⇒ 150 sells/yr ⇒ ₹2,301 ⇒ **2.30% of ₹1L, 0.77% of ₹3L.** The conclusion "capital fixes the cost problem" holds **only for the daily-turnover book.** | A swing book with a hold period materially under 5 days. At 3-day holds it is 3.83%/1.28% — still a third of the CAS figure. |
| "Tripling capital buys ~6% more effective breadth" | **Kimi** | `N_eff = N ÷ (1 + (m−1)ρ̄)` where `N = m × 250 ÷ hold`. At m=3: N=150, I=2.0, **N_eff = 75**. At m=9: N=450, I=5.0, **N_eff = 90**. **+20%, not +6%.** The 6% figure appears to hold N fixed while raising m, but more slots produce proportionally more trades. | A reason concurrent slots would not raise the trade rate proportionally — e.g. a signal-supply constraint. At ~25–55 signals minted nightly, supply is not binding at 9 slots. |
| "Tripling capital buys ~33% more effective breadth" | **Claude** | Same formula, same measurement: **+20%.** Your concurrent figure `m_eff = m ÷ (1+(m−1)ρ̄)` gives 3→1.50 and 9→**1.80**, i.e. +20%, not the 1.5→2.0 (+33%) in your table. | An error in the inflation formula. Both of us used `1+(m−1)ρ̄`; the arithmetic at m=9, ρ̄=0.5 is 9/5 = 1.80. |
| "Comparing required gross against the Sharpe-1.0 benchmark shows you need 2.8–3.8× a world-class edge" | **mine (§12.5)** | ⛔ **SELF-REJECTED on Claude R5.** `required gross = friction + MDE` includes friction; a Sharpe ratio is conventionally **net**. Friction was counted on one side only. Consistent gross-vs-gross: Sharpe-1.0 **grosses** 0.189–0.286R against an MDE of 0.116–0.203R ⇒ **detectable ×1.11–1.63.** | Defining the benchmark **gross** instead — under which a Sharpe-1.0 system nets 0.015R against a 0.116R MDE and fails by ~8×. **The convention is NET. It is now stated, because the answer swings on it.** |

### 15.6 ⛔ Two of the three inputs were unmeasured assumptions — now measured (§12.10)

**This is mine, and it applies to every reviewer's arithmetic including my own.** Rounds 3–5 all
turn on three quantities. Only one of them has been measured.

| input | status | value used | how it was obtained |
|---|---|---:|---|
| **σ_R** | ✅ **measured** | 1.489 swing · 1.844–2.088 positional | positional measured directly by probe; swing derived from n=1,975, mean −0.065, t=−1.94 (an **iid** t — verified, every corpus t in our scripts is `mean/(sd/√n)`) |
| **ρ̄** (mean pairwise correlation of concurrent trades) | ⛔ **ASSUMED** | **0.5** | Introduced in round 3 as an illustrative figure and used unchallenged ever since. **Nobody has measured it.** It sets the variance inflation `1+(m−1)ρ̄`, which drives the effective-n correction, which drives §12.5, §12.8 and the entire capital analysis |
| **friction** | ⚠ **half measured** | 0.11R at a 5% stop | Explicit charges are **0.051R** (25.5 bps, computed on `roundtrip_charges`). The other **~0.06R is an unmeasured slippage assumption** (§12.8b) |

⭐ **So the headline conclusion — in either direction — rests on one measured number and two
assumptions.** At ρ̄ = 0.3 the corpus inflation falls from 6.5 to 4.3 and every MDE improves ~23%; at
ρ̄ = 0.7 it rises to 8.7 and they worsen ~16%. **ρ̄ is directly measurable from the corpus** (pairwise
correlation of R across concurrent trades) and it is one query. Until it and the slippage term are
measured, **no reviewer's arithmetic on this — mine included — is better than its inputs.**

⇒ **Added to the cut as items 10 and 11**, because both feed the two levers §12.5 says can move the
answer, and both are cheaper than anything else on the list.

### 15.7 Round-7 rejections, with the derivation

⚠ **Read before re-raising any of these. Each was checked, not argued.**

| claim | source | why it is rejected |
|---|---|---|
| *"pytest still connects to `DATABASE_URL` — implement purge protection"* | Gemini item 1 | ⛔ **SHIPPED 2026-09-07.** `[code]` `tests/conftest.py:36` `_refuse_non_test_database()` aborts at import unless every URL ends `_test`; backups at `0 11 * * 1-5`. **The fix is described in the document Gemini was reviewing** |
| *"fix defect #4 at `engine.py:212` — ensure gap exits fill at candle open"* | Gemini item 3 | ⛔ **Wrong line, wrong repair.** `:212` is the correct fill (`fill_candle["open"]`); gap exits **already** fill at the open (`:249-255`). The defect is a **missing through-stop rejection on the FILL bar** (`if i > fill_idx` skips the gap branch there). Frequency **1.08%** |
| *"query Kite adjust ratios back to 2019-10; run stride 1 from 2019-10 to 2026-09"* | Gemini items 2–3 | ⛔ **The bars do not exist.** §12.12: a **922-day hole**, 2020-12-23 → 2023-07-03 |
| *"applied to the corpus (mean −0.065R, σ=0.878) t ≈ −3.3 — the negative strengthens"* | Kimi Catch 2 | ⛔ **σ from `probe-185`, n and mean from `corpus-1975`.** With the corpus's own σ: −1.94, **the published t**. No new number. §16.1's sample-tag rule now forbids the combination |
| *"the slippage measurement deserves the front of the plan"* | Kimi Catch 5 | ⛔ **Not adopted.** The book is net-negative by **0.24R–0.32R at every point in 10–30 bps** (R7-3), so slippage changes a **future** hurdle, not the current verdict. Demoted to item 9 |
| *"the 80–84 dip may be SELL-concentrated ⇒ the score mis-ranks shorts"* | Kimi Q7 | ⛔ **REFUTED by measurement.** Worst bucket in **both** directions: BUY −0.433 (n=18), SELL −0.186 (n=24). R7-B2 |
| *"R-correlation ≈ 0 does not imply portfolio correlation ≈ 0 — measure cash P&L"* | ChatGPT §3 | ⚠ **Measured, and it does not bite:** ρ̄ is −0.013 (R), −0.011 (%), **+0.028 (cash)**, downside lift **0.925×**. The identity ChatGPT did not invoke: risk-first sizing makes cash ≈ R × constant. ✅ **The distinction is still correct in principle** — and the mechanism that does bite is **direction** (R7-A2) |
| *the twenty-section evidence-extraction interrogation* | ChatGPT §24 | ⚠ **CUT to four items.** 3–4× the capacity that forced §13's CUT, in the same response whose §18 warns the document is becoming poor operational specification. §18 wins; the other sixteen live in §14 as open questions, not as work. §13f has the derivation |
| *"that single refactor retires nine plan items, most of a week's work"* | Claude, architecture | ⚠ **Refined.** `backtest/engine.py` is **FROZEN**: a kernel refactor needs explicit sign-off, an §8 backtest regression and **regenerated Rust oracle fixtures in the same commit**. The design is adopted; the cost estimate is not |
| *"un-truncation is blocked behind a CA source that doesn't exist"* | Claude (and every prior round, mine included) | ⛔ **Wrong blocker.** It is blocked behind **615 missing sessions** (§12.12). Recorded as a shared miss |
| *"Kelly mandates zero" as governance language* | ChatGPT §9 asked for this to be softened | ⚠ **Partly rejected — the measurement went the other way.** The empirical estimator gives **f\* = 0.0000 exactly**, and μ/σ²'s 90% CI **excludes zero even BUY-only after costs** [−0.72, −0.016] (R7-E). ✅ ChatGPT is right that `p − q/b` was the wrong instrument; ⛔ it is wrong that the right instrument would weaken the conclusion. It hardened it |

## 16. ⭐ REFERENCE CARD AND REVIEWER NOTES

**Why this section exists.** Five rounds have produced roughly a dozen arithmetic disagreements, and
**most of them came from different sources using different values for the same quantity**, or from
asserting a formula without evaluating it once. This section fixes the shared inputs and tells each
reviewer, specifically and with evidence, where its own reasoning has repeatedly gone wrong.

**All five sources stay in the panel** (user ruling, 2026-09-11). The point of these notes is not
ranking — it is to raise the floor, because every source here has contributed something the others
missed, and every source here has also been confidently wrong at least once.

### 16.1 Canonical constants — use these, or say why you are not

⚠ **Marked `[measured]` or `[ASSUMED]`. Do not treat an assumption as a measurement.**

⭐ **TWO NEW COLUMNS, round 7 — and they are the enforcement mechanism, not decoration.** Kimi
Catch 4 found this card still carrying the round-3 inputs the whole of round 6 was spent retiring,
and Claude's Finding A found §12.10a combining a σ from one sample with an n from another.
**Both are the same defect: a quantity used without its provenance.** So every row now names the
**sample** it was measured on and the **date** it was last verified, and:

> ⛔ **NO FORMULA IN THIS DOCUMENT MAY COMBINE TWO QUANTITIES WHOSE `sample` TAGS DIFFER.**
> A σ measured on `probe-185` may not be divided by √n for `corpus-1975`. This is a mechanical rule,
> checkable by reading two cells, and it is the only defence that has ever worked against a failure
> this document has now committed **five** times (R2-11 → §12.5 → R4-1 · gross-vs-net in §12.5 ·
> m=12-vs-2.5 inside one §12.8 row · ρ̄ → §12.9 · σ → §12.10a).

| quantity | value | **sample** | **verified** | status |
|---|---:|---|---|---|
| σ_R, swing — **mixed direction** | **0.878** | `probe-185` | 2026-09-11 | `[measured]` ⚠ **not transferable to `corpus-1975`** — five structural differences, §12.13b |
| σ_R, swing — **BUY only** | **0.957** | `probe-82` | 2026-09-11 | ⭐ `[measured]` R7-A. **The tradeable book's σ** |
| σ_R, swing — corpus | **1.489** | `corpus-1975` | — | ⚠ `[DERIVED]` from `SE = 0.065/1.94`, never measured. **σ on the corpus is an open measurement** |
| σ_R, positional — all / reachable | **2.088 / 1.844** | `positional-probe` | 2026-09-10 | `[measured]` directly |
| ρ̄, concurrent trades — **mixed** | **−0.013** | `probe-263-pairs` | 2026-09-11 | `[measured]` ⚠ **a 56%-short book; the cancellation is directional** (R7-A2) |
| ρ̄, concurrent trades — **long only** | **≈ +0.19** | `probe-82` | 2026-09-11 | ⭐ `[derived]` from inflation 1.19–1.23× at m=2.08. **Use THIS for any live-book conclusion** |
| variance inflation — mixed | **1.00×** | `probe-185` | 2026-09-11 | `[measured]` calendar-block, 10d and 30d agree |
| variance inflation — **long only** | **1.19–1.23×** | `probe-82` | 2026-09-11 | ⭐ `[measured]` R7-A2 |
| mean R, swing — **mixed** | **−0.1489** (t −2.31) | `probe-185` | 2026-09-11 | `[measured]` ⛔ **blends an untradeable short majority — do not quote alone** |
| mean R, swing — **BUY only** | **−0.0992** (t **−0.94**) | `probe-82` | 2026-09-11 | ⭐⭐ `[measured]` **THE HEADLINE.** Not distinguishable from zero |
| mean R, swing — corpus | −0.065 (t −1.94) | `corpus-1975` | 2026-09-09 | `[measured]` ⚠ **mixed class AND mixed direction** |
| Spearman ρ(confidence, R) | **−0.018**, perm p 0.807 | `probe-185` | 2026-09-11 | ⭐ `[measured]` R7-B. Detectable at 0.147, so this is a **powered** negative |
| Kelly f\* (empirical, `max E[log(1+fR)]`) | **0.0000** in every cell | `probe-185` / `-82` / `-147` / `-61` | 2026-09-11 | ⭐ `[measured]` R7-E. ⚠ §12.11a's **−0.5 was the binary-bet formula, wrong by 2.6×**. ⚠ **μ/σ²'s CI includes zero on the CLEAN BUY book** [−0.844, +0.016] — `f*=0` is the robust claim, the interval is not (R7-K) |
| effective n | `n ÷ inflation` | — | — | identity |
| MDE at t=2 | `2σ_R ÷ √(effective n)` | — | — | identity ⚠ **σ and n must share a sample tag** |
| m, live / corpus / observed | 2.5 / 12 `[derived]` · **2.08** | `probe-185` | 2026-09-11 | ⚠ **2.08 does NOT bracket 12** — it samples a 10× sparser regime (Kimi Catch 3, accepted) |
| trades per year, live / corpus | **125 / 619** | `corpus-1975` | 2026-09-09 | `[measured]` (1,975 over 3.19 yr) |
| friction at the median 5% stop | **0.051R explicit** + **0.060R ASSUMED** | `fees.py` / — | 2026-09-10 | ⚠ the assumed half is **15 bps/leg** and can NEVER be measured retrospectively (`orders` = 0). Report at **10 / 15 / 20 bps** = 0.091 / 0.111 / 0.131R |
| explicit round-trip charges | **22–29 bps** (25.5 at ₹1L / 5% stop) | `roundtrip_charges` | 2026-09-05 | `[measured]` |
| STT, delivery round trip | ≈ **20 bps**, purely proportional | `[code]` | 2026-09-05 | why capital barely helps the swing book |
| DP charge | **₹15.34 flat**, delivery SELL leg only | `fees.py:228` | 2026-09-05 | the only cost that scales away with capital |
| concurrent slots — **Policy A** | `heat ÷ risk = 6% ÷ 2% = **3**` | identity | — | ⭐ **scale-free; capital cancels** |
| concurrent slots — **Policy B** | 3 / 4 / 6 / 9 at ₹1L→₹3L | identity | — | ⚠ a **different policy** — it cuts `risk_pct`, and **is available at ₹1L** (§12.11b) |
| **Σ notional constraint** | ⛔ **DOES NOT EXIST IN CODE** | `paper_broker` · `risk_engine` | 2026-09-11 | ⭐ `[code]` R7 / ChatGPT §11. 3 slots at a 5% stop = **120% of capital**, unchecked (§12.14) |
| minimum stop width (notional cap) | `risk_pct ÷ leverage = **2%**` | identity | — | ⭐ also scale-free |
| Sharpe-1.0 benchmark — **NET** | ⭐ **+0.0785R** at N=125, I=1.00, σ=0.878 · gross **+0.1295R** | `probe-185` | 2026-09-11 | ⛔ **SUPERSEDES the ~~0.125R at N=250/m=2.5~~ and ~~0.176R at N=125/m=2.5~~ rows, which carried σ=1.489 and I=1.75** — the retired inputs (Kimi Catch 4). ⚠ **state N, I and the sample or the number is meaningless** |
| Sharpe-1.0 benchmark — **long-only** | **+0.0942R** net at N=125, I=1.21, σ=0.957 | `probe-82` | 2026-09-11 | ⭐ `[derived]` — the benchmark the tradeable book must actually clear |
| **sessions in `ohlcv_1d`** | ⛔ **1,097**, with a **922-day hole 2020-12-23 → 2023-07-03** | `[db]` | 2026-09-11 | ⭐⭐ **NOT a 7-year continuous span.** §12.12. Any span claim must cite a session count |
| un-truncation yield | ⛔ **n ≈ 2,662 (bar-50 walk) · 0 (300-bar walk)** | `[db]` | 2026-09-11 | ⛔ **supersedes "1,975 → ~4,300"** |
| universe bias, today-ranked vs as-of | ⛔ **46%** of the 2021 top-250 absent from today's | `[db]` | 2026-09-11 | ⭐ 1,294 inactive-today names held >100 bars in H2-2020 — **the DB is not the constraint, the query is** |
| ⭐⭐ **mean R, swing — CLEAN × BUY (the honest estimate)** | **−0.0843** (t **−0.66**), σ **1.0050**, MDE **+0.29R** | `probe-61` | 2026-09-11 | ⭐⭐ `[measured]` R7-K. **THE cell every conclusion depends on, and it is UNINFORMATIVE** |
| σ_R ladder, as the population is restricted | **0.878 → 0.911 → 0.957 → 1.0050** | mixed-all → mixed-clean → BUY-all → **BUY-clean** | 2026-09-11 | ⭐ `[measured]` R7-K. **Monotone; every correction makes it worse and walks halfway back to the corpus's 1.489** |
| variance inflation ladder | **1.00× → 0.92–0.99× → 1.19–1.23× → 1.24–1.43×** | same ladder | 2026-09-11 | ⭐ `[measured]` ρ̄ ≈ **+0.26** at m=2.28 on the clean long-only book |
| mean R, swing — **gap-clean windows only** | **−0.1341** (t **−1.79**), σ **0.911** | `probe-147` | 2026-09-11 | ⭐ `[measured]` R7-I. **Removing gap-straddled trades alone drops the headline below significance** |
| stop-width gradient, `Rw ~ w` | ⛔ **GONE.** +0.065 t +2.30 all-windows → **t +1.06 clean** → **SIGN FLIPS NEGATIVE on clean × BUY** (−0.032, t −0.56); **t +1.07 in raw %** | `probe-185` → `probe-61` | 2026-09-11 | ⛔ `[measured]` R7-J + R7-K. **Survives NEITHER the unit change NOR the gap filter** ⇒ the 2026-08-25 stop-width finding was a gap-contaminated R-denominator artifact. **NOT an ATR proxy either** (ATR% t −0.43) |
| `RVOL-20` on R | **+0.198, t +3.67**; **clean +3.65**, clean × BUY **+3.13** | `probe-185` / `probe-147` / `probe-61` | 2026-09-11 | ⛔⭐ `[measured]` R7-J + R7-K — **the only t ≥ 3.6 in seven rounds, ROBUST to the gap filter, and DISQUALIFIED by §12.10b**: in raw % it is **t −0.36** (clean × BUY −0.67). **The only thing that kills it is the unit.** Recorded, NOT promoted; D1 refuted RVOL as a generator at t −2.91 |
| reporting bounds | `MAX_RR` 50 · `WINSOR_R` 10 · `MAX_R` 9999.999 | `ratios.py` | 2026-09-05 | three different jobs, do not merge. ⚠ **`WINSOR_R` is inert on `probe-185` — 0 of 185 clipped** |


### 16.1b ⭐ Round-8 corrections to the card above

⚠ **These SUPERSEDE the rows they name. The card is the contract; when a row here disagrees with a
row above, this one wins.** Every entry was re-derived independently from the round-8 audit before
being accepted (§12.18).

| quantity | ⛔ round-7 value | ✅ **round-8 value** | why |
|---|---|---|---|
| **"MDE"** | `2σ_R ÷ √n_eff` | ⭐ **`2.8016·SE` at 80% power**; `2·SE` is the **critical effect at t=2 (50% power)** and must be labelled so | C1. `2·SE` is the effect that *produces* t=2 if observed exactly. Factor **1.4008** |
| MDE, honest cell (`probe-61`) | +0.29R | ⭐ **+0.417R** | C1, at SE 0.1490 |
| detectability of a Sharpe-1.0 edge | ×2.87 | **×2.05** | C1 |
| **direction split** | *"the negative edge is carried by the untradeable half"* | ⛔ **WITHDRAWN — the contrast is +0.0893, SE 0.1325, t = +0.67, p = 0.50.** The halves **do not differ**; the BUY cell is preferred on **instrument grounds** (no overnight cash short), never statistical ones | C2 |
| **gap filter** | *"the hole biases the mean DOWN and σ DOWN"* | ⛔ **WITHDRAWN — contrast +0.0718, SE 0.1420, t = +0.51.** And **0.33 of the 0.52 t-drop is power loss, 0.20 the mean** | C2 |
| **σ_R ladder 0.878 → 1.005** | *"rises MONOTONICALLY … every correction makes it harder"* | ⛔ **NOISE: 0.62 SE** by this document's own `SE(s)`, and **t = 0.82** on a proper two-sample test against the derived complement (n=124, σ 0.811) | C3 |
| σ_R, corpus-vs-probe gap (5.93 SE) | real | ✅ **UNCHANGED — still real.** Item 2″ is still the right response | C3 |
| **ρ̄ as a function of m** | *"could rise with concurrency"* (Q7-2) | ⛔ **FLAT in m** — `ρ̄ ≈ β̄²σ²_mkt/σ²_total` is a factor-share identity. What asymptotes is diversification at `1/ρ̄` ≈ **5.3 bets** | D2 |
| **the breadth lever** | slot count / capital / the 2021–23 back-fill | ⭐⭐ **HOLD PERIOD.** 9 slots × 3-day holds = **298** effective obs/yr vs **109** today; `250/hold` multiplies while `m/(1+(m−1)ρ̄)` saturates | D2 — and this answers Q7-4 |
| **the IC→return law** | `IR ≈ IC·√BR` (§4.5) | ⛔ **WRONG LAW for a gated tail selector.** Use `E[excess\|selected] ≈ IC·σ_cs·E[z\|selected]`, `E[z]` = **2.268** at a 3% rate ⇒ **IC 0.02 ≈ break-even/trade, IC 0.04 comfortably positive** | D3. §4.5's "not investable" is a **turnover** diagnosis |
| **the honest cell's verdict** | *"UNINFORMATIVE — the evidence base is EMPTY, not negative"* | ⭐⭐ **P(positive net edge) = 0.4%–5.7%** across prior sds 0.03R→0.20R ⇒ **economic closure without statistical closure** | D4 |
| n for a Sharpe-1.0 net edge | — | ⭐ **1,198 trades = 9.6 yr** at 125/yr (859 = 6.9 yr for break-even) | D5 — decade-scale is **back** |
| **the equity-beta null** | ⛔ *"blocked — `index_ohlcv_1d` = 51 rows"* | ⭐⭐ **COMPUTED: equal-weight eligible-universe basket, 789 sessions, +0.0816%/day, t +2.06, +22.8%/yr.** 5-session null = **+0.088R** ⇒ **α = −0.137R…−0.172R** | C8 / §12.20. **`index_ohlcv_1d` was never the right instrument** |
| **`paper_tick_size`** | 0.05, one constant | ⛔ **WRONG GRID for sub-₹250 names since 2024** — on-₹0.05 fell 0.98 → 0.49 → **0.22** (2019/2024/2025) while >₹250 is unchanged. A ₹39 name is overcharged **~10 bps round trip = 0.064R at a 2% stop** | §12.19. **Changes a recorded number ⇒ before cycle 2** |
| **`σ_IC` per date** | — | ⚠ **0.10 `[ASSUMED]`** — enters at §12.15, inherited by every IC power number in both documents, **linear in it**. Pure-noise floor 0.063 at 250 names/date, 0.027 at 1,360. **MUST be an output of 3b, never an input** | C7 |
| **3b's horizon** | unstated | ⭐ **PRE-REGISTER 5d.** At 20d, SE(IC) 0.0159 ⇒ t 1.26 at IC 0.02 ⇒ **can only return INCONCLUSIVE** — KILL LINE 4's defect one level up | C7 |
| `factor_sweep`'s power | *"nothing survived"* read as a clean negative | ⚠ **it resolved only IC ≈ 0.05–0.07** — the TOP of its own 0.018–0.071 break-even band, derived from its **own** published day-block interval (SE(spread) 0.436%). ⛔ The audit's √5 route is wrong (`factor_sweep.py:271` already samples every 5th date); the **conclusion** stands | C7 |

### 16.1c ⭐⭐ Round-9 corrections to the card — these SUPERSEDE both §16.1 and §16.1b

⚠ **Precedence: §16.1c > §16.1b > §16.1.** Every row below was MEASURED this round on
`probe-185` / `probe-49`, not argued. ⭐ **Four published numbers are withdrawn and two of them
were the document's own headlines.**

| quantity | ⛔ previous value | ✅ **round-9 value** | sample | why |
|---|---|---|---|---|
| ⭐⭐ **mean holding period `T`** | ⚠ **never measured; assumed 5** | ⭐ **3.59 sessions** (median 5; **14.6% exit same-session**); **4.00** on the E3 cell | `probe-185` | §12.31a. Every per-day and fixed-horizon statement in the record was conditional on this |
| ⭐⭐ **the equity-beta null, on the trades' OWN windows** | +0.0816%/day × 5 = **+0.408% = +0.088R** | ⛔⛔ **PAIRED: −0.166% (BUY), −0.338% (E3) ⇒ −0.048R** | `probe-82` / `-49` | §12.31c. **The basket over the tradeable book's actual windows is NEGATIVE** |
| ⭐⭐ **α vs the drift null** | **−0.137R…−0.172R** ("the null roughly DOUBLES the deficit") | ⛔⛔ **WITHDRAWN. Gross paired excess = −0.0218%, t = −0.07 (BUY)** | `probe-82` | §12.31c. **Gross alpha on the tradeable book is indistinguishable from ZERO** — the loss is timing and cost, not selection |
| ⭐⭐ **the E3 cell** | never computed | ⭐ **n=49 · gross −0.1212R (t −1.26) · NET −0.1772R (t −1.84) · −0.2432R at 15 bps (t −2.52)** | `probe-49` | §12.31b |
| **σ_R on the reachable book** | ⚠ assumed to stay at 1.0050 | ⭐ **0.6712** | `probe-49` | §12.31b. Dropping w<2% removes the high-variance tail — **this is why both E3 predictions were too optimistic** |
| **`E[cost in R]`, reachable book** | +0.0573R `[derived]` | ✅ **+0.0561R** `[measured]` — 2% error, **confirmed** | `probe-49` | §12.31b |
| **net R, BUY (all windows, all w)** | **−0.2435, t −2.19** quoted as *"the net question is answered"* | ⚠ **the number stands for that cohort and the cohort is wrong** — it includes trades the order path refuses. **Quote the E3 row instead** | `probe-82` | §12.25 / §12.31b |
| **date-clustered SE on the net mean** | ⚠ unverified (ChatGPT §6 demanded it) | ✅ **verified: every t moves by ≤0.06.** RVOL collapsed under clustering because it is a per-DATE regressor; a per-trade mean does not | `probe-49` | §12.31b |
| ⭐⭐ **stop-width contrast, third unit** | *"`1/w` explains 116% of it"* | ⭐ **R −0.386 (t −1.55) → raw % −0.262 (t −0.78) → excess vs basket +0.069 (t +0.17).** Decays and **flips sign** | `probe-185` | §12.31d. `1/w` **and** `drift×T`, not `1/w` alone |
| **`d(T)/dw`** | ⚠ never measured | ⭐ **+0.3844, SE 0.0574, t = +6.69** | `probe-185` | §12.31a. The premise of the third mechanism, measured. **Structural fact ⇒ no DSR bar** |
| **"independence of `ret` and `w` is MEASURED"** | asserted from t = +1.07 | ⛔ **WITHDRAWN — it is a NON-REJECTION.** ~25% of the slope is drift×T (predicted +0.0264, measured removal +0.0298) | `probe-185` | §12.31d |
| ⭐ **the four rival ranking keys** | ⚠ untested | ⛔ **ALL ≈ 0.** conf −0.018 (p 0.807) · raw sum +0.054 (p 0.465) · breadth +0.030 (p 0.691) · concentration −0.044 (p 0.555) | `probe-185` | §12.31e. **The normalizer is not the culprit; the closure covers the factor set** |
| ⭐ **the `choppy` display filter** | ⚠ a governance item | ⛔ **SELECTS NOTHING: contrast −0.0001, t −0.00, p 0.999** — and it hides **67%** of the offered set | `probe-185` | §12.31e ⇒ **delete it** |
| ⭐⭐ **₹/day vs the basket** | ⚠ never computed | ⭐ **−19 to −56 pp/yr (BUY) · −30 to −63 pp/yr (E3)** net of explicit charges; −39…−90 with 15 bps/leg. ⚠ **range = aggregation, not uncertainty** | `probe-82` / `-49` | §12.31f. ⭐ **THE headline** |
| **posterior, drift-inclusive** | *"under 2% at any prior"* (round 9) · 0.4–5.7% vs break-even (round 8) | ⭐ **vs cash 12.7–35.3% · vs break-even 1.0–4.3% · vs break-even + PAIRED basket 10.8–25.2%** | `probe-49` | §12.31g. ⚠ **The prior belongs on the GROSS mean; costs are known and must not be shrunk** |
| **`paper_tick_size` artifact** | 0.064R at a 2% stop | ✅ **0.0513R** — 0.064R is the TOTAL wrong-grid cost; the artifact is the **EXCESS** over the true grid | `[derived]` | §12.30b (Kimi C6) |
| **tick-bug blast radius** | *"lands on exactly the cohort carrying §12.1, §7, §12.10b"* | ⛔ **WITHDRAWN — `_round_tick` exists ONLY in `paper_broker.py` (3 call sites) and `positions` = 0. It contaminates NO number in this document** | `[code]` | §12.30a |
| **"MDE"** | `2.8016·SE at 80% power` | ✅ unchanged as a value; ⭐ **now requires `alpha · sidedness · power · SE-flavour` alongside it.** One-sided at 80% is 2.487·SE | — | §12.30d |

⭐ **AND THE NEW MECHANICAL RULE, earned twice this round — the sample-tag rule in the TIME dimension:**

> ⛔ **A BENCHMARK MEASURED OVER ONE SET OF SESSIONS MAY NOT BE SUBTRACTED FROM A RETURN MEASURED
> OVER A DIFFERENT SET. PAIR IT, OR DO NOT SUBTRACT IT.**
> §12.20a violated it (789 post-gap sessions × an assumed 5-day horizon, subtracted from trades
> with a 3.59-session mean hold), and round 9's own D1 inherited the violation while diagnosing a
> different one. **This is the eighth instance of the sample-tag family and the first in time
> rather than in population.**

### 16.2 Per-reviewer notes

**These are written from five rounds of evidence, not impressions. Each includes the specific
instances, so they can be checked.**

**ChatGPT — the estimand thinker. Best at "you are measuring the wrong quantity."**
Your standout contributions are the ones nobody else reached: **R4-15, that IC within gate-passers is
a collider** (gate-passage is a function of the factors, so conditioning on it induces spurious
association) — the best single statistical contribution of five rounds, and both other reviewers said
so independently. Also hazard curves and *"a 2–5 day strategy masquerading as a 30-day one"*, capital-
time economics, effective breadth, the three-layer null, the feature-lineage table, and the CA
over-filtering objection. ⚠ **Two of your round-1 points were rediscovered and credited to others
because I adjudicated in bulk — that was my error, now corrected in §13d.**
**Your characteristic failure is arithmetic under a correct framing.** R4-2 was the right instinct
(the benchmark must carry the hurdle's dependence assumption) carrying the gross/net error that R5-1
then had to fix. R5-15 applied the CAS DP figures to the swing book — wrong by 5×. **Ask for one
worked number before shipping a framing**; your framings are the best on the panel and they deserve
arithmetic that survives.

**Claude — the arithmetic auditor. Best at "recompute that claim."**
You have twice caught this document failing to propagate a correction it had already accepted
(R2-11 → §12.5 → R4-1), and in round 5 you overturned its central conclusion on a units error nobody
saw in five rounds. **R5-4 — deriving CA factors from Kite-adjusted ÷ our unadjusted series — is the
most practically valuable idea anyone has contributed**, converting a procurement blocker into seven
minutes of API calls. R4-3 (cycle 2 as a paired calibration) is the only genuine reframe of round 4.
⚠ **Your characteristic failure is that your own arithmetic is not exempt** — R5-17 put effective
breadth at +33% where the measurement is +20%, using a formula we both agree on. And your framings
sometimes over-reach where your numbers are right: "the answer is fixed by arithmetic" licensed a cut
that R5-1 then showed was premature. **Evaluate before asserting a magnitude, the same way you ask
this document to.**

**Kimi — the governance conscience. Best at "does this obey its own rules, and does the data exist?"**
Your two highest-value catches are both meta: **R2-2** (our own counter-evidence carried the
contamination we diagnosed in everyone else's) and **R2-6** (no kill lines — which turned out to apply
to the reviewing process itself). In round 4 your two *data questions* blocked two plan items by
query, which is a better outcome than an unblocked plan running on absent data, and in round 5 the
**programme sunset** and the **un-gating of the holdout freeze** are process fixes nobody else
proposed. ⚠ **Your characteristic failure is arithmetic, twice now.** R4-25 compared an MDE against an
SE, double-counting a factor of 2 and inflating a dependence premium from 1.046× to "2×". R5-16 put
effective breadth at +6% where it is +20%. ⭐ **Note that in R4-25 your conclusion was still right** —
Claude reached it correctly by a different route — which is why §15.4.3 now says to attack a
derivation and its conclusion separately. **Keep the governance questions; show the working on any
number.**

**Gemini — the panel keeps you (user ruling), and here is how to be useful.**
Your one adopted contribution across five rounds is **R4-24**: high statistical power over a
heterogeneous mixture can hide *factor decay*, which is distinct from the estimand argument the others
made. That is a real observation. ⚠ **Your characteristic failure is asserting formulas and
architectures without evaluating them once.** Four instances: an injection script whose t-statistic
was computed on `np.random.normal` placeholder data; `IC_min = cost/(breadth × σ_R)`, which does not
type-check and returns values 4–100× too permissive; a recommendation to pivot to ETFs "where flat DP
charges don't destroy net expectancy" when `fees.py:228` charges an ETF delivery sell identically; and
a self-credit for pivot-window arithmetic that was itself wrong. **The prescription is narrow and it
would change your value on this panel completely: pick ONE number from §16.1, plug it into whatever
you propose, and print the result.** If the result is dimensionally odd or off by an order of
magnitude, that is the signal. You reach conclusions the others sometimes miss; the gap is verification.

**Perplexity — absent since round 1, and its round-1 contribution was the frame everyone else built on:**
the selection-versus-timing decomposition, which became the two permutation nulls. If it rejoins, that
decomposition is the kind of contribution to ask it for.

### 16.2b Per-reviewer notes — round-7 addenda

**These append to §16.2 rather than replacing it. Every instance is checkable.**

**Claude — the arithmetic auditor, and in round 7 also the best structural reader.**
⭐ **Finding D asked the most valuable question of any round since R5-4.** Six rounds and
twenty-five reviews walked past the largest number in the denominator chain — 60.8% of gate-passing
swing panels die at the level stage — and you were the only source to ask what happens to them. It
measured **+0.16R in favour of the discarded cohort** under two independent rules (R7-C) — ⛔ **and
then the gap filter took the effect away** (+0.09R, t 0.69, reversing on the clean tradeable book;
R7-K). ⭐ **The credit is undiminished and belongs to the question, not the number:** the largest
filter in the pipeline is now measured, and the answer is "not anti-selective", which is a real result
and closes a suspect. ⚠ Note also that **your Kelly prediction was right on the honest sample** and my
contrary claim was the one that had to be withdrawn. Your
Finding A was right and the mechanism it implies (σ cancels in the ratio) made it sharper than you
stated it. Your Finding C forced the continuous estimator, and **the result vindicated your method
and refuted your expectation** — the negative is now properly powered. And the ex-date third answer
(R7-1) dissolved a question two rounds had treated as open.
⚠ **Your characteristic failure remains scope creep at the framing level, not arithmetic.** "That
single refactor retires nine plan items" is the kind of claim that licensed a premature cut in round
5; `backtest/engine.py` is FROZEN, so the kernel refactor needs sign-off, an §8 regression and
regenerated Rust fixtures — it is not a week. And you named the wrong blocker on un-truncation,
as every prior round did. **Keep doing exactly what Finding D did: pick the biggest number nobody
has interrogated and ask what is on the other side of it.**

**Kimi — the governance conscience, and in round 7 the most useful single catch.**
⭐ **Catch 1 is the sharpest catch of the round** and it is your third meta-catch to land: the
document accepted ρ̄ = −0.013 and left §12.9 computing at 0.5. ⭐⭐ **And then you did something
better than being right — you asked for the stress case (ρ̄ = +0.2) on the grounds that ρ̄ at 9 slots
was unmeasured, and the stress case turned out to be the REAL case** (long-only ρ̄ ≈ +0.19,
R7-A2). Your own ×1.62 is the number the plan now uses, not your ×3.26. That is the best example on
this panel of a reviewer's caveat outperforming their headline. Catch 4 (the card) and Part 6 (the
diff-verified card) are now merged into §16.1's enforcement rule.
⚠ **Your characteristic failure is arithmetic, and round 7 is the third instance — this time you
committed the exact error Claude was diagnosing four paragraphs earlier.** Catch 2's closing
"t ≈ −3.3" divides the **corpus** mean by the **probe** σ; with the corpus's own σ it is −1.94, the
published number. Derivation in §13f. ⭐ **And your conclusion was still right** — the direction
split mattered, enormously — which is the R4-25 pattern again and exactly why §15.4.3 exists.
⚠ Q7 was **refuted by measurement**: the 80–84 dip is worst in both directions (R7-B2).

**ChatGPT — the estimand thinker, and now also the systems reader.**
⭐ **§7 is your best structural contribution of the exercise** and it converged with Claude D and
Kimi Q8 from an unrelated direction: a kill line cannot close a feature family using an endpoint
measured three stages downstream of the feature. KILL LINE 3 is now 3a/3b because of it (§12.15).
⭐ **§11 found the first genuinely new RAIL any review has produced** — no portfolio cash constraint
exists, and three slots at the median stop need 120% of capital (§12.14). §10's causal chain
(capital → granularity → risk allocation → breadth) is the correction §12.13a needed. §12's
`DecisionSnapshot` chain is now the ledger schema. §18 is correct and has been acted on.
⚠ **Your characteristic failure has shifted from arithmetic to SCOPE, and §18 is your own diagnosis
of it.** §24's twenty-audit interrogation is 3–4× the capacity that forced §13's CUT, in the same
response that warns the document is becoming "poor operational specification." Both cannot be acted
on; §18 won. ⚠ And §3's portfolio-dependence fear did not materialise in the coordinate you chose —
all three units measure ≈ 0 — **because risk-first sizing makes cash ≈ R × constant, an identity you
did not invoke.** The mechanism was direction, not unit. **Right question, wrong coordinate: still
worth more than most sources' right answers.**

**Gemini — the prescription worked, once, and that is progress worth recording.**
⭐⭐ **Item 4 is your first runnable contribution since R4-24, and it did more than any other
reviewer point this round.** Controlling the stop-width gradient for ATR% was a control nobody had
thought to add to the one positive result that most needed it. Three outcomes, all from one request:
**(a) your own hypothesis was refuted** — ATR% is insignificant (t = −0.43) and the gradient survives
it intact; **(b) it partially refuted one of OUR standing findings** — the gradient is t = +2.30 in R
and **+1.07 in raw %**, so the 2026-08-25 stop-width result is substantially a denominator effect;
**(c) it surfaced `RVOL-20` at t = +3.67, the only coefficient in seven rounds to clear our own
t ≈ 3.6 bar** — which our own §12.10b rule then disqualified, because in raw % it is t = −0.28
(R7-J). **That is precisely what §16.2 asked for: one number, plugged in, printed.** Nothing on this
panel has produced more per unit of effort.
⚠ **And three of your five items rest on state you did not check** (R7-10/11/12): the pytest DB leak
was fixed on 2026-09-07 **and the fix is in the document you were reviewing**; the CA-ratio and
stride-1 requests need 2021–2023 bars that **do not exist**; the defect-#4 fix cites the wrong line
and proposes the wrong repair. ⭐ **The pattern across six rounds is now unmistakable and it is not a
reasoning problem — it is a verification problem.** Your table of measured realities at the top of
round 7 was accurate, because it quoted this document. Everything you added from your own model of
the system was wrong, except item 4, which asked a question instead of asserting a state.
**Prescription, narrowed further: ask, do not assert. One question per round, phrased as a
measurement we can run.**

**Perplexity — absent since round 1.** Its selection-versus-timing decomposition is still the frame
the two permutation nulls rest on, and R7-C has just made the *stage* decomposition urgent. If it
rejoins, that is the contribution to ask for.

### 16.3 What to attack next

⚠ **§16.3's previous three items are CLOSED.** Items 1 and 2 were "ρ̄ is assumed" and "half the
friction term is assumed": ρ̄ is now **measured twice** (mixed −0.013, long-only +0.19) and the
slippage residual is **proven unmeasurable retrospectively** (`orders` = 0 rows). Item 3, the
corpus/deployed estimand gap, is now the *whole* subject of §12.13b and §16.1's sample-tag rule.

**The three that replace them — each is one measurement, and each can change a decision:**

1. ⭐ **σ_R on the 1,975-trade corpus, split by classification and by direction.** It has never been
   measured; 1.489 is back-derived from a t. §12.13b lists five structural reasons the probe's 0.878
   cannot be transferred, and **mechanism 1 — the corpus is swing + positional, and positional σ_R is
   1.844–2.088 — plausibly closes the whole gap on its own.** One flag on
   `entry_confirmation_study.py`. **Everything in §12.10a and §16.1 that combines a σ with n=1,975 is
   waiting on this.**
2. ⭐ **ρ̄ as a function of concurrency, on a long-only book.** `1 + (m−1)ρ̄` is a pairwise form; a
   long-only equity book's dependence is a shared *factor*, so ρ̄ should **rise** with slot count
   rather than stay fixed (Q7-2). If it does, effective breadth has an asymptote and §4.5's breadth
   argument gets a mechanism. **Every capital conclusion in §12.9 and §12.13a rests on the answer.**
3. ⛔ ~~The level stage as a selector, properly powered.~~ **CLOSED THE SAME DAY** — the gap filter
   removed the effect (R7-K). ⭐ **What replaces it: the equity-beta NULL, computed.** §4.2's central
   claim is that we have *negative alpha, not zero alpha*, because the correct null for a 100%-long
   beta-0.92 book in a rising market is strongly positive. **That null has never been computed**, and
   it cannot be while `index_ohlcv_1d` holds **51 rows** — so the redone index backfill is now the
   gating item for the document's most consequential interpretive claim (§17 Q7-1).

⛔ **And what NOT to attack:** the document's consistency. Seven rounds have exhausted it, and §15
plus §16.1's sample-tag rule now handle the recurrence mechanically. **The marginal value of review
breadth is negative** — §13f's scoreboard shows 4 of 37 round-7 points changed a decision and 5 were
refuted by a query the reviewer could have asked for. See §17.

## 17. ⭐ QUESTIONS BACK TO THE PANEL (asked after round 7) — ✅ ALL FOUR ANSWERED BY ROUND 8; see §17b

✅ **ALL FOUR OF THESE WERE ANSWERED BY ROUND 8 — the outcomes are tabulated in §17b, and two of the four
turned out to rest on premises of mine that were false.** Kept in full because the questions are what
produced the answers.

⚠ **Read §13f first.** Round 7 produced 37 reviewer points and **four** of them changed a decision.
The binding constraint on this programme is not insight — it is that **one item has shipped as code
in 50 days and the sunset is 2026-10-31.** So this is not an invitation to review the document again.
⛔ **Do not re-audit consistency, do not propose indicators, do not restate the plan.** §15 lists what
has already been rejected and why; §16.1 is the shared arithmetic.

**The standing rule from round 6, now hardened: a round only happens if a probe runs with it**
(Claude's phrasing, adopted). If your answer cannot be checked against a number in this document or
one you ask us to produce, it is not a round-8 contribution.

### Q7-1 ⭐ The BUY-only book is t = −0.94. Which of two verdicts does that license?

`[measured]` n = 82, mean **−0.0992R**, SE 0.1057, MDE @ t=2 = **+0.211R**. The tradeable book is
**not distinguishable from zero and negative in expectation**, and it cannot resolve anything smaller
than 0.21R.

**The question is not "is there an edge".** It is: **which of these is the correct scientific
statement to carry into the Week-4 decision, and what distinguishes them with the data that exists?**

- **(i) NO RESULT.** n=82 with MDE 0.211R against a Sharpe-1.0 benchmark of 0.130R — the test is
  under-powered by 1.6× and licenses nothing. The programme's evidence base is then **empty**, not
  negative, and §12.10a's "detectability is retired" is wrong for the only book we can trade.
- **(ii) A NEGATIVE POINT ESTIMATE UNDER A CORRECT NULL.** §4.2 established the correct null for a
  100%-long, beta-0.92 book in a rising market is **strongly positive**, so −0.099R against a
  positive null is informative *even at t = −0.94*.

⛔ **AND R7-K SETTLED IT AGAINST US WHILE THIS SECTION WAS BEING WRITTEN.** On clean windows ×
long-only the cell is **n = 61, −0.0843R, t = −0.66, σ_R 1.0050, MDE +0.29R** — so the honest
tradeable estimate cannot resolve anything under 0.29R and **(i) NO RESULT is the correct reading on
present data.** ⇒ **the question narrows to (ii)'s prerequisite:** §4.2's claim that we have *negative
alpha rather than zero alpha* needs a computed equity-beta null, and **the index history is 51 rows**
(R7-G2). **Is there a defensible way to state (ii) quantitatively without the index series, or is
§4.2 unquantified until the index backfill is redone?** A "use the risk-free rate" answer will not do
— the null is an equity-beta null. ⚠ **And note what (i) costs us: if the evidence base for the
tradeable book is empty, then KILL LINE 3 cannot fire on this sample either, in either direction.**

### Q7-2 ⭐ ρ̄ is +0.19 long-only and −0.013 mixed. Does effective breadth scale with slots at all?

`[measured]` R7-A2. Long-only overlapping trades are positively dependent (inflation 1.19–1.23× at
m = 2.08); the mixed book's ρ̄ ≈ 0 was a directional cancellation. Kimi's stress case turned out to
be the real case: **₹3L buys ×1.63 effective observations, not ×3.26 and not +20%.**

**The question:** ρ̄ was measured at **concurrency 2.08**. Every capital conclusion needs ρ̄ at
**9 slots**, and we cannot measure it without running a 9-slot book. **Is `1 + (m−1)ρ̄` even the right
functional form for a long-only equity book, where the dependence is a shared *factor* rather than a
pairwise correlation?** A one-factor decomposition (`ρ̄ ≈ β²σ²_mkt / σ²_total`) would make breadth a
function of β and residual variance rather than of slot count — and would predict ρ̄ **rises** with
slots, since more names means a larger share of common factor. ⚠ **If that is right, effective
breadth has an asymptote and no amount of capital crosses it** — which is §4.5's breadth argument
with a mechanism attached. **Is the one-factor form the right instrument, and what is the cheapest
measurement that distinguishes it from the pairwise form on 185 trades?**

### Q7-3 ⭐ Claude's Finding D measures +0.16R at t = 1.5. What is the correct next test?

`[measured]` R7-C: the level stage discards 60.8% of gate-passing swing panels, and the discarded
cohort **outperforms the kept cohort by +0.16R** under two independent fallback rules, paired by
entry date, with the predicted wider stops. **t = 1.43 and 1.54. MDE = +0.22R.**

⛔ **UPDATED THE SAME DAY: the effect did NOT survive the gap filter (R7-K).** Clean windows give
**+0.0953R (t 0.69)** and **+0.0887R (t 0.66)**, and on the clean tradeable book it **reverses**
(rejects BUY −0.1180R vs accepts −0.0843R). ⇒ **the +0.16R was substantially gap contamination plus a
shorts effect, and we are not asking you how to chase it.** The question that survives is sharper and
smaller: **given that the largest filter in the pipeline is now measured as NOT anti-selective at
n ≈ 220, is there any remaining reason to prefer a fallback stop over the pivot stop — or is
`compute_levels`' stop side simply exonerated?** ⚠ **We are inclined to say exonerated and close it.**
Argue otherwise only with arithmetic. The routes we considered, kept for the record:

- **(a) More data.** Stride 1 + `--clean-only` takes the paired sample from 56 shared days to
  perhaps 400. Cheap. ⚠ **But stride 1 adds overlapping panels of the same name** — does the paired
  day estimator survive that, or does it need a name-clustered SE?
- **(b) A better estimator.** The paired-by-day contrast throws away the within-day pairing of
  *identical panels*. Every rejected panel has a date **and a name**; accepted and rejected panels
  are frequently the same name days apart. **Is a within-name fixed-effects contrast the right
  estimator, and what does it cost in n?**
- **(c) Pre-register it as 3b's first test and accept the power it has.** ⚠ Our objection to our own
  route: publishing an MDE of 0.22R against an effect of 0.16R and running anyway is exactly KILL
  LINE 4's original defect.

**And the substantive question underneath:** if the level stage is anti-selective, is that
**evidence about the scorer** (its information survives only in the panels the level stage happens to
keep) or **evidence about `compute_levels`** (a stop-placement rule that discards good trades)?
⚠ **D5 already tested and closed the target geometry and found no lever.** The *stop* side has never
been tested, and `compute_levels` is FROZEN. **What distinguishes these two, measurably?**

### Q7-4 ⭐ §12.12 removed the breadth lever. What replaces it?

`[measured]` `ohlcv_1d` has a **922-day hole (2020-12-23 → 2023-07-03)**; 1,097 sessions exist, not
~1,730. Un-truncation yields **n ≈ 2,662** on the corpus's bar-50 walk and **exactly 0 additional
panels** at a 300-bar window — not the 4,300 the plan's MDE rested on. **33.2% of round 6's panels
were scored across the hole.**

§12.5 named three levers that can move the answer: **friction, σ_R, breadth.** Round 7's state:
friction is half-assumed and unmeasurable retrospectively; σ_R is measured on the wrong population
and un-transferable (§12.13b); **breadth just lost its cheapest source.** What remains:

| source of breadth | n gained | cost | blocker |
|---|---:|---|---|
| back-fill 2021-01 → 2023-06 | ~2,300 | **days of ingestion** | none known — bhavcopy archive, same shape as the 2026-09-07 recovery |
| the level-stage rejects (R7-C) | **+288 today** | one re-run | none |
| un-truncate as planned | **0** | — | ⛔ the bars |
| stride 1 on the existing window | ~1,800 | hours of compute | overlapping panels of the same name |

**The question we actually want answered: is the 2021–2023 back-fill worth days of ingestion, given
that everything it buys is more n on an estimator whose population we have just shown does not
transfer to the live book?** ⚠ Our own prior: **no** — R7-C's 288 trades and a long-only re-baseline
are better value per hour, and more n on a 56%-short corpus converges on a quantity nobody can
trade. **Argue the other side if it is arguable, with the arithmetic.**

### One thing we will NOT ask for again

⛔ **A list. Of anything.** Round 7 produced 37 points across four sources; §13f's scoreboard shows
**4 changed a decision and 5 were refuted by a query the reviewer could have requested.** The
marginal value of breadth in *review* is now clearly negative, which is the same finding
§12.10 produced about the programme's own gating. **One argument, with one number in it, beats twenty
framings.**

---

## 17b. ⭐ ROUND 9 IS NOT REQUESTED — and here is the standing invitation instead

⛔ **Do not send another round.** §13g's arithmetic: **4 of 37 round-7 points and 3 of 29 round-8
points changed a decision.** Round 8 was worth it for exactly one reason — **one source recomputed
instead of reading** — and that source's own closing line is the right standing rule:

> *"a round only happens if a probe runs with it."*

### The four round-7 questions, and what happened to them

| | status |
|---|---|
| **Q7-1** — does t = −0.66 license "no result" or "negative against a positive null"? | ⭐ **ANSWERED, and both branches were wrong.** The null is **+0.088R** (computed, §12.20) and the posterior gives **P(positive net edge) 0.4–5.7%** ⇒ **option (iii): economic closure without statistical closure** |
| **Q7-2** — does ρ̄ rise with concurrency; is `1+(m−1)ρ̄` the right form? | ⭐ **ANSWERED: ρ̄ is FLAT in m** (factor-share identity), the asymptote is real at `1/ρ̄` ≈ 5.3 bets, and **hold period is the bigger lever** (D2) |
| **Q7-3** — what is the right next test of the level stage? | ⭐ **DISSOLVED.** The effect did not survive the gap filter and the gradient is arithmetic ⇒ **the stop side of `compute_levels` is exonerated and the question is closed** |
| **Q7-4** — is the 2021–23 back-fill worth days of ingestion? | ⭐ **ANSWERED: NO**, and the replacement lever is **turnover**, not observations (D2). Our stated prior was right |

⇒ **All four are closed. That is what a round is supposed to do, and it is why there is no Q8 list.**

### The standing invitation, deliberately singular

**If you want to contribute to the 2026-10-31 decision, run one of E1/E2/E3 (§13.8) or tell us which
number in §16.1 you can refute.** Everything else is now either measured, dropped, or waiting on E2.

⚠ **And one request that applies to every source, earned five times over:** ⭐ **before asserting that
something is missing, broken or blocked, check whether the document you are reading already answers
it.** Round 8's three sources between them re-asked the `conftest` guard (shipped 2026-09-07 and
described in the document), the portfolio cash check (§12.14, written in round 7), the raw-%/ATR
re-report (R7-J, run in round 7), and re-asserted a level-stage claim R7-K had already withdrawn.
**That is four of twenty-nine points spent on answered questions**, and the reviewing is where the
programme's remaining time is going.

## 17c. ⭐ AFTER ROUND 9 — the invitation is CLOSED, and the reason is arithmetic

⛔ **No round 10. Not "probably not" — closed.**

⭐ **§17b's rule ("a round only happens if a probe runs with it") worked and should now be
retired along with the rounds themselves.** Round 9 produced 7 decision changes from 5 sources —
a better rate than rounds 7 or 8 — **and every one of the seven came from a claim that a probe
could test.** The other ~60 points were architecture already adopted, questions the document
answers, or restatement.

⚠ **The decisive arithmetic is that the remaining questions are no longer REVIEWABLE.** B1–B8 are
builds and measurements, not arguments: deleting two filters, adding a cash rail, a tick table, a
span guard, one positional re-run, one three-estimand IC pass, and the ledger. ⭐ **No reviewer,
however good, can shorten that list — and round 9 demonstrated the converse, that a reviewer who
recomputes can only help by pointing at a probe.**

⇒ ⭐ **What the panel is thanked for, precisely: nine rounds produced ONE surviving strategy
finding (there is no measurable edge) and roughly TWENTY surviving instrument findings.** The
instruments are the deliverable. **The panel is closed at round 9.**

### The one thing a future source may still send

**A refutation of a §16.1c row, with the recomputation attached.** Nothing else.

---

# PART VI — ⭐⭐ ANSWERS TO EVERY QUESTION THE PANEL ASKED (round 9)

**Status key:** ✅ **ANSWERED** (with the number) · ⏸ **QUEUED** (agreed, in B1–B8) · ⛔ **BLOCKED**
(a fact makes it unanswerable) · ⚠ **REFRAMED** (the question contains a false premise, stated).

⚠ **Nothing here is a promise. Every ✅ row points at a measured number in §12.31 or §12.32, and
every ⏸ row points at a numbered build in §13.10.**

## 18.1 ChatGPT — six verification packages, and its final eight-row table

| # | its package | answer |
|---|---|---|
| **1** | **E3 — the one final tradeable economic cell, in ONE pipeline** | ✅ **RUN (§12.31b).** `clean × BUY × w≥2%`, **n = 49**: gross −0.1212R (t −1.26) · **net −0.1772R (t −1.84)** explicit · −0.2432R (t −2.52) @15bps · −0.3092R (t −3.19) @30bps · net raw % −0.8331 (t −1.69) · net ÷ATR20 −0.3510 (t −1.74) · net ₹ −307.50 (t −1.67) · **mean hold 4.00 sessions** · median stop 5.20% · `E[cost in R]` +0.0561. ⭐ **PRIMARY inference = date-clustered** (trades share entry sessions); it moves every t by **≤ 0.06**, so the choice does not matter here — **which is itself the answer to package 6's worry** |
| **2** | **Verify the Bayesian decision — same dataset, dependence-adjusted, state what is subjective** | ✅ **RUN (§12.31g), and it changed the answer.** ⚠ **First, a fix of our own: the prior belongs on the GROSS mean — costs are KNOWN and must not be shrunk.** On E3's gross (−0.1212R, iid SE 0.0959, clustered 0.0991) against hurdles from the **same 49 trades**: `E[cost]` +0.0561R and the **paired** basket **−0.0478R** ⇒ break-even+basket = **+0.0083R**. **P(> cash) 12.7–35.3% · P(> break-even) 1.0–4.3% · P(> break-even + basket) 10.8–25.2%.** ⛔ **Round-9 Claude's "under 2% at any prior" is refuted** — its hurdle used an unpaired drift. **Empirical: μ̂, SE, cost, basket. Subjective: the prior sd alone** |
| **3** | **E2 — trace the score that is actually deployed; can history reproduce it?** | ✅ **ANSWERED, and the blocker you assumed is gone (§12.32).** `[code]` **26 registry entries, 325 declared weight**, of which the mean weight that **scores** is **30.6 (9.4%)**. ⛔ **`FII_DII_FLOW` scores on 0 of 487 panels** (because `fii_dii_daily` = 4 rows) — **so the non-price term is already inert on LIVE panels, and E2 can test the SHIPPED scorer rather than a "price-only variant."** ⚠ Two other factors are also structurally dead: `DOW_TREND` (weight **20**, the heaviest) and `MARUBOZU`. ⏸ **The IC test itself is B6, re-specified as three estimands per your §16** |
| **4** | **Selection / picker causal test — what does ρ = −0.018 actually test?** | ✅ **ANSWERED precisely, and you were right to force the distinction.** It tests **(D) resolved-trade survivors, within gate-passers** — so it licenses *"the deployed RANKING key carries no measured information"* and **NOT** *"the human picker destroys value."* ⛔ **The human's choices are unrecoverable: `positions` = `orders` = 0 (destroyed 2026-09-07) and the offered-set → selected-set mapping was never logged even when rows existed.** ⇒ **B8 is the only unblock and it only starts the clock forward.** ⭐ **Cheapest discriminator among your four causes: B6's 3a vs 3b separates *bad generator* from *bad gate*; B7's hazard curve separates *bad level stage* from *bad horizon*; the human stays unmeasurable** |
| **5** | **Execution / parity contract, and verify the tick schedule** | ✅ **The matrix is §12.21c** (already assembled in round 8). ⭐ **Round 9 corrected its tick row's blast radius: `_round_tick` exists ONLY in `paper_broker.py` — 3 call sites — so the bug contaminates NO research number** (§12.30a). ⚠ **And your instinct not to hardcode is adopted verbatim:** the measured phase-in (on-₹0.05 **0.98 → 0.49 → 0.22** across 2019/2024/2025) is a **staged rollout**, so **B3 reads a `valid_from`/`price_lo`/`price_hi`/`tick`/`source` TABLE**, never a constant and never `0.01 if price < 250` |
| **6** | **Research-platform invariants — nine schemas, do not implement** | ⏸ **QUEUED as B8**, and your three additions (`ExperimentManifest`, `DataSnapshot`, `UniverseSnapshot`) were **already adopted in §12.21e** and are now the shape of the build. ⭐ **Every node carries `code_commit · spec_version · experiment_id · data_version · created_at`** — which is your point that the sample-tag rule must become a software invariant rather than human discipline. ⚠ **Round 9 supplied the eighth violation to justify it, in the TIME dimension (§16.1c)** |
| **§4** | **"MDE" needs `alpha · sidedness · power · test_type · SE_definition`** | ✅ **ADOPTED as a schema rule (§12.30d).** ⚠ Bounded honestly: it changes nothing operationally (+0.417R two-sided vs +0.371R one-sided on the honest cell; no plausible edge lies between). **Adopted because this exact ambiguity produced the `2·SE` error the card corrected one round earlier** |
| **§30** | **Re-order the plan: E3 → E2 → E1** | ✅ **EFFECTIVELY ADOPTED.** E3 ran first (it was an afternoon), E1 is B5 and E2 is B6. ⚠ **Your decision tree is better than the one it replaced and is now §12.28's**, with one change: the `E3 bad + E2 good` branch is **"the pipeline destroys alpha"**, and §12.31c has already located a candidate — **entry timing**, not the level stage |

### ⭐ Your final eight-row table, answered from the measurements

| question | answer | confidence | evidence |
|---|---|---|---|
| **Is the configured BUY strategy economically viable today?** | ⛔ **No.** Net **−0.1772R (t −1.84)** explicit, **−0.2432R (t −2.52)** at 15 bps/leg, and **−19 to −56 pp/yr per rupee-day vs the basket it selects from** | **High** on the economics, **moderate** on the statistics | §12.31b, §12.31f · `probe-49` / `probe-82` |
| **Does the confidence score contain useful selection information?** | ⛔ **Not as a RANKING key, on resolved gate-passers: ρ = −0.018 (p 0.807), and no rival key does better** (raw sum +0.054 p 0.465 · breadth +0.030 · concentration −0.044) | **High** for the ranking, ⚠ **UNKNOWN unconditionally** | §12.31e · `probe-185` · **unconditional = B6/3a** |
| **Does the human picker add or destroy value?** | ⛔ **UNANSWERABLE.** `positions` = `orders` = 0; the offered→selected mapping was never logged | — | §18.1 row 4 · **B8 unblocks it forward only** |
| **Does the level stage add or destroy value?** | ⚠ **Not anti-selective, and not a lever.** R7-C's +0.16R did not survive the gap filter and **reverses on the clean tradeable book** | Moderate | §12.16 R7-C · R7-K |
| **Is the stop-width family real or denominator-induced?** | ⛔ **DENOMINATOR-INDUCED, twice over.** The contrast decays and **flips sign** as each mechanical term is removed: **R −0.386 → raw % −0.262 → excess vs the matched basket +0.069** | ⭐ **High — closed** | §12.31d · `d(T)/dw = +0.384, t +6.69` |
| **Is the backtest faithful enough to validate production?** | ⛔ **No, and it never claimed to be.** Zero fees, zero slippage, no rounding, no risk rule, no through-stop rejection, and it simulates a short side a cash account cannot hold | High | §12.21c |
| **Is the current ₹1L portfolio economically executable?** | ⛔ **No — and this is the one thing that could lose real money.** `Σ notional ≤ cash` **does not exist in code**; 3 slots at the median 5% stop need **120% of capital** | ⭐ **High — `[code]`** | §12.14 · ⇒ **B2, precondition for cycle 2** |
| ⭐ **What single measurement remains capable of changing the strategic decision?** | ⭐⭐ **B6/3a — the UNCONDITIONAL IC of the composite across the eligible universe at h = 5d.** ⭐ **Everything else is now measured, blocked, or a corner of a cell that has been computed** | High | §12.28 |

## 18.2 Kimi — R1 through R12

| # | its request | answer |
|---|---|---|
| **R1** | the document tail (§16.1b onward) | ⚠ **NOT REPRODUCIBLE — a transfer artifact.** The file is 4,500+ lines with §16.2, §16.3, §17 and §17b all present and always was. ⚠ **Consequence worth stating: its adjudication of §17's four questions was made without having read them** |
| **R2** | the scorer internals, exact code | ✅ **QUOTED IN FULL (§12.29).** `confluence.py:159-166`: `total_weight = sum(f.weight for f in factors if f.score != 0.0)` — **the denominator counts only factors that FIRED.** ⭐ **Your mechanism is confirmed in the code** |
| **R3** | the 15-factor inventory, weights, and which are historically reconstructable | ✅ **MEASURED (§12.32).** **26 registry entries, not 15** (pattern detectors are separate and only one can be selected). Full weight table there. ⭐ **All reconstructable terms are price-derived; the only non-price factor (`FII_DII_FLOW`) scores on 0 of 487 panels, so the reconstruction blocker you identified is real but INERT** |
| **R4** | a per-trade dump, 185 trades, all columns | ✅ ⭐ **BUILT — `--dump-trades` on `swing_dependence_probe.py`, 185 × 25 columns**, including everything you listed plus `T`, `bench`, `excess`, `er`, `wsum`, `nsc`, `wsc`, `top`. ⭐ **This one ask produced five of the round's adjudications, exactly as you predicted** |
| **R5** | the complete filter chain, panel → fill | ✅ **`[code]` TEN restrictions in the registry** (`restrictions.py:488-512`): `offmarket · regime · circuit · entry_quality · rr · sector_rs · market_regime · liquidity · chase · through_stop` — **plus the 2 undeclared display filters = 12 total**, of which **the corpus applies ZERO** and the order path applies 10 |
| **R6** | stop-width and holding-period distributions | ✅ **MEASURED (§12.31a).** E3 cell: **mean T 4.00**, median 5, **10.2% same-session**, mean w 5.20%, **E[1/w] 0.220**. Full book: mean T **3.59**, **14.6%** same-session, E[1/w] 0.597 |
| **R7** | does a committed E2 script exist; which estimand? | ⛔ **No script exists.** ✅ **And your C1 is ACCEPTED: E2 had drifted from 3b's pre-registered matched-tail contrast to a full cross-sectional IC.** ⇒ **B6 restores BOTH plus the collider, with the matched-tail contrast as the one that maps to the picker's job (§12.28)** |
| **R8** | does `factor_sweep` store per-date ICs? | ⛔ **NO — `[code]` verified, there is no `by_date`/`ic_t` structure.** ⚠ **So your cheapest suggestion does not work: `sd(IC_t)` cannot be retired today and MUST be an output of B6.** ⭐ **Asking was still right — it converted an assumption into a known unknown** |
| **R9** | git state of the scorer since 2026-07-03 | ✅ **`[git]` `confluence.py` last touched `ea4b06d`, 2026-07-04 — the freeze commit — and nothing since.** Corpus analysis began 2026-08-12, **five weeks later.** ⭐ **The "scorer is pre-registered" claim is VERIFIED, which is what makes B6 a test rather than a fit** |
| **R10** | `_round_tick`, its call sites, the charge stack | ✅ **ANSWERED and it settled a contradiction (§12.30a/b).** 3 call sites, `paper_broker.py` only. ⭐ **And your C6 is CORRECT: the artifact is the EXCESS (10.26 bps ⇒ 0.0513R at a 2% stop), not the total (12.82 bps ⇒ 0.0641R). §12.19b used both for one quantity** |
| **R11** | which harness produces cycle 2's "predicted" arm? | ⚠ **REFRAMED and the worry is justified.** §12.21c: the backtest is uncosted, the paper broker is fully costed ⇒ **a paired residual against the uncosted engine would be a cost-model validation wearing a calibration label.** ⏸ **B8's `ExperimentManifest` is where the predicted arm gets named; the near-expiry/choppy filters are removed by B1 before cycle 2 either way** |
| **R12** | the session calendar and coverage tables | ✅ **PARTIALLY (§12.23):** post-gap block **790 sessions, 3,129 names**, bars/name median 620 **p10 67**, and **65% of names below 95% coverage**; cross-section **46 → 250**. ⭐ **Your C8 consequence is ADOPTED: at 46 names the noise floor `1/√46` = 0.147 exceeds the whole 0.018–0.071 break-even band, so B6's power must be coverage-weighted.** ⏸ `nse_holidays` 2019–20 completeness is §12.22a (7 recorded vs ≥17) and only matters for the pre-gap block, which is dropped |
| **C5** | *"my prediction: E3 net ≈ −0.15R, t −1.1 to −1.4, not significant"* | ⚠ **HALF RIGHT — measured −0.1772R, t −1.84.** The mean was close; the `t` was not, because the prediction held **σ = 1.0050** and the reachable cell's σ is **0.6712**. ⭐ **Publishing it before the run was the correct methodology and is adopted as standard** |

## 18.3 Deepseek — eight requests

| # | its request | answer |
|---|---|---|
| **R1** | ⭐ which IC does E2 measure — and give all three | ⭐⭐ **THE BEST SINGLE POINT OF THE ROUND, ACCEPTED IN FULL (§12.28).** The collider framing is exactly right: the 70 gate is a threshold **on the same weighted sum the score is**, so IC-within-passers conditions on the estimator's own output. ⏸ **B6 emits all three — (a) unconditional, (b) matched-tail, (c) the collider labelled as one — with the four-branch decision tree pre-registered** |
| **R2** | propagate the drift null into every positive-looking cell | ✅ **DONE for every swing cell (§12.31c/d)** — and it did **more** than you expected: the paired basket is **negative** on the tradeable book, so it **refuted our own α** rather than deepening it. ⭐ **§12.1's positional cells are the remaining ones and they are B5** (the same three columns, same `basket_series` owner) |
| **R3** | instrument the human selector | ⛔ **BLOCKED, permanently for history.** See §18.1 row 4. ⭐ **Your framing — *"if the human picks near the top, the human is implementing an uninformative sort"* — is the right experiment and B8 is the only way to run it, forward only** |
| **R4** | the MFE/MAE hazard curve by day | ⏸ **QUEUED as B7, folded into B6's pass.** ⭐ **Round 9 already produced one slice of it and it is alarming: the `T = 0` cohort is 27 of 185 trades at mean R −0.7034 and a 14.8% win rate** (§12.31f) — **1 trade in 7 dies on the bar it opened** |
| **R5** | the factor correlation matrix and effective factor count | ⚠ **LARGELY ANSWERED WITHOUT IT (§12.32), and DOWNGRADED.** Four factors carry nearly every scoring event (PRICE_VS_EMA 70% · ADX 46% · MACD_HISTOGRAM 43% · RSI_LEVEL 36%) and **two of the top three are EMA-derived**, so effective dimensionality is plausibly **2–3**. ⭐ **Combined with §12.31e (no ranking key on the factor set carries information), the matrix would explain *why*, not *whether*.** ⏸ Queued behind B6 |
| **R6** | the turnover / IC frontier | ⏸ **QUEUED as a B6 follow-on, and it is the right question.** ⭐ Your reading of D3 is correct — `IC·σ_cs·E[z\|selected]` makes IC 0.02 roughly break-even *per trade*, so the failure is **annual**, i.e. turnover. ⛔ **Every cell of the frontier needs an IC we have not measured. It is downstream of B6 by construction** |
| **R7** | is `positional` a strategy or a holding-period descriptor? | ✅ **`[code]` THE CODE TREATS IT AS A STRATEGY — seven branch points:** `risk.py:107` and `:119` (sizing), `market_calendar.py:29` (30 trading days vs 5), `classifier.py:21/24`, `profit_lock.py:56` (its own ratchet params), `provisional.py:118`, `expiry.py:43`. ⚠ **And the evidence treats it as a label:** paired on identical panels the two rule sets are **not separable** (ΔR −0.120, t −1.47). ⇒ **Your framing is right and the mismatch is real.** ⏸ **B5 is the measurement that decides repair-vs-delete** |
| **R8** | reconstruction cost per data gap | ⚠ **PARTIALLY MOOT (§12.32).** ⭐ **FII/DII drops off the critical path entirely** — the factor scores on **0 of 487** panels, so back-filling it changes no score. **2021–23 is already DROPPED** (D2: hold period is the bigger lever). ⏸ **What remains is the CA table and index history, and neither gates any round-9 conclusion** |

## 18.4 Claude — G1 through G7

| # | its ask | answer |
|---|---|---|
| **G1** | re-specify E1 with the drift null and `T`, on BOTH samples | ⭐⭐ **ACCEPTED AND HALF-RUN.** The swing half is **§12.31d** — and it **confirmed your mechanism by measurement**: the contrast decays **R −0.386 → raw % −0.262 → excess +0.069** and **flips sign**, with **`d(T)/dw = +0.384, t = +6.69**. ⏸ **The positional half is B5.** ⚠ **One correction: your table's row label is inverted** — `drift·T/w` is **larger for tight** stops (+0.192R vs +0.075R), so it makes **tight** look better, not wide. Your prose ("opposite directions") is right |
| **G2** | recompute the net result in raw %, ATR and ₹ with the inflation | ✅ **RUN across five cohorts (§12.31b).** ⭐ **Your refutation is UPHELD on the cohort question and REFUTED on the conclusion:** `t = −2.19` is indeed the wrong cohort's number, **and the right cohort reads t = −1.84 explicit / −2.52 at 15 bps.** ⭐ **Your closed form predicted −2.202 against an exact −2.190** — right to 0.01. ⚠ **On your p99/max question: on `w ≥ 2%` the cost distribution collapses to mean 0.0561R, sd 0.0240 — the 5.935R tail is entirely sub-2% stops, so it is a leverage-point problem that the reachable restriction removes by construction** |
| **G3** | run E2 with the MFE/MAE surface in the same pass | ⏸ **QUEUED as B6 + B7, exactly as specified** — including `E[z\|selected]` as a measured output rather than the 2.268 normal-tail approximation. ⭐ **Your point (c) is the one that mattered: a hard gate at 70 on a bounded score whose passers have mean 77.8 / sd 5.8 is not a normal tail, and every break-even-IC number is linear in it** |
| **G4** | test the `choppy` filter as a selector | ✅ ⭐ **RUN AND REFUTED (§12.31e): contrast −0.0001, t −0.00, `p = 0.999`** on 185 trades — **as close to a perfect null as this document has produced** — while the filter hides **67%** of the offered set. ⚠ **On the tradeable cell its sign is wrong** (the hidden cohort is better by +0.18R, ns). ⇒ **B1 deletes both filters.** ⭐ **Your reframing of a governance item into a measurement was correct and it cost one column** |
| **G5** | pair the drift null and give it an interval | ✅ ⭐⭐ **RUN, AND IT REFUTED THREE PUBLISHED CONCLUSIONS — two of ours and one of yours (§12.31c).** You predicted pairing would **lower SE and make |t| larger in the document's favour**; measured, the paired basket is **NEGATIVE on the tradeable book** (−0.166% BUY) so gross α is **−0.0218%, t = −0.07**. ⭐ **The estimator you recommended is what refuted the conclusions you drew without it** — the strongest possible endorsement of the recommendation |
| **G6** | publish the ₹/day table and the drift-inclusive posterior | ✅ **BOTH RUN (§12.31f/g).** ⚠ **Your −43 pp/yr is inside the measured range and is not the number:** it is **−19 to −56 pp/yr** (BUY) and **−30 to −63** (E3) — **the range is the aggregation choice, which your table did not state.** ⛔ **And the posterior claim is refuted: P(beats the basket) is 10.8–25.2%, not <2%**, because the hurdle used an unpaired drift. ⭐ **Your SE-inconsistency catch (0.1287 vs 0.1490 for one cell) is real and is fixed** |
| **G7** | reconcile §12.19b with §12.21c; fix the duplicate heading | ✅ **BOTH DONE.** ⭐ **The matrix was right and the prose was wrong:** `_round_tick` is `paper_broker.py`-only, 3 call sites, `positions` = 0 ⇒ **the bug contaminates no number in the document** (§12.30a, corrected in place). Headings disambiguated to `12.18f-C7` / `12.18f-C5` |

## 18.5 Gemini — four tasks

⛔ **All four were already answered in the document it was given.** Recorded for completeness
because the pattern is now two rounds old and is the evidence behind §17c's closure.

| # | its task | where it was already answered |
|---|---|---|
| 1 | fix the tick-rounding bug | **§12.19** (round 8). ⚠ **And its proposed `tick = 0.01 if price < 250 else 0.05` is precisely what §12.19b warns against** — the phase-in is staged (0.98 → 0.49 → 0.22), so it must be a **dated table**. ⇒ B3 |
| 2 | enforce `Σ notional ≤ cash` in the backtester | **§12.14** (round 7). ⚠ **Its target is wrong too**: the backtest is not the money path — **the RiskEngine is.** ⇒ B2 |
| 3 | audit and bound the 922-day hole | **§12.12** (round 7) and **§12.23** (round 8), including the per-name second hole it did not know about |
| 4 | the IC power test on raw return % | **This is E2**, and it has been the plan's decisive item since §13.8. ⏸ B6 |

⭐ **Its one contribution stands: its restatement of the document is accurate, which is evidence
the document is readable by someone who was not in the rounds that produced it.** ⛔ **That is not
worth a review round, and §13i measures its marginal decision value at zero for the second round
running.**
