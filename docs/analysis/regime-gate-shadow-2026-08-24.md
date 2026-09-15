# Regime-gate shadow (live cohort) — 2026-08-24

_Read-only. What the regime overlay (skip: transitional (20–25)) WOULD do to the live tradeable cohort since 2026-07-19 — the forward, live counterpart to the §8 backtest (`gate-walkforward-*.md`). SHADOW: nothing is suppressed. Same §8 metrics; a POSITIVE `killed (suppressed)` row means the live tape disagrees with the backtest — do not flip to active._

| variant | trades | decided | win% | Sharpe | maxDD R | total-R | mean expR | reach1R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| baseline (all live signals) | 352 | 159 | 35% | +0.061 | 10.8 | +19.7 | +0.124 | 26% |
| gated (kept — would trade) | 204 | 104 | 35% | +0.066 | 12.5 | +12.6 | +0.121 | 26% |
| killed (suppressed) | 148 | 55 | 35% | +0.055 | 8.2 | +7.1 | +0.130 | 26% |

**Flip readiness:** ⏳ NOT READY — 55 resolved suppressed trades but the suppressed set is not net-negative (+0.130 expR) — the live tape disagrees with the backtest; do NOT flip. Review checkpoint 2026-09-15 (the real trigger is the count, not the date); flipping also requires explicit user §8 sign-off.

**Verdict:** ⚠ Suppressed trades are POSITIVE (+0.130 expR) on the live tape — the backtest finding is NOT reproducing live. Do not flip to active.

