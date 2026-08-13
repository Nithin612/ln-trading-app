# Gate experiment — 2026-08-13

_Read-only backtest over the Nifty50 daily corpus (Rust `run_universe`); NO engine change. `mean expR` = mean over decided of (+RR/−1R), winsorized ±10R; `total-R` = Σ realized R (net-profit proxy); `reach1R` = share whose MFE reached +1R._

| variant | trades | decided | win% | mean expR | total-R | reach1R |
|---|--:|--:|--:|--:|--:|--:|
| gate-70 (baseline) | 816 | 794 | 40% | +0.052 | +41.2 | 44% |
| gate-80 | 270 | 267 | 45% | +0.142 | +37.9 | 45% |
| gate-70 + skip transitional | 477 | 467 | 43% | +0.158 | +73.8 | 46% |
| gate-80 + skip transitional | 181 | 180 | 44% | +0.090 | +16.3 | 41% |
