# Carter's squeeze as a generation lever - market-neutral test

_Generated 2026-09-10 - 250 liquid stocks - window from 2023-07-03 - 3,610 squeeze fires (49% long). **41 fire/horizon observations dropped** for an unadjusted corporate action (|close-to-close| > 25%) inside the forward window._


BB(20,2) inside KC(20,1.5) = compression; the fire is the bar compression ENDS. Direction from 12-period momentum. Entry at the NEXT session's open (bar t is only complete at its close). Returns are **excess over that day's cross-sectional mean** at the same horizon, signed so a short earns the negative of market drift - the corpus window is a strong bull market and a long-biased rule would otherwise look free. **`t` is Newey-West at lag k-1 on the daily mean of the excess**; `naive t` is the uncorrected one. Consecutive days share k-1 sessions of the same future, which inflates a naive t - small here because fires are sparse (~5.5/day), but shown.


| cohort | horizon | fires | mean excess % | t (Newey-West) | naive t |
|---|---|---|---|---|---|
| squeeze fire (all) | +1d | 3,609 | -0.023% | -0.49 (653d) | -0.49 |
| squeeze fire (all) | +3d | 3,605 | -0.024% | -0.28 (653d) | -0.28 |
| squeeze fire (all) | +5d | 3,604 | +0.051% | +0.44 (653d) | +0.46 |
| squeeze fire (all) | +10d | 3,598 | +0.163% | +0.90 (653d) | +1.05 |
| squeeze fire (all) | +20d | 3,593 | +0.108% | +0.41 (653d) | +0.45 |
| squeeze fire, long | +1d | 1,763 | -0.024% | -0.31 (544d) | -0.31 |
| squeeze fire, long | +3d | 1,759 | -0.029% | -0.23 (544d) | -0.22 |
| squeeze fire, long | +5d | 1,758 | -0.038% | -0.24 (544d) | -0.23 |
| squeeze fire, long | +10d | 1,755 | +0.070% | +0.28 (542d) | +0.29 |
| squeeze fire, long | +20d | 1,752 | -0.157% | -0.45 (542d) | -0.47 |
| squeeze fire, short | +1d | 1,846 | -0.063% | -0.95 (517d) | -0.95 |
| squeeze fire, short | +3d | 1,846 | -0.050% | -0.39 (517d) | -0.41 |
| squeeze fire, short | +5d | 1,846 | +0.044% | +0.28 (517d) | +0.29 |
| squeeze fire, short | +10d | 1,843 | +0.242% | +0.96 (517d) | +1.11 |
| squeeze fire, short | +20d | 1,841 | +0.289% | +0.73 (517d) | +0.90 |
| squeeze fire + weekly aligned | +1d | 2,357 | +0.007% | +0.12 (618d) | +0.12 |
| squeeze fire + weekly aligned | +3d | 2,355 | +0.016% | +0.17 (618d) | +0.17 |
| squeeze fire + weekly aligned | +5d | 2,354 | +0.128% | +0.94 (618d) | +0.96 |
| squeeze fire + weekly aligned | +10d | 2,350 | +0.207% | +1.09 (618d) | +1.07 |
| squeeze fire + weekly aligned | +20d | 2,348 | -0.041% | -0.16 (618d) | -0.14 |
| squeeze fire + weekly opposed | +1d | 1,252 | -0.124% | -1.67 (520d) | -1.67 |
| squeeze fire + weekly opposed | +3d | 1,250 | -0.183% | -1.47 (519d) | -1.45 |
| squeeze fire + weekly opposed | +5d | 1,250 | -0.149% | -0.86 (519d) | -0.91 |
| squeeze fire + weekly opposed | +10d | 1,248 | +0.150% | +0.62 (519d) | +0.59 |
| squeeze fire + weekly opposed | +20d | 1,245 | +0.674% | +2.29 (519d) | +1.88 |

_Reference: the promotion bar for this project is t ~ 3.6 on the trade series (H8, `docs/analysis/dsr-negative-control-2026-09-04.md`). A t below that is not evidence of no edge - power is near zero between t 2.6 and 3.5 - but it is not a promotion either. Record the t._
