# Regime-gate §8 walk-forward — 2026-08-13

_Read-only over the Nifty50 daily corpus (parity-pinned Rust `run_universe`, gate-70); NO engine change. Promotes the gate experiment into a §8-grade regression: the three metrics §8 gates a merge on (win rate, Sharpe, max drawdown) plus an out-of-sample test of the finding._

_Definitions: realized R = +RR (target) / −1R (stop), winsorized ±10R. Sharpe = mean(R)/stdev(R) per trade. maxDD = worst peak-to-trough on the daily-aggregated R equity curve. Folds = 5 contiguous time slices. A regime is 'learned' as bad only with ≥20 decided trades._

## 1. Aggregate §8 metrics (whole corpus)

| variant | trades | decided | win% | Sharpe | maxDD R | total-R | mean expR | reach1R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| baseline (all regimes) | 816 | 794 | 40% | +0.034 | 36.5 | +41.2 | +0.052 | 44% |
| proposed (skip transitional) | 477 | 467 | 43% | +0.097 | 20.4 | +73.8 | +0.158 | 46% |

**§8 change gate** — relative move vs baseline (⚠ = >5%, needs explicit sign-off):

| metric | baseline | proposed | change |
|---|--:|--:|--:|
| win rate | 40% | 43% | +7% ⚠ |
| Sharpe | +0.034 | +0.097 | +186% ⚠ |
| max drawdown (R) | 36.5 | 20.4 | -44% ⚠ |

## 2. Fixed-rule consistency across 5 time folds

_Skip-transitional scored INSIDE each fold — is the edge everywhere or one stretch?_

| fold | n (base→var) | win% (base→var) | total-R (base→var) | mean expR (base→var) | variant wins? |
|---|--:|--:|--:|--:|:-:|
| 2023-09-13 → 2024-03-07 | 208→108 | 40%→45% | +1.7→+22.7 | +0.008→+0.210 | ✓ |
| 2024-03-12 → 2024-10-28 | 149→85 | 46%→51% | +36.7→+29.0 | +0.247→+0.341 | ✓ |
| 2024-10-29 → 2025-06-05 | 149→91 | 44%→45% | +31.4→+21.9 | +0.211→+0.240 | ✓ |
| 2025-06-09 → 2025-12-22 | 166→107 | 32%→36% | -28.3→-2.0 | -0.170→-0.018 | ✓ |
| 2025-12-23 → 2026-08-11 | 144→86 | 38%→37% | -0.4→+2.2 | -0.003→+0.029 | ✓ |

**Variant wins expectancy in 5/5 folds.**

## 3. Anchored walk-forward (out-of-sample)

_Learn the negative-expectancy regime(s) from every EARLIER fold, apply to the next unseen fold. Defeats the circularity: the skip is decided without seeing the fold it is scored on._

| test fold | train n | learned skip | total-R (base→gated) | mean expR (base→gated) | win% (base→gated) |
|---|--:|---|--:|--:|--:|
| 2024-03-12 → 2024-10-28 | 208 | transitional (20–25) | +36.7→+29.0 | +0.247→+0.341 | 46%→51% |
| 2024-10-29 → 2025-06-05 | 357 | transitional (20–25) | +31.4→+21.9 | +0.211→+0.240 | 44%→45% |
| 2025-06-09 → 2025-12-22 | 506 | transitional (20–25) | -28.3→-2.0 | -0.170→-0.018 | 32%→36% |
| 2025-12-23 → 2026-08-11 | 672 | transitional (20–25) | -0.4→+2.2 | -0.003→+0.029 | 38%→37% |

**Aggregate out-of-sample (all test folds):**

| variant | trades | decided | win% | Sharpe | maxDD R | total-R | mean expR | reach1R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| OOS baseline (all regimes) | 608 | 586 | 40% | +0.044 | 36.5 | +39.5 | +0.067 | 46% |
| OOS learned-gate | 369 | 359 | 42% | +0.091 | 20.4 | +51.1 | +0.142 | 47% |

## Verdict

**HOLDS out-of-sample — the learned gate beats baseline expectancy on unseen folds and skip-transitional wins the majority of time folds (5/5).**

The §8 change gate above flags the win-rate / Sharpe / drawdown moves that exceed ±5%: those require **explicit user sign-off** before the regime gate is implemented in the engine. This report is read-only evidence — it changes nothing.

