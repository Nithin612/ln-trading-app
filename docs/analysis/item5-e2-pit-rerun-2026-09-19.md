# Item 5 — E2 re-run on a point-in-time cohort (2026-09-19)

`scripts/e2_score_ic.py --pit --stocks 250 --stride 5`, 26 min, panel dumped
(31,378 rows). Run against the pre-registration committed at `fe5d508` **before** the code,
with amendments 1 and 2 recorded as their own commits.

## The answer

**3a — UNCONDITIONAL IC, h = 5d. The pre-registration says the decision reads this.**

| | IC | SE | t | 90% CI | verdict |
|---|--:|--:|--:|---|---|
| **PIT cohort (this run)** | **−0.0055** | 0.0084 | −0.65 | **[−0.0192, +0.0083]** | **NULL** |
| published (look-ahead cohort) | −0.0070 | — | — | [−0.0259, +0.0119] | NULL |

**break-even IC = 0.0313** (25.5 bps ÷ σ_cs 4.340% × E[z\|sel] 1.876). The interval's upper
bound is **3.8× below** it.

⭐⭐ **THE LOOK-AHEAD WAS REAL AND IT DID NOT DRIVE THE CONCLUSION.** M62 found E2's cohort was
34.4% look-ahead-selected; item 6 then found it was not even reproducible. Repairing it with a
per-session point-in-time cohort leaves the verdict **unchanged and the interval TIGHTER**
(width 0.0378 → **0.0275**). The null was not an artifact of the defect.

## The CA robustness check — a prediction made before the run, and it held

I argued 3a would be largely robust to corporate actions **because it is a Spearman RANK
correlation**: a split-induced −90% only moves a name to last place on its session, and the
magnitude never enters. That was testable, so it was tested inline.

| | IC | 90% CI |
|---|--:|---|
| all rows | −0.0055 | [−0.0192, +0.0083] |
| CA-tainted rows dropped | −0.0054 | [−0.0192, +0.0084] |

**The IC moves +0.0001.** ⇒ the rank argument holds, and 3a's answer does not depend on the
CA question at all. **44 of 31,378 panels (0.140%)** carry a CA candidate in their 5d forward
window; **2,020 (6.4%)** carry one in their 300-bar scoring window — the latter counted and
reported because it is a *different* defect (corrupted indicators, not a corrupted return) and
is not what this estimand is about.

## Three assumed constants, now measured on a CLEAN cohort

| constant | assumed | measured here |
|---|--:|--:|
| `sd(IC_t)` | 0.10 | **0.1046** |
| `E[z \| selected]` | 2.268 | **1.8758** (SE 0.0194) |
| σ_cs (5d cross-sectional sd) | — | **4.340%** |

⭐ `sd(IC_t)` lands essentially **on** its assumed value — every power figure linear in it
stands. `E[z|sel]` is materially lower than assumed, which *raises* break-even, and the
measured break-even (0.0313) still comes out within 0.0003 of the published 0.0310.

## The other two estimands

**3b — matched-tail contrast:** passer minus matched non-passer, 5d = **−0.0598%**, SE 0.1950,
t −0.31, 90% [−0.3805, +0.2610] against a break-even of +0.255% ⇒ **INCONCLUSIVE**.
⛔ **Reported, not decided on.** 3b is a MEAN contrast, so unlike 3a it is *not* robust to the
CA question — one −89.8% moves the mean by ~0.9/n. Resolving it needs **item 16** (a real CA
source), not a 25% screen measured at 62.5% false-positive. **⇒ the ≥70% GATE remains unproven
in both directions.**

**3c — gate-conditional IC:** +0.0427, t +1.27. A **collider** on the estimator's own output.
Reported, never decided on.

## ⛔⛔ What this triggers

§13.8 item 19's pre-registered kill criterion, stated before this run:

> point estimate **< 0.0121** ⇒ retire · **≥ 0.0499** ⇒ resurrection candidate · in between ⇒
> a second null, the scorer is retired, and the holdout is **NOT** opened to break the tie

**The point estimate is −0.0055. That is below 0.0121, so the RETIRE branch fires** — and it
does so on the first branch, not the ambiguous middle one.

What "retired" was pre-defined to mean, quoted rather than reinterpreted: *the scorer stops
being a candidate; `entry_diversity` stays as the one hard rule; the 617- and 313-session
blocks are preserved unopened for a successor generator; and the harness stays.*

⭐ **The holdouts stay sealed.** They open only on the ≥0.0499 branch, which did not fire. Both
were sealed with digests on 2026-09-19 — the seal is now doing the job it was built for.

⚠ **What this does NOT say.** It is a verdict on the **scorer as a cross-sectional ranker**, on
the 798-session test block, at h=5d. It is not a verdict on the gate (3b is inconclusive), and
it is not evidence that no generator can work — the blocks were preserved precisely so a
successor can be tested honestly.

## Reproducing it

```
cd backend && uv run python scripts/e2_score_ic.py --pit --stocks 250 --stride 5 \
    --dump /tmp/e2_panel_pit.csv
```

⚠ `--pit` is the point. Without it the script falls back to `load_frames`' ranking on
`now() - interval '180 days'` — M62's look-ahead, which item 6 showed also re-derives against
`is_active` and is therefore not reproducible run to run.
