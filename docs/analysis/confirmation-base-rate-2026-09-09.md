# Confirmation base rate - does breaking yesterday's high pay, on its own?

_Generated 2026-09-10 - 250 liquid stocks - window from 2023-07-03 - 108,506 stock-days, 49,060 (45.2%) traded through the prior high. **841 stock-day/horizon observations dropped** because an unadjusted corporate action (|close-to-close| > 25%) fell inside the forward window._


Forward return in %, from the stated entry price to the close k sessions later. **`t` is Newey-West at lag k-1 on the daily cross-sectional mean series**; `naive t` is the uncorrected one, shown only so the size of the overlap correction is visible. Averaging the cross-section removes same-day dependence but NOT the overlap between day t and day t+1, which share k-1 sessions of the same future - under H0 that inflates the naive t by ~sqrt(k) (sd 3.32 at k=10, 4.45 at k=20).


## Horizon: close in +1 session(s)


| cohort | stock-days | mean fwd % | t (Newey-West) | naive t |
|---|---|---|---|---|
| all: enter at open | 108,432 | -0.070% | -0.96 (628d) | -0.96 |
| confirmed: enter at open (same days) | 49,036 | +1.018% | +13.85 (628d) | +13.83 |
| confirmed: enter at trigger | 49,036 | -0.176% | -2.78 (628d) | -2.78 |
| confirmed + under a 2% ceiling (Weinstein) | 47,641 | -0.172% | -2.75 (628d) | -2.75 |
| not confirmed: enter at open | 59,396 | -0.915% | -13.60 (627d) | -13.59 |
| confirmed + above rising 150DMA [from trigger] | 21,341 | -0.231% | -3.30 (624d) | -3.29 |
| confirmed + NOT above rising 150DMA [from trigger] | 27,695 | -0.139% | -2.07 (628d) | -2.06 |
| confirmed + above rising 150DMA [from close] | 21,341 | +0.051% | +0.97 (624d) | +0.97 |
| confirmed + NOT above rising 150DMA [from close] | 27,695 | +0.060% | +1.13 (628d) | +1.12 |
| confirmed + QUIET bar [from trigger] | 25,257 | -1.028% | -17.76 (626d) | -17.74 |
| confirmed + HOT bar [from trigger] | 23,779 | +0.775% | +10.06 (628d) | +10.06 |
| confirmed + QUIET bar [from close] | 25,257 | +0.026% | +0.51 (626d) | +0.51 |
| confirmed + HOT bar [from close] | 23,779 | +0.078% | +1.48 (628d) | +1.48 |

## Horizon: close in +3 session(s)


| cohort | stock-days | mean fwd % | t (Newey-West) | naive t |
|---|---|---|---|---|
| all: enter at open | 108,358 | +0.087% | +0.53 (628d) | +0.80 |
| confirmed: enter at open (same days) | 49,001 | +1.177% | +9.40 (628d) | +10.87 |
| confirmed: enter at trigger | 49,001 | -0.020% | -0.17 (628d) | -0.20 |
| confirmed + under a 2% ceiling (Weinstein) | 47,608 | -0.010% | -0.09 (628d) | -0.10 |
| not confirmed: enter at open | 59,357 | -0.744% | -5.89 (627d) | -7.04 |
| confirmed + above rising 150DMA [from trigger] | 21,323 | -0.062% | -0.48 (624d) | -0.58 |
| confirmed + NOT above rising 150DMA [from trigger] | 27,678 | -0.028% | -0.23 (628d) | -0.27 |
| confirmed + above rising 150DMA [from close] | 21,323 | +0.227% | +1.96 (624d) | +2.32 |
| confirmed + NOT above rising 150DMA [from close] | 27,678 | +0.173% | +1.53 (628d) | +1.76 |
| confirmed + QUIET bar [from trigger] | 25,243 | -0.787% | -7.86 (626d) | -8.16 |
| confirmed + HOT bar [from trigger] | 23,758 | +0.830% | +7.30 (628d) | +7.59 |
| confirmed + QUIET bar [from close] | 25,243 | +0.269% | +2.76 (626d) | +2.88 |
| confirmed + HOT bar [from close] | 23,758 | +0.136% | +1.46 (628d) | +1.45 |

## Horizon: close in +5 session(s)


| cohort | stock-days | mean fwd % | t (Newey-West) | naive t |
|---|---|---|---|---|
| all: enter at open | 108,285 | +0.236% | +0.93 (628d) | +1.74 |
| confirmed: enter at open (same days) | 48,967 | +1.284% | +7.36 (628d) | +9.35 |
| confirmed: enter at trigger | 48,967 | +0.083% | +0.49 (628d) | +0.65 |
| confirmed + under a 2% ceiling (Weinstein) | 47,577 | +0.086% | +0.52 (628d) | +0.68 |
| not confirmed: enter at open | 59,318 | -0.586% | -3.11 (627d) | -4.40 |
| confirmed + above rising 150DMA [from trigger] | 21,301 | +0.081% | +0.42 (624d) | +0.59 |
| confirmed + NOT above rising 150DMA [from trigger] | 27,666 | +0.043% | +0.24 (628d) | +0.31 |
| confirmed + above rising 150DMA [from close] | 21,301 | +0.371% | +2.03 (624d) | +2.76 |
| confirmed + NOT above rising 150DMA [from close] | 27,666 | +0.245% | +1.47 (628d) | +1.83 |
| confirmed + QUIET bar [from trigger] | 25,231 | -0.723% | -5.15 (626d) | -5.72 |
| confirmed + HOT bar [from trigger] | 23,736 | +0.965% | +6.00 (628d) | +7.07 |
| confirmed + QUIET bar [from close] | 25,231 | +0.335% | +2.38 (626d) | +2.67 |
| confirmed + HOT bar [from close] | 23,736 | +0.273% | +1.92 (628d) | +2.16 |

## Horizon: close in +10 session(s)


| cohort | stock-days | mean fwd % | t (Newey-West) | naive t |
|---|---|---|---|---|
| all: enter at open | 108,108 | +0.591% | +1.29 (628d) | +3.29 |
| confirmed: enter at open (same days) | 48,868 | +1.632% | +5.38 (628d) | +9.05 |
| confirmed: enter at trigger | 48,868 | +0.426% | +1.44 (628d) | +2.50 |
| confirmed + under a 2% ceiling (Weinstein) | 47,484 | +0.419% | +1.45 (628d) | +2.47 |
| not confirmed: enter at open | 59,240 | -0.238% | -0.70 (627d) | -1.33 |
| confirmed + above rising 150DMA [from trigger] | 21,250 | +0.558% | +1.72 (624d) | +2.99 |
| confirmed + NOT above rising 150DMA [from trigger] | 27,618 | +0.196% | +0.68 (628d) | +1.06 |
| confirmed + above rising 150DMA [from close] | 21,250 | +0.850% | +2.68 (624d) | +4.57 |
| confirmed + NOT above rising 150DMA [from close] | 27,618 | +0.405% | +1.46 (628d) | +2.24 |
| confirmed + QUIET bar [from trigger] | 25,180 | -0.401% | -1.69 (626d) | -2.36 |
| confirmed + HOT bar [from trigger] | 23,688 | +1.307% | +5.35 (628d) | +7.23 |
| confirmed + QUIET bar [from close] | 25,180 | +0.663% | +2.75 (626d) | +3.86 |
| confirmed + HOT bar [from close] | 23,688 | +0.617% | +2.74 (628d) | +3.55 |

## The hypotheses, actually tested

Every table above reports the t of a LEVEL. A hypothesis is a DIFFERENCE, so each row here builds the daily series `mean(A) - mean(B)` over the days both cohorts occupy and reports the Newey-West t of that one series. This is the only place H-A/H-A2/H-B/H-C are decided; the level t's above cannot do it.


| hypothesis | A - B | horizon | days | mean diff | t (Newey-West) |
|---|---|---|---|---|---|
| H-A | `confirmed: enter at trigger` - `all: enter at open` | +1d | 628 | -0.107% | -3.46 |
| H-A | `confirmed: enter at trigger` - `all: enter at open` | +3d | 628 | -0.107% | -2.94 |
| H-A | `confirmed: enter at trigger` - `all: enter at open` | +5d | 628 | -0.153% | -3.51 |
| H-A | `confirmed: enter at trigger` - `all: enter at open` | +10d | 628 | -0.165% | -3.00 |
| H-A2 | `confirmed + under a 2% ceiling (Weinstein)` - `all: enter at open` | +1d | 628 | -0.102% | -3.24 |
| H-A2 | `confirmed + under a 2% ceiling (Weinstein)` - `all: enter at open` | +3d | 628 | -0.097% | -2.55 |
| H-A2 | `confirmed + under a 2% ceiling (Weinstein)` - `all: enter at open` | +5d | 628 | -0.150% | -3.35 |
| H-A2 | `confirmed + under a 2% ceiling (Weinstein)` - `all: enter at open` | +10d | 628 | -0.172% | -3.06 |
| H-B | `confirmed + above rising 150DMA [from close]` - `confirmed + NOT above rising 150DMA [from close]` | +1d | 624 | -0.013% | -0.35 |
| H-B | `confirmed + above rising 150DMA [from close]` - `confirmed + NOT above rising 150DMA [from close]` | +3d | 624 | +0.053% | +0.68 |
| H-B | `confirmed + above rising 150DMA [from close]` - `confirmed + NOT above rising 150DMA [from close]` | +5d | 624 | +0.139% | +1.15 |
| H-B | `confirmed + above rising 150DMA [from close]` - `confirmed + NOT above rising 150DMA [from close]` | +10d | 624 | +0.466% | +2.20 |
| H-C | `confirmed + QUIET bar [from close]` - `confirmed + HOT bar [from close]` | +1d | 626 | -0.046% | -1.44 |
| H-C | `confirmed + QUIET bar [from close]` - `confirmed + HOT bar [from close]` | +3d | 626 | +0.150% | +2.70 |
| H-C | `confirmed + QUIET bar [from close]` - `confirmed + HOT bar [from close]` | +5d | 626 | +0.088% | +1.35 |
| H-C | `confirmed + QUIET bar [from close]` - `confirmed + HOT bar [from close]` | +10d | 626 | +0.086% | +1.06 |

## Reading it

- **`confirmed: enter at open (same days)` is NOT a strategy.** It uses information (that the day WILL trade through the prior high) that does not exist at the open. It is here only to decompose the rule: against `confirmed: enter at trigger` it isolates the **price paid** for confirmation with the day set held fixed, and against `not confirmed` it isolates the **selection** effect.
- The only two implementable rows are `all: enter at open` and `confirmed: enter at trigger`. Those are the two that decide H-A.
- For H-B and H-C read the `[from close]` rows: `[from trigger]` spans the rest of the entry day and so rewards a bar that has already run.
