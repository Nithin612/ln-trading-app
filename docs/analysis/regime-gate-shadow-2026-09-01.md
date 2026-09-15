# Regime-gate shadow (live cohort) — 2026-09-01

_Read-only. What the regime overlay (skip: transitional (20–25)) WOULD do to the live tradeable cohort since 2026-07-19 — the forward, live counterpart to the §8 backtest (`gate-walkforward-*.md`). SHADOW: nothing is suppressed. (Mode as of report time, effective 2026-09-02 — the cohort below may span an earlier period under a DIFFERENT mode; check the changelog before reading a suppressed-set number as counterfactual.) Same §8 metrics; a POSITIVE `killed (suppressed)` row means the live tape disagrees with the backtest — do not flip to active._

| variant | trades | decided | win% | Sharpe | maxDD R | total-R | mean expR | reach1R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| baseline (all live signals) | 464 | 243 | 32% | +0.004 | 15.9 | +2.0 | +0.008 | 29% |
| gated (kept — would trade) | 265 | 152 | 30% | -0.018 | 33.5 | -5.1 | -0.033 | 28% |
| killed (suppressed) | 199 | 91 | 36% | +0.039 | 11.2 | +7.1 | +0.078 | 31% |

**Flip readiness:** ⏳ NOT READY — 91 resolved suppressed trades but the suppressed set is not net-negative (+0.078 expR) — the live tape disagrees with the backtest; do NOT flip. Review checkpoint 2026-09-15 (the real trigger is the count, not the date); flipping also requires explicit user §8 sign-off.

**Verdict:** ⚠ Suppressed trades are POSITIVE (+0.078 expR) on the live tape — the backtest finding is NOT reproducing live. Do not flip to active.

