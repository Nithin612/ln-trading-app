# Q2.4 — the momentum ×1.5 retune, decided by the bar (2026-09-07)
**The forward route is dead.** The 6.4 shadow A/B has minted **7 signals per arm**
and resolved **0 in 21 days** (2026-08-13 → 09-03). At that rate the decision is
years away, so waiting for forward evidence is not a plan — it is a way of never
deciding.
**So it is decided here, with the instrument that did not exist in August.** The
original sweep chose best-of-12 on the full corpus and said so; `folds+` was its
only guard against a lucky pick. The deflated-Sharpe bar is built for exactly this.
- **trials charged: 13** (baseline + 12 variants — the honest count
  for a best-of-N selection)
- **trial dispersion: MEASURED at +0.0078**
  (we ran the trials, so their spread is observable — strictly more faithful than
  the `1/√n` fallback the bar uses when it has to guess)
⭐ **The bar restates as t ≈ 3.6, and H8 established that hurdle is FLAT IN n** —
so a candidate far below it cannot be rescued by accruing more of the same.
| config | trades | Sharpe | **t** | total-R | expR | folds+ | DSR | clears? |
|---|--:|--:|--:|--:|--:|:-:|--:|:-:|
| structure ×0.5 | 723 | +0.038 | **+1.02** | +42.5 | +0.059 | 4/5 | 75.4% | ❌ |
| momentum ×1.5 | 734 | +0.037 | **+1.00** | +41.6 | +0.057 | 4/5 | 74.8% | ❌ |
| trend ×0.5 | 991 | +0.026 | **+0.83** | +38.8 | +0.039 | 2/5 | 66.5% | ❌ |
| pattern ×0.5 | 683 | +0.033 | **+0.87** | +35.3 | +0.052 | 3/5 | 70.6% | ❌ |
| volume ×1.5 | 733 | +0.030 | **+0.82** | +34.0 | +0.046 | 3/5 | 68.1% | ❌ |
| momentum ×0.5 | 1014 | +0.021 | **+0.67** | +33.0 | +0.033 | 3/5 | 59.8% | ❌ |
| baseline | 811 | +0.025 | **+0.71** | +30.5 | +0.038 | — | 63.1% | ❌ |
| volume ×0.5 | 956 | +0.020 | **+0.63** | +28.7 | +0.030 | 3/5 | 58.6% | ❌ |
| trend ×1.5 | 772 | +0.023 | **+0.64** | +27.2 | +0.035 | 3/5 | 60.9% | ❌ |
| institutional ×0.5 | 788 | +0.021 | **+0.60** | +25.5 | +0.032 | 1/5 | 59.2% | ❌ |
| institutional ×1.5 | 844 | +0.020 | **+0.58** | +25.5 | +0.030 | 2/5 | 57.6% | ❌ |
| structure ×1.5 | 962 | +0.017 | **+0.54** | +24.8 | +0.026 | 2/5 | 55.1% | ❌ |
| pattern ×1.5 | 1044 | +0.011 | **+0.36** | +17.4 | +0.017 | 2/5 | 47.3% | ❌ |
## Verdict
**momentum ×1.5 stands at t = +1.00** against a hurdle of **≈3.6** — short by ~3.6×.
> DSR 74.8% < 95%: needs ≈4,453 observations at these moments (have 734) to clear a 13-trial benchmark of +0.013
⭐ **THE WINNER HAS CHANGED. `structure ×0.5` now ranks first, not `momentum ×1.5`.**
The August sweep put `momentum ×1.5` top on total-R (+50.4). Re-running the
same method on a slightly larger corpus reorders the table — and the gap
between first and the middle of the pack is a fraction of a t. **A ranking
that reshuffles when the sample nudges was never measuring a real ordering**,
which is a sharper argument against the original pick than any single
statistic: it shows the selection itself was the noise.
⛔ **NOT ONE CONFIG CLEARS THE BAR — including whichever one leads.**
**⇒ DECIDE: NO. The momentum ×1.5 retune is not promotable, and the forward
A/B should stop being treated as a pending decision.** It is not that the
evidence is incomplete; it is that the apparent edge is the size a best-of-13
selection produces by chance, and the hurdle does not fall with more data.
This is the same shape as `sl_atr` (t ≈ 0.41 vs 3.6, decided NO on 09-04) and
it belongs in the same bucket: **the instrument working, not failing.**
## ⚠ Limits
- **Still in-sample.** Deflation prices the selection, not the lack of a holdout.
- **Per-GROUP, not per-factor.** The 6.2 leak is per-factor; groups mix helping and
  hurting factors, so a group that nets flat can hide a real per-factor signal. A
  null here argues for per-factor weights — a larger, frozen-engine change.
- **The corpus is Nifty50 daily since ~2023-07**, so this says nothing about other
  regimes (that is what the parked pre-COVID backtest would address).
