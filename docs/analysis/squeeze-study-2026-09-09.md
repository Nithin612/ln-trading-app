# Carter's squeeze as a generation lever - market-neutral test

_Generated 2026-09-09 - 250 liquid stocks - CA-clean window from 2023-07-03 - 3,610 squeeze fires (49% long)._


BB(20,2) inside KC(20,1.5) = compression; the fire is the bar compression ENDS. Direction from 12-period momentum. Entry at the NEXT session's open (bar t is only complete at its close). Returns are **excess over that day's cross-sectional mean** at the same horizon, signed so a short earns the negative of market drift - the corpus window is a strong bull market and a long-biased rule would otherwise look free. **t is on the daily mean of the excess** (n = trading days), never per trade.


| cohort | horizon | fires | mean excess % | t (daily) |
|---|---|---|---|---|
| squeeze fire (all) | +1d | 3,610 | -0.025% | -0.53 (653d) |
| squeeze fire (all) | +3d | 3,610 | -0.087% | -0.97 (653d) |
| squeeze fire (all) | +5d | 3,610 | -0.074% | -0.57 (653d) |
| squeeze fire (all) | +10d | 3,610 | -0.005% | -0.03 (653d) |
| squeeze fire (all) | +20d | 3,610 | -0.060% | -0.23 (653d) |
| squeeze fire, long | +1d | 1,764 | -0.027% | -0.35 (544d) |
| squeeze fire, long | +3d | 1,764 | -0.102% | -0.71 (544d) |
| squeeze fire, long | +5d | 1,764 | -0.156% | -0.82 (544d) |
| squeeze fire, long | +10d | 1,764 | -0.221% | -0.71 (544d) |
| squeeze fire, long | +20d | 1,764 | -0.343% | -0.88 (544d) |
| squeeze fire, short | +1d | 1,846 | -0.063% | -0.95 (517d) |
| squeeze fire, short | +3d | 1,846 | -0.087% | -0.72 (517d) |
| squeeze fire, short | +5d | 1,846 | -0.028% | -0.18 (517d) |
| squeeze fire, short | +10d | 1,846 | +0.157% | +0.71 (517d) |
| squeeze fire, short | +20d | 1,846 | +0.085% | +0.26 (517d) |
| squeeze fire + weekly aligned | +1d | 2,357 | +0.007% | +0.12 (618d) |
| squeeze fire + weekly aligned | +3d | 2,357 | -0.012% | -0.11 (618d) |
| squeeze fire + weekly aligned | +5d | 2,357 | +0.038% | +0.26 (618d) |
| squeeze fire + weekly aligned | +10d | 2,357 | +0.099% | +0.46 (618d) |
| squeeze fire + weekly aligned | +20d | 2,357 | -0.131% | -0.44 (618d) |
| squeeze fire + weekly opposed | +1d | 1,253 | -0.135% | -1.80 (521d) |
| squeeze fire + weekly opposed | +3d | 1,253 | -0.399% | -2.09 (521d) |
| squeeze fire + weekly opposed | +5d | 1,253 | -0.377% | -1.69 (521d) |
| squeeze fire + weekly opposed | +10d | 1,253 | -0.122% | -0.40 (521d) |
| squeeze fire + weekly opposed | +20d | 1,253 | +0.325% | +0.80 (521d) |

_Reference: the promotion bar for this project is t ~ 3.6 on the trade series (H8, `docs/analysis/dsr-negative-control-2026-09-04.md`). A t below that is not evidence of no edge - power is near zero between t 2.6 and 3.5 - but it is not a promotion either. Record the t._
