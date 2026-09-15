# Regime-gate shadow (live cohort) — 2026-08-31

_Read-only. What the regime overlay (skip: transitional (20–25)) WOULD do to the live tradeable cohort since 2026-07-19 — the forward, live counterpart to the §8 backtest (`gate-walkforward-*.md`). SHADOW: nothing is suppressed. Same §8 metrics; a POSITIVE `killed (suppressed)` row means the live tape disagrees with the backtest — do not flip to active._

| variant | trades | decided | win% | Sharpe | maxDD R | total-R | mean expR | reach1R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| baseline (all live signals) | 427 | 220 | 33% | +0.014 | 16.7 | +5.7 | +0.026 | 30% |
| gated (kept — would trade) | 240 | 136 | 32% | -0.008 | 29.4 | -1.8 | -0.013 | 28% |
| killed (suppressed) | 187 | 84 | 36% | +0.043 | 11.2 | +7.4 | +0.088 | 32% |

**Flip readiness:** ⏳ NOT READY — 84 resolved suppressed trades but the suppressed set is not net-negative (+0.088 expR) — the live tape disagrees with the backtest; do NOT flip. Review checkpoint 2026-09-15 (the real trigger is the count, not the date); flipping also requires explicit user §8 sign-off.

**Verdict:** ⚠ Suppressed trades are POSITIVE (+0.088 expR) on the live tape — the backtest finding is NOT reproducing live. Do not flip to active.

