# Confirmation base rate - does breaking yesterday's high pay, on its own?

_Generated 2026-09-09 - 250 liquid stocks - CA-clean window from 2023-07-03 - 108,506 stock-days, 49,060 (45.2%) traded through the prior high._


Forward return in %, from the stated entry price to the close k sessions later. **t is computed on the daily cross-sectional mean series** (n = trading days), never per trade - overlapping windows across days and stocks would inflate a per-trade t by roughly an order of magnitude.


## Horizon: close in +1 session(s)


| cohort | stock-days | mean fwd % | t (daily x-sec) |
|---|---|---|---|
| all: enter at open | 108,506 | -0.088% | -1.21 (628d) |
| confirmed: enter at open (same days) | 49,060 | +0.985% | +13.40 (628d) |
| confirmed: enter at trigger | 49,060 | -0.208% | -3.28 (628d) |
| not confirmed: enter at open | 59,446 | -0.924% | -13.69 (627d) |
| confirmed + above rising 150DMA [from trigger] | 21,358 | -0.310% | -3.96 (624d) |
| confirmed + NOT above rising 150DMA [from trigger] | 27,702 | -0.156% | -2.29 (628d) |
| confirmed + above rising 150DMA [from close] | 21,358 | -0.029% | -0.46 (624d) |
| confirmed + NOT above rising 150DMA [from close] | 27,702 | +0.043% | +0.79 (628d) |
| confirmed + QUIET bar [from trigger] | 25,265 | -1.056% | -17.78 (626d) |
| confirmed + HOT bar [from trigger] | 23,795 | +0.736% | +9.54 (628d) |
| confirmed + QUIET bar [from close] | 25,265 | -0.002% | -0.05 (626d) |
| confirmed + HOT bar [from close] | 23,795 | +0.039% | +0.73 (628d) |

## Horizon: close in +3 session(s)


| cohort | stock-days | mean fwd % | t (daily x-sec) |
|---|---|---|---|
| all: enter at open | 108,506 | +0.032% | +0.29 (628d) |
| confirmed: enter at open (same days) | 49,060 | +1.109% | +10.21 (628d) |
| confirmed: enter at trigger | 49,060 | -0.087% | -0.88 (628d) |
| not confirmed: enter at open | 59,446 | -0.789% | -7.41 (627d) |
| confirmed + above rising 150DMA [from trigger] | 21,358 | -0.197% | -1.73 (624d) |
| confirmed + NOT above rising 150DMA [from trigger] | 27,702 | -0.081% | -0.74 (628d) |
| confirmed + above rising 150DMA [from close] | 21,358 | +0.089% | +0.84 (624d) |
| confirmed + NOT above rising 150DMA [from close] | 27,702 | +0.120% | +1.18 (628d) |
| confirmed + QUIET bar [from trigger] | 25,265 | -0.845% | -8.58 (626d) |
| confirmed + HOT bar [from trigger] | 23,795 | +0.747% | +6.82 (628d) |
| confirmed + QUIET bar [from close] | 25,265 | +0.211% | +2.21 (626d) |
| confirmed + HOT bar [from close] | 23,795 | +0.053% | +0.56 (628d) |

## Horizon: close in +5 session(s)


| cohort | stock-days | mean fwd % | t (daily x-sec) |
|---|---|---|---|
| all: enter at open | 108,506 | +0.145% | +1.06 (628d) |
| confirmed: enter at open (same days) | 49,060 | +1.177% | +8.54 (628d) |
| confirmed: enter at trigger | 49,060 | -0.022% | -0.17 (628d) |
| not confirmed: enter at open | 59,446 | -0.665% | -4.94 (627d) |
| confirmed + above rising 150DMA [from trigger] | 21,358 | -0.142% | -0.95 (624d) |
| confirmed + NOT above rising 150DMA [from trigger] | 27,702 | -0.031% | -0.22 (628d) |
| confirmed + above rising 150DMA [from close] | 21,358 | +0.145% | +1.00 (624d) |
| confirmed + NOT above rising 150DMA [from close] | 27,702 | +0.170% | +1.26 (628d) |
| confirmed + QUIET bar [from trigger] | 25,265 | -0.819% | -6.34 (626d) |
| confirmed + HOT bar [from trigger] | 23,795 | +0.839% | +6.09 (628d) |
| confirmed + QUIET bar [from close] | 25,265 | +0.238% | +1.86 (626d) |
| confirmed + HOT bar [from close] | 23,795 | +0.147% | +1.15 (628d) |

## Horizon: close in +10 session(s)


| cohort | stock-days | mean fwd % | t (daily x-sec) |
|---|---|---|---|
| all: enter at open | 108,506 | +0.410% | +2.27 (628d) |
| confirmed: enter at open (same days) | 49,060 | +1.415% | +7.77 (628d) |
| confirmed: enter at trigger | 49,060 | +0.211% | +1.23 (628d) |
| not confirmed: enter at open | 59,446 | -0.378% | -2.10 (627d) |
| confirmed + above rising 150DMA [from trigger] | 21,358 | +0.198% | +1.03 (624d) |
| confirmed + NOT above rising 150DMA [from trigger] | 27,702 | +0.032% | +0.17 (628d) |
| confirmed + above rising 150DMA [from close] | 21,358 | +0.487% | +2.54 (624d) |
| confirmed + NOT above rising 150DMA [from close] | 27,702 | +0.239% | +1.30 (628d) |
| confirmed + QUIET bar [from trigger] | 25,265 | -0.586% | -3.36 (626d) |
| confirmed + HOT bar [from trigger] | 23,795 | +1.050% | +5.73 (628d) |
| confirmed + QUIET bar [from close] | 25,265 | +0.477% | +2.71 (626d) |
| confirmed + HOT bar [from close] | 23,795 | +0.361% | +2.04 (628d) |

## Reading it

- **`confirmed: enter at open (same days)` is NOT a strategy.** It uses information (that the day WILL trade through the prior high) that does not exist at the open. It is here only to decompose the rule: against `confirmed: enter at trigger` it isolates the **price paid** for confirmation with the day set held fixed, and against `not confirmed` it isolates the **selection** effect.
- The only two implementable rows are `all: enter at open` and `confirmed: enter at trigger`. Those are the two that decide H-A.
- For H-B and H-C read the `[from close]` rows: `[from trigger]` spans the rest of the entry day and so rewards a bar that has already run.
