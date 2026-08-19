# Regime-gate shadow (live cohort) — 2026-08-19

_Read-only. What the regime overlay (skip: transitional (20–25)) WOULD do to the live tradeable cohort since 2026-07-19 — the forward, live counterpart to the §8 backtest (`gate-walkforward-*.md`). SHADOW: nothing is suppressed. Same §8 metrics; a POSITIVE `killed (suppressed)` row means the live tape disagrees with the backtest — do not flip to active._

| variant | trades | decided | win% | Sharpe | maxDD R | total-R | mean expR | reach1R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| baseline (all live signals) | 308 | 146 | 32% | -0.006 | 10.8 | -1.7 | -0.012 | 26% |
| gated (kept — would trade) | 174 | 92 | 30% | -0.065 | 10.3 | -9.8 | -0.107 | 26% |
| killed (suppressed) | 134 | 54 | 35% | +0.064 | 7.2 | +8.1 | +0.150 | 27% |

**Flip readiness:** ⏳ NOT READY — 54 resolved suppressed trades but the suppressed set is not net-negative (+0.150 expR) — the live tape disagrees with the backtest; do NOT flip. Review checkpoint 2026-09-15 (the real trigger is the count, not the date); flipping also requires explicit user §8 sign-off.

**Verdict:** ⚠ Suppressed trades are POSITIVE (+0.150 expR) on the live tape — the backtest finding is NOT reproducing live. Do not flip to active.

