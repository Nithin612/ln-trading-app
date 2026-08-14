# Regime-gate shadow (live cohort) — 2026-08-14

_Read-only. What the regime overlay (skip: transitional (20–25)) WOULD do to the live tradeable cohort since 2026-07-19 — the forward, live counterpart to the §8 backtest (`gate-walkforward-*.md`). SHADOW: nothing is suppressed. Same §8 metrics; a POSITIVE `killed (suppressed)` row means the live tape disagrees with the backtest — do not flip to active._

| variant | trades | decided | win% | Sharpe | maxDD R | total-R | mean expR | reach1R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| baseline (all live signals) | 220 | 106 | 37% | +0.015 | 8.8 | +2.8 | +0.027 | 28% |
| gated (kept — would trade) | 118 | 62 | 37% | +0.050 | 4.7 | +5.5 | +0.089 | 29% |
| killed (suppressed) | 102 | 44 | 36% | -0.033 | 8.4 | -2.7 | -0.061 | 26% |

**Flip readiness:** ✅ READY — 44 resolved suppressed trades, net-negative (-0.061); gating lifts expectancy +0.027→+0.089 — READY for §8 sign-off + flip. Review checkpoint 2026-09-15 (the real trigger is the count, not the date); flipping also requires explicit user §8 sign-off.

**Verdict:** Consistent with the backtest: gating lifts live expectancy +0.027→+0.089 and the suppressed set is net-negative (-0.061). See the **Flip readiness** line for the sign-off bar.

