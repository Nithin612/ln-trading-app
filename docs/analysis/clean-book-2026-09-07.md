# The book without the trades that were never really chosen (2026-09-07)

**106 closed paper positions.** Exclusion threshold `settings.chase_max_r = 0.33` — read from the same setting `chase_guard.py` enforces, never copied (W5).

## ⚠ No mis-click is recorded anywhere

Nothing in `CHANGELOG.md`, `docs/`, the phase docs or the memory files marks a
position as unintended, and there is no intent field on `positions`. What follows
is a **forensic reconstruction from execution signatures** and can be wrong about
any individual trade.

## ⚠ The 'wrong button' class is empty

- LONG opened on a SELL signal (or the reverse): **0 of 106**
- entered through its own stop: **1** (the side-blind `size_for_fill` bug, fixed forward-only)

Nobody bought a sell signal. Whatever went wrong was not a mis-click.

## The book, split

| set | n | realised ₹ | total R | win% |
|---|--:|--:|--:|--:|
| **KEEP** — entered at or near the signal | 93 | ₹13,262 | +18.8R | 55% |
| EXCLUDE — filled >0.33R past the signal entry | 12 | ₹-21,609 | -9.1R | 25% |
| EXCLUDE — R not computable (stop on the wrong side of the fill) | 1 | ₹-4,022 | +0.0R | 0% |

⭐ **The book as recorded is ₹-12,369. Without those 13 trades it is ₹13,262** — a swing of ₹25,631 across 12% of the positions.

## ⚠⚠ But 'chased' is largely a proxy for 'tight stop'

Displacement is measured in units of the **stop distance**, so a tight stop
mechanically inflates it: a stock that ran ₹1 past its entry is 0.1R chased on a
₹10 stop and 1.0R chased on a ₹1 stop. Same price action, opposite verdict.

| set | n | avg stop width | tight stops (<2%) |
|---|--:|--:|--:|
| clean | 93 | 5.33% | 5 |
| chased | 12 | 2.13% | 8 |

CLAUDE.md already records the tight-stop leak independently — *14 trades with
stops <2% of price lost ₹25,951 at 29% win*. The two partitions overlap heavily.

| stop | entry | n | ₹ | avg R | win% |
|---|---|--:|--:|--:|--:|
| tight (<2%) | chased | 8 | ₹-15,548 | -0.84 | 38% |
| tight (<2%) | clean | 5 | ₹-6,381 | +1.14 | 20% |
| wide (>=2%) | chased | 4 | ₹-6,061 | -0.60 | 0% |
| wide (>=2%) | clean | 88 | ₹19,643 | +0.15 | 57% |

**The cells are too small to separate the two effects.** Chasing survives inside
the wide-stop group, which is the cleanest look available — but on a handful of
trades. Read this as *two entangled defects*, not a measurement of chasing.

## Does excluding them change the EXIT verdict? No.

| peak bucket | n | peak R | realised R | capture |
|---|--:|--:|--:|--:|
| <0.25R (incl. never above entry) | 29 | 1.2R | -17.7R | — (no peak) |
| 0.25-0.5R | 14 | 5.2R | -4.2R | — (no peak) |
| 0.5-1R | 18 | 13.1R | +5.9R | 45% |
| 1-2R | 22 | 28.8R | +20.2R | 70% |
| >=2R | 3 | 7.8R | +5.1R | 65% |

⭐ On the clean set the exits still keep **63%** of peak on the 43 trades that reached 0.5R, and **43 of 86** still never got there (₹-47,751).

**⇒ The exit conclusion is robust to the exclusion.** Removing the badly-entered
trades does not turn this into an exit problem; it makes the entry problem smaller
without moving where it lives.

## ⚠ What this does NOT license

- **Flipping `chase_gate_mode` active.** n = 12. The bar is
  t ≈ 3.6 and it is flat in n — more data will not lower it.
- **Treating ₹13,262 as a P&L we could have had.** Removing the worst
  12% of any book improves it. The only reason this
  cut is not hindsight is that displacement is knowable BEFORE the order.
