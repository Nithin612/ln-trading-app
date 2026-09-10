# Overhead supply - is the +6% swing target reachable?

_Generated 2026-09-10 - 250 liquid stocks - window from 2023-07-03 - 81,567 stock-days (645 dropped for an unadjusted corporate action in the forward window)._


`overhead` = share of the trailing 250-session traded volume that changed hands between today's close and +6% above it (the frozen swing target). Quintile 0 = least trapped supply overhead, 4 = most. Volume is attributed to each bar's close.


Quintile cuts: 0.037, 0.078, 0.125, 0.191


## O-1: P(the +6% target is touched within k sessions) - and its downside twin

⚠ A reachability gradient is NOT an opportunity gradient. The same volatility that makes the +6% target easier to touch makes the −8% stop easier to touch too, so `P(stop)` is reported beside it and the spread between them is the only number that could mean anything. (Neither is a trade: a real trade stops at whichever comes FIRST, which daily bars cannot resolve.)


| overhead quintile | horizon | n | P(+6% touched) | P(−8% touched) | spread |
|---|---|---|---|---|---|
| Q0 | +5d | 16,314 | 34.2% | 16.8% | +17.3pp |
| Q1 | +5d | 16,313 | 30.9% | 15.2% | +15.7pp |
| Q2 | +5d | 16,313 | 29.1% | 13.6% | +15.5pp |
| Q3 | +5d | 16,313 | 25.3% | 11.5% | +13.8pp |
| Q4 | +5d | 16,314 | 21.5% | 9.6% | +11.9pp |
| Q0 | +10d | 16,314 | 49.1% | 31.3% | +17.8pp |
| Q1 | +10d | 16,313 | 45.9% | 30.1% | +15.8pp |
| Q2 | +10d | 16,313 | 43.9% | 27.7% | +16.2pp |
| Q3 | +10d | 16,313 | 39.8% | 25.7% | +14.0pp |
| Q4 | +10d | 16,314 | 35.3% | 21.4% | +13.9pp |
| Q0 | +20d | 16,314 | 63.3% | 46.5% | +16.8pp |
| Q1 | +20d | 16,313 | 60.6% | 46.6% | +14.0pp |
| Q2 | +20d | 16,313 | 57.7% | 44.2% | +13.5pp |
| Q3 | +20d | 16,313 | 54.7% | 42.7% | +12.1pp |
| Q4 | +20d | 16,314 | 49.5% | 37.5% | +12.0pp |

## O-2: forward excess return, market-demeaned


| overhead quintile | horizon | n | mean excess % | t (Newey-West) | naive t |
|---|---|---|---|---|---|
| Q0 | +5d | 16,314 | +0.192% | +3.10 (518d) | +4.18 |
| Q1 | +5d | 16,313 | +0.023% | +0.48 (518d) | +0.59 |
| Q2 | +5d | 16,313 | +0.014% | +0.30 (518d) | +0.37 |
| Q3 | +5d | 16,313 | -0.108% | -2.20 (518d) | -2.63 |
| Q4 | +5d | 16,314 | -0.160% | -2.18 (518d) | -3.25 |
| Q0 | +10d | 16,314 | +0.386% | +3.92 (518d) | +6.38 |
| Q1 | +10d | 16,313 | +0.084% | +1.07 (518d) | +1.43 |
| Q2 | +10d | 16,313 | -0.021% | -0.27 (518d) | -0.38 |
| Q3 | +10d | 16,313 | -0.261% | -3.25 (518d) | -4.55 |
| Q4 | +10d | 16,314 | -0.312% | -2.32 (518d) | -4.51 |
| Q0 | +20d | 16,314 | +0.669% | +3.60 (518d) | +7.63 |
| Q1 | +20d | 16,313 | +0.156% | +1.22 (518d) | +1.83 |
| Q2 | +20d | 16,313 | -0.058% | -0.53 (518d) | -0.72 |
| Q3 | +20d | 16,313 | -0.281% | -2.22 (518d) | -3.43 |
| Q4 | +20d | 16,314 | -0.585% | -2.68 (518d) | -6.20 |

## O-3 (the proxy check): the same gradient WITHIN a control tercile

If `overhead` is only a disguise for volatility or momentum, the Q0-Q4 spread collapses once the control is held roughly fixed. `spread` = Q0 mean excess - Q4 mean excess at +10d; the whole-sample spread is the row labelled `(none)`.


Volatility (60d daily-return sd) terciles at: 0.0205, 0.0279

12m momentum terciles at: -0.139, +0.205


| control | tercile | n | Q0 excess | Q4 excess | spread (Q0-Q4) |
|---|---|---|---|---|---|
| (none) | whole sample | 32,628 | +0.386% | -0.312% | **+0.698%** |
| volatility | low | 12,411 | -0.299% | -0.147% | **-0.153%** |
| volatility | mid | 10,648 | +0.130% | -0.261% | **+0.390%** |
| volatility | high | 9,569 | +0.591% | -0.782% | **+1.373%** |
| 12m momentum | low | 10,828 | +0.250% | -0.598% | **+0.848%** |
| 12m momentum | mid | 11,575 | -0.269% | -0.240% | **-0.029%** |
| 12m momentum | high | 10,225 | +0.818% | -0.010% | **+0.828%** |

### O-3b: the proxy check on O-1 too (reachability, not just return)

O-1 is the outcome most mechanically driven by volatility, and Q0 IS the volatile end. If the reachability gradient is a volatility artefact it should shrink sharply once volatility is held roughly fixed.


| control | tercile | Q0 P(reach) | Q4 P(reach) | spread |
|---|---|---|---|---|
| (none) | whole sample | 49.1% | 35.3% | **+13.8pp** |
| volatility | low | 36.1% | 32.0% | **+4.2pp** |
| volatility | mid | 47.4% | 37.2% | **+10.1pp** |
| volatility | high | 56.9% | 41.4% | **+15.5pp** |
| 12m momentum | low | 48.5% | 35.2% | **+13.3pp** |
| 12m momentum | mid | 41.2% | 34.4% | **+6.8pp** |
| 12m momentum | high | 51.6% | 41.1% | **+10.5pp** |

## Reading it

- O-1's `t` is the t of the daily mean HIT RATE, so it tests 'is this rate different from zero', which is uninteresting on its own. **Read the SPREAD across quintiles**: if Q0's P(reach) materially exceeds Q4's, overhead supply predicts reachability and is a candidate veto. If the quintiles are flat, it does not.
- O-2 is the profitability side, market-neutral. A monotone gradient there is the stronger claim.
- Neither is a promotion. The bar is t ~ 3.6 on a trade series (`docs/analysis/dsr-negative-control-2026-09-04.md`).
