# Q3.6 — the Minervini trend template on our closed book (2026-09-07)

The cycle-2 checklist accepts **either** answer — *tested or explicitly dropped* —
so this is written to reach a decision, not to defend the idea.

**91 closed positions evaluable** (14 skipped for want of 260
daily bars before entry or a defined return).

⚠ **No look-ahead:** every condition is computed from bars strictly BEFORE the entry
date (constraint #3). A template read on the entry bar would be using the day it is
meant to predict.

## Conditions 1–7 (the price/moving-average structure)

| cohort | n | mean return | win | total |
|---|--:|--:|--:|--:|
| **passes all of 1–7** | 0 | — | — | — |
| **fails at least one** | 91 | +0.175% | 49% | ₹-18,950 |

### Which condition bites, one at a time

| condition | n passing | mean return of passers |
|---|--:|--:|
| 1 close>SMA150,SMA200 | 61 | +0.352% |
| 2 SMA150>SMA200 | 25 | -0.545% |
| 3 SMA200 rising | 29 | +0.703% |
| 4 SMA50>SMA150,SMA200 | 46 | -0.026% |
| 5 close>SMA50 | 55 | +0.172% |
| 6 >=30% above 52w low | 45 | +0.051% |
| 7 within 25% of 52w high | 69 | -0.042% |

## Condition 8 (relative strength) — approximated

⚠ Minervini ranks against the **whole market** from a specific vendor. This ranks
the 6-month return **within the names we traded** — a smaller, self-selected
universe — so it is a weaker test and is reported separately.

| cohort | n | mean return | win | total |
|---|--:|--:|--:|--:|
| **passes 1–7 AND RS≥70** | 0 | — | — | — |

## Verdict

⛔ **NOT ONE of the 91 evaluable positions passes all seven conditions.**

That is not an uninformative split — it is a **disjoint** one. The template and
our engine are selecting from effectively non-overlapping sets, so this book
cannot test it: there is no passing cohort to compare a failing one against.

**The conditions that bind hardest:**

- `2 SMA150>SMA200` — only **25 of 91** entries pass
- `3 SMA200 rising` — only **29 of 91** entries pass
- `6 >=30% above 52w low` — only **45 of 91** entries pass

⭐ **Read that as a finding about OUR engine, not about Minervini.** The binding
conditions are the trend-structure ones, so a large majority of the names we
entered were in a structural DOWNTREND on his definition — trading below or
against their own long moving averages. Our selection is not a weaker version
of this template; it is close to its opposite.

On these 91 positions that book made **₹-18,950**.

**⇒ NOT a clean drop, and NOT a gate either.** The template makes a claim about
which names should be *eligible*, and the only honest test is a **universe-level
corpus rerun** — does applying it change what the engine generates, and is that
set better? That is a real piece of work, not a shadow gate, and it is the
correct next step if anyone wants to pursue it.

⚠ **It must NOT be shipped as a ninth selection gate.** On this book it would
block 100% of entries, which is not a filter — it is a different strategy
wearing a filter's clothes.

## ⚠ What this cannot tell you

- **These are the names our engine chose**, not a cross-section. The template could
  work as a universe filter and be invisible here, which is exactly why a favourable
  direction argues for a corpus rerun rather than a gate.
- **Condition 8 is approximated** within the traded set (see above).
- **~3 years of daily history**, all of it one broad regime.
