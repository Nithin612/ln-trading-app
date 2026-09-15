# Regime-gate shadow (live cohort) — 2026-08-26

_Read-only. What the regime overlay (skip: transitional (20–25)) WOULD do to the live tradeable cohort since 2026-07-19 — the forward, live counterpart to the §8 backtest (`gate-walkforward-*.md`). SHADOW: nothing is suppressed. Same §8 metrics; a POSITIVE `killed (suppressed)` row means the live tape disagrees with the backtest — do not flip to active._

| variant | trades | decided | win% | Sharpe | maxDD R | total-R | mean expR | reach1R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| baseline (all live signals) | 364 | 169 | 34% | +0.050 | 11.1 | +16.8 | +0.099 | 26% |
| gated (kept — would trade) | 208 | 108 | 33% | +0.044 | 16.5 | +8.6 | +0.080 | 25% |
| killed (suppressed) | 156 | 61 | 36% | +0.059 | 9.2 | +8.2 | +0.134 | 26% |

**Flip readiness:** ⏳ NOT READY — 61 resolved suppressed trades but the suppressed set is not net-negative (+0.134 expR) — the live tape disagrees with the backtest; do NOT flip. Review checkpoint 2026-09-15 (the real trigger is the count, not the date); flipping also requires explicit user §8 sign-off.

**Verdict:** ⚠ Suppressed trades are POSITIVE (+0.134 expR) on the live tape — the backtest finding is NOT reproducing live. Do not flip to active.

