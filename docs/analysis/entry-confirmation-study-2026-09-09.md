# Entry-confirmation study - does the market have to prove it first?

_Generated 2026-09-10 - universe `liquid` - 250 stocks - window from 2023-07-03 - 1975 resolved baseline trades (4 dropped for an unadjusted corporate action inside the holding span)._


Walker verified against the frozen `_simulate_trade` on **400** trades (exit date, exit price and both flags identical). Read-only; the frozen engine was neither edited nor subclassed.


## 1. What the whole book looks like under each entry rule

`kept` = share of the baseline's trades this rule still takes. R is measured against the risk ACTUALLY taken (`|fill - SL|`), so a worse fill is already charged for. **R is winsorized at the project's owned bound (`ratios.WINSOR_R` = 10R)** wherever it is averaged - a structural stop can land 23 bps from entry and that one trade then carries the mean (see section 6). The raw mean is shown beside it; where the two differ the tails are doing the talking. `tp_hit` is a target touch; `win` is pnl > 0. They differ by right-edge marks that happen to be positive AND by the rare case where the trigger sits ABOVE the frozen target (signal-bar high already past it), which books a target touch AT A LOSS.


| entry rule | n | kept | mean R (wins.) | median R | total R (wins.) | mean R (raw) | win | tp_hit | t |
|---|---|---|---|---|---|---|---|---|---|
| baseline: fill at next open (frozen) | 1975 | 100% | -0.065 | -1.000 | -128.4 | -0.045 | 36% | 35% | -1.94 |
| stop @ prior-bar extreme, 1d | 1182 | 60% | -0.044 | -1.000 | -52.4 | -0.044 | 44% | 43% | -1.27 |
| ... + 0.33R ceiling (stop-limit), 1d | 1151 | 58% | -0.047 | -1.000 | -53.6 | -0.047 | 45% | 44% | -1.34 |
| ... + dead if the stop was touched in the SAME BAR, 1d | 1083 | 55% | +0.013 | -1.000 | +14.4 | +0.013 | 47% | 46% | +0.37 |
| stop @ prior-bar extreme, 2d | 1376 | 70% | -0.056 | -1.000 | -77.4 | -0.056 | 45% | 44% | -1.79 |
| ... + 0.33R ceiling (stop-limit), 2d | 1339 | 68% | -0.057 | -1.000 | -76.9 | -0.057 | 45% | 44% | -1.82 |
| ... + dead if the stop was touched in the SAME BAR, 2d | 1234 | 62% | +0.008 | -0.709 | +9.4 | +0.008 | 48% | 47% | +0.23 |
| stop @ prior-bar extreme, 3d | 1469 | 74% | -0.074 | -1.000 | -108.1 | -0.074 | 44% | 44% | -2.43 |
| ... + 0.33R ceiling (stop-limit), 3d | 1431 | 72% | -0.074 | -1.000 | -106.5 | -0.074 | 45% | 44% | -2.45 |
| ... + dead if the stop was touched in the SAME BAR, 3d | 1298 | 66% | -0.006 | -1.000 | -8.3 | -0.006 | 48% | 47% | -0.20 |
| stop @ prior-bar extreme, 5d | 1578 | 80% | -0.083 | -1.000 | -130.5 | -0.083 | 44% | 44% | -2.86 |
| ... + 0.33R ceiling (stop-limit), 5d | 1537 | 78% | -0.084 | -1.000 | -128.4 | -0.084 | 45% | 44% | -2.87 |
| ... + dead if the stop was touched in the SAME BAR, 5d | 1363 | 69% | -0.011 | -1.000 | -14.6 | -0.011 | 48% | 47% | -0.34 |

### 1b. Robustness: resolved trades only (right-edge marks dropped)

A trade still open at the right edge is marked to the last close by the frozen engine - a mark, not an outcome. A confirmation rule enters LATER, so it is more exposed to that fudge; if the ranking only survives WITH the marks, it is an artifact of the corpus end, not an entry effect.


| entry rule | n | mean R | median R | total R | tp_hit | t |
|---|---|---|---|---|---|---|
| baseline: fill at next open (frozen) | 1935 | -0.048 | -1.000 | -93.2 | 36% | -1.25 |
| stop+cap+samebar, 1d | 1054 | +0.016 | -1.000 | +16.8 | 48% | +0.43 |
| stop+cap+samebar, 2d | 1200 | +0.011 | -1.000 | +12.9 | 49% | +0.32 |
| stop+cap+samebar, 3d | 1263 | -0.004 | -1.000 | -4.8 | 48% | -0.12 |
| stop+cap+samebar, 5d | 1327 | -0.009 | -1.000 | -11.3 | 48% | -0.27 |

_Right-edge marks in the baseline: 40 of 1975 (2.0%)._


## 2. Selection vs fill cost - the two effects separated

Left block = the baseline restricted to the trades this rule also took (pure selection). Right = paired mean dR on that same intersection (pure fill cost).


_All four columns are winsorized R._

| entry rule | n_int | baseline R on int | variant R on int | paired dR | t(dR) |
|---|---|---|---|---|---|
| stop, 1d | 1182 | +0.163 | -0.044 | -0.207 | -10.57 |
| stop+cap, 1d | 1151 | +0.166 | -0.047 | -0.213 | -10.59 |
| stop+cap+samebar, 1d | 1083 | +0.239 | +0.013 | -0.226 | -10.62 |
| stop, 2d | 1376 | +0.153 | -0.056 | -0.209 | -10.88 |
| stop+cap, 2d | 1339 | +0.156 | -0.057 | -0.214 | -10.93 |
| stop+cap+samebar, 2d | 1234 | +0.255 | +0.008 | -0.247 | -12.20 |
| stop, 3d | 1469 | +0.128 | -0.074 | -0.202 | -10.30 |
| stop+cap, 3d | 1431 | +0.132 | -0.074 | -0.206 | -10.34 |
| stop+cap+samebar, 3d | 1298 | +0.248 | -0.006 | -0.254 | -12.46 |
| stop, 5d | 1578 | +0.109 | -0.083 | -0.192 | -9.66 |
| stop+cap, 5d | 1537 | +0.111 | -0.084 | -0.194 | -9.61 |
| stop+cap+samebar, 5d | 1363 | +0.253 | -0.011 | -0.264 | -12.84 |

### 2b. Is the fill cost real, or is it target truncation? (sensitivity)

The variants above keep the FROZEN target, anchored to the planned entry, while the fill moves toward it - so a worse fill widens the risk AND truncates the reward, charging the premium twice. `retp` re-anchors the target to the actual fill, keeping the frozen GEOMETRY (the same +% distance) and isolating the risk-side cost. If the paired dR roughly halves here, the headline overstates the cost; if it barely moves, the conclusion is bulletproof.


| window | n | frozen-TP dR | re-anchored-TP dR | mean R (frozen) | mean R (retp) |
|---|---|---|---|---|---|
| 1d | 1083 | -0.262 | -0.268 | +0.013 | +0.007 |
| 2d | 1234 | -0.279 | -0.284 | +0.008 | +0.003 |
| 3d | 1298 | -0.284 | -0.288 | -0.006 | -0.011 |
| 5d | 1363 | -0.292 | -0.296 | -0.011 | -0.014 |

### 2c. What the same-bar rule actually deletes

`stop+cap+samebar` declines a trade whose triggering bar ALSO traded through the stop. Daily bars cannot say which came first, so this deletes both the setup that fell to the stop before triggering (legitimately cancellable live) and the setup that triggered and was then stopped - a real -1R a live implementation would have taken. The mean R of what it removes is the tell: at -1.000 exactly it is deleting nothing but stop-outs.


| window | fills kept by stop+cap | kept by +samebar | deleted | mean R deleted |
|---|---|---|---|---|
| 1d | 1151 | 1083 | 68 | -1.000 |
| 2d | 1339 | 1234 | 105 | -0.822 |
| 3d | 1431 | 1298 | 133 | -0.738 |
| 5d | 1537 | 1363 | 174 | -0.654 |

## 3. Does it survive inside every stop-width cohort?

The mandatory check: the R:R>=1 gate looked good in aggregate because it re-sorted the stop-width mix. A rule that only wins by shifting the mix is the same trap.


| cohort | baseline n / mean R | stop+cap+samebar 5d, mean R | delta |
|---|---|---|---|
| tight <2% | 313 / -0.119 | 100 / -0.052 | +0.068 |
| mid 2-5% | 701 / -0.010 | 500 / +0.066 | +0.075 |
| wide >5% | 961 / -0.047 | 763 / -0.055 | -0.008 |

## 3b. By classification


| class | baseline n / mean R | stop+cap+samebar 5d, mean R | delta |
|---|---|---|---|
| positional | 333 / -0.162 | 246 / -0.151 | +0.011 |
| swing | 1642 / -0.022 | 1117 / +0.020 | +0.042 |

## 3c. By direction


| side | baseline n / mean R | stop+cap+samebar 5d, mean R | delta |
|---|---|---|---|
| BUY | 1115 / -0.103 | 737 / -0.059 | +0.044 |
| SELL | 860 / +0.030 | 626 / +0.046 | +0.017 |

## 4. When does confirmation arrive? (the alert-timing question)

Day 1 = the bar the frozen engine fills on. This is the distribution the alert clock has to cover: a 1-day window is a different product from a 5-day one.


| day | triggered | cumulative share of 1975 baseline trades |
|---|---|---|
| +1 | 1182 | 60% |
| +2 | 194 | 70% |
| +3 | 93 | 74% |
| +4 | 63 | 78% |
| +5 | 46 | 80% |
| never (within 5d) | 397 | - |

## 5. What the OPEN alone tells you (the gap census)

Where the fill bar opened relative to the signal bar, and how the frozen baseline then did. `confirmed` = the trade also cleared the prior-bar extreme within the window.


| open vs signal bar | n | mean baseline R | share confirmed |
|---|---|---|---|
| SELL no gap dn | 627 | +0.034 | 80% |
| BUY partial up | 519 | -0.151 | 78% |
| BUY no gap up | 432 | -0.095 | 70% |
| SELL partial dn | 175 | +0.086 | 87% |
| BUY full gap up | 164 | +0.026 | 98% |
| SELL full gap dn | 58 | -0.191 | 98% |

_Census check: 1975 classified._


## 6. The largest surviving trades (is one event carrying a conclusion?)

Unadjusted corporate actions are already excluded, but the check that matters is whether the totals rest on a handful of extreme trades. A -80% split gap would book roughly -16R on a 5% stop, so a single survivor would be visible here. Cross-check the dates against any known split/bonus.

⚠ What this table actually found is a DIFFERENT hazard: every one of these trades has a stop a fraction of a percent from entry, so its R denominator is tiny and its R explodes. That is the documented tiny-SL artifact, and it is why every averaged R in this report is winsorized at 10R. The raw totals below are printed unwinsorized on purpose, to show the size of the problem.


| rank | stock | entry date | direction | risk% | R |
|---|---|---|---|---|---|
| 1 | MAPMYINDIA | 2024-08-16 | BUY | 0.23% | +26.36 |
| 2 | LODHA | 2023-10-17 | SELL | 0.30% | +19.72 |
| 3 | CAMPUS | 2025-01-30 | BUY | 0.58% | +15.45 |
| 4 | BIKAJI | 2026-01-01 | SELL | 0.44% | +13.67 |
| 5 | PPLPHARMA | 2025-09-23 | SELL | 0.44% | +13.51 |
| 6 | ABREL | 2026-07-17 | SELL | 0.68% | +8.76 |
| 7 | KRN | 2025-11-12 | BUY | 0.70% | +8.57 |
| 8 | SONACOMS | 2024-04-01 | SELL | 0.74% | +8.11 |
| 9 | SAMHI | 2026-04-16 | SELL | 0.83% | +7.19 |
| 10 | IKS | 2026-08-12 | BUY | 0.86% | +7.01 |

_Top-10 |R| trades contribute +128.4R of the baseline's -89.7R total._
