# Regime-gate shadow (live cohort) — 2026-09-15

_Read-only. What the regime overlay (skip: transitional (20–25)) WOULD do to the live tradeable cohort since 2026-07-19 — the forward, live counterpart to the §8 backtest (`gate-walkforward-*.md`). SHADOW: nothing is suppressed. (Mode as of report time, effective 2026-09-02 — the cohort below may span an earlier period under a DIFFERENT mode; check the changelog before reading a suppressed-set number as counterfactual.) Same §8 metrics; a POSITIVE `killed (suppressed)` row means the live tape disagrees with the backtest — do not flip to active._

| variant | trades | decided | win% | Sharpe | maxDD R | total-R | mean expR | reach1R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| baseline (all live signals) | 4 | 4 | 0% | — | 4.0 | -4.0 | -1.000 | 25% |
| gated (kept — would trade) | 1 | 1 | 0% | — | 1.0 | -1.0 | -1.000 | 0% |
| killed (suppressed) | 3 | 3 | 0% | — | 3.0 | -3.0 | -1.000 | 33% |

**Flip readiness:** ⏳ NOT READY — 3/20 resolved suppressed trades — keep accruing. Review checkpoint 2026-09-15 (the real trigger is the count, not the date); flipping also requires explicit user §8 sign-off.

**Verdict:** Gating does not lift live expectancy yet — keep measuring before any flip.

