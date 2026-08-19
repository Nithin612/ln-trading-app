# Regime-gate shadow (live cohort) — 2026-08-18

_Read-only. What the regime overlay (skip: transitional (20–25)) WOULD do to the live tradeable cohort since 2026-07-19 — the forward, live counterpart to the §8 backtest (`gate-walkforward-*.md`). SHADOW: nothing is suppressed. Same §8 metrics; a POSITIVE `killed (suppressed)` row means the live tape disagrees with the backtest — do not flip to active._

| variant | trades | decided | win% | Sharpe | maxDD R | total-R | mean expR | reach1R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| baseline (all live signals) | 276 | 129 | 33% | -0.014 | 9.8 | -3.5 | -0.027 | 26% |
| gated (kept — would trade) | 158 | 81 | 31% | -0.058 | 9.3 | -7.8 | -0.096 | 25% |
| killed (suppressed) | 118 | 48 | 35% | +0.039 | 6.2 | +4.3 | +0.090 | 26% |

**Flip readiness:** ⏳ NOT READY — 48 resolved suppressed trades but the suppressed set is not net-negative (+0.090 expR) — the live tape disagrees with the backtest; do NOT flip. Review checkpoint 2026-09-15 (the real trigger is the count, not the date); flipping also requires explicit user §8 sign-off.

**Verdict:** ⚠ Suppressed trades are POSITIVE (+0.090 expR) on the live tape — the backtest finding is NOT reproducing live. Do not flip to active.

