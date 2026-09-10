# Overhead supply - is the +6% swing target reachable?

_Generated 2026-09-09 - 250 liquid stocks - CA-clean window from 2023-07-03 - 82,212 stock-days._


`overhead` = share of the trailing 250-session traded volume that changed hands between today's close and +6% above it (the frozen swing target). Quintile 0 = least trapped supply overhead, 4 = most. Volume is attributed to each bar's close.


Quintile cuts: 0.037, 0.078, 0.125, 0.191


## O-1: P(the +6% target is touched within k sessions)


| overhead quintile | horizon | n | P(reach) | t (daily) |
|---|---|---|---|---|
| Q0 | +5d | 16,443 | 34.3% | +39.0 (518d) |
| Q1 | +5d | 16,442 | 30.8% | +36.7 (518d) |
| Q2 | +5d | 16,442 | 29.1% | +35.3 (518d) |
| Q3 | +5d | 16,442 | 25.3% | +32.7 (518d) |
| Q4 | +5d | 16,443 | 21.5% | +29.9 (518d) |
| Q0 | +10d | 16,443 | 49.3% | +52.3 (518d) |
| Q1 | +10d | 16,442 | 45.9% | +50.0 (518d) |
| Q2 | +10d | 16,442 | 43.8% | +46.7 (518d) |
| Q3 | +10d | 16,442 | 39.8% | +44.9 (518d) |
| Q4 | +10d | 16,443 | 35.4% | +40.3 (518d) |
| Q0 | +20d | 16,443 | 63.3% | +72.3 (518d) |
| Q1 | +20d | 16,442 | 60.5% | +67.4 (518d) |
| Q2 | +20d | 16,442 | 57.7% | +63.6 (518d) |
| Q3 | +20d | 16,442 | 54.7% | +61.3 (518d) |
| Q4 | +20d | 16,443 | 49.6% | +53.4 (518d) |

## O-2: forward excess return, market-demeaned


| overhead quintile | horizon | n | mean excess % | t (daily) |
|---|---|---|---|---|
| Q0 | +5d | 16,443 | +0.210% | +4.36 (518d) |
| Q1 | +5d | 16,442 | +0.033% | +0.74 (518d) |
| Q2 | +5d | 16,442 | +0.037% | +0.88 (518d) |
| Q3 | +5d | 16,442 | -0.088% | -2.00 (518d) |
| Q4 | +5d | 16,443 | -0.163% | -3.03 (518d) |
| Q0 | +10d | 16,443 | +0.403% | +6.18 (518d) |
| Q1 | +10d | 16,442 | +0.159% | +2.49 (518d) |
| Q2 | +10d | 16,442 | -0.019% | -0.30 (518d) |
| Q3 | +10d | 16,442 | -0.251% | -3.97 (518d) |
| Q4 | +10d | 16,443 | -0.308% | -3.94 (518d) |
| Q0 | +20d | 16,443 | +0.789% | +8.57 (518d) |
| Q1 | +20d | 16,442 | +0.257% | +2.73 (518d) |
| Q2 | +20d | 16,442 | -0.102% | -1.09 (518d) |
| Q3 | +20d | 16,442 | -0.275% | -3.08 (518d) |
| Q4 | +20d | 16,443 | -0.637% | -5.83 (518d) |

## O-3 (the proxy check): the same gradient WITHIN a control tercile

If `overhead` is only a disguise for volatility or momentum, the Q0-Q4 spread collapses once the control is held roughly fixed. `spread` = Q0 mean excess - Q4 mean excess at +10d; the whole-sample spread is the row labelled `(none)`.


Volatility (60d daily-return sd) terciles at: 0.0205, 0.0279

12m momentum terciles at: -0.139, +0.206


| control | tercile | n | Q0 excess | Q4 excess | spread (Q0-Q4) |
|---|---|---|---|---|---|
| (none) | whole sample | 32,886 | +0.403% | -0.308% | **+0.711%** |
| volatility | low | 12,524 | -0.443% | -0.214% | **-0.229%** |
| volatility | mid | 10,716 | +0.331% | -0.159% | **+0.490%** |
| volatility | high | 9,646 | +0.526% | -0.726% | **+1.253%** |
| 12m momentum | low | 10,913 | +0.366% | -0.489% | **+0.855%** |
| 12m momentum | mid | 11,674 | -0.229% | -0.315% | **+0.086%** |
| 12m momentum | high | 10,299 | +0.846% | +0.139% | **+0.706%** |

## Reading it

- O-1's `t` is the t of the daily mean HIT RATE, so it tests 'is this rate different from zero', which is uninteresting on its own. **Read the SPREAD across quintiles**: if Q0's P(reach) materially exceeds Q4's, overhead supply predicts reachability and is a candidate veto. If the quintiles are flat, it does not.
- O-2 is the profitability side, market-neutral. A monotone gradient there is the stronger claim.
- Neither is a promotion. The bar is t ~ 3.6 on a trade series (`docs/analysis/dsr-negative-control-2026-09-04.md`).
