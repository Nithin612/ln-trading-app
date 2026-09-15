# Regime-gate shadow (live cohort) — 2026-08-21

_Read-only. What the regime overlay (skip: transitional (20–25)) WOULD do to the live tradeable cohort since 2026-07-19 — the forward, live counterpart to the §8 backtest (`gate-walkforward-*.md`). SHADOW: nothing is suppressed. Same §8 metrics; a POSITIVE `killed (suppressed)` row means the live tape disagrees with the backtest — do not flip to active._

| variant | trades | decided | win% | Sharpe | maxDD R | total-R | mean expR | reach1R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| baseline (all live signals) | 347 | 155 | 34% | +0.049 | 10.8 | +15.2 | +0.098 | 26% |
| gated (kept — would trade) | 200 | 101 | 34% | +0.039 | 11.5 | +7.1 | +0.070 | 25% |
| killed (suppressed) | 147 | 54 | 35% | +0.064 | 7.2 | +8.1 | +0.150 | 26% |

**Flip readiness:** ⏳ NOT READY — 54 resolved suppressed trades but the suppressed set is not net-negative (+0.150 expR) — the live tape disagrees with the backtest; do NOT flip. Review checkpoint 2026-09-15 (the real trigger is the count, not the date); flipping also requires explicit user §8 sign-off.

**Verdict:** ⚠ Suppressed trades are POSITIVE (+0.150 expR) on the live tape — the backtest finding is NOT reproducing live. Do not flip to active.

