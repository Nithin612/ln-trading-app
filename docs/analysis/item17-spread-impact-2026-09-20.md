# Item 17 — spread and impact on the intraday cohort, measured

**Run 2026-09-20** against the pre-registration committed at `6a4af12`, before this
script existed. Read-only; both sealed holdouts untouched.

## Verdict

**BRANCH A — NOT BINDING — spread does not close the intraday thesis.**

Abdi-Ranaldo median half-spread **1.74 bps**, 90% cluster-bootstrap interval
**[1.58, 1.93]**. The pre-registration evaluates the branch on the bound
unfavourable to proceeding, so **1.93 bps** is the number the tree reads.

| quantity | value |
|---|--:|
| name-windows measured | 6,748 |
| measurement windows | 37 of 21-session blocks |
| median cohort per window | 185 names |
| **AR median half-spread** | **1.74 bps** [1.58, 1.93] |
| AR zero-clamp share | 28.6% |
| CS median half-spread (biased UP) | 3.28 bps [3.12, 3.43] |
| median per-bar volatility | 17.9 bps |
| degenerate (no-range) bars | 0.1% |
| **AR half-spread in TICKS** | **2.43** (one-tick market = 0.50) |
| median name price | Rs 989 |
| intraday round-trip charges @ Rs 20,000 | 10.60 bps |
| median participation impact @ Rs 20,000 | 0.00 bps |
| **implied intraday hurdle** | **14.09 bps** (upper bound 14.47) |

## How to read the two estimators

⛔ **Corwin-Schultz is a corroborating UPPER BOUND, not a measurement.** Its
zero-spread null is linear in volatility (4.33 bps of artifact at 30 bps/bar, 11.44 at
80), which is why the branch decision is taken on Abdi-Ranaldo alone — as
pre-registered. A CS reading above AR is expected and is not disagreement.

⭐ **The zero-clamp share (28.6%) is the independent read.** Validation
put it near 50% when the true spread is zero and near 0% once a real spread is present.

## ⭐ Does the estimate agree with the exchange's own tick grid?

A real market cannot be narrower than one tick, so a half-spread of about **0.50
ticks** is what a one-tick-wide book looks like. This is the only ground-truth-free
check available, and it is a PHYSICAL constraint rather than another estimator.

Measured median: **2.43 ticks** at a median price of Rs 989.

✅✅ **The strongest available outcome: 2.43 ticks means a book about 4.9 ticks wide.** That is comfortably clear of BOTH floors — the exchange's minimum increment (0.50 as a half-spread) and the estimator's own resolution — so this is a real multi-tick spread being measured, not an artifact and not a clamp.

## ⚠ The drift, and what a 0.00 window means

⛔ **A window reading 0.00 has CLAMPED — that is 'below the estimator's resolution',
never 'no spread'.** Under a true zero spread about half of windows clamp; the share
here is reported per window so a clamped window is never read as a measurement.

| period | windows | AR median | CS median | sigma/bar | clamp share |
|---|--:|--:|--:|--:|--:|
| before 2024-06 (Rs 0.05 grid) | 10 | 2.19 | 3.52 | 17.9 | 19.1% |
| from 2024-06 (Rs 0.01 sub-250) | 27 | 1.60 | 3.20 | 17.8 | 31.7% |

### The control: did the tick change actually cause it?

| price band | period | name-windows | AR median | sigma/bar | clamp share |
|---|---|--:|--:|--:|--:|
| below Rs 225 (tick DID change) | before 2024-06 | 359 | 2.66 | 21.8 | 21.7% |
| below Rs 225 (tick DID change) | from 2024-06 | 766 | 1.35 | 19.3 | 37.5% |
| Rs 225+ (tick UNCHANGED) | before 2024-06 | 1,300 | 2.12 | 17.0 | 18.4% |
| Rs 225+ (tick UNCHANGED) | from 2024-06 | 4,323 | 1.63 | 17.6 | 30.7% |

## Per-window detail

| # | window | cohort | AR median | CS median | sigma/bar | clamped |
|--:|---|--:|--:|--:|--:|--:|
| 0 | 2023-07-03..2023-07-31 | 166 | 2.07 | 3.21 | 16.3 | 22% |
| 1 | 2023-08-01..2023-08-30 | 167 | 2.40 | 3.31 | 16.2 | 16% |
| 2 | 2023-08-31..2023-09-29 | 164 | 2.01 | 3.39 | 16.9 | 19% |
| 3 | 2023-10-03..2023-11-01 | 168 | 2.46 | 3.34 | 16.1 | 18% |
| 4 | 2023-11-02..2023-12-04 | 165 | 1.92 | 3.05 | 15.3 | 21% |
| 5 | 2023-12-05..2024-01-03 | 165 | 1.88 | 3.49 | 17.7 | 22% |
| 6 | 2024-01-04..2024-02-02 | 162 | 2.71 | 3.85 | 20.3 | 18% |
| 7 | 2024-02-05..2024-03-02 | 167 | 2.41 | 4.04 | 20.9 | 17% |
| 8 | 2024-03-04..2024-04-04 | 166 | 1.85 | 3.90 | 21.0 | 25% |
| 9 | 2024-04-05..2024-05-08 | 169 | 2.54 | 3.71 | 19.4 | 14% |
| 10 | 2024-05-09..2024-06-06 | 168 | 2.40 | 4.67 | 27.6 | 33% |
| 11 | 2024-06-07..2024-07-08 | 170 | 2.17 | 3.57 | 17.7 | 16% |
| 12 | 2024-07-09..2024-08-07 | 173 | 1.73 | 3.90 | 20.4 | 36% |
| 13 | 2024-08-08..2024-09-06 | 173 | 1.94 | 3.23 | 16.1 | 17% |
| 14 | 2024-09-09..2024-10-08 | 175 | 2.06 | 3.53 | 18.6 | 25% |
| 15 | 2024-10-09..2024-11-07 | 179 | 2.53 | 4.03 | 20.9 | 21% |
| 16 | 2024-11-08..2024-12-10 | 181 | 2.47 | 3.58 | 19.2 | 18% |
| 17 | 2024-12-11..2025-01-09 | 181 | 1.99 | 3.29 | 17.2 | 18% |
| 18 | 2025-01-10..2025-02-06 | 185 | 1.85 | 4.06 | 23.2 | 33% |
| 19 | 2025-02-07..2025-03-10 | 187 | 2.82 | 4.25 | 22.6 | 17% |
| 20 | 2025-03-11..2025-04-11 | 188 | 1.45 | 3.71 | 21.3 | 40% |
| 21 | 2025-04-15..2025-05-15 | 189 | 2.72 | 3.58 | 20.5 | 12% |
| 22 | 2025-05-16..2025-06-13 | 189 | 2.15 | 2.96 | 16.1 | 20% |
| 23 | 2025-06-16..2025-07-14 | 190 | 1.58 | 2.76 | 15.3 | 19% |
| 24 | 2025-07-15..2025-08-12 | 191 | 1.69 | 2.79 | 15.5 | 27% |
| 25 | 2025-08-13..2025-09-12 | 194 | 0.00 | 2.36 | 13.9 | 63% |
| 26 | 2025-09-15..2025-10-14 | 195 | 1.38 | 2.62 | 14.6 | 23% |
| 27 | 2025-10-15..2025-11-14 | 200 | 1.39 | 2.68 | 15.4 | 36% |
| 28 | 2025-11-17..2025-12-15 | 200 | 1.64 | 2.52 | 14.2 | 18% |
| 29 | 2025-12-16..2026-01-14 | 202 | 0.00 | 2.64 | 15.2 | 53% |
| 30 | 2026-01-16..2026-02-13 | 203 | 0.00 | 3.45 | 21.2 | 53% |
| 31 | 2026-02-16..2026-03-17 | 200 | 0.00 | 3.34 | 19.0 | 63% |
| 32 | 2026-03-18..2026-04-21 | 200 | 1.71 | 3.61 | 19.9 | 27% |
| 33 | 2026-04-22..2026-05-21 | 199 | 0.72 | 3.25 | 18.9 | 47% |
| 34 | 2026-05-22..2026-06-22 | 191 | 1.10 | 2.96 | 17.4 | 40% |
| 35 | 2026-06-23..2026-07-22 | 193 | 1.11 | 2.80 | 16.6 | 38% |
| 36 | 2026-07-23..2026-08-20 | 193 | 1.43 | 2.67 | 15.3 | 35% |

## Limits, stated

⚠ **An estimate, not an observation.** No historical order book exists; item 17b
(forward top-of-book capture) is what would validate this against a real book.
⚠ **One cohort, one size.** Every bps figure is at the stated order value on the
PIT-liquid cohort; a thinner name or a larger order is a different question.
⚠ **Cost, not edge.** A favourable branch means the arithmetic does not forbid an
intraday generator. It does not mean one exists.

---

## ⭐⭐ Second pass — the drift is an ARTIFACT, and the tick change is
smaller than it looks

The headline median falls 2.19 -> 1.60 bps across mid-2024. Sliced on the dump, with
the clamped windows separated from the rest, it resolves completely.

| band | period | n | ticks (ALL) | n live | **ticks (NOT clamped)** | clamp |
|---|---|--:|--:|--:|--:|--:|
| below Rs 225 | before 2024-06 | 359 | 0.51 | 281 | **0.59** | 21.7% |
| below Rs 225 | from 2024-06 | 766 | 1.08 | 479 | **2.51** | 37.5% |
| Rs 225+ | before 2024-06 | 1,300 | 4.03 | 1,061 | **5.25** | 18.4% |
| Rs 225+ | from 2024-06 | 4,323 | 2.85 | 2,997 | **5.46** | 30.7% |

### ⛔ Finding 1 — the cohort-wide decline is the CLAMP, not the market

On the Rs 225+ band, whose tick **never changed**, the half-spread
in ticks is **flat on non-clamped windows: 5.25 -> 5.46**, while the
all-windows median falls. The difference is entirely the clamp share rising
18.4% -> 30.7%.

⭐ **And the mechanism is arithmetic, not mysterious.** The median price rose
Rs 1,140 -> Rs 1,316 against a FIXED Rs 0.05 tick, so the same book in
ticks is a smaller spread in bps. A smaller spread at the same volatility is a worse
signal-to-noise ratio for the estimator, so more windows fall under its resolution and
clamp. **Falling bps and a rising clamp share are the same fact seen twice.**

### ⭐ Finding 2 — the tick change UNPINNED the cheap band more than it narrowed it

Before the change **64.8%** of sub-Rs 225 windows sat at or under
0.75 ticks — a book pinned on the exchange's minimum increment, which is the
signature of **the tick size itself being the binding constraint**. After, only
**15.0%** are.

⚠ **But the narrowing is far smaller than the bps figures suggest.** In rupees the
median half-spread went **Rs 0.0296 -> Rs 0.0263** (-11%), not the
~50% the clamped medians imply.

### What this does to the headline

⚠ **The pooled 1.74 bps is a LOWER bound** — clamped windows report 0.00 and drag
it down. On non-clamped windows the recent-period median is **2.20 bps**.
⭐ **The true typical half-spread is bracketed at 1.74-2.20 bps, and the branch verdict does not move**: both ends are far below
the pre-registered 5 bps boundary, and the implied hurdle spans 14.1-15.0 bps.

⛔ **Neither bound is a measurement of a real book.** Item 17b is
what would settle it.
