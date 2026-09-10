# Entry-confirmation study - does the market have to prove it first?

_Generated 2026-09-09 - universe `liquid` - 250 stocks - CA-clean window from 2023-07-03 - 1979 resolved baseline trades._


Walker verified against the frozen `_simulate_trade` on **400** trades (exit date, exit price and both flags identical). Read-only; the frozen engine was neither edited nor subclassed.


## 1. What the whole book looks like under each entry rule

`kept` = share of the baseline's trades this rule still takes. R is measured against the risk ACTUALLY taken (`|fill - SL|`), so a worse fill is already charged for. `tp_hit` is a target touch; `win` also counts a right-edge mark that happens to be positive. They diverge only by those marks - see the robustness table.


| entry rule | n | kept | mean R | median R | total R | win | tp_hit | t |
|---|---|---|---|---|---|---|---|---|
| baseline: fill at next open (frozen) | 1979 | 100% | -0.020 | -1.000 | -40.3 | 36% | 35% | -0.51 |
| stop @ prior-bar extreme, 1d | 1189 | 60% | -0.015 | -1.000 | -17.3 | 44% | 43% | -0.37 |
| ... + 0.33R ceiling (stop-limit), 1d | 1154 | 58% | -0.016 | -1.000 | -18.6 | 45% | 44% | -0.41 |
| ... + dead if stop hit first, 1d | 1086 | 55% | +0.046 | -1.000 | +49.4 | 48% | 47% | +1.11 |
| stop @ prior-bar extreme, 2d | 1383 | 70% | -0.031 | -1.000 | -42.4 | 45% | 44% | -0.88 |
| ... + 0.33R ceiling (stop-limit), 2d | 1342 | 68% | -0.031 | -1.000 | -41.8 | 45% | 44% | -0.88 |
| ... + dead if stop hit first, 2d | 1237 | 63% | +0.036 | -0.596 | +44.5 | 48% | 47% | +0.96 |
| stop @ prior-bar extreme, 3d | 1477 | 75% | -0.050 | -1.000 | -73.8 | 44% | 44% | -1.49 |
| ... + 0.33R ceiling (stop-limit), 3d | 1434 | 72% | -0.050 | -1.000 | -71.4 | 45% | 44% | -1.48 |
| ... + dead if stop hit first, 3d | 1301 | 66% | +0.021 | -1.000 | +26.7 | 48% | 47% | +0.57 |
| stop @ prior-bar extreme, 5d | 1586 | 80% | -0.061 | -1.000 | -96.2 | 44% | 44% | -1.91 |
| ... + 0.33R ceiling (stop-limit), 5d | 1540 | 78% | -0.061 | -1.000 | -93.3 | 45% | 44% | -1.89 |
| ... + dead if stop hit first, 5d | 1366 | 69% | +0.015 | -1.000 | +20.4 | 48% | 47% | +0.43 |

### 1b. Robustness: resolved trades only (right-edge marks dropped)

A trade still open at the right edge is marked to the last close by the frozen engine - a mark, not an outcome. A confirmation rule enters LATER, so it is more exposed to that fudge; if the ranking only survives WITH the marks, it is an artifact of the corpus end, not an entry effect.


| entry rule | n | mean R | median R | total R | tp_hit | t |
|---|---|---|---|---|---|---|
| baseline: fill at next open (frozen) | 1939 | -0.023 | -1.000 | -43.8 | 36% | -0.55 |
| stop+cap+sl, 1d | 1057 | +0.049 | -1.000 | +51.8 | 48% | +1.17 |
| stop+cap+sl, 2d | 1203 | +0.040 | -1.000 | +48.0 | 49% | +1.04 |
| stop+cap+sl, 3d | 1266 | +0.024 | -1.000 | +30.3 | 49% | +0.65 |
| stop+cap+sl, 5d | 1330 | +0.018 | -1.000 | +23.7 | 49% | +0.50 |

_Right-edge marks in the baseline: 40 of 1979 (2.0%)._


## 2. Selection vs fill cost - the two effects separated

Left block = the baseline restricted to the trades this rule also took (pure selection). Right = paired mean dR on that same intersection (pure fill cost).


| entry rule | n_int | baseline R on int | variant R on int | paired dR | t(dR) |
|---|---|---|---|---|---|
| stop, 1d | 1189 | +0.229 | -0.015 | -0.243 | -7.28 |
| stop+cap, 1d | 1154 | +0.235 | -0.016 | -0.251 | -7.28 |
| stop+cap+sl, 1d | 1086 | +0.312 | +0.046 | -0.266 | -7.29 |
| stop, 2d | 1383 | +0.209 | -0.031 | -0.240 | -7.96 |
| stop+cap, 2d | 1342 | +0.215 | -0.031 | -0.247 | -7.96 |
| stop+cap+sl, 2d | 1237 | +0.319 | +0.036 | -0.283 | -8.57 |
| stop, 3d | 1477 | +0.187 | -0.050 | -0.237 | -7.92 |
| stop+cap, 3d | 1434 | +0.187 | -0.050 | -0.237 | -7.88 |
| stop+cap+sl, 3d | 1301 | +0.308 | +0.021 | -0.288 | -8.98 |
| stop, 5d | 1586 | +0.164 | -0.061 | -0.225 | -7.76 |
| stop+cap, 5d | 1540 | +0.162 | -0.061 | -0.223 | -7.65 |
| stop+cap+sl, 5d | 1366 | +0.311 | +0.015 | -0.296 | -9.47 |

## 3. Does it survive inside every stop-width cohort?

The mandatory check: the R:R>=1 gate looked good in aggregate because it re-sorted the stop-width mix. A rule that only wins by shifting the mix is the same trap.


| cohort | baseline n / mean R | stop+cap+sl 5d n / mean R | delta |
|---|---|---|---|
| tight <2% | 313 / -0.119 | 100 / -0.052 | +0.068 |
| mid 2-5% | 702 / +0.018 | 501 / +0.099 | +0.080 |
| wide >5% | 964 / -0.016 | 765 / -0.031 | -0.015 |

## 3b. By classification


| class | baseline n / mean R | stop+cap+sl 5d n / mean R | delta |
|---|---|---|---|
| positional | 333 / -0.162 | 246 / -0.151 | +0.011 |
| swing | 1646 / +0.008 | 1120 / +0.051 | +0.043 |

## 3c. By direction


| side | baseline n / mean R | stop+cap+sl 5d n / mean R | delta |
|---|---|---|---|
| BUY | 1115 / -0.103 | 737 / -0.059 | +0.044 |
| SELL | 864 / +0.087 | 629 / +0.102 | +0.015 |

## 4. When does confirmation arrive? (the alert-timing question)

Day 1 = the bar the frozen engine fills on. This is the distribution the alert clock has to cover: a 1-day window is a different product from a 5-day one.


| day | triggered | cumulative share of 1979 baseline trades |
|---|---|---|
| +1 | 1189 | 60% |
| +2 | 194 | 70% |
| +3 | 94 | 75% |
| +4 | 63 | 78% |
| +5 | 46 | 80% |
| never (within 5d) | 393 | - |

## 5. What the OPEN alone tells you (the gap census)

Where the fill bar opened relative to the signal bar, and how the frozen baseline then did. `confirmed` = the trade also cleared the prior-bar extreme within the window.


| open vs signal bar | n | mean baseline R | share confirmed |
|---|---|---|---|
| SELL no gap dn | 631 | +0.112 | 80% |
| BUY partial up | 519 | -0.151 | 78% |
| BUY no gap up | 432 | -0.095 | 70% |
| SELL partial dn | 175 | +0.086 | 87% |
| BUY full gap up | 164 | +0.026 | 100% |
| SELL full gap dn | 58 | -0.191 | 100% |

_Census check: 1979 classified._
