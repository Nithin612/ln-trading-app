# Item 5, estimand 3b — the ≥70% gate selects nothing (2026-09-19)

The last undecided question in the programme. 3a retired the scorer as a *ranker*; 3b asks the
separate question of whether the **gate** selects anything, and it has read "unproven in both
directions" for months because it could not be run on a trustworthy corporate-action set.
Item 16 supplied one.

Same run as 3a — PIT cohort, stride 5, 31,378 panels over 156 sessions, pre-registration
`fe5d508`. 3a reproduces to the decimal (`IC −0.0055`), so the run is deterministic.

## The answer

Passer minus date-and-characteristic-matched non-passer, h = 5d. Break-even is **+0.255%**.

| cohort | pairs | contrast | SE | t | 90% CI | verdict |
|---|--:|--:|--:|--:|---|---|
| all rows, no CA handling | 1,274 | −0.0598% | 0.1950 | −0.31 | [−0.3805, **+0.2610**] | INCONCLUSIVE |
| 25% screen dropped | 1,272 | −0.0885% | 0.1519 | −0.58 | [−0.3384, +0.1614] | NULL |
| ⭐ **authority dropped** | **1,272** | **−0.0885%** | **0.1519** | **−0.58** | **[−0.3384, +0.1614]** | **NULL** |

⭐⭐ **THE VERDICT FLIPS, AND THE MARGIN IT FLIPPED ON WAS 0.006 PERCENTAGE POINTS.** The
published 3b was INCONCLUSIVE for exactly one reason: its upper bound, **+0.2610%**, sat above
break-even **+0.255%** — by six thousandths of a point. Removing the corporate actions tightens
the standard error from 0.1950 to **0.1519** and pulls the bound to **+0.1614**, comfortably
inside. **3b is NULL: the ≥70% gate does not select a forward return that pays for the trade.**

## ⚠ Two of one thousand two hundred and seventy-four

The CA exclusion removed **2 matched pairs**. Two. That is what moved the standard error by 22%
and flipped a pre-registered verdict.

⭐ **This is the 3a/3b asymmetry, demonstrated rather than argued.** The same cleaning moved 3a
by **+0.0001** — because 3a is a Spearman RANK correlation and a split only sends a name to
last place, while 3b is a MEAN and one −89.8% moves it by roughly `0.9/n`. The claim that 3a
could run without item 16 and 3b could not was made before either was run; both halves now hold.

## ⛔ What item 16 actually bought — stated honestly

**The screen and the authority give the SAME answer here** (−0.0885%, identically). So item 16
did **not** change this number.

What it changed is whether the number could be believed. Measured the same day, the 25% screen
is **36.9% false-positive** and **13.1% false-negative** against the authority set. A verdict
resting on it would have been a verdict resting on a tool that is wrong a third of the time —
and there was no way to know it happened to be adequate *for this estimand* without the
authority set to check against. **The finding is that the screen was good enough here, and that
finding required the thing it is being compared to.**

⚠ It also explains why: the CA events that actually land inside a gate-passer's forward window
are the large ones, which both tools catch. The screen's false positives are genuine price
moves, and its structural false negatives are small bonuses — neither class is concentrated in
this particular 1,274-pair sample.

## Where this leaves the programme

**Both pre-registered estimands are now NULL.**

- **3a** — the scorer carries no cross-sectional information. IC −0.0055, 90% [−0.0192,
  +0.0083] against break-even 0.0313.
- **3b** — the gate selects nothing. −0.0885%, 90% [−0.3384, +0.1614] against +0.255%.

⭐ §13.8 item 19's retire branch had already fired on 3a's point estimate (−0.0055 < 0.0121).
**3b removes the one remaining reading under which the apparatus might still have had value:**
that the ranking was worthless but the *threshold* was doing real work. It is not.

⚠ **Scope, unchanged.** This is a verdict on the scorer and its gate, on the 798-session test
block, at h = 5d. It is not evidence that no generator can work — which is why the 617- and
313-session holdouts remain **sealed and unopened**, and why the harness stays.

**3c** (gate-conditional IC) remains a collider on the estimator's own output: reported, never
decided on.
