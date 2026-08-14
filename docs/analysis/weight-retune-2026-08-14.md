# Weight-retune experiment (6.4) — 2026-08-14

_Read-only coordinate sweep over the Nifty50 daily corpus (parity-pinned `run_universe`, gate-70): each confluence weight-group scaled ×0.5 / ×1.5 one at a time. Group multipliers apply inside the frozen scorer (byte-identical to frozen when empty); the engine is untouched and nothing is promoted. `Δexp` = mean-expectancy change vs baseline; `folds+` = of 5 shared time folds, how many this config beats baseline expectancy in (a per-fold temporal-consistency proxy — NOT out-of-sample; no train/test split)._

_Note: the 6.2 leak is per-FACTOR but this lever is per-GROUP, and groups mix helping and hurting factors — so a group that nets flat can still hide a real per-factor signal. A clean win here is actionable; a null result argues for per-factor weights (a larger, frozen-engine change) rather than group tuning._

| config | trades | win% | Sharpe | maxDD R | total-R | mean expR | Δexp | folds+ |
|---|--:|--:|--:|--:|--:|--:|--:|:-:|
| baseline | 818 | 40% | +0.034 | 36.5 | +41.2 | +0.052 | +0.000 | 0/5 |
| momentum ×1.5 | 742 | 41% | +0.045 | 32.4 | +50.4 | +0.070 | +0.018 | 4/5 |
| trend ×0.5 | 996 | 41% | +0.033 | 50.8 | +47.7 | +0.049 | -0.003 | 2/5 |
| structure ×0.5 | 728 | 40% | +0.043 | 31.8 | +47.0 | +0.066 | +0.014 | 4/5 |
| pattern ×0.5 | 690 | 41% | +0.045 | 29.1 | +46.9 | +0.070 | +0.018 | 3/5 |
| momentum ×0.5 | 1020 | 39% | +0.028 | 46.1 | +43.8 | +0.044 | -0.008 | 3/5 |
| volume ×1.5 | 737 | 40% | +0.038 | 32.1 | +42.5 | +0.059 | +0.007 | 3/5 |
| volume ×0.5 | 964 | 40% | +0.030 | 47.3 | +41.5 | +0.044 | -0.008 | 3/5 |
| trend ×1.5 | 778 | 40% | +0.034 | 34.1 | +39.1 | +0.052 | -0.000 | 3/5 |
| institutional ×1.5 | 852 | 39% | +0.029 | 50.4 | +36.2 | +0.044 | -0.008 | 2/5 |
| institutional ×0.5 | 795 | 40% | +0.030 | 34.1 | +35.2 | +0.046 | -0.006 | 1/5 |
| structure ×1.5 | 966 | 40% | +0.024 | 43.4 | +33.7 | +0.036 | -0.016 | 2/5 |
| pattern ×1.5 | 1049 | 39% | +0.015 | 60.7 | +23.0 | +0.023 | -0.029 | 2/5 |

## Verdict

**momentum ×1.5** leads: expR +0.052→+0.070, total-R +41.2→+50.4, beats baseline in 4/5 folds. Candidate for a shadow retune profile — NOT promoted here; that needs forward evidence + sign-off. Best-of-12 selected on the full corpus, so treat even this as in-sample until forward shadow confirms; `folds+` is the only guard against a lucky pick.

