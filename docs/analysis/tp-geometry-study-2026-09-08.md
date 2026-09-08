# TP-geometry counterfactual (D5) — 2026-09-08

> ## ⛔ VERDICT: the take-profit geometry is NOT the lever. D5 → keep the tourniquet.
>
> On 1,152 swing+positional signals (150 liquid names, 2023-07-03+), **no constant-R:R target
> geometry improves expectancy** — every candidate's paired ΔR vs frozen is *negative* (−0.012 to
> −0.025R, |t| ≤ 0.65, wrong sign), and every geometry's absolute mean R is negative including the
> baseline (−0.026R). The one place a higher R:R "helps" is the *tight-stop minority* (199 of 1,152);
> it does so by **damaging the wide-stop majority** (547 trades: rr_2.0 −0.090, rr_3.0 −0.110R) — the
> exact R:R-reversal mechanism that got the R:R≥1 gate reverted on 2026-09-03. You cannot manufacture
> edge at the exit from entries that carry none: the leak is upstream in candidate *generation* (R1),
> not in `compute_levels`. **Untested:** a *structural* target (next S/R) rather than the constant-R:R
> family — a different hypothesis, but a strong prior says re-slicing an edgeless set won't rescue it.
> **This changed no recorded number and touched no frozen code** (rides the sanctioned `tp_rule`).
>
> ⚙ Reproduce: `uv run python scripts/tp_geometry_study.py --universe liquid --max-stocks 150`
> (a re-run with `--universe nifty50` will overwrite this file with the 5-stock sample — the liquid
> run is the decisive one).

Universe **liquid** (150 stocks, ≤150) · window **2023-07-03 → today** (CA-clean) · min_confidence 70 · frozen entries+stops, target varied via the sanctioned `tp_rule` freeze-extension (baseline `None` = byte-identical to frozen).

**1152 swing+positional signals** (scalp/intraday geometry-invariant, excluded from the verdict). Paired on `(stock, entry_date)` — identical entry set, only the exit differs. **R** = pnl% / risk%; a flat cost cancels in the paired ΔR (identical stop).

## 1. Expectancy per geometry (swing+positional, GROSS)

| geometry | n | mean R | median R | t | win% | tp_hit% | sl_hit% | sumR |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| baseline_frozen | 1152 | -0.026 | -1.000 | -0.52 | 37 | 36 | 62 | -29.9 |
| rr_1.0 | 1152 | -0.041 | -1.000 | -1.16 | 47 | 46 | 53 | -47.0 |
| rr_1.5 | 1152 | -0.047 | -1.000 | -1.14 | 37 | 36 | 62 | -54.6 |
| rr_2.0 | 1152 | -0.042 | -1.000 | -0.90 | 31 | 30 | 68 | -48.5 |
| rr_2.5 | 1152 | -0.051 | -1.000 | -1.01 | 27 | 25 | 72 | -58.9 |
| rr_3.0 | 1152 | -0.038 | -1.000 | -0.69 | 25 | 22 | 74 | -43.2 |

## 2. Paired ΔR vs frozen baseline — overall and by stop-width cohort

ΔR = candidate_R − baseline_R on the SAME signal. A candidate is a real fix only if ΔR>0 **and** it does not come apart inside the wide-stop cohort (the R:R-reversal trap).

| geometry | overall ΔR (t, n) | tight <2% (n) | mid 2-5% (n) | wide >5% (n) |
|---|---|---|---|---|
| rr_1.0 | -0.015 (t=-0.42, n=1152) | +0.008 (199) | -0.063 (406) | +0.012 (547) |
| rr_1.5 | -0.021 (t=-0.61, n=1152) | +0.057 (199) | -0.055 (406) | -0.025 (547) |
| rr_2.0 | -0.016 (t=-0.44, n=1152) | +0.098 (199) | +0.027 (406) | -0.090 (547) |
| rr_2.5 | -0.025 (t=-0.65, n=1152) | +0.069 (199) | +0.014 (406) | -0.089 (547) |
| rr_3.0 | -0.012 (t=-0.28, n=1152) | +0.041 (199) | +0.095 (406) | -0.110 (547) |

## 3. Paired ΔR by class (GROSS)

| geometry | swing ΔR (t, n) | positional ΔR (t, n) |
|---|--:|--:|
| rr_1.0 | -0.047 (t=-1.23, 953) | +0.140 (t=+1.51, 199) |
| rr_1.5 | -0.023 (t=-0.56, 953) | -0.016 (t=-0.23, 199) |
| rr_2.0 | -0.015 (t=-0.35, 953) | -0.020 (t=-0.37, 199) |
| rr_2.5 | -0.026 (t=-0.56, 953) | -0.021 (t=-0.58, 199) |
| rr_3.0 | -0.014 (t=-0.28, 953) | +0.000 (t=+0.00, 199) |

---

**Reading it.** Promotion bar for a real edge is t ≈ 3.6 (deflated-Sharpe, flat in n); this answers the narrower question of whether geometry moves expectancy at all, and where. A ~zero or negative overall ΔR, or a positive that inverts in the wide-stop cohort, says the frozen geometry is not the lever (tourniquet stays). A robust positive ΔR holding across cohorts is the case to take to a §8 spec change.
