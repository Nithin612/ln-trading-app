# Entry-confirmation study - does the market have to prove it first?

_Generated 2026-09-23 - universe `liquid` - 250 stocks - window from 2023-07-03 - 3266 resolved baseline trades (6 dropped for an unadjusted corporate action inside the holding span)._


Walker verified against the frozen `_simulate_trade` on **400** trades (exit date, exit price and both flags identical). Read-only; the frozen engine was neither edited nor subclassed.


## 1. What the whole book looks like under each entry rule

`kept` = share of the baseline's trades this rule still takes. R is measured against the risk ACTUALLY taken (`|fill - SL|`), so a worse fill is already charged for. **R is winsorized at the project's owned bound (`ratios.WINSOR_R` = 10R)** wherever it is averaged - a structural stop can land 23 bps from entry and that one trade then carries the mean (see section 6). The raw mean is shown beside it; where the two differ the tails are doing the talking. `tp_hit` is a target touch; `win` is pnl > 0. They differ by right-edge marks that happen to be positive AND by the rare case where the trigger sits ABOVE the frozen target (signal-bar high already past it), which books a target touch AT A LOSS.


| entry rule | n | kept | mean R (wins.) | median R | total R (wins.) | mean R (raw) | win | tp_hit | t |
|---|---|---|---|---|---|---|---|---|---|
| baseline: fill at next open (frozen) | 3266 | 100% | +0.004 | -1.000 | +12.9 | +0.022 | 38% | 37% | +0.15 |
| stop @ prior-bar extreme, 1d | 2059 | 63% | -0.026 | -1.000 | -53.1 | -0.026 | 44% | 42% | -0.93 |
| ... + 0.33R ceiling (stop-limit), 1d | 2018 | 62% | -0.032 | -1.000 | -64.5 | -0.032 | 44% | 42% | -1.16 |
| ... + dead if the stop was touched in the SAME BAR, 1d | 1931 | 59% | +0.012 | -1.000 | +22.5 | +0.012 | 46% | 44% | +0.41 |
| stop @ prior-bar extreme, 2d | 2386 | 73% | -0.026 | -1.000 | -62.9 | -0.026 | 44% | 43% | -1.05 |
| ... + 0.33R ceiling (stop-limit), 2d | 2337 | 72% | -0.032 | -1.000 | -74.7 | -0.032 | 44% | 43% | -1.27 |
| ... + dead if the stop was touched in the SAME BAR, 2d | 2200 | 67% | +0.017 | -1.000 | +38.1 | +0.017 | 47% | 45% | +0.67 |
| stop @ prior-bar extreme, 3d | 2514 | 77% | -0.022 | -1.000 | -55.2 | -0.022 | 45% | 44% | -0.90 |
| ... + 0.33R ceiling (stop-limit), 3d | 2461 | 75% | -0.028 | -1.000 | -68.9 | -0.028 | 44% | 43% | -1.14 |
| ... + dead if the stop was touched in the SAME BAR, 3d | 2304 | 71% | +0.021 | -1.000 | +47.9 | +0.021 | 47% | 46% | +0.82 |
| stop @ prior-bar extreme, 5d | 2677 | 82% | -0.012 | -1.000 | -31.7 | -0.012 | 45% | 44% | -0.50 |
| ... + 0.33R ceiling (stop-limit), 5d | 2621 | 80% | -0.018 | -1.000 | -46.4 | -0.018 | 45% | 44% | -0.75 |
| ... + dead if the stop was touched in the SAME BAR, 5d | 2422 | 74% | +0.029 | -1.000 | +69.6 | +0.029 | 48% | 46% | +1.17 |

### 1b. Robustness: resolved trades only (right-edge marks dropped)

A trade still open at the right edge is marked to the last close by the frozen engine - a mark, not an outcome. A confirmation rule enters LATER, so it is more exposed to that fudge; if the ranking only survives WITH the marks, it is an artifact of the corpus end, not an entry effect.


| entry rule | n | mean R | median R | total R | tp_hit | t |
|---|---|---|---|---|---|---|
| baseline: fill at next open (frozen) | 3204 | +0.017 | -1.000 | +52.9 | 38% | +0.54 |
| stop+cap+samebar, 1d | 1890 | +0.007 | -1.000 | +13.7 | 45% | +0.25 |
| stop+cap+samebar, 2d | 2154 | +0.013 | -1.000 | +27.9 | 46% | +0.49 |
| stop+cap+samebar, 3d | 2258 | +0.017 | -1.000 | +37.7 | 47% | +0.65 |
| stop+cap+samebar, 5d | 2371 | +0.025 | -1.000 | +58.2 | 47% | +0.98 |

_Right-edge marks in the baseline: 62 of 3266 (1.9%)._


## 2. Selection vs fill cost - the two effects separated

Left block = the baseline restricted to the trades this rule also took (pure selection). Right = paired mean dR on that same intersection (pure fill cost).


_All four columns are winsorized R._

| entry rule | n_int | baseline R on int | variant R on int | paired dR | t(dR) iid | **t(dR) CLUSTERED** | dates |
|---|---|---|---|---|---|---|---|
| stop, 1d | 2059 | +0.137 | -0.026 | -0.163 | -12.11 | -11.89 | 663 |
| stop+cap, 1d | 2018 | +0.134 | -0.032 | -0.166 | -12.12 | -11.94 | 658 |
| stop+cap+samebar, 1d | 1931 | +0.185 | +0.012 | -0.174 | -12.14 | -11.92 | 649 |
| stop, 2d | 2386 | +0.158 | -0.026 | -0.185 | -12.25 | -12.10 | 694 |
| stop+cap, 2d | 2337 | +0.159 | -0.032 | -0.191 | -12.49 | -12.36 | 689 |
| stop+cap+samebar, 2d | 2200 | +0.231 | +0.017 | -0.214 | -13.64 | -13.45 | 677 |
| stop, 3d | 2514 | +0.163 | -0.022 | -0.185 | -12.25 | -12.39 | 698 |
| stop+cap, 3d | 2461 | +0.164 | -0.028 | -0.191 | -12.50 | -12.71 | 693 |
| stop+cap+samebar, 3d | 2304 | +0.243 | +0.021 | -0.222 | -14.40 | -14.28 | 682 |
| stop, 5d | 2677 | +0.164 | -0.012 | -0.176 | -11.61 | -11.61 | 702 |
| stop+cap, 5d | 2621 | +0.163 | -0.018 | -0.180 | -11.77 | -11.81 | 699 |
| stop+cap+samebar, 5d | 2422 | +0.260 | +0.029 | -0.231 | -15.43 | -15.33 | 685 |

⛔ **Read the CLUSTERED column, not the iid one.** Signals cluster by date — a market-wide move mints dozens on one morning — and `sqrt(n)` over signals treats them as independent. `signed_displacement_study.py` made that assumption and its headline t fell from +14.33 to +1.66 when corrected (`docs/analysis/m93-audit-2026-09-21.md`). ⚠ The paired design here cancels most of the common market move, so the deflation is expected to be much smaller — the two columns are printed together so that expectation is tested rather than assumed.


### 2b. Is the fill cost real, or is it target truncation? (sensitivity)

The variants above keep the FROZEN target, anchored to the planned entry, while the fill moves toward it - so a worse fill widens the risk AND truncates the reward, charging the premium twice. `retp` re-anchors the target to the actual fill, keeping the frozen GEOMETRY (the same +% distance) and isolating the risk-side cost. If the paired dR roughly halves here, the headline overstates the cost; if it barely moves, the conclusion is bulletproof.


| window | n | frozen-TP dR | re-anchored-TP dR | mean R (frozen) | mean R (retp) |
|---|---|---|---|---|---|
| 1d | 1931 | -0.192 | -0.183 | +0.012 | +0.020 |
| 2d | 2200 | -0.240 | -0.240 | +0.017 | +0.017 |
| 3d | 2304 | -0.247 | -0.247 | +0.021 | +0.021 |
| 5d | 2422 | -0.255 | -0.252 | +0.029 | +0.031 |

### 2c. What the same-bar rule actually deletes

`stop+cap+samebar` declines a trade whose triggering bar ALSO traded through the stop. Daily bars cannot say which came first, so this deletes both the setup that fell to the stop before triggering (legitimately cancellable live) and the setup that triggered and was then stopped - a real -1R a live implementation would have taken. The mean R of what it removes is the tell: at -1.000 exactly it is deleting nothing but stop-outs.


| window | fills kept by stop+cap | kept by +samebar | deleted | mean R deleted |
|---|---|---|---|---|
| 1d | 2018 | 1931 | 87 | -1.000 |
| 2d | 2337 | 2200 | 137 | -0.824 |
| 3d | 2461 | 2304 | 157 | -0.744 |
| 5d | 2621 | 2422 | 199 | -0.583 |

## 3. Does it survive inside every stop-width cohort?

The mandatory check: the R:R>=1 gate looked good in aggregate because it re-sorted the stop-width mix. A rule that only wins by shifting the mix is the same trap.


| cohort | baseline n / mean R | stop+cap+samebar 5d, mean R | delta |
|---|---|---|---|
| tight <2% | 506 / +0.010 | 190 / +0.152 | +0.142 |
| mid 2-5% | 1201 / +0.032 | 920 / +0.059 | +0.027 |
| wide >5% | 1559 / +0.017 | 1312 / -0.010 | -0.027 |

## 3b. By classification


| class | baseline n / mean R | stop+cap+samebar 5d, mean R | delta |
|---|---|---|---|
| positional | 454 / -0.008 | 378 / -0.013 | -0.006 |
| swing | 2812 / +0.026 | 2044 / +0.037 | +0.010 |

## 3c. By direction


| side | baseline n / mean R | stop+cap+samebar 5d, mean R | delta |
|---|---|---|---|
| BUY | 1647 / -0.030 | 1207 / +0.033 | +0.063 |
| SELL | 1619 / +0.074 | 1215 / +0.025 | -0.050 |

## 4. When does confirmation arrive? (the alert-timing question)

Day 1 = the bar the frozen engine fills on. This is the distribution the alert clock has to cover: a 1-day window is a different product from a 5-day one.


| day | triggered | cumulative share of 3266 baseline trades |
|---|---|---|
| +1 | 2059 | 63% |
| +2 | 327 | 73% |
| +3 | 128 | 77% |
| +4 | 98 | 80% |
| +5 | 65 | 82% |
| never (within 5d) | 589 | - |

## 5. What the OPEN alone tells you (the gap census)

Where the fill bar opened relative to the signal bar, and how the frozen baseline then did. `confirmed` = the trade also cleared the prior-bar extreme within the window.


| open vs signal bar | n | mean baseline R | share confirmed |
|---|---|---|---|
| SELL no gap dn | 1110 | +0.124 | 80% |
| BUY partial up | 681 | +0.025 | 81% |
| BUY no gap up | 647 | -0.107 | 73% |
| SELL partial dn | 349 | +0.038 | 85% |
| BUY full gap up | 319 | +0.009 | 98% |
| SELL full gap dn | 160 | -0.188 | 99% |

_Census check: 3266 classified._


## 6. The largest surviving trades (is one event carrying a conclusion?)

Unadjusted corporate actions are already excluded, but the check that matters is whether the totals rest on a handful of extreme trades. A -80% split gap would book roughly -16R on a 5% stop, so a single survivor would be visible here. Cross-check the dates against any known split/bonus.

⚠ What this table actually found is a DIFFERENT hazard: every one of these trades has a stop a fraction of a percent from entry, so its R denominator is tiny and its R explodes. That is the documented tiny-SL artifact, and it is why every averaged R in this report is winsorized at 10R. The raw totals below are printed unwinsorized on purpose, to show the size of the problem.


| rank | stock | entry date | direction | risk% | R |
|---|---|---|---|---|---|
| 1 | JINDALSTEL | 2025-03-20 | SELL | 0.21% | +27.95 |
| 2 | LODHA | 2023-10-17 | SELL | 0.30% | +19.72 |
| 3 | IOC | 2026-06-25 | SELL | 0.32% | +18.89 |
| 4 | DRREDDY | 2025-12-23 | SELL | 0.34% | +17.57 |
| 5 | PPLPHARMA | 2025-09-23 | SELL | 0.44% | +13.51 |
| 6 | APOLLOHOSP | 2023-10-03 | SELL | 0.45% | +13.38 |
| 7 | BEL | 2026-09-01 | SELL | 0.46% | +13.09 |
| 8 | BSOFT | 2024-05-29 | SELL | 0.50% | +12.01 |
| 9 | EXIDEIND | 2023-10-10 | BUY | 0.55% | +10.93 |
| 10 | APOLLOHOSP | 2024-02-29 | SELL | 0.57% | +10.61 |

_Top-10 |R| trades contribute +157.7R of the baseline's +70.6R total._
