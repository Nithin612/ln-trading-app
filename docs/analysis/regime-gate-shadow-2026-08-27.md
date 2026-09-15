# Regime-gate shadow (live cohort) — 2026-08-27

_Read-only. What the regime overlay (skip: transitional (20–25)) WOULD do to the live tradeable cohort since 2026-07-19 — the forward, live counterpart to the §8 backtest (`gate-walkforward-*.md`). SHADOW: nothing is suppressed. Same §8 metrics; a POSITIVE `killed (suppressed)` row means the live tape disagrees with the backtest — do not flip to active._

| variant | trades | decided | win% | Sharpe | maxDD R | total-R | mean expR | reach1R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| baseline (all live signals) | 377 | 182 | 32% | +0.018 | 16.6 | +6.3 | +0.035 | 27% |
| gated (kept — would trade) | 220 | 120 | 30% | -0.016 | 25.5 | -3.4 | -0.028 | 27% |
| killed (suppressed) | 157 | 62 | 37% | +0.070 | 9.2 | +9.7 | +0.156 | 27% |

**Flip readiness:** ⏳ NOT READY — 62 resolved suppressed trades but the suppressed set is not net-negative (+0.156 expR) — the live tape disagrees with the backtest; do NOT flip. Review checkpoint 2026-09-15 (the real trigger is the count, not the date); flipping also requires explicit user §8 sign-off.

**Verdict:** ⚠ Suppressed trades are POSITIVE (+0.156 expR) on the live tape — the backtest finding is NOT reproducing live. Do not flip to active.

