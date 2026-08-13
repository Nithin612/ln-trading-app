# Regime-gate shadow (live cohort) — 2026-08-13

_Read-only. What the regime overlay (skip: transitional (20–25)) WOULD do to the live tradeable cohort since 2026-07-19 — the forward, live counterpart to the §8 backtest (`gate-walkforward-*.md`). SHADOW: nothing is suppressed. Same §8 metrics; a POSITIVE `killed (suppressed)` row means the live tape disagrees with the backtest — do not flip to active._

| variant | trades | decided | win% | Sharpe | maxDD R | total-R | mean expR | reach1R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| baseline (all live signals) | 210 | 98 | 36% | -0.020 | 8.8 | -3.4 | -0.034 | 28% |
| gated (kept — would trade) | 113 | 58 | 36% | -0.010 | 4.7 | -0.9 | -0.016 | 30% |
| killed (suppressed) | 97 | 40 | 35% | -0.032 | 6.4 | -2.4 | -0.061 | 26% |

**Verdict:** Consistent with the backtest: gating lifts live expectancy -0.034→-0.016 and the suppressed set is net-negative (-0.061). Keep accruing before flipping.

