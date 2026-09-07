# R1 pre-screen — do VWAP / RVOL separate our outcomes? (2026-09-07)

**Run before the frozen-engine work, not after.** Adding a confluence factor costs a
Python impl **plus a byte-identical Rust impl**, 7 regenerated golden fixtures, exact
parity on scores/confidence/decisions, an §8 regression and a hook-protected spec
change. Days. So first: does either quantity separate winners from losers on the
trades we actually took? **105 closed positions** (0 skipped for
insufficient history).

⚠ No look-ahead — both computed from bars strictly BEFORE the entry date.

## 1. RVOL (graded) — the factor that already exists

⭐ `volume_factor` already computes `current / 20-day average`. It is **binarised** at
`>= 1.5` → `+0.5`, else `0.0`. So the real R1 question is whether the
**magnitude** carries information the threshold discards.

| quintile | n | mean RVOL | mean return | win | total |
|---|--:|--:|--:|--:|--:|
| Q1 | 21 | 0.35× | +0.419% | 57% | ₹-842 |
| Q2 | 21 | 0.61× | +1.202% | 62% | ₹3,800 |
| Q3 | 21 | 0.74× | -0.016% | 43% | ₹2,052 |
| Q4 | 21 | 1.15× | +1.689% | 52% | ₹-5,702 |
| Q5 | 21 | 3.64× | -1.384% | 43% | ₹-9,526 |

### And how the LIVE binary threshold actually splits

| cohort | n | mean return | win | total |
|---|--:|--:|--:|--:|
| RVOL ≥ 1.5 (factor fires) | 18 | -0.708% | 50% | ₹-2,821 |
| RVOL < 1.5 (silent) | 87 | +0.608% | 52% | ₹-7,397 |

## 2. Anchored VWAP gap — price vs its own 20-day volume-weighted average

⚠ **The anchor is a stand-in.** Session VWAP does not exist on daily bars; a real
anchored VWAP would run from a swing pivot, and *choosing that anchor is a spec
decision*. A 20-day anchor is used here to get a first read.

| quintile | n | mean gap | mean return | win | total |
|---|--:|--:|--:|--:|--:|
| Q1 | 21 | -4.41% | +0.020% | 43% | ₹-5,206 |
| Q2 | 21 | -1.67% | +0.452% | 43% | ₹179 |
| Q3 | 21 | -0.26% | +0.271% | 48% | ₹-18,206 |
| Q4 | 21 | 2.31% | +0.322% | 52% | ₹549 |
| Q5 | 21 | 4.96% | +0.845% | 71% | ₹12,465 |

## Verdict

- **RVOL** Q5−Q1 spread: **-1.802 pp**
- **VWAP gap** Q5−Q1 spread: **+0.825 pp**

⚠ **n ≈ 21 per quintile.** Nothing here approaches the t ≈ 3.6 bar, and that bar does
not fall with more data. This is a **screen**, not a test: it exists to decide whether
the expensive engine change is worth starting, not to promote anything.

**How to read it:** a monotonic gradient with a wide spread would justify the frozen-
engine work. A flat or non-monotonic one says the factor carries nothing our existing
confluence does not already have — and the fixtures, parity work and spec change
should not be spent.
